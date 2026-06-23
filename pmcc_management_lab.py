#!/usr/bin/env python3
"""PMCC management laboratory — simulate rip-then-drop whipsaw scenarios.

Tests the core question: how do different management rules perform when TSLA
rips up then comes back down? Sweeps roll timing, roll target, harvest rules,
and short strike distance to find the optimal configuration.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from itertools import product

import pandas as pd

from pmcc.daily_playthrough import (
    DailyPlayPath,
    MonthPoint,
    build_daily_paths,
    daily_policy,
    run_all_daily_paths,
    run_daily_path,
    pnl_return_pct,
)
from pmcc.paths import CANONICAL_PATHS
from pmcc.playthrough import PlayPolicy, POLICY_BY_PRESET
from pmcc.scenarios import PmccPair


# ---------------------------------------------------------------------------
# Custom paths — the scenarios the trader cares about
# ---------------------------------------------------------------------------

def rip_pullback_daily(leaps_dte: int, *, rip_pct: float = 0.15,
                       drop_to: float = 1.0, rip_day: int = 45,
                       flush_days: int = 7) -> DailyPlayPath:
    """Rip up then drop back — the covered-call curse.

    Flat → +15% gap → flush back to entry over 7 days → flat rest of life.
    This is the scenario that burns covered call sellers: you roll up (pay
    tax), then the stock drops back and your new short is far OTM.
    """
    days: list[MonthPoint] = []
    rip_spot = 1.0 * (1 + rip_pct)
    for d in range(1, leaps_dte + 1):
        if d < rip_day:
            spot = 1.0
        elif d == rip_day:
            spot = rip_spot
        elif rip_day < d <= rip_day + flush_days:
            t = (d - rip_day) / flush_days
            spot = rip_spot + t * (drop_to - rip_spot)
        else:
            spot = drop_to
        iv = max(0.75, 1.15 - 0.10 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "rip_pullback",
        f"+{rip_pct:.0%} rip d{rip_day} then flush to {drop_to:.0%}",
        tuple(days),
    )


def rip_continue_daily(leaps_dte: int, *, rip_pct: float = 0.15,
                       end_mult: float = 1.50, rip_day: int = 45) -> DailyPlayPath:
    """Rip up and continue grinding — the TSLA bull case over 2 years."""
    days: list[MonthPoint] = []
    rip_spot = 1.0 * (1 + rip_pct)
    for d in range(1, leaps_dte + 1):
        if d < rip_day:
            spot = 1.0
        elif d == rip_day:
            spot = rip_spot
        else:
            t = (d - rip_day) / max(leaps_dte - rip_day, 1)
            spot = rip_spot + t * (end_mult - rip_spot)
        iv = max(0.65, 1.05 - 0.12 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "rip_continue",
        f"+{rip_pct:.0%} rip d{rip_day} then grind to +{(end_mult-1):.0%}",
        tuple(days),
    )


def flat_survival_daily(leaps_dte: int) -> DailyPlayPath:
    """Flat ±3% for entire LEAPS life — pure theta survival test."""
    import math
    days: list[MonthPoint] = []
    for d in range(1, leaps_dte + 1):
        spot = 1.0 + 0.03 * math.sin(d / 21.0)
        iv = 1.0
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "flat_survival",
        "Flat ±3% sine wave — pure theta test",
        tuple(days),
    )


def whipsaw_triple_daily(leaps_dte: int) -> DailyPlayPath:
    """Three rip-flush cycles — the worst case for roll tax."""
    rips = {45: 0.12, 150: 0.10, 270: 0.08}
    flush_cfg = {45: (7, -0.09), 150: (7, -0.07), 270: (5, -0.06)}
    days: list[MonthPoint] = []
    spot = 1.0
    flush_state = None
    for d in range(1, leaps_dte + 1):
        if flush_state is not None:
            start, end, left, total = flush_state
            step = total - left + 1
            spot = start + (step / total) * (end - start)
            left -= 1
            flush_state = (start, end, left, total) if left > 0 else None
        elif d in rips:
            spot *= 1 + rips[d]
            n, pct = flush_cfg[d]
            flush_state = (spot, spot * (1 + pct), n, n)
        else:
            spot *= 1.0005
        iv = max(0.78, 1.10 - 0.06 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "whipsaw_triple",
        "Three rip+flush cycles (d45/d150/d270)",
        tuple(days),
    )


def build_lab_paths(leaps_dte: int) -> tuple[DailyPlayPath, ...]:
    """All paths for the management lab — custom + key canonical."""
    custom = (
        rip_pullback_daily(leaps_dte),
        rip_pullback_daily(leaps_dte, drop_to=0.92, rip_pct=0.15),
        rip_continue_daily(leaps_dte),
        rip_continue_daily(leaps_dte, end_mult=1.90),  # moonshot-like
        flat_survival_daily(leaps_dte),
        whipsaw_triple_daily(leaps_dte),
    )
    # Add key canonical daily paths
    all_daily = build_daily_paths(leaps_dte)
    canonical_keep = {"steady_bull", "moonshot", "single_day_rip_10",
                      "gap_rip_flush", "gap_whipsaw_double", "post_earnings_whipsaw",
                      "tsla_range_chop", "flat_chop", "steady_bear", "crash_recover",
                      "v_recovery"}
    canonical = tuple(p for p in all_daily if p.name in canonical_keep)
    return custom + canonical


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def make_pair(spot: float, leaps_strike: float, short_strike: float,
              leaps_dte: int, short_dte: int, leaps_debit: float,
              short_credit: float, *, leaps_iv: float = 0.55,
              short_iv: float = 0.45) -> PmccPair:
    return PmccPair(
        spot_entry=spot, leaps_strike=leaps_strike, leaps_exp="2028-01-21",
        leaps_dte=leaps_dte, leaps_iv=leaps_iv, leaps_debit=leaps_debit,
        short_strike=short_strike, short_exp="2026-09-19",
        short_dte=short_dte, short_iv=short_iv, short_credit=short_credit,
        leaps_delta_target=0.70, short_delta_target=0.20,
    )


def run_scenario(pair: PmccPair, path: DailyPlayPath, policy: PlayPolicy,
                 *, r: float = 0.04) -> pd.DataFrame:
    return run_daily_path(pair, path, policy, r=r)


def pnl_at_leaps_dte(df: pd.DataFrame, target_dte: int) -> dict | None:
    """P/L decomposition when LEAPS DTE first crosses below target_dte."""
    sub = df[df["leaps_dte"] <= target_dte]
    if sub.empty:
        return None
    row = sub.iloc[0]
    return {
        "day": int(row["day"]),
        "leaps_dte": int(row["leaps_dte"]),
        "spot": float(row["spot"]),
        "net_pnl": float(row["net_pnl"]),
        "realized_short": float(row["realized_short_pnl"]),
        "roll_tax": float(row["roll_tax"]),
        "roll_count": int(row["roll_count"]),
    }


def format_trade_log(df: pd.DataFrame, path_name: str, *, max_rows: int = 35) -> str:
    sub = df[df["path"] == path_name].copy()
    if sub.empty:
        return f"(no data for {path_name})"
    action_mask = sub["action"].str.contains(
        "CHALLENGED|GAP RIP|ROLL|CRASH|LEAPS EXPIRE|DROP|SELL new|FLUSH|harvest",
        case=False, regex=True,
    )
    keep = sub[action_mask | (sub["day"] % 30 == 0) | (sub["day"] == sub["day"].max())]
    keep = keep.drop_duplicates(subset=["day"]).head(max_rows)
    view = keep[["day", "spot", "leaps_dte", "short_strike", "short_dte",
                 "net_pnl", "roll_tax", "action"]].copy()
    view["spot"] = view["spot"].map(lambda x: f"${x:,.0f}")
    view["net_pnl"] = view["net_pnl"].map(lambda x: f"${x:+,.0f}")
    view["roll_tax"] = view["roll_tax"].map(lambda x: f"${x:,.0f}")
    return view.to_string(index=False)


# ---------------------------------------------------------------------------
# Sweeps
# ---------------------------------------------------------------------------

def sweep_parameter(pair: PmccPair, paths: tuple[DailyPlayPath, ...],
                    base_policy: PlayPolicy, param_name: str,
                    values: tuple, *, r: float = 0.04) -> pd.DataFrame:
    rows = []
    for val in values:
        policy = replace(base_policy, **{param_name: val})
        pol = daily_policy(policy)
        _, summary = run_all_daily_paths(pair, paths, pol, r=r)
        by_path = {row["path"]: float(row["final_pnl"]) for _, row in summary.iterrows()}
        roll_dte_180 = None
        for p in paths:
            df = run_daily_path(pair, p, pol, r=r)
            info = pnl_at_leaps_dte(df, 180)
            if info and p.name == paths[0].name:
                roll_dte_180 = info
        row = {
            param_name: val,
            "rip_pullback": pnl_return_pct(by_path.get("rip_pullback", 0), pair.net_debit),
            "rip_continue": pnl_return_pct(by_path.get("rip_continue", 0), pair.net_debit),
            "whipsaw_triple": pnl_return_pct(by_path.get("whipsaw_triple", 0), pair.net_debit),
            "gap_rip_flush": pnl_return_pct(by_path.get("gap_rip_flush", 0), pair.net_debit),
            "gap_whipsaw": pnl_return_pct(by_path.get("gap_whipsaw_double", 0), pair.net_debit),
            "flat_chop": pnl_return_pct(by_path.get("flat_chop", 0), pair.net_debit),
            "steady_bull": pnl_return_pct(by_path.get("steady_bull", 0), pair.net_debit),
            "moonshot": pnl_return_pct(by_path.get("moonshot", 0), pair.net_debit),
            "steady_bear": pnl_return_pct(by_path.get("steady_bear", 0), pair.net_debit),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def sweep_short_distance(spot: float, leaps_strike: float, short_strikes: tuple,
                         leaps_dte: int, short_dte: int, leaps_debit: float,
                         paths: tuple[DailyPlayPath, ...], policy: PlayPolicy,
                         *, r: float = 0.04) -> pd.DataFrame:
    rows = []
    for ss in short_strikes:
        # Estimate short credit from BS at entry
        import pricing
        short_iv = 0.45
        T = short_dte / 365.0
        short_px = max(pricing.price(spot, ss, T, short_iv, "call", r=r), 0.01)
        short_credit = short_px * 0.97 * 100.0
        pair = make_pair(spot, leaps_strike, ss, leaps_dte, short_dte,
                         leaps_debit, short_credit, short_iv=short_iv)
        pol = daily_policy(policy)
        _, summary = run_all_daily_paths(pair, paths, pol, r=r)
        by_path = {row["path"]: float(row["final_pnl"]) for _, row in summary.iterrows()}
        otm_pct = (ss - spot) / spot * 100
        rows.append({
            "short_strike": ss,
            "otm_pct": otm_pct,
            "short_credit": short_credit,
            "coverage_pct": short_credit / leaps_debit * 100,
            "rip_pullback": pnl_return_pct(by_path.get("rip_pullback", 0), pair.net_debit),
            "rip_continue": pnl_return_pct(by_path.get("rip_continue", 0), pair.net_debit),
            "whipsaw_triple": pnl_return_pct(by_path.get("whipsaw_triple", 0), pair.net_debit),
            "flat_chop": pnl_return_pct(by_path.get("flat_chop", 0), pair.net_debit),
            "steady_bull": pnl_return_pct(by_path.get("steady_bull", 0), pair.net_debit),
            "moonshot": pnl_return_pct(by_path.get("moonshot", 0), pair.net_debit),
            "steady_bear": pnl_return_pct(by_path.get("steady_bear", 0), pair.net_debit),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC management rule laboratory")
    ap.add_argument("--spot", type=float, default=400.49)
    ap.add_argument("--leaps-strike", type=float, default=420.0)
    ap.add_argument("--short-strike", type=float, default=520.0)
    ap.add_argument("--leaps-dte", type=int, default=726)
    ap.add_argument("--short-dte", type=int, default=89)
    ap.add_argument("--leaps-debit", type=float, default=12385.0)
    ap.add_argument("--short-credit", type=float, default=800.0)
    ap.add_argument("--preset", default="managed",
                    choices=("income", "balanced", "bullish", "managed"))
    ap.add_argument("--show-logs", action="store_true",
                    help="show trade-by-trade logs for key paths")
    ap.add_argument("--sweep", action="store_true",
                    help="run parameter sweeps")
    args = ap.parse_args()

    spot = args.spot
    pair = make_pair(spot, args.leaps_strike, args.short_strike,
                     args.leaps_dte, args.short_dte, args.leaps_debit,
                     args.short_credit)
    base_policy = POLICY_BY_PRESET[args.preset]
    paths = build_lab_paths(args.leaps_dte)

    print(f"\n{'='*70}")
    print(f"PMCC MANAGEMENT LAB")
    print(f"{'='*70}")
    print(f"Pair: {int(args.leaps_strike)}/{int(args.short_strike)} "
          f"(LEAPS {args.leaps_dte}d, short {args.short_dte}d)")
    print(f"Spot: ${spot:.2f}  LEAPS debit: ${args.leaps_debit:,.0f}  "
          f"Short credit: ${args.short_credit:,.0f}")
    print(f"Net debit: ${pair.net_debit:,.0f}  Coverage: "
          f"{args.short_credit/args.leaps_debit*100:.1f}%")
    print(f"Preset: {args.preset}")
    print(f"Short OTM: {(args.short_strike - spot)/spot*100:.0f}%")
    print()

    # --- Base case: P/L summary across all paths ---
    pol = daily_policy(base_policy)
    _, summary = run_all_daily_paths(pair, paths, pol, r=0.04)
    cap = pair.net_debit

    print(f"{'BASE CASE — P/L by path (% return on net debit)':^70}")
    print("-" * 70)
    summary["pnl_pct"] = summary["final_pnl"].apply(lambda x: pnl_return_pct(x, cap))
    summary = summary.sort_values("pnl_pct", ascending=False)
    for _, row in summary.iterrows():
        flag = ""
        if "rip" in row["path"] or "whip" in row["path"]:
            flag = " ← whipsaw"
        elif "flat" in row["path"]:
            flag = " ← survival"
        elif "bear" in row["path"] or "crash" in row["path"]:
            flag = " ← bear"
        elif "bull" in row["path"] or "moon" in row["path"]:
            flag = " ← bull"
        print(f"  {row['path']:<26} {row['pnl_pct']:+8.1f}%  "
              f"({row['final_pnl']:+,.0f})  rolls={row['roll_count']:.0f}"
              f"  roll_tax=${row['roll_tax']:,.0f}{flag}")

    # --- LEAPS roll point analysis ---
    print(f"\n{'LEAPS ROLL POINT ANALYSIS (P/L if you exit at 180 DTE vs expiry)':^70}")
    print("-" * 70)
    print(f"{'path':<26} {'@180d DTE':>10} {'@expiry':>10} {'difference':>12}")
    for p in paths:
        df = run_daily_path(pair, p, pol, r=0.04)
        info = pnl_at_leaps_dte(df, 180)
        final_row = df.iloc[-1]
        pnl_180 = pnl_return_pct(info["net_pnl"], cap) if info else float("nan")
        pnl_final = pnl_return_pct(final_row["net_pnl"], cap)
        diff = pnl_180 - pnl_final if info else float("nan")
        print(f"  {p.name:<26} {pnl_180:+8.1f}%  {pnl_final:+8.1f}%  {diff:+10.1f}%")

    # --- Trade logs ---
    if args.show_logs:
        for path_name in ("rip_pullback", "rip_continue", "whipsaw_triple",
                          "gap_whipsaw_double", "flat_chop"):
            df = run_daily_path(pair, next(p for p in paths if p.name == path_name), pol, r=0.04)
            print(f"\n{'TRADE LOG — ' + path_name:^70}")
            print("-" * 70)
            print(format_trade_log(df, path_name))

    # --- Sweeps ---
    if args.sweep:
        print(f"\n{'='*70}")
        print(f"PARAMETER SWEEPS")
        print(f"{'='*70}")

        sweeps = [
            ("challenged_pct", (0.90, 0.92, 0.96, 1.00), "When to roll (lower = earlier, less tax)"),
            ("roll_up_pct", (0.06, 0.08, 0.10, 0.12, 0.15), "How far up to roll"),
            ("gap_rip_trigger_pct", (0.06, 0.08, 0.10, 0.12), "Proactive gap-rip roll trigger"),
            ("harvest_profit_pct", (0.40, 0.50, 0.55, 0.60, 0.70), "General harvest target"),
            ("flush_harvest_min_profit", (0.25, 0.35, 0.50), "Pullback harvest profit floor"),
            ("reentry_cooldown_days", (3, 7, 14, 21, 30), "Cooldown after harvest/flush"),
            ("min_roll_gap_days", (3, 7, 12, 18, 25), "Min days between rolls"),
        ]

        for param, values, desc in sweeps:
            print(f"\n--- {param}: {desc} ---")
            result = sweep_parameter(pair, paths, base_policy, param, values, r=0.04)
            cols = [param, "rip_pullback", "rip_continue", "whipsaw_triple",
                    "gap_whipsaw", "flat_chop", "steady_bull", "moonshot", "steady_bear"]
            cols = [c for c in cols if c in result.columns]
            for c in cols[1:]:
                result[c] = result[c].map(lambda x: f"{x:+.1f}%")
            print(result[cols].to_string(index=False))

        # --- Short strike distance sweep ---
        print(f"\n--- short_strike distance: further = easier to manage? ---")
        short_strikes = tuple(spot * (1 + pct) for pct in
                              (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50))
        # Round to nearest 10
        short_strikes = tuple(float(int(s / 10) * 10) for s in short_strikes)
        result = sweep_short_distance(spot, args.leaps_strike, short_strikes,
                                      args.leaps_dte, args.short_dte,
                                      args.leaps_debit, paths, base_policy, r=0.04)
        cols = ["short_strike", "otm_pct", "short_credit", "coverage_pct",
                "rip_pullback", "rip_continue", "whipsaw_triple",
                "flat_chop", "steady_bull", "moonshot", "steady_bear"]
        for c in cols[4:]:
            result[c] = result[c].map(lambda x: f"{x:+.1f}%")
        result["short_credit"] = result["short_credit"].map(lambda x: f"${x:,.0f}")
        result["coverage_pct"] = result["coverage_pct"].map(lambda x: f"{x:.1f}%")
        print(result[cols].to_string(index=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Integrated PMCC scoring with conditional LEAPS roll + parameter sweeps.

Replaces the hold-to-expiry scoring with conditional-roll scoring.
Sweeps short strike distance, LEAPS DTE, and roll DTE to find optimal config.
"""

from __future__ import annotations

import math
import argparse
from dataclasses import replace
from itertools import product
from pathlib import Path

import pandas as pd
import pricing

from pmcc.daily_playthrough import (
    DailyPlayPath,
    MonthPoint,
    build_daily_paths,
    daily_policy,
    run_daily_path,
    run_all_daily_paths,
    pnl_return_pct,
)
from pmcc.playthrough import PlayPolicy, POLICY_BY_PRESET, _px, _strike_for_delta
from pmcc.scenarios import PmccPair
from pmcc.config import apply_preset, PmccConfig


# ---------------------------------------------------------------------------
# Conditional LEAPS roll P/L computation
# ---------------------------------------------------------------------------

def conditional_roll_pnl(
    pair: PmccPair,
    path: DailyPlayPath,
    policy: PlayPolicy,
    *,
    roll_dte: int = 365,
    deep_itm_threshold: float = 1.25,
    r: float = 0.04,
) -> dict:
    """P/L with conditional LEAPS roll.

    At roll_dte remaining on LEAPS:
      - If LEAPS is deep ITM (spot/strike >= threshold): hold to expiry (capture upside)
      - Otherwise: take P/L at roll point (avoid theta cliff)

    The roll point P/L is conservative — it includes the LEAPS mark at that
    point (capturing remaining time value) plus all realized short P/L.
    Cycle 2 (new LEAPS) would add more, but we measure cycle 1 alone to
    keep comparisons fair across different initial DTEs.
    """
    pol = daily_policy(policy)
    df = run_daily_path(pair, path, pol, r=r)
    if df.empty:
        return {"pnl": 0.0, "pnl_pct": 0.0, "mode": "empty"}

    final = df.iloc[-1]
    hold_pnl = float(final["net_pnl"])
    hold_pct = pnl_return_pct(hold_pnl, pair.net_debit)

    roll_mask = df["leaps_dte"] <= roll_dte
    if not roll_mask.any():
        return {"pnl": hold_pnl, "pnl_pct": hold_pct, "mode": "hold"}

    roll_row = df[roll_mask].iloc[0]
    roll_spot = float(roll_row["spot"])
    roll_pnl = float(roll_row["net_pnl"])
    roll_pct = pnl_return_pct(roll_pnl, pair.net_debit)

    moneyness = roll_spot / pair.leaps_strike
    if moneyness >= deep_itm_threshold:
        return {"pnl": hold_pnl, "pnl_pct": hold_pct, "mode": "hold_deep_itm",
                "roll_spot": roll_spot, "moneyness": moneyness}
    return {"pnl": roll_pnl, "pnl_pct": roll_pct, "mode": "roll",
            "roll_spot": roll_spot, "moneyness": moneyness}


# ---------------------------------------------------------------------------
# Custom paths — the scenarios the trader cares about
# ---------------------------------------------------------------------------

def make_rip_pullback(leaps_dte: int, *, rip_pct: float = 0.15,
                      drop_to: float = 1.0, rip_day: int = 45) -> DailyPlayPath:
    days: list[MonthPoint] = []
    rip_spot = 1.0 * (1 + rip_pct)
    flush_days = 7
    for d in range(1, leaps_dte + 1):
        if d < rip_day:
            s = 1.0
        elif d == rip_day:
            s = rip_spot
        elif d <= rip_day + flush_days:
            t = (d - rip_day) / flush_days
            s = rip_spot + t * (drop_to - rip_spot)
        else:
            s = drop_to
        iv = max(0.75, 1.15 - 0.10 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    return DailyPlayPath("rip_pullback",
        f"+{rip_pct:.0%} rip d{rip_day} then flush to {drop_to:.0%}", tuple(days))


def make_rip_continue(leaps_dte: int, *, rip_pct: float = 0.15,
                      end_mult: float = 1.50, rip_day: int = 45) -> DailyPlayPath:
    days: list[MonthPoint] = []
    rip_spot = 1.0 * (1 + rip_pct)
    for d in range(1, leaps_dte + 1):
        if d < rip_day:
            s = 1.0
        elif d == rip_day:
            s = rip_spot
        else:
            t = (d - rip_day) / max(leaps_dte - rip_day, 1)
            s = rip_spot + t * (end_mult - rip_spot)
        iv = max(0.65, 1.05 - 0.12 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    return DailyPlayPath("rip_continue",
        f"+{rip_pct:.0%} rip d{rip_day} then grind to +{(end_mult-1):.0%}", tuple(days))


def make_flat_survival(leaps_dte: int) -> DailyPlayPath:
    days: list[MonthPoint] = []
    for d in range(1, leaps_dte + 1):
        s = 1.0 + 0.03 * math.sin(d / 21.0)
        days.append(MonthPoint(s, 1.0))
    return DailyPlayPath("flat_survival", "Flat ±3% sine wave", tuple(days))


def make_immediate_rip(leaps_dte: int, *, rip_pct: float = 0.15,
                       days_to_rip: int = 3,
                       after: str = "plateau") -> DailyPlayPath:
    """Rip immediately after entry — the worst case for short sellers.

    after: 'plateau' (stays high), 'continue' (keeps going), 'drop' (comes back)
    """
    days: list[MonthPoint] = []
    rip_spot = 1.0 * (1 + rip_pct)
    for d in range(1, leaps_dte + 1):
        if d < days_to_rip:
            s = 1.0
        elif d == days_to_rip:
            s = rip_spot
        elif after == "plateau":
            s = rip_spot
        elif after == "continue":
            t = (d - days_to_rip) / max(leaps_dte - days_to_rip, 1)
            s = rip_spot + t * (1.50 - rip_spot)
        elif after == "drop":
            if d <= days_to_rip + 7:
                t = (d - days_to_rip) / 7
                s = rip_spot + t * (1.0 - rip_spot)
            else:
                s = 1.0
        else:
            s = rip_spot
        iv = max(0.65, 1.20 - 0.10 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    return DailyPlayPath(
        f"imm_rip_{int(rip_pct*100)}_{after}",
        f"+{rip_pct:.0%} in {days_to_rip}d then {after}", tuple(days))


def make_double_rip(leaps_dte: int, *, rip1_pct: float = 0.15,
                    rip1_day: int = 3, rip2_pct: float = 0.10,
                    rip2_day: int = 10) -> DailyPlayPath:
    """Two rips in quick succession — the TSLA +20-30% in a week scenario."""
    days: list[MonthPoint] = []
    for d in range(1, leaps_dte + 1):
        if d < rip1_day:
            s = 1.0
        elif d == rip1_day:
            s = 1.0 * (1 + rip1_pct)
        elif d < rip2_day:
            s = 1.0 * (1 + rip1_pct)
        elif d == rip2_day:
            s = 1.0 * (1 + rip1_pct) * (1 + rip2_pct)
        else:
            t = (d - rip2_day) / max(leaps_dte - rip2_day, 1)
            # Slight upward drift after
            s = 1.0 * (1 + rip1_pct) * (1 + rip2_pct) * (1 + t * 0.10)
        iv = max(0.60, 1.25 - 0.12 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    total_rip = (1 + rip1_pct) * (1 + rip2_pct) - 1
    return DailyPlayPath(
        f"double_rip_{int(total_rip*100)}",
        f"+{rip1_pct:.0%} d{rip1_day} then +{rip2_pct:.0%} d{rip2_day} = +{total_rip:.0%} total",
        tuple(days),
    )


def build_all_paths(leaps_dte: int) -> tuple[DailyPlayPath, ...]:
    """All paths for integrated scoring."""
    canonical = build_daily_paths(leaps_dte)
    custom = (
        make_rip_pullback(leaps_dte),
        make_rip_pullback(leaps_dte, drop_to=0.92, rip_pct=0.15),
        make_rip_continue(leaps_dte),
        make_rip_continue(leaps_dte, end_mult=1.90),
        make_flat_survival(leaps_dte),
        # Immediate rip scenarios
        make_immediate_rip(leaps_dte, rip_pct=0.10, days_to_rip=3, after="plateau"),
        make_immediate_rip(leaps_dte, rip_pct=0.15, days_to_rip=3, after="plateau"),
        make_immediate_rip(leaps_dte, rip_pct=0.15, days_to_rip=3, after="continue"),
        make_immediate_rip(leaps_dte, rip_pct=0.15, days_to_rip=3, after="drop"),
        make_immediate_rip(leaps_dte, rip_pct=0.20, days_to_rip=5, after="plateau"),
        make_immediate_rip(leaps_dte, rip_pct=0.30, days_to_rip=7, after="plateau"),
        make_immediate_rip(leaps_dte, rip_pct=0.30, days_to_rip=7, after="continue"),
        make_immediate_rip(leaps_dte, rip_pct=0.30, days_to_rip=7, after="drop"),
        # Double rip (the +26.5% in a week scenario)
        make_double_rip(leaps_dte, rip1_pct=0.15, rip2_pct=0.10),
        make_double_rip(leaps_dte, rip1_pct=0.20, rip2_pct=0.10),
    )
    names_seen = {p.name for p in canonical}
    extra = [p for p in custom if p.name not in names_seen]
    return tuple(canonical) + tuple(extra)


# ---------------------------------------------------------------------------
# Scoring with conditional roll
# ---------------------------------------------------------------------------

BULL_PATHS = frozenset({
    "steady_bull", "moonshot", "rip_continue", "v_recovery",
    "single_day_rip_10",
})
WHIPSAW_PATHS = frozenset({
    "gap_whipsaw_double", "post_earnings_whipsaw",
    "rip_pullback", "gap_rip_flush", "tsla_range_chop",
})
FLAT_PATHS = frozenset({"flat_chop", "flat_survival"})
BEAR_PATHS = frozenset({"steady_bear", "crash_recover"})
IMMEDIATE_RIP_PATHS = frozenset({
    "imm_rip_10_plateau", "imm_rip_15_plateau", "imm_rip_15_continue",
    "imm_rip_15_drop", "imm_rip_20_plateau", "imm_rip_30_plateau",
    "imm_rip_30_continue", "imm_rip_30_drop",
    "double_rip_26", "double_rip_31",
})


def score_pair_integrated(
    pair: PmccPair,
    paths: tuple[DailyPlayPath, ...],
    policy: PlayPolicy,
    *,
    roll_dte: int = 365,
    deep_itm_threshold: float = 1.25,
    r: float = 0.04,
    bull_weight: float = 2.0,
    whipsaw_weight: float = 1.5,
    flat_weight: float = 1.0,
    bear_weight: float = 0.5,
    imm_rip_weight: float = 1.0,
) -> dict:
    results = {}
    for p in paths:
        results[p.name] = conditional_roll_pnl(
            pair, p, policy, roll_dte=roll_dte,
            deep_itm_threshold=deep_itm_threshold, r=r,
        )

    def avg(names: set[str], weight_dict: dict[str, float] | None = None) -> float:
        vals = []
        for n in names:
            if n in results:
                v = results[n]["pnl_pct"]
                w = weight_dict.get(n, 1.0) if weight_dict else 1.0
                vals.append((v, w))
        if not vals:
            return 0.0
        total_w = sum(w for _, w in vals)
        return sum(v * w for v, w in vals) / max(total_w, 1e-9)

    bull_avg = avg(BULL_PATHS)
    whipsaw_avg = avg(WHIPSAW_PATHS)
    flat_avg = avg(FLAT_PATHS)
    bear_avg = avg(BEAR_PATHS)
    imm_rip_avg = avg(IMMEDIATE_RIP_PATHS)
    bear_worst = min((results[n]["pnl_pct"] for n in BEAR_PATHS if n in results),
                     default=0.0)
    imm_rip_worst = min((results[n]["pnl_pct"] for n in IMMEDIATE_RIP_PATHS if n in results),
                        default=0.0)

    total_w = bull_weight + whipsaw_weight + flat_weight + bear_weight + imm_rip_weight
    score = (
        bull_avg * bull_weight
        + whipsaw_avg * whipsaw_weight
        + flat_avg * flat_weight
        + bear_avg * bear_weight
        + imm_rip_avg * imm_rip_weight
    ) / total_w

    # Penalties for unacceptable survival
    if flat_avg < -15:
        score -= abs(flat_avg + 15) * 0.5
    if bear_worst < -40:
        score -= abs(bear_worst + 40) * 0.3
    if imm_rip_worst < -20:
        score -= abs(imm_rip_worst + 20) * 0.4

    return {
        "score": score,
        "bull_avg": bull_avg,
        "whipsaw_avg": whipsaw_avg,
        "flat_avg": flat_avg,
        "bear_avg": bear_avg,
        "bear_worst": bear_worst,
        "imm_rip_avg": imm_rip_avg,
        "imm_rip_worst": imm_rip_worst,
        "by_path": results,
    }


# ---------------------------------------------------------------------------
# Pair construction from live chain or synthetic
# ---------------------------------------------------------------------------

def make_pair(spot: float, leaps_strike: float, short_strike: float,
              leaps_dte: int, short_dte: int, *,
              leaps_iv: float = 0.55, short_iv: float = 0.45,
              r: float = 0.04) -> PmccPair:
    leaps_debit = _px(spot, leaps_strike, leaps_dte, leaps_iv, r) * 100.0
    short_credit = _px(spot, short_strike, short_dte, short_iv, r) * 0.97 * 100.0
    return PmccPair(
        spot_entry=spot, leaps_strike=leaps_strike, leaps_exp="2028-01-21",
        leaps_dte=leaps_dte, leaps_iv=leaps_iv, leaps_debit=leaps_debit,
        short_strike=short_strike, short_exp="2026-09-19",
        short_dte=short_dte, short_iv=short_iv, short_credit=short_credit,
        leaps_delta_target=0.70, short_delta_target=0.20,
    )


# ---------------------------------------------------------------------------
# Sweeps
# ---------------------------------------------------------------------------

def sweep_short_distance(spot: float, leaps_strike: float, leaps_dte: int,
                         short_dte: int, otm_pcts: tuple,
                         paths: tuple, policy: PlayPolicy,
                         *, r: float = 0.04) -> pd.DataFrame:
    rows = []
    for otm in otm_pcts:
        ss = float(int(spot * (1 + otm) / 10) * 10)
        pair = make_pair(spot, leaps_strike, ss, leaps_dte, short_dte, r=r)
        s = score_pair_integrated(pair, paths, policy, r=r)
        rows.append({
            "short_strike": ss,
            "otm_pct": otm * 100,
            "short_credit": pair.short_credit,
            "coverage_pct": pair.short_credit / pair.leaps_debit * 100,
            "score": s["score"],
            "bull_avg": s["bull_avg"],
            "whipsaw_avg": s["whipsaw_avg"],
            "flat_avg": s["flat_avg"],
            "bear_worst": s["bear_worst"],
            "imm_rip_avg": s["imm_rip_avg"],
            "imm_rip_worst": s["imm_rip_worst"],
            "imm_rip_15_plateau": s["by_path"].get("imm_rip_15_plateau", {}).get("pnl_pct", 0),
            "imm_rip_30_plateau": s["by_path"].get("imm_rip_30_plateau", {}).get("pnl_pct", 0),
            "double_rip_26": s["by_path"].get("double_rip_26", {}).get("pnl_pct", 0),
            "rip_pullback": s["by_path"].get("rip_pullback", {}).get("pnl_pct", 0),
            "flat_chop": s["by_path"].get("flat_chop", {}).get("pnl_pct", 0),
        })
    return pd.DataFrame(rows)


def sweep_leaps_dte(spot: float, leaps_strike: float, short_strike: float,
                    short_dte: int, leaps_dtes: tuple,
                    paths_fn, policy: PlayPolicy,
                    *, r: float = 0.04) -> pd.DataFrame:
    rows = []
    for ld in leaps_dtes:
        pair = make_pair(spot, leaps_strike, short_strike, ld, short_dte, r=r)
        paths = paths_fn(ld)
        s = score_pair_integrated(pair, paths, policy, r=r)
        rows.append({
            "leaps_dte": ld,
            "leaps_debit": pair.leaps_debit,
            "net_debit": pair.net_debit,
            "coverage_pct": pair.short_credit / pair.leaps_debit * 100,
            "score": s["score"],
            "bull_avg": s["bull_avg"],
            "whipsaw_avg": s["whipsaw_avg"],
            "flat_avg": s["flat_avg"],
            "bear_worst": s["bear_worst"],
            "imm_rip_avg": s["imm_rip_avg"],
            "imm_rip_worst": s["imm_rip_worst"],
            "flat_chop": s["by_path"].get("flat_chop", {}).get("pnl_pct", 0),
            "flat_survival": s["by_path"].get("flat_survival", {}).get("pnl_pct", 0),
        })
    return pd.DataFrame(rows)


def sweep_leaps_strike(spot: float, leaps_strikes: tuple, short_strike: float,
                       leaps_dte: int, short_dte: int,
                       paths: tuple, policy: PlayPolicy,
                       *, r: float = 0.04) -> pd.DataFrame:
    rows = []
    for ls in leaps_strikes:
        pair = make_pair(spot, ls, short_strike, leaps_dte, short_dte, r=r)
        s = score_pair_integrated(pair, paths, policy, r=r)
        rows.append({
            "leaps_strike": ls,
            "leaps_delta": pricing.delta(spot, ls, leaps_dte/365, 0.55, "call", r=r),
            "leaps_debit": pair.leaps_debit,
            "net_debit": pair.net_debit,
            "coverage_pct": pair.short_credit / pair.leaps_debit * 100,
            "score": s["score"],
            "bull_avg": s["bull_avg"],
            "flat_avg": s["flat_avg"],
            "bear_worst": s["bear_worst"],
            "imm_rip_worst": s["imm_rip_worst"],
            "imm_rip_30_plateau": s["by_path"].get("imm_rip_30_plateau", {}).get("pnl_pct", 0),
            "flat_chop": s["by_path"].get("flat_chop", {}).get("pnl_pct", 0),
            "moonshot": s["by_path"].get("moonshot", {}).get("pnl_pct", 0),
        })
    return pd.DataFrame(rows)


def fmt_pct(x: float) -> str:
    return f"{x:+.0f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC integrated scoring + sweeps")
    ap.add_argument("--spot", type=float, default=400.49)
    ap.add_argument("--leaps-strike", type=float, default=410.0)
    ap.add_argument("--short-strike", type=float, default=460.0)
    ap.add_argument("--leaps-dte", type=int, default=726)
    ap.add_argument("--short-dte", type=int, default=89)
    ap.add_argument("--preset", default="managed")
    ap.add_argument("--roll-dte", type=int, default=365)
    ap.add_argument("--deep-itm", type=float, default=1.25)
    ap.add_argument("--sweep-all", action="store_true")
    ap.add_argument("--rip-detail", action="store_true",
                    help="Show detailed rip scenario trade logs")
    args = ap.parse_args()

    spot = args.spot
    policy = POLICY_BY_PRESET[args.preset]
    pair = make_pair(spot, args.leaps_strike, args.short_strike,
                     args.leaps_dte, args.short_dte, r=0.04)
    paths = build_all_paths(args.leaps_dte)

    print(f"\n{'='*80}")
    print(f"PMCC INTEGRATED SCORING — conditional roll at {args.roll_dte} DTE")
    print(f"{'='*80}")
    print(f"Pair: {int(args.leaps_strike)}/{int(args.short_strike)} "
          f"({args.leaps_dte}d/{args.short_dte}d)")
    print(f"Spot: ${spot:.2f}  LEAPS debit: ${pair.leaps_debit:,.0f}  "
          f"Short credit: ${pair.short_credit:,.0f}")
    print(f"Coverage: {pair.short_credit/pair.leaps_debit*100:.1f}%  "
          f"Short OTM: {(args.short_strike-spot)/spot*100:.0f}%")
    print()

    # --- Base case: all paths ---
    s = score_pair_integrated(pair, paths, policy, roll_dte=args.roll_dte,
                              deep_itm_threshold=args.deep_itm)
    print(f"{'BASE CASE — P/L by path (conditional roll)':^80}")
    print("-" * 80)
    path_results = sorted(s["by_path"].items(), key=lambda x: x[1]["pnl_pct"], reverse=True)
    for name, r in path_results:
        mode = r["mode"][:4]
        flag = ""
        if name in BULL_PATHS: flag = " ← bull"
        elif name in WHIPSAW_PATHS: flag = " ← whipsaw"
        elif name in FLAT_PATHS: flag = " ← flat"
        elif name in BEAR_PATHS: flag = " ← bear"
        elif name in IMMEDIATE_RIP_PATHS: flag = " ← IMM RIP"
        print(f"  {name:<28} {r['pnl_pct']:+8.1f}%  [{mode}] {flag}")

    print(f"\n  SCORE: {s['score']:.1f}")
    print(f"  bull_avg={s['bull_avg']:+.0f}%  whipsaw_avg={s['whipsaw_avg']:+.0f}%  "
          f"flat_avg={s['flat_avg']:+.0f}%  bear_worst={s['bear_worst']:+.0f}%  "
          f"imm_rip_worst={s['imm_rip_worst']:+.0f}%")

    # --- Immediate rip detail ---
    if args.rip_detail:
        print(f"\n{'='*80}")
        print(f"IMMEDIATE RIP SCENARIO DETAILS")
        print(f"{'='*80}")
        rip_paths = [
            ("imm_rip_10_plateau", "+10% in 3d, stays high"),
            ("imm_rip_15_plateau", "+15% in 3d, stays high"),
            ("imm_rip_15_continue", "+15% in 3d, keeps going to +50%"),
            ("imm_rip_15_drop", "+15% in 3d, drops back"),
            ("imm_rip_20_plateau", "+20% in 5d, stays high"),
            ("imm_rip_30_plateau", "+30% in 7d, stays high"),
            ("imm_rip_30_continue", "+30% in 7d, keeps going"),
            ("imm_rip_30_drop", "+30% in 7d, drops back"),
            ("double_rip_26", "+15% d3 then +10% d10 = +26.5%"),
            ("double_rip_31", "+20% d5 then +10% d10 = +31%"),
        ]
        for pname, desc in rip_paths:
            p = next((x for x in paths if x.name == pname), None)
            if p is None:
                continue
            df = run_daily_path(pair, p, daily_policy(policy), r=0.04)
            action_mask = df["action"].str.contains(
                "CHALLENGED|GAP RIP|ROLL|CRASH|LEAPS EXPIRE|DROP|SELL new|FLUSH|harvest",
                case=False, regex=True,
            )
            keep = df[action_mask | (df["day"] <= 15) | (df["day"] == df["day"].max())]
            keep = keep.drop_duplicates(subset=["day"]).head(12)
            print(f"\n  --- {pname}: {desc} ---")
            view = keep[["day", "spot", "leaps_dte", "short_strike", "short_dte",
                         "net_pnl", "roll_tax", "action"]].copy()
            view["spot"] = view["spot"].map(lambda x: f"${x:,.0f}")
            view["net_pnl"] = view["net_pnl"].map(lambda x: f"${x:+,.0f}")
            view["roll_tax"] = view["roll_tax"].map(lambda x: f"${x:,.0f}")
            print(view.to_string(index=False))

    # --- Sweeps ---
    if args.sweep_all:
        print(f"\n{'='*80}")
        print(f"SWEEP 1: SHORT STRIKE DISTANCE (OTM %)")
        print(f"{'='*80}")
        otm_pcts = (0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30, 0.35, 0.40)
        result = sweep_short_distance(spot, args.leaps_strike, args.leaps_dte,
                                      args.short_dte, otm_pcts, paths, policy)
        display = result.copy()
        for c in ["score"]:
            display[c] = display[c].map(lambda x: f"{x:.1f}")
        for c in ["bull_avg", "whipsaw_avg", "flat_avg", "bear_worst",
                  "imm_rip_avg", "imm_rip_worst", "imm_rip_15_plateau",
                  "imm_rip_30_plateau", "double_rip_26", "rip_pullback", "flat_chop"]:
            display[c] = display[c].map(fmt_pct)
        display["short_credit"] = display["short_credit"].map(lambda x: f"${x:,.0f}")
        display["coverage_pct"] = display["coverage_pct"].map(lambda x: f"{x:.1f}%")
        print(display.to_string(index=False))

        print(f"\n{'='*80}")
        print(f"SWEEP 2: LEAPS DTE (initial tenor)")
        print(f"{'='*80}")
        leaps_dtes = (362, 454, 545, 630, 727)
        result = sweep_leaps_dte(spot, args.leaps_strike, args.short_strike,
                                 args.short_dte, leaps_dtes, build_all_paths, policy)
        display = result.copy()
        display["score"] = display["score"].map(lambda x: f"{x:.1f}")
        for c in ["bull_avg", "whipsaw_avg", "flat_avg", "bear_worst",
                  "imm_rip_avg", "imm_rip_worst", "flat_chop", "flat_survival"]:
            display[c] = display[c].map(fmt_pct)
        display["leaps_debit"] = display["leaps_debit"].map(lambda x: f"${x:,.0f}")
        display["net_debit"] = display["net_debit"].map(lambda x: f"${x:,.0f}")
        display["coverage_pct"] = display["coverage_pct"].map(lambda x: f"{x:.1f}%")
        print(display.to_string(index=False))

        print(f"\n{'='*80}")
        print(f"SWEEP 3: LEAPS STRIKE (delta)")
        print(f"{'='*80}")
        leaps_strikes = tuple(float(x) for x in range(370, 470, 10))
        result = sweep_leaps_strike(spot, leaps_strikes, args.short_strike,
                                    args.leaps_dte, args.short_dte, paths, policy)
        display = result.copy()
        display["score"] = display["score"].map(lambda x: f"{x:.1f}")
        display["leaps_delta"] = display["leaps_delta"].map(lambda x: f"{x:.2f}")
        for c in ["bull_avg", "flat_avg", "bear_worst", "imm_rip_worst",
                  "imm_rip_30_plateau", "flat_chop", "moonshot"]:
            display[c] = display[c].map(fmt_pct)
        display["leaps_debit"] = display["leaps_debit"].map(lambda x: f"${x:,.0f}")
        display["net_debit"] = display["net_debit"].map(lambda x: f"${x:,.0f}")
        display["coverage_pct"] = display["coverage_pct"].map(lambda x: f"{x:.1f}%")
        print(display.to_string(index=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""PMCC LEAPS roll simulator — model the strategy with periodic LEAPS rolls.

Instead of holding the LEAPS to expiry (theta cliff), roll at a target DTE
into a fresh LEAPS. This is how PMCC is actually traded. Compares:
  1. Hold to expiry (current sim)
  2. Roll at 180 DTE (avoid theta cliff)
  3. Conditional roll: roll at 180 DTE unless LEAPS is deep ITM (capture upside)
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

import pricing
from pmcc.daily_playthrough import (
    DailyPlayPath,
    MonthPoint,
    build_daily_paths,
    daily_policy,
    run_all_daily_paths,
    run_daily_path,
    pnl_return_pct,
)
from pmcc.playthrough import PlayPolicy, POLICY_BY_PRESET, _px, _strike_for_delta
from pmcc.scenarios import PmccPair


def _new_leaps(spot: float, target_delta: float, dte: int, iv: float,
               r: float) -> tuple[float, float]:
    """Strike and price for a new LEAPS at target delta."""
    strike = _strike_for_delta(spot, dte, iv, target_delta, r)
    price = _px(spot, strike, dte, iv, r) * 100.0
    return strike, price


def _slice_path(path: DailyPlayPath, from_day: int, to_day: int,
                spot_mult_scale: float, iv_mult_scale: float) -> DailyPlayPath:
    """Slice a daily path and rescale multipliers for a new entry point."""
    days = []
    for d in range(from_day + 1, min(to_day + 1, len(path.days) + 1)):
        idx = d - 1  # 0-indexed
        if idx >= len(path.days):
            break
        old = path.days[idx]
        days.append(MonthPoint(
            old.spot_mult / spot_mult_scale,
            old.iv_mult / iv_mult_scale,
        ))
    if not days:
        days = [MonthPoint(1.0, 1.0)]
    return DailyPlayPath(f"{path.name}_c2", path.label + " (cycle 2)", tuple(days))


def simulate_with_leaps_roll(
    pair: PmccPair,
    path: DailyPlayPath,
    policy: PlayPolicy,
    *,
    roll_dte: int = 180,
    new_leaps_dte: int = 730,
    new_leaps_delta: float = 0.70,
    r: float = 0.04,
    conditional: bool = False,
    deep_itm_threshold: float = 1.25,
) -> dict:
    """Run sim with LEAPS roll at target DTE.

    If conditional=True, only roll if LEAPS is NOT deep ITM
    (spot / leaps_strike < deep_itm_threshold). If deep ITM, hold to expiry
    to capture intrinsic value.
    """
    pol = daily_policy(policy)

    # --- Cycle 1: run until LEAPS DTE hits roll_dte ---
    df1 = run_daily_path(pair, path, pol, r=r)

    # Find the roll point (first day where LEAPS DTE <= roll_dte)
    roll_mask = df1["leaps_dte"] <= roll_dte
    if roll_mask.empty or not roll_mask.any():
        # Path is shorter than roll point — no roll needed
        final = df1.iloc[-1]
        return {
            "rolled": False,
            "cycles": 1,
            "total_pnl": float(final["net_pnl"]),
            "total_pnl_pct": pnl_return_pct(float(final["net_pnl"]), pair.net_debit),
            "roll_day": None,
            "roll_cost": 0.0,
            "cycle1_pnl": float(final["net_pnl"]),
            "cycle2_pnl": 0.0,
        }

    roll_row = df1[roll_mask].iloc[0]
    roll_day = int(roll_row["day"])
    roll_spot = float(roll_row["spot"])
    roll_leaps_dte = int(roll_row["leaps_dte"])

    # Check conditional roll
    moneyness = roll_spot / pair.leaps_strike
    if conditional and moneyness >= deep_itm_threshold:
        # LEAPS is deep ITM — hold to expiry, don't roll
        final = df1.iloc[-1]
        return {
            "rolled": False,
            "cycles": 1,
            "total_pnl": float(final["net_pnl"]),
            "total_pnl_pct": pnl_return_pct(float(final["net_pnl"]), pair.net_debit),
            "roll_day": roll_day,
            "roll_cost": 0.0,
            "cycle1_pnl": float(final["net_pnl"]),
            "cycle2_pnl": 0.0,
            "reason": f"deep ITM (spot/strike={moneyness:.2f}), hold to expiry",
        }

    # Compute LEAPS mark at roll point
    leaps_mark = _px(roll_spot, pair.leaps_strike, roll_leaps_dte,
                     pair.leaps_iv, r) * 100.0

    # Compute new LEAPS
    # Use IV from the path at the roll point
    path_idx = min(roll_day - 1, len(path.days) - 1)
    path_iv_mult = path.days[path_idx].iv_mult
    new_iv = pair.leaps_iv * path_iv_mult
    new_strike, new_debit = _new_leaps(roll_spot, new_leaps_delta, new_leaps_dte,
                                       new_iv, r)
    roll_cost = new_debit - leaps_mark  # positive = need to pay more

    # Cycle 1 realized P/L (at roll point)
    cycle1_pnl = float(roll_row["net_pnl"])

    # --- Cycle 2: new LEAPS, continue path ---
    spot_mult_scale = path.days[path_idx].spot_mult
    iv_mult_scale = path_iv_mult

    path2 = _slice_path(path, roll_day, roll_day + new_leaps_dte,
                        spot_mult_scale, iv_mult_scale)

    # Cycle 2: new LEAPS. Start with no open short (let sim open one).
    # Set short_dte=1 with a far-OTM strike and 0 credit so it settles
    # immediately at dte=0, then the sim opens a fresh short.
    pair2 = PmccPair(
        spot_entry=roll_spot,
        leaps_strike=new_strike,
        leaps_exp="2029-01-19",
        leaps_dte=new_leaps_dte,
        leaps_iv=new_iv,
        leaps_debit=new_debit,
        short_strike=new_strike + 200,
        short_exp="2026-12-19",
        short_dte=1,
        short_iv=new_iv * 0.82,
        short_credit=0.01,
        leaps_delta_target=new_leaps_delta,
        short_delta_target=policy.short_delta_new,
    )

    df2 = run_daily_path(pair2, path2, pol, r=r)
    if df2.empty:
        cycle2_pnl = 0.0
    else:
        final2 = df2.iloc[-1]
        cycle2_pnl = float(final2["net_pnl"])

    # total_pnl = cycle1 + cycle2 (NO roll_cost subtraction)
    # cycle1_pnl already includes selling old LEAPS at mark
    # cycle2_pnl already includes buying new LEAPS at debit
    total_pnl = cycle1_pnl + cycle2_pnl
    total_capital = pair.net_debit

    return {
        "rolled": True,
        "cycles": 2,
        "total_pnl": total_pnl,
        "total_pnl_pct": pnl_return_pct(total_pnl, pair.net_debit),
        "roll_day": roll_day,
        "roll_spot": roll_spot,
        "old_leaps_mark": leaps_mark,
        "new_leaps_strike": new_strike,
        "new_leaps_debit": new_debit,
        "roll_cost": roll_cost,
        "cycle1_pnl": cycle1_pnl,
        "cycle2_pnl": cycle2_pnl,
        "total_capital": total_capital,
    }


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


def build_lab_paths(leaps_dte: int) -> tuple[DailyPlayPath, ...]:
    """Key paths for LEAPS roll analysis."""
    all_daily = build_daily_paths(leaps_dte)
    keep = {"steady_bull", "moonshot", "single_day_rip_10",
            "gap_rip_flush", "gap_whipsaw_double", "post_earnings_whipsaw",
            "tsla_range_chop", "flat_chop", "steady_bear", "crash_recover",
            "v_recovery"}
    paths = tuple(p for p in all_daily if p.name in keep)

    # Add custom paths
    import math
    rip_pullback_days = []
    rip_continue_days = []
    flat_survival_days = []
    for d in range(1, leaps_dte + 1):
        # rip_pullback: flat 45d → +15% → flush to entry → flat
        if d < 45:
            s = 1.0
        elif d == 45:
            s = 1.15
        elif d <= 52:
            t = (d - 45) / 7
            s = 1.15 + t * (1.0 - 1.15)
        else:
            s = 1.0
        iv = max(0.75, 1.15 - 0.10 * (s - 1.0))
        rip_pullback_days.append(MonthPoint(s, iv))

        # rip_continue: flat 45d → +15% → grind to +50%
        if d < 45:
            s2 = 1.0
        elif d == 45:
            s2 = 1.15
        else:
            t2 = (d - 45) / max(leaps_dte - 45, 1)
            s2 = 1.15 + t2 * (1.50 - 1.15)
        iv2 = max(0.65, 1.05 - 0.12 * (s2 - 1.0))
        rip_continue_days.append(MonthPoint(s2, iv2))

        # flat_survival
        s3 = 1.0 + 0.03 * math.sin(d / 21.0)
        flat_survival_days.append(MonthPoint(s3, 1.0))

    custom = (
        DailyPlayPath("rip_pullback", "+15% rip d45 then flush to entry",
                      tuple(rip_pullback_days)),
        DailyPlayPath("rip_continue", "+15% rip then grind to +50%",
                      tuple(rip_continue_days)),
        DailyPlayPath("flat_survival", "Flat ±3% sine wave",
                      tuple(flat_survival_days)),
    )
    return custom + paths


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC LEAPS roll simulator")
    ap.add_argument("--spot", type=float, default=400.49)
    ap.add_argument("--leaps-strike", type=float, default=420.0)
    ap.add_argument("--short-strike", type=float, default=520.0)
    ap.add_argument("--leaps-dte", type=int, default=726)
    ap.add_argument("--short-dte", type=int, default=89)
    ap.add_argument("--leaps-debit", type=float, default=12385.0)
    ap.add_argument("--short-credit", type=float, default=800.0)
    ap.add_argument("--preset", default="managed")
    ap.add_argument("--roll-dte", type=int, default=180,
                    help="DTE at which to roll the LEAPS")
    ap.add_argument("--new-leaps-dte", type=int, default=730)
    ap.add_argument("--new-leaps-delta", type=float, default=0.70)
    ap.add_argument("--conditional", action="store_true",
                    help="Only roll if LEAPS is NOT deep ITM")
    ap.add_argument("--deep-itm-threshold", type=float, default=1.25,
                    help="Spot/strike ratio above which LEAPS is 'deep ITM'")
    ap.add_argument("--sweep-roll-dte", action="store_true",
                    help="Sweep roll DTE values")
    ap.add_argument("--sweep-leaps-dte", action="store_true",
                    help="Sweep initial LEAPS DTE values")
    args = ap.parse_args()

    spot = args.spot
    pair = make_pair(spot, args.leaps_strike, args.short_strike,
                     args.leaps_dte, args.short_dte, args.leaps_debit,
                     args.short_credit)
    policy = POLICY_BY_PRESET[args.preset]
    paths = build_lab_paths(args.leaps_dte)
    cap = pair.net_debit

    print(f"\n{'='*75}")
    print(f"PMCC LEAPS ROLL SIMULATOR")
    print(f"{'='*75}")
    print(f"Pair: {int(args.leaps_strike)}/{int(args.short_strike)} "
          f"(LEAPS {args.leaps_dte}d, short {args.short_dte}d)")
    print(f"Spot: ${spot:.2f}  Net debit: ${cap:,.0f}  Coverage: "
          f"{args.short_credit/args.leaps_debit*100:.1f}%")
    print(f"Roll: at {args.roll_dte} DTE → new {args.new_leaps_dte}d LEAPS "
          f"at {args.new_leaps_delta:.2f}Δ"
          f"{' (conditional: skip if deep ITM)' if args.conditional else ''}")
    print()

    # --- Compare: hold to expiry vs roll at roll_dte vs conditional roll ---
    pol = daily_policy(policy)
    _, summary_hold = run_all_daily_paths(pair, paths, pol, r=0.04)
    hold_by_path = {row["path"]: float(row["final_pnl"]) for _, row in summary_hold.iterrows()}

    roll_results = {}
    cond_results = {}
    for p in paths:
        roll_results[p.name] = simulate_with_leaps_roll(
            pair, p, policy, roll_dte=args.roll_dte,
            new_leaps_dte=args.new_leaps_dte,
            new_leaps_delta=args.new_leaps_delta, r=0.04,
        )
        if args.conditional:
            cond_results[p.name] = simulate_with_leaps_roll(
                pair, p, policy, roll_dte=args.roll_dte,
                new_leaps_dte=args.new_leaps_dte,
                new_leaps_delta=args.new_leaps_delta, r=0.04,
                conditional=True, deep_itm_threshold=args.deep_itm_threshold,
            )

    print(f"{'COMPARISON: hold to expiry vs LEAPS roll':^75}")
    print("-" * 75)
    print(f"{'path':<26} {'hold':>8} {'roll':>8} {'cond':>8} {'roll_cost':>10}")
    print("-" * 75)
    for p in paths:
        name = p.name
        hold_pct = pnl_return_pct(hold_by_path.get(name, 0), cap)
        roll_r = roll_results.get(name, {})
        roll_pct = roll_r.get("total_pnl_pct", 0)
        roll_cost = roll_r.get("roll_cost", 0)
        if args.conditional:
            cond_r = cond_results.get(name, {})
            cond_pct = cond_r.get("total_pnl_pct", 0)
            cond_str = f"{cond_pct:+7.1f}%"
        else:
            cond_str = "   —"
        print(f"  {name:<26} {hold_pct:+7.1f}% {roll_pct:+7.1f}% {cond_str} "
              f"${roll_cost:>9,.0f}")

    # --- Roll details ---
    print(f"\n{'ROLL DETAILS (roll at {args.roll_dte} DTE)':^75}")
    print("-" * 75)
    print(f"{'path':<26} {'day':>5} {'spot':>7} {'old_mark':>9} {'new_k':>6} "
          f"{'new_debit':>10} {'cost':>8}")
    for name, r in roll_results.items():
        if not r.get("rolled"):
            reason = r.get("reason", "path too short")
            print(f"  {name:<26} {'—':>5} {'—':>7} {'—':>9} {'—':>6} "
                  f"{'—':>10} {'—':>8}  ({reason})")
            continue
        print(f"  {name:<26} {r['roll_day']:>5} ${r['roll_spot']:>6,.0f} "
              f"${r['old_leaps_mark']:>8,.0f} {int(r['new_leaps_strike']):>5} "
              f"${r['new_leaps_debit']:>9,.0f} ${r['roll_cost']:>7,.0f}")

    # --- Sweep roll DTE ---
    if args.sweep_roll_dte:
        print(f"\n{'='*75}")
        print(f"SWEEP: roll DTE (when to roll the LEAPS)")
        print(f"{'='*75}")
        roll_dtes = (90, 120, 150, 180, 210, 240, 300, 365)
        key_paths = ["flat_chop", "flat_survival", "rip_pullback", "rip_continue",
                     "steady_bull", "moonshot", "steady_bear", "gap_whipsaw_double"]
        print(f"{'roll_dte':<10}", end="")
        for kp in key_paths:
            print(f"{kp[:12]:>13}", end="")
        print()
        print("-" * (10 + 13 * len(key_paths)))
        for rd in roll_dtes:
            print(f"{rd:<10}", end="")
            for kp in key_paths:
                p = next((x for x in paths if x.name == kp), None)
                if p is None:
                    print(f"{'—':>13}", end="")
                    continue
                r = simulate_with_leaps_roll(
                    pair, p, policy, roll_dte=rd,
                    new_leaps_dte=args.new_leaps_dte,
                    new_leaps_delta=args.new_leaps_delta, r=0.04,
                )
                print(f"{r['total_pnl_pct']:+12.1f}%", end="")
            print()

    # --- Sweep initial LEAPS DTE ---
    if args.sweep_leaps_dte:
        print(f"\n{'='*75}")
        print(f"SWEEP: initial LEAPS DTE (with roll at {args.roll_dte} DTE)")
        print(f"{'='*75}")
        leaps_dtes = (362, 454, 545, 630, 727)
        key_paths = ["flat_chop", "flat_survival", "rip_pullback", "rip_continue",
                     "steady_bull", "moonshot", "steady_bear"]
        print(f"{'leaps_dte':<10}", end="")
        for kp in key_paths:
            print(f"{kp[:12]:>13}", end="")
        print()
        print("-" * (10 + 13 * len(key_paths)))
        for ld in leaps_dtes:
            test_paths = build_lab_paths(ld)
            # Estimate LEAPS debit for this DTE
            test_iv = 0.55
            test_debit = _px(spot, args.leaps_strike, ld, test_iv, 0.04) * 100.0
            test_pair = make_pair(spot, args.leaps_strike, args.short_strike,
                                  ld, args.short_dte, test_debit,
                                  args.short_credit, leaps_iv=test_iv)
            print(f"{ld:<10}", end="")
            for kp in key_paths:
                p = next((x for x in test_paths if x.name == kp), None)
                if p is None:
                    print(f"{'—':>13}", end="")
                    continue
                r = simulate_with_leaps_roll(
                    test_pair, p, policy, roll_dte=args.roll_dte,
                    new_leaps_dte=args.new_leaps_dte,
                    new_leaps_delta=args.new_leaps_delta, r=0.04,
                )
                print(f"{r['total_pnl_pct']:+12.1f}%", end="")
            print()


if __name__ == "__main__":
    main()

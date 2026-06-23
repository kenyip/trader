#!/usr/bin/env python3
"""Multi-cycle LEAPS refresh comparison — continuous re-entry, no foresight.

Simulates buying a LEAPS, holding for X days, rolling to a new LEAPS, and
CONTINUING through the full 2-year path. Always re-enters. No staying out.

Compares refresh frequencies:
  - Buy 727d, refresh every 365d (hold 1yr, roll to new 727d)  — current default
  - Buy 727d, refresh every 180d (hold 6mo, roll to new 727d)
  - Buy 727d, refresh every 90d  (hold 3mo, roll to new 727d)
  - Buy 545d, refresh every 180d (hold 6mo, roll to new 545d)
  - Buy 545d, refresh every 90d  (hold 3mo, roll to new 545d)

Each strategy runs the SAME path over the SAME 2-year horizon. We measure
total cumulative P/L at day 730 (end of 2 years). No foresight, no escape.
"""
from __future__ import annotations
import math
import pricing
from pmcc.playthrough import _px, _strike_for_delta, POLICY_BY_PRESET
from pmcc.daily_playthrough import (
    DailyPlayPath, MonthPoint, daily_policy, run_daily_path, pnl_return_pct,
)
from pmcc.scenarios import PmccPair
import pandas as pd

SPOT = 400.49
LEAPS_K = 410
SHORT_K = 500
R = 0.04
BASE = POLICY_BY_PRESET["managed"]

# Strategies: (name, initial_dte, hold_days, roll_to_dte)
# roll_to_dte = what DTE the new LEAPS has when you buy it
STRATEGIES = [
    ("727d/hold365d",  727, 365, 727),   # current default
    ("727d/hold180d",  727, 180, 727),    # roll every 6 months to fresh 2yr
    ("727d/hold90d",   727, 90,  727),    # roll every 3 months to fresh 2yr
    ("545d/hold180d",  545, 180, 545),    # 1.5yr LEAPS, roll every 6mo to fresh 1.5yr
    ("545d/hold90d",   545, 90,  545),    # 1.5yr LEAPS, roll every 3mo
    ("362d/hold180d",  362, 180, 362),    # 1yr LEAPS, roll every 6mo
    ("362d/hold90d",   362, 90,  362),     # 1yr LEAPS, roll every 3mo
]


def make_paths_730():
    """Full 2-year (730-day) scenario paths."""
    paths = []

    # Flat ±3% for 730 days
    days = tuple(MonthPoint(1.0 + 0.03 * math.sin(d / 21.0), 1.0) for d in range(1, 731))
    paths.append(DailyPlayPath("flat", "Flat ±3% for 2yr", days))

    # Steady bull +40% over 2yr
    days = tuple(MonthPoint(1.0 + 0.40 * d / 730, max(0.80, 1.0 - 0.05 * (1.0 + 0.40*d/730 - 1.0)), ) for d in range(1, 731))
    paths.append(DailyPlayPath("steady_bull", "Steady bull +40% over 2yr", days))

    # Moonshot: +50% in first 90d, then plateau for rest
    days = []
    for d in range(1, 731):
        if d < 90: s = 1.0 + 0.50 * d / 90
        else: s = 1.50
        iv = max(0.65, 1.05 - 0.10 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("moon_early", "+50% in first 90d then flat for 2yr", tuple(days)))

    # Moonshot: +50% in months 12-18 (late rip)
    days = []
    for d in range(1, 731):
        if d < 365: s = 1.0
        elif d < 487: s = 1.0 + 0.50 * (d - 365) / 122
        else: s = 1.50
        iv = max(0.65, 1.05 - 0.10 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("moon_late", "Flat for 1yr then +50% rip in months 12-18", tuple(days)))

    # Rip + flush: +25% in 30d, drop back, repeat 3x over 2yr
    days = []
    cycle_len = 240
    for d in range(1, 731):
        cycle_day = d % cycle_len
        if cycle_day < 30: s = 1.0
        elif cycle_day == 30: s = 1.25
        elif cycle_day <= 90:
            t = (cycle_day - 30) / 60
            s = 1.25 + t * (1.05 - 1.25)
        else: s = 1.05
        iv = max(0.70, 1.15 - 0.08 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("rip_flush_3x", "3 rip+flush cycles over 2yr", tuple(days)))

    # Steady bear -30% over 2yr
    days = tuple(MonthPoint(1.0 - 0.30 * d / 730, max(0.80, 1.15 + 0.10 * (1.0 - (1.0 - 0.30*d/730)))) for d in range(1, 731))
    paths.append(DailyPlayPath("steady_bear", "Steady bear -30% over 2yr", days))

    # Chop: ±15% swings every 120 days
    days = []
    for d in range(1, 731):
        phase = (d // 120) % 2
        cycle_day = d % 120
        if phase == 0:
            s = 1.0 + 0.15 * cycle_day / 120
        else:
            s = 1.15 - 0.15 * cycle_day / 120
        iv = max(0.80, 1.0 - 0.03 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("chop_15pct", "±15% swings every 120d for 2yr", tuple(days)))

    # V-shape: -20% in first 180d, then rip to +30% by day 730
    days = []
    for d in range(1, 731):
        if d < 180:
            s = 1.0 - 0.20 * d / 180
        else:
            t = (d - 180) / 550
            s = 0.80 + t * (1.30 - 0.80)
        iv = max(0.65, 1.15 - 0.08 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("v_shape", "V-shape: -20% then rip to +30%", tuple(days)))

    # Slow bleed: -8% in first year, then -15% in second year (protracted bear)
    days = []
    for d in range(1, 731):
        if d < 365:
            s = 1.0 - 0.08 * d / 365
        else:
            s = 0.92 - 0.15 * (d - 365) / 365
        iv = max(0.80, 1.20 + 0.10 * (1.0 - s))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("slow_bleed", "Slow bear: -8% yr1, -15% yr2", tuple(days)))

    return tuple(paths)


def simulate_multi_cycle(path, initial_dte, hold_days, roll_to_dte,
                         leaps_strike, short_strike, spot_entry, *, r=0.04):
    """Run a full path with continuous LEAPS refreshing.

    Each cycle:
      1. Buy LEAPS at (spot, strike, dte) — debit = market price
      2. Sell shorts against it for hold_days
      3. At end of hold, sell LEAPS at mark, realize P/L
      4. Buy new LEAPS at (current spot, strike, roll_to_dte)
      5. Continue until path ends

    Short management: same rules as managed preset.
    LEAPS re-entry: SAME strike (no foresight, no adjusting strike).
    """
    pol = daily_policy(BASE)
    total_realized = 0.0  # cumulative realized P/L from LEAPS rolls + short income
    total_invested = 0.0  # cumulative capital deployed (for return calc)
    cycle_results = []

    dte = initial_dte
    day_offset = 0
    cycle_num = 0

    # Initial LEAPS debit
    leaps_debit = _px(spot_entry, leaps_strike, dte, 0.55, r) * 100
    total_invested += leaps_debit

    while day_offset < len(path.days):
        cycle_num += 1
        # Build a sub-path for this cycle (hold_days or until end)
        end_day = min(day_offset + hold_days, len(path.days))
        sub_days = path.days[day_offset:end_day]

        # How many days in this cycle
        cycle_days = end_day - day_offset

        # Create a sub-path
        sub_path = DailyPlayPath(
            f"cycle{cycle_num}",
            "",
            sub_days,
        )

        # Create a pair for this cycle
        spot_at_cycle_start = spot_entry * sub_days[0].spot_mult
        iv_at_start = 0.55 * sub_days[0].iv_mult
        leaps_debit_cycle = _px(spot_at_cycle_start, leaps_strike, dte, iv_at_start, r) * 100
        short_credit_cycle = _px(spot_at_cycle_start, short_strike, 60, 0.45 * sub_days[0].iv_mult, r) * 0.97 * 100

        pair = PmccPair(
            spot_entry=spot_at_cycle_start,
            leaps_strike=leaps_strike,
            leaps_exp="2028-01-21",
            leaps_dte=dte,
            leaps_iv=iv_at_start,
            leaps_debit=leaps_debit_cycle,
            short_strike=short_strike,
            short_exp="2026-09-19",
            short_dte=60,
            short_iv=0.45 * sub_days[0].iv_mult,
            short_credit=short_credit_cycle,
            leaps_delta_target=0.70,
            short_delta_target=0.30,
        )

        # Roll DTE for this cycle = dte - hold_days (when to sell the LEAPS)
        roll_dte_remaining = max(dte - cycle_days, 1)
        policy = type(BASE)(
            **{**BASE.__dict__,
               "leaps_roll_dte": roll_dte_remaining,
               "leaps_deep_itm_threshold": 1.25,
               "leaps_extreme_itm_threshold": 1.35,
        })

        # Override with the right roll_dte
        from dataclasses import replace
        policy = replace(BASE, leaps_roll_dte=roll_dte_remaining)

        # Run the sub-path
        df = run_daily_path(pair, sub_path, daily_policy(policy), r=r)
        if df.empty:
            break

        final = df.iloc[-1]
        cycle_pnl = float(final["net_pnl"])
        total_realized += cycle_pnl

        # Where did the cycle end?
        end_spot = float(final["spot"])
        end_day_actual = int(final["day"])

        cycle_results.append({
            "cycle": cycle_num,
            "start_day": day_offset + 1,
            "end_day": day_offset + end_day_actual,
            "start_spot": spot_at_cycle_start,
            "end_spot": end_spot,
            "leaps_dte_start": dte,
            "leaps_dte_end": roll_dte_remaining,
            "leaps_debit": leaps_debit_cycle,
            "cycle_pnl": cycle_pnl,
            "cumulative_pnl": total_realized,
            "rolls": int(final.get("roll_count", 0)),
        })

        # If the LEAPS was rolled early (deep ITM / extreme ITM), the sim breaks
        # at the roll point. We need to continue with a new LEAPS.
        actual_days_run = end_day_actual
        day_offset += actual_days_run

        # Buy new LEAPS at current spot, same strike, roll_to_dte
        if day_offset < len(path.days):
            current_spot = spot_entry * path.days[day_offset].spot_mult
            current_iv = 0.55 * path.days[day_offset].iv_mult
            new_debit = _px(current_spot, leaps_strike, roll_to_dte, current_iv, r) * 100
            total_invested += new_debit
            dte = roll_to_dte
        else:
            break

        # Check for deep ITM / extreme ITM — sim may have broken early
        # If the sim broke because of deep ITM (leaps_rolled=True), we still
        # re-enter with a new LEAPS (no foresight — always in market)

    return cycle_results, total_realized, total_invested


def main():
    paths = make_paths_730()

    print("=" * 110)
    print("MULTI-CYCLE LEAPS REFRESH COMPARISON — continuous re-entry, no foresight")
    print("=" * 110)
    print()
    print("Every strategy runs the FULL 2-year path. Always re-enters after rolling.")
    print("Same LEAPS strike ($410), same short ($500), same management rules.")
    print("The ONLY difference: how often you refresh the LEAPS.")
    print()
    print("Total P/L = cumulative realized P/L across all LEAPS cycles + short income")
    print("  (does NOT include any foresight — you always re-enter at the same strike)")
    print()

    # Main comparison table
    header = f"  {'scenario':<22}"
    for name, _, _, _ in STRATEGIES:
        header += f"  {name:>16}"
    print(header)
    print("-" * (24 + 18 * len(STRATEGIES)))

    for p in paths:
        row = f"  {p.name:<22}"
        for name, init_dte, hold, roll_to in STRATEGIES:
            cycles, total_pnl, total_invested = simulate_multi_cycle(
                p, init_dte, hold, roll_to,
                LEAPS_K, SHORT_K, SPOT, r=R,
            )
            # Return = total_pnl / total_invested (across all cycles)
            pct = total_pnl / total_invested * 100 if total_invested > 0 else 0
            row += f"  {pct:>+15.0f}%"
        print(row)

    print()
    print("  Values = total 2-year P/L as % of total capital deployed across all cycles")
    print()

    # Cycle detail for a few key scenarios
    print("=" * 110)
    print("CYCLE DETAIL: how many LEAPS refreshes, and what each cycle earns")
    print("=" * 110)
    print()

    detail_paths = ["flat", "steady_bull", "steady_bear", "moon_early", "moon_late"]

    for pname in detail_paths:
        p = next((x for x in paths if x.name == pname), None)
        if p is None:
            continue
        print(f"--- {p.name}: {p.label} ---")
        print()
        for name, init_dte, hold, roll_to in STRATEGIES:
            cycles, total_pnl, total_inv = simulate_multi_cycle(
                p, init_dte, hold, roll_to,
                LEAPS_K, SHORT_K, SPOT, r=R,
            )
            n_cycles = len(cycles)
            pct = total_pnl / total_inv * 100 if total_inv > 0 else 0
            print(f"  {name:>16}: {n_cycles} cycles, total P/L ${total_pnl:+,.0f} "
                  f"({pct:+.0f}%), capital ${total_inv:,.0f}")
            for c in cycles[:5]:
                print(f"             cycle {c['cycle']}: d{c['start_day']}-{c['end_day']} "
                      f"spot ${c['start_spot']:.0f}-${c['end_spot']:.0f} "
                      f"LEAPS {c['leaps_dte_start']}d→{c['leaps_dte_end']}d "
                      f"P/L ${c['cycle_pnl']:+,.0f} (cum ${c['cumulative_pnl']:+,.0f})")
            if n_cycles > 5:
                print(f"             ... ({n_cycles - 5} more cycles)")
        print()

    # Summary
    print("=" * 110)
    print("SUMMARY: average P/L across all scenarios")
    print("=" * 110)
    print()

    header = f"  {'strategy':<18} {'avg P/L':>8} {'flat':>7} {'bull':>7} {'bear':>7} {'moon':>7} {'whip':>7} {'n_cycles':>8}"
    print(header)
    print("-" * 70)

    for name, init_dte, hold, roll_to in STRATEGIES:
        pnls = []
        flat_pnl = bull_pnl = bear_pnl = moon_pnl = whip_pnl = 0
        for p in paths:
            _, total_pnl, total_inv = simulate_multi_cycle(
                p, init_dte, hold, roll_to,
                LEAPS_K, SHORT_K, SPOT, r=R,
        )
            pct = total_pnl / total_inv * 100 if total_inv > 0 else 0
            pnls.append(pct)
            if p.name in ("flat",): flat_pnl = pct
            if p.name in ("steady_bull", "moon_early", "moon_late"): 
                if bull_pnl == 0: bull_pnl = pct
                else: bull_pnl = (bull_pnl + pct) / 2
            if p.name in ("steady_bear", "slow_bleed"):
                if bear_pnl == 0: bear_pnl = pct
                else: bear_pnl = (bear_pnl + pct) / 2
            if p.name in ("moon_early", "moon_late"):
                if moon_pnl == 0: moon_pnl = pct
                else: moon_pnl = (moon_pnl + pct) / 2
            if p.name in ("rip_flush_3x", "chop_15pct", "v_shape"):
                if whip_pnl == 0: whip_pnl = pct
                else: whip_pnl = (whip_pnl + pct) / 2

        avg = sum(pnls) / len(pnls)
        n_cyc = 730 // hold
        print(f"  {name:<18} {avg:>+6.0f}%  {flat_pnl:>+5.0f}%  {bull_pnl:>+5.0f}%  "
              f"{bear_pnl:>+5.0f}%  {moon_pnl:>+5.0f}%  {whip_pnl:>+5.0f}%  {n_cyc:>6}cyc")

    print()
    print("  n_cyc = number of LEAPS refreshes over 2 years")
    print("  avg = simple average across all 9 scenarios (no weighting, no foresight)")
    print()

    print("=" * 110)
    print("THE ANSWER: which refresh frequency wins with NO foresight?")
    print("=" * 110)
    print()
    print("If you ALWAYS re-enter (no foresight, no staying out):")
    print("  - Refreshing more often = more roll costs but fresher LEAPS each cycle")
    print("  - Refreshing less often = less roll costs but more theta per cycle")
    print("  - The question is purely: which dominates, roll cost or theta?")


if __name__ == "__main__":
    main()

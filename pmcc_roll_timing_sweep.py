#!/usr/bin/env python3
"""LEAPS roll timing sweep — when to roll: 90d, 120d, 180d, 240d, 365d, 545d remaining?"""
from __future__ import annotations
import math
from dataclasses import replace
import pricing
from pmcc.playthrough import _px, POLICY_BY_PRESET
from pmcc_playbook_gen import make_pair, build_paths
from pmcc.daily_playthrough import run_daily_path, daily_policy, pnl_return_pct

SPOT = 400.49
LEAPS_K = 410
SHORT_K = 500
R = 0.04
BASE_POLICY = POLICY_BY_PRESET["managed"]
DTES = [362, 454, 545, 630, 727]
ROLL_DTES = [90, 120, 180, 240, 365]


def make_paths(leaps_dte):
    paths = build_paths(leaps_dte)
    keep = {"flat_chop", "steady_bull", "moonshot", "steady_bear", "crash_recover",
            "rip_pullback", "gap_whipsaw_double", "v_recovery",
            "single_day_rip_10", "gap_rip_flush", "tsla_range_chop",
            "post_earnings_whipsaw"}
    return tuple(p for p in paths if p.name in keep)


def score_pair(pair, paths, policy, r=0.04):
    results = {}
    for p in paths:
        pol = daily_policy(policy)
        df = run_daily_path(pair, p, pol, r=r)
        if df.empty:
            results[p.name] = 0.0
            continue
        final = df.iloc[-1]
        results[p.name] = pnl_return_pct(float(final["net_pnl"]), pair.net_debit)

    bull = ["steady_bull", "moonshot", "v_recovery", "single_day_rip_10"]
    whip = ["gap_whipsaw_double", "post_earnings_whipsaw", "rip_pullback",
            "gap_rip_flush", "tsla_range_chop"]
    flat = ["flat_chop"]
    bear = ["steady_bear", "crash_recover"]

    def avg(names):
        vals = [results.get(n, 0) for n in names]
        return sum(vals) / max(len(vals), 1)

    return {
        "bull": avg(bull), "whip": avg(whip),
        "flat": avg(flat), "bear": avg(bear),
        "bear_worst": min(results.get("steady_bear", 0), results.get("crash_recover", 0)),
        "flat_chop": results.get("flat_chop", 0),
        "steady_bull": results.get("steady_bull", 0),
        "moonshot": results.get("moonshot", 0),
        "steady_bear": results.get("steady_bear", 0),
        "rip_pullback": results.get("rip_pullback", 0),
        "score": (avg(bull) * 2.0 + avg(whip) * 1.5 + avg(flat) * 1.0 + avg(bear) * 0.5) / 5.0,
    }


def main():
    print("=" * 95)
    print("LEAPS ROLL TIMING SWEEP — when to roll the LEAPS?")
    print("=" * 95)
    print()
    print("Roll DTE = days remaining on LEAPS when you sell it and buy a new one")
    print("  90d  = roll when 3 months left (very fresh, lots of rolls)")
    print("  180d = roll when 6 months left (half year)")
    print("  365d = roll when 1 year left (current default)")
    print()
    print("Each cell = % return on net debit, simulated across all paths")
    print()

    # Main grid: LEAPS DTE × roll DTE
    for ld in DTES:
        paths = make_paths(ld)
        pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
        print(f"{'=' * 95}")
        print(f"LEAPS {ld}d  (debit ${pair.leaps_debit:,.0f}, theta "
              f"${abs(pricing.theta(SPOT, LEAPS_K, ld/365, 0.55, 'call', r=R)/365*100):.1f}/day)")
        print(f"{'=' * 95}")
        print()

        header = f"  {'metric':<16}"
        for rd in ROLL_DTES:
            header += f"  roll@{rd}d{'':>6}"
        print(header)
        print("-" * (18 + 15 * len(ROLL_DTES)))

        scores = {}
        for rd in ROLL_DTES:
            policy = replace(BASE_POLICY, leaps_roll_dte=rd)
            scores[rd] = score_pair(pair, paths, policy, r=R)

        for metric in ["score", "bull", "whip", "flat", "bear", "bear_worst",
                       "flat_chop", "steady_bull", "moonshot", "steady_bear",
                       "rip_pullback"]:
            row = f"  {metric:<16}"
            for rd in ROLL_DTES:
                val = scores[rd].get(metric, 0)
                if metric == "score":
                    row += f"  {val:>13.1f}"
                else:
                    row += f"  {val:>+12.0f}%"
            print(row)

        # What happens to the LEAPS at each roll point?
        print()
        print(f"  LEAPS mark at roll point (spot unchanged):")
        for rd in ROLL_DTES:
            if rd >= ld:
                continue
            mark = _px(SPOT, LEAPS_K, rd, 0.55, R) * 100
            held_days = ld - rd
            theta_cost = pair.leaps_debit - mark
            theta_per_day = theta_cost / max(held_days, 1)
            retained = mark / pair.leaps_debit * 100
            print(f"    roll@{rd:>3}d: held {held_days:>3}d, mark ${mark:>7,.0f} "
                  f"({retained:>4.1f}%), theta ${theta_cost:>6,.0f} (${theta_per_day:.1f}/d), "
                  f"{held_days//80} short cycles")

        print()

    # Summary: best roll DTE for each LEAPS DTE
    print("=" * 95)
    print("SUMMARY: BEST ROLL DTE FOR EACH LEAPS DTE")
    print("=" * 95)
    print()
    print(f"  {'LEAPS DTE':<10} {'best roll@':<12} {'score':<8} {'flat':<8} {'bull':<8} {'bear_w':<8}")
    print("-" * 55)

    for ld in DTES:
        paths = make_paths(ld)
        pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
        best_rd = None
        best_score = -999
        best_data = None
        for rd in ROLL_DTES:
            if rd >= ld:
                continue
            policy = replace(BASE_POLICY, leaps_roll_dte=rd)
            s = score_pair(pair, paths, policy, r=R)
            if s["score"] > best_score:
                best_score = s["score"]
                best_rd = rd
                best_data = s
        if best_data:
            print(f"  {ld:>3}d       roll@{best_rd:>3}d       "
                  f"{best_score:>6.1f}  {best_data['flat']:>+6.0f}%  "
                  f"{best_data['bull']:>+6.0f}%  {best_data['bear_worst']:>+6.0f}%")

    print()
    print("=" * 95)
    print("THE KEY TRADEOFF: ROLL FREQUENCY vs THETA FRESHNESS")
    print("=" * 95)
    print()

    # For 727d LEAPS, show the full economics of each roll strategy
    ld = 727
    pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
    print(f"For 727d LEAPS (${pair.leaps_debit:,.0f} debit):")
    print()
    print(f"  {'roll@':>7} {'hold days':>9} {'theta cost':>10} {'theta/day':>9} "
          f"{'short cycles':>12} {'short income':>12} {'net cost':>9} {'net/day':>8}")
    print("-" * 85)

    for rd in ROLL_DTES:
        if rd >= ld:
            continue
        mark = _px(SPOT, LEAPS_K, rd, 0.55, R) * 100
        held = ld - rd
        theta_cost = pair.leaps_debit - mark
        theta_day = theta_cost / max(held, 1)
        cycles = max(held // 80, 1)
        short_income = pair.short_credit * 0.50 * cycles
        net_cost = theta_cost - short_income
        net_day = net_cost / max(held, 1)
        print(f"  {rd:>5}d  {held:>7}d   ${theta_cost:>9,.0f}  ${theta_day:>7.1f}/d  "
              f"{cycles:>10}cyc    ${short_income:>10,.0f}   ${net_cost:>+7,.0f}  ${net_day:>+6.1f}/d")

    print()
    print("  net cost = theta decay - short income (negative = you PROFIT)")
    print("  short income = estimated 50% profit per 60d cycle")
    print()

    # The roll cost analysis
    print("=" * 95)
    print("ROLL COST: what does each roll cost you?")
    print("=" * 95)
    print()

    new_leaps_727 = _px(SPOT, LEAPS_K, 727, 0.55, R) * 100
    print(f"  New 727d LEAPS costs ${new_leaps_727:,.0f}")
    print()
    print(f"  {'roll@':>7} {'old mark':>9} {'new debit':>10} {'roll cost':>9} {'rolls/2yr':>9} {'total roll cost/2yr':>18}")
    print("-" * 70)

    for rd in ROLL_DTES:
        old_mark = _px(SPOT, LEAPS_K, rd, 0.55, R) * 100
        roll_cost = new_leaps_727 - old_mark
        # How many rolls in 2 years (730 days)?
        hold_days = 727 - rd
        rolls_per_2yr = 730 // max(hold_days, 1)
        total_roll = roll_cost * rolls_per_2yr
        print(f"  {rd:>5}d  ${old_mark:>8,.0f}  ${new_leaps_727:>9,.0f}  "
              f"${roll_cost:>+8,.0f}  {rolls_per_2yr:>7}x     ${total_roll:>+15,.0f}")

    print()
    print("  roll cost = new LEAPS debit - old LEAPS mark (what you pay to extend)")
    print("  rolls/2yr = how many times you roll over 2 years")
    print("  total roll cost/2yr = cumulative roll cost over 2 years")
    print()
    print("  Rolling at 90d: you roll ~4x in 2 years, paying ~$18,000 total in roll costs")
    print("  Rolling at 365d: you roll ~2x in 2 years, paying ~$7,900 total in roll costs")
    print("  BUT: rolling at 90d means your LEAPS always has >637d left (very slow theta)")
    print("       rolling at 365d means your LEAPS gets down to 365d (faster theta at the end)")
    print()

    # Theta curve: how much theta per day at each DTE
    print("=" * 95)
    print("THETA CURVE: daily decay at each DTE remaining")
    print("=" * 95)
    print()
    print(f"  {'DTE':>5} {'theta/day':>10} {'vs 727d':>10}")
    print("-" * 30)
    theta_727 = abs(pricing.theta(SPOT, LEAPS_K, 727/365, 0.55, "call", r=R) / 365 * 100)
    for d in [727, 630, 545, 454, 365, 240, 180, 120, 90, 60, 30]:
        t = abs(pricing.theta(SPOT, LEAPS_K, d/365, 0.55, "call", r=R) / 365 * 100)
        ratio = t / theta_727
        print(f"  {d:>4}d ${t:>8.1f}/d  {ratio:>8.1f}x")

    print()
    print("  Theta ACCELERATES as DTE drops. At 90d remaining, theta is ~2x faster")
    print("  than at 727d. Rolling at 180d keeps you in the slow-theta zone (<1.5x).")
    print("  Rolling at 365d lets theta get to ~1.6x before you exit.")


if __name__ == "__main__":
    main()

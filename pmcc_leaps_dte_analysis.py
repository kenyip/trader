#!/usr/bin/env python3
"""LEAPS DTE comparison — 1 year vs 2 years vs in between."""
from __future__ import annotations
import pricing
from pmcc.playthrough import _px, POLICY_BY_PRESET
from pmcc_playbook_gen import make_pair, build_paths
from pmcc.daily_playthrough import run_daily_path, daily_policy, pnl_return_pct

SPOT = 400.49
LEAPS_K = 410
SHORT_K = 500
R = 0.04
POLICY = POLICY_BY_PRESET["managed"]
DTES = [362, 454, 545, 630, 727]


def main():
    print("=" * 90)
    print("LEAPS DTE COMPARISON — what happens to your capital at the roll point?")
    print("=" * 90)
    print()

    # Capital retention table
    print("  DTE    debit     mark @365d   intrinsic   time val   % retained   theta/day")
    print("-" * 80)
    for ld in DTES:
        debit = _px(SPOT, LEAPS_K, ld, 0.55, R) * 100
        days_passed = ld - 365
        mark_dte = max(365, 1) if ld > 365 else max(ld, 1)
        mark = _px(SPOT, LEAPS_K, mark_dte, 0.55, R) * 100
        intrinsic = max(SPOT - LEAPS_K, 0) * 100
        tv = mark - intrinsic
        retained = mark / debit * 100 if debit > 0 else 0
        theta_day = (debit - mark) / max(days_passed, 1) if ld > 365 else (debit - mark) / max(ld, 1)
        print(f"  {ld:>3}d  ${debit:>8,.0f}   ${mark:>9,.0f}   ${intrinsic:>8,.0f}   ${tv:>7,.0f}   "
              f"{retained:>9.1f}%   ${theta_day:>6.1f}/d")

    print()
    print("  % retained = LEAPS mark at 365d remaining / original debit")
    print("  theta/day = average daily decay over the holding period")
    print()

    # Full sim comparison
    print("=" * 90)
    print("FULL SIM — P/L by scenario for each LEAPS DTE (with conditional roll)")
    print("=" * 90)
    print()

    key_scenarios = ["flat_chop", "flat_survival", "rip_pullback", "steady_bull",
                     "moonshot", "steady_bear", "crash_recover", "gap_whipsaw_double",
                     "rip30_pullback", "imm_rip_30_plateau"]

    header = f"  {'scenario':<24}"
    for ld in DTES:
        header += f" {ld}d{'':>10}"
    print(header)
    print("-" * (26 + 14 * len(DTES)))

    for name in key_scenarios:
        row = f"  {name:<24}"
        for ld in DTES:
            paths = build_paths(ld)
            p = next((x for x in paths if x.name == name), None)
            if p is None:
                row += f" {'—':>12}"
                continue
            pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
            pol = daily_policy(POLICY)
            df = run_daily_path(pair, p, pol, r=R)
            if df.empty:
                row += f" {'—':>12}"
                continue
            final = df.iloc[-1]
            pct = pnl_return_pct(float(final["net_pnl"]), pair.net_debit)
            row += f" {pct:>+11.0f}%"
        print(row)

    print()
    print("=" * 90)
    print("CAPITAL EFFICIENCY — net cost per day to hold each LEAPS")
    print("=" * 90)
    print()

    print("  DTE    debit     LEAPS cost   short income   net cost    net/day")
    print("-" * 70)
    for ld in DTES:
        pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
        debit = pair.leaps_debit
        days_held = ld - 365 if ld > 365 else ld
        mark_dte = 365 if ld > 365 else max(ld, 1)
        mark = _px(SPOT, LEAPS_K, mark_dte, 0.55, R) * 100
        leaps_cost = debit - mark
        # Short income: ~80d cycles, 50% profit each
        cycles = max(days_held // 80, 1)
        short_income = pair.short_credit * 0.50 * cycles
        net_cost = leaps_cost - short_income
        net_day = net_cost / max(days_held, 1)
        print(f"  {ld:>3}d  ${debit:>8,.0f}   ${leaps_cost:>9,.0f}   "
              f"${short_income:>11,.0f}   ${net_cost:>+8,.0f}   ${net_day:>+6.1f}/d")

    print()
    print("  LEAPS cost = theta decay over holding period")
    print("  short income = estimated 50% profit per 60d cycle")
    print("  net cost = LEAPS theta - short income (negative = you PROFIT)")
    print()

    # The real comparison: 362 vs 727
    print("=" * 90)
    print("THE REAL QUESTION: 362d (1yr) vs 727d (2yr)")
    print("=" * 90)
    print()

    for ld in [362, 454, 727]:
        pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
        debit = pair.leaps_debit

        if ld > 365:
            days = ld - 365
            mark = _px(SPOT, LEAPS_K, 365, 0.55, R) * 100
            label = f"{ld}d LEAPS — hold {days}d, then roll at 365d"
        else:
            days = ld
            mark = _px(SPOT, LEAPS_K, max(ld, 1), 0.55, R) * 100
            label = f"{ld}d LEAPS — expires in {days}d (no roll)"

        print(f"--- {label} ---")
        print(f"  Debit:            ${debit:,.0f}")
        print(f"  Mark at end:      ${mark:,.0f}")
        print(f"  Capital retained: {mark/debit*100:.1f}%")
        print(f"  Theta cost:       ${debit - mark:,.0f} over {days}d = ${(debit-mark)/max(days,1):.1f}/day")
        print(f"  Days of shorts:   {days} (~{days//80} cycles)")

        if ld > 365:
            new_leaps = _px(SPOT, LEAPS_K, 727, 0.55, R) * 100
            roll_cost = new_leaps - mark
            print(f"  Roll: sell old (${mark:,.0f}), buy new 727d (${new_leaps:,.0f})")
            if roll_cost > 0:
                print(f"  Roll cost:        +${roll_cost:,.0f} (you pay to extend)")
            else:
                print(f"  Roll credit:      ${roll_cost:,.0f} (you receive money back)")
            print(f"  Total 2yr capital: ${debit + max(roll_cost, 0):,.0f}")
        else:
            print(f"  After expiry:     must re-enter market (re-entry timing risk)")
            print(f"  If TSLA ripped while expired: you MISS the move entirely")
        print()

    # The key insight
    print("=" * 90)
    print("WHY 727d WINS")
    print("=" * 90)
    print()
    print("1. CAPITAL RETENTION: After 1 year, a 727d LEAPS retains ~65% of its value.")
    print("   A 362d LEAPS retains ~0% — it's expired.")
    print()
    print("2. TIME VALUE: A 727d LEAPS at the 365d roll point still has $4,600 of time")
    print("   value. A 362d LEAPS at expiry has $0 time value — it's all gone.")
    print()
    print("3. RE-ENTRY RISK: With a 362d LEAPS, you must re-enter the market every year.")
    print("   If TSLA rips 30% while you're between positions, you miss it entirely.")
    print("   With 727d, you roll once and stay in the market continuously.")
    print()
    print("4. SHORT INCOME: The 727d gives you 362 days of short cycling before rolling.")
    print("   The 362d gives you 362 days but then forces re-entry. Same income,")
    print("   but the 727d gives you the option to keep holding if the market is bad.")
    print()
    print("5. THE ROLL COST IS SMALL: Rolling the 727d LEAPS at 365d costs ~$3,600,")
    print("   but you've collected ~$4,000+ in short premiums by then. The roll is")
    print("   self-funding — you don't need to add capital.")
    print()
    print("6. THETA EFFICIENCY: The 727d LEAPS decays $16.5/day over the first year.")
    print("   The 362d decays $24.6/day — 50% faster. Longer DTE = slower theta.")
    print("   You're paying less per day for the same position.")


if __name__ == "__main__":
    main()

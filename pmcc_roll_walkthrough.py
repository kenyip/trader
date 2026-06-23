#!/usr/bin/env python3
"""Walk through short call roll mechanics near expiration with actual premiums."""

from __future__ import annotations
import pricing
from pmcc.playthrough import _px, _roll_strike, POLICY_BY_PRESET


def main():
    spot_entry = 400.49
    leaps_strike = 410
    short_strike = 460
    short_dte_orig = 89
    r = 0.04
    policy = POLICY_BY_PRESET["managed"]

    short_credit_entry = _px(spot_entry, short_strike, short_dte_orig, 0.45, r) * 0.97 * 100
    leaps_debit = _px(spot_entry, leaps_strike, 726, 0.55, r) * 100

    print("=" * 80)
    print("ROLL NEAR EXPIRY — SHORT $460 CALL, SPOT RIPS TO $500 AND STAYS")
    print("=" * 80)
    print(f"Entry: spot=${spot_entry:.2f}  short=${short_strike} {short_dte_orig}d  credit=${short_credit_entry:,.0f}")
    print(f"LEAPS: ${leaps_strike} 726d  debit=${leaps_debit:,.0f}")
    print(f"Rip: spot -> $500 (short is $40 ITM)")
    print()

    # Summary table
    header = (
        f"{'DTE':>4}  {'short mark':>11}  {'intrinsic':>10}  {'time val':>9}  "
        f"{'new strike':>10}  {'new credit':>10}  {'net roll':>10}  {'vs assign':>10}"
    )
    print(header)
    print("-" * len(header))

    for dte_left in [60, 45, 30, 21, 14, 7, 3, 1, 0]:
        spot = 500.0
        if dte_left > 30:
            iv = 0.55
        elif dte_left > 14:
            iv = 0.50
        elif dte_left > 7:
            iv = 0.45
        elif dte_left > 0:
            iv = 0.40
        else:
            iv = 0.35

        short_mid = _px(spot, short_strike, max(dte_left, 0), iv, r)
        short_buyback = short_mid * 1.01 * 100
        intrinsic = max(spot - short_strike, 0) * 100
        time_value = short_buyback - intrinsic

        new_strike = _roll_strike(spot, short_strike, leaps_strike, policy)
        new_dte = policy.short_dte_new
        new_iv = iv * 0.92
        new_credit = _px(spot, new_strike, new_dte, new_iv, r) * 0.97 * 100
        net_roll = short_buyback - new_credit

        vs_assign = intrinsic - net_roll

        print(
            f"{dte_left:>4}d  ${short_buyback:>10,.0f}  ${intrinsic:>9,.0f}  "
            f"${time_value:>8,.0f}  ${new_strike:>9,.0f}  ${new_credit:>9,.0f}  "
            f"${net_roll:>+9,.0f}  ${vs_assign:>+9,.0f}"
        )

    print()

    # Detailed walk-through at key points
    scenarios = [
        (60, "60 DTE — plenty of time, short just went ITM"),
        (30, "30 DTE — comfortable decision window"),
        (21, "21 DTE — should decide soon"),
        (14, "14 DTE — gamma risk rising"),
        (7, "7 DTE — MUST act this week"),
        (3, "3 DTE — emergency, gamma is extreme"),
        (0, "0 DTE — EXPIRY (assignment incoming)"),
    ]

    for dte_left, label in scenarios:
        spot = 500.0
        if dte_left > 30:
            iv = 0.55
        elif dte_left > 14:
            iv = 0.50
        elif dte_left > 7:
            iv = 0.45
        elif dte_left > 0:
            iv = 0.40
        else:
            iv = 0.35

        short_mid = _px(spot, short_strike, max(dte_left, 0), iv, r)
        short_buyback = short_mid * 1.01 * 100
        intrinsic = max(spot - short_strike, 0) * 100
        time_value = short_buyback - intrinsic

        new_strike = _roll_strike(spot, short_strike, leaps_strike, policy)
        new_dte = policy.short_dte_new
        new_iv = iv * 0.92
        new_credit = _px(spot, new_strike, new_dte, new_iv, r) * 0.97 * 100
        net_roll = short_buyback - new_credit

        print(f"--- {label} ---")
        print(f"  IV assumed: {iv:.0%}")
        print(f"  Short $460 mark:     ${short_buyback:,.0f}")
        print(f"    intrinsic:         ${intrinsic:,.0f}  ($40 ITM x 100)")
        print(f"    time value:        ${time_value:,.0f}  (this decays to $0 by expiry)")

        if dte_left > 0:
            print(f"  Buy back short:      -${short_buyback:,.0f}")
            print(f"  Sell new ${new_strike:.0f} ({new_dte}d):  +${new_credit:,.0f}")
            print(f"  Net roll cost:       ${net_roll:+,.0f}", "(YOU PAY)" if net_roll > 0 else "(YOU RECEIVE)")
            print(f"  If you DON'T roll:   -${intrinsic:,.0f} at expiry (assignment)")
            print(f"  Rolling saves you:   ${intrinsic - net_roll:,.0f} vs assignment")
            print(f"  New short OTM by:    ${new_strike - spot:.0f} ({(new_strike - spot) / spot * 100:.0f}%)")
        else:
            print(f"  TOO LATE — short is assigned at expiry")
            print(f"  You must deliver 100 shares at $460 (sell at $460)")
            print(f"  But you own LEAPS $410 — exercise to buy at $410")
            print(f"  Net spread settle:   ${(460 - 410) * 100:+,.0f}")
            print(f"  Plus original credit: ${short_credit_entry:,.0f}")
            print(f"  Minus LEAPS debit:    -${leaps_debit:,.0f}")
            print(f"  Total P/L:            ${(460 - 410) * 100 + short_credit_entry - leaps_debit:+,.0f}")
        print()

    # Now show what happens at different spot prices at 14 DTE
    print("=" * 80)
    print("ROLL COST AT DIFFERENT SPOT PRICES (14 DTE remaining on short)")
    print("=" * 80)
    print()
    spots = [440, 460, 480, 500, 520, 550, 600]
    print(f"{'spot':>6}  {'ITM by':>8}  {'buyback':>9}  {'new strike':>10}  {'new credit':>10}  {'net roll':>9}  {'vs assign':>9}")
    print("-" * 75)
    for spot in spots:
        iv = 0.50
        dte_left = 14
        short_mid = _px(spot, short_strike, dte_left, iv, r)
        short_buyback = short_mid * 1.01 * 100
        intrinsic = max(spot - short_strike, 0) * 100
        new_strike = _roll_strike(spot, short_strike, leaps_strike, policy)
        new_dte = policy.short_dte_new
        new_credit = _px(spot, new_strike, new_dte, iv * 0.92, r) * 0.97 * 100
        net_roll = short_buyback - new_credit
        itm = max(spot - short_strike, 0)
        vs_assign = intrinsic - net_roll
        print(
            f"${spot:>5}  ${itm:>7,.0f}  ${short_buyback:>8,.0f}  "
            f"${new_strike:>9,.0f}  ${new_credit:>9,.0f}  "
            f"${net_roll:>+8,.0f}  ${vs_assign:>+8,.0f}"
        )

    # The key insight: roll "up and out" vs just closing
    print()
    print("=" * 80)
    print("ROLL UP-AND-OUT vs JUST CLOSE (spot=$500, 14 DTE)")
    print("=" * 80)
    print()
    spot = 500.0
    iv = 0.50
    dte_left = 14
    short_buyback = _px(spot, short_strike, dte_left, iv, r) * 1.01 * 100

    # Option A: just close, take the loss, no new short
    print(f"Option A: CLOSE ONLY (take the loss, hold LEAPS naked)")
    print(f"  Buy back $460 short:    -${short_buyback:,.0f}")
    print(f"  Short leg P/L:          ${short_credit_entry - short_buyback:+,.0f}")
    print(f"  LEAPS still open:       yes (unlimited upside now)")
    print(f"  No new short income:    $0 going forward")
    print()

    # Option B: roll up and out (standard)
    new_strike = _roll_strike(spot, short_strike, leaps_strike, policy)
    new_dte = policy.short_dte_new
    new_credit = _px(spot, new_strike, new_dte, iv * 0.92, r) * 0.97 * 100
    net_roll = short_buyback - new_credit
    print(f"Option B: ROLL UP-AND-OUT (close $460, sell ${new_strike:.0f} {new_dte}d)")
    print(f"  Buy back $460 short:    -${short_buyback:,.0f}")
    print(f"  Sell new ${new_strike:.0f} {new_dte}d:      +${new_credit:,.0f}")
    print(f"  Net roll cost:          ${net_roll:+,.0f}")
    print(f"  New short OTM by:       ${new_strike - spot:.0f} ({(new_strike - spot) / spot * 100:.0f}%)")
    print(f"  New short gives you:    ${new_credit:,.0f} of new premium income")
    print()

    # Option C: roll to different strikes
    print(f"Option C: ROLL TO DIFFERENT STRIKES (spot=$500, 14 DTE, new 90d)")
    print(f"{'new strike':>10}  {'OTM %':>7}  {'new credit':>10}  {'net roll':>9}  {'coverage of buyback':>20}")
    for new_k in [530, 540, 550, 560, 570, 580, 600, 650]:
        new_cr = _px(spot, float(new_k), new_dte, iv * 0.92, r) * 0.97 * 100
        net = short_buyback - new_cr
        otm_pct = (new_k - spot) / spot * 100
        coverage = new_cr / short_buyback * 100
        print(f"${new_k:>9}  {otm_pct:>6.0f}%  ${new_cr:>9,.0f}  ${net:>+8,.0f}  {coverage:>18.0f}%")

    print()
    print("=" * 80)
    print("THE KEY DYNAMIC: time value is your friend")
    print("=" * 80)
    print()
    print("At 60 DTE, the short $460 at spot $500 has significant time value.")
    print("At 7 DTE, almost all the value is intrinsic — time value is gone.")
    print()
    print("The roll cost = buyback - new credit.")
    print("  - Buyback DECREASES as DTE drops (time value decays)")
    print("  - New credit is roughly the same (90-day new short)")
    print("  - So the NET ROLL COST DECREASES as you approach expiry")
    print()
    print("BUT: the intrinsic ($4,000) is ALWAYS there until you close.")
    print("Rolling early: you pay buyback (intrinsic + time value)")
    print("Rolling late:  you pay buyback (intrinsic only, time value = $0)")
    print("Assignment:    you pay intrinsic only (same as late roll, but forced)")
    print()
    print("CONCLUSION: Waiting to roll saves you the time value you'd pay")
    print("on the buyback. But gamma risk rises near expiry — if spot drops")
    print("$20 in the last week, the short might go OTM and expire worthless.")


if __name__ == "__main__":
    main()

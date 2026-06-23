#!/usr/bin/env python3
"""Roll-out comparison: different DTEs, and the 'stock drops after you close' scenario.

Addresses the trader's core fear: close the short, stock drops, no premium income,
LEAPS bleeding. Compares roll-up-and-out (various DTEs) vs close-only.
"""

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

    print("=" * 85)
    print("THE ASSIGNMENT QUESTION — you don't own shares, you own LEAPS")
    print("=" * 85)
    print()
    print("If the short $460 call is assigned, you must SELL 100 shares at $460.")
    print("You don't have shares. Two ways to fulfill:")
    print()
    print("  Option 1: BUY at market ($500), deliver at $460")
    print(f"    Loss = ($500 - $460) x 100 = -$4,000")
    print(f"    LEAPS: KEPT (still have time value + upside)")
    print(f"    Short: GONE (no more premium income)")
    print()
    print("  Option 2: EXERCISE LEAPS (buy at $410), deliver at $460")
    print(f"    Spread = ($460 - $410) x 100 = +$5,000")
    print(f"    LEAPS: DESTROYED (forfeit ALL remaining time value)")
    print(f"    Short: GONE")
    print()

    # Show how much LEAPS time value you'd forfeit
    spot = 500.0
    leaps_dte_left = 600
    leaps_iv = 0.55
    leaps_mark = _px(spot, leaps_strike, leaps_dte_left, leaps_iv, r) * 100
    leaps_intrinsic = max(spot - leaps_strike, 0) * 100
    leaps_time_value = leaps_mark - leaps_intrinsic

    print(f"  At spot $500 with {leaps_dte_left}d left on LEAPS:")
    print(f"    LEAPS mark:        ${leaps_mark:,.0f}")
    print(f"    LEAPS intrinsic:   ${leaps_intrinsic:,.0f}  (what you get if exercised)")
    print(f"    LEAPS time value:  ${leaps_time_value:,.0f}  (FORFEITED if exercised)")
    print()
    print(f"  So Option 2 actually costs you: ${leaps_time_value:,.0f} in forfeited time value")
    print(f"  Option 1 (buy at market) costs: $4,000 but keeps the ${leaps_time_value:,.0f} time value")
    print()
    print("  ==> Assignment is catastrophic either way. ROLL BEFORE EXPIRY.")
    print()

    print("=" * 85)
    print("ROLL UP-AND-OUT TO DIFFERENT DTEs (spot=$500, 14 DTE on $460 short)")
    print("=" * 85)
    print()
    print("The question: how far OUT in time should you roll the new short?")
    print()

    iv = 0.45
    dte_left = 14
    short_buyback = _px(spot, short_strike, dte_left, iv, r) * 1.01 * 100

    # Roll to different DTEs and strikes
    new_dtes = [30, 45, 60, 75, 90, 120, 150, 180]
    new_strikes = [530, 540, 550, 560, 575]

    print(f"Buyback $460 short (14 DTE): ${short_buyback:,.0f}")
    print()
    print(f"{'':>3}  ", end="")
    for nd in new_dtes:
        print(f"{nd}d{'':>10}", end="")
    print()
    print(f"{'strike':>8}", end="")
    for nd in new_dtes:
        print(f"{'credit':>7} {'net':>7}", end="")
    print()
    print("-" * 100)

    for ns in new_strikes:
        otm_pct = (ns - spot) / spot * 100
        print(f"${ns:>6} ({otm_pct:>3.0f}%)", end="")
        for nd in new_dtes:
            new_iv = iv * 0.92
            new_credit = _px(spot, float(ns), nd, new_iv, r) * 0.97 * 100
            net_roll = short_buyback - new_credit
            print(f"  ${new_credit:>5,.0f} ${net_roll:>+6,.0f}", end="")
        print()

    print()
    print("Reading: net = buyback - new credit. Negative = you RECEIVE money on the roll.")
    print("         Positive = you PAY to roll. Lower = better for the roll.")
    print()

    # Detail for a few specific combos
    print("=" * 85)
    print("DETAILED ROLL COMPARISONS (spot=$500, 14 DTE on $460 short)")
    print("=" * 85)
    print()

    roll_options = [
        ("$530 / 45d", 530, 45, "Close to spot, short DTE — quick cycle, high challenge risk"),
        ("$530 / 90d", 530, 90, "Close to spot, long DTE — more credit, more challenge risk"),
        ("$550 / 45d", 550, 45, "10% OTM, short DTE — balanced, re-decide in 6 weeks"),
        ("$550 / 90d", 550, 90, "10% OTM, long DTE — standard managed preset"),
        ("$550 / 150d", 550, 150, "10% OTM, long DTE — lock in credit, less management"),
        ("$575 / 90d", 575, 90, "15% OTM, long DTE — safer, less credit"),
        ("$575 / 150d", 575, 150, "15% OTM, very long — safe + decent credit"),
        ("$650 / 90d", 650, 90, "30% OTM, long DTE — very safe, low credit"),
    ]

    print(f"{'roll to':<16} {'credit':>8} {'net roll':>9} {'daily θ':>8} {'Δ new':>6} {'break-even':>10}")
    print("-" * 70)
    for label, ns, nd, desc in roll_options:
        new_iv = iv * 0.92
        new_credit = _px(spot, float(ns), nd, new_iv, r) * 0.97 * 100
        net_roll = short_buyback - new_credit
        # New short theta per day
        T = nd / 365.0
        theta = pricing.theta(spot, float(ns), T, new_iv, "call", r=r) / 365.0 * 100
        new_delta = pricing.delta(spot, float(ns), T, new_iv, "call", r=r)
        # Break-even: spot above which new short loses money
        # Approximate: strike + credit/100
        breakeven = ns + new_credit / 100
        print(f"{label:<16} ${new_credit:>6,.0f} ${net_roll:>+8,.0f} ${theta:>+7.1f} {new_delta:>5.2f} ${breakeven:>8,.0f}")

    print()
    print("daily θ = theta per day on the new short (income you collect daily)")
    print("Δ new = delta of new short (higher = more challenge risk)")
    print("break-even = spot above which the new short starts losing")
    print()

    # THE KEY SCENARIO: stock drops after you act
    print("=" * 85)
    print("THE SCENARIO THAT BIT YOU: stock drops after closing/rolling")
    print("=" * 85)
    print()
    print("Setup: You sold $460 at $400 spot. Stock ripped to $500. It's 14 DTE.")
    print("You need to act. Three choices. Then stock drops back to $420 over 30 days.")
    print()

    # LEAPS value at different spots
    leaps_dte_at_action = 712  # 14 days into the sim
    leaps_dte_after_drop = 712 - 30  # 30 days later

    # At action time (spot=500)
    leaps_at_500 = _px(500, leaps_strike, leaps_dte_at_action, 0.55, r) * 100

    # After stock drops to 420 (30 days later)
    leaps_at_420 = _px(420, leaps_strike, leaps_dte_after_drop, 0.50, r) * 100

    # --- Choice A: CLOSE ONLY (buy back short, no new short) ---
    print("--- CHOICE A: CLOSE ONLY — buy back $460, take the loss, LEAPS naked ---")
    print(f"  Day 0 (spot $500):")
    print(f"    Buy back $460 short:     -${short_buyback:,.0f}")
    print(f"    Short leg realized P/L:  ${short_credit_entry - short_buyback:+,.0f}")
    print(f"    LEAPS mark:              ${leaps_at_500:,.0f}")
    print(f"    Net position value:      ${leaps_at_500 - leaps_debit + (short_credit_entry - short_buyback):+,.0f}")
    print(f"  Day 30 (spot drops to $420):")
    print(f"    LEAPS mark:              ${leaps_at_420:,.0f}")
    print(f"    LEAPS P/L vs entry:      ${leaps_at_420 - leaps_debit:+,.0f}")
    print(f"    Short income (30 days):  $0  ← NO PREMIUM INCOME")
    print(f"    Total P/L:               ${leaps_at_420 - leaps_debit + (short_credit_entry - short_buyback):+,.0f}")
    print(f"    THIS IS THE CURSE: LEAPS lost ${leaps_at_500 - leaps_at_420:,.0f}, no income to offset")
    print()

    # --- Choice B: ROLL UP AND OUT to $550/90d ---
    ns, nd = 550, 90
    new_iv = iv * 0.92
    new_credit_b = _px(spot, float(ns), nd, new_iv, r) * 0.97 * 100
    net_roll_b = short_buyback - new_credit_b

    # After 30 days at spot 420, the new $550/90d short (now 60d) is worth?
    new_short_dte_after = nd - 30
    new_short_mark_at_420 = _px(420, float(ns), new_short_dte_after, 0.45, r) * 1.01 * 100

    print(f"--- CHOICE B: ROLL to $550/{nd}d — keep both legs ---")
    print(f"  Day 0 (spot $500):")
    print(f"    Buy back $460 short:     -${short_buyback:,.0f}")
    print(f"    Sell $550 {nd}d:           +${new_credit_b:,.0f}")
    print(f"    Net roll cost:           ${net_roll_b:+,.0f}")
    print(f"    LEAPS mark:              ${leaps_at_500:,.0f}")
    print(f"  Day 30 (spot drops to $420):")
    print(f"    LEAPS mark:              ${leaps_at_420:,.0f}")
    print(f"    LEAPS P/L vs entry:      ${leaps_at_420 - leaps_debit:+,.0f}")
    print(f"    New $550 short mark:     ${new_short_mark_at_420:,.0f}  (nearly worthless!)")
    print(f"    Short unrealized P/L:    ${new_credit_b - new_short_mark_at_420:+,.0f}")
    print(f"    Short income potential:  ${new_credit_b:,.0f} if expires OTM")
    print(f"    Total P/L (mark-to-mkt): ${leaps_at_420 - leaps_debit + (short_credit_entry - short_buyback) + (new_credit_b - new_short_mark_at_420):+,.0f}")
    print(f"    ==> The short INCOME offsets the LEAPS decay!")
    print()

    # --- Choice C: ROLL to $575/150d (further out) ---
    ns2, nd2 = 575, 150
    new_credit_c = _px(spot, float(ns2), nd2, new_iv, r) * 0.97 * 100
    net_roll_c = short_buyback - new_credit_c
    new_short_dte_after_c = nd2 - 30
    new_short_mark_at_420_c = _px(420, float(ns2), new_short_dte_after_c, 0.45, r) * 1.01 * 100

    print(f"--- CHOICE C: ROLL to $575/{nd2}d — further out, more credit ---")
    print(f"  Day 0 (spot $500):")
    print(f"    Buy back $460 short:     -${short_buyback:,.0f}")
    print(f"    Sell $575 {nd2}d:          +${new_credit_c:,.0f}")
    print(f"    Net roll cost:           ${net_roll_c:+,.0f}")
    print(f"    LEAPS mark:              ${leaps_at_500:,.0f}")
    print(f"  Day 30 (spot drops to $420):")
    print(f"    LEAPS mark:              ${leaps_at_420:,.0f}")
    print(f"    LEAPS P/L vs entry:      ${leaps_at_420 - leaps_debit:+,.0f}")
    print(f"    New $575 short mark:     ${new_short_mark_at_420_c:,.0f}")
    print(f"    Short unrealized P/L:    ${new_credit_c - new_short_mark_at_420_c:+,.0f}")
    print(f"    Short income potential:  ${new_credit_c:,.0f} if expires OTM")
    print(f"    Total P/L (mark-to-mkt): ${leaps_at_420 - leaps_debit + (short_credit_entry - short_buyback) + (new_credit_c - new_short_mark_at_420_c):+,.0f}")
    print()

    # --- The full picture at different drop levels ---
    print("=" * 85)
    print("STOCK DROPS FROM $500 — comparing the three choices at different drop levels")
    print("(30 days after the roll decision)")
    print("=" * 85)
    print()
    drop_spots = [500, 480, 460, 440, 420, 400, 380]
    print(f"{'spot':>6}  {'A: close only':>14}  {'B: roll $550/90d':>16}  {'C: roll $575/150d':>17}  {'B - A':>8}  {'C - A':>8}")
    print("-" * 80)

    for ds in drop_spots:
        dte_after = 30
        leaps_mark_drop = _px(ds, leaps_strike, leaps_dte_after_drop, 0.50, r) * 100
        leaps_pl = leaps_mark_drop - leaps_debit

        # Choice A: close only
        a_total = leaps_pl + (short_credit_entry - short_buyback)

        # Choice B: roll to 550/90d, now 60d
        b_short_mark = _px(ds, 550, 90 - dte_after, 0.45, r) * 1.01 * 100
        b_total = leaps_pl + (short_credit_entry - short_buyback) + (new_credit_b - b_short_mark)

        # Choice C: roll to 575/150d, now 120d
        c_short_mark = _px(ds, 575, 150 - dte_after, 0.45, r) * 1.01 * 100
        c_total = leaps_pl + (short_credit_entry - short_buyback) + (new_credit_c - c_short_mark)

        print(f"${ds:>5}  ${a_total:>+12,.0f}  ${b_total:>+14,.0f}  ${c_total:>+15,.0f}  ${b_total - a_total:>+7,.0f}  ${c_total - a_total:>+7,.0f}")

    print()
    print("B - A / C - A = how much better rolling is vs closing-only, at each spot level")
    print("Positive = rolling beats closing. The further the stock drops, the more rolling wins.")

    # --- What if stock keeps ripping? ---
    print()
    print("=" * 85)
    print("STOCK KEEPS RIPPING FROM $500 — comparing the three choices")
    print("(30 days after the roll decision)")
    print("=" * 85)
    print()
    rip_spots = [500, 520, 540, 560, 580, 600, 650]
    print(f"{'spot':>6}  {'A: close only':>14}  {'B: roll $550/90d':>16}  {'C: roll $575/150d':>17}  {'B - A':>8}  {'C - A':>8}")
    print("-" * 80)

    for rs in rip_spots:
        leaps_mark_rip = _px(rs, leaps_strike, leaps_dte_after_drop, 0.50, r) * 100
        leaps_pl = leaps_mark_rip - leaps_debit

        a_total = leaps_pl + (short_credit_entry - short_buyback)

        b_short_mark = _px(rs, 550, 90 - 30, 0.50, r) * 1.01 * 100
        b_total = leaps_pl + (short_credit_entry - short_buyback) + (new_credit_b - b_short_mark)

        c_short_mark = _px(rs, 575, 150 - 30, 0.50, r) * 1.01 * 100
        c_total = leaps_pl + (short_credit_entry - short_buyback) + (new_credit_c - c_short_mark)

        print(f"${rs:>5}  ${a_total:>+12,.0f}  ${b_total:>+14,.0f}  ${c_total:>+15,.0f}  ${b_total - a_total:>+7,.0f}  ${c_total - a_total:>+7,.0f}")

    print()
    print("When stock keeps ripping, closing-only wins (unlimited LEAPS upside).")
    print("Rolling caps your upside with the new short. This is the tradeoff.")


if __name__ == "__main__":
    main()

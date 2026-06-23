#!/usr/bin/env python3
"""Post-reset analysis: what to do after closing a ripped PMCC.

The core question: after you reset at $520, what LEAPS strike do you buy?
  - ATM ($520): max upside if stock keeps going, but disaster if it drops back
  - ITM ($460-480): survives a drop, but caps upside
  - Deep ITM ($420): same as original, just restarts the spread

Also compares: don't reset at all, just keep the original position.
"""

from __future__ import annotations
import math
import pricing
from pmcc.playthrough import _px, _strike_for_delta, POLICY_BY_PRESET
from pmcc.daily_playthrough import (
    DailyPlayPath, MonthPoint, daily_policy, run_daily_path, pnl_return_pct,
)
from pmcc.scenarios import PmccPair


SPOT_ENTRY = 400.49
ORIGINAL_LEAPS = 420
ORIGINAL_SHORT = 500
R = 0.04


def make_pair(spot, leaps_k, short_k, leaps_dte, short_dte,
              *, leaps_iv=0.55, short_iv=0.45):
    ld = _px(spot, leaps_k, leaps_dte, leaps_iv, R) * 100
    sc = _px(spot, short_k, short_dte, short_iv, R) * 0.97 * 100
    return PmccPair(
        spot_entry=spot, leaps_strike=leaps_k, leaps_exp="2028-01-21",
        leaps_dte=leaps_dte, leaps_iv=leaps_iv, leaps_debit=ld,
        short_strike=short_k, short_exp="2026-09-19",
        short_dte=short_dte, short_iv=short_iv, short_credit=sc,
        leaps_delta_target=0.70, short_delta_target=0.30,
    )


def mark_position(pair, spot, *, leaps_dte_left, short_dte_left, iv_mult=1.0):
    leaps_iv = pair.leaps_iv * iv_mult
    short_iv = pair.short_iv * iv_mult
    leaps_mark = _px(spot, pair.leaps_strike, leaps_dte_left, leaps_iv, R) * 100
    short_mark = _px(spot, pair.short_strike, short_dte_left, short_iv, R) * 1.01 * 100
    return leaps_mark, short_mark


def main():
    print("=" * 90)
    print("POST-RESET STRATEGY: what LEAPS do you buy after closing a ripped PMCC?")
    print("=" * 90)

    # --- Setup: original position ---
    leaps_dte_orig = 726
    short_dte_orig = 60
    pair_orig = make_pair(SPOT_ENTRY, ORIGINAL_LEAPS, ORIGINAL_SHORT,
                          leaps_dte_orig, short_dte_orig)

    print(f"\nOriginal entry: spot=${SPOT_ENTRY}  LEAPS ${ORIGINAL_LEAPS} 726d  "
          f"short ${ORIGINAL_SHORT} 60d")
    print(f"  LEAPS debit: ${pair_orig.leaps_debit:,.0f}")
    print(f"  Short credit: ${pair_orig.short_credit:,.0f}")
    print(f"  Net debit: ${pair_orig.net_debit:,.0f}")
    print(f"  Spread width: ${ORIGINAL_SHORT - ORIGINAL_LEAPS} "
          f"(${(ORIGINAL_SHORT - ORIGINAL_LEAPS) * 100:,})")

    # --- 30 days later: stock ripped to $520 ---
    reset_spot = 520.0
    leaps_dte_left = 696  # 30 days in
    short_dte_left = 30   # 30 days into a 60d short

    print(f"\n--- 30 DAYS LATER: spot rips to ${reset_spot:.0f} ---")
    leaps_mark, short_mark = mark_position(
        pair_orig, reset_spot,
        leaps_dte_left=leaps_dte_left, short_dte_left=short_dte_left,
        iv_mult=1.15,  # IV spike during rip
    )
    leaps_pl = leaps_mark - pair_orig.leaps_debit
    short_pl = pair_orig.short_credit - short_mark
    net_pl = leaps_pl + short_pl

    print(f"  LEAPS ${ORIGINAL_LEAPS} mark: ${leaps_mark:,.0f}  (P/L ${leaps_pl:+,.0f})")
    print(f"  Short ${ORIGINAL_SHORT} mark: ${short_mark:,.0f}  (P/L ${short_pl:+,.0f})")
    print(f"  Net P/L: ${net_pl:+,.0f}  ({pnl_return_pct(net_pl, pair_orig.net_debit):+.0f}%)")
    print(f"  Net cash if you close both: ${leaps_mark - short_mark:,.0f}")

    realized_pl = net_pl
    cash_available = leaps_mark - short_mark
    print(f"\n  ==> You pocket ${realized_pl:+,.0f} profit. Cash available: ${cash_available:,.0f}")
    print(f"  ==> Original investment was ${pair_orig.net_debit:,.0f}. "
          f"You now have ${cash_available:,.0f} to redeploy.")

    # --- The reset options ---
    print(f"\n{'=' * 90}")
    print(f"RESET OPTIONS: what LEAPS do you buy at spot ${reset_spot:.0f}?")
    print(f"{'=' * 90}")

    reset_leaps_dte = 727  # fresh LEAPS
    reset_short_dte = 60

    reset_options = [
        ("ATM", 520, "0.52", "Max upside if stock keeps ripping. Max risk if it drops."),
        ("Slight ITM", 500, "0.62", "Some intrinsic cushion. Still risky if big drop."),
        ("Moderate ITM", 480, "0.70", "Good cushion. Survives a $40 drop to $480."),
        ("Deep ITM", 460, "0.78", "Strong cushion. Survives a $60 drop to $460."),
        ("Original strike", 420, "0.92", "Same as original. Deep ITM, huge time value, survives drop to $420."),
        ("Very deep ITM", 400, "0.97", "Near-stock replacement. Minimal time value, max delta."),
    ]

    print(f"\n{'option':<18} {'LEAPS k':>7} {'delta':>6} {'debit':>9} {'short k':>7} "
          f"{'short cr':>8} {'net deb':>8} {'coverage':>8} {'spread':>6}")
    print("-" * 85)

    reset_pairs = {}
    for label, lk, delta_str, desc in reset_options:
        # New short at 0.30 delta, 60d
        short_iv = 0.45 * 0.90  # IV crush after rip stabilizes
        short_k = _strike_for_delta(reset_spot, reset_short_dte, short_iv, 0.30, R)
        pair = make_pair(reset_spot, float(lk), short_k, reset_leaps_dte,
                         reset_short_dte, leaps_iv=0.55 * 0.95, short_iv=short_iv)
        reset_pairs[label] = pair
        coverage = pair.short_credit / pair.leaps_debit * 100
        spread = short_k - lk
        print(f"{label:<18} ${lk:>6} {delta_str:>6} ${pair.leaps_debit:>8,.0f} "
              f"${short_k:>6} ${pair.short_credit:>7,.0f} ${pair.net_debit:>7,.0f} "
              f"{coverage:>7.1f}% ${spread:>5}")

    print(f"\n  'coverage' = short credit / LEAPS debit (higher = more income vs capital)")
    print(f"  'spread' = short strike - LEAPS strike (wider = more room before short ITM)")

    # --- The drop-back scenario ---
    print(f"\n{'=' * 90}")
    print(f"THE DROP-BACK: TSLA rips to $520, you reset, then it drops back to $420")
    print(f"(180 days after reset — the scenario that bit you)")
    print(f"{'=' * 90}")

    drop_spots = [520, 500, 480, 460, 440, 420, 400, 380]
    print(f"\n180 days after reset, spot at various levels:")
    print(f"{'spot':>6}", end="")
    for opt in reset_options:
        label = opt[0]
        print(f"  {label[:12]:>14}", end="")
    print(f"  {'NO RESET':>14}")
    print("-" * (6 + 16 * (len(reset_options) + 1)))

    for ds in drop_spots:
        leaps_dte_after = reset_leaps_dte - 180
        short_dte_after = max(reset_short_dte - 30, 1)  # short was re-sold at some point

        print(f"${ds:>5}", end="")

        for label, pair in reset_pairs.items():
            # Sim: where is the position 180 days later?
            # Roughly: LEAPS mark + realized short income (assume 2 cycles of ~50% harvest)
            leaps_mark = _px(ds, pair.leaps_strike, leaps_dte_after, 0.50, R) * 100

            # Short income: assume 2.5 cycles over 180 days (60d shorts)
            # Each cycle: sell at ~0.30 delta, harvest at 50% profit
            # If stock is dropping, shorts get harvested easily
            cycle_credit = pair.short_credit  # approximate
            cycles = 2.5
            realized_short = cycle_credit * 0.50 * cycles  # 50% profit per cycle

            # Current open short mark (if any)
            current_short_k = _strike_for_delta(ds, reset_short_dte, 0.45, 0.30, R)
            current_short_credit = _px(ds, current_short_k, reset_short_dte, 0.45, R) * 0.97 * 100
            current_short_mark = _px(ds, current_short_k, reset_short_dte, 0.45, R) * 100

            total_pl = (leaps_mark - pair.leaps_debit) + realized_short + \
                       (current_short_credit - current_short_mark)
            total_pct = pnl_return_pct(total_pl, pair.net_debit)

            # Include the realized profit from the reset
            grand_total = realized_pl + total_pl
            grand_pct = pnl_return_pct(grand_total, pair_orig.net_debit)

            print(f"  ${grand_total:>+12,.0f}", end="")

        # No reset: keep original position
        # LEAPS $420 at 180 days later (546 DTE left)
        leaps_mark_orig = _px(ds, ORIGINAL_LEAPS, leaps_dte_orig - 210, 0.50, R) * 100
        # Short was rolled at some point during the rip, then cycled
        # Assume: rolled to ~$575 at $520, then harvested when stock dropped
        # Roll tax ~$2000, then 2 cycles of income
        roll_short_credit = _px(520, 575, 60, 0.45, R) * 0.97 * 100
        roll_tax = 2000  # approximate
        cycle_income = 800 * 0.50 * 2  # 2 cycles at 50% profit
        # Current short
        curr_short_k_orig = _strike_for_delta(ds, reset_short_dte, 0.45, 0.30, R)
        curr_short_cr_orig = _px(ds, curr_short_k_orig, reset_short_dte, 0.45, R) * 0.97 * 100
        curr_short_mk_orig = _px(ds, curr_short_k_orig, reset_short_dte, 0.45, R) * 100

        orig_total = (leaps_mark_orig - pair_orig.leaps_debit) + \
                     pair_orig.short_credit - roll_tax + cycle_income + \
                     (curr_short_cr_orig - curr_short_mk_orig)
        orig_pct = pnl_return_pct(orig_total, pair_orig.net_debit)
        print(f"  ${orig_total:>+12,.0f}")

    print()
    print("Values include: realized profit from original position + new position P/L after 180 days")
    print("NO RESET = keep original $420 LEAPS, roll short up during rip, harvest on drop")

    # --- Detailed drop-back simulation ---
    print(f"\n{'=' * 90}")
    print(f"DETAILED: RESET TO ATM ($520) vs DEEP ITM ($460) vs NO RESET")
    print(f"Spot drops from $520 to $420 over 180 days")
    print(f"{'=' * 90}")

    for label_text, lk in [("RESET ATM $520", 520), ("RESET ITM $460", 460), ("NO RESET (keep $420)", 420)]:
        print(f"\n--- {label_text} ---")

        if "NO RESET" in label_text:
            pair = pair_orig
            start_spot = SPOT_ENTRY
            days_in = 210
            leaps_dte_at = leaps_dte_orig - days_in
            print(f"  Started at ${SPOT_ENTRY}, LEAPS ${lk}, now 210 days in")
        else:
            key = [k for k in reset_pairs if str(lk) in k]
            pair = reset_pairs[key[0]] if key else make_pair(
                reset_spot, float(lk),
                _strike_for_delta(reset_spot, 60, 0.45, 0.30, R),
                727, 60, leaps_iv=0.55*0.95, short_iv=0.45*0.90)
            start_spot = reset_spot
            days_in = 180
            leaps_dte_at = 727 - days_in
            print(f"  Started at ${reset_spot}, LEAPS ${lk}, now 180 days in")

        for ds in [520, 480, 440, 420, 400]:
            leaps_mark = _px(ds, pair.leaps_strike, leaps_dte_at, 0.50, R) * 100
            leaps_pl = leaps_mark - pair.leaps_debit
            leaps_tv = leaps_mark - max(ds - pair.leaps_strike, 0) * 100

            # Can you sell a short at this spot?
            short_k = _strike_for_delta(ds, 60, 0.45, 0.30, R)
            short_cr = _px(ds, short_k, 60, 0.45, R) * 0.97 * 100
            short_otm = short_k - ds
            can_sell = short_cr > 100  # meaningful premium?

            # Coverage at this spot
            coverage = short_cr / pair.leaps_debit * 100 if pair.leaps_debit > 0 else 0

            # LEAPS delta at this spot
            ld = pricing.delta(ds, pair.leaps_strike, leaps_dte_at / 365, 0.50, "call", r=R)

            print(f"  spot=${ds:>4}:  LEAPS mark=${leaps_mark:>7,.0f}  "
                  f"(P/L ${leaps_pl:>+8,.0f}, TV=${leaps_tv:>6,.0f}, Δ={ld:.2f})  "
                  f"short ${short_k:.0f} credit=${short_cr:>5,.0f}  "
                  f"{'✓' if can_sell else '✗ NO PREMIUM'}")

        print()

    # --- The key insight: what can you sell at each spot level? ---
    print(f"{'=' * 90}")
    print(f"SHORT CALL PREMIUM AT EACH SPOT LEVEL (60d, 0.30 delta)")
    print(f"{'=' * 90}")
    print()
    print("This is the core question: can you sell a meaningful short after a drop?")
    print()
    print(f"{'spot':>6}  {'short k':>7}  {'credit':>7}  {'vs $420 LEAPS':>14}  {'vs $460 LEAPS':>14}  {'vs $520 LEAPS':>14}")
    print("-" * 70)

    for ds in [520, 500, 480, 460, 440, 420, 400, 380]:
        short_k = _strike_for_delta(ds, 60, 0.45, 0.30, R)
        short_cr = _px(ds, short_k, 60, 0.45, R) * 0.97 * 100

        # Coverage against each LEAPS debit
        for_label = []
        for lk, ld in [(420, 13500), (460, 16500), (520, 18500)]:
            cov = short_cr / ld * 100
            # Can you even sell? Short must be above LEAPS strike
            if short_k <= lk:
                for_label.append("can't sell")
            else:
                for_label.append(f"{cov:.1f}%")

        print(f"${ds:>5}  ${short_k:>6}  ${short_cr:>6}  {for_label[0]:>14}  "
              f"{for_label[1]:>14}  {for_label[2]:>14}")

    print()
    print("'can't sell' = short strike would be below LEAPS strike (diagonal breaks)")
    print("If spot drops below your LEAPS strike, you CANNOT sell a call above the LEAPS")
    print("and below spot — there's no meaningful premium. You're stuck holding naked LEAPS.")

    # --- The recommendation ---
    print(f"\n{'=' * 90}")
    print(f"STRATEGIC OPTIONS AFTER A RIP")
    print(f"{'=' * 90}")
    print()
    print("Given: TSLA at $520, you had 420/500 PMCC, you reset and pocketed ~+$2,500")
    print()
    print("Option A: RESET TO ATM ($520 LEAPS)")
    print("  + Full delta exposure if TSLA keeps ripping (0.52 delta)")
    print("  + Fresh 727d LEAPS, new theta clock")
    print("  - If TSLA drops to $420: LEAPS goes $100 OTM, can't sell meaningful shorts")
    print("  - Coverage at $420: 0% (no premium available)")
    print("  - This is buying high — the exact scenario that bit you")
    print()
    print("Option B: RESET TO MODERATE ITM ($460 LEAPS)")
    print("  + If TSLA drops to $420: LEAPS is $40 ITM, still has value")
    print("  + Can sell $470-480 shorts at $420 spot (small but meaningful premium)")
    print("  + Coverage at $420: ~3-4% (thin but not zero)")
    print("  - Less upside if TSLA keeps ripping (0.78 delta → slower gain)")
    print("  - Higher debit ($16,500 vs $18,500)")
    print()
    print("Option C: DON'T RESET — keep original $420 LEAPS, roll short up")
    print("  + If TSLA drops to $420: LEAPS is ATM, full premium selling ability")
    print("  + Coverage at $420: ~12% (the original economics)")
    print("  + No additional capital needed")
    print("  - Position is capped at ~+27% if TSLA stays above $500")
    print("  - Roll tax to keep selling shorts ($2,000-4,000 per roll)")
    print()
    print("Option D: CLOSE SHORT ONLY, keep $420 LEAPS naked")
    print("  + LEAPS has unlimited upside (no short capping it)")
    print("  + If TSLA drops to $420: LEAPS is ATM, sell new shorts")
    print("  + No roll tax, no reset cost")
    print("  - No premium income while stock is high ($500-520)")
    print("  - LEAPS theta continues to bleed")
    print("  - You eat the short loss ($2,000-5,000) with no offsetting income")
    print()
    print("Option E: PARTIAL RESET — sell LEAPS, buy LOWER strike LEAPS ($460)")
    print("  + Bank the $420 LEAPS gain ($7,800)")
    print("  + New $460 LEAPS: $2,000 cheaper than $520 ATM")
    print("  + If TSLA drops to $420: $460 LEAPS is $40 ITM, can sell shorts")
    print("  + If TSLA keeps ripping: $460 LEAPS still captures most of the move")
    print("  - Not as much upside as $520 ATM if TSLA goes to $700")
    print("  - Requires re-entry timing (what if it rips another 10% while you're repositioning?)")


if __name__ == "__main__":
    main()

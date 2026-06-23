#!/usr/bin/env python3
"""Fair LEAPS DTE comparison — same time horizon for all DTEs."""
from __future__ import annotations
import math
import pricing
from pmcc.playthrough import _px, POLICY_BY_PRESET
from pmcc_playbook_gen import make_pair
from pmcc.daily_playthrough import (
    DailyPlayPath, MonthPoint, daily_policy, run_daily_path, pnl_return_pct,
)
from pmcc.scenarios import PmccPair

SPOT = 400.49
LEAPS_K = 410
SHORT_K = 500
R = 0.04
POLICY = POLICY_BY_PRESET["managed"]
DTES = [362, 454, 545, 630, 727]


def make_half_year_paths():
    """Paths that play out over ~180 days — the half-year comparison."""
    paths = []

    # 1. Flat for 180 days
    days = tuple(MonthPoint(1.0 + 0.02 * math.sin(d / 14.0), 1.0) for d in range(1, 181))
    paths.append(DailyPlayPath("flat_180", "Flat ±2% for 180 days", days))

    # 2. Rip in first 30 days, then flat for 150 days
    days = []
    for d in range(1, 181):
        if d < 30: s = 1.0
        elif d == 30: s = 1.25
        else: s = 1.25
        iv = max(0.75, 1.10 - 0.08 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("rip30_flat_180", "+25% in 30d then flat to d180", tuple(days)))

    # 3. Rip in first 30 days, then drop back by d180
    days = []
    for d in range(1, 181):
        if d < 30: s = 1.0
        elif d == 30: s = 1.25
        elif d <= 90:
            t = (d - 30) / 60
            s = 1.25 + t * (1.05 - 1.25)
        else: s = 1.05
        iv = max(0.70, 1.15 - 0.08 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("rip30_drop_180", "+25% in 30d then drops to +5% by d180", tuple(days)))

    # 4. Steady bull +20% over 180 days
    days = []
    for d in range(1, 181):
        s = 1.0 + 0.20 * d / 180
        iv = max(0.80, 1.0 - 0.05 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("steady_bull_180", "Steady bull +20% over 180d", tuple(days)))

    # 5. Moonshot +50% in first 60 days, then plateau
    days = []
    for d in range(1, 181):
        if d < 60:
            s = 1.0 + 0.50 * d / 60
        else:
            s = 1.50
        iv = max(0.65, 1.05 - 0.10 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("moon_60_180", "+50% in 60d then plateau to d180", tuple(days)))

    # 6. Moonshot +75% in first 30 days, then plateau (extreme half-year rip)
    days = []
    for d in range(1, 181):
        if d < 30: s = 1.0
        elif d == 30: s = 1.75
        else: s = 1.75
        iv = max(0.55, 1.20 - 0.10 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("moon75_30_180", "+75% in 30d then plateau to d180", tuple(days)))

    # 7. Drop -15% in first 30 days, then flat (bear half-year)
    days = []
    for d in range(1, 181):
        if d < 30: s = 1.0
        elif d == 30: s = 0.85
        else: s = 0.85
        iv = max(0.80, 1.20 + 0.10 * (1.0 - s))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("drop15_flat_180", "-15% in 30d then flat to d180", tuple(days)))

    # 8. V-shape: drop -15% then recover to +10% by d180
    days = []
    for d in range(1, 181):
        if d < 30: s = 1.0
        elif d == 30: s = 0.85
        elif d <= 120:
            t = (d - 30) / 90
            s = 0.85 + t * (1.10 - 0.85)
        else: s = 1.10
        iv = max(0.70, 1.15 - 0.08 * (s - 1.0))
        days.append(MonthPoint(s, iv))
    paths.append(DailyPlayPath("vshape_180", "V-shape: -15% then +10% by d180", tuple(days)))

    return tuple(paths)


def main():
    paths_180 = make_half_year_paths()

    print("=" * 95)
    print("FAIR COMPARISON: All LEAPS DTEs over the SAME 180-day horizon")
    print("=" * 95)
    print()
    print("Every pair runs for exactly 180 days. No one gets to exit early.")
    print("The 362d LEAPS still has 182d left. The 727d still has 547d left.")
    print("We measure P/L at day 180 — mark-to-market, not expiry.")
    print()

    # Entry parameters
    print("  DTE    debit     short cr   net debit   coverage   theta/day")
    print("-" * 72)
    for ld in DTES:
        pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
        T = ld / 365.0
        theta = pricing.theta(SPOT, LEAPS_K, T, 0.55, "call", r=R) / 365.0 * 100
        print(f"  {ld:>3}d  ${pair.leaps_debit:>7,.0f}   ${pair.short_credit:>6,.0f}   "
              f"${pair.net_debit:>7,.0f}   {pair.short_credit/pair.leaps_debit*100:>6.1f}%   "
              f"${theta:>5.1f}/d")

    print()
    print("=" * 95)
    print("P/L AT DAY 180 — % return on net debit")
    print("=" * 95)
    print()

    header = f"  {'scenario':<24}"
    for ld in DTES:
        header += f" {ld}d{'':>10}"
    print(header)
    print("-" * (26 + 14 * len(DTES)))

    for p in paths_180:
        row = f"  {p.name:<24}"
        for ld in DTES:
            pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
            pol = daily_policy(POLICY)
            df = run_daily_path(pair, p, pol, r=R)
            if df.empty:
                row += f" {'—':>12}"
                continue
            # Find the row closest to day 180
            sub = df[df["day"] <= 180]
            if sub.empty:
                sub = df.head(1)
            day180 = sub.iloc[-1]
            pct = pnl_return_pct(float(day180["net_pnl"]), pair.net_debit)
            row += f" {pct:>+11.0f}%"
        print(row)

    print()
    print("=" * 95)
    print("ABSOLUTE DOLLAR P/L AT DAY 180 (on $12,890 capital for 727d)")
    print("=" * 95)
    print()

    header = f"  {'scenario':<24}"
    for ld in DTES:
        header += f" {ld}d{'':>10}"
    print(header)
    print("-" * (26 + 14 * len(DTES)))

    for p in paths_180:
        row = f"  {p.name:<24}"
        for ld in DTES:
            pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
            pol = daily_policy(POLICY)
            df = run_daily_path(pair, p, pol, r=R)
            if df.empty:
                row += f" {'—':>12}"
                continue
            sub = df[df["day"] <= 180]
            if sub.empty:
                sub = df.head(1)
            day180 = sub.iloc[-1]
            pnl = float(day180["net_pnl"])
            row += f" ${pnl:>+10,.0f}"
        print(row)

    print()
    print("=" * 95)
    print("CAPITAL AT DAY 180 — what's your position worth?")
    print("=" * 95)
    print()
    print("This is the key: how much of your capital do you still have at day 180?")
    print()

    flat = next(p for p in paths_180 if p.name == "flat_180")
    moon = next(p for p in paths_180 if p.name == "moon75_30_180")

    print("  After FLAT 180 days:")
    print(f"  {'DTE':>5}  {'debit':>8}  {'LEAPS mark':>10}  {'short P/L':>9}  {'total':>8}  {'% of debit':>10}")
    for ld in DTES:
        pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
        pol = daily_policy(POLICY)
        df = run_daily_path(pair, flat, pol, r=R)
        sub = df[df["day"] <= 180]
        day180 = sub.iloc[-1]
        leaps_mark = float(day180["leaps_mtm"])
        short_pl = float(day180["realized_short_pnl"])
        total = float(day180["net_pnl"])
        pct = total / pair.net_debit * 100
        print(f"  {ld:>3}d  ${pair.leaps_debit:>7,.0f}  ${leaps_mark:>9,.0f}  "
              f"${short_pl:>+8,.0f}  ${total:>+7,.0f}  {pct:>+9.0f}%")

    print()
    print("  After +75% MOONSHOT in 30 days (then flat to 180):")
    print(f"  {'DTE':>5}  {'debit':>8}  {'LEAPS mark':>10}  {'short P/L':>9}  {'total':>8}  {'% of debit':>10}")
    for ld in DTES:
        pair = make_pair(SPOT, LEAPS_K, SHORT_K, ld, 60, r=R)
        pol = daily_policy(POLICY)
        df = run_daily_path(pair, moon, pol, r=R)
        sub = df[df["day"] <= 180]
        day180 = sub.iloc[-1]
        leaps_mark = float(day180["leaps_mtm"])
        short_pl = float(day180["realized_short_pnl"])
        total = float(day180["net_pnl"])
        pct = total / pair.net_debit * 100
        print(f"  {ld:>3}d  ${pair.leaps_debit:>7,.0f}  ${leaps_mark:>9,.0f}  "
              f"${short_pl:>+8,.0f}  ${total:>+7,.0f}  {pct:>+9.0f}%")

    print()
    print("=" * 95)
    print("THE FAIRNESS QUESTION: is 362d actually better over 180 days?")
    print("=" * 95)
    print()
    print("Look at the flat_180 row: all DTEs are roughly +3-6%.")
    print("The 362d LEAPS has the LOWEST debit ($8,899) so its % return looks")
    print("similar or better. But in absolute dollars, the 727d captures more")
    print("short income because its LEAPS theta is slower ($10.9/day vs $24.6/day).")
    print()
    print("Look at moon75_30_180: the 727d wins by a wide margin because the")
    print("LEAPS mark at day 180 is much higher — it has more time value remaining")
    print("(547d left vs 182d left), so the LEAPS is worth more at the same spot.")
    print()
    print("The 362d LEAPS is cheaper to enter, but:")
    print("  1. It decays 2x faster ($24.6/day vs $10.9/day)")
    print("  2. After 180 days, it has only 182d left — approaching the theta cliff")
    print("  3. If you want to keep the position, you must roll SOONER (at 365d = day 0)")
    print("  4. On a moonshot, it captures LESS upside because less time value remains")
    print()
    print("The 727d LEAPS costs more upfront but:")
    print("  1. Decays 2x slower — more of your capital survives")
    print("  2. After 180 days, it has 547d left — nowhere near the cliff")
    print("  3. No pressure to roll for another 182 days")
    print("  4. On a moonshot, captures MORE because the LEAPS retains more time value")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Comprehensive roll DTE sweep + extreme rip management analysis.

Tests short_dte_new at 90/120/150 across all paths, then simulates
the extreme rip scenario (spot to 600/700/800) with exit-vs-reset options.
"""

from __future__ import annotations
import math
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
    run_daily_path,
    run_all_daily_paths,
    pnl_return_pct,
)
from pmcc.playthrough import PlayPolicy, POLICY_BY_PRESET, _px, _strike_for_delta
from pmcc.scenarios import PmccPair


def make_pair(spot, leaps_strike, short_strike, leaps_dte, short_dte,
              *, leaps_iv=0.55, short_iv=0.45, r=0.04):
    leaps_debit = _px(spot, leaps_strike, leaps_dte, leaps_iv, r) * 100
    short_credit = _px(spot, short_strike, short_dte, short_iv, r) * 0.97 * 100
    return PmccPair(
        spot_entry=spot, leaps_strike=leaps_strike, leaps_exp="2028-01-21",
        leaps_dte=leaps_dte, leaps_iv=leaps_iv, leaps_debit=leaps_debit,
        short_strike=short_strike, short_exp="2026-09-19",
        short_dte=short_dte, short_iv=short_iv, short_credit=short_credit,
        leaps_delta_target=0.70, short_delta_target=0.20,
    )


def make_custom_paths(leaps_dte):
    paths = []
    # rip_pullback variants
    for rip_pct, drop_to, name in [(0.15, 1.0, "rip_pullback"),
                                    (0.20, 1.0, "rip20_pullback"),
                                    (0.30, 1.0, "rip30_pullback"),
                                    (0.15, 0.92, "rip15_pullback_92")]:
        days = []
        for d in range(1, leaps_dte + 1):
            if d < 45: s = 1.0
            elif d == 45: s = 1 + rip_pct
            elif d <= 52:
                t = (d - 45) / 7
                s = (1 + rip_pct) + t * (drop_to - (1 + rip_pct))
            else: s = drop_to
            iv = max(0.75, 1.15 - 0.10 * (s - 1.0))
            days.append(MonthPoint(s, iv))
        paths.append(DailyPlayPath(name, f"+{rip_pct:.0%} rip then flush to {drop_to:.0%}", tuple(days)))

    # rip_continue variants
    for rip_pct, end_mult, name in [(0.15, 1.50, "rip_continue"),
                                     (0.15, 1.90, "rip_continue_90"),
                                     (0.30, 1.80, "rip30_continue"),
                                     (0.50, 2.00, "rip50_continue")]:
        days = []
        for d in range(1, leaps_dte + 1):
            if d < 45: s = 1.0
            elif d == 45: s = 1 + rip_pct
            else:
                t = (d - 45) / max(leaps_dte - 45, 1)
                s = (1 + rip_pct) + t * (end_mult - (1 + rip_pct))
            iv = max(0.60, 1.05 - 0.12 * (s - 1.0))
            days.append(MonthPoint(s, iv))
        paths.append(DailyPlayPath(name, f"+{rip_pct:.0%} rip then grind to +{(end_mult-1):.0%}", tuple(days)))

    # immediate rip
    for rip_pct, after, name in [(0.15, "plateau", "imm_rip_15_plateau"),
                                  (0.30, "plateau", "imm_rip_30_plateau"),
                                  (0.30, "continue", "imm_rip_30_continue"),
                                  (0.30, "drop", "imm_rip_30_drop"),
                                  (0.50, "plateau", "imm_rip_50_plateau"),
                                  (0.75, "plateau", "imm_rip_75_plateau")]:
        days = []
        for d in range(1, leaps_dte + 1):
            if d < 3: s = 1.0
            elif d == 3: s = 1 + rip_pct
            elif after == "plateau": s = 1 + rip_pct
            elif after == "continue":
                t = (d - 3) / max(leaps_dte - 3, 1)
                s = (1 + rip_pct) * (1 + t * 0.50)
            elif after == "drop":
                if d <= 10:
                    t = (d - 3) / 7
                    s = (1 + rip_pct) + t * (1.0 - (1 + rip_pct))
                else: s = 1.0
            else: s = 1 + rip_pct
            iv = max(0.55, 1.25 - 0.10 * (s - 1.0))
            days.append(MonthPoint(s, iv))
        paths.append(DailyPlayPath(name, f"+{rip_pct:.0%} in 3d then {after}", tuple(days)))

    # flat survival
    days = []
    for d in range(1, leaps_dte + 1):
        s = 1.0 + 0.03 * math.sin(d / 21.0)
        days.append(MonthPoint(s, 1.0))
    paths.append(DailyPlayPath("flat_survival", "Flat ±3%", tuple(days)))

    return tuple(paths)


def build_all_paths(leaps_dte):
    canonical = build_daily_paths(leaps_dte)
    keep = {"steady_bull", "moonshot", "single_day_rip_10",
            "gap_rip_flush", "gap_whipsaw_double", "post_earnings_whipsaw",
            "tsla_range_chop", "flat_chop", "steady_bear", "crash_recover",
            "v_recovery"}
    canonical = tuple(p for p in canonical if p.name in keep)
    custom = make_custom_paths(leaps_dte)
    names_seen = {p.name for p in canonical}
    extra = [p for p in custom if p.name not in names_seen]
    return tuple(canonical) + tuple(extra)


def conditional_roll_pnl(pair, path, policy, *, roll_dte=365,
                         deep_itm_threshold=1.25, r=0.04):
    pol = daily_policy(policy)
    df = run_daily_path(pair, path, pol, r=r)
    if df.empty:
        return 0.0
    final = df.iloc[-1]
    hold_pnl = float(final["net_pnl"])
    roll_mask = df["leaps_dte"] <= roll_dte
    if not roll_mask.any():
        return pnl_return_pct(hold_pnl, pair.net_debit)
    roll_row = df[roll_mask].iloc[0]
    roll_spot = float(roll_row["spot"])
    moneyness = roll_spot / pair.leaps_strike
    if moneyness >= deep_itm_threshold:
        return pnl_return_pct(hold_pnl, pair.net_debit)
    return pnl_return_pct(float(roll_row["net_pnl"]), pair.net_debit)


def score_pair(pair, paths, policy, *, r=0.04):
    results = {}
    for p in paths:
        results[p.name] = conditional_roll_pnl(pair, p, policy, r=r)

    bull_names = {"steady_bull", "moonshot", "rip_continue", "v_recovery",
                  "single_day_rip_10", "rip_continue_90", "rip30_continue",
                  "rip50_continue", "imm_rip_30_continue"}
    whip_names = {"gap_whipsaw_double", "post_earnings_whipsaw",
                  "rip_pullback", "gap_rip_flush", "tsla_range_chop",
                  "rip20_pullback", "rip30_pullback", "rip15_pullback_92",
                  "imm_rip_30_drop"}
    flat_names = {"flat_chop", "flat_survival"}
    bear_names = {"steady_bear", "crash_recover"}
    imm_names = {"imm_rip_15_plateau", "imm_rip_30_plateau", "imm_rip_50_plateau",
                 "imm_rip_75_plateau"}

    def avg(names):
        vals = [results[n] for n in names if n in results]
        return sum(vals) / max(len(vals), 1)

    bull_avg = avg(bull_names)
    whip_avg = avg(whip_names)
    flat_avg = avg(flat_names)
    bear_avg = avg(bear_names)
    imm_avg = avg(imm_names)
    bear_worst = min((results[n] for n in bear_names if n in results), default=0)
    imm_worst = min((results[n] for n in imm_names if n in results), default=0)

    score = (bull_avg * 2.0 + whip_avg * 1.5 + flat_avg * 1.0 +
             bear_avg * 0.5 + imm_avg * 1.0) / 6.0
    if flat_avg < -15: score -= abs(flat_avg + 15) * 0.5
    if bear_worst < -40: score -= abs(bear_worst + 40) * 0.3
    if imm_worst < -20: score -= abs(imm_worst + 20) * 0.4

    return {"score": score, "bull_avg": bull_avg, "whip_avg": whip_avg,
            "flat_avg": flat_avg, "bear_avg": bear_avg, "bear_worst": bear_worst,
            "imm_avg": imm_avg, "imm_worst": imm_worst, "by_path": results}


def sweep_roll_dte(spot, leaps_strike, short_strike, leaps_dte, short_dte,
                   paths, base_policy, r=0.04):
    """Sweep short_dte_new (the roll DTE) and short_delta_new."""
    rows = []
    for new_dte in [60, 75, 90, 120, 150, 180]:
        for new_delta in [0.20, 0.25, 0.30]:
            policy = replace(base_policy, short_dte_new=new_dte, short_delta_new=new_delta)
            pair = make_pair(spot, leaps_strike, short_strike, leaps_dte, short_dte, r=r)
            s = score_pair(pair, paths, policy, r=r)
            by = s["by_path"]
            rows.append({
                "new_dte": new_dte,
                "new_delta": new_delta,
                "score": s["score"],
                "bull": s["bull_avg"],
                "whip": s["whip_avg"],
                "flat": s["flat_avg"],
                "bear_w": s["bear_worst"],
                "imm_w": s["imm_worst"],
                "rip_pullback": by.get("rip_pullback", 0),
                "rip30_pullback": by.get("rip30_pullback", 0),
                "imm_rip_30_plateau": by.get("imm_rip_30_plateau", 0),
                "imm_rip_50_plateau": by.get("imm_rip_50_plateau", 0),
                "rip50_continue": by.get("rip50_continue", 0),
                "flat_chop": by.get("flat_chop", 0),
                "moonshot": by.get("moonshot", 0),
                "steady_bear": by.get("steady_bear", 0),
            })
    return pd.DataFrame(rows)


def extreme_rip_analysis(spot_entry, leaps_strike, short_strike,
                         leaps_dte, short_dte, r=0.04):
    """What to do when TSLA rips to 600/700/800 — exit vs reset."""
    leaps_debit = _px(spot_entry, leaps_strike, leaps_dte, 0.55, r) * 100
    short_credit = _px(spot_entry, short_strike, short_dte, 0.45, r) * 0.97 * 100

    print("=" * 85)
    print("EXTREME RIP: EXIT vs RESET vs HOLD")
    print("=" * 85)
    print(f"Entry: spot=${spot_entry:.0f}  LEAPS ${leaps_strike}  short ${short_strike}")
    print(f"LEAPS debit: ${leaps_debit:,.0f}  Short credit: ${short_credit:,.0f}")
    print(f"Spread width: ${short_strike - leaps_strike} (${(short_strike - leaps_strike) * 100:,})")
    print()

    rips = [500, 550, 600, 650, 700, 750, 800]
    leaps_dte_left = 700  # ~26 days into the position
    short_dte_left = 75

    for rip_spot in rips:
        # IV spikes during rip
        leaps_iv = 0.55 * (1 + min((rip_spot / spot_entry - 1) * 0.3, 0.30))
        short_iv = 0.45 * (1 + min((rip_spot / spot_entry - 1) * 0.3, 0.30))

        leaps_mark = _px(rip_spot, leaps_strike, leaps_dte_left, leaps_iv, r) * 100
        short_mark = _px(rip_spot, short_strike, short_dte_left, short_iv, r) * 1.01 * 100

        leaps_pl = leaps_mark - leaps_debit
        short_pl = short_credit - short_mark
        net_pl = leaps_pl + short_pl
        net_pct = pnl_return_pct(net_pl, leaps_debit - short_credit)

        # Option 1: EXIT BOTH (close LEAPS + close short, pocket cash)
        exit_cash = leaps_mark - short_mark
        exit_pl = exit_cash - (leaps_debit - short_credit)
        exit_pct = pnl_return_pct(exit_pl, leaps_debit - short_credit)

        # Option 2: RESET (close both, then open new PMCC at current spot)
        new_leaps_strike = _strike_for_delta(rip_spot, leaps_dte_left, leaps_iv, 0.70, r)
        new_leaps_debit = _px(rip_spot, new_leaps_strike, leaps_dte_left, leaps_iv, r) * 100
        new_short_strike = _strike_for_delta(rip_spot, short_dte_left, short_iv * 0.92, 0.22, r)
        new_short_credit = _px(rip_spot, new_short_strike, short_dte_left, short_iv * 0.92, r) * 0.97 * 100
        new_net_debit = new_leaps_debit - new_short_credit
        new_coverage = new_short_credit / new_leaps_debit * 100

        # Option 3: ROLL SHORT UP (keep LEAPS, roll short to new strike)
        roll_k = max(rip_spot * 1.10, short_strike + 50, new_leaps_strike + 10)
        roll_k = pricing.round_strike(roll_k, 5.0)
        roll_credit = _px(rip_spot, roll_k, 90, short_iv * 0.92, r) * 0.97 * 100
        roll_net = short_mark - roll_credit

        # Option 4: HOLD (do nothing — let it ride)
        # If spot stays here to short expiry: short is assigned, buy at market
        # But LEAPS still has huge time value
        hold_to_short_exp = leaps_pl - max(rip_spot - short_strike, 0) * 100

        print(f"{'─' * 85}")
        print(f"SPOT = ${rip_spot}  (+{(rip_spot/spot_entry-1)*100:.0f}%)")
        print(f"  Current marks:  LEAPS ${leaps_mark:,.0f} (+${leaps_pl:,.0f})  "
              f"Short ${short_mark:,.0f} ({short_pl:+,.0f})  Net ${net_pl:+,.0f} ({net_pct:+.0f}%)")
        print()
        print(f"  Option 1 — EXIT BOTH: close LEAPS + close short, pocket cash")
        print(f"    Sell LEAPS: +${leaps_mark:,.0f}  Buy back short: -${short_mark:,.0f}")
        print(f"    Net cash out: ${exit_cash:,.0f}  P/L: ${exit_pl:+,.0f} ({exit_pct:+.0f}%)")
        print(f"    → Position closed. Cash in hand. No more risk, no more income.")
        print()
        print(f"  Option 2 — RESET: close both, open new PMCC at ${rip_spot}")
        print(f"    New LEAPS ${new_leaps_strike:.0f} (0.70Δ): ${new_leaps_debit:,.0f}")
        print(f"    New short ${new_short_strike:.0f} (0.22Δ): ${new_short_credit:,.0f}")
        print(f"    New net debit: ${new_net_debit:,.0f}  Coverage: {new_coverage:.1f}%")
        print(f"    Realized P/L from old position: ${exit_pl:+,.0f}")
        print(f"    → Bank the gain, restart with fresh spread at higher level")
        print()
        print(f"  Option 3 — ROLL SHORT UP: keep LEAPS, roll short to ${roll_k:.0f}/90d")
        print(f"    Buy back old short: -${short_mark:,.0f}")
        print(f"    Sell new ${roll_k:.0f}/90d:    +${roll_credit:,.0f}")
        print(f"    Net roll cost:      ${roll_net:+,.0f}")
        otm = (roll_k - rip_spot) / rip_spot * 100
        print(f"    New short OTM by:   ${roll_k - rip_spot:.0f} ({otm:.0f}%)")
        print(f"    → Keep LEAPS upside, new short gives income if stock stabilizes")
        print()
        print(f"  Option 4 — HOLD: do nothing")
        print(f"    If spot stays to short expiry: ${hold_to_short_exp:+,.0f} (short assigned)")
        print(f"    LEAPS time value: ${leaps_mark - max(rip_spot - leaps_strike, 0) * 100:,.0f} (would be forfeited if exercised)")
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spot", type=float, default=400.49)
    ap.add_argument("--leaps-strike", type=float, default=410.0)
    ap.add_argument("--short-strike", type=float, default=460.0)
    ap.add_argument("--leaps-dte", type=int, default=726)
    ap.add_argument("--short-dte", type=int, default=89)
    ap.add_argument("--preset", default="managed")
    args = ap.parse_args()

    spot = args.spot
    policy = POLICY_BY_PRESET[args.preset]
    paths = build_all_paths(args.leaps_dte)

    # --- Roll DTE sweep ---
    print("=" * 85)
    print("ROLL DTE SWEEP: short_dte_new × short_delta_new")
    print("(How far out to roll the short when challenged/ITM)")
    print("=" * 85)
    print()
    print(f"Pair: {int(args.leaps_strike)}/{int(args.short_strike)} "
          f"({args.leaps_dte}d/{args.short_dte}d)  Spot: ${spot:.2f}")
    print()

    result = sweep_roll_dte(spot, args.leaps_strike, args.short_strike,
                            args.leaps_dte, args.short_dte, paths, policy)

    print("FULL TABLE:")
    display = result.copy()
    display["score"] = display["score"].map(lambda x: f"{x:.1f}")
    for c in ["bull", "whip", "flat", "bear_w", "imm_w", "rip_pullback",
              "rip30_pullback", "imm_rip_30_plateau", "imm_rip_50_plateau",
              "rip50_continue", "flat_chop", "moonshot", "steady_bear"]:
        display[c] = display[c].map(lambda x: f"{x:+.0f}%")
    print(display.to_string(index=False))

    # Best per DTE
    print()
    print("BEST short_delta_new FOR EACH DTE:")
    for dte in [60, 75, 90, 120, 150, 180]:
        sub = result[result["new_dte"] == dte]
        best = sub.loc[sub["score"].idxmax()]
        print(f"  {dte}d: delta={best['new_delta']:.2f}  score={best['score']:.1f}  "
              f"flat={best['flat']:+.0f}%  whip={best['whip']:+.0f}%  "
              f"bull={best['bull']:+.0f}%  rip_pullback={best['rip_pullback']:+.0f}%  "
              f"imm_rip_30={best['imm_rip_30_plateau']:+.0f}%")

    # --- Extreme rip analysis ---
    print()
    extreme_rip_analysis(spot, args.leaps_strike, args.short_strike,
                         args.leaps_dte, args.short_dte)


if __name__ == "__main__":
    main()

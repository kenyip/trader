#!/usr/bin/env python3
"""PMCC scenario playbook generator — walk through each scenario with real premiums.

For a given pair, generates a comprehensive playbook showing:
  1. Entry parameters and premiums
  2. Management rules with actual dollar amounts
  3. Trade-by-trade walkthrough of each scenario
  4. Rip management decision tree
  5. Reset analysis at extreme rips
"""

from __future__ import annotations
import math
import argparse
from pathlib import Path

import pandas as pd
import pricing

from pmcc.daily_playthrough import (
    DailyPlayPath, MonthPoint, build_daily_paths, daily_policy,
    run_daily_path, run_all_daily_paths, pnl_return_pct,
)
from pmcc.playthrough import PlayPolicy, POLICY_BY_PRESET, _px, _roll_strike, _strike_for_delta
from pmcc.scenarios import PmccPair


def make_pair(spot, leaps_k, short_k, leaps_dte, short_dte,
              *, leaps_iv=0.55, short_iv=0.45, r=0.04):
    ld = _px(spot, leaps_k, leaps_dte, leaps_iv, r) * 100
    sc = _px(spot, short_k, short_dte, short_iv, r) * 0.97 * 100
    return PmccPair(
        spot_entry=spot, leaps_strike=leaps_k, leaps_exp="2028-01-21",
        leaps_dte=leaps_dte, leaps_iv=leaps_iv, leaps_debit=ld,
        short_strike=short_k, short_exp="2026-09-19",
        short_dte=short_dte, short_iv=short_iv, short_credit=sc,
        leaps_delta_target=0.70, short_delta_target=0.30,
    )


def make_custom_paths(leaps_dte):
    paths = []
    for rip_pct, drop_to, name in [(0.15, 1.0, "rip_pullback"),
                                    (0.30, 1.0, "rip30_pullback"),
                                    (0.30, 0.92, "rip30_pullback_92")]:
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
        paths.append(DailyPlayPath(name, "", tuple(days)))

    for rip_pct, end_mult, name in [(0.15, 1.50, "rip_continue"),
                                     (0.30, 1.80, "rip30_continue")]:
        days = []
        for d in range(1, leaps_dte + 1):
            if d < 45: s = 1.0
            elif d == 45: s = 1 + rip_pct
            else:
                t = (d - 45) / max(leaps_dte - 45, 1)
                s = (1 + rip_pct) + t * (end_mult - (1 + rip_pct))
            iv = max(0.60, 1.05 - 0.12 * (s - 1.0))
            days.append(MonthPoint(s, iv))
        paths.append(DailyPlayPath(name, "", tuple(days)))

    for rip_pct, after, name in [(0.15, "plateau", "imm_rip_15_plateau"),
                                  (0.30, "plateau", "imm_rip_30_plateau"),
                                  (0.30, "drop", "imm_rip_30_drop")]:
        days = []
        for d in range(1, leaps_dte + 1):
            if d < 3: s = 1.0
            elif d == 3: s = 1 + rip_pct
            elif after == "plateau": s = 1 + rip_pct
            elif after == "drop":
                if d <= 10:
                    t = (d - 3) / 7
                    s = (1 + rip_pct) + t * (1.0 - (1 + rip_pct))
                else: s = 1.0
            else: s = 1 + rip_pct
            iv = max(0.55, 1.25 - 0.10 * (s - 1.0))
            days.append(MonthPoint(s, iv))
        paths.append(DailyPlayPath(name, "", tuple(days)))

    days = []
    for d in range(1, leaps_dte + 1):
        s = 1.0 + 0.03 * math.sin(d / 21.0)
        days.append(MonthPoint(s, 1.0))
    paths.append(DailyPlayPath("flat_survival", "", tuple(days)))

    return tuple(paths)


def build_paths(leaps_dte):
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


def format_log(df, path_name, *, max_rows=30):
    sub = df[df["path"] == path_name].copy()
    if sub.empty:
        return f"(no data for {path_name})"
    action_mask = sub["action"].str.contains(
        "CHALLENGED|GAP RIP|ROLL|CRASH|LEAPS|DROP|SELL new|FLUSH|harvest|"
        "FORCE|EXTREME|DEEP ITM|naked",
        case=False, regex=True,
    )
    keep = sub[action_mask | (sub["day"] % 30 == 0) | (sub["day"] == sub["day"].max())]
    keep = keep.drop_duplicates(subset=["day"]).head(max_rows)

    lines = []
    for _, row in keep.iterrows():
        day = int(row["day"])
        spot = f"${row['spot']:,.0f}"
        ldte = int(row["leaps_dte"]) if pd.notna(row["leaps_dte"]) else "—"
        sk = f"${row['short_strike']:.0f}" if pd.notna(row["short_strike"]) else "—"
        sdte = int(row["short_dte"]) if pd.notna(row["short_dte"]) else "—"
        pnl = f"${row['net_pnl']:+,.0f}"
        rtx = f"${row['roll_tax']:,.0f}" if row["roll_tax"] > 0 else "—"

        lines.append(f"  d{day:>3}  spot {spot:>5}  LEAPS {ldte:>3}d  "
                      f"short {sk:>5} {sdte:>3}d  P/L {pnl:>8}  tax {rtx:>5}")

        actions = str(row["action"]).split(" | ")
        for a in actions:
            if a.strip() and a.strip() != "hold":
                lines.append(f"           → {a.strip()}")

    return "\n".join(lines)


def generate_playbook(pair, policy, spot, *, r=0.04):
    paths = build_paths(pair.leaps_dte)
    pol = daily_policy(policy)
    lines = []
    w = lines.append

    w(f"# PMCC Playbook — {int(pair.leaps_strike)}/{int(pair.short_strike)}")
    w(f"")
    w(f"## Entry Parameters")
    w(f"")
    w(f"| Parameter | Value |")
    w(f"|---|---|")
    w(f"| Spot at entry | ${spot:.2f} |")
    w(f"| LEAPS strike | ${pair.leaps_strike:.0f} |")
    w(f"| LEAPS DTE | {pair.leaps_dte}d |")
    w(f"| LEAPS debit | ${pair.leaps_debit:,.0f} |")
    w(f"| LEAPS delta | {pricing.delta(spot, pair.leaps_strike, pair.leaps_dte/365, pair.leaps_iv, 'call', r=r):.2f} |")
    w(f"| Short strike | ${pair.short_strike:.0f} |")
    w(f"| Short DTE | {pair.short_dte}d |")
    w(f"| Short credit | ${pair.short_credit:,.0f} |")
    w(f"| Short delta | {pricing.delta(spot, pair.short_strike, pair.short_dte/365, pair.short_iv, 'call', r=r):.2f} |")
    w(f"| Net debit | ${pair.net_debit:,.0f} |")
    w(f"| Coverage | {pair.short_credit/pair.leaps_debit*100:.1f}% |")
    w(f"| Short OTM | {(pair.short_strike-spot)/spot*100:.0f}% |")
    w(f"| Spread width | ${pair.short_strike - pair.leaps_strike:.0f} (${(pair.short_strike - pair.leaps_strike)*100:,.0f}) |")
    w(f"")

    w(f"## Management Rules")
    w(f"")
    w(f"### Short Call Management")
    w(f"")
    w(f"1. **Harvest at 50%+ profit** — buy back short when mark drops to 50% of credit")
    harvest_px = pair.short_credit / 100 * (1 - policy.harvest_profit_pct)
    w(f"   - Trigger: short mark <= ${harvest_px:.2f}/sh (${harvest_px*100:.0f}/contract)")
    w(f"   - Action: buy back, bank profit, wait {policy.reentry_cooldown_days}d, sell new {policy.short_dte_new}d short")
    w(f"")
    w(f"2. **Gap-rip roll** — spot jumps {policy.gap_rip_trigger_pct:.0%}+ in one day and approaches short")
    w(f"   - Trigger: spot >= {policy.gap_rip_proximity:.0%} of short strike (${pair.short_strike * policy.gap_rip_proximity:.0f})")
    roll_k = _roll_strike(spot * 1.10, pair.short_strike, pair.leaps_strike, policy)
    w(f"   - Action: close short, roll up to ~${roll_k:.0f} ({policy.short_dte_new}d)")
    w(f"   - Min {policy.min_roll_gap_days}d between rolls (prevents panic rolling)")
    w(f"")
    w(f"3. **Challenged roll** — spot reaches short strike")
    w(f"   - Trigger: spot >= ${pair.short_strike:.0f} (challenged_pct={policy.challenged_pct})")
    w(f"   - Action: close short, roll up to ~${roll_k:.0f}")
    w(f"")
    w(f"4. **Force close at {policy.force_close_dte} DTE** — if short is ITM near expiry")
    w(f"   - Trigger: short DTE <= {policy.force_close_dte}d AND spot >= short strike")
    w(f"   - Action: close short, roll up-and-out")
    w(f"   - NEVER let short expire ITM (assignment forfeits LEAPS time value)")
    w(f"")
    w(f"### LEAPS Management")
    w(f"")
    w(f"1. **Conditional roll at {policy.leaps_roll_dte} DTE remaining** — avoid theta cliff")
    deep_itm_spot = pair.leaps_strike * policy.leaps_deep_itm_threshold
    extreme_itm_spot = pair.leaps_strike * policy.leaps_extreme_itm_threshold
    w(f"   - If spot < ${deep_itm_spot:.0f} ({policy.leaps_deep_itm_threshold:.2f}x strike): ROLL LEAPS")
    w(f"     - Sell LEAPS at mark, buy new 727d LEAPS at 0.70 delta")
    w(f"     - Avoids theta acceleration in final year")
    w(f"   - If spot ${deep_itm_spot:.0f}-${extreme_itm_spot:.0f} ({policy.leaps_deep_itm_threshold:.2f}-{policy.leaps_extreme_itm_threshold:.2f}x): HOLD")
    w(f"     - LEAPS is deep ITM, capture upside, keep selling shorts")
    w(f"   - If spot > ${extreme_itm_spot:.0f} ({policy.leaps_extreme_itm_threshold:.2f}x): CLOSE SHORT, LEAPS NAKED")
    w(f"     - Position is capped at spread value, short limits upside")
    w(f"     - Close short, stop selling, let LEAPS run free")
    w(f"     - Original LEAPS strike is your anchor — never reset to higher strike")
    w(f"")

    # --- Scenario walkthroughs ---
    w(f"## Scenario Walkthroughs")
    w(f"")
    w(f"Each scenario shows the trade-by-trade log with actual premiums and P/L.")
    w(f"")

    scenarios = [
        ("flat_chop", "Flat ±5% chop — the survival test"),
        ("flat_survival", "Flat ±3% sine wave — pure theta"),
        ("steady_bull", "Steady bull +35% — the base case"),
        ("moonshot", "Extreme bull +90% — the TSLA dream"),
        ("rip_pullback", "+15% rip then flush back — the covered-call curse"),
        ("rip_continue", "+15% rip then grind to +50% — rip keeps going"),
        ("rip30_pullback", "+30% rip then flush back — extreme whipsaw"),
        ("gap_whipsaw_double", "Rip+flush twice — quarterly chop"),
        ("post_earnings_whipsaw", "Earnings +12% gap then -8% week"),
        ("steady_bear", "Steady grind down -20% — the risk"),
        ("crash_recover", "Crash -25% then slow recovery"),
        ("v_recovery", "V-shape: -22% then rip to +40%"),
        ("imm_rip_15_plateau", "+15% in 3 days, stays high — immediate rip"),
        ("imm_rip_30_plateau", "+30% in 7 days, stays high — extreme rip"),
        ("imm_rip_30_drop", "+30% in 7 days, drops back — the worst case"),
        ("tsla_range_chop", "Flat net ±7% swings every 3 weeks"),
    ]

    for path_name, desc in scenarios:
        p = next((x for x in paths if x.name == path_name), None)
        if p is None:
            continue
        df = run_daily_path(pair, p, pol, r=r)
        if df.empty:
            continue
        final = df.iloc[-1]
        final_pct = pnl_return_pct(float(final["net_pnl"]), pair.net_debit)
        w(f"### {desc}")
        w(f"")
        w(f"**Final P/L: ${final['net_pnl']:+,.0f} ({final_pct:+.0f}%)** "
          f"at day {int(final['day'])} (LEAPS DTE {int(final['leaps_dte'])})")
        w(f"Rolls: {int(final['roll_count'])}  Roll tax: ${final['roll_tax']:,.0f}")
        w(f"")
        w(f"```")
        w(format_log(df, path_name))
        w(f"```")
        w(f"")

    # --- Rip management decision tree ---
    w(f"## Rip Management Decision Tree")
    w(f"")
    w(f"What to do when TSLA rips after you've sold the short:")
    w(f"")
    w(f"```")
    w(f"Spot rips → IS SHORT STILL OTM?")
    w(f"  │")
    w(f"  ├─ YES (spot < ${pair.short_strike:.0f})")
    w(f"  │   ├─ Spot within 8% of short → GAP RIP ROLL (close + roll up)")
    w(f"  │   │   Roll cost: ~$200-400 (short still has time value)")
    w(f"  │   └─ Spot far from short → HOLD (position is profitable)")
    w(f"  │       LEAPS gains more than short loses (higher delta)")
    w(f"  │")
    w(f"  └─ NO (spot >= ${pair.short_strike:.0f})")
    w(f"      │")
    w(f"      ├─ SHORT DEEPLY ITM (spot > ${pair.short_strike + 40:.0f})?")
    w(f"      │   ├─ DTE > 21 → HOLD (don't panic roll)")
    w(f"      │   │   Roll cost would be $2,000-5,000+ (paying intrinsic)")
    w(f"      │   │   Position is still profitable (LEAPS gaining more)")
    w(f"      │   │")
    w(f"      │   └─ DTE <= 14 → FORCE CLOSE + ROLL UP-AND-OUT")
    w(f"      │       Roll to 10-15% OTM, {policy.short_dte_new}d")
    w(f"      │       Accept the roll cost — assignment is worse")
    w(f"      │")
    w(f"      └─ SHORT SLIGHTLY ITM (spot near ${pair.short_strike:.0f})?")
    w(f"          ├─ DTE > 21 → HOLD, let time value decay")
    w(f"          └─ DTE <= 14 → ROLL UP-AND-OUT")
    w(f"```")
    w(f"")

    # --- Extreme rip: reset analysis ---
    w(f"## Extreme Rip: When to Reset")
    w(f"")
    w(f"If spot exceeds ${pair.leaps_strike * policy.leaps_extreme_itm_threshold:.0f} "
      f"({policy.leaps_extreme_itm_threshold:.2f}x LEAPS strike), the position is capped.")
    w(f"")
    w(f"| Spot | LEAPS mark | Short mark | Net P/L | Net % | Action |")
    w(f"|---|---|---|---|---|---|")

    for rip_mult in [1.15, 1.25, 1.35, 1.50, 1.75, 2.00]:
        rip_spot = spot * rip_mult
        leaps_iv = pair.leaps_iv * (1 + min((rip_mult - 1) * 0.3, 0.30))
        short_iv = pair.short_iv * (1 + min((rip_mult - 1) * 0.3, 0.30))
        leaps_mark = _px(rip_spot, pair.leaps_strike, 696, leaps_iv, r) * 100
        short_mark = _px(rip_spot, pair.short_strike, 30, short_iv, r) * 1.01 * 100
        net = leaps_mark - pair.leaps_debit + pair.short_credit - short_mark
        net_pct = pnl_return_pct(net, pair.net_debit)
        if rip_mult < policy.leaps_deep_itm_threshold:
            action = "Roll short up if challenged"
        elif rip_mult < policy.leaps_extreme_itm_threshold:
            action = "HOLD — deep ITM, keep selling shorts"
        else:
            action = "CLOSE SHORT — LEAPS naked for upside"
        w(f"| ${rip_spot:.0f} | ${leaps_mark:,.0f} | ${short_mark:,.0f} | "
          f"${net:+,.0f} | {net_pct:+.0f}% | {action} |")

    w(f"")
    w(f"**Key insight**: Once spot exceeds {policy.leaps_extreme_itm_threshold:.2f}x LEAPS strike, "
      f"the spread is capped. The short gains $1 for every $1 the LEAPS loses above the short strike. "
      f"Closing the short unlocks unlimited LEAPS upside.")
    w(f"")
    w(f"**Never reset the LEAPS to a higher strike.** The original LEAPS strike is your anchor — "
      f"it's what lets you sell shorts in any market condition. If TSLA drops back, a higher-strike "
      f"LEAPS can't generate premium income. Keep the original LEAPS, manage the short.")
    w(f"")

    # --- Premium reference table ---
    w(f"## Premium Reference: Short Call Credits at Different Spot Levels")
    w(f"")
    w(f"What you can sell a {policy.short_dte_new}d short call for at each spot level:")
    w(f"")
    w(f"| Spot | Short strike (0.30Δ) | Credit | Coverage of LEAPS | Can sell? |")
    w(f"|---|---|---|---|---|")

    for ds in [spot * m for m in [0.75, 0.85, 0.90, 0.95, 1.00, 1.10, 1.15, 1.25, 1.35, 1.50]]:
        short_k = _strike_for_delta(ds, policy.short_dte_new, 0.45, 0.30, r)
        short_cr = _px(ds, short_k, policy.short_dte_new, 0.45, r) * 0.97 * 100
        coverage = short_cr / pair.leaps_debit * 100
        can_sell = "✓" if short_k > pair.leaps_strike and short_cr > 100 else "✗"
        w(f"| ${ds:.0f} | ${short_k:.0f} | ${short_cr:,.0f} | {coverage:.1f}% | {can_sell} |")

    w(f"")
    w(f"'Can sell' = short strike above LEAPS strike AND credit > $100")
    w(f"If spot drops below LEAPS strike (${pair.leaps_strike:.0f}), you cannot sell a "
      f"meaningful short call — the diagonal structure breaks.")
    w(f"")

    # --- Path summary table ---
    w(f"## Summary: P/L by Scenario")
    w(f"")
    w(f"| Scenario | Final P/L | % Return | Day | LEAPS DTE | Rolls | Roll Tax |")
    w(f"|---|---|---|---|---|---|---|")

    _, summary = run_all_daily_paths(pair, paths, pol, r=r)
    for _, row in summary.sort_values("final_pnl", ascending=False).iterrows():
        pct = pnl_return_pct(float(row["final_pnl"]), pair.net_debit)
        w(f"| {row['path']} | ${row['final_pnl']:+,.0f} | {pct:+.0f}% | "
          f"{int(row['days'])} | — | {int(row['roll_count'])} | ${row['roll_tax']:,.0f} |")

    w(f"")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="PMCC scenario playbook generator")
    ap.add_argument("--spot", type=float, default=400.49)
    ap.add_argument("--leaps-strike", type=float, default=410.0)
    ap.add_argument("--short-strike", type=float, default=460.0)
    ap.add_argument("--leaps-dte", type=int, default=726)
    ap.add_argument("--short-dte", type=int, default=60)
    ap.add_argument("--preset", default="managed")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    pair = make_pair(args.spot, args.leaps_strike, args.short_strike,
                     args.leaps_dte, args.short_dte)
    policy = POLICY_BY_PRESET[args.preset]
    playbook = generate_playbook(pair, policy, args.spot)

    if args.out:
        args.out.write_text(playbook)
        print(f"Playbook written to {args.out}")
    else:
        print(playbook)


if __name__ == "__main__":
    main()

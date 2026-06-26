#!/usr/bin/env python3
"""PMCC live manager — daily position status + action recommendations.

Usage:
  just pmcc-manage                    # check all positions in pmcc_positions.yaml
  just pmcc-manage --spot 420         # override spot (for testing scenarios)
  just pmcc-manage --what-if 500      # what-if spot moves to $500
  just pmcc-manage --triggers         # show full trigger playbook for top pair
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from pmcc.positions import (
    load_pmcc_positions, check_pmcc_position, format_pmcc_portfolio,
    PMCC_POSITIONS_PATH, PMCC_SAMPLE,
)
from pmcc.playbook import generate_triggers, format_playbook
from pmcc.income import reentry_candidates
from pmcc.playthrough import POLICY_BY_PRESET
from pmcc.scenarios import PmccPair


def _get_spot(ticker: str = "TSLA") -> float:
    try:
        from pmcc.chain_data import fetch_call_chain
        spot, _chain = fetch_call_chain(ticker)
        return float(spot)
    except Exception:
        pass
    try:
        import yfinance as yf
        return float(yf.Ticker(ticker).fast_info["last_price"])
    except Exception:
        pass
    return 0.0


def format_carry_section(s: dict) -> str:
    c = s["carry"]
    p = s["pair"]
    lines = []
    lines.append("  INCOME PACE / PREMIUM CLOCK")
    lines.append(f"    Short opened:        {c['short_open_date']}  ({c['days_held']} days held, opened ~{c['short_open_dte']} DTE)")
    lines.append(f"    Short credit:        ${c['short_credit']:,.0f}  (${c['full_credit_daily']:.1f}/day full-credit pace — {c['full_credit_pace_label']})")
    lines.append(f"    Current short mark:  ${c['short_mark']:,.0f}")
    lines.append(f"    Current short P/L:   ${c['current_short_profit']:+,.0f}  (${c['current_profit_daily']:+.1f}/day realized-if-closed — {c['current_profit_pace_label']})")
    lines.append(f"    50% harvest level:   buy back ≤ ${c['harvest_mark']:,.0f}, profit ${c['harvest_profit']:,.0f}")
    lines.append(f"    If harvested today:  ${c['harvest_profit_daily_if_today']:.1f}/day pace — {c['harvest_pace_label_if_today']}")
    lines.append("")
    lines.append("    Targets after harvest:")
    lines.append(f"      floor:  ${c['floor_target_daily']:.0f}/day covers {c['floor_days_covered']:.1f} days; wait budget {c['wait_floor_days_after_harvest']:.1f} days")
    lines.append(f"      good:   ${c['good_target_daily']:.0f}/day covers {c['good_days_covered']:.1f} days; wait budget {c['wait_good_days_after_harvest']:.1f} days")
    lines.append(f"      strong: ${c['strong_target_daily']:.0f}/day covers {c['strong_days_covered']:.1f} days; wait budget {c['wait_strong_days_after_harvest']:.1f} days")
    lines.append("")
    lines.append("    LEAPS carry burden, flat-market estimate:")
    lines.append(f"      current LEAPS mark → {c['roll_dte_for_decay']} DTE mark: ${c['leaps_decay_to_roll']:,.0f} decay over {c['days_to_roll_dte']}d")
    lines.append(f"      estimated LEAPS decay: ${c['leaps_decay_daily']:.1f}/day")
    lines.append(f"      net current short pace after LEAPS decay: ${c['net_current_profit_daily']:+.1f}/day")
    lines.append(f"      net full-credit pace after LEAPS decay:   ${c['net_full_credit_daily']:+.1f}/day")
    lines.append("")
    if c['current_short_profit'] >= c['harvest_profit']:
        if c['wait_good_days_after_harvest'] > 0:
            lines.append(f"    Premium clock says: harvest is ahead of good pace; you can wait ~{c['wait_good_days_after_harvest']:.0f}d for a quality reload.")
        else:
            lines.append("    Premium clock says: harvest is not ahead of good pace; reload soon if safe.")
    else:
        remaining = c['harvest_profit'] - c['current_short_profit']
        lines.append(f"    Premium clock says: not at harvest yet; need about ${remaining:,.0f} more short P/L to hit 50% harvest.")
    lines.append("")
    return "\n".join(lines)


def format_reentry_section(s: dict) -> str:
    p = s["pair"]
    spot = s["spot_now"]
    rows = reentry_candidates(spot, p, dte=int(p.short_dte if 45 <= p.short_dte <= 75 else 60), iv=p.short_iv)
    lo = max(p.leaps_strike + 5, spot * 1.05)
    hi = spot * 1.35
    rows = [r for r in rows if lo <= r["strike"] <= hi]
    lines = []
    lines.append("  NEXT SHORT CANDIDATES AFTER HARVEST")
    lines.append("    Aim: reload premium, but do not choke upside. Prefer carry/good income with balanced/wide risk.")
    floor = float(s["record"].get("income_floor_daily", 10.0))
    good = float(s["record"].get("income_good_daily", 15.0))
    strong = float(s["record"].get("income_strong_daily", 20.0))
    lines.append(f"    {'strike':>6}  {'credit':>8}  {'$/day':>6}  {'delta':>5}  {'upside':>7}  {'income':>8}  {'risk':>10}")
    lines.append(f"    {'-' * 62}")
    for r in rows:
        if r["daily"] >= strong:
            income = "strong"
        elif r["daily"] >= good:
            income = "good"
        elif r["daily"] >= floor:
            income = "carry"
        else:
            income = "low"
        marker = ""
        if income in {"carry", "good", "strong"} and r["risk"] in {"balanced", "wide"}:
            marker = "  <-- candidate"
        lines.append(
            f"    ${r['strike']:>5.0f}  ${r['credit']:>7,.0f}  ${r['daily']:>5.1f}  "
            f"{r['delta']:>5.2f}  {r['upside_pct']:>6.1f}%  {income:>8}  {r['risk']:>10}{marker}"
        )
    lines.append("")
    return "\n".join(lines)


def format_leaps_only_detail(s: dict) -> str:
    p = s["pair"]
    spot = s["spot_now"]
    contracts = s["contracts"]
    leaps_mark = s["leaps_mark"]["price"] * 100
    realized_short_total = float(s.get("realized_short_total", 0.0))
    clock = s.get("closed_short_clock") or {}
    lines = []
    lines.append(f"  {'=' * 78}")
    lines.append(f"  {s['record'].get('ticker', 'TSLA')}  LEAPS ONLY  ${p.leaps_strike:.0f} {p.leaps_dte}d  |  Spot ${spot:,.2f}")
    lines.append(f"  {'=' * 78}")
    lines.append("")
    lines.append(f"  POSITION MARKS ({contracts} long LEAPS contract{'s' if contracts > 1 else ''}, no open short)")
    lines.append(f"    LEAPS ${p.leaps_strike:.0f}: mark ${leaps_mark:,.0f}  "
                 f"(debit ${p.leaps_debit:,.0f}, P/L ${s['leaps_leg_pnl']:+,.0f}/long)")
    lines.append(f"    Closed-short realized P/L: ${realized_short_total:+,.0f} total")
    lines.append(f"    NET P/L: ${s['net_pnl']:+,.0f}/long  (${s['net_pnl_total']:+,.0f} total incl. closed shorts)")
    lines.append("")
    if clock:
        lines.append("  CLOSED-SHORT PREMIUM CLOCK")
        lines.append(
            f"    Banked ${clock['realized']:,.0f} from {clock['short_contracts']} closed short contract"
            f"{'s' if clock['short_contracts'] != 1 else ''}; {clock['days_since_open']} day(s) since first open, "
            f"{clock['days_since_close']} day(s) since close."
        )
        lines.append(
            f"    Average so far: ${clock['avg_since_open']:.1f}/day total, "
            f"${clock['avg_per_long_since_open']:.1f}/day per long LEAPS."
        )
        lines.append("    Budget remaining before the bank falls below target:")
        for key in ("strong", "good", "floor"):
            t = clock["targets"][key]
            lines.append(
                f"      {key:>6}: portfolio target ${t['portfolio_target_daily']:.0f}/day "
                f"(${t['target_per_contract']:.0f}/day x {clock['long_contracts']} longs) — "
                f"covers {t['portfolio_days_covered']:.1f} total days; "
                f"wait budget {t['portfolio_wait_days']:.1f}d (until ~{t['portfolio_budget_until']})"
            )
        one = clock["targets"]["good"]
        lines.append(
            f"    One-short lens: at ${one['target_per_contract']:.0f}/day, the closed short alone covers "
            f"{one['one_short_days_covered']:.1f} total days; wait budget {one['one_short_wait_days']:.1f}d."
        )
        lines.append(f"    Reload mode: {clock['reload_mode']}")
        lines.append("")
    lines.append("  NEXT SHORT CANDIDATES")
    lines.append("    Aim: reload income, but avoid choking upside. These are model quotes, not live orders.")
    lines.append(format_reentry_section(s))
    lines.append("  ACTIVE TRIGGERS")
    for check in s["checks"]:
        level_icon = {"alert": "🔴", "warn": "🟡", "ok": "🟢", "info": "🔵"}.get(check["level"], "⚪")
        lines.append(f"    {level_icon} [{check['level'].upper()}] {check['rule']}")
        lines.append(f"       {check['detail']}")
    lines.append("")
    lines.append(f"  >>> NEXT ACTION: [{s['primary_level'].upper()}] {s['primary_action']}")
    lines.append(f"      {s['primary_detail']}")
    lines.append("")
    return "\n".join(lines)


def format_position_detail(s: dict) -> str:
    if s.get("no_open_short"):
        return format_leaps_only_detail(s)

    p = s["pair"]
    pol = s["policy"]
    spot = s["spot_now"]
    lines = []

    lines.append(f"  {'=' * 78}")
    lines.append(f"  {s['record'].get('ticker', 'TSLA')}  "
                 f"LEAPS ${p.leaps_strike:.0f} {p.leaps_dte}d  |  "
                 f"Short ${p.short_strike:.0f} {p.short_dte}d  |  "
                 f"Spot ${spot:,.2f}")
    lines.append(f"  {'=' * 78}")
    lines.append("")

    # Position marks
    leaps_mark = s["leaps_mark"]["price"] * 100
    short_mark = s["short_mark"]["price"] * 100
    contracts = s["contracts"]

    lines.append(f"  POSITION MARKS ({contracts} contract{'s' if contracts > 1 else ''})")
    lines.append(f"    LEAPS ${p.leaps_strike:.0f}:  mark ${leaps_mark:,.0f}  "
                 f"(debit ${p.leaps_debit:,.0f}, P/L ${s['leaps_leg_pnl']:+,.0f})")
    lines.append(f"    Short ${p.short_strike:.0f}:  mark ${short_mark:,.0f}  "
                 f"(credit ${p.short_credit:,.0f}, P/L ${s['short_leg_pnl']:+,.0f})")
    lines.append(f"    NET P/L: ${s['net_pnl']:+,.0f}/ct  (${s['net_pnl_total']:+,.0f} total)")
    lines.append(f"    Spread: ${s['spread_width']:.0f}  |  "
                 f"Roll target: ${s['roll_target']:.0f}")
    lines.append("")
    lines.append(format_carry_section(s))
    lines.append(format_reentry_section(s))

    # Key levels
    deep_itm = p.leaps_strike * pol.leaps_deep_itm_threshold
    extreme_itm = p.leaps_strike * pol.leaps_extreme_itm_threshold
    harvest_px = (p.short_credit / 100) * (1 - pol.harvest_profit_pct)

    lines.append(f"  KEY LEVELS")
    lines.append(f"    LEAPS strike:         ${p.leaps_strike:.0f}")
    lines.append(f"    Short strike:         ${p.short_strike:.0f}  ({(p.short_strike/spot-1)*100:+.0f}% from spot)")
    lines.append(f"    LEAPS deep ITM:       ${deep_itm:.0f}  (hold LEAPS)")
    lines.append(f"    LEAPS extreme ITM:    ${extreme_itm:.0f}  (close short, naked LEAPS)")
    lines.append(f"    Harvest trigger:      short mark ≤ ${harvest_px*100:.0f}  "
                 f"({pol.harvest_profit_pct:.0%} profit)")
    lines.append(f"    Force close:          short DTE ≤ {pol.force_close_dte}d AND spot ≥ ${p.short_strike:.0f}")
    lines.append(f"    LEAPS roll:           DTE ≤ {pol.leaps_roll_dte}d")
    lines.append("")

    # Active triggers
    lines.append(f"  ACTIVE TRIGGERS (sorted by priority)")
    for check in s["checks"]:
        level_icon = {"alert": "🔴", "warn": "🟡", "ok": "🟢", "info": "🔵"}.get(check["level"], "⚪")
        lines.append(f"    {level_icon} [{check['level'].upper()}] {check['rule']}")
        lines.append(f"       {check['detail']}")
    lines.append("")

    # Next action
    lines.append(f"  >>> NEXT ACTION: [{s['primary_level'].upper()}] {s['primary_action']}")
    lines.append(f"      {s['primary_detail']}")
    lines.append("")

    return "\n".join(lines)


def format_monitor(rows: list[dict], *, quiet_ok: bool = False) -> str:
    lines = []
    for s in rows:
        p = s["pair"]
        if s.get("no_open_short"):
            actionable = True
            if quiet_ok and not actionable:
                continue
            status = "ACTION"
            ticker = s['record'].get('ticker', 'TSLA')
            lines.append(
                f"PMCC {status}: {ticker} LEAPS {int(p.leaps_strike)} x{s['contracts']} "
                f"spot ${s['spot_now']:.2f} | NO OPEN SHORT | P/L ${s['net_pnl']:+,.0f}/long"
            )
            lines.append(f"  {s['primary_detail']}")
            lines.append(
                f"  closed-short realized P/L ${float(s.get('realized_short_total', 0.0)):+,.0f}; "
                f"LEAPS mark ${s['leaps_mark']['price']*100:,.0f} vs debit ${p.leaps_debit:,.0f}"
            )
            clock = s.get("closed_short_clock") or {}
            if clock:
                good = clock["targets"]["good"]
                lines.append(
                    f"  premium clock: ${clock['avg_since_open']:.1f}/d total since open; "
                    f"good portfolio target ${good['portfolio_target_daily']:.0f}/d; "
                    f"wait budget {good['portfolio_wait_days']:.1f}d"
                )
            lines.append("")
            continue

        c = s["carry"]
        actionable = (
            s["primary_level"] in {"alert", "warn"}
            or "HARVEST" in s["primary_action"].upper()
            or c["current_short_profit"] >= c["harvest_profit"]
        )
        if quiet_ok and not actionable:
            continue
        status = "ACTION" if actionable else "OK"
        ticker = s['record'].get('ticker', 'TSLA')
        lines.append(
            f"PMCC {status}: {ticker} {int(p.leaps_strike)}/{int(p.short_strike)} "
            f"spot ${s['spot_now']:.2f} | {s['primary_action']} | P/L ${s['net_pnl']:+,.0f}/ct"
        )
        lines.append(f"  {s['primary_detail']}")
        lines.append(
            f"  short P/L ${c['current_short_profit']:+,.0f}; harvest at ${c['harvest_mark']:,.0f}; "
            f"pace ${c['current_profit_daily']:+.1f}/d; LEAPS decay ~${c['leaps_decay_daily']:.1f}/d"
        )
        if c["current_short_profit"] >= c["harvest_profit"]:
            lines.append(
                f"  HARVEST CLOCK: profit ${c['harvest_profit']:,.0f}; "
                f"good wait budget {c['wait_good_days_after_harvest']:.1f}d, floor wait budget {c['wait_floor_days_after_harvest']:.1f}d"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def format_what_if(record: dict, base_spot: float, *, preset: str = "managed") -> str:
    """Show what happens at different spot levels for this position."""
    if record.get("open_short", True) is False:
        return (
            f"  WHAT-IF SCENARIO TABLE: {record.get('ticker', 'TSLA')} LEAPS ONLY\n"
            f"  No open short is recorded, so diagonal what-if is skipped. Reload a short first to get roll/harvest levels.\n"
        )
    from pmcc.positions import record_to_pair, _call_mark
    from pmcc.playbook import _roll_target
    from pmcc.playthrough import POLICY_BY_PRESET
    from pmcc.daily_playthrough import daily_policy
    from pmcc.tune import load_tuned_policy

    pair = record_to_pair(record, base_spot)
    base = POLICY_BY_PRESET.get(preset, POLICY_BY_PRESET["managed"])
    policy = daily_policy(load_tuned_policy(preset, pair.leaps_strike, pair.short_strike, base))

    spots = [base_spot * m for m in [0.75, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15,
                                      1.20, 1.25, 1.35, 1.50, 1.75, 2.00]]

    lines = []
    lines.append(f"  WHAT-IF SCENARIO TABLE: {record.get('ticker', 'TSLA')} "
                 f"{int(pair.leaps_strike)}/{int(pair.short_strike)}")
    lines.append(f"  (current spot ${base_spot:,.2f}, LEAPS DTE {pair.leaps_dte}, short DTE {pair.short_dte})")
    lines.append("")
    lines.append(f"  {'spot':>6}  {'% chg':>6}  {'LEAPS mark':>10}  {'short mark':>10}  "
                 f"{'net P/L':>9}  {'action':>30}")
    lines.append(f"  {'-' * 80}")

    for sp in spots:
        leaps_m = _call_mark(sp, pair.leaps_strike, pair.leaps_dte, pair.leaps_iv, 0.04)
        short_m = _call_mark(sp, pair.short_strike, pair.short_dte, pair.short_iv, 0.04)
        leaps_pl = leaps_m["price"] * 100 - pair.leaps_debit
        short_pl = pair.short_credit - short_m["price"] * 100
        net = leaps_pl + short_pl
        pct = (sp / base_spot - 1) * 100

        # Determine action
        moneyness = sp / pair.leaps_strike
        if pair.short_dte <= policy.force_close_dte and sp >= pair.short_strike:
            action = "FORCE CLOSE + ROLL"
        elif moneyness >= policy.leaps_extreme_itm_threshold:
            action = "CLOSE SHORT — NAKED LEAPS"
        elif sp >= pair.short_strike * policy.challenged_pct:
            roll_k = _roll_target(sp, pair.short_strike, pair.leaps_strike, policy)
            action = f"ROLL to ${roll_k:.0f}"
        elif short_m["price"] * 100 <= pair.short_credit * (1 - policy.harvest_profit_pct):
            action = "HARVEST (take profit)"
        elif moneyness >= policy.leaps_deep_itm_threshold:
            action = "HOLD (deep ITM)"
        elif sp <= pair.spot_entry * policy.bear_pause_mult:
            action = "NO SHORTS (bear)"
        else:
            action = "HOLD"

        lines.append(f"  ${sp:>5.0f}  {pct:>+5.0f}%  ${leaps_m['price']*100:>9,.0f}  "
                     f"${short_m['price']*100:>9,.0f}  ${net:>+8,.0f}  {action:>30}")

    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="PMCC live position manager")
    ap.add_argument("--spot", type=float, default=None,
                    help="Override current spot price")
    ap.add_argument("--what-if", type=float, default=None,
                    help="Show what-if table centered on this spot")
    ap.add_argument("--triggers", action="store_true",
                    help="Show full trigger playbook for top pair")
    ap.add_argument("--monitor", action="store_true",
                    help="Concise monitor output for cron/alerts")
    ap.add_argument("--quiet-ok", action="store_true",
                    help="With --monitor, print nothing unless action is needed")
    ap.add_argument("--preset", default="managed")
    args = ap.parse_args()

    # Check positions
    positions = load_pmcc_positions()
    if not positions:
        spot = args.spot if args.spot else _get_spot()
        if spot == 0:
            print("Could not fetch TSLA spot price. Use --spot to override.")
            sys.exit(1)
        if not (args.monitor and args.quiet_ok):
            print(f"\n  TSLA spot: ${spot:,.2f}  |  preset: {args.preset}")
            print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
            print()
        print(f"  No positions found in {PMCC_POSITIONS_PATH}")
        print(f"  Create one with: just pmcc-positions example")
        print()
        # Show scan top pair instead
        from pathlib import Path
        cache = Path(".cache/pmcc_pair_scan_TSLA_managed.parquet")
        if cache.exists():
            import pandas as pd
            df = pd.read_parquet(cache)
            top = df.iloc[0]
            print(f"  TOP SCAN PAIR: {top['pair']} (sim score {top['path_sim_score']:.1f})")
            print(f"  LEAPS ${top['leaps_strike']:.0f} {int(top['leaps_dte'])}d, "
                  f"short ${top['short_strike']:.0f} {int(top['short_dte'])}d")
            print(f"  Coverage {top['coverage_pct']:.1f}%, net debit ${top['leaps_debit']-top['short_credit']:,.0f}")
            print()
        if args.triggers:
            print("\n  Use --triggers with a position to see the full playbook.")
        return

    if not (args.monitor and args.quiet_ok):
        if args.spot:
            print(f"\n  spot override: ${args.spot:,.2f} for all positions  |  preset: {args.preset}")
        else:
            tickers = sorted({str(r.get('ticker', 'TSLA')) for r in positions})
            spots = {t: _get_spot(t) for t in tickers}
            spot_line = ", ".join(f"{t} ${v:,.2f}" for t, v in spots.items())
            print(f"\n  Spots: {spot_line}  |  preset: {args.preset}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
        print()

    # Check each position
    results = []
    for record in positions:
        ticker = str(record.get("ticker", "TSLA"))
        spot = args.spot if args.spot else _get_spot(ticker)
        if spot == 0:
            print(f"Could not fetch {ticker} spot price. Use --spot to override.")
            sys.exit(1)
        result = check_pmcc_position(record, spot, preset=args.preset)
        results.append(result)

    if args.monitor:
        msg = format_monitor(results, quiet_ok=args.quiet_ok)
        if msg:
            print(msg)
        return

    # Summary
    print(format_pmcc_portfolio(results))
    print()

    # Detail for each position
    for s in results:
        print(format_position_detail(s))

    # What-if table
    if args.what_if:
        for record in positions:
            print(format_what_if(record, args.what_if, preset=args.preset))

    # Full trigger playbook
    if args.triggers:
        for s in results:
            p = s["pair"]
            pol = s["policy"]
            print(f"\n  {'=' * 78}")
            print(f"  FULL TRIGGER PLAYBOOK: {int(p.leaps_strike)}/{int(p.short_strike)}")
            print(f"  {'=' * 78}\n")
            triggers = generate_triggers(p, pol)
            print(format_playbook(triggers))


if __name__ == "__main__":
    from datetime import datetime
    main()

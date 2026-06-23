#!/usr/bin/env python3
"""Generate optimized PMCC management playbook with daily spot/premium triggers."""

from __future__ import annotations

import argparse
from pathlib import Path

from pmcc.analyze import build_pmcc_grid
from pmcc.chain_data import chain_fetch_meta, format_chain_source
from pmcc.config import PmccConfig, apply_preset
from pmcc.daily_sim import search_rules
from pmcc.tune import load_tuned_policy
from pmcc.paths import CANONICAL_PATHS
from pmcc.playbook import format_playbook, generate_triggers
from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy, format_monthly_log, run_all_paths
from pmcc.scenarios import PmccPair


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC optimized rules + daily playbook")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish"), default="balanced")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--no-optimize", action="store_true")
    ap.add_argument("--out", type=Path, help="write playbook markdown")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--leaps-strike", type=float)
    ap.add_argument("--short-strike", type=float)
    args = ap.parse_args()

    cfg = apply_preset(PmccConfig(ticker=args.ticker), args.preset)
    cfg = PmccConfig(**{
        **cfg.__dict__,
        "chain_use_cache": not args.no_cache,
        "chain_refresh": args.refresh,
    })
    if args.preset == "bullish":
        cfg = PmccConfig(**{**cfg.__dict__, "target_spot": 550.0})

    spot, df = build_pmcc_grid(cfg)
    row = df.iloc[0]
    if args.leaps_strike and args.short_strike:
        m = df[(df.leaps_strike == args.leaps_strike) & (df.short_strike == args.short_strike)]
        if not m.empty:
            row = m.iloc[0]
    pair = PmccPair.from_row(row, spot)
    base_policy = POLICY_BY_PRESET.get(args.preset, PlayPolicy())

    if args.no_optimize:
        policy = load_tuned_policy(args.preset, pair.leaps_strike, pair.short_strike, base_policy)
        opt = {"score": 0, "bull_avg": 0, "whipsaw_avg": 0, "bear_worst": 0}
    else:
        policy, opt = search_rules(pair, base_policy, r=cfg.risk_free_rate)

    print(f"\n=== PMCC playbook — {cfg.ticker} @ ${spot:,.2f} ===")
    print(format_chain_source(chain_fetch_meta()))
    print()
    print("Starting pair:")
    print(f"  LEAPS  ${pair.leaps_strike:.0f}  {pair.leaps_dte}d  debit ${pair.leaps_debit:,.0f}")
    print(f"  Short  ${pair.short_strike:.0f}  {pair.short_dte}d  credit ${pair.short_credit:,.0f}  "
          f"(${pair.short_credit / 100:.2f}/sh)")
    print(f"  Net debit ${pair.net_debit:,.0f}")
    print()

    if not args.no_optimize:
        print("Optimized rules (bull-weighted; bear = loss-cap only):")
        print(f"  harvest short when ≤ ${pair.short_credit / 100 * (1 - policy.harvest_profit_pct):.2f}/sh mark")
        print(f"  ({policy.harvest_profit_pct:.0%} profit on ${pair.short_credit / 100:.2f} credit)")
        print(f"  crash defer {policy.crash_defer_days}d | roll up {policy.roll_up_pct:.0%}")
        print(f"  new short {policy.short_delta_new:.2f}Δ / {policy.short_dte_new}d")
        print(f"  score {opt['score']:,.0f}  bull avg ${opt.get('bull_avg', 0):+,.0f}  "
              f"whipsaw avg ${opt.get('whipsaw_avg', 0):+,.0f}  "
              f"bear worst ${opt.get('bear_worst', 0):+,.0f}")
        print()

    _, summary = run_all_paths(pair, CANONICAL_PATHS, policy, r=cfg.risk_free_rate)
    print("Path results:\n")
    for _, s in summary.iterrows():
        label = next(p.label for p in CANONICAL_PATHS if p.name == s["path"])
        print(f"  {s['path']:<14} ${s['final_pnl']:+,.0f}  {label}")
    print()

    triggers = generate_triggers(pair, policy, r=cfg.risk_free_rate)
    playbook_md = format_playbook(triggers)
    print(playbook_md)

    if args.out:
        args.out.write_text(playbook_md)
        print(f"Wrote playbook → {args.out}")


if __name__ == "__main__":
    main()
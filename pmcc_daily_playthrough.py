#!/usr/bin/env python3
"""Daily PMCC playthrough — 1-day granularity with extreme gap-up paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from pmcc.analyze import build_pmcc_grid, format_table
from pmcc.chain_data import chain_fetch_meta, format_chain_source
from pmcc.config import MANAGEMENT_RULES, PmccConfig, apply_preset
from pmcc.daily_playthrough import (
    EXTREME_DAILY_PATHS,
    WHIPSAW_DAILY_PATHS,
    build_daily_paths,
    compare_pairs_daily,
    daily_policy,
    format_daily_log,
    run_all_daily_paths,
)
from pmcc.daily_sim import search_rules
from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy
from pmcc.scenarios import PmccPair


COMPARE_PAIRS = (
    (420, 430),
    (420, 455),
    (390, 510),
)


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC daily playthrough (1d steps, gap-rip paths)")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish"), default="balanced")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--path", help="single path name (default: all)")
    ap.add_argument("--leaps-strike", type=float)
    ap.add_argument("--short-strike", type=float)
    ap.add_argument("--compare", action="store_true", help="compare 420/430 vs 420/455 vs 390/510")
    ap.add_argument("--no-optimize", action="store_true")
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
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
        policy = daily_policy(base_policy)
    else:
        opt_policy, opt = search_rules(pair, base_policy, r=cfg.risk_free_rate)
        policy = daily_policy(opt_policy)
        print(f"Optimized monthly rules → daily (score {opt['score']:,.0f}, bull avg ${opt['bull_avg']:+,.0f})")

    paths = build_daily_paths(pair.leaps_dte)
    if args.path:
        paths = tuple(p for p in paths if p.name == args.path)
        if not paths:
            from pmcc.daily_playthrough import build_daily_paths as _b
            all_names = [p.name for p in _b(pair.leaps_dte)]
            raise SystemExit(f"unknown path {args.path!r}; choose {all_names}")

    print(f"\n=== PMCC daily playthrough — {cfg.ticker} @ ${spot:,.2f} ===")
    print(f"Preset: {args.preset}  |  {len(paths[0].days)}-day granularity  |  gap rip ≥{policy.gap_rip_trigger_pct:.0%}")
    print(format_chain_source(chain_fetch_meta()))
    print()
    print("Selected pair:")
    print(f"  LEAPS  ${pair.leaps_strike:.0f}  {pair.leaps_dte}d  debit ${pair.leaps_debit:,.0f}")
    print(f"  Short  ${pair.short_strike:.0f}  {pair.short_dte}d  credit ${pair.short_credit:,.0f}")
    print(f"  Net debit ${pair.net_debit:,.0f}  score {pair.score:.3f}")
    print()
    key = "income" if args.preset == "income" else args.preset
    for rule in MANAGEMENT_RULES[key]:
        print(f"  • {rule}")
    print()

    detail, summary = run_all_daily_paths(pair, paths, policy, r=cfg.risk_free_rate)

    print("=== DAILY PATH SUMMARY (final P/L at LEAPS expiry) ===\n")
    for _, s in summary.iterrows():
        label = next((p.label for p in paths if p.name == s["path"]), s["path"])
        flag = ""
        if s["path"] in WHIPSAW_DAILY_PATHS:
            flag = " ⟳"
        elif s["path"] in EXTREME_DAILY_PATHS:
            flag = " ★"
        print(f"  {s['path']:<22}{flag} {label}")
        print(f"    final ${s['final_pnl']:+,.0f}  |  min ${s['min_pnl']:+,.0f}  |  max ${s['max_pnl']:+,.0f}")
    print()

    extreme = (
        "single_day_rip_10", "gap_rip_then_plateau", "double_gap_rip",
        "gap_rip_flush", "gap_whipsaw_double", "tsla_range_chop", "post_earnings_whipsaw",
        "moonshot", "rip_plateau",
    )
    for pname in extreme:
        if pname in summary["path"].values:
            label = next((p.label for p in paths if p.name == pname), pname)
            print(f"--- {pname}: {label} (key days) ---\n")
            print(format_daily_log(detail, pname))
            print()

    if args.compare:
        print("=== PAIR COMPARISON (daily bull-weighted score) ===\n")
        pairs = []
        for leaps_k, short_k in COMPARE_PAIRS:
            m = df[(df.leaps_strike == leaps_k) & (df.short_strike == short_k)]
            if m.empty:
                print(f"  {leaps_k}/{short_k} — not in grid today")
                continue
            pairs.append(PmccPair.from_row(m.iloc[0], spot))
        if pairs:
            cmp_df = compare_pairs_daily(pairs, policy, r=cfg.risk_free_rate)
            print(cmp_df.to_string(index=False, formatters={
                "net_debit": "${:,.0f}".format,
                "score": "{:,.0f}".format,
                "bull_avg": "${:+,.0f}".format,
                "extreme_avg": "${:+,.0f}".format,
                "bear_worst": "${:+,.0f}".format,
            }))
        print()

    print("Ranked pair context (top 3 today):\n")
    print(format_table(df, 3))

    if args.csv:
        detail.to_csv(args.csv, index=False)
        print(f"Wrote {len(detail)} rows → {args.csv}")


if __name__ == "__main__":
    main()
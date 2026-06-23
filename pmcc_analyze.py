#!/usr/bin/env python3
"""PMCC snapshot analyzer — rank LEAPS × short-call pairs from live option chains."""

from __future__ import annotations

import argparse
from pathlib import Path

from pmcc.analyze import format_heatmap, format_table, run_analysis
from pmcc.chain_data import chain_fetch_meta, format_chain_source
from pmcc.config import (
    MANAGEMENT_RULES,
    PmccConfig,
    WIDE_LEAPS_DTE_GRID,
    WIDE_SHORT_DTE_GRID,
    apply_preset,
)


def _parse_floats(s: str) -> tuple[float, ...]:
    return tuple(float(x.strip()) for x in s.split(",") if x.strip())


def _parse_ints(s: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in s.split(",") if x.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC LEAPS diagonal snapshot analyzer (TSLA)")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--top", type=int, default=30, help="rows to print (default 30)")
    ap.add_argument("--csv", type=Path, help="write full ranked grid to CSV")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish", "managed"),
                    help="management preset: grids + scoring + rules")
    ap.add_argument("--score", choices=("premium", "balanced", "bullish", "managed"), default=None)
    ap.add_argument("--leaps-dte", default="365,450,540,630,730")
    ap.add_argument("--short-dte", default="14,21,30,45,60,75,90,120")
    ap.add_argument("--leaps-delta", default="0.60,0.65,0.70,0.75,0.80,0.85")
    ap.add_argument("--short-delta", default="0.10,0.15,0.20,0.25,0.30,0.35,0.40")
    ap.add_argument("--max-spread", type=float, default=0.25)
    ap.add_argument("--no-heatmap", action="store_true")
    ap.add_argument("--wide", action="store_true")

    ap.add_argument("--target-spot", type=float,
                    help="score path to this spot (e.g. 550); bullish preset defaults to 550")
    ap.add_argument("--refresh", action="store_true",
                    help="bypass cache and re-fetch live option chain")
    ap.add_argument("--no-cache", action="store_true", help="do not read or write chain cache")
    ap.add_argument("--cache-ttl", type=int, default=30,
                    help="during market hours only: refresh after N minutes (default 30); "
                         "when closed, last session cache is kept until next open")
    args = ap.parse_args()

    if args.preset:
        cfg = apply_preset(PmccConfig(ticker=args.ticker), args.preset)
    else:
        leaps_dte = WIDE_LEAPS_DTE_GRID if args.wide else _parse_ints(args.leaps_dte)
        short_dte = WIDE_SHORT_DTE_GRID if args.wide else _parse_ints(args.short_dte)
        cfg = PmccConfig(
            ticker=args.ticker,
            leaps_dte_grid=leaps_dte,
            short_dte_grid=short_dte,
            leaps_delta_grid=_parse_floats(args.leaps_delta),
            short_delta_grid=_parse_floats(args.short_delta),
            max_bid_ask_spread_pct=args.max_spread,
            short_dte_max=200 if args.wide else 180,
            score_profile=args.score or "balanced",
        )

    if args.score:
        cfg = PmccConfig(**{**cfg.__dict__, "score_profile": args.score})
    if args.target_spot is not None:
        cfg = PmccConfig(**{**cfg.__dict__, "target_spot": args.target_spot})
    cfg = PmccConfig(**{
        **cfg.__dict__,
        "chain_use_cache": not args.no_cache,
        "chain_refresh": args.refresh,
        "chain_max_age_minutes": args.cache_ttl,
    })

    result = run_analysis(cfg, top=args.top)
    spot = result["spot"]
    summary = result["summary"]
    preset = args.preset or cfg.score_profile

    print(f"\n=== PMCC snapshot — {cfg.ticker} @ ${spot:,.2f} ===")
    if args.preset:
        print(f"Preset: {args.preset}")
    print(f"Score profile: {cfg.score_profile}")
    if cfg.target_spot:
        print(f"Target spot: ${cfg.target_spot:,.0f}")
    print(format_chain_source(chain_fetch_meta()))
    print(f"Grid: {result['n_grid']} target combos → {result['n_pairs']} valid pairs\n")

    rules_key = args.preset or (
        "bullish" if cfg.score_profile == "bullish" else
        "income" if cfg.score_profile == "premium" else "balanced"
    )
    print("Management rules:")
    for rule in MANAGEMENT_RULES.get(rules_key, MANAGEMENT_RULES["balanced"]):
        print(f"  • {rule}")
    print()

    if summary:
        print("Top-slice medians:")
        print(f"  coverage:     {summary['median_coverage_pct']:.2f}% of LEAPS debit")
        print(f"  roll tax:     {summary['median_roll_tax']:.2f}x first-cycle credit")
        print(f"  1st-cycle net:{summary['median_first_cycle_net']:+,.0f} after challenge roll")
        if "median_drop_profit_pct" in summary:
            print(f"  drop profit:  {summary['median_drop_profit_pct']:.0f}% on −10% mid-cycle")
        if cfg.target_spot and "median_rolls_to_target" in summary:
            print(f"  rolls→target: {summary['median_rolls_to_target']:.0f}  "
                  f"path short net ${summary['median_path_short_net']:+,.0f}")
        print()

    if not args.no_heatmap:
        print("DTE ratio heatmap:\n")
        print(format_heatmap(result["heatmap"]))
        print()

    print(f"Top {args.top} ranked pairs:\n")
    print(format_table(result["all"], args.top))

    if args.csv:
        result["all"].to_csv(args.csv, index=False)
        print(f"\nWrote {len(result['all'])} rows → {args.csv}")


if __name__ == "__main__":
    main()
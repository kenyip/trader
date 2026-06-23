#!/usr/bin/env python3
"""PMCC scenario walkthrough — spot rip/drop paths and management actions."""

from __future__ import annotations

import argparse

from pmcc.analyze import build_pmcc_grid, format_table
from pmcc.chain_data import chain_fetch_meta, format_chain_source
from pmcc.config import MANAGEMENT_RULES, PmccConfig, apply_preset
from pmcc.scenarios import (
    PmccPair,
    estimate_roll_credit,
    format_midcycle_table,
    format_scenario_table,
    run_scenarios,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC scenario walkthrough on best (or chosen) pair")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish"))
    ap.add_argument("--target-spot", type=float)
    ap.add_argument("--leaps-strike", type=float)
    ap.add_argument("--short-strike", type=float)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--cache-ttl", type=int, default=30,
                    help="refresh TTL during market hours only (see pmcc-snapshot --help)")
    args = ap.parse_args()

    if args.preset:
        cfg = apply_preset(PmccConfig(ticker=args.ticker), args.preset)
    else:
        cfg = PmccConfig(ticker=args.ticker)
    if args.target_spot is not None:
        cfg = PmccConfig(**{**cfg.__dict__, "target_spot": args.target_spot})
    cfg = PmccConfig(**{
        **cfg.__dict__,
        "chain_use_cache": not args.no_cache,
        "chain_refresh": args.refresh,
        "chain_max_age_minutes": args.cache_ttl,
    })

    spot, df = build_pmcc_grid(cfg)
    best = df.iloc[0]
    pair = PmccPair.from_row(best, spot)

    if args.leaps_strike and args.short_strike:
        match = df[
            (df["leaps_strike"] == args.leaps_strike)
            & (df["short_strike"] == args.short_strike)
        ]
        if not match.empty:
            pair = PmccPair.from_row(match.iloc[0], spot)

    rules_key = args.preset or cfg.score_profile
    if rules_key == "premium":
        rules_key = "income"

    print(f"\n=== PMCC scenarios — {cfg.ticker} @ ${spot:,.2f} ===")
    if args.preset:
        print(f"Preset: {args.preset}")
    print(format_chain_source(chain_fetch_meta()))
    print()

    print("Management rules:")
    for rule in MANAGEMENT_RULES.get(rules_key, MANAGEMENT_RULES["balanced"]):
        print(f"  • {rule}")
    print()

    print("Selected pair:")
    print(f"  LEAPS:  {pair.leaps_exp}  ${pair.leaps_strike:.0f} call  "
          f"({pair.leaps_dte}d)  debit ${pair.leaps_debit:,.0f}")
    print(f"  Short:  {pair.short_exp}  ${pair.short_strike:.0f} call  "
          f"({pair.short_dte}d)  credit ${pair.short_credit:,.0f}")
    print(f"  Net debit: ${pair.net_debit:,.0f}  |  score: {pair.score:.3f}")
    row = df.iloc[0]
    if "roll_tax_ratio" in row:
        print(f"  Roll tax: {row['roll_tax_ratio']:.2f}x  |  "
              f"1st-cycle net after roll: ${row['first_cycle_net_after_roll']:+,.0f}")
    if "drop_profit_ratio" in row:
        print(f"  Drop (−10% mid-cycle) short profit: {row['drop_profit_ratio']:.0%}")
    if cfg.target_spot and "rolls_to_target" in row:
        print(f"  Path to ${cfg.target_spot:.0f}: {int(row['rolls_to_target'])} rolls  "
              f"short-leg net ${row['path_short_net']:+,.0f}  "
              f"clears={bool(row['clears_target'])}")
    print()

    scen = run_scenarios(pair, r=cfg.risk_free_rate)
    print(f"At SHORT EXPIRY (LEAPS {max(pair.leaps_dte - pair.short_dte, 0)}d left):\n")
    print(format_scenario_table(scen))
    print()

    print("Mid-short-cycle (~halfway):\n")
    print(format_midcycle_table(scen))
    print()

    rip_spot = cfg.target_spot or spot * 1.20
    roll = estimate_roll_credit(pair, rip_spot, cfg=cfg)
    if roll:
        print(f"Roll example (spot ${rip_spot:,.0f}):")
        print(f"  Sell ${roll['roll_strike']:.0f}  {roll['roll_exp']}  "
              f"credit ${roll['roll_credit']:,.0f}  Δ≈{roll['roll_delta']:.2f}")
        print()

    print("Top 5 pairs:\n")
    print(format_table(df, 5))


if __name__ == "__main__":
    main()
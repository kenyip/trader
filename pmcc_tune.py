#!/usr/bin/env python3
"""Systematic PMCC management-rule tuner — daily sim grid search."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pmcc.analyze import build_pmcc_grid
from pmcc.chain_data import chain_fetch_meta, format_chain_source
from pmcc.config import PmccConfig, apply_preset
from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy
from pmcc.scenarios import PmccPair
from pmcc.tune import (
    TUNED_POLICY_BY_PRESET,
    compare_path_table,
    format_tune_report,
    policy_knobs,
    tune_policy,
)

CACHE_DIR = Path(".cache")


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC systematic rule tuner (daily sim)")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish"), default="balanced")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--leaps-strike", type=float)
    ap.add_argument("--short-strike", type=float)
    ap.add_argument("--full-grid", action="store_true", help="search on all paths (slower)")
    ap.add_argument("--save", action="store_true", help="write tuned policy to .cache/")
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
    base = POLICY_BY_PRESET.get(args.preset, PlayPolicy())

    print(f"\n=== PMCC tune — {cfg.ticker} @ ${spot:,.2f} ===")
    print(format_chain_source(chain_fetch_meta()))
    print(f"Pair: LEAPS ${pair.leaps_strike:.0f} / short ${pair.short_strike:.0f}  "
          f"net debit ${pair.net_debit:,.0f}")
    print(f"Grid: whipsaw stage ({3**5 * 2} combos) → roll stage ({3**5} combos)")
    print("Searching…\n")

    tuned, tuned_score, baseline_score = tune_policy(pair, base, r=cfg.risk_free_rate, fast=not args.full_grid)
    cmp = compare_path_table(baseline_score, tuned_score)

    print(format_tune_report(pair, base, tuned, tuned_score, baseline_score, cmp))
    print()
    print("Tuned knobs:")
    for k, v in policy_knobs(tuned).items():
        print(f"  {k:28s} {v}")

    TUNED_POLICY_BY_PRESET[args.preset] = tuned

    if args.save:
        CACHE_DIR.mkdir(exist_ok=True)
        out = CACHE_DIR / f"pmcc_tuned_{args.preset}_{int(pair.leaps_strike)}_{int(pair.short_strike)}.json"
        payload = {
            "preset": args.preset,
            "pair": {"leaps": pair.leaps_strike, "short": pair.short_strike},
            "knobs": policy_knobs(tuned),
            "score": tuned_score["score"],
            "whipsaw_avg": tuned_score["whipsaw_avg"],
            "chop_pnl": tuned_score["chop_pnl"],
        }
        out.write_text(json.dumps(payload, indent=2))
        cmp.to_csv(out.with_suffix(".csv"), index=False)
        print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Compare default vs wide PMCC DTE search ranges."""

from __future__ import annotations

import argparse

import pandas as pd

from pmcc.analyze import build_pmcc_grid, dte_heatmap, format_heatmap
from pmcc.chain_data import chain_fetch_meta, fetch_call_chain, format_chain_source
from pmcc.config import PmccConfig, WIDE_LEAPS_DTE_GRID, WIDE_SHORT_DTE_GRID


def _best_cell_label(heat: pd.DataFrame) -> str:
    stacked = heat.stack()
    if stacked.empty:
        return "n/a"
    idx = stacked.idxmax()
    return f"LEAPS {idx[0]}d × short {idx[1]}d (score {stacked.max():.3f})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--cache-ttl", type=int, default=30)
    args = ap.parse_args()

    spot, chain = fetch_call_chain(
        args.ticker,
        use_cache=not args.no_cache,
        refresh=args.refresh,
        max_age_minutes=args.cache_ttl,
    )
    exps = chain.groupby("expiration")["dte"].first().sort_values()
    print(f"\n=== DTE range audit — {args.ticker} @ ${spot:,.2f} ===")
    print(format_chain_source(chain_fetch_meta()))
    print(f"Chain expirations: {len(exps)}  |  DTE {exps.min()}–{exps.max()} days")
    print(f"  ≤30d: {(exps <= 30).sum()}  |  31–180d: {((exps > 30) & (exps <= 180)).sum()}  "
          f"|  181–365d: {((exps > 180) & (exps <= 365)).sum()}  |  >365d: {(exps > 365).sum()}")
    print()

    configs = [
        ("default", PmccConfig(ticker=args.ticker)),
        ("wide", PmccConfig(
            ticker=args.ticker,
            leaps_dte_grid=WIDE_LEAPS_DTE_GRID,
            short_dte_grid=WIDE_SHORT_DTE_GRID,
            short_dte_max=200,
        )),
    ]

    for label, cfg in configs:
        _, df = build_pmcc_grid(cfg, chain=chain)
        top = df.iloc[0]
        heat = dte_heatmap(df)
        print(f"--- {label} grid ({len(df)} pairs) ---")
        print(f"Best: LEAPS {top['leaps_dte_target']}d / short {top['short_dte_target']}d  "
              f"Δ {top['leaps_delta_target']:.2f}/{top['short_delta_target']:.2f}  "
              f"K {top['leaps_strike']:.0f}/{top['short_strike']:.0f}  score {top['score']:.3f}")
        print(f"Best DTE cell: {_best_cell_label(heat)}")
        print()
        print(format_heatmap(heat))
        print()


if __name__ == "__main__":
    main()
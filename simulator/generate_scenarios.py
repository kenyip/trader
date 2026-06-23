#!/usr/bin/env python3
"""
simulator/generate_scenarios.py

One-command way to generate "a bunch of scenarios" for exploration, labeling, or stress testing.

This is the practical tool that moves us toward the north star: being able to
quickly produce large numbers of representative paths across different market
conditions so we can evaluate many entry + management strategies on them.

Usage examples:
    .venv/bin/python simulator/generate_scenarios.py
    .venv/bin/python simulator/generate_scenarios.py --tickers TSLA TSLL --per-regime 80
    .venv/bin/python simulator/generate_scenarios.py --earnings 100 --length 30
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulator.market_generator import MarketGenerator, GeneratorConfig
from simulator.path_utils import assign_global_path_ids


def main():
    parser = argparse.ArgumentParser(description="Generate large batches of representative market scenarios.")
    parser.add_argument("--tickers", nargs="+", default=["TSLA", "TSLL"])
    parser.add_argument("--per-regime", type=int, default=80, help="Base number of paths per regime")
    parser.add_argument("--earnings", type=int, default=80, help="Number of dedicated earnings-event paths")
    parser.add_argument("--high-vol", type=int, default=60, help="Extra high-vol / choppy scenarios")
    parser.add_argument("--focus", type=str, default=None,
                        help="Focus generation on hard cases: high_gamma_marginal, v_recovery, post_earnings_weak, high_vol_chop")
    parser.add_argument("--length", type=int, default=25, help="Length of each generated path in days")
    parser.add_argument("--save", type=str, default=None, help="Optional path to save the combined scenarios as parquet")
    args = parser.parse_args()

    regimes = ["normal_up", "huge_up", "normal_down", "huge_down", "flat"]

    all_scenarios = []

    for ticker in args.tickers:
        print(f"\n{'='*70}")
        print(f"GENERATING SCENARIOS FOR {ticker}")
        print(f"{'='*70}")

        cfg = GeneratorConfig(ticker=ticker, random_seed=42)
        gen = MarketGenerator(cfg)
        gen.calibrate()

        # 1. Regime-specific batches (core diversity)
        for regime in regimes:
            n = args.per_regime
            df = gen.generate_regime_batch(regime, n_paths=n, length_days=args.length)
            df["ticker"] = ticker
            df["scenario_type"] = f"regime_{regime}"
            all_scenarios.append(df)
            print(f"  {regime:15s}: {n} paths of {args.length} days")

        # 2. Dedicated earnings-heavy scenarios (very important for TSLA/TSLL)
        earn_df = gen.generate_earnings_scenarios(n_paths=args.earnings, length_days=args.length)
        earn_df["ticker"] = ticker
        earn_df["scenario_type"] = "earnings_event"
        all_scenarios.append(earn_df)
        print(f"  earnings_event : {args.earnings} paths of {args.length} days (forced earnings reaction)")

        # 3. High-vol / choppy emphasis (helps minority policies win)
        high_vol = gen.generate_daily_dataframe(n_paths=args.high_vol, length_days=args.length)
        high_vol["ticker"] = ticker
        high_vol["scenario_type"] = "high_vol_chop"
        all_scenarios.append(high_vol)
        print(f"  high_vol_chop  : {args.high_vol} paths of {args.length} days (mixed high vol)")

        # 4. Mixed "normal" batch
        mixed = gen.generate_daily_dataframe(n_paths=args.per_regime, length_days=args.length)
        mixed["ticker"] = ticker
        mixed["scenario_type"] = "mixed"
        all_scenarios.append(mixed)
        print(f"  mixed          : {args.per_regime} paths of {args.length} days (unforced)")

        # 5. Targeted focus generation for hard cases (for better model training)
        # Known weak areas: high_gamma_marginal (high gamma + low recent momentum), v_recovery,
        # post_earnings_weak (earnings jump followed by adverse drift), high_vol_chop
        if args.focus:
            n_focus = max(30, args.per_regime // 2)
            if args.focus in ("high_gamma_marginal", "v_recovery", "post_earnings_weak"):
                # Bias toward flat / normal regimes + earnings for these (where gamma risk + marginal move hurts most)
                focus_df = gen.generate_regime_batch("flat", n_paths=n_focus // 2, length_days=args.length)
                focus_df2 = gen.generate_earnings_scenarios(n_paths=n_focus // 2, length_days=args.length)
                focus_df = pd.concat([focus_df, focus_df2], ignore_index=True)
            else:
                focus_df = gen.generate_daily_dataframe(n_paths=n_focus, length_days=args.length)
            focus_df["ticker"] = ticker
            focus_df["scenario_type"] = f"focus_{args.focus}"
            all_scenarios.append(focus_df)
            print(f"  focus_{args.focus}: {len(focus_df)//args.length} paths (targeted for model weakness: {args.focus})")

    combined = assign_global_path_ids(pd.concat(all_scenarios, ignore_index=True))

    print(f"\n{'='*70}")
    print("SCENARIO GENERATION COMPLETE")
    print(f"{'='*70}")
    total_paths = combined["path_id"].nunique() if "path_id" in combined.columns else len(combined) // args.length
    print(f"Total paths generated : {total_paths:,} (unique path_id: {combined['path_id'].nunique()})")
    print(f"Total rows            : {len(combined):,}")
    print(f"Columns               : {list(combined.columns)}")

    summary = (
        combined.groupby(["ticker", "scenario_type"])
        .agg(
            n_paths=("path_id", "nunique"),
            avg_vol=("close", lambda x: x.pct_change().std() * 100),
            p95_gap=("open", lambda x: (x / x.shift(1) - 1).abs().quantile(0.95) * 100),
        )
        .round(2)
    )
    print("\nQuick summary by type:")
    print(summary)

    if args.save:
        out_path = Path(args.save)
        combined.to_parquet(out_path)
        print(f"\nSaved full scenario set to: {out_path}")

    print("\nThese scenarios are now ready for the (rich) labeling engine.")
    print("Recommended: run build_training_set.py with a large --paths value.")


if __name__ == "__main__":
    main()

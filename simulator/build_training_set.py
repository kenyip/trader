#!/usr/bin/env python3
"""
simulator/build_training_set.py

The main "populate the model" script.

This script:
1. Generates a large collection of representative scenarios (using the generator).
2. Runs the Trade Labeler over them to create rich (state, action, outcome) labels.
3. Joins entry-time features + peek greeks (exactly what the live policy model will see).
4. Saves a clean, model-ready training dataset.

This is the practical tool that turns the simulator into training data for the policy model.

Run this whenever you want fresh labeled data for modeling.

Example:
    .venv/bin/python simulator/build_training_set.py --paths 300 --length 22 --output training_set_v1.parquet
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulator.market_generator import MarketGenerator, GeneratorConfig
from simulator.trade_labeler import TradeLabelerV2, EntryAction, ManagementPolicy, DEFAULT_MANAGEMENT_POLICIES, DEFAULT_ENTRY_ACTIONS
from simulator.feature_utils import build_model_features, get_peek_features_for_action, build_management_decision_features, TRAJECTORY_FEATURES
from simulator.path_utils import assign_global_path_ids
from data import build as build_features


def add_entry_features_and_greeks(labeled_df: pd.DataFrame, scenarios_df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich labeled data with consistent features using the shared feature_utils.
    This ensures perfect alignment between training and live inference.
    """
    scenarios = scenarios_df.reset_index(drop=True)
    records = []

    for _, row in labeled_df.iterrows():
        path_id = int(row["path_id"])
        ticker = row["ticker"]
        entry_idx = int(row["entry_index"])

        path = scenarios[(scenarios["path_id"] == path_id) & (scenarios["ticker"] == ticker)]
        if len(path) <= entry_idx + 1:
            continue

        decision_row = path.iloc[entry_idx].copy()

        # Reconstruct the EntryAction and ManagementPolicy from the labeled row
        action = EntryAction(
            side=row["side"],
            dte=int(row["dte"]),
            target_delta=float(row["target_delta"]),
            min_credit_pct=0.010  # default, not critical for feature building
        )

        policy = ManagementPolicy(
            name=row["management_policy"],
            profit_target=float(row["profit_target"]),
            max_loss_mult=float(row["max_loss_mult"]),
            daily_capture_mult=float(row["daily_capture_mult"])
        )

        # Use the shared utility — this is the key alignment fix
        feat_df = build_model_features(decision_row, action, policy)

        rec = dict(row)

        # Clean up any existing mgmt_* columns from previous enrichment attempts
        keys_to_remove = [k for k in list(rec.keys()) if k.startswith("mgmt_")]
        for k in keys_to_remove:
            rec.pop(k, None)

        # Also drop the raw management_policy column since we're using one-hots
        rec.pop("management_policy", None)

        # Add the fresh aligned features from the utility (this should be the only source of mgmt_* columns)
        for col in feat_df.columns:
            rec[col] = feat_df.iloc[0][col]

        # Phase A/B: also ensure trajectory/decision-state features are present via the single source of truth
        # builder (applies deterministic regime encoding + NaN/inf robustness). Raw values from labeler
        # are overridden with the exact transforms used at live inference time. This prevents the
        # duplication/drift issues that have bitten past extensions.
        has_traj = any(k in row for k in TRAJECTORY_FEATURES)
        if has_traj:
            traj_kwargs = {}
            for k in TRAJECTORY_FEATURES:
                v = row.get(k, 0 if k != "is_gap_day" else False)
                traj_kwargs[k] = v
            mgmt_df = build_management_decision_features(decision_row, action, policy, **traj_kwargs)
            for k in TRAJECTORY_FEATURES:
                if k in mgmt_df.columns:
                    rec[k] = mgmt_df.iloc[0][k]

        rec["entry_spot"] = float(decision_row["close"])
        records.append(rec)

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", type=int, default=250, help="Total paths to generate across all types")
    parser.add_argument("--length", type=int, default=22)
    parser.add_argument("--output", type=str, default=None, help="Output parquet path")
    parser.add_argument("--scenarios", type=str, default=None, help="Pre-generated scenarios parquet (from generate_scenarios.py --save); skips internal generation")
    parser.add_argument("--label", action="store_true", help="Force labeling step (always performed for --scenarios path)")
    parser.add_argument("--low-regret-filter", type=float, default=None, metavar="N", help="Low-regret filter: keep rows where regret_vs_oracle <= N OR oracle_best_pnl > 0 (densifies weak states)")
    parser.add_argument("--midtrade", action="store_true", help="Emit per-bar trajectory rows for standard policy (Phase 4 management densification)")
    parser.add_argument("--join-real", action="store_true", help="After save, union real backtest trades via join_real_trades.py")
    parser.add_argument("--join-period", type=str, default="10y", help="Feature history for real trade join")
    args = parser.parse_args()

    print("=" * 70)
    print("BUILDING TRAINING SET FOR POLICY MODEL")
    print("=" * 70)

    # 1. Scenarios: either pre-generated (--scenarios for focused/low-regret recipe) or internal gen
    if args.scenarios:
        print(f"\n[1/4] Loading pre-generated scenarios from {args.scenarios}...")
        scenarios = assign_global_path_ids(pd.read_parquet(args.scenarios))
        n_paths = scenarios["path_id"].nunique() if "path_id" in scenarios.columns else "n/a"
        print(f"      Loaded {len(scenarios)} rows ({n_paths} unique paths after global path_id remap)")
    else:
        print("\n[1/4] Generating scenarios...")
        all_paths = []
        for ticker in ["TSLA", "TSLL"]:
            cfg = GeneratorConfig(ticker=ticker, random_seed=42)
            gen = MarketGenerator(cfg)
            gen.calibrate()

            # Regime batches
            for regime in ["normal_up", "huge_up", "normal_down", "huge_down"]:
                df = gen.generate_regime_batch(regime, n_paths=args.paths // 8, length_days=args.length)
                df["ticker"] = ticker
                df["scenario_type"] = f"regime_{regime}"
                all_paths.append(df)

            # Earnings heavy
            earn = gen.generate_earnings_scenarios(n_paths=args.paths // 10, length_days=args.length)
            earn["ticker"] = ticker
            earn["scenario_type"] = "earnings_event"
            all_paths.append(earn)

        scenarios = assign_global_path_ids(pd.concat(all_paths, ignore_index=True))
        print(f"      Generated {scenarios['path_id'].nunique()} paths ({len(scenarios)} rows)")

    # 2. Label them with the upgraded rich labeler (multiple management policies)
    print("\n[2/4] Labeling trades with multiple management policies...")
    labeler = TradeLabelerV2()

    labeled = labeler.label_scenarios(
        scenarios,
        entry_actions=DEFAULT_ENTRY_ACTIONS,
        management_policies=DEFAULT_MANAGEMENT_POLICIES,
        use_sampling=True,
        n_sampled_policies=18,  # richer sampling for better oracle coverage + regret labels
        compute_oracle_regret=True,
        emit_midtrade=args.midtrade,
    )
    print(f"      Created {len(labeled)} rich labeled examples (entry × management policy, with sampling + oracle regret)")
    if "regret_vs_oracle" in labeled.columns:
        avg_regret = labeled["regret_vs_oracle"].mean()
        median_regret = labeled["regret_vs_oracle"].median()
        pct_zero_regret = (labeled["regret_vs_oracle"] == 0).mean() * 100
        print(f"      Regret vs Oracle — mean: ${avg_regret:,.1f} | median: ${median_regret:,.1f} | zero-regret (oracle achieved): {pct_zero_regret:.1f}%")

    # 2.5 PR 2: low-regret filter (keeps only high-quality labels where some policy actually wins)
    if args.low_regret_filter is not None:
        N = float(args.low_regret_filter)
        before = len(labeled)
        if "regret_vs_oracle" in labeled.columns:
            mask = (labeled["regret_vs_oracle"] <= N) | (labeled.get("oracle_best_pnl", pd.Series([0.0] * before)) > 0)
            labeled = labeled[mask].copy()
            kept = len(labeled)
            print(f"      [low-regret-filter {N}] kept {kept}/{before} ({100.0 * kept / before:.1f}%) — rows with regret<={N} or oracle>0")
        else:
            print("      [low-regret-filter] skipped (no regret_vs_oracle column)")

    # 3. Enrich with features + greeks at decision time
    print("\n[3/4] Joining features and peek greeks at every decision point...")
    training_df = add_entry_features_and_greeks(labeled, scenarios)
    print(f"      Final training set shape: {training_df.shape}")

    # 4. Save
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = Path(f".cache/training_set_{timestamp}.parquet")
    else:
        out_path = Path(args.output)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    training_df.to_parquet(out_path, index=False)

    if args.join_real:
        from simulator.join_real_trades import merge_training_sets
        merged_path = out_path.with_name(out_path.stem + "_merged.parquet")
        merge_training_sets(out_path, merged_path, period=args.join_period)
        out_path = merged_path

    print(f"\n[4/4] Saved training set to: {out_path}")
    print("\nColumns available for modeling:")
    print(list(training_df.columns))

    print("\n" + "=" * 70)
    print("TRAINING SET READY FOR POLICY MODEL (incl. Phase A/B management-decision 33-col vectors via SoT)")
    print("=" * 70)
    print("Next steps:")
    print("  - Train LightGBM / CatBoost on this data (entry best-policy or management advisor on traj features)")
    print("  - For focused weak-regime + low-regret (per playbook): use generate_scenarios --focus + --low-regret-filter")
    print("  - Evaluate feature importance (traj features now first-class for close/roll re-scoring)")
    print("  - Extract candidate rules or use model directly in strategies.py / positions.py")
    print("  - Validate any new policy through the real historical gauntlet (validate_model_policy.py parity)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
simulator/train_policy_model.py

First end-to-end policy model training on data produced by the simulator + labeler.

This demonstrates the full "generate scenarios → label → train model" loop that leads to new rules.

For now it trains a simple LightGBM regressor to predict realized P/L per contract.
Later versions can do multi-task (P/L + probability of needing roll + best DTE bin, etc.).

The output of this (feature importance + top splits) is exactly what becomes new adaptive rules
or a direct model-based entry function in strategies.py.
"""

import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import lightgbm as lgb
except ImportError:
    print("LightGBM not installed. Install with: pip install lightgbm")
    sys.exit(1)


def main():
    # Find the most recent training set
    cache_dir = Path(".cache")
    training_files = sorted(cache_dir.glob("training_set_*.parquet"))
    if not training_files:
        print("No training set found. Run build_training_set.py first.")
        return

    latest = training_files[-1]
    print(f"Loading training set: {latest}")
    df = pd.read_parquet(latest)

    print(f"Training examples: {len(df)}")

    # Expanded feature set from the rich labeler (includes management policy params)
    feature_cols = [
        "ret_1d", "ret_5d", "ret_14d",
        "iv_proxy", "iv_rank", "ema_stack", "volume_surge",
        "peek_theta_yield", "peek_gamma_dollar", "peek_credit",
        "target_delta", "dte",
        "profit_target", "max_loss_mult", "daily_capture_mult"
    ]

    # Filter to rows that have all features
    # Handle the new 'management_policy' categorical column
    if "management_policy" in df.columns:
        df = pd.get_dummies(df, columns=["management_policy"], prefix="mgmt")
        # Update feature_cols with the new dummy columns
        mgmt_cols = [c for c in df.columns if c.startswith("mgmt_")]
        feature_cols = [f for f in feature_cols if f != "management_policy"] + mgmt_cols

    df = df.dropna(subset=feature_cols + ["pnl_per_contract"])
    print(f"Usable rows after dropping NaNs: {len(df)}")

    X = df[feature_cols]
    y = df["pnl_per_contract"]

    print("\nTraining LightGBM regressor to predict P/L per contract...")

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=200,
        learning_rate=0.05,
        max_depth=5,
        num_leaves=31,
        random_state=42,
        verbose=-1
    )
    model.fit(X, y)

    # Feature importance
    importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    print("\n=== Feature Importance (what the model thinks matters most) ===")
    print(importance.to_string(index=False))

    # Simple prediction on a few rows
    preds = model.predict(X.head(8))
    print("\n=== Sample Predictions vs Actual ===")
    for i in range(8):
        print(f"  Actual: ${y.iloc[i]:7.1f}   Predicted: ${preds[i]:7.1f}")

    # Save the model
    model_dir = Path(".cache/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"policy_model_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    model.booster_.save_model(str(model_path))
    print(f"\nModel saved to: {model_path}")

    print("\n" + "="*70)
    print("FIRST POLICY MODEL TRAINED ON SIMULATOR DATA")
    print("="*70)
    print("Next actions:")
    print("  1. Analyze the top features and turn them into candidate adaptive rules")
    print("  2. Use the model to score new (state, action) pairs at live decision time")
    print("  3. Validate any rule or model-derived policy on real historical data only")


if __name__ == "__main__":
    main()

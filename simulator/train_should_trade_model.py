#!/usr/bin/env python3
"""
simulator/train_should_trade_model.py

Trains a simple binary classifier: "Should I consider trading at all in this state?"

This is a separate "gate" model that can be used before the Best Policy model.

Target: 1 if the best management policy on that path had positive P/L, 0 otherwise.

This helps the overall system be less conservative or too eager.
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

def main():
    import argparse
    from simulator.train_best_policy_model import _resolve_training_path

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=None, help="Training parquet (default: latest training_set_*.parquet)")
    args = parser.parse_args()

    latest = _resolve_training_path(args.input)
    print(f"Loading: {latest}")
    df = pd.read_parquet(latest)

    # Create target: was the best policy profitable?
    df = df[df["best_policy_for_path"].notna() & (df["best_policy_for_path"] != "")]
    df["should_trade"] = (df["pnl_per_contract"] > 0).astype(int)

    print(f"Should trade distribution:\n{df['should_trade'].value_counts()}")

    feature_cols = [
        "ret_1d", "ret_5d", "ret_14d",
        "iv_proxy", "iv_rank", "ema_stack", "volume_surge",
        "peek_theta_yield", "peek_gamma_dollar", "peek_credit",
        "target_delta", "dte"
    ]

    # Add management one-hots if present
    mgmt_cols = [c for c in df.columns if c.startswith("mgmt_")]
    feature_cols += mgmt_cols

    df = df.dropna(subset=feature_cols + ["should_trade"])
    print(f"Usable rows: {len(df)}")

    X = df[feature_cols]
    y = df["should_trade"]

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("\nTraining 'Should Trade' classifier...")

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=200,
        learning_rate=0.05,
        max_depth=5,
        random_state=42,
        verbose=-1,
        class_weight="balanced"
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_val)
    proba = model.predict_proba(X_val)[:, 1]

    print("\n=== Classification Report ===")
    print(classification_report(y_val, preds))
    print(f"AUC: {roc_auc_score(y_val, proba):.3f}")

    importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    print("\n=== Feature Importance for 'Should Trade' ===")
    print(importance.head(10).to_string(index=False))

    # Save
    model_dir = Path(".cache/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / f"should_trade_model_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    model.booster_.save_model(str(path))
    print(f"\nModel saved to {path}")

if __name__ == "__main__":
    main()

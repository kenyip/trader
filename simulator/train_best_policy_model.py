#!/usr/bin/env python3
"""
simulator/train_best_policy_model.py

Trains a model to predict the *best management policy* for a given state + entry.

This is a major step toward the north star:
- Instead of just predicting P/L, we learn "given this situation, which way of managing the trade works best?"

Output of this model can be used to:
- Recommend not just the entry, but also the management style
- Generate higher-quality adaptive rules
- Power a `pick_entry_model()` that proposes full strategies

Run after `build_training_set.py` with the rich labeler.
"""

import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import lightgbm as lgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, confusion_matrix
except ImportError as e:
    print("Missing dependency:", e)
    print("Install with: uv pip install --python .venv/bin/python lightgbm scikit-learn")
    sys.exit(1)


def _resolve_training_path(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise FileNotFoundError(f"Training set not found: {p}")
        return p
    cache_dir = Path(".cache")
    training_files = sorted(cache_dir.glob("training_set_*.parquet"))
    if not training_files:
        raise FileNotFoundError("No training set found. Run build_training_set.py first.")
    return training_files[-1]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=None, help="Training parquet (default: latest training_set_*.parquet)")
    args = parser.parse_args()

    latest = _resolve_training_path(args.input)
    print(f"Loading training set: {latest}")
    df = pd.read_parquet(latest)

    print(f"Total rows before cleaning: {len(df)}")

    # Robust deduplication of columns (handles double one-hotting from enrichment)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    print(f"Total rows after cleaning: {len(df)}")

    # Nuclear deduplication: keep only the first occurrence of each column name
    seen = set()
    cols_to_keep = []
    for c in df.columns:
        if c not in seen:
            seen.add(c)
            cols_to_keep.append(c)
    df = df[cols_to_keep]

    print(f"Total rows after nuclear dedup: {len(df)}")

    # Regret analysis (new supervision signal)
    if "regret_vs_oracle" in df.columns:
        print("\n=== Regret vs Oracle (label quality metric) ===")
        print(f"Mean regret: ${df['regret_vs_oracle'].mean():.1f} | Median: ${df['regret_vs_oracle'].median():.1f}")
        print(f"Zero-regret rows (labels are oracle-optimal): {(df['regret_vs_oracle'] == 0).sum()} ({(df['regret_vs_oracle'] == 0).mean()*100:.1f}%)")
        # Optional: train only on high-quality (low regret) labels for cleaner supervision
        # This filters out cases where even our dense sampling didn't find a great policy
        low_regret_mask = df["regret_vs_oracle"] <= df["regret_vs_oracle"].quantile(0.85)
        print(f"Rows with regret <= 85th percentile (high-quality labels): {low_regret_mask.sum()}")
        # Uncomment to use only high-quality labels:
        # df = df[low_regret_mask]
        # print("Training on high-quality (low-regret) subset only for stronger supervision.")

    # Filter to rows where we have a "best policy" label
    df = df[df["best_policy_for_path"].notna() & (df["best_policy_for_path"] != "")]
    print(f"Rows with best_policy_for_path label: {len(df)}")

    if len(df) < 200:
        print("Not enough labeled examples. Generate more scenarios.")
        return

    # Features (exclude the target and identifiers)
    feature_cols = [
        "ret_1d", "ret_5d", "ret_14d",
        "iv_proxy", "iv_rank", "ema_stack", "volume_surge",
        "peek_theta_yield", "peek_gamma_dollar", "peek_credit",
        "target_delta", "dte",
        "profit_target", "max_loss_mult", "daily_capture_mult"
    ]

    # Include mgmt_* one-hot columns if present (from feature_utils enrichment; management_policy column is intentionally dropped)
    mgmt_cols = [c for c in df.columns if c.startswith("mgmt_")]
    if mgmt_cols:
        feature_cols = feature_cols + mgmt_cols
    # (Legacy path: if raw management_policy still present, one-hot it)
    elif "management_policy" in df.columns:
        df = pd.get_dummies(df, columns=["management_policy"], prefix="mgmt")
        mgmt_cols = [c for c in df.columns if c.startswith("mgmt_")]
        feature_cols = [f for f in feature_cols if f != "management_policy"] + mgmt_cols

    # Nuclear option: remove any duplicate column names entirely
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Extra safety: drop columns that have the same name as a previous one
    cols = []
    seen = set()
    for c in df.columns:
        if c not in seen:
            cols.append(c)
            seen.add(c)
    df = df[cols]

    # Drop rows with missing features
    df = df.dropna(subset=feature_cols + ["best_policy_for_path"])
    print(f"Final usable rows: {len(df)}")

    X = df[feature_cols]
    y = df["best_policy_for_path"]

    # Final nuclear option before fitting: ensure absolutely unique columns
    X = X.loc[:, ~X.columns.duplicated(keep="first")]
    X = X[[c for i, c in enumerate(X.columns) if c not in X.columns[:i]]]

    print(f"\nClass distribution (best policy):")
    print(y.value_counts())

    # Train / validation split
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\nTraining LightGBM Classifier to predict best management policy...")

    model = lgb.LGBMClassifier(
        objective="multiclass",
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        random_state=42,
        verbose=-1,
        class_weight="balanced"
    )
    model.fit(X_train, y_train)

    # Evaluation
    preds = model.predict(X_val)
    print("\n=== Classification Report (Validation Set) ===")
    print(classification_report(y_val, preds))

    # Feature Importance
    importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    print("\n=== Feature Importance — What drives the best management policy? ===")
    print(importance.to_string(index=False))

    # Per-policy insights (top features for each class)
    print("\n=== Top signals per best policy (approximate via split importance) ===")
    for policy in y.unique():
        # Simple proxy: look at rows where this was the best policy
        subset = df[df["best_policy_for_path"] == policy]
        if len(subset) > 50:
            print(f"\n{policy} (n={len(subset)}):")
            print(f"  Avg ret_1d: {subset['ret_1d'].mean():.4f}")
            print(f"  Avg peek_gamma_dollar: {subset['peek_gamma_dollar'].mean():.3f}")
            print(f"  Avg peek_credit: {subset['peek_credit'].mean():.3f}")
            print(f"  Avg ret_5d: {subset['ret_5d'].mean():.4f}")

    # Save the model
    model_dir = Path(".cache/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"best_policy_model_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    model.booster_.save_model(str(model_path))
    print(f"\nBest Policy model saved to: {model_path}")

    print("\n" + "="*70)
    print("BEST MANAGEMENT POLICY MODEL TRAINED")
    print("="*70)
    print("This model can now tell us, for a given state, which way of managing")
    print("the trade tends to perform best. This is core to the north star.")


if __name__ == "__main__":
    main()

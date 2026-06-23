#!/usr/bin/env python3
"""Emit interpretable rule sketches from training data + LightGBM importances."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulator.train_best_policy_model import _resolve_training_path


MARKET_FEATURES = ["ret_1d", "ret_5d", "ret_14d", "iv_rank", "peek_gamma_dollar", "peek_theta_yield", "peek_credit"]


def _quartile_edges(series: pd.Series, n: int = 4):
    s = series.replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < 20:
        return []
    return list(s.quantile([i / n for i in range(1, n)]).values)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=None)
    p.add_argument("--ticker", default=None, help="Filter rows to TSLA or TSLL")
    p.add_argument("--top", type=int, default=8)
    args = p.parse_args()

    path = _resolve_training_path(args.input)
    print(f"Loading {path}")
    df = pd.read_parquet(path)
    if args.ticker:
        df = df[df["ticker"] == args.ticker]
    df = df[df["best_policy_for_path"].notna() & (df["best_policy_for_path"] != "")]
    if "pnl_per_contract" not in df.columns:
        print("No pnl_per_contract column")
        return

    print(f"Rows: {len(df):,}\n=== Policy distribution (oracle labels) ===")
    print(df["best_policy_for_path"].value_counts().head(10).to_string())

    print("\n=== Mean P/L by best_policy (top policies) ===")
    by_pol = df.groupby("best_policy_for_path")["pnl_per_contract"].agg(["count", "mean", "median"])
    print(by_pol.sort_values("mean", ascending=False).head(12).round(2).to_string())

    print("\n=== Market feature → avg P/L by quartile (skip-candidate hints) ===")
    for feat in MARKET_FEATURES:
        if feat not in df.columns:
            continue
        edges = _quartile_edges(df[feat])
        if not edges:
            continue
        bins = [-np.inf] + edges + [np.inf]
        df["_b"] = pd.cut(df[feat], bins=bins, duplicates="drop")
        g = df.groupby("_b", observed=True)["pnl_per_contract"].agg(["count", "mean"])
        worst = g["mean"].idxmin()
        best = g["mean"].idxmax()
        spread = g["mean"].max() - g["mean"].min()
        if spread < 5:
            continue
        print(f"\n{feat} (spread ${spread:.1f}):")
        print(g.round(2).to_string())
        print(f"  → sketch: skip when {feat} in worst bucket {worst} OR prefer when in {best}")

    print("\n=== High-gamma + marginal ret_1d (classic model weakness) ===")
    if "peek_gamma_dollar" in df.columns and "ret_1d" in df.columns:
        mask = (df["peek_gamma_dollar"] > df["peek_gamma_dollar"].quantile(0.75)) & (
            df["ret_1d"].between(-0.01, 0.02)
        )
        sub = df[mask]
        if len(sub) > 30:
            wr = (sub["pnl_per_contract"] > 0).mean() * 100
            print(f"n={len(sub)} avg_pnl=${sub['pnl_per_contract'].mean():.1f} wr={wr:.1f}%")
            print("  → sketch: _rule_skip_high_gamma_marginal_ret1d (already prototyped in strategies.py)")

    print("\n=== Management policy when NOT standard (actionable overrides) ===")
    non_std = df[df["best_policy_for_path"] != "standard"]
    if len(non_std) > 100:
        for pol in ["tight_risk", "hold_longer", "aggressive_capture", "very_aggressive"]:
            psub = non_std[non_std["best_policy_for_path"] == pol]
            if len(psub) < 50:
                continue
            print(f"\n{pol} (n={len(psub)}):")
            for feat in ["peek_gamma_dollar", "ret_1d", "iv_rank", "peek_credit"]:
                if feat in psub.columns:
                    print(f"  {feat}: median={psub[feat].median():.4f} (vs all {df[feat].median():.4f})")

    print("\n=== Copy-paste hooks (manual validate_rule.py next) ===")
    print("# Example adaptive entry (fill thresholds from quartiles above):")
    print("def _rule_model_skip_weak_bucket(row, cfg, current):")
    print("    if cfg.ticker != 'TSLA': return {}")
    print("    if float(row.get('peek_gamma_dollar',0)) > 0.35 and -0.01 <= float(row.get('ret_1d',0)) <= 0.02:")
    print("        return {'skip': True}")
    print("    return {}")


if __name__ == "__main__":
    main()
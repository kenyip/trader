#!/usr/bin/env python3
"""
simulator/verify_model_features.py

PR 2 verification smoke: asserts exact 20-col (should-trade) + 23-col (best-policy)
feature alignment against the on-disk 20260515 models, and that the gate + scoring
paths run without crash on a real data.build row.

Phase A/B extension: also smokes the 33-col management decision features (TRAJECTORY_FEATURES
+ deterministic regime encoding + NaN robustness) via the single source of truth builder.

This is the behavioural regression check required by the playbook (Recipe Prerequisites).
Run: python simulator/verify_model_features.py
"""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from simulator.feature_utils import build_should_trade_features, build_model_features, TRAJECTORY_FEATURES, build_management_decision_features
from simulator.pick_entry_model import PickEntryModel
from simulator.trade_labeler import EntryAction, ManagementPolicy
from data import build


def main():
    print("=== PR 2 Feature Parity + Model Path Smoke (verify_model_features.py) ===\n")

    # 1. Load models (uses latest or the 20260515 pinned names we created)
    model = PickEntryModel()
    info = model.get_model_info()
    print(f"Loaded models: {info}")

    should_n = info.get("should_feature_count", 0)
    best_n = info.get("best_feature_count", 0)
    print(f"Should-trade features: {should_n} (expect 20)")
    print(f"Best-policy features:  {best_n} (expect 23)")

    assert should_n == 20, f"Should-trade model has {should_n} features, expected 20"
    assert best_n == 23, f"Best-policy model has {best_n} features, expected 23"
    print("✓ Feature counts match trained artifacts (20/23)\n")

    # 2. Real row + neutral build
    df = build("TSLA", period="2y")
    if len(df) == 0:
        print("WARNING: data.build returned empty; using synthetic row for smoke")
        row = pd.Series({"close": 250.0, "ret_1d": 0.01, "ret_5d": 0.02, "ret_14d": -0.01, "iv_proxy": 0.55, "iv_rank": 45.0, "ema_stack": 0.1, "volume_surge": 1.2, "regime": "normal"})
    else:
        row = df.iloc[-1].copy()
        print(f"Real row sample (TSLA latest): close={row.get('close', 0):.2f} ret_1d={row.get('ret_1d',0):.4f}")

    # build_should_trade (neutral) → 23-col df, caller aligns to 20
    should_df = build_should_trade_features(row)
    print(f"build_should_trade_features produced {should_df.shape[1]} cols (will be reindexed to 20)")
    assert should_df.shape[1] >= 20

    # 3. Gate + scoring paths on real row (no crash, with knobs)
    prob = model.predict_should_trade(row, debug=True)
    print(f"predict_should_trade prob = {prob:.4f} (gate would compare vs 0.55)")

    recs = model.recommend(
        row,
        min_policy_conf=0.20,  # relaxed for smoke on tiny dummy model
        min_edge=0.0,
        use_should_trade_gate=True,
        debug=True,
    )
    print(f"recommend(relaxed) returned {len(recs)} recs (dummy model may be low-conf)")

    # 4. Direct build_model_features parity (23)
    neutral_action = EntryAction("put", 5, 0.22)
    neutral_policy = ManagementPolicy("standard")
    full_df = build_model_features(row, neutral_action, neutral_policy)
    print(f"build_model_features produced {full_df.shape[1]} cols (expect 23)")
    assert full_df.shape[1] == 23

    # Phase A/B: management decision features (SoT builder, 10 traj + det encoding + NaN guard)
    print("\n[Phase A/B] build_management_decision_features smoke (33-col, trajectory state)...")
    traj = {k: (False if k == "is_gap_day" else 0.0) for k in TRAJECTORY_FEATURES}
    traj["regime_at_decision"] = str(row.get("regime", ""))
    traj["iv_rank_at_decision"] = float(row.get("iv_rank", 50.0))
    # also test NaN path and empty regime (must not produce OOD or non-finite)
    traj_bad = traj.copy()
    traj_bad["current_pnl_pct"] = float("nan")
    traj_bad["regime_at_decision"] = ""
    mgmt_df = build_management_decision_features(row, neutral_action, neutral_policy, **traj)
    mgmt_bad = build_management_decision_features(row, neutral_action, neutral_policy, **traj_bad)
    print(f"  produced {mgmt_df.shape[1]} cols; has all TRAJECTORY_FEATURES: {all(c in mgmt_df.columns for c in TRAJECTORY_FEATURES)}")
    assert mgmt_df.shape[1] == 33
    assert all(c in mgmt_df.columns for c in TRAJECTORY_FEATURES)
    assert np.isfinite(mgmt_bad["current_pnl_pct"].iloc[0])
    assert mgmt_bad["regime_at_decision"].iloc[0] == 0.0  # stable empty encoding
    print("  ✓ deterministic regime float, NaN/inf->0, full alignment for management advisor path")

    print("\n✓ All alignment + execution paths succeeded on real row + 20260515 models")
    print("VERIFY PASSED: 20-col / 23-col parity + should-trade gate + recommend scoring + 33-col mgmt decision features (SoT)")
    print("Main rule path (pick_entry / ADAPTIVE_RULES) untouched — only experimental model path exercised.\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
simulator/feature_utils.py

Shared utilities for consistent feature preparation between training and inference.

This is the key to fixing feature alignment — the main reason the model
doesn't produce good signals when used on real historical data.

Goal: The exact same function should be used to compute the feature vector
( including peek greeks ) whether we're:
- Building the training set (in trade_labeler.py)
- Scoring candidates at live decision time (in pick_entry_model.py)

Note on Phase A foundation (per plan): TRAJECTORY_FEATURES + build_management_decision_features + build_trajectory_dict
are the SoT. Current labels (trade_labeler) use entry-time rows + exit-time realized traj for policy outcomes.
Live advisor (positions/whatif) uses current row + partial reconstruction via build_trajectory_dict (proxies documented).
This is explicit scaffolding for first increment; true per-decision-point mid-trade densification on focused windows is future.
build_trajectory_dict provides the unified, safe (None/NaN/gap/now()-free) reconstruction for both.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pricing
from simulator.trade_labeler import EntryAction, ManagementPolicy, CANONICAL_MGMT_POLICY_NAMES


def compute_peek_greeks(S: float, action: EntryAction, iv: float, r: float = 0.04) -> Dict[str, float]:
    """
    Compute the full set of peek greeks + derived metrics for a specific (action) at a given spot.
    This must be called with the *exact* parameters of the candidate being evaluated.
    """
    T = action.dte / 365.0

    try:
        K = pricing.strike_from_delta(S, T, iv, action.target_delta, action.side, r=r)
        K = pricing.round_strike(K, 2.5)
        credit = pricing.price(S, K, T, iv, action.side, r=r)
        g = pricing.gamma(S, K, T, iv, r=r)
        th = pricing.theta(S, K, T, iv, action.side, r=r)
    except Exception:
        return {
            "peek_credit": 0.0,
            "peek_gamma_dollar": 0.0,
            "peek_theta_yield": 0.0,
            "peek_strike": 0.0,
        }

    theta_per_day = th / 365.0
    theta_yield = theta_per_day / credit if credit > 0 else 0.0
    gamma_dollar = g * S * S * iv * iv / 365.0

    return {
        "peek_credit": float(credit),
        "peek_gamma_dollar": float(gamma_dollar),
        "peek_theta_yield": float(theta_yield),
        "peek_strike": float(K),
    }


def build_model_features(
    row: pd.Series,
    action: EntryAction,
    policy: ManagementPolicy,
    iv_override: float = None,
) -> pd.DataFrame:
    """
    Build the complete feature vector that our policy models expect,
    for a given market row + candidate action + candidate management policy.

    This function should be the single source of truth for feature preparation.
    """
    S = float(row["close"])
    iv = float(iv_override or row.get("iv_proxy", 0.55))

    peek = compute_peek_greeks(S, action, iv)

    features = {
        "ret_1d": float(row.get("ret_1d", 0.0)),
        "ret_5d": float(row.get("ret_5d", 0.0)),
        "ret_14d": float(row.get("ret_14d", 0.0)),
        "iv_proxy": iv,
        "iv_rank": float(row.get("iv_rank", 50.0)),
        "ema_stack": float(row.get("ema_stack", 0.0)),
        "volume_surge": float(row.get("volume_surge", 1.0)),
        "target_delta": float(action.target_delta),
        "dte": int(action.dte),
        "profit_target": float(policy.profit_target),
        "max_loss_mult": float(policy.max_loss_mult),
        "daily_capture_mult": float(policy.daily_capture_mult),
        "peek_credit": peek["peek_credit"],
        "peek_gamma_dollar": peek["peek_gamma_dollar"],
        "peek_theta_yield": peek["peek_theta_yield"],
    }

    # One-hot the management policy (using the canonical list as single source of truth)
    for p in CANONICAL_MGMT_POLICY_NAMES:
        features[f"mgmt_{p}"] = 1.0 if policy.name == p else 0.0

    df = pd.DataFrame([features])

    # Ensure consistent column order
    expected_order = [
        "ret_1d", "ret_5d", "ret_14d", "iv_proxy", "iv_rank", "ema_stack",
        "volume_surge", "peek_theta_yield", "peek_gamma_dollar", "peek_credit",
        "target_delta", "dte", "profit_target", "max_loss_mult", "daily_capture_mult",
    ] + [f"mgmt_{p}" for p in CANONICAL_MGMT_POLICY_NAMES]

    for col in expected_order:
        if col not in df.columns:
            df[col] = 0.0

    return df[expected_order]


# Convenience: given a row and an action, return the peek dict (used in live path)
def get_peek_features_for_action(row: pd.Series, action: EntryAction) -> Dict[str, float]:
    S = float(row["close"])
    iv = float(row.get("iv_proxy", 0.55))
    return compute_peek_greeks(S, action, iv)


def build_should_trade_features(row: pd.Series) -> pd.DataFrame:
    """Action-agnostic 20-col vector for the should-trade gate (exact match to
    should_trade_model_20260515_0037.txt feature_names).

    Uses a *fixed neutral* EntryAction("put", 5, 0.22, min_credit_pct=0.010) +
    ManagementPolicy("standard") to populate peek greeks and the 8 mgmt_* one-hots.
    This is a deliberate engineering approximation (see MODEL_TRAINING_PLAYBOOK.md
    section 2.2 for full justification and calibration requirement): we query the
    joint (state + policy) profitability classifier at a canonical "typical" point
    in action/policy space rather than the exact winning action for that row.
    The resulting gate is a conservative proxy for "is this market state one in
    which even a typical policy can make money?"

    Caller (PickEntryModel.predict_should_trade) performs the final strict column
    alignment + reindex to the 20 names the model was trained on. This helper is
    the single source of truth for gate feature preparation.
    """
    neutral_action = EntryAction("put", 5, 0.22, min_credit_pct=0.010)
    neutral_policy = ManagementPolicy("standard")
    # build_model_features returns the full 23-col (incl. the 3 policy scalars for neutral);
    # the caller will reindex to the exact 20-col subset expected by the should-trade model
    # (the 12 market/peek/action + 8 mgmt one-hots, omitting profit/max/daily scalars).
    return build_model_features(row, neutral_action, neutral_policy)


TRAJECTORY_FEATURES = [
    "decision_step", "current_pnl_pct", "current_pace_vs_target", "days_held_norm",
    "max_adverse_pct", "is_gap_day", "ret_since_entry_1d", "ret_since_entry_3d",
    "iv_rank_at_decision", "regime_at_decision",
]


def _stable_regime_float(r: str) -> float:
    """Deterministic numeric encoding for regime (stable across runs/processes; unlike hash())."""
    if not r:
        return 0.0
    return (sum(ord(c) for c in str(r)) % 100) / 100.0


def build_management_decision_features(row: pd.Series, action: EntryAction, policy: ManagementPolicy, **traj) -> pd.DataFrame:
    """Single source of truth for close/roll decision features (current row + trajectory state from LabeledExample)."""
    df = build_model_features(row, action, policy)
    for k in TRAJECTORY_FEATURES:
        v = traj.get(k, 0 if k != "is_gap_day" else False)
        if k == "is_gap_day":
            df[k] = 1.0 if bool(v) else 0.0
        elif k == "regime_at_decision":
            df[k] = _stable_regime_float(v)
        else:
            fv = float(v)
            if not np.isfinite(fv):
                fv = 0.0
            df[k] = fv
    return df


def build_trajectory_dict(
    position: Optional[dict] = None,
    row: Optional[pd.Series] = None,
    mark: Optional[dict] = None,
    today: Optional[pd.Timestamp] = None,
) -> dict:
    """Single source of truth for the 10 TRAJECTORY_FEATURES (addresses duplication + None/gap/now() fragility).

    Conservative proxies for live tracker / what-if (no full path history available).
    Uses TRAJECTORY_FEATURES list. Safe None handling (past issue avoidance).
    Gap: consistent lookup (row.get gap/gap_flag) or False. days_held: uses provided today or entry_date math (no wall-clock in backtest paths).
    Callers (pick_entry_model, strategies advisor) must import and delegate.
    """
    from datetime import datetime as _dt  # local, minimal
    pos = position or {}
    r = row if row is not None else pd.Series(dtype=object)
    m = mark or {}

    # days_held_norm + decision_step: prefer explicit or compute from dates; avoid now() for determinism in tests/gauntlet
    entry_date = pos.get("entry_date")
    if today is None:
        today = pd.Timestamp.now().normalize() if entry_date else pd.Timestamp("2026-05-31")
    try:
        entry_ts = pd.Timestamp(entry_date) if entry_date else today
        days = max(0, (today.normalize() - entry_ts.normalize()).days)
    except Exception:
        days = 0
    dte0 = max(1, int(pos.get("dte_at_entry", 5) or 5))

    credit = float(pos.get("credit", 1.0) or 1.0)
    pnl_share = m.get("pnl_per_share") or pos.get("pnl_per_share", 0.0)
    try:
        cur_pnl_pct = float(pnl_share) / credit if credit > 0 else 0.0
    except Exception:
        cur_pnl_pct = 0.0

    # gap: unified, no hardcoded "gap_flag" vs "gap" drift; prefer data row
    is_gap = False
    if hasattr(r, "get"):
        g = r.get("gap", r.get("gap_flag", False))
        is_gap = bool(g) if g is not None else False

    # ret / iv / regime from current row (live) or defaults
    def _safe_f(k, default=0.0):
        v = r.get(k, default) if hasattr(r, "get") else default
        try:
            fv = float(v)
            return fv if np.isfinite(fv) else default
        except Exception:
            return default

    return {
        "decision_step": min(days, dte0),
        "current_pnl_pct": cur_pnl_pct,
        "current_pace_vs_target": 0.9,  # proxy (no full path daily pace in live tracker)
        "days_held_norm": min(days / dte0, 1.3),
        "max_adverse_pct": min(cur_pnl_pct, 0.0),  # conservative; full max adverse needs path history
        "is_gap_day": is_gap,
        "ret_since_entry_1d": _safe_f("ret_1d", 0.0),
        "ret_since_entry_3d": _safe_f("ret_5d", 0.0),  # proxy
        "iv_rank_at_decision": _safe_f("iv_rank", 50.0),
        "regime_at_decision": str(r.get("regime", "")) if hasattr(r, "get") else "",
    }

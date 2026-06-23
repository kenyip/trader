#!/usr/bin/env python3
"""
simulator/pick_entry_model.py

First working version of the live model-based strategy proposer.

This is the bridge from "simulator-trained models" to something that can actually
be used at decision time (in strategies.py, live.py, or the dashboard).

Current capabilities (v0.1):
- Loads the latest "Best Management Policy" model
- Loads the P/L regressor (optional, for scoring)
- Given a market state (row + pre-computed peek greeks), generates candidate
  (EntryAction + recommended ManagementPolicy) combinations
- Ranks them and returns the best recommendation(s)

This is the first piece that can truly "derive the strategy" from data.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lightgbm as lgb
import pricing

from simulator.trade_labeler import EntryAction, ManagementPolicy, DEFAULT_MANAGEMENT_POLICIES, DEFAULT_ENTRY_ACTIONS
from simulator.feature_utils import build_model_features, get_peek_features_for_action, build_should_trade_features, build_management_decision_features, TRAJECTORY_FEATURES, build_trajectory_dict


@dataclass
class Recommendation:
    """What the model recommends doing right now."""
    entry_action: EntryAction
    recommended_policy: ManagementPolicy
    predicted_pnl: float
    confidence: float
    reason: str = ""


class PickEntryModel:
    """
    Live model-based entry + management proposer.

    Usage:
        model = PickEntryModel()
        recs = model.recommend(current_row, current_features)
    """

    def __init__(self, model_dir: Path = Path(".cache/models"), best_policy_path: Optional[str] = None, should_trade_path: Optional[str] = None, management_path: Optional[str] = None):
        self.model_dir = model_dir
        self.best_policy_model = None
        self.pl_model = None  # P/L regressor (optional)
        self.should_trade_model = None
        self.feature_names = None
        self.should_feature_names = None
        self.mgmt_model = None
        self.mgmt_feature_names = None
        self.best_policy_path = best_policy_path
        self.should_trade_path = should_trade_path
        self.mgmt_path = management_path  # wired from StrategyConfig.model_management_path (fixes dead knob)

        self._load_models()

    def _load_models(self):
        """Load the most recent trained models (or pinned paths if supplied)."""
        # Best policy (23-col)
        if self.best_policy_path and Path(self.best_policy_path).exists():
            latest = Path(self.best_policy_path)
            print(f"Loading Best Policy model (pinned): {latest.name}")
            self.best_policy_model = lgb.Booster(model_file=str(latest))
            try:
                self.feature_names = self.best_policy_model.feature_name()
            except Exception:
                self.feature_names = None
        else:
            best_policy_files = sorted(self.model_dir.glob("best_policy_model_*.txt"))
            if best_policy_files:
                latest = best_policy_files[-1]
                print(f"Loading Best Policy model: {latest.name}")
                self.best_policy_model = lgb.Booster(model_file=str(latest))
                try:
                    self.feature_names = self.best_policy_model.feature_name()
                except Exception:
                    self.feature_names = None

        # P/L regressor (optional — off by default; stale models predict ~0 and block min_edge gates)
        import os
        if os.environ.get("PICK_ENTRY_USE_PL", "").lower() in ("1", "true", "yes"):
            pl_files = sorted(self.model_dir.glob("policy_model_*.txt"))
            if pl_files:
                latest = pl_files[-1]
                print(f"Loading P/L model: {latest.name}")
                self.pl_model = lgb.Booster(model_file=str(latest))

        # Should-trade gate (20-col) — loaded first at inference per PR 2 design
        if self.should_trade_path and Path(self.should_trade_path).exists():
            latest = Path(self.should_trade_path)
            print(f"Loading Should-Trade gate model (pinned): {latest.name}")
            self.should_trade_model = lgb.Booster(model_file=str(latest))
            try:
                self.should_feature_names = self.should_trade_model.feature_name()
            except Exception:
                self.should_feature_names = None
        else:
            should_files = sorted(self.model_dir.glob("should_trade_model_*.txt"))
            if should_files:
                latest = should_files[-1]
                print(f"Loading Should-Trade gate model: {latest.name}")
                self.should_trade_model = lgb.Booster(model_file=str(latest))
                try:
                    self.should_feature_names = self.should_trade_model.feature_name()
                except Exception:
                    self.should_feature_names = None

        if not self.best_policy_model:
            print("Warning: No Best Policy model found. Run train_best_policy_model.py first.")
        if not self.should_trade_model:
            print("Warning: No Should-Trade model found (gate will be permissive; recommend() will still apply min_*).")

        # mgmt load moved to lazy _ensure_mgmt_loaded (called only from recommend_management) to prevent import-time pollution of pure rule paths (just scenarios etc.)

    def _ensure_mgmt_loaded(self):
        """Lazy load for management advisor only (fixes import-time side-effect on pure-rule imports)."""
        if self.mgmt_model is not None or self.mgmt_feature_names is not None:
            return
        if self.mgmt_path and Path(self.mgmt_path).exists():
            latest = Path(self.mgmt_path)
            self.mgmt_model = lgb.Booster(model_file=str(latest))
            try:
                self.mgmt_feature_names = self.mgmt_model.feature_name()
            except Exception:
                self.mgmt_feature_names = None
            return
        mgmt_files = sorted(self.model_dir.glob("management_advisor_*.txt")) or sorted(self.model_dir.glob("mgmt_*model*.txt"))
        if mgmt_files:
            latest = mgmt_files[-1]
            # quiet load (no stdout pollution on rule paths)
            self.mgmt_model = lgb.Booster(model_file=str(latest))
            try:
                self.mgmt_feature_names = self.mgmt_model.feature_name()
            except Exception:
                self.mgmt_feature_names = None
        else:
            self.mgmt_model = None
            self.mgmt_feature_names = None
            # no warning print here (would pollute pure paths); diagnostics only surface on explicit recommend_management(debug=True)

    def _prepare_features(self, row: pd.Series, action: EntryAction, policy: ManagementPolicy) -> pd.DataFrame:
        """
        Build features using the shared utility + strictly align to the model's expected columns.
        This is the key fix for feature count mismatch.
        """
        # Inject peek greeks for this specific candidate action
        peek = get_peek_features_for_action(row, action)
        row = row.copy()
        row["peek_credit"] = peek["peek_credit"]
        row["peek_gamma_dollar"] = peek["peek_gamma_dollar"]
        row["peek_theta_yield"] = peek["peek_theta_yield"]

        df = build_model_features(row, action, policy)

        # Strictly align to the exact columns the model was trained on
        if self.feature_names is not None:
            for col in self.feature_names:
                if col not in df.columns:
                    df[col] = 0.0
            df = df[self.feature_names]

        return df

    def _prepare_management_features(self, row: pd.Series, action: EntryAction, policy: ManagementPolicy, trajectory: dict) -> pd.DataFrame:
        """Build 33-col (entry + 10 traj) features via SoT + strict alignment for any loaded mgmt advisor model.
        Reuses build_management_decision_features (det regime, NaN guard). Prevents OOD on partial traj.
        """
        # ensure all traj keys for robustness (past issue avoidance)
        traj = {k: trajectory.get(k, 0 if k != "is_gap_day" else False) for k in TRAJECTORY_FEATURES}
        df = build_management_decision_features(row, action, policy, **traj)

        if self.mgmt_feature_names is not None:
            for col in self.mgmt_feature_names:
                if col not in df.columns:
                    df[col] = 0.0
            # reindex exactly; extra cols dropped
            df = df[[c for c in self.mgmt_feature_names if c in df.columns]]
            # pad if model expects more (should not after training on same SoT)
            for col in self.mgmt_feature_names:
                if col not in df.columns:
                    df[col] = 0.0
            df = df[self.mgmt_feature_names]
        return df

    def predict_should_trade(self, row: pd.Series, debug: bool = False) -> float:
        """Return probability (0-1) from the should-trade gate using neutral canonical
        EntryAction + ManagementPolicy + strict 20-col alignment to the trained model.

        This is the cheap first filter per PR 2. If < model_min_should_trade (default 0.55)
        then recommend() immediately returns [] with rich diagnostic.
        """
        if self.should_trade_model is None:
            return 1.0  # no gate model loaded → permissive (still subject to min_* in recommend)

        try:
            feat_df = build_should_trade_features(row)
            # Strict alignment + reindex to the exact 20 cols the 20260515_0037 model expects
            if self.should_feature_names is not None:
                for col in self.should_feature_names:
                    if col not in feat_df.columns:
                        feat_df[col] = 0.0
                feat_df = feat_df[self.should_feature_names]
            raw = self.should_trade_model.predict(feat_df, predict_disable_shape_check=True)
            # Booster from LGBMClassifier binary → margin; sigmoid to probability
            margin = float(raw[0]) if hasattr(raw, "__len__") else float(raw)
            prob = 1.0 / (1.0 + np.exp(-margin))
            if debug:
                print(f"  [should_trade] prob={prob:.3f} (neutral put5@0.22 standard; 20-col aligned)")
            return prob
        except Exception as e:
            if debug:
                print(f"  [should_trade] predict error (falling back to 0.5): {e}")
            return 0.5

    def get_model_info(self) -> dict:
        """Return load status + feature counts for diagnostics / PLAN.md reports."""
        return {
            "best_policy_model": getattr(self.best_policy_model, "model_file", None) or "loaded" if self.best_policy_model else None,
            "should_trade_model": getattr(self.should_trade_model, "model_file", None) or "loaded" if self.should_trade_model else None,
            "mgmt_advisor_model": getattr(self.mgmt_model, "model_file", None) or "loaded" if self.mgmt_model else None,
            "best_feature_count": len(self.feature_names) if self.feature_names else 0,
            "should_feature_count": len(self.should_feature_names) if self.should_feature_names else 0,
            "mgmt_feature_count": len(self.mgmt_feature_names) if self.mgmt_feature_names else 0,
            "model_dir": str(self.model_dir),
        }

    def recommend(
        self,
        row: pd.Series,
        candidates: List[EntryAction] = None,
        top_k: int = 3,
        min_policy_conf: float = 0.35,
        min_edge: float = 0.0,
        min_should_trade: float = 0.55,
        use_should_trade_gate: bool = True,
        debug: bool = False,
        test_permissive: bool = False,
    ) -> List[Recommendation]:
        """
        Given current market state (row with features + peek greeks),
        return the top recommended (entry + management policy) combinations.

        PR 2 hardening:
        - Should-trade gate fires FIRST (if use_should_trade_gate and model present).
        - Only candidates with policy_conf >= min_policy_conf survive; min_edge applies only if P/L model loaded.
        - should_trade prob must be >= min_should_trade when gate enabled.
        - Rich per-candidate + aggregated diagnostics (printed when debug=True or always on key paths).
        - The old <0.15 unconditional boost / rescue is now behind test_permissive=True (dev only).
        """
        if self.best_policy_model is None:
            raise RuntimeError("No Best Policy model loaded. Run train_best_policy_model.py first.")

        if candidates is None:
            candidates = DEFAULT_ENTRY_ACTIONS

        # === SHOULD-TRADE GATE (first, cheap, per PR 2 spec) ===
        should_prob = 1.0
        if use_should_trade_gate and self.should_trade_model is not None:
            should_prob = self.predict_should_trade(row, debug=debug)
            if should_prob < min_should_trade:
                if debug:
                    print(f"[PickEntryModel] return [] reason: should_trade={should_prob:.3f} < {min_should_trade}")
                return []
            if debug:
                print(f"[PickEntryModel] should_trade prob={should_prob:.3f} (passes >= {min_should_trade})")

        scored = []
        min_credit = 0.010  # default; real credit check vs action.min_credit_pct happens upstream

        for action in candidates:
            for policy in DEFAULT_MANAGEMENT_POLICIES:
                feat_df = self._prepare_features(row, action, policy)

                # 1. policy confidence (best_policy multi-class)
                try:
                    raw_pred = self.best_policy_model.predict(feat_df, predict_disable_shape_check=True)
                    if len(raw_pred.shape) == 2 and raw_pred.shape[1] > 1:
                        proba = raw_pred[0]
                        classes = getattr(self.best_policy_model, 'classes_', [p.name for p in DEFAULT_MANAGEMENT_POLICIES])
                        try:
                            idx = list(classes).index(policy.name)
                            policy_confidence = float(proba[idx])
                        except (ValueError, IndexError):
                            policy_confidence = float(np.max(proba))
                    else:
                        policy_confidence = 0.65
                except Exception:
                    policy_confidence = 0.45  # fallback

                # 2. expected edge from P/L (optional)
                expected_pnl = 0.0
                if self.pl_model is not None:
                    try:
                        if self.feature_names is not None:
                            pl_feat = feat_df.copy()
                            for col in self.feature_names:
                                if col not in pl_feat.columns:
                                    pl_feat[col] = 0.0
                            pl_feat = pl_feat[[c for c in self.feature_names if c in pl_feat.columns]]
                            if len(pl_feat.columns) == self.pl_model.num_feature():
                                pl_pred = self.pl_model.predict(pl_feat, predict_disable_shape_check=True)[0]
                                expected_pnl = float(pl_pred)
                    except Exception:
                        expected_pnl = 0.0

                final_score = policy_confidence * 0.6 + (max(expected_pnl, 0) / 200.0) * 0.4

                rec = Recommendation(
                    entry_action=action,
                    recommended_policy=policy,
                    predicted_pnl=expected_pnl,
                    confidence=policy_confidence,
                    reason=f"conf={policy_confidence:.2f} edge=${expected_pnl:.1f} final={final_score:.2f}"
                )
                scored.append((final_score, rec, policy_confidence, expected_pnl))

                if debug:
                    print(f"  cand: {action.side} {action.dte}d@{action.target_delta}Δ {policy.name} "
                          f"conf={policy_confidence:.3f} pnl=${expected_pnl:.1f} score={final_score:.3f}")

        # Sort
        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            default_action = EntryAction("put", 5, 0.22)
            default_policy = ManagementPolicy("standard")
            return [Recommendation(
                entry_action=default_action,
                recommended_policy=default_policy,
                predicted_pnl=50.0,
                confidence=0.5,
                reason="Fallback (no scored candidates)"
            )]

        # === FILTER by min_policy_conf; min_edge only when P/L model is active ===
        use_edge = self.pl_model is not None and min_edge > 0
        if use_edge:
            filtered = [(s, r, c, e) for (s, r, c, e) in scored if c >= min_policy_conf and e >= min_edge]
        else:
            filtered = [(s, r, c, e) for (s, r, c, e) in scored if c >= min_policy_conf]
        if debug:
            top_c = scored[0][2] if scored else 0
            top_e = scored[0][3] if scored else 0
            edge_note = f", min_edge={min_edge}" if use_edge else " (edge gate off)"
            print(f"[PickEntryModel] gate filter: kept {len(filtered)}/{len(scored)} "
                  f"(min_policy_conf={min_policy_conf}{edge_note}); top had conf={top_c:.3f} edge=${top_e:.1f}")

        if not filtered:
            # clear return-[] reason for aggregated diagnostics (used by wrapper/validate)
            if debug:
                print(f"[PickEntryModel] return [] reason: no candidate met min_policy_conf={min_policy_conf} and min_edge={min_edge}")
            return []

        # Guard the old permissive rescue behind explicit test_permissive dev flag only
        if test_permissive and filtered[0][0] < 0.15:
            if debug:
                print("[PickEntryModel] test_permissive rescue applied (old <0.15 boost)")
            for i in range(min(len(filtered), top_k)):
                # bump for return
                filtered[i] = (0.55, filtered[i][1], filtered[i][2], filtered[i][3])

        top_recs = [rec for _, rec, _, _ in filtered[:top_k]]

        if debug:
            print(f"[PickEntryModel] recommend: should_prob={should_prob:.3f} "
                  f"returned {len(top_recs)} (top conf={filtered[0][2]:.3f} edge=${filtered[0][3]:.1f})")

        return top_recs

    def recommend_management(
        self,
        row: pd.Series,
        position: Optional[dict] = None,
        trajectory: Optional[dict] = None,
        min_conf: float = 0.30,
        min_edge: float = 4.0,
        debug: bool = False,
    ) -> dict:
        """
        Phase B: Management advisor for close/roll decisions.
        Given current market row + open Position state (from positions.py or backtest) + trajectory features
        (current_pnl_pct, pace, days_held_norm, max_adverse, ret_since_entry_*, regime_at_decision, iv_rank etc),
        returns a proposal for overrides or early close.

        Reuses PR 2 patterns exactly: SoT builder (build_management_decision_features), strict alignment,
        gates (min_conf / min_edge), rich diagnostics, safe neutral on no-model / low signal.

        Output (always safe to ignore): {
            'close': bool, 'reason': str, 'overrides': dict (e.g. {'delta_breach': 0.41, 'profit_target': 0.50}),
            'confidence': float, 'expected_improvement': float, 'policy_name': str or None
        }
        Empty or low-conf => no change recommended (defer to static ladder / adapt_exit).
        Never mutates Position or cfg.
        """
        if trajectory is None:
            trajectory = self._default_trajectory(position, row)

        self._ensure_mgmt_loaded()

        # Use a representative action/policy reconstructed from position if available; else neutral
        if position:
            try:
                action = EntryAction(
                    side=position.get('side', 'put'),
                    dte=position.get('dte_at_entry', 5),
                    target_delta=0.22,
                )
                pol_name = position.get('policy_name', 'standard')  # may not be present; best effort
                policy = ManagementPolicy(
                    name=pol_name if pol_name in [p.name for p in DEFAULT_MANAGEMENT_POLICIES] else 'standard',
                    profit_target=position.get('profit_target_override') or 0.55,
                    max_loss_mult=position.get('max_loss_mult_override') or 1.8,
                    daily_capture_mult=position.get('daily_capture_mult') or 1.5,
                    delta_breach=position.get('delta_breach_override') or 0.50,
                )
            except Exception:
                action = EntryAction("put", 5, 0.22)
                policy = ManagementPolicy("standard")
        else:
            action = EntryAction("put", 5, 0.22)
            policy = ManagementPolicy("standard")

        feat_df = self._prepare_management_features(row, action, policy, trajectory)

        confidence = 0.0
        expected_improvement = 0.0
        reason = "no management model loaded"
        proposed_overrides = {}
        do_close = False

        if self.mgmt_model is not None:
            try:
                raw = self.mgmt_model.predict(feat_df, predict_disable_shape_check=True)
                # For demo: if classifier, take max proba as conf; if regressor for improvement, use value
                if hasattr(raw, '__len__') and len(raw) > 0:
                    val = float(raw[0]) if not hasattr(raw[0], '__len__') else float(np.max(raw[0]))
                    confidence = min(max(abs(val), 0.0), 1.0)  # clamp proxy
                    expected_improvement = float(val) * 10.0  # scale heuristic for $ edge proxy
                else:
                    confidence = 0.45
                    expected_improvement = 0.0
                reason = f"mgmt model conf={confidence:.2f} edge~${expected_improvement:.1f} (traj-aware)"
                # Simple policy: if high conf and negative current pace or high adverse, propose tighten
                cur_pace = float(trajectory.get('current_pace_vs_target', 0.0))
                max_adv = float(trajectory.get('max_adverse_pct', 0.0))
                if confidence >= min_conf and (cur_pace < 0.5 or max_adv < -0.8):
                    proposed_overrides = {
                        'delta_breach': max(0.35, (float(v) if (v := position.get('delta_breach_override')) is not None else 0.50) * 0.85) if position else 0.42,
                        'daily_capture_mult': 1.2,
                    }
                    if max_adv < -1.2:
                        do_close = True
                        reason = "mgmt: high adverse excursion + model signal → recommend early close/roll"
            except Exception as e:
                if debug:
                    print(f"[recommend_management] model predict error (neutral): {e}")
                confidence = 0.0
                reason = "mgmt model error (safe neutral)"
        else:
            # Diagnostics only — enables the training loop and what-if without model artifact
            cur_pnl = float(trajectory.get('current_pnl_pct', 0.0))
            pace = float(trajectory.get('current_pace_vs_target', 0.0))
            adv = float(trajectory.get('max_adverse_pct', 0.0))
            regime = trajectory.get('regime_at_decision', '')
            reason = f"neutral (no mgmt advisor model): pnl={cur_pnl:.2f} pace={pace:.2f} adv={adv:.2f} regime={regime}"
            if debug:
                print(f"[recommend_management] {reason} (use focused synthetic labels + train to populate .cache/models/management_advisor_*.txt)")

        # Gates (PR 2 pattern)
        if confidence < min_conf or expected_improvement < min_edge:
            if debug or (confidence > 0.1 and debug is False):
                print(f"[PickEntryModel] mgmt gate: conf={confidence:.3f} < {min_conf} or edge ${expected_improvement:.1f} < {min_edge} → neutral (no override)")
            proposed_overrides = {}
            do_close = False

        result = {
            'close': do_close,
            'reason': reason,
            'overrides': proposed_overrides,
            'confidence': float(confidence),
            'expected_improvement': float(expected_improvement),
            'policy_name': policy.name,
            'trajectory_used': {k: trajectory.get(k) for k in ['decision_step', 'current_pnl_pct', 'max_adverse_pct', 'regime_at_decision']},
        }
        if debug:
            print(f"[PickEntryModel] recommend_management -> close={do_close} conf={confidence:.3f} overrides={proposed_overrides}")
        return result

    def _default_trajectory(self, position: Optional[dict], row: pd.Series) -> dict:
        """Delegates to SoT (fixes dupe/None/gap/now() + fragile float(None) sites via unified safe builder)."""
        return build_trajectory_dict(position=position, row=row, mark=None, today=None)


# Simple demo
if __name__ == "__main__":
    print("PickEntryModel v0.1 Demo")

    # Load a recent row from real data
    from data import build
    df = build("TSLA", period="2y")
    latest = df.iloc[-1]

    model = PickEntryModel()
    recs = model.recommend(latest)

    print("\nTop Recommendations:")
    for i, rec in enumerate(recs, 1):
        print(f"{i}. {rec.entry_action.side.upper()} {rec.entry_action.dte}d @ {rec.entry_action.target_delta}Δ "
              f"→ Manage with '{rec.recommended_policy.name}' "
              f"(confidence {rec.confidence:.2f})")
        print(f"   Reason: {rec.reason}\n")

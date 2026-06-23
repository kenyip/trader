#!/usr/bin/env python3
"""
simulator/trade_labeler.py  —  Upgraded Trade Labeling Engine (v0.2+)

This is the highest-leverage component for the north star.

Major upgrades in this version:
- Much more faithful trade simulation (closer to real check_exits behavior).
- Explicit **Management Policies**: We now evaluate multiple exit/roll strategies
  per candidate entry (not just one fixed ladder).
- Richer labels: For each (entry, management) pair we record detailed outcomes.
- Designed to produce high-quality training data so a model can learn
  not just "should I enter?" but "**what is the best full plan** (entry + management)?"
- Still fast enough to label thousands of paths.

This version moves us from "better skip rules" toward "learned full strategies".
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pricing


@dataclass
class EntryAction:
    """A candidate entry we want to evaluate."""
    side: str                    # 'put' or 'call'
    dte: int
    target_delta: float
    min_credit_pct: float = 0.010


@dataclass
class ManagementPolicy:
    """
    A named exit + roll management strategy.
    This is what allows the labeler to evaluate different ways of managing the same entry.
    """
    name: str
    profit_target: float = 0.55
    max_loss_mult: float = 1.8
    daily_capture_mult: float = 1.5
    delta_breach: float = 0.50
    allow_roll: bool = False
    roll_credit_ratio: float = 1.0


# Base set of management policies
DEFAULT_MANAGEMENT_POLICIES: List[ManagementPolicy] = [
    ManagementPolicy("standard", profit_target=0.55, max_loss_mult=1.8, daily_capture_mult=1.5),
    ManagementPolicy("aggressive_capture", profit_target=0.35, max_loss_mult=1.4, daily_capture_mult=1.1),
    ManagementPolicy("very_aggressive", profit_target=0.25, max_loss_mult=1.2, daily_capture_mult=0.9),
    ManagementPolicy("hold_longer", profit_target=0.70, max_loss_mult=2.8, daily_capture_mult=2.2),
    ManagementPolicy("hold_very_long", profit_target=0.80, max_loss_mult=3.5, daily_capture_mult=3.0),
    ManagementPolicy("tight_risk", profit_target=0.50, max_loss_mult=1.3, daily_capture_mult=1.3, delta_breach=0.38),
    ManagementPolicy("ultra_tight", profit_target=0.45, max_loss_mult=1.1, daily_capture_mult=1.1, delta_breach=0.35),
    ManagementPolicy("credit_focused", profit_target=0.60, max_loss_mult=2.0, daily_capture_mult=1.6),
]


def sample_management_policies(n: int = 18, random_state: int = None) -> List[ManagementPolicy]:
    """
    Generate a richer, parameterized set of management policies for high-quality labeling.
    Covers the spectrum: tight risk, aggressive capture, ride-to-expiry, credit-focused, etc.
    """
    rng = np.random.default_rng(random_state)
    policies = []

    for _ in range(n):
        # Bias toward interesting corners for better oracle coverage
        if rng.random() < 0.15:
            # Ride-to-expiry style (high target, loose risk, low daily capture)
            pt = float(rng.uniform(0.70, 0.90))
            ml = float(rng.uniform(2.8, 4.5))
            dc = float(rng.uniform(0.6, 1.1))
            db = float(rng.uniform(0.48, 0.60))
        elif rng.random() < 0.15:
            # Ultra tight gamma risk
            pt = float(rng.uniform(0.35, 0.55))
            ml = float(rng.uniform(0.95, 1.35))
            dc = float(rng.uniform(1.0, 1.6))
            db = float(rng.uniform(0.30, 0.38))
        else:
            pt = float(rng.uniform(0.25, 0.82))
            ml = float(rng.uniform(1.05, 3.6))
            dc = float(rng.uniform(0.85, 3.0))
            db = float(rng.uniform(0.32, 0.55))

        allow_roll = bool(rng.choice([True, False], p=[0.25, 0.75]))

        policies.append(
            ManagementPolicy(
                name=f"sampled_{len(policies)}",
                profit_target=pt,
                max_loss_mult=ml,
                daily_capture_mult=dc,
                delta_breach=db,
                allow_roll=allow_roll,
            )
        )

    # Always include the strong fixed ones at the end (they get deduped in oracle)
    policies.extend(DEFAULT_MANAGEMENT_POLICIES)
    return policies


@dataclass
class LabeledExample:
    """One rich training example: (state + entry_action + management_policy) → outcome"""
    # Identifiers
    path_id: int
    ticker: str
    scenario_type: str
    entry_index: int

    # Action
    entry_action: EntryAction
    management_policy: ManagementPolicy

    # Outcomes
    realized_pnl_per_contract: float
    max_adverse_excursion: float
    days_held: int
    exit_reason: str
    needed_roll: bool
    best_policy_for_path: str = ""   # Best among the policies we explicitly evaluated for this (path, entry, action)
    oracle_best_pnl: float = 0.0
    oracle_best_policy: str = ""
    regret_vs_oracle: float = 0.0   # How much better the oracle could have done on this path (max(0, oracle - realized))

    # === Phase A: Trajectory / decision-state features (for close/roll condition learning) ===
    # Captured at the decision/exit point (or sampled mid-trade points in future extensions).
    # These give the model "previous signals + current trade context" for dynamic management.
    decision_step: int = 0                    # 0 = entry time; >0 = steps after entry when this state was observed
    current_pnl_pct: float = 0.0              # (credit - mtm) / credit at the observation point
    current_pace_vs_target: float = 0.0       # (daily_pace) / daily_theta_target
    days_held_norm: float = 0.0               # days_held / dte_at_entry (0..1+)
    max_adverse_pct: float = 0.0              # worst (credit - mtm) / credit seen so far (negative = loss)
    is_gap_day: bool = False                  # overnight gap >3% on the day this decision state was observed
    regime_at_decision: str = ""              # regime flag from the path row at observation time
    ret_since_entry_1d: float = 0.0           # underlying return over the last 1 trading day at decision time
    ret_since_entry_3d: float = 0.0           # ... last 3 days (useful for momentum/reversal context)
    iv_rank_at_decision: float = 50.0         # IV rank at the observation bar


class TradeLabelerV2:
    """
    Upgraded labeling engine.

    For every interesting point on every generated path, it:
      1. Evaluates a set of EntryActions
      2. For each EntryAction, evaluates multiple ManagementPolicies
      3. Simulates the trade forward on the actual path
      4. Records detailed outcomes
    """

    def __init__(self, risk_free_rate: float = 0.04):
        self.r = risk_free_rate

    def _trajectory_at_step(
        self,
        path: pd.DataFrame,
        entry_idx: int,
        action: EntryAction,
        policy: ManagementPolicy,
        step: int,
        credit: float,
        K: float,
        iv: float,
        mtm: float,
        max_adverse: float,
        is_gap_day: bool,
        daily_pace: float,
    ) -> Dict[str, Any]:
        daily_theta_target = credit / action.dte if action.dte > 0 else 0.0
        current_pnl_pct = (credit - mtm) / credit if credit > 0 else 0.0
        ret_since_1d = 0.0
        ret_since_3d = 0.0
        if entry_idx + step < len(path):
            entry_s = float(path["close"].iloc[entry_idx])
            decision_s = float(path["close"].iloc[entry_idx + step])
            if step >= 1:
                s_prev1 = float(path["close"].iloc[entry_idx + step - 1])
                ret_since_1d = (decision_s - s_prev1) / s_prev1 if s_prev1 > 0 else 0.0
            if step >= 3:
                s_prev3 = float(path["close"].iloc[entry_idx + step - 3])
                ret_since_3d = (decision_s - s_prev3) / s_prev3 if s_prev3 > 0 else 0.0
        return {
            "decision_step": step,
            "current_pnl_pct": current_pnl_pct,
            "current_pace_vs_target": (daily_pace / daily_theta_target) if daily_theta_target > 0 else 0.0,
            "days_held_norm": step / max(action.dte, 1),
            "max_adverse_pct": max_adverse / credit if credit > 0 else 0.0,
            "is_gap_day": is_gap_day,
            "ret_since_entry_1d": ret_since_1d,
            "ret_since_entry_3d": ret_since_3d,
            "regime_at_decision": str(
                path["regime"].iloc[entry_idx + step]
                if "regime" in path.columns and entry_idx + step < len(path)
                else ""
            ),
            "iv_rank_at_decision": float(
                path["iv_rank"].iloc[entry_idx + step]
                if "iv_rank" in path.columns and entry_idx + step < len(path)
                else 50.0
            ),
        }

    def _simulate_on_path(
        self,
        path: pd.DataFrame,
        entry_idx: int,
        action: EntryAction,
        policy: ManagementPolicy,
        max_steps: int = 35,
        collect_midtrade: bool = False,
    ) -> Dict[str, Any]:
        """
        Simulate one entry + one management policy forward on the path.
        This is more faithful than v0.1.
        """
        if entry_idx >= len(path) - 3:
            return {"valid": False}

        S0 = float(path["close"].iloc[entry_idx])
        T = action.dte / 365.0
        iv = 0.60  # TODO: later use simulated or path-derived IV

        try:
            K = pricing.strike_from_delta(S0, T, iv, action.target_delta, action.side, r=self.r)
            K = pricing.round_strike(K, 2.5)
            credit = pricing.price(S0, K, T, iv, action.side, r=self.r)
        except Exception:
            return {"valid": False}

        if credit <= 0 or (credit / K) < action.min_credit_pct:
            return {"valid": False}

        # Simulation state
        current_credit = credit
        max_adverse = 0.0
        realized_pnl = 0.0
        exit_reason = "end_of_path"
        days_held = 0
        is_gap_day = False
        daily_pace = 0.0
        mtm = 0.0
        midtrade_snapshots: List[Dict[str, Any]] = []

        for step in range(1, max_steps + 1):
            if entry_idx + step >= len(path):
                break

            S = float(path["close"].iloc[entry_idx + step])
            days_held = step
            T_rem = max((action.dte - step) / 365.0, 0.001)

            try:
                mtm = pricing.price(S, K, T_rem, iv, action.side, r=self.r)
            except:
                mtm = max(S - K, 0) if action.side == "call" else max(K - S, 0)

            pnl = credit - mtm
            max_adverse = min(max_adverse, pnl)

            # === Improved Management Policy Logic (closer to real engine) ===

            # Detect overnight gap (simple version)
            prev_close = path["close"].iloc[entry_idx + step - 1]
            gap = abs(S - prev_close) / prev_close if prev_close > 0 else 0
            is_gap_day = gap > 0.03

            daily_theta_target = credit / action.dte
            daily_pace = pnl / days_held if days_held > 0 else 0

            if collect_midtrade:
                midtrade_snapshots.append(
                    self._trajectory_at_step(
                        path, entry_idx, action, policy, step, credit, K, iv, mtm,
                        max_adverse, is_gap_day, daily_pace,
                    )
                )

            # Max loss (with simple gap penalty, like real engine)
            effective_max_loss = policy.max_loss_mult
            if is_gap_day and pnl < 0:
                effective_max_loss *= 0.85  # harsher on gap days

            if pnl <= -effective_max_loss * credit:
                exit_reason = "max_loss"
                realized_pnl = pnl
                break

            # Daily capture (more accurate pace check)
            if pnl > 0 and daily_pace >= policy.daily_capture_mult * daily_theta_target:
                exit_reason = "daily_capture"
                realized_pnl = pnl
                break

            # Profit target
            if pnl >= policy.profit_target * credit:
                exit_reason = "profit_target"
                realized_pnl = pnl
                break

            # Delta breach
            try:
                current_delta = pricing.delta(S, K, T_rem, iv, action.side, r=self.r)
                if abs(current_delta) > policy.delta_breach:
                    exit_reason = "delta_breach"
                    realized_pnl = pnl
                    break
            except:
                pass

            # Expiration
            if step >= action.dte:
                exit_reason = "expired"
                realized_pnl = pnl
                break

            realized_pnl = pnl

        # Phase A: capture trajectory state at the (exit or end-of-path) decision point
        # These become training features for learning close/roll conditions.
        exit_step = days_held
        current_pnl_pct = (credit - mtm) / credit if credit > 0 else 0.0
        daily_theta_target = credit / action.dte if action.dte > 0 else 0.0
        current_pace_vs_target = (daily_pace / daily_theta_target) if daily_theta_target > 0 else 0.0
        days_held_norm = days_held / max(action.dte, 1)
        max_adverse_pct = max_adverse / credit if credit > 0 else 0.0

        # ret_since_entry (simple lookback on the path; 0 if not enough history)
        ret_since_1d = 0.0
        ret_since_3d = 0.0
        if entry_idx + exit_step < len(path):
            # underlying returns from entry to the decision bar (and recent slices)
            entry_s = float(path["close"].iloc[entry_idx])
            decision_s = float(path["close"].iloc[entry_idx + exit_step])
            if entry_s > 0:
                # full since-entry move (for context); recent slices for momentum
                full_ret = (decision_s - entry_s) / entry_s
                # approximate recent slices (best effort; real features preferred in enrichment)
                if exit_step >= 1:
                    s_prev1 = float(path["close"].iloc[entry_idx + exit_step - 1])
                    ret_since_1d = (decision_s - s_prev1) / s_prev1 if s_prev1 > 0 else 0.0
                if exit_step >= 3:
                    s_prev3 = float(path["close"].iloc[entry_idx + exit_step - 3])
                    ret_since_3d = (decision_s - s_prev3) / s_prev3 if s_prev3 > 0 else 0.0

        return {
            "valid": True,
            "realized_pnl_per_contract": realized_pnl * 100,
            "max_adverse_excursion": max_adverse * 100,
            "days_held": days_held,
            "exit_reason": exit_reason,
            "needed_roll": (exit_reason == "max_loss" and policy.allow_roll),
            # Trajectory state at decision (Phase A)
            "decision_step": exit_step,
            "current_pnl_pct": current_pnl_pct,
            "current_pace_vs_target": current_pace_vs_target,
            "days_held_norm": days_held_norm,
            "max_adverse_pct": max_adverse_pct,
            "is_gap_day": is_gap_day,
            "ret_since_entry_1d": ret_since_1d,
            "ret_since_entry_3d": ret_since_3d,
            "regime_at_decision": str(path["regime"].iloc[entry_idx + exit_step] if "regime" in path.columns and entry_idx + exit_step < len(path) else ""),
            "iv_rank_at_decision": float(path["iv_rank"].iloc[entry_idx + exit_step] if "iv_rank" in path.columns and entry_idx + exit_step < len(path) else 50.0),
            "midtrade_snapshots": midtrade_snapshots if collect_midtrade else [],
        }

    def label_path(
        self,
        path_df: pd.DataFrame,
        path_id: int,
        ticker: str,
        scenario_type: str,
        entry_actions: List[EntryAction],
        management_policies: List[ManagementPolicy] = None,
        sample_every: int = 3,
        use_sampling: bool = False,
        n_sampled_policies: int = 10,
        emit_midtrade: bool = False,
    ) -> List[LabeledExample]:
        """
        Label one path with multiple entry actions × multiple management policies.
        If use_sampling=True, it will sample additional parameterized policies for richer labels.
        """
        if management_policies is None:
            management_policies = DEFAULT_MANAGEMENT_POLICIES

        if use_sampling:
            sampled = sample_management_policies(n_sampled_policies)
            # Remove duplicates by name
            all_policies = {p.name: p for p in management_policies + sampled}.values()
            management_policies = list(all_policies)

        examples = []
        n = len(path_df)

        for i in range(3, n - 8, sample_every):
            for action in entry_actions:
                action_examples = []  # valid ones only for this (i, action)
                best_pnl_for_action = -np.inf
                best_policy_name = ""

                for policy in management_policies:
                    track_mid = emit_midtrade and policy.name == "standard"
                    outcome = self._simulate_on_path(
                        path_df, i, action, policy, collect_midtrade=track_mid,
                    )

                    if not outcome.get("valid"):
                        continue

                    pnl = outcome["realized_pnl_per_contract"]

                    ex = LabeledExample(
                        path_id=path_id,
                        ticker=ticker,
                        scenario_type=scenario_type,
                        entry_index=i,
                        entry_action=action,
                        management_policy=policy,
                        realized_pnl_per_contract=pnl,
                        max_adverse_excursion=outcome["max_adverse_excursion"],
                        days_held=outcome["days_held"],
                        exit_reason=outcome["exit_reason"],
                        needed_roll=outcome["needed_roll"],
                        # Phase A trajectory / decision state (safe fallbacks if older outcome dict)
                        decision_step=outcome.get("decision_step", 0),
                        current_pnl_pct=outcome.get("current_pnl_pct", 0.0),
                        current_pace_vs_target=outcome.get("current_pace_vs_target", 0.0),
                        days_held_norm=outcome.get("days_held_norm", 0.0),
                        max_adverse_pct=outcome.get("max_adverse_pct", 0.0),
                        is_gap_day=outcome.get("is_gap_day", False),
                        ret_since_entry_1d=outcome.get("ret_since_entry_1d", 0.0),
                        ret_since_entry_3d=outcome.get("ret_since_entry_3d", 0.0),
                        iv_rank_at_decision=outcome.get("iv_rank_at_decision", 50.0),
                        regime_at_decision=outcome.get("regime_at_decision", ""),
                    )
                    action_examples.append(ex)
                    examples.append(ex)

                    if track_mid:
                        for snap in outcome.get("midtrade_snapshots", []):
                            if snap["decision_step"] <= 0 or snap["decision_step"] >= outcome["days_held"]:
                                continue
                            mid_ex = LabeledExample(
                                path_id=path_id,
                                ticker=ticker,
                                scenario_type=f"{scenario_type}_midtrade",
                                entry_index=i,
                                entry_action=action,
                                management_policy=policy,
                                realized_pnl_per_contract=pnl,
                                max_adverse_excursion=outcome["max_adverse_excursion"],
                                days_held=snap["decision_step"],
                                exit_reason="midtrade_snapshot",
                                needed_roll=False,
                                decision_step=snap["decision_step"],
                                current_pnl_pct=snap["current_pnl_pct"],
                                current_pace_vs_target=snap["current_pace_vs_target"],
                                days_held_norm=snap["days_held_norm"],
                                max_adverse_pct=snap["max_adverse_pct"],
                                is_gap_day=snap["is_gap_day"],
                                ret_since_entry_1d=snap["ret_since_entry_1d"],
                                ret_since_entry_3d=snap["ret_since_entry_3d"],
                                iv_rank_at_decision=snap["iv_rank_at_decision"],
                                regime_at_decision=snap["regime_at_decision"],
                            )
                            examples.append(mid_ex)

                    if pnl > best_pnl_for_action:
                        best_pnl_for_action = pnl
                        best_policy_name = policy.name

                # Compute oracle (denser search) once per action at this entry point
                oracle = self.compute_oracle_best_on_path(path_df, i, action)
                oracle_pnl = oracle.get("oracle_best_pnl", 0.0)
                oracle_name = oracle.get("oracle_best_policy", "")

                # Assign best among evaluated + oracle/regret to the action's examples
                for ex in action_examples:
                    ex.best_policy_for_path = best_policy_name if best_policy_name else ""
                    ex.oracle_best_pnl = oracle_pnl
                    ex.oracle_best_policy = oracle_name
                    ex.regret_vs_oracle = max(0.0, oracle_pnl - ex.realized_pnl_per_contract) if oracle_pnl > 0 else 0.0

        return examples

    def compute_oracle_best_on_path(
        self,
        path_df: pd.DataFrame,
        entry_idx: int,
        action: EntryAction,
        n_oracle_policies: int = 25,
    ) -> Dict[str, Any]:
        """
        For a given state + entry action, evaluate a denser set of management policies
        (DEFAULT canonical + many sampled) and return the best possible outcome we can find on this path.
        This is the "oracle" (future-path-informed) best for regret tracking.
        """
        # Combine dense random samples + the strong canonical defaults for best coverage
        oracle_policies = sample_management_policies(n_oracle_policies, random_state=entry_idx)
        # de-dup by (profit_target, max_loss_mult, daily_capture_mult) approx
        seen_keys = set()
        unique_policies = []
        for p in oracle_policies + DEFAULT_MANAGEMENT_POLICIES:
            key = (round(p.profit_target, 3), round(p.max_loss_mult, 2), round(p.daily_capture_mult, 2))
            if key not in seen_keys:
                seen_keys.add(key)
                unique_policies.append(p)

        best_pnl = -np.inf
        best_policy_name = ""
        best_policy_obj = None

        for policy in unique_policies:
            outcome = self._simulate_on_path(path_df, entry_idx, action, policy)
            if outcome.get("valid") and outcome["realized_pnl_per_contract"] > best_pnl:
                best_pnl = outcome["realized_pnl_per_contract"]
                best_policy_name = policy.name
                best_policy_obj = policy

        return {
            "oracle_best_pnl": best_pnl if best_pnl > -np.inf else 0.0,
            "oracle_best_policy": best_policy_name,
            # Best-effort: if we have the best_policy_obj, we could simulate one more time to get its exact trajectory state at the decision point.
            # For v1 the caller in label_path already has rich outcomes from the explicit policies; oracle is mainly for regret scalar.
        }

    def label_scenarios(self, scenarios_df: pd.DataFrame,
                        entry_actions: List[EntryAction] = None,
                        management_policies: List[ManagementPolicy] = None,
                        use_sampling: bool = False,
                        n_sampled_policies: int = 10,
                        compute_oracle_regret: bool = True,
                        emit_midtrade: bool = False) -> pd.DataFrame:
        """
        High-level method: take output from generate_scenarios.py and produce
        a rich labeled DataFrame ready for model training.
        """
        if entry_actions is None:
            entry_actions = DEFAULT_ENTRY_ACTIONS

        all_examples = []

        for (ticker, stype, pid), group in scenarios_df.groupby(["ticker", "scenario_type", "path_id"]):
            group = group.sort_index()
            exs = self.label_path(
                group,
                path_id=int(pid),
                ticker=ticker,
                scenario_type=stype,
                entry_actions=entry_actions,
                management_policies=management_policies,
                use_sampling=use_sampling,
                n_sampled_policies=n_sampled_policies,
                emit_midtrade=emit_midtrade,
            )
            all_examples.extend(exs)

        # Convert to DataFrame
        records = []
        for ex in all_examples:
            rec = {
                "path_id": ex.path_id,
                "ticker": ex.ticker,
                "scenario_type": ex.scenario_type,
                "entry_index": ex.entry_index,
                "side": ex.entry_action.side,
                "dte": ex.entry_action.dte,
                "target_delta": ex.entry_action.target_delta,
                "management_policy": ex.management_policy.name,
                "profit_target": ex.management_policy.profit_target,
                "max_loss_mult": ex.management_policy.max_loss_mult,
                "daily_capture_mult": ex.management_policy.daily_capture_mult,
                "pnl_per_contract": ex.realized_pnl_per_contract,
                "max_adverse": ex.max_adverse_excursion,
                "days_held": ex.days_held,
                "exit_reason": ex.exit_reason,
                "needed_roll": ex.needed_roll,
                "best_policy_for_path": ex.best_policy_for_path,
                # Regret / oracle supervision (new in v0.3+)
                "oracle_best_pnl": ex.oracle_best_pnl,
                "oracle_best_policy": ex.oracle_best_policy,
                "regret_vs_oracle": ex.regret_vs_oracle,
                "decision_step": ex.decision_step,
                "current_pnl_pct": ex.current_pnl_pct,
                "current_pace_vs_target": ex.current_pace_vs_target,
                "days_held_norm": ex.days_held_norm,
                "max_adverse_pct": ex.max_adverse_pct,
                "is_gap_day": ex.is_gap_day,
                "regime_at_decision": ex.regime_at_decision,
                "ret_since_entry_1d": ex.ret_since_entry_1d,
                "ret_since_entry_3d": ex.ret_since_entry_3d,
                "iv_rank_at_decision": ex.iv_rank_at_decision,
            }
            records.append(rec)

        return pd.DataFrame(records)


# Canonical management policy names used for one-hot encoding in features (single source of truth)
CANONICAL_MGMT_POLICY_NAMES = [
    "standard", "aggressive_capture", "very_aggressive",
    "hold_longer", "hold_very_long", "tight_risk",
    "ultra_tight", "credit_focused",
]

# Default entry actions used across the project
DEFAULT_ENTRY_ACTIONS = [
    EntryAction("put", 3, 0.25),
    EntryAction("put", 5, 0.22),
    EntryAction("put", 7, 0.20),
    EntryAction("call", 3, 0.20),
    EntryAction("call", 5, 0.20),
]


if __name__ == "__main__":
    print("TradeLabelerV2 smoke test")

    from simulator.market_generator import MarketGenerator, GeneratorConfig

    cfg = GeneratorConfig(ticker="TSLA", random_seed=42)
    gen = MarketGenerator(cfg)
    gen.calibrate()
    scenarios = gen.generate_daily_dataframe(n_paths=5, length_days=18)
    scenarios["ticker"] = "TSLA"
    scenarios["scenario_type"] = "test"

    labeler = TradeLabelerV2()
    labeled = labeler.label_scenarios(scenarios, entry_actions=DEFAULT_ENTRY_ACTIONS)

    print(f"\nGenerated {len(labeled)} rich labeled examples")
    print("Columns:", list(labeled.columns))
    print("\nSample:")
    print(labeled[["side", "dte", "management_policy", "pnl_per_contract", "exit_reason", "best_policy_for_path"]].head(6))

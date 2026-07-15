#!/usr/bin/env python3
"""Train-only time-series breakout-continuation discovery lab."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from scripts.low_hv_cross_section_train_lab import (
        assemble_close_panel,
        circular_block_bootstrap_lower_bound,
        load_adjusted_history,
    )
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from low_hv_cross_section_train_lab import (  # type: ignore[no-redef]
        assemble_close_panel,
        circular_block_bootstrap_lower_bound,
        load_adjusted_history,
    )


DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AMD", "TSLA"]


def _validate_panel(close_panel: pd.DataFrame) -> pd.DataFrame:
    if close_panel.empty or close_panel.shape[1] < 1:
        raise ValueError("close panel must contain at least one symbol")
    prepared = close_panel.copy()
    prepared.index = pd.DatetimeIndex(pd.to_datetime(prepared.index)).tz_localize(None).normalize()
    prepared.columns = [str(column).strip().upper() for column in prepared.columns]
    prepared = prepared.apply(pd.to_numeric, errors="coerce")
    values = prepared.to_numpy(dtype=float)
    if (
        not prepared.index.is_unique
        or not prepared.index.is_monotonic_increasing
        or len(set(prepared.columns)) != len(prepared.columns)
        or not np.isfinite(values).all()
        or (values <= 0.0).any()
    ):
        raise ValueError("close panel must be unique, increasing, finite, and positive")
    return prepared


def _overlaps(
    window: tuple[pd.Timestamp, pd.Timestamp],
    occupied: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    start, end = window
    return any(not (end < prior_start or start > prior_end) for prior_start, prior_end in occupied)


def build_matched_blueprints(
    close_panel: pd.DataFrame,
    *,
    breakout_lookback_sessions: int = 20,
    breakout_ratio_min: float = 1.02,
    control_breakout_ratio_low: float = 0.95,
    control_breakout_ratio_high: float = 1.00,
    trend_lookback_sessions: int = 100,
    forward_sessions: int = 10,
    max_match_distance_sessions: int = 126,
    max_return_20d_distance: float = 0.08,
    max_hv_20d_distance: float = 0.25,
) -> list[dict[str, Any]]:
    """Match breakouts to earlier same-symbol near-high controls without outcomes."""
    panel = _validate_panel(close_panel)
    if min(breakout_lookback_sessions, trend_lookback_sessions, forward_sessions) < 1:
        raise ValueError("lookbacks and forward sessions must be positive")
    if not 0.0 < control_breakout_ratio_low <= control_breakout_ratio_high <= breakout_ratio_min:
        raise ValueError("control and breakout bounds must be ordered")
    if max_match_distance_sessions < forward_sessions + 1:
        raise ValueError("match distance must exceed the forward window")

    all_blueprints: list[dict[str, Any]] = []
    for symbol in panel.columns:
        close = panel[symbol]
        prior_high = close.shift(1).rolling(
            breakout_lookback_sessions, min_periods=breakout_lookback_sessions
        ).max()
        prior_sma = close.shift(1).rolling(
            trend_lookback_sessions, min_periods=trend_lookback_sessions
        ).mean()
        ret_20 = close / close.shift(20) - 1.0
        log_return = np.log(close / close.shift(1))
        hv_20 = log_return.rolling(20, min_periods=20).std() * np.sqrt(252.0)
        features = pd.DataFrame(
            {
                "breakout_ratio": close / prior_high,
                "trend_distance": close / prior_sma - 1.0,
                "ret_20": ret_20,
                "hv_20": hv_20,
            },
            index=panel.index,
        )
        last_signal_position = len(panel) - forward_sessions - 2
        eligible = [
            position
            for position in range(len(panel))
            if position <= last_signal_position
            and np.isfinite(features.iloc[position].to_numpy(dtype=float)).all()
            and float(features.iloc[position]["trend_distance"]) > 0.0
        ]
        treated_positions = [
            position
            for position in eligible
            if float(features.iloc[position]["breakout_ratio"]) >= breakout_ratio_min
        ]
        control_positions = [
            position
            for position in eligible
            if control_breakout_ratio_low
            <= float(features.iloc[position]["breakout_ratio"])
            <= control_breakout_ratio_high
        ]
        occupied: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        used_controls: set[int] = set()
        for treated_position in treated_positions:
            treated_window = (
                pd.Timestamp(panel.index[treated_position + 1]),
                pd.Timestamp(panel.index[treated_position + 1 + forward_sessions]),
            )
            if _overlaps(treated_window, occupied):
                continue
            treated = features.iloc[treated_position]
            candidates: list[tuple[float, int]] = []
            for control_position in control_positions:
                if control_position >= treated_position or control_position in used_controls:
                    continue
                distance = treated_position - control_position
                if distance > max_match_distance_sessions:
                    continue
                control_window = (
                    pd.Timestamp(panel.index[control_position + 1]),
                    pd.Timestamp(panel.index[control_position + 1 + forward_sessions]),
                )
                if control_window[1] >= pd.Timestamp(panel.index[treated_position]):
                    continue
                if _overlaps(control_window, occupied) or _overlaps(control_window, [treated_window]):
                    continue
                control = features.iloc[control_position]
                return_gap = abs(float(treated["ret_20"]) - float(control["ret_20"]))
                hv_gap = abs(float(treated["hv_20"]) - float(control["hv_20"]))
                if return_gap > max_return_20d_distance or hv_gap > max_hv_20d_distance:
                    continue
                score = (
                    return_gap / max_return_20d_distance
                    + hv_gap / max_hv_20d_distance
                    + distance / max_match_distance_sessions
                )
                candidates.append((float(score), control_position))
            if not candidates:
                continue
            _, control_position = min(candidates, key=lambda item: (item[0], -item[1]))
            control = features.iloc[control_position]
            control_window = (
                pd.Timestamp(panel.index[control_position + 1]),
                pd.Timestamp(panel.index[control_position + 1 + forward_sessions]),
            )
            all_blueprints.append(
                {
                    "symbol": symbol,
                    "control_signal_date": pd.Timestamp(panel.index[control_position]),
                    "control_entry_date": control_window[0],
                    "control_exit_date": control_window[1],
                    "control_breakout_ratio": float(control["breakout_ratio"]),
                    "control_trend_distance": float(control["trend_distance"]),
                    "control_ret_20": float(control["ret_20"]),
                    "control_hv_20": float(control["hv_20"]),
                    "treated_signal_date": pd.Timestamp(panel.index[treated_position]),
                    "treated_entry_date": treated_window[0],
                    "treated_exit_date": treated_window[1],
                    "treated_breakout_ratio": float(treated["breakout_ratio"]),
                    "treated_trend_distance": float(treated["trend_distance"]),
                    "treated_ret_20": float(treated["ret_20"]),
                    "treated_hv_20": float(treated["hv_20"]),
                    "calendar_distance_sessions": int(treated_position - control_position),
                    "return_20d_match_distance": abs(
                        float(treated["ret_20"]) - float(control["ret_20"])
                    ),
                    "hv_20d_match_distance": abs(
                        float(treated["hv_20"]) - float(control["hv_20"])
                    ),
                }
            )
            used_controls.add(control_position)
            occupied.extend([control_window, treated_window])
    return sorted(
        all_blueprints,
        key=lambda row: (pd.Timestamp(row["treated_signal_date"]), str(row["symbol"])),
    )


def evaluate_train_partition(
    close_panel: pd.DataFrame,
    train_blueprints: list[dict[str, Any]],
    *,
    min_pairs: int = 80,
    min_symbols: int = 1,
    round_trip_cost_bps: float = 20.0,
    bootstrap_samples: int = 10_000,
    breakout_ratio_min: float = 1.02,
    control_breakout_ratio_low: float = 0.95,
    control_breakout_ratio_high: float = 1.00,
    max_match_distance_sessions: int = 126,
    max_return_20d_distance: float = 0.08,
    max_hv_20d_distance: float = 0.25,
) -> dict[str, Any]:
    """Evaluate frozen train pairs with chronology, costs, and uncertainty gate."""
    panel = _validate_panel(close_panel)
    if min_pairs < 1 or min_symbols < 1 or not train_blueprints:
        raise ValueError("non-empty train blueprints and positive pair/symbol minima are required")
    if not np.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0.0:
        raise ValueError("round-trip cost bps must be finite and non-negative")
    cost_fraction = float(round_trip_cost_bps) / 10_000.0
    rows: list[dict[str, Any]] = []
    occupied_by_symbol: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    controls_by_symbol: dict[str, set[pd.Timestamp]] = {}
    violations: list[str] = []

    for index, blueprint in enumerate(train_blueprints):
        symbol = str(blueprint["symbol"]).upper()
        if symbol not in panel.columns:
            raise ValueError(f"blueprint {index} symbol {symbol} is outside the panel")
        control_signal = pd.Timestamp(blueprint["control_signal_date"])
        control_entry = pd.Timestamp(blueprint["control_entry_date"])
        control_exit = pd.Timestamp(blueprint["control_exit_date"])
        treated_signal = pd.Timestamp(blueprint["treated_signal_date"])
        treated_entry = pd.Timestamp(blueprint["treated_entry_date"])
        treated_exit = pd.Timestamp(blueprint["treated_exit_date"])
        if not (
            control_signal < control_entry < control_exit < treated_signal
            and treated_signal < treated_entry < treated_exit
        ):
            violations.append(f"chronology:{index}")
        occupied = occupied_by_symbol.setdefault(symbol, [])
        windows = [(control_entry, control_exit), (treated_entry, treated_exit)]
        if any(_overlaps(window, occupied) for window in windows):
            violations.append(f"overlap:{index}")
        occupied.extend(windows)
        controls = controls_by_symbol.setdefault(symbol, set())
        if control_signal in controls:
            violations.append(f"control_reuse:{index}")
        controls.add(control_signal)
        if float(blueprint["treated_breakout_ratio"]) < breakout_ratio_min:
            violations.append(f"treated_breakout:{index}")
        control_ratio = float(blueprint["control_breakout_ratio"])
        if not control_breakout_ratio_low <= control_ratio <= control_breakout_ratio_high:
            violations.append(f"control_breakout:{index}")
        if int(blueprint["calendar_distance_sessions"]) > max_match_distance_sessions:
            violations.append(f"calendar_distance:{index}")
        if float(blueprint["return_20d_match_distance"]) > max_return_20d_distance:
            violations.append(f"return_distance:{index}")
        if float(blueprint["hv_20d_match_distance"]) > max_hv_20d_distance:
            violations.append(f"hv_distance:{index}")
        required_dates = {control_entry, control_exit, treated_entry, treated_exit}
        if not required_dates.issubset(set(panel.index)):
            raise ValueError(f"blueprint {index} dates are outside the close panel")
        treated_return = (
            float(panel.loc[treated_exit, symbol] / panel.loc[treated_entry, symbol] - 1.0)
            - cost_fraction
        )
        control_return = (
            float(panel.loc[control_exit, symbol] / panel.loc[control_entry, symbol] - 1.0)
            - cost_fraction
        )
        rows.append(
            {
                "symbol": symbol,
                "control_signal_date": str(control_signal.date()),
                "control_entry_date": str(control_entry.date()),
                "control_exit_date": str(control_exit.date()),
                "treated_signal_date": str(treated_signal.date()),
                "treated_entry_date": str(treated_entry.date()),
                "treated_exit_date": str(treated_exit.date()),
                "treated_return_after_cost": treated_return,
                "control_return_after_cost": control_return,
                "paired_excess_return": treated_return - control_return,
                "calendar_distance_sessions": int(blueprint["calendar_distance_sessions"]),
                "return_20d_match_distance": float(blueprint["return_20d_match_distance"]),
                "hv_20d_match_distance": float(blueprint["hv_20d_match_distance"]),
            }
        )

    treated = np.asarray([row["treated_return_after_cost"] for row in rows], dtype=float)
    control = np.asarray([row["control_return_after_cost"] for row in rows], dtype=float)
    excess = treated - control
    lower_bound = circular_block_bootstrap_lower_bound(
        excess,
        block_length=5,
        samples=bootstrap_samples,
        seed=20260715,
    )
    symbol_set = sorted({row["symbol"] for row in rows})
    gate_checks = {
        "minimum_train_pairs": len(rows) >= min_pairs,
        "minimum_symbol_breadth": len(symbol_set) >= min_symbols,
        "positive_treated_mean_after_cost": float(treated.mean()) > 0.0,
        "positive_paired_excess_mean": float(excess.mean()) > 0.0,
        "paired_excess_bootstrap_lb90_positive": lower_bound > 0.0,
        "zero_integrity_violations": not violations,
    }
    return {
        "n_pairs": len(rows),
        "round_trip_cost_bps": float(round_trip_cost_bps),
        "treated_mean_return_after_cost": float(treated.mean()),
        "control_mean_return_after_cost": float(control.mean()),
        "paired_excess_mean": float(excess.mean()),
        "paired_excess_median": float(np.median(excess)),
        "paired_excess_positive_frequency": float(np.mean(excess > 0.0)),
        "paired_excess_bootstrap_lb90": lower_bound,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length": 5,
        "symbols_with_pairs": symbol_set,
        "pairs_by_symbol": {
            symbol: sum(row["symbol"] == symbol for row in rows) for symbol in symbol_set
        },
        "integrity_violations": violations,
        "gate_checks": gate_checks,
        "gate_pass": bool(all(gate_checks.values())),
        "pairs": rows,
    }


def _empty_train_result(
    *, min_pairs: int, min_symbols: int, round_trip_cost_bps: float, bootstrap_samples: int
) -> dict[str, Any]:
    return {
        "n_pairs": 0,
        "round_trip_cost_bps": float(round_trip_cost_bps),
        "treated_mean_return_after_cost": None,
        "control_mean_return_after_cost": None,
        "paired_excess_mean": None,
        "paired_excess_median": None,
        "paired_excess_positive_frequency": None,
        "paired_excess_bootstrap_lb90": None,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length": 5,
        "symbols_with_pairs": [],
        "pairs_by_symbol": {},
        "integrity_violations": [],
        "gate_checks": {
            "minimum_train_pairs": 0 >= min_pairs,
            "minimum_symbol_breadth": 0 >= min_symbols,
            "positive_treated_mean_after_cost": False,
            "positive_paired_excess_mean": False,
            "paired_excess_bootstrap_lb90_positive": False,
            "zero_integrity_violations": True,
        },
        "gate_pass": False,
        "pairs": [],
    }


def run_lab_from_panel(
    close_panel: pd.DataFrame,
    *,
    symbols: list[str],
    provenance: dict[str, Any],
    train_fraction: float = 0.60,
    breakout_lookback_sessions: int = 20,
    breakout_ratio_min: float = 1.02,
    control_breakout_ratio_low: float = 0.95,
    control_breakout_ratio_high: float = 1.00,
    trend_lookback_sessions: int = 100,
    forward_sessions: int = 10,
    max_match_distance_sessions: int = 126,
    max_return_20d_distance: float = 0.08,
    max_hv_20d_distance: float = 0.25,
    min_train_pairs: int = 80,
    min_train_symbols: int = 6,
    round_trip_cost_bps: float = 20.0,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    """Run frozen F0 train test while preserving all holdout outcomes unread."""
    panel = _validate_panel(close_panel)
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if normalized != list(panel.columns) or len(normalized) != len(set(normalized)):
        raise ValueError("symbols must exactly match the ordered close-panel columns")
    if not 0.50 <= float(train_fraction) <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    blueprints = build_matched_blueprints(
        panel,
        breakout_lookback_sessions=breakout_lookback_sessions,
        breakout_ratio_min=breakout_ratio_min,
        control_breakout_ratio_low=control_breakout_ratio_low,
        control_breakout_ratio_high=control_breakout_ratio_high,
        trend_lookback_sessions=trend_lookback_sessions,
        forward_sessions=forward_sessions,
        max_match_distance_sessions=max_match_distance_sessions,
        max_return_20d_distance=max_return_20d_distance,
        max_hv_20d_distance=max_hv_20d_distance,
    )
    ordered = sorted(
        blueprints,
        key=lambda row: (pd.Timestamp(row["treated_signal_date"]), str(row["symbol"])),
    )
    split = int(len(ordered) * train_fraction)
    train = ordered[:split]
    holdout = ordered[split:]
    if train:
        train_result = evaluate_train_partition(
            panel,
            train,
            min_pairs=min_train_pairs,
            min_symbols=min_train_symbols,
            round_trip_cost_bps=round_trip_cost_bps,
            bootstrap_samples=bootstrap_samples,
            breakout_ratio_min=breakout_ratio_min,
            control_breakout_ratio_low=control_breakout_ratio_low,
            control_breakout_ratio_high=control_breakout_ratio_high,
            max_match_distance_sessions=max_match_distance_sessions,
            max_return_20d_distance=max_return_20d_distance,
            max_hv_20d_distance=max_hv_20d_distance,
        )
    else:
        train_result = _empty_train_result(
            min_pairs=min_train_pairs,
            min_symbols=min_train_symbols,
            round_trip_cost_bps=round_trip_cost_bps,
            bootstrap_samples=bootstrap_samples,
        )
    advanced = bool(train_result["gate_pass"])
    failed_checks = [name for name, passed in train_result["gate_checks"].items() if not passed]
    dominant_failure = None if advanced else (
        "no outcome-independent breakout/control pairs survived the frozen matching geometry"
        if not train
        else "frozen train gate failed: " + ", ".join(failed_checks)
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_UNDERLYING_DISCOVERY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": "MULTINAME_BREAKOUT_BULL_CALL_14D_V1",
        "mechanism_family": "TIME_SERIES_20D_BREAKOUT_CONTINUATION",
        "market_underlying": normalized,
        "forecast_type": "direction_up",
        "economic_mechanism": (
            "gradual information diffusion and trend-following demand may cause a close at least 2% "
            "above the prior completed 20-session high, while above a fully warmed SMA100, to retain "
            "positive ten-session drift versus earlier same-symbol near-high non-breakout controls"
        ),
        "candidate_or_family_scope": (
            "fixed liquid multi-name panel; next-session entry after a completed-bar 20-session "
            "breakout in positive SMA100 trend; ten-session hold; earlier same-symbol near-high "
            "controls matched on 20-session return and realized volatility"
        ),
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "falsifier": (
            f"on the chronological first {train_fraction:.0%} of frozen matched pairs, fewer than "
            f"{min_train_pairs} pairs or {min_train_symbols} represented symbols, non-positive "
            "treated mean after labeled 20-bps underlying round-trip sensitivity, non-positive "
            "paired excess, non-positive one-sided 90% five-pair-block bootstrap lower bound, or "
            "any chronology/match violation closes the exact family"
        ),
        "claim_scope": (
            "split/dividend-adjusted underlying closes only with a fixed ten-session outcome and "
            "labeled symmetric 20-bps underlying absolute-level sensitivity; because the same "
            "sensitivity is subtracted from treated and control returns, it does not stress paired "
            "excess or represent option execution costs; fixed present-day panel with "
            "survivorship/listing bias; train-only L0 discovery; no managed option path, option "
            "marks, option costs, fills, L1, capital seat, or paper eligibility"
        ),
        "regime_hypothesis": (
            "positive fully warmed SMA100 trend and a completed-bar breakout; stand aside in weak "
            "trend, absent breakout, or when the future option package cannot fit the one-lot bound"
        ),
        "entry_trigger": (
            "enter next session only after completed close >=1.02 times prior completed 20-session "
            "high and close above prior completed SMA100"
        ),
        "exit_rule": (
            "measured discovery outcome is the fixed ten-session underlying return; a future option "
            "expression may test earlier thesis invalidation, but no managed exit was simulated here"
        ),
        "management_rule": (
            "untested future option plan only: harvest at 50% of debit-spread maximum value; cut if "
            "close returns below the pre-breakout 20-session high; hard ten-session time stop; no "
            "same-bar re-entry"
        ),
        "horizon_alignment": (
            "the fixed ten-session underlying continuation outcome is only an approximate directional "
            "pre-screen for a later 14-DTE debit spread; it does not show that the option package "
            "captures the drift after theta, vega, bid/ask friction, or the proposed managed exits"
        ),
        "greek_exposures": {
            "intended": "positive delta and bounded positive gamma through a one-lot bull-call debit spread",
            "dangerous_unintended": (
                "long-vega exposure, theta decay if continuation stalls, and pin/liquidity/assignment "
                "risk not measured by this underlying-only train study"
            ),
        },
        "mispricing_claim": (
            "none yet; this wake tests directional continuation before any option-price or implied-volatility claim"
        ),
        "stand_aside_rule": (
            "no completed-bar 2% breakout, close not above fully warmed SMA100, insufficient matched "
            "train support, failed discovery gate, or future package loss/cost above the one-lot bound"
        ),
        "all_train_rows_are_inspected_development_data": True,
        "f2_or_l1_claim": False,
        "config": {
            "symbols": normalized,
            "breakout_lookback_sessions": breakout_lookback_sessions,
            "breakout_ratio_min": breakout_ratio_min,
            "control_breakout_ratio_bounds": [
                control_breakout_ratio_low,
                control_breakout_ratio_high,
            ],
            "trend_lookback_sessions": trend_lookback_sessions,
            "forward_sessions": forward_sessions,
            "train_fraction": train_fraction,
            "minimum_train_pairs": min_train_pairs,
            "minimum_train_symbols": min_train_symbols,
            "round_trip_cost_bps": round_trip_cost_bps,
            "max_match_distance_sessions": max_match_distance_sessions,
            "max_return_20d_distance": max_return_20d_distance,
            "max_hv_20d_distance": max_hv_20d_distance,
            "bootstrap_confidence": 0.90,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_block_length": 5,
            "controls_prior_only": True,
            "matched_without_replacement_per_symbol": True,
            "non_overlapping_pair_windows_per_symbol": True,
        },
        "data_provenance": provenance,
        "selection_diagnostics": {
            "matched_blueprints": len(ordered),
            "train_blueprints": len(train),
            "holdout_blueprints": len(holdout),
            "train_symbols": sorted({str(row["symbol"]) for row in train}),
            "holdout_symbols": sorted({str(row["symbol"]) for row in holdout}),
        },
        "population_validity": {
            "population_type": "fixed present-day liquid US equity panel",
            "population_pure": True,
            "population_pure_semantics": (
                "the frozen ordered panel was evaluated completely without row mixing; this does not "
                "mean the panel is survivorship-bias-free or generalizable"
            ),
            "bias_free": False,
            "ranking_complete": True,
            "survivorship_bias": True,
            "listing_bias": True,
            "generalization_allowed": False,
        },
        "train": train_result,
        "untouched_holdout": {
            "n_blueprints": len(holdout),
            "first_treated_signal_date": (
                str(pd.Timestamp(holdout[0]["treated_signal_date"]).date()) if holdout else None
            ),
            "last_treated_exit_date": (
                str(pd.Timestamp(holdout[-1]["treated_exit_date"]).date()) if holdout else None
            ),
            "outcome_metrics_read": False,
            "simulation_run": False,
            "required_non_gating_diagnostics_if_opened": [
                "per-symbol treated/control/paired means and pair counts",
                "leave-one-symbol-out pooled paired-excess bootstrap lower bounds",
                "chronological tertile paired means and bootstrap lower bounds",
            ],
            "diagnostic_role": (
                "mandatory concentration reporting beside the unchanged pooled holdout gate; these "
                "diagnostics must not become a post-hoc second gate on already-inspected train rows"
            ),
        },
        "option_stage": {
            "status": "NOT_RUN_PENDING_UNTOUCHED_HOLDOUT" if advanced else "NOT_RUN_TRAIN_GATE_FAILED",
            "pricing_run": False,
            "pricing_calls": 0,
            "planned_structure": "bull_call_debit_spread",
            "planned_dte": 14,
            "planned_width_usd": 1.0,
            "option_mark_provenance": None,
        },
        "structure": "conditional_bull_call_debit_spread_not_yet_priced",
        "capital_fit_usd": 100.0,
        "one_lot_max_loss_usd": 100.0,
        "max_loss_usd": 100.0,
        "max_lots": 1,
        "portfolio_overlap_rule": (
            "one open risk unit across highly correlated mega-cap/high-beta breakout candidates; no concurrent same-cluster entries"
        ),
        "capital_basis": (
            "structural $1-wide one-lot debit-spread upper bound before closing friction; not an observed or simulated paid debit"
        ),
        "bar_claimed": "discovery",
        "confidence_stage": "F1_TRAIN/L0" if advanced else "F0_MECHANISM/L0",
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "decision": (
            "ADVANCE_TIME_SERIES_BREAKOUT_CONTINUATION_TO_F1_TRAIN"
            if advanced
            else "CLOSE_TIME_SERIES_BREAKOUT_CONTINUATION_TRAIN_FAMILY"
        ),
        "closed_family": None if advanced else "TIME_SERIES_20D_BREAKOUT_CONTINUATION",
        "dominant_failure_mechanism": dominant_failure,
        "registration_eligible": False,
        "authority": "research only; no registry, paper, shadow, funding, broker, arm, or live authority",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2026-07-15")
    parser.add_argument("--cache-dir", default=".cache/platform/breakout_continuation")
    parser.add_argument("--train-fraction", type=float, default=0.60)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    histories: dict[str, pd.Series] = {}
    source_meta: dict[str, Any] = {}
    for symbol in symbols:
        history, meta = load_adjusted_history(
            symbol,
            cache_dir=Path(args.cache_dir),
            start=args.start,
            end=args.end,
        )
        histories[symbol] = history
        source_meta[symbol] = meta
    panel = assemble_close_panel(histories, symbols=symbols, min_common_rows=2_000)
    provenance = {
        "sources": source_meta,
        "common_panel": {
            "rows": int(len(panel)),
            "start": str(panel.index[0].date()),
            "end": str(panel.index[-1].date()),
            "join": "inner join on trading dates; no forward fill",
        },
    }
    payload = run_lab_from_panel(
        panel,
        symbols=symbols,
        provenance=provenance,
        train_fraction=args.train_fraction,
        bootstrap_samples=args.bootstrap_samples,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_id": payload["candidate_id"],
                "strategy_outcome": payload["strategy_outcome"],
                "decision": payload["decision"],
                "funnel_stage_after": payload["funnel_stage_after"],
                "train_gate_pass": payload["train"]["gate_pass"],
                "train_n": payload["train"]["n_pairs"],
                "paired_excess_mean": payload["train"]["paired_excess_mean"],
                "paired_excess_bootstrap_lb90": payload["train"][
                    "paired_excess_bootstrap_lb90"
                ],
                "out": str(out),
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Train-only broad-sector breadth-thrust SPY discovery lab.

BUILD/L0 only. The final chronological 40% remains outcome-unread and option
pricing is forbidden in this stage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from scripts.low_hv_cross_section_train_lab import assemble_close_panel, load_adjusted_history
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from low_hv_cross_section_train_lab import (  # type: ignore[no-redef]
        assemble_close_panel,
        load_adjusted_history,
    )

SECTOR_SYMBOLS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
DEFAULT_SYMBOLS = ["SPY", *SECTOR_SYMBOLS]


def _validate_panel(close_panel: pd.DataFrame) -> pd.DataFrame:
    if close_panel.empty:
        raise ValueError("close panel must be non-empty")
    panel = close_panel.copy()
    panel.index = pd.DatetimeIndex(pd.to_datetime(panel.index)).tz_localize(None).normalize()
    panel.columns = [str(column).strip().upper() for column in panel.columns]
    if list(panel.columns) != DEFAULT_SYMBOLS:
        raise ValueError("close panel must exactly match the frozen SPY plus eleven-sector order")
    panel = panel.apply(pd.to_numeric, errors="coerce")
    values = panel.to_numpy(dtype=float)
    if (
        not panel.index.is_unique
        or not panel.index.is_monotonic_increasing
        or not np.isfinite(values).all()
        or (values <= 0.0).any()
    ):
        raise ValueError("close panel must be unique, increasing, finite, and positive")
    return panel


def _overlaps(
    window: tuple[pd.Timestamp, pd.Timestamp],
    occupied: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    start, end = window
    return any(not (end < prior_start or start > prior_end) for prior_start, prior_end in occupied)


def build_breadth_thrust_blueprints(
    close_panel: pd.DataFrame,
    *,
    breadth_lookback_sessions: int = 50,
    breadth_change_sessions: int = 5,
    trend_lookback_sessions: int = 100,
    momentum_lookback_sessions: int = 60,
    forward_sessions: int = 10,
    breadth_min: float = 9.0 / 11.0,
    breadth_change_min: float = 3.0 / 11.0,
    control_breadth_change_max: float = 1.0 / 11.0,
    max_match_distance_sessions: int = 504,
    max_return_60d_distance: float = 0.15,
    max_hv_ratio_distance: float = 0.50,
    max_breadth_distance: float = 2.0 / 11.0,
) -> list[dict[str, Any]]:
    """Freeze prior-only high-breadth controls without reading forward outcomes."""
    panel = _validate_panel(close_panel)
    if min(
        breadth_lookback_sessions,
        breadth_change_sessions,
        trend_lookback_sessions,
        momentum_lookback_sessions,
        forward_sessions,
        max_match_distance_sessions,
    ) < 1:
        raise ValueError("lookbacks, horizon, and match distance must be positive")
    if not 0.0 <= breadth_min <= 1.0:
        raise ValueError("breadth minimum must be a fraction")
    if not -1.0 <= breadth_change_min <= 1.0 or not -1.0 <= control_breadth_change_max <= 1.0:
        raise ValueError("breadth-change gates must be fractions")
    if min(max_return_60d_distance, max_hv_ratio_distance, max_breadth_distance) <= 0.0:
        raise ValueError("matching distances must be positive")

    sectors = panel[SECTOR_SYMBOLS]
    sector_sma = sectors.rolling(
        breadth_lookback_sessions,
        min_periods=breadth_lookback_sessions,
    ).mean()
    breadth = (sectors > sector_sma).sum(axis=1).astype(float) / float(len(SECTOR_SYMBOLS))
    breadth_change = breadth - breadth.shift(breadth_change_sessions)
    spy = panel["SPY"]
    spy_sma = spy.rolling(trend_lookback_sessions, min_periods=trend_lookback_sessions).mean()
    ret_60 = spy / spy.shift(momentum_lookback_sessions) - 1.0
    log_return = np.log(spy / spy.shift(1))
    hv_20 = log_return.rolling(20, min_periods=20).std() * np.sqrt(252.0)
    hv_60 = log_return.rolling(60, min_periods=60).std() * np.sqrt(252.0)
    features = pd.DataFrame(
        {
            "breadth": breadth,
            "breadth_change": breadth_change,
            "spy_ret_60": ret_60,
            "spy_hv_ratio": hv_20 / hv_60,
            "regime": (spy > spy_sma) & (ret_60 > 0.0),
        },
        index=panel.index,
    )
    last_signal_position = len(panel) - forward_sessions - 2
    eligible = [
        position
        for position in range(len(panel))
        if position <= last_signal_position
        and bool(features.iloc[position]["regime"])
        and np.isfinite(
            features.iloc[position][["breadth", "breadth_change", "spy_ret_60", "spy_hv_ratio"]]
            .to_numpy(dtype=float)
        ).all()
        and float(features.iloc[position]["breadth"]) >= breadth_min
    ]
    treated_positions = [
        position
        for position in eligible
        if float(features.iloc[position]["breadth_change"]) >= breadth_change_min
    ]
    control_positions = [
        position
        for position in eligible
        if float(features.iloc[position]["breadth_change"]) <= control_breadth_change_max
    ]

    rows: list[dict[str, Any]] = []
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
        matches: list[tuple[float, int]] = []
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
            ret_gap = abs(float(treated["spy_ret_60"]) - float(control["spy_ret_60"]))
            hv_gap = abs(float(treated["spy_hv_ratio"]) - float(control["spy_hv_ratio"]))
            breadth_gap = abs(float(treated["breadth"]) - float(control["breadth"]))
            if (
                ret_gap > max_return_60d_distance
                or hv_gap > max_hv_ratio_distance
                or breadth_gap > max_breadth_distance
            ):
                continue
            score = (
                ret_gap / max_return_60d_distance
                + hv_gap / max_hv_ratio_distance
                + breadth_gap / max_breadth_distance
                + distance / max_match_distance_sessions
            )
            matches.append((float(score), control_position))
        if not matches:
            continue
        _, control_position = min(matches, key=lambda item: (item[0], -item[1]))
        control = features.iloc[control_position]
        control_window = (
            pd.Timestamp(panel.index[control_position + 1]),
            pd.Timestamp(panel.index[control_position + 1 + forward_sessions]),
        )
        rows.append(
            {
                "control_signal_date": pd.Timestamp(panel.index[control_position]),
                "control_feature_max_date": pd.Timestamp(panel.index[control_position]),
                "control_entry_date": control_window[0],
                "control_exit_date": control_window[1],
                "control_breadth": float(control["breadth"]),
                "control_breadth_change": float(control["breadth_change"]),
                "control_spy_ret_60": float(control["spy_ret_60"]),
                "control_spy_hv_ratio": float(control["spy_hv_ratio"]),
                "treated_signal_date": pd.Timestamp(panel.index[treated_position]),
                "treated_feature_max_date": pd.Timestamp(panel.index[treated_position]),
                "treated_entry_date": treated_window[0],
                "treated_exit_date": treated_window[1],
                "treated_breadth": float(treated["breadth"]),
                "treated_breadth_change": float(treated["breadth_change"]),
                "treated_spy_ret_60": float(treated["spy_ret_60"]),
                "treated_spy_hv_ratio": float(treated["spy_hv_ratio"]),
                "calendar_distance_sessions": int(treated_position - control_position),
                "return_60d_match_distance": abs(
                    float(treated["spy_ret_60"]) - float(control["spy_ret_60"])
                ),
                "hv_ratio_match_distance": abs(
                    float(treated["spy_hv_ratio"]) - float(control["spy_hv_ratio"])
                ),
                "breadth_match_distance": abs(
                    float(treated["breadth"]) - float(control["breadth"])
                ),
            }
        )
        used_controls.add(control_position)
        occupied.extend([control_window, treated_window])
    return sorted(rows, key=lambda row: pd.Timestamp(row["treated_signal_date"]))


def _date_block_lower_bound(
    values: np.ndarray,
    *,
    samples: int,
    block_length: int = 3,
    confidence: float = 0.90,
    seed: int = 20260715,
) -> float:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or not len(vector) or not np.isfinite(vector).all():
        raise ValueError("date-block bootstrap input must be a non-empty finite vector")
    if samples < 100 or block_length < 1 or not 0.5 < confidence < 1.0:
        raise ValueError("date-block bootstrap configuration is invalid")
    block = min(block_length, len(vector))
    n_blocks = int(np.ceil(len(vector) / block))
    offsets = np.arange(block)
    rng = np.random.default_rng(seed)
    estimates = np.empty(samples, dtype=float)
    for sample in range(samples):
        starts = rng.integers(0, len(vector), size=n_blocks)
        draw = np.concatenate([vector[(start + offsets) % len(vector)] for start in starts])[
            : len(vector)
        ]
        estimates[sample] = float(draw.mean())
    return float(np.quantile(estimates, 1.0 - confidence))


def _worst_decile_mean(values: np.ndarray) -> float:
    vector = np.asarray(values, dtype=float)
    if not len(vector) or not np.isfinite(vector).all():
        raise ValueError("worst-decile input must be non-empty and finite")
    count = max(1, int(np.ceil(len(vector) * 0.10)))
    return float(np.sort(vector)[:count].mean())


def _distance_summary(values: list[float | int]) -> dict[str, float | int]:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or not len(vector) or not np.isfinite(vector).all():
        raise ValueError("match-distance summary requires non-empty finite values")
    return {
        "count": int(len(vector)),
        "min": float(vector.min()),
        "median": float(np.median(vector)),
        "max": float(vector.max()),
    }


def evaluate_train_partition(
    close_panel: pd.DataFrame,
    train_blueprints: list[dict[str, Any]],
    *,
    min_pairs: int = 20,
    min_signal_years: int = 8,
    round_trip_cost_bps: float = 10.0,
    min_treated_mean_return: float = 0.005,
    min_treated_positive_frequency: float = 0.55,
    min_paired_excess_mean: float = 0.0025,
    minimum_tail_return: float = -0.03,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    """Evaluate frozen train outcomes under absolute and matched-control gates."""
    panel = _validate_panel(close_panel)
    if not train_blueprints or min(min_pairs, min_signal_years) < 1:
        raise ValueError("non-empty blueprints and positive density gates are required")
    if not np.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0.0:
        raise ValueError("round-trip cost must be finite and non-negative")
    cost = round_trip_cost_bps / 10_000.0
    rows: list[dict[str, Any]] = []
    integrity_violations: list[str] = []
    occupied: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    used_controls: set[pd.Timestamp] = set()

    for index, blueprint in enumerate(train_blueprints):
        control_signal = pd.Timestamp(blueprint["control_signal_date"])
        control_feature_max = pd.Timestamp(blueprint["control_feature_max_date"])
        control_entry = pd.Timestamp(blueprint["control_entry_date"])
        control_exit = pd.Timestamp(blueprint["control_exit_date"])
        treated_signal = pd.Timestamp(blueprint["treated_signal_date"])
        treated_feature_max = pd.Timestamp(blueprint["treated_feature_max_date"])
        treated_entry = pd.Timestamp(blueprint["treated_entry_date"])
        treated_exit = pd.Timestamp(blueprint["treated_exit_date"])
        if not (
            control_feature_max == control_signal < control_entry < control_exit < treated_signal
            and treated_feature_max == treated_signal < treated_entry < treated_exit
        ):
            integrity_violations.append(f"chronology:{index}")
        windows = [(control_entry, control_exit), (treated_entry, treated_exit)]
        if any(_overlaps(window, occupied) for window in windows):
            integrity_violations.append(f"overlap:{index}")
        occupied.extend(windows)
        if control_signal in used_controls:
            integrity_violations.append(f"control_reuse:{index}")
        used_controls.add(control_signal)
        if float(blueprint["treated_breadth"]) < 9.0 / 11.0:
            integrity_violations.append(f"treated_breadth:{index}")
        if float(blueprint["treated_breadth_change"]) < 3.0 / 11.0:
            integrity_violations.append(f"treated_thrust:{index}")
        if float(blueprint["control_breadth"]) < 9.0 / 11.0:
            integrity_violations.append(f"control_breadth:{index}")
        if float(blueprint["control_breadth_change"]) > 1.0 / 11.0:
            integrity_violations.append(f"control_non_thrust:{index}")
        required = {control_entry, control_exit, treated_entry, treated_exit}
        if not required.issubset(set(panel.index)):
            raise ValueError(f"blueprint {index} dates are outside the close panel")
        control_return = float(panel.loc[control_exit, "SPY"] / panel.loc[control_entry, "SPY"] - 1.0 - cost)
        treated_return = float(panel.loc[treated_exit, "SPY"] / panel.loc[treated_entry, "SPY"] - 1.0 - cost)
        if not np.isfinite([control_return, treated_return]).all():
            raise ValueError("outcome return is nonfinite")
        rows.append(
            {
                "control_signal_date": str(control_signal.date()),
                "control_entry_date": str(control_entry.date()),
                "control_exit_date": str(control_exit.date()),
                "treated_signal_date": str(treated_signal.date()),
                "treated_entry_date": str(treated_entry.date()),
                "treated_exit_date": str(treated_exit.date()),
                "control_return_after_cost": control_return,
                "treated_return_after_cost": treated_return,
                "paired_excess_return": treated_return - control_return,
            }
        )

    treated = np.asarray([row["treated_return_after_cost"] for row in rows], dtype=float)
    control = np.asarray([row["control_return_after_cost"] for row in rows], dtype=float)
    excess = treated - control
    lower_bound = _date_block_lower_bound(excess, samples=bootstrap_samples)
    signal_years = sorted({pd.Timestamp(row["treated_signal_date"]).year for row in rows})
    signal_year_counts = {
        str(year): sum(pd.Timestamp(row["treated_signal_date"]).year == year for row in rows)
        for year in signal_years
    }
    treated_mean = float(treated.mean())
    control_mean = float(control.mean())
    paired_mean = float(excess.mean())
    positive_frequency = float(np.mean(treated > 0.0))
    tail = _worst_decile_mean(treated)
    worst_decile_n = max(1, int(np.ceil(len(treated) * 0.10)))
    match_quality = {
        field: _distance_summary([blueprint[field] for blueprint in train_blueprints])
        for field in (
            "calendar_distance_sessions",
            "breadth_match_distance",
            "return_60d_match_distance",
            "hv_ratio_match_distance",
        )
    }
    gate_checks = {
        "minimum_train_pairs": len(rows) >= min_pairs,
        "minimum_signal_years": len(signal_years) >= min_signal_years,
        "treated_mean_return_above_0_50pct": treated_mean > min_treated_mean_return,
        "treated_positive_frequency_at_least_55pct": positive_frequency >= min_treated_positive_frequency,
        "paired_excess_mean_at_least_0_25pct": paired_mean >= min_paired_excess_mean,
        "paired_excess_bootstrap_lb90_positive": lower_bound > 0.0,
        "treated_worst_decile_at_least_negative_3pct": tail >= minimum_tail_return,
        "high_breadth_non_thrust_control_is_weaker": treated_mean > control_mean,
        "zero_integrity_violations": not integrity_violations,
    }
    return {
        "n_pairs": len(rows),
        "signal_years": signal_years,
        "signal_year_counts": signal_year_counts,
        "round_trip_underlying_cost_bps": float(round_trip_cost_bps),
        "treated_mean_return_after_cost": treated_mean,
        "control_mean_return_after_cost": control_mean,
        "treated_positive_frequency_after_cost": positive_frequency,
        "paired_excess_mean": paired_mean,
        "paired_excess_median": float(np.median(excess)),
        "paired_excess_positive_frequency": float(np.mean(excess > 0.0)),
        "paired_excess_bootstrap_lb90": lower_bound,
        "treated_worst_decile_return_after_cost": tail,
        "worst_decile_n": worst_decile_n,
        "match_quality": match_quality,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length_signal_dates": 3,
        "integrity_violations": integrity_violations,
        "gate_checks": gate_checks,
        "gate_pass": bool(all(gate_checks.values())),
        "pairs": rows,
    }


def _split_blueprints(
    blueprints: list[dict[str, Any]], *, train_fraction: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.50 <= train_fraction <= 0.80:
        raise ValueError("train fraction must be between 0.50 and 0.80")
    if len(blueprints) < 2:
        raise ValueError("at least two frozen pairs are required")
    ordered = sorted(blueprints, key=lambda row: pd.Timestamp(row["treated_signal_date"]))
    split = int(len(ordered) * train_fraction)
    train, holdout = ordered[:split], ordered[split:]
    if not train or not holdout:
        raise ValueError("train and holdout must both be non-empty")
    if pd.Timestamp(train[-1]["treated_signal_date"]) >= pd.Timestamp(
        holdout[0]["treated_signal_date"]
    ):
        raise ValueError("train and holdout must be strictly chronological")
    return train, holdout


def _holdout_identity(blueprints: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        {
            "control_signal_date": str(pd.Timestamp(row["control_signal_date"]).date()),
            "control_entry_date": str(pd.Timestamp(row["control_entry_date"]).date()),
            "control_exit_date": str(pd.Timestamp(row["control_exit_date"]).date()),
            "treated_signal_date": str(pd.Timestamp(row["treated_signal_date"]).date()),
            "treated_entry_date": str(pd.Timestamp(row["treated_entry_date"]).date()),
            "treated_exit_date": str(pd.Timestamp(row["treated_exit_date"]).date()),
        }
        for row in blueprints
    ]
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "n_frozen_pairs": len(rows),
        "first_treated_signal_date": rows[0]["treated_signal_date"],
        "last_treated_signal_date": rows[-1]["treated_signal_date"],
        "last_treated_exit_date": rows[-1]["treated_exit_date"],
        "identity_sha256": hashlib.sha256(encoded).hexdigest(),
        "identity_fields": list(rows[0]),
        "outcome_metrics_read": False,
        "simulation_run": False,
    }


def _dominant_failure(failed_gates: list[str]) -> str:
    if any("paired_excess" in gate for gate in failed_gates):
        return (
            "mechanism-specific paired_excess failure: breadth thrust did not beat the prior-only "
            "same-regime high-breadth non-thrust control under the frozen magnitude/uncertainty gates"
        )
    if failed_gates:
        return "frozen train gate failure(s): " + ", ".join(failed_gates)
    return "none; every frozen train gate passed"


def run_lab_from_panel(
    close_panel: pd.DataFrame,
    *,
    provenance: dict[str, Any],
    frozen_blueprints: list[dict[str, Any]] | None = None,
    train_fraction: float = 0.60,
    min_pairs: int = 20,
    min_signal_years: int = 8,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    panel = _validate_panel(close_panel)
    blueprints = (
        build_breadth_thrust_blueprints(panel)
        if frozen_blueprints is None
        else list(frozen_blueprints)
    )
    train, holdout = _split_blueprints(blueprints, train_fraction=train_fraction)
    train_result = evaluate_train_partition(
        panel,
        train,
        min_pairs=min_pairs,
        min_signal_years=min_signal_years,
        bootstrap_samples=bootstrap_samples,
    )
    advanced = bool(train_result["gate_pass"])
    failed_gates = [
        name for name, passed in train_result["gate_checks"].items() if not passed
    ]
    common_panel_start = str(panel.index[0])[:10]
    limiting_listings = [
        symbol
        for symbol, source in provenance.items()
        if isinstance(source, dict) and str(source.get("start") or "")[:10] == common_panel_start
    ]
    limiting_listing = limiting_listings[0] if len(limiting_listings) == 1 else None
    history_floor = (
        f"{limiting_listing or 'latest-listed panel component'} limits the fixed present-day panel "
        f"to {common_panel_start}; {len(train_result['signal_years'])} train signal years are "
        "non-generalizing density context and may not be repaired post hoc by dropping a panel "
        "component or loosening the predeclared minimum-year gate"
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_UNDERLYING_DISCOVERY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": "BROAD_SECTOR_BREADTH_THRUST_SPY_BULL_CALL_21D_V1",
        "mechanism_family": "BROAD_SECTOR_BREADTH_THRUST_FORWARD_DRIFT",
        "novelty_key": (
            "direction_up|sector_breadth_thrust_50d_delta5d|spy|"
            "spy_sma100_positive60d|10session|prior_high_breadth_non_thrust_control|"
            "bull_call_debit_spread_21d_2wide_planned"
        ),
        "economic_mechanism": (
            "rapid expansion from narrow to broad sector participation inside a positive SPY trend "
            "reflects distributed institutional demand and slow position diffusion that should persist "
            "for ten sessions beyond high-breadth non-thrust controls"
        ),
        "forecast_type": "direction_up",
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "claim_scope": (
            "adjusted daily underlying closes only; fixed present-day SPY/sector ETF panel; train-only "
            "L0 discovery; no option marks, IV, skew, debit, fill, F2, L1, capital-seat, or paper claim"
        ),
        "f2_or_l1_claim": False,
        "f2_claim": False,
        "l1_or_capital_seat_claim": False,
        "capital_seat_claim": False,
        "all_train_rows_are_inspected_development_data": True,
        "falsifier": (
            "fewer than 20 train pairs or eight years; chronology/overlap/reuse failure; treated mean "
            "after 10 bps <=0.50%; positive frequency <55%; paired excess <0.25%; paired-excess "
            "date-block LB90 <=0; worst decile <-3%; or high-breadth non-thrust control equal/better"
        ),
        "config": {
            "symbols": DEFAULT_SYMBOLS,
            "start": "2010-01-01",
            "end_exclusive": "2026-07-16",
            "train_fraction": train_fraction,
            "breadth_lookback_sessions": 50,
            "breadth_change_sessions": 5,
            "breadth_min": 9.0 / 11.0,
            "breadth_change_min": 3.0 / 11.0,
            "control_breadth_change_max": 1.0 / 11.0,
            "trend_lookback_sessions": 100,
            "momentum_lookback_sessions": 60,
            "forward_sessions": 10,
            "max_match_distance_sessions": 504,
            "max_return_60d_distance": 0.15,
            "max_hv_ratio_distance": 0.50,
            "max_breadth_distance": 2.0 / 11.0,
            "minimum_train_pairs": min_pairs,
            "minimum_signal_years": min_signal_years,
            "round_trip_underlying_cost_bps": 10.0,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_block_length_signal_dates": 3,
        },
        "layered_edge_stack": {
            "market_underlying": "SPY with fixed eleven-sector breadth panel",
            "forecast_type": "direction_up over next ten completed sessions",
            "economic_mechanism": "broad participation acceleration / slow demand diffusion",
            "option_structure": "future conditional one-lot 18-24 DTE $2-wide SPY bull call debit spread",
            "intended_greeks": ["positive_delta", "positive_gamma", "bounded_negative_theta"],
            "dangerous_greeks_and_exposures": [
                "negative_theta_if_drift_stalls",
                "overpaying_implied_volatility_after_rally",
                "capped_upside",
                "short_call_assignment_and_expiration_handling",
            ],
            "regime_envelope": "completed SPY close above SMA100 and positive completed 60-session return",
            "entry_trigger": "completed sector breadth >=9/11 and five-session breadth expansion >=3/11; next completed close entry",
            "exit_management": "future plan: +50%/-50% debit, ten sessions, five DTE, SMA100 break, or assignment guard; no roll",
            "capital_fit_usd": 200.0,
            "max_loss_usd": 200.0,
            "max_lots": 1,
            "portfolio_overlap": "no concurrent SPY/QQQ/IWM or sector-option positive-delta Agentic risk",
            "evidence_falsifier": "frozen train gates above; holdout sealed",
            "confidence_stage": "F1_TRAIN" if advanced else "F0_MECHANISM_CLOSED",
            "stand_aside": "any trend, thrust, option debit/liquidity, event, max-loss, or overlap gate failure",
        },
        "provenance": provenance,
        "population_purity": {
            "panel": DEFAULT_SYMBOLS,
            "join": "inner join; no forward fill",
            "common_panel_start_date": common_panel_start,
            "limiting_listing": limiting_listing,
            "present_day_survivorship_bias": True,
            "optionability_not_historically_reconstructed": True,
        },
        "train": train_result,
        "holdout": _holdout_identity(holdout),
        "failed_gates": failed_gates,
        "dominant_failure_mechanism": _dominant_failure(failed_gates),
        "search_information": (
            "new train-only broad-participation mechanism decision with prior-only high-breadth "
            "non-thrust specificity control and sealed holdout"
        ),
        "strategy_advancement": advanced,
        "strategy_advancement_summary": (
            "advanced F0_MECHANISM -> F1_TRAIN under the discovery bar"
            if advanced
            else "none; exact mechanism family closed at F0"
        ),
        "quarantine": {
            "enabled": not advanced,
            "scope": ["exact_family", "same_panel_retunes"],
            "nearby_same_panel_retunes": [
                "breadth thresholds near 9/11, including 8/11 and 10/11",
                "five-session thrust threshold near +3/11",
                "non-thrust control band near <=1/11",
                "forward horizons from 5 through 15 sessions on the same thrust definition",
                "SMA50 sector or SMA100 SPY lookback nudges",
                "the same novelty class without a materially new control design",
            ],
            "reopen_condition": (
                "a materially new economic mechanism or evidence class; train-inspected knob polish is forbidden"
            ),
        },
        "methodology_boundaries": {
            "chronology": "features through completed signal close; entry at next completed close",
            "control": "prior-only; control outcome ends before treated signal; one-to-one no reuse",
            "matching": (
                "match distances are serialized in train.match_quality; calendar matches can be coarse and "
                "must not be described as tight local controls"
            ),
            "dependence": "circular three-signal-date block bootstrap of complete paired-excess rows",
            "history_floor": history_floor,
            "tail": "worst-decile gate is predeclared; train tail estimate is thin and reports worst_decile_n",
            "horizon_option_alignment": (
                "ten-session underlying drift with a planned ten-session management exit does not validate "
                "the full 18-24 DTE option path, IV crush, debit fills, or early-exit economics"
            ),
            "observed_option_marks": False,
            "proxy_option_marks": False,
            "holdout_outcomes_read": False,
            "l1_or_paper_eligibility": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=".cache/platform/sector_breadth_thrust_train_2026-07-15T2254.json",
    )
    parser.add_argument("--cache-dir", default=".cache/platform/sector_breadth_thrust")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    histories: dict[str, pd.Series] = {}
    provenance: dict[str, Any] = {}
    for symbol in DEFAULT_SYMBOLS:
        history, source = load_adjusted_history(
            symbol,
            cache_dir=cache_dir,
            start="2010-01-01",
            end="2026-07-16",
        )
        histories[symbol] = history
        provenance[symbol] = source
    panel = assemble_close_panel(
        histories,
        symbols=DEFAULT_SYMBOLS,
        min_common_rows=1_500,
    )
    payload = run_lab_from_panel(
        panel,
        provenance=provenance,
        bootstrap_samples=args.bootstrap_samples,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidate_id": payload["candidate_id"],
                "strategy_outcome": payload["strategy_outcome"],
                "n_pairs": payload["train"]["n_pairs"],
                "failed_gates": payload["failed_gates"],
                "out": str(out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

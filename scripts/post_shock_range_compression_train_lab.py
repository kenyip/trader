#!/usr/bin/env python3
"""Train-only post-shock range-compression discovery lab.

BUILD/L0 only. The script tests an underlying range forecast before any option
pricing and preserves the chronological final 40% of matched blueprints unread.
"""
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


DEFAULT_SYMBOLS = ["AAPL", "AMD", "META", "GOOGL", "NVDA", "AVGO"]
CANDIDATE_ID = "POST_SHOCK_RANGE_COMPRESSION_IRON_BUTTERFLY_21D_V1"
FAMILY_ID = "POST_SHOCK_RANGE_COMPRESSION_MATCHED_CONTROL"


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
    shock_return_min: float = 0.02,
    hv_ratio_min: float = 1.20,
    control_abs_return_max: float = 0.005,
    sma20_distance_max: float = 0.05,
    forward_sessions: int = 5,
    max_match_distance_sessions: int = 252,
    max_return_20d_distance: float = 0.10,
    max_hv_ratio_distance: float = 0.50,
    max_sma20_distance_gap: float = 0.05,
) -> list[dict[str, Any]]:
    """Match completed shock bars to earlier same-symbol neutral high-HV controls."""
    panel = _validate_panel(close_panel)
    if min(shock_return_min, hv_ratio_min, forward_sessions) <= 0:
        raise ValueError("shock, volatility ratio, and forward horizon must be positive")
    if not 0.0 <= control_abs_return_max < shock_return_min:
        raise ValueError("control return bound must be non-negative and below shock threshold")
    if sma20_distance_max <= 0.0 or max_match_distance_sessions <= forward_sessions:
        raise ValueError("SMA and calendar bounds must be positive")
    if min(max_return_20d_distance, max_hv_ratio_distance, max_sma20_distance_gap) <= 0.0:
        raise ValueError("matching-distance bounds must be positive")

    all_blueprints: list[dict[str, Any]] = []
    for symbol in panel.columns:
        close = panel[symbol]
        ret_1 = close / close.shift(1) - 1.0
        ret_20 = close / close.shift(20) - 1.0
        log_return = np.log(close / close.shift(1))
        hv_20 = log_return.rolling(20, min_periods=20).std() * np.sqrt(252.0)
        hv_60 = log_return.rolling(60, min_periods=60).std() * np.sqrt(252.0)
        prior_sma_20 = close.shift(1).rolling(20, min_periods=20).mean()
        features = pd.DataFrame(
            {
                "abs_ret_1": ret_1.abs(),
                "ret_20": ret_20,
                "hv_ratio": hv_20 / hv_60,
                "sma20_distance": close / prior_sma_20 - 1.0,
            },
            index=panel.index,
        )
        last_signal_position = len(panel) - forward_sessions - 2
        eligible = [
            position
            for position in range(len(panel))
            if position <= last_signal_position
            and np.isfinite(features.iloc[position].to_numpy(dtype=float)).all()
            and abs(float(features.iloc[position]["sma20_distance"])) <= sma20_distance_max
            and float(features.iloc[position]["hv_ratio"]) >= hv_ratio_min
        ]
        treated_positions = [
            position
            for position in eligible
            if float(features.iloc[position]["abs_ret_1"]) >= shock_return_min
        ]
        control_positions = [
            position
            for position in eligible
            if float(features.iloc[position]["abs_ret_1"]) <= control_abs_return_max
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
                hv_gap = abs(float(treated["hv_ratio"]) - float(control["hv_ratio"]))
                sma_gap = abs(
                    float(treated["sma20_distance"]) - float(control["sma20_distance"])
                )
                if (
                    return_gap > max_return_20d_distance
                    or hv_gap > max_hv_ratio_distance
                    or sma_gap > max_sma20_distance_gap
                ):
                    continue
                score = (
                    return_gap / max_return_20d_distance
                    + hv_gap / max_hv_ratio_distance
                    + sma_gap / max_sma20_distance_gap
                    + distance / max_match_distance_sessions
                )
                candidates.append((float(score), control_position))
            if not candidates:
                continue
            _, control_position = min(candidates, key=lambda item: (item[0], -item[1]))
            control = features.iloc[control_position]
            return_gap = abs(float(treated["ret_20"]) - float(control["ret_20"]))
            hv_gap = abs(float(treated["hv_ratio"]) - float(control["hv_ratio"]))
            sma_gap = abs(
                float(treated["sma20_distance"]) - float(control["sma20_distance"])
            )
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
                    "control_abs_ret_1d": float(control["abs_ret_1"]),
                    "control_ret_20": float(control["ret_20"]),
                    "control_hv_ratio": float(control["hv_ratio"]),
                    "control_sma20_distance": float(control["sma20_distance"]),
                    "treated_signal_date": pd.Timestamp(panel.index[treated_position]),
                    "treated_entry_date": treated_window[0],
                    "treated_exit_date": treated_window[1],
                    "treated_abs_ret_1d": float(treated["abs_ret_1"]),
                    "treated_ret_20": float(treated["ret_20"]),
                    "treated_hv_ratio": float(treated["hv_ratio"]),
                    "treated_sma20_distance": float(treated["sma20_distance"]),
                    "calendar_distance_sessions": int(treated_position - control_position),
                    "return_20d_match_distance": return_gap,
                    "hv_ratio_match_distance": hv_gap,
                    "sma20_distance_match_gap": sma_gap,
                }
            )
            used_controls.add(control_position)
            occupied.extend([control_window, treated_window])
    return sorted(
        all_blueprints,
        key=lambda row: (pd.Timestamp(row["treated_signal_date"]), str(row["symbol"])),
    )


def _path_metrics(
    panel: pd.DataFrame,
    *,
    symbol: str,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    pin_threshold: float,
) -> dict[str, Any]:
    path = panel.loc[entry_date:exit_date, symbol].astype(float)
    if len(path) < 2 or path.index[0] != entry_date or path.index[-1] != exit_date:
        raise ValueError("outcome path must include exact entry and exit dates")
    entry = float(path.iloc[0])
    terminal_return = float(path.iloc[-1] / entry - 1.0)
    path_range = float((path.max() - path.min()) / entry)
    return {
        "path_range": path_range,
        "terminal_abs_return": abs(terminal_return),
        "pinned": abs(terminal_return) <= pin_threshold,
    }


def evaluate_train_partition(
    close_panel: pd.DataFrame,
    train_blueprints: list[dict[str, Any]],
    *,
    min_pairs: int = 60,
    min_symbols: int = 5,
    pin_threshold: float = 0.03,
    min_pin_rate_edge: float = 0.05,
    bootstrap_samples: int = 10_000,
    shock_return_min: float = 0.02,
    hv_ratio_min: float = 1.20,
    control_abs_return_max: float = 0.005,
    max_match_distance_sessions: int = 252,
    max_return_20d_distance: float = 0.10,
    max_hv_ratio_distance: float = 0.50,
    max_sma20_distance_gap: float = 0.05,
) -> dict[str, Any]:
    """Evaluate only frozen train outcomes under the predeclared range gate."""
    panel = _validate_panel(close_panel)
    if min(min_pairs, min_symbols, bootstrap_samples) < 1 or not train_blueprints:
        raise ValueError("non-empty train blueprints and positive gates are required")
    if not 0.0 < pin_threshold < 1.0 or not 0.0 <= min_pin_rate_edge < 1.0:
        raise ValueError("pin thresholds must be valid fractions")

    rows: list[dict[str, Any]] = []
    occupied_by_symbol: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    controls_by_symbol: dict[str, set[pd.Timestamp]] = {}
    violations: list[str] = []
    for index, blueprint in enumerate(train_blueprints):
        symbol = str(blueprint["symbol"]).upper()
        if symbol not in panel.columns:
            raise ValueError(f"blueprint {index} symbol is outside the panel")
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
        if float(blueprint["treated_abs_ret_1d"]) < shock_return_min:
            violations.append(f"treated_shock:{index}")
        if float(blueprint["control_abs_ret_1d"]) > control_abs_return_max:
            violations.append(f"control_shock:{index}")
        if min(float(blueprint["treated_hv_ratio"]), float(blueprint["control_hv_ratio"])) < hv_ratio_min:
            violations.append(f"hv_ratio:{index}")
        if int(blueprint["calendar_distance_sessions"]) > max_match_distance_sessions:
            violations.append(f"calendar_distance:{index}")
        if float(blueprint["return_20d_match_distance"]) > max_return_20d_distance:
            violations.append(f"return_distance:{index}")
        if float(blueprint["hv_ratio_match_distance"]) > max_hv_ratio_distance:
            violations.append(f"hv_distance:{index}")
        if float(blueprint["sma20_distance_match_gap"]) > max_sma20_distance_gap:
            violations.append(f"sma_distance:{index}")
        required = {control_entry, control_exit, treated_entry, treated_exit}
        if not required.issubset(set(panel.index)):
            raise ValueError(f"blueprint {index} dates are outside the panel")
        control = _path_metrics(
            panel,
            symbol=symbol,
            entry_date=control_entry,
            exit_date=control_exit,
            pin_threshold=pin_threshold,
        )
        treated = _path_metrics(
            panel,
            symbol=symbol,
            entry_date=treated_entry,
            exit_date=treated_exit,
            pin_threshold=pin_threshold,
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
                "control_path_range": float(control["path_range"]),
                "treated_path_range": float(treated["path_range"]),
                "paired_range_compression": float(control["path_range"] - treated["path_range"]),
                "control_terminal_abs_return": float(control["terminal_abs_return"]),
                "treated_terminal_abs_return": float(treated["terminal_abs_return"]),
                "control_pinned": bool(control["pinned"]),
                "treated_pinned": bool(treated["pinned"]),
            }
        )

    treated_ranges = np.asarray([row["treated_path_range"] for row in rows], dtype=float)
    control_ranges = np.asarray([row["control_path_range"] for row in rows], dtype=float)
    compression = control_ranges - treated_ranges
    treated_pin_rate = float(np.mean([row["treated_pinned"] for row in rows]))
    control_pin_rate = float(np.mean([row["control_pinned"] for row in rows]))
    pin_rate_edge = treated_pin_rate - control_pin_rate
    lower_bound = circular_block_bootstrap_lower_bound(
        compression,
        block_length=5,
        samples=bootstrap_samples,
        seed=20260715,
    )
    symbols = sorted({row["symbol"] for row in rows})
    gate_checks = {
        "minimum_train_pairs": len(rows) >= min_pairs,
        "minimum_symbol_breadth": len(symbols) >= min_symbols,
        "treated_mean_path_range_below_control": float(treated_ranges.mean())
        < float(control_ranges.mean()),
        "pin_rate_edge_gte_5pct": pin_rate_edge >= min_pin_rate_edge,
        "positive_paired_range_compression_mean": float(compression.mean()) > 0.0,
        "paired_range_compression_bootstrap_lb90_positive": lower_bound > 0.0,
        "zero_integrity_violations": not violations,
    }
    return {
        "n_pairs": len(rows),
        "symbols_with_pairs": symbols,
        "pairs_by_symbol": {symbol: sum(row["symbol"] == symbol for row in rows) for symbol in symbols},
        "pin_threshold": float(pin_threshold),
        "minimum_pin_rate_edge": float(min_pin_rate_edge),
        "treated_mean_path_range": float(treated_ranges.mean()),
        "control_mean_path_range": float(control_ranges.mean()),
        "paired_range_compression_mean": float(compression.mean()),
        "paired_range_compression_median": float(np.median(compression)),
        "paired_range_compression_positive_frequency": float(np.mean(compression > 0.0)),
        "paired_range_compression_bootstrap_lb90": lower_bound,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length": 5,
        "treated_pin_rate": treated_pin_rate,
        "control_pin_rate": control_pin_rate,
        "pin_rate_edge": pin_rate_edge,
        "integrity_violations": violations,
        "gate_checks": gate_checks,
        "gate_pass": bool(all(gate_checks.values())),
        "pairs": rows,
    }


def _empty_train_result(
    *,
    min_pairs: int,
    min_symbols: int,
    pin_threshold: float,
    min_pin_rate_edge: float,
    bootstrap_samples: int,
) -> dict[str, Any]:
    return {
        "n_pairs": 0,
        "symbols_with_pairs": [],
        "pairs_by_symbol": {},
        "pin_threshold": float(pin_threshold),
        "minimum_pin_rate_edge": float(min_pin_rate_edge),
        "treated_mean_path_range": None,
        "control_mean_path_range": None,
        "paired_range_compression_mean": None,
        "paired_range_compression_median": None,
        "paired_range_compression_positive_frequency": None,
        "paired_range_compression_bootstrap_lb90": None,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length": 5,
        "treated_pin_rate": None,
        "control_pin_rate": None,
        "pin_rate_edge": None,
        "integrity_violations": [],
        "gate_checks": {
            "minimum_train_pairs": 0 >= min_pairs,
            "minimum_symbol_breadth": 0 >= min_symbols,
            "treated_mean_path_range_below_control": False,
            "pin_rate_edge_gte_5pct": False,
            "positive_paired_range_compression_mean": False,
            "paired_range_compression_bootstrap_lb90_positive": False,
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
    shock_return_min: float = 0.02,
    hv_ratio_min: float = 1.20,
    control_abs_return_max: float = 0.005,
    sma20_distance_max: float = 0.05,
    forward_sessions: int = 5,
    max_match_distance_sessions: int = 252,
    max_return_20d_distance: float = 0.10,
    max_hv_ratio_distance: float = 0.50,
    max_sma20_distance_gap: float = 0.05,
    min_train_pairs: int = 60,
    min_train_symbols: int = 5,
    pin_threshold: float = 0.03,
    min_pin_rate_edge: float = 0.05,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    """Run frozen F0 train test without reading holdout outcomes."""
    panel = _validate_panel(close_panel)
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if normalized != list(panel.columns) or len(normalized) != len(set(normalized)):
        raise ValueError("symbols must exactly match the ordered close-panel columns")
    if not 0.50 <= float(train_fraction) <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    blueprints = build_matched_blueprints(
        panel,
        shock_return_min=shock_return_min,
        hv_ratio_min=hv_ratio_min,
        control_abs_return_max=control_abs_return_max,
        sma20_distance_max=sma20_distance_max,
        forward_sessions=forward_sessions,
        max_match_distance_sessions=max_match_distance_sessions,
        max_return_20d_distance=max_return_20d_distance,
        max_hv_ratio_distance=max_hv_ratio_distance,
        max_sma20_distance_gap=max_sma20_distance_gap,
    )
    ordered = sorted(
        blueprints,
        key=lambda row: (pd.Timestamp(row["treated_signal_date"]), str(row["symbol"])),
    )
    split = int(len(ordered) * train_fraction)
    train = ordered[:split]
    holdout = ordered[split:]
    train_result = (
        evaluate_train_partition(
            panel,
            train,
            min_pairs=min_train_pairs,
            min_symbols=min_train_symbols,
            pin_threshold=pin_threshold,
            min_pin_rate_edge=min_pin_rate_edge,
            bootstrap_samples=bootstrap_samples,
            shock_return_min=shock_return_min,
            hv_ratio_min=hv_ratio_min,
            control_abs_return_max=control_abs_return_max,
            max_match_distance_sessions=max_match_distance_sessions,
            max_return_20d_distance=max_return_20d_distance,
            max_hv_ratio_distance=max_hv_ratio_distance,
            max_sma20_distance_gap=max_sma20_distance_gap,
        )
        if train
        else _empty_train_result(
            min_pairs=min_train_pairs,
            min_symbols=min_train_symbols,
            pin_threshold=pin_threshold,
            min_pin_rate_edge=min_pin_rate_edge,
            bootstrap_samples=bootstrap_samples,
        )
    )
    advanced = bool(train_result["gate_pass"])
    failed_checks = [name for name, passed in train_result["gate_checks"].items() if not passed]
    dominant_failure = None if advanced else (
        "control_support" if not train else "frozen train gate failed: " + ", ".join(failed_checks)
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_UNDERLYING_DISCOVERY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": CANDIDATE_ID,
        "mechanism_family": FAMILY_ID,
        "market_underlying": normalized,
        "forecast_type": "range_bound",
        "economic_mechanism": (
            "temporary liquidity and attention pressure after a completed large move may normalize, "
            "causing the following five-session close path to compress and finish nearer its entry "
            "than prior same-symbol high-volatility neutral no-shock controls"
        ),
        "candidate_or_family_scope": (
            "fixed six-name neutral/high-premium panel from current research rank; completed absolute "
            "one-day shock >=2%, hv20/hv60 >=1.20, close within 5% of prior SMA20; next-session entry; "
            "five-session underlying range/pin outcome; earlier same-symbol matched controls"
        ),
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "falsifier": (
            f"chronological train has fewer than {min_train_pairs} pairs or {min_train_symbols} symbols; "
            "treated mean path range is not below control; treated pin-rate edge is below five percentage "
            "points; paired control-minus-treated range compression mean or one-sided 90% five-pair "
            "block-bootstrap lower bound is non-positive; or any chronology/match integrity check fails"
        ),
        "claim_scope": (
            "underlying-only split/dividend-adjusted closes; outcome is five-session path range and "
            "terminal pin frequency, not a traded underlying return. No option marks, option costs, "
            "four-leg fills, implied-volatility crush, assignment, or managed option PnL were measured. "
            "The fixed present-day panel has survivorship/listing bias. Train-only L0 discovery cannot "
            "grant L1, a capital seat, or paper eligibility."
        ),
        "regime_hypothesis": (
            "completed large move with elevated short-versus-long realized volatility but close still "
            "near prior SMA20; stand aside without every condition or after a failed discovery gate"
        ),
        "entry_trigger": (
            "next session after a completed bar with absolute one-day return >=2%, hv20/hv60 >=1.20, "
            "and close within +/-5% of a fully warmed prior completed SMA20"
        ),
        "exit_rule": (
            "measured discovery outcome is fixed five-session underlying path range and terminal +/-3% "
            "pin; no option exit was simulated"
        ),
        "management_rule": (
            "untested future option plan only: 40% credit harvest, 70% defined-loss cut, 5-DTE stop, "
            "contract-expiration precedence, and no same-bar reentry"
        ),
        "horizon_alignment": (
            "the five-session range/pin pre-screen is only an approximate mechanism test for a later "
            "21-DTE credit iron butterfly; it does not establish theta/vega capture after four-leg friction"
        ),
        "greek_exposures": {
            "intended": "positive theta, short vega, and bounded short gamma through a symmetric credit iron butterfly",
            "dangerous_unintended": (
                "short gamma after a shock, renewed vega expansion, body/pin and early-assignment risk, "
                "and four-leg spread friction"
            ),
        },
        "mispricing_claim": (
            "none yet; the wake tests post-shock range compression before any implied-volatility or option-price claim"
        ),
        "stand_aside_rule": (
            "missing trigger, failed train gate, unavailable exact package, one-lot risk above $300, "
            "unsupported four-leg friction, scheduled-event uncertainty, or another correlated risk unit open"
        ),
        "funnel_claim_f2": False,
        "l1_claim": False,
        "config": {
            "symbols": normalized,
            "shock_return_min": shock_return_min,
            "hv_ratio_min": hv_ratio_min,
            "control_abs_return_max": control_abs_return_max,
            "sma20_distance_max": sma20_distance_max,
            "forward_sessions": forward_sessions,
            "train_fraction": train_fraction,
            "minimum_train_pairs": min_train_pairs,
            "minimum_train_symbols": min_train_symbols,
            "pin_threshold": pin_threshold,
            "minimum_pin_rate_edge": min_pin_rate_edge,
            "max_match_distance_sessions": max_match_distance_sessions,
            "max_return_20d_distance": max_return_20d_distance,
            "max_hv_ratio_distance": max_hv_ratio_distance,
            "max_sma20_distance_gap": max_sma20_distance_gap,
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
            "population_type": "fixed present-day liquid neutral/high-premium US equity panel",
            "population_pure": True,
            "population_pure_semantics": (
                "the frozen ordered panel was evaluated completely without row mixing; this does not "
                "mean survivorship-bias-free or generalizable"
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
        },
        "option_stage": {
            "status": "NOT_RUN_PENDING_UNTOUCHED_HOLDOUT" if advanced else "NOT_RUN_TRAIN_GATE_FAILED",
            "pricing_run": False,
            "pricing_calls": 0,
            "planned_structure": "iron_butterfly",
            "planned_dte": 21,
            "planned_width_usd": 2.0,
            "option_mark_provenance": None,
        },
        "structure": "conditional_iron_butterfly_not_yet_priced",
        "capital_fit_usd": 200.0,
        "one_lot_max_loss_usd": 200.0,
        "max_loss_usd": 200.0,
        "max_lots": 1,
        "portfolio_overlap_rule": (
            "one open risk unit across the correlated mega-cap/semi panel; no concurrent same-cluster entries"
        ),
        "capital_basis": (
            "structural $2-wing one-lot upper bound before entry credit and closing friction; not an observed or simulated max loss"
        ),
        "bar_claimed": "discovery",
        "confidence_stage": "F1_TRAIN/L0" if advanced else "F0_MECHANISM/L0",
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "decision": (
            "ADVANCE_POST_SHOCK_RANGE_COMPRESSION_TO_F1_TRAIN"
            if advanced
            else "CLOSE_POST_SHOCK_RANGE_COMPRESSION_TRAIN_FAMILY"
        ),
        "closed_family": None if advanced else FAMILY_ID,
        "dominant_failure_mechanism": dominant_failure,
        "registration_eligible": False,
        "authority": "research only; no registry, paper, shadow, funding, broker, arm, or live authority",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2026-07-16")
    parser.add_argument("--cache-dir", default=".cache/platform/post_shock_range_compression")
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
        "selection_source": (
            "research.db run 36 current full-universe rank; neutral/high-premium panel frozen before train outcomes"
        ),
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
                "train_symbols": payload["train"]["symbols_with_pairs"],
                "paired_range_compression_mean": payload["train"][
                    "paired_range_compression_mean"
                ],
                "paired_range_compression_bootstrap_lb90": payload["train"][
                    "paired_range_compression_bootstrap_lb90"
                ],
                "pin_rate_edge": payload["train"]["pin_rate_edge"],
                "out": str(out),
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

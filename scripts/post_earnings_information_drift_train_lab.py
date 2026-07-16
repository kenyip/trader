#!/usr/bin/env python3
"""Train-only post-earnings information-drift discovery lab.

BUILD/L0 only. The lab tests a signed underlying continuation mechanism after
an explicitly timestamped issuer earnings announcement. It does not price
options and preserves the chronological final 40% of matched blueprints unread.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yfinance as yf

try:
    from scripts.low_hv_cross_section_train_lab import (
        circular_block_bootstrap_lower_bound,
        load_adjusted_history,
    )
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from low_hv_cross_section_train_lab import (  # type: ignore[no-redef]
        circular_block_bootstrap_lower_bound,
        load_adjusted_history,
    )


DEFAULT_SYMBOLS = ["AAPL", "AMD", "SMCI", "TSLA", "META", "GOOGL", "ARM", "NVDA"]
CANDIDATE_ID = "POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT_CALL_DEBIT_21D_V1"
FAMILY_ID = "POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT"
NEW_YORK = "America/New_York"


def _validate_panel(close_panel: pd.DataFrame) -> pd.DataFrame:
    if close_panel.empty or close_panel.shape[1] < 1:
        raise ValueError("close panel must contain at least one symbol")
    prepared = close_panel.copy()
    prepared.index = pd.DatetimeIndex(pd.to_datetime(prepared.index)).tz_localize(None).normalize()
    prepared.columns = [str(column).strip().upper() for column in prepared.columns]
    prepared = prepared.apply(pd.to_numeric, errors="coerce")
    if not prepared.index.is_unique or not prepared.index.is_monotonic_increasing:
        raise ValueError("close panel index must be unique and increasing")
    if len(set(prepared.columns)) != len(prepared.columns):
        raise ValueError("close panel symbols must be unique")
    for symbol in prepared.columns:
        series = prepared[symbol]
        valid = series.notna()
        if valid.sum() < 80:
            raise ValueError(f"{symbol} requires at least 80 finite rows")
        first = int(np.flatnonzero(valid.to_numpy())[0])
        last = int(np.flatnonzero(valid.to_numpy())[-1])
        interior = series.iloc[first : last + 1].to_numpy(dtype=float)
        if not np.isfinite(interior).all() or (interior <= 0.0).any():
            raise ValueError("close panel must be finite and positive inside each listing window")
    return prepared


def _symbol_series(panel: pd.DataFrame, symbol: str) -> pd.Series:
    series = panel[symbol].dropna().astype(float)
    return series


def _validate_events(events: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if not {"symbol", "announcement_at"}.issubset(events.columns):
        raise ValueError("events require symbol and announcement_at columns")
    allowed = set(symbols)
    rows: list[dict[str, Any]] = []
    for row_number, row in events.iterrows():
        symbol = str(row["symbol"]).strip().upper()
        if symbol not in allowed:
            continue
        stamp = pd.Timestamp(row["announcement_at"])
        if stamp.tzinfo is None:
            raise ValueError(f"event {row_number} announcement_at requires timezone")
        rows.append({"symbol": symbol, "announcement_at": stamp.tz_convert("UTC")})
    if not rows:
        raise ValueError("no timestamped earnings events remain for the panel")
    prepared = pd.DataFrame(rows).drop_duplicates(["symbol", "announcement_at"])
    return prepared.sort_values(["announcement_at", "symbol"]).reset_index(drop=True)


def first_completed_session_after_announcement(
    announcement_at: pd.Timestamp, sessions: pd.DatetimeIndex
) -> pd.Timestamp:
    """Map explicit BMO/AMC timing to the first fully completed RTH session."""
    stamp = pd.Timestamp(announcement_at)
    if stamp.tzinfo is None:
        raise ValueError("announcement timestamp requires timezone")
    ordered = pd.DatetimeIndex(pd.to_datetime(sessions)).tz_localize(None).normalize()
    if ordered.empty or not ordered.is_unique or not ordered.is_monotonic_increasing:
        raise ValueError("sessions must be non-empty, unique, and increasing")
    local = stamp.tz_convert(NEW_YORK)
    local_date = pd.Timestamp(local.date())
    local_time = local.time().replace(tzinfo=None)
    if local_time <= time(9, 30):
        candidates = ordered[ordered >= local_date]
    elif local_time >= time(16, 0):
        candidates = ordered[ordered > local_date]
    else:
        raise ValueError("ambiguous regular-session earnings announcement timing")
    if candidates.empty:
        raise ValueError("announcement has no completed session in price history")
    return pd.Timestamp(candidates[0])


def _overlaps(
    window: tuple[pd.Timestamp, pd.Timestamp],
    occupied: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    start, end = window
    return any(not (end < prior_start or start > prior_end) for prior_start, prior_end in occupied)


def build_event_matched_blueprints(
    close_panel: pd.DataFrame,
    events: pd.DataFrame,
    *,
    reaction_abs_min: float = 0.02,
    forward_sessions: int = 5,
    max_match_distance_sessions: int = 504,
    max_abs_reaction_gap: float = 0.015,
    max_ret20_gap: float = 0.10,
    max_hv20_gap: float = 0.20,
) -> list[dict[str, Any]]:
    """Match earnings reactions to prior same-sign non-event reaction sessions."""
    panel = _validate_panel(close_panel)
    normalized_symbols = list(panel.columns)
    event_table = _validate_events(events, normalized_symbols)
    if min(reaction_abs_min, forward_sessions, max_match_distance_sessions) <= 0:
        raise ValueError("reaction, horizon, and calendar bounds must be positive")
    if max_match_distance_sessions <= forward_sessions:
        raise ValueError("matching distance must exceed the forward horizon")
    if min(max_abs_reaction_gap, max_ret20_gap, max_hv20_gap) <= 0.0:
        raise ValueError("matching feature bounds must be positive")

    all_blueprints: list[dict[str, Any]] = []
    for symbol in normalized_symbols:
        close = _symbol_series(panel, symbol)
        symbol_events = event_table[event_table["symbol"] == symbol]
        if symbol_events.empty:
            continue
        event_signals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        for row in symbol_events.itertuples(index=False):
            try:
                signal = first_completed_session_after_announcement(row.announcement_at, close.index)
            except ValueError as exc:
                if "no completed session" in str(exc) or "ambiguous" in str(exc):
                    continue
                raise
            event_signals.append((pd.Timestamp(row.announcement_at), signal))
        if not event_signals:
            continue
        signal_dates = sorted({signal for _, signal in event_signals})
        signal_set = set(signal_dates)
        signal_positions = {date: int(close.index.get_loc(date)) for date in signal_dates}
        excluded_positions: set[int] = set()
        for position in signal_positions.values():
            excluded_positions.update(
                range(max(0, position - forward_sessions), min(len(close), position + forward_sessions + 1))
            )

        ret_1 = close / close.shift(1) - 1.0
        ret_20 = close / close.shift(20) - 1.0
        hv_20 = np.log(close / close.shift(1)).rolling(20, min_periods=20).std() * np.sqrt(252.0)
        features = pd.DataFrame(
            {"ret_1": ret_1, "ret_20": ret_20, "hv_20": hv_20}, index=close.index
        )
        occupied: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        used_controls: set[int] = set()
        for announcement_at, event_signal in sorted(event_signals, key=lambda item: item[1]):
            event_position = int(close.index.get_loc(event_signal))
            event_exit_position = event_position + forward_sessions
            if event_exit_position >= len(close):
                continue
            event_feature = features.iloc[event_position]
            if not np.isfinite(event_feature.to_numpy(dtype=float)).all():
                continue
            event_reaction = float(event_feature["ret_1"])
            if abs(event_reaction) < reaction_abs_min:
                continue
            event_window = (event_signal, pd.Timestamp(close.index[event_exit_position]))
            if _overlaps(event_window, occupied):
                continue
            lower = max(20, event_position - max_match_distance_sessions)
            candidates: list[tuple[float, int]] = []
            for control_position in range(lower, event_position - forward_sessions):
                if control_position in used_controls or control_position in excluded_positions:
                    continue
                control_exit_position = control_position + forward_sessions
                if control_exit_position >= event_position:
                    continue
                control_feature = features.iloc[control_position]
                if not np.isfinite(control_feature.to_numpy(dtype=float)).all():
                    continue
                control_reaction = float(control_feature["ret_1"])
                if control_reaction == 0.0 or np.sign(control_reaction) != np.sign(event_reaction):
                    continue
                reaction_gap = abs(abs(event_reaction) - abs(control_reaction))
                ret20_gap = abs(float(event_feature["ret_20"]) - float(control_feature["ret_20"]))
                hv20_gap = abs(float(event_feature["hv_20"]) - float(control_feature["hv_20"]))
                if (
                    reaction_gap > max_abs_reaction_gap
                    or ret20_gap > max_ret20_gap
                    or hv20_gap > max_hv20_gap
                ):
                    continue
                control_window = (
                    pd.Timestamp(close.index[control_position]),
                    pd.Timestamp(close.index[control_exit_position]),
                )
                if _overlaps(control_window, occupied) or _overlaps(control_window, [event_window]):
                    continue
                distance = event_position - control_position
                score = (
                    reaction_gap / max_abs_reaction_gap
                    + ret20_gap / max_ret20_gap
                    + hv20_gap / max_hv20_gap
                    + distance / max_match_distance_sessions
                )
                candidates.append((float(score), control_position))
            if not candidates:
                continue
            _, control_position = min(candidates, key=lambda item: (item[0], -item[1]))
            control_feature = features.iloc[control_position]
            control_exit_position = control_position + forward_sessions
            control_window = (
                pd.Timestamp(close.index[control_position]),
                pd.Timestamp(close.index[control_exit_position]),
            )
            control_reaction = float(control_feature["ret_1"])
            all_blueprints.append(
                {
                    "symbol": symbol,
                    "announcement_at": pd.Timestamp(announcement_at).isoformat(),
                    "event_signal_date": event_signal,
                    "event_exit_date": event_window[1],
                    "event_reaction": event_reaction,
                    "event_ret20": float(event_feature["ret_20"]),
                    "event_hv20": float(event_feature["hv_20"]),
                    "control_signal_date": control_window[0],
                    "control_exit_date": control_window[1],
                    "control_reaction": control_reaction,
                    "control_ret20": float(control_feature["ret_20"]),
                    "control_hv20": float(control_feature["hv_20"]),
                    "calendar_distance_sessions": int(event_position - control_position),
                    "abs_reaction_match_gap": abs(abs(event_reaction) - abs(control_reaction)),
                    "ret20_match_gap": abs(
                        float(event_feature["ret_20"]) - float(control_feature["ret_20"])
                    ),
                    "hv20_match_gap": abs(
                        float(event_feature["hv_20"]) - float(control_feature["hv_20"])
                    ),
                    "excluded_event_signal_dates": signal_dates,
                }
            )
            used_controls.add(control_position)
            occupied.extend([control_window, event_window])
    return sorted(
        all_blueprints,
        key=lambda row: (pd.Timestamp(row["event_signal_date"]), str(row["symbol"])),
    )


def evaluate_train_partition(
    close_panel: pd.DataFrame,
    train_blueprints: list[dict[str, Any]],
    *,
    min_pairs: int = 40,
    min_symbols: int = 6,
    min_hit_rate_edge: float = 0.05,
    bootstrap_samples: int = 10_000,
    reaction_abs_min: float = 0.02,
    max_match_distance_sessions: int = 504,
    max_abs_reaction_gap: float = 0.015,
    max_ret20_gap: float = 0.10,
    max_hv20_gap: float = 0.20,
) -> dict[str, Any]:
    panel = _validate_panel(close_panel)
    if min(min_pairs, min_symbols, bootstrap_samples) < 1 or not train_blueprints:
        raise ValueError("non-empty train blueprints and positive gates are required")
    if not 0.0 <= min_hit_rate_edge < 1.0:
        raise ValueError("hit-rate edge must be a valid fraction")
    rows: list[dict[str, Any]] = []
    occupied_by_symbol: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    controls_by_symbol: dict[str, set[pd.Timestamp]] = {}
    violations: list[str] = []
    for index, blueprint in enumerate(train_blueprints):
        symbol = str(blueprint["symbol"]).upper()
        if symbol not in panel.columns:
            raise ValueError(f"blueprint {index} symbol is outside the panel")
        close = _symbol_series(panel, symbol)
        control_signal = pd.Timestamp(blueprint["control_signal_date"])
        control_exit = pd.Timestamp(blueprint["control_exit_date"])
        event_signal = pd.Timestamp(blueprint["event_signal_date"])
        event_exit = pd.Timestamp(blueprint["event_exit_date"])
        if not control_signal < control_exit < event_signal < event_exit:
            violations.append(f"chronology:{index}")
        occupied = occupied_by_symbol.setdefault(symbol, [])
        windows = [(control_signal, control_exit), (event_signal, event_exit)]
        if any(_overlaps(window, occupied) for window in windows):
            violations.append(f"overlap:{index}")
        occupied.extend(windows)
        controls = controls_by_symbol.setdefault(symbol, set())
        if control_signal in controls:
            violations.append(f"control_reuse:{index}")
        controls.add(control_signal)
        excluded = {pd.Timestamp(value) for value in blueprint["excluded_event_signal_dates"]}
        if control_signal in excluded:
            violations.append(f"event_control:{index}")
        event_reaction = float(blueprint["event_reaction"])
        control_reaction = float(blueprint["control_reaction"])
        if abs(event_reaction) < reaction_abs_min:
            violations.append(f"event_reaction:{index}")
        if control_reaction == 0.0 or np.sign(control_reaction) != np.sign(event_reaction):
            violations.append(f"reaction_sign:{index}")
        if int(blueprint["calendar_distance_sessions"]) > max_match_distance_sessions:
            violations.append(f"calendar_distance:{index}")
        if float(blueprint["abs_reaction_match_gap"]) > max_abs_reaction_gap:
            violations.append(f"reaction_distance:{index}")
        if float(blueprint["ret20_match_gap"]) > max_ret20_gap:
            violations.append(f"ret20_distance:{index}")
        if float(blueprint["hv20_match_gap"]) > max_hv20_gap:
            violations.append(f"hv20_distance:{index}")
        required = {control_signal, control_exit, event_signal, event_exit}
        if not required.issubset(set(close.index)):
            raise ValueError(f"blueprint {index} dates are outside the symbol history")
        event_signed = float(
            np.sign(event_reaction) * (close.loc[event_exit] / close.loc[event_signal] - 1.0)
        )
        control_signed = float(
            np.sign(control_reaction) * (close.loc[control_exit] / close.loc[control_signal] - 1.0)
        )
        rows.append(
            {
                "symbol": symbol,
                "announcement_at": str(blueprint["announcement_at"]),
                "event_signal_date": str(event_signal.date()),
                "event_exit_date": str(event_exit.date()),
                "control_signal_date": str(control_signal.date()),
                "control_exit_date": str(control_exit.date()),
                "event_reaction": event_reaction,
                "control_reaction": control_reaction,
                "calendar_distance_sessions": int(blueprint["calendar_distance_sessions"]),
                "abs_reaction_match_gap": float(blueprint["abs_reaction_match_gap"]),
                "ret20_match_gap": float(blueprint["ret20_match_gap"]),
                "hv20_match_gap": float(blueprint["hv20_match_gap"]),
                "event_signed_forward_return": event_signed,
                "control_signed_forward_return": control_signed,
                "paired_signed_excess": event_signed - control_signed,
                "event_continuation_hit": event_signed > 0.0,
                "control_continuation_hit": control_signed > 0.0,
            }
        )
    excess = np.asarray([row["paired_signed_excess"] for row in rows], dtype=float)
    event_values = np.asarray([row["event_signed_forward_return"] for row in rows], dtype=float)
    control_values = np.asarray([row["control_signed_forward_return"] for row in rows], dtype=float)
    calendar_distances = np.asarray(
        [row["calendar_distance_sessions"] for row in rows], dtype=float
    )
    reaction_gaps = np.asarray([row["abs_reaction_match_gap"] for row in rows], dtype=float)
    ret20_gaps = np.asarray([row["ret20_match_gap"] for row in rows], dtype=float)
    hv20_gaps = np.asarray([row["hv20_match_gap"] for row in rows], dtype=float)
    event_hit_rate = float(np.mean([row["event_continuation_hit"] for row in rows]))
    control_hit_rate = float(np.mean([row["control_continuation_hit"] for row in rows]))
    hit_rate_edge = event_hit_rate - control_hit_rate
    lower_bound = circular_block_bootstrap_lower_bound(
        excess,
        block_length=5,
        samples=bootstrap_samples,
        seed=20260715,
    )
    symbols = sorted({row["symbol"] for row in rows})
    gate_checks = {
        "minimum_train_pairs": len(rows) >= min_pairs,
        "minimum_symbol_breadth": len(symbols) >= min_symbols,
        "event_signed_mean_above_control": float(event_values.mean()) > float(control_values.mean()),
        "positive_paired_signed_excess_mean": float(excess.mean()) > 0.0,
        "paired_signed_excess_bootstrap_lb90_positive": lower_bound > 0.0,
        "continuation_hit_rate_edge_gte_5pct": hit_rate_edge >= min_hit_rate_edge,
        "zero_integrity_violations": not violations,
    }
    return {
        "n_pairs": len(rows),
        "symbols_with_pairs": symbols,
        "pairs_by_symbol": {symbol: sum(row["symbol"] == symbol for row in rows) for symbol in symbols},
        "event_signed_forward_mean": float(event_values.mean()),
        "control_signed_forward_mean": float(control_values.mean()),
        "paired_signed_excess_mean": float(excess.mean()),
        "paired_signed_excess_median": float(np.median(excess)),
        "paired_signed_excess_positive_frequency": float(np.mean(excess > 0.0)),
        "paired_signed_excess_bootstrap_lb90": lower_bound,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length": 5,
        "event_continuation_hit_rate": event_hit_rate,
        "control_continuation_hit_rate": control_hit_rate,
        "continuation_hit_rate_edge": hit_rate_edge,
        "match_diagnostics": {
            "diagnostic_only_not_a_predeclared_gate": True,
            "calendar_distance_sessions_max": int(calendar_distances.max()),
            "calendar_distance_sessions_median": float(np.median(calendar_distances)),
            "abs_reaction_match_gap_max": float(reaction_gaps.max()),
            "abs_reaction_match_gap_median": float(np.median(reaction_gaps)),
            "ret20_match_gap_max": float(ret20_gaps.max()),
            "ret20_match_gap_median": float(np.median(ret20_gaps)),
            "hv20_match_gap_max": float(hv20_gaps.max()),
            "hv20_match_gap_median": float(np.median(hv20_gaps)),
            "paired_signed_excess_extreme_abs_threshold": 0.10,
            "paired_signed_excess_extreme_abs_count": int(np.sum(np.abs(excess) >= 0.10)),
        },
        "integrity_violations": violations,
        "gate_checks": gate_checks,
        "gate_pass": bool(all(gate_checks.values())),
        "pairs": rows,
    }


def _empty_train_result(*, min_pairs: int, min_symbols: int, bootstrap_samples: int) -> dict[str, Any]:
    return {
        "n_pairs": 0,
        "symbols_with_pairs": [],
        "pairs_by_symbol": {},
        "event_signed_forward_mean": None,
        "control_signed_forward_mean": None,
        "paired_signed_excess_mean": None,
        "paired_signed_excess_median": None,
        "paired_signed_excess_positive_frequency": None,
        "paired_signed_excess_bootstrap_lb90": None,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length": 5,
        "event_continuation_hit_rate": None,
        "control_continuation_hit_rate": None,
        "continuation_hit_rate_edge": None,
        "match_diagnostics": {
            "diagnostic_only_not_a_predeclared_gate": True,
            "calendar_distance_sessions_max": None,
            "calendar_distance_sessions_median": None,
            "abs_reaction_match_gap_max": None,
            "abs_reaction_match_gap_median": None,
            "ret20_match_gap_max": None,
            "ret20_match_gap_median": None,
            "hv20_match_gap_max": None,
            "hv20_match_gap_median": None,
            "paired_signed_excess_extreme_abs_threshold": 0.10,
            "paired_signed_excess_extreme_abs_count": 0,
        },
        "integrity_violations": [],
        "gate_checks": {
            "minimum_train_pairs": 0 >= min_pairs,
            "minimum_symbol_breadth": 0 >= min_symbols,
            "event_signed_mean_above_control": False,
            "positive_paired_signed_excess_mean": False,
            "paired_signed_excess_bootstrap_lb90_positive": False,
            "continuation_hit_rate_edge_gte_5pct": False,
            "zero_integrity_violations": True,
        },
        "gate_pass": False,
        "pairs": [],
    }


def run_lab_from_panel(
    close_panel: pd.DataFrame,
    events: pd.DataFrame,
    *,
    symbols: list[str],
    provenance: dict[str, Any],
    train_fraction: float = 0.60,
    reaction_abs_min: float = 0.02,
    forward_sessions: int = 5,
    max_match_distance_sessions: int = 504,
    max_abs_reaction_gap: float = 0.015,
    max_ret20_gap: float = 0.10,
    max_hv20_gap: float = 0.20,
    min_train_pairs: int = 40,
    min_train_symbols: int = 6,
    min_hit_rate_edge: float = 0.05,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    panel = _validate_panel(close_panel)
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if normalized != list(panel.columns) or len(normalized) != len(set(normalized)):
        raise ValueError("symbols must exactly match ordered close-panel columns")
    if not 0.50 <= train_fraction <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    event_table = _validate_events(events, normalized)
    blueprints = build_event_matched_blueprints(
        panel,
        event_table,
        reaction_abs_min=reaction_abs_min,
        forward_sessions=forward_sessions,
        max_match_distance_sessions=max_match_distance_sessions,
        max_abs_reaction_gap=max_abs_reaction_gap,
        max_ret20_gap=max_ret20_gap,
        max_hv20_gap=max_hv20_gap,
    )
    ordered = sorted(
        blueprints,
        key=lambda row: (pd.Timestamp(row["event_signal_date"]), str(row["symbol"])),
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
            min_hit_rate_edge=min_hit_rate_edge,
            bootstrap_samples=bootstrap_samples,
            reaction_abs_min=reaction_abs_min,
            max_match_distance_sessions=max_match_distance_sessions,
            max_abs_reaction_gap=max_abs_reaction_gap,
            max_ret20_gap=max_ret20_gap,
            max_hv20_gap=max_hv20_gap,
        )
        if train
        else _empty_train_result(
            min_pairs=min_train_pairs,
            min_symbols=min_train_symbols,
            bootstrap_samples=bootstrap_samples,
        )
    )
    advanced = bool(train_result["gate_pass"])
    failed = [name for name, passed in train_result["gate_checks"].items() if not passed]
    dominant_failure = None if advanced else (
        "timestamped_event_or_control_support" if not train else "frozen train gate failed: " + ", ".join(failed)
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
        "forecast_type": "signed_direction_continuation",
        "economic_mechanism": (
            "earnings resolve concentrated information uncertainty; gradual interpretation and investor "
            "underreaction may continue the signed first completed post-announcement move over five sessions"
        ),
        "candidate_or_family_scope": (
            "fixed present-day liquid operating-company panel from current rank; explicit BMO/AMC timestamp; "
            "absolute first completed-session reaction >=2%; prior same-symbol same-sign non-event matched control"
        ),
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "falsifier": (
            f"train has fewer than {min_train_pairs} matched pairs or {min_train_symbols} symbols; paired signed "
            "five-session excess mean or one-sided 90% five-pair circular-block-bootstrap lower bound is non-positive; "
            "continuation hit-rate edge is below five percentage points; or integrity fails"
        ),
        "claim_scope": (
            "underlying-only split/dividend-adjusted closes and retrospectively downloaded explicit earnings "
            "timestamps. No open-price execution, option marks, bid/ask costs, IV crush, debit-spread fills, or "
            "managed option PnL were measured. The present-day panel has survivorship/listing bias. L0 train-only "
            "discovery cannot grant L1, a capital seat, or paper eligibility."
        ),
        "regime_hypothesis": (
            "issuer earnings with an explicit timing label and absolute first completed-session move >=2%; "
            "stand aside on ambiguous timing, weak reaction, missing history, overlap, or failed gate"
        ),
        "entry_trigger": (
            "future option plan: after the first fully completed post-announcement regular session, enter at the "
            "next regular-session open in the completed reaction direction; current mechanism outcome is measured "
            "from signal close through five sessions and is not an execution simulation"
        ),
        "exit_rule": "underlying mechanism horizon is five completed sessions; no option exit was simulated",
        "management_rule": (
            "untested future option plan only: 50% debit-spread profit harvest, completed-session reversal stop "
            "through signal-session opposite extreme, hard five-session time stop, no roll or same-bar re-entry"
        ),
        "horizon_alignment": (
            "five-session signed close continuation is directionally aligned with a later 21-DTE call/put debit "
            "spread but does not establish next-open fill quality, theta/vega economics, or after-cost option edge"
        ),
        "option_structure": (
            "conditional 21-DTE $2-wide call debit spread after positive reactions and $2-wide put debit spread "
            "after negative reactions; not priced in this wake"
        ),
        "greek_exposures": {
            "intended": "bounded signed delta and convexity",
            "dangerous_unintended": (
                "long vega into post-event IV crush, long gamma/theta decay, gap risk, and sparse two-leg liquidity"
            ),
        },
        "mispricing_claim": "none yet; the wake tests an underlying information-underreaction mechanism",
        "stand_aside_rule": (
            "missing or ambiguous timing, reaction below threshold, unavailable exact history, overlapping event "
            "window, non-finite feature, failed train gate, exact package max loss above $300, or another event-risk unit open"
        ),
        "funnel_claim_f2": False,
        "l1_claim": False,
        "config": {
            "symbols": normalized,
            "reaction_abs_min": reaction_abs_min,
            "forward_sessions": forward_sessions,
            "train_fraction": train_fraction,
            "minimum_train_pairs": min_train_pairs,
            "minimum_train_symbols": min_train_symbols,
            "minimum_hit_rate_edge": min_hit_rate_edge,
            "max_match_distance_sessions": max_match_distance_sessions,
            "max_abs_reaction_gap": max_abs_reaction_gap,
            "max_ret20_gap": max_ret20_gap,
            "max_hv20_gap": max_hv20_gap,
            "bootstrap_confidence": 0.90,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_block_length": 5,
            "controls_prior_only": True,
            "controls_exclude_event_windows": True,
            "matched_without_replacement_per_symbol": True,
            "non_overlapping_pair_windows_per_symbol": True,
        },
        "data_provenance": provenance,
        "selection_diagnostics": {
            "timestamped_events": int(len(event_table)),
            "matched_blueprints": len(ordered),
            "train_blueprints": len(train),
            "holdout_blueprints": len(holdout),
            "train_symbols": sorted({str(row["symbol"]) for row in train}),
            "holdout_symbols": sorted({str(row["symbol"]) for row in holdout}),
        },
        "population_validity": {
            "population_type": "fixed present-day liquid operating-company panel from research rank 36",
            "population_pure": True,
            "population_pure_semantics": "the frozen ordered panel is complete; purity does not mean bias-free",
            "bias_free": False,
            "ranking_complete": True,
            "survivorship_bias": True,
            "listing_bias": True,
            "earnings_timestamp_source_is_current_retrospective_download": True,
            "generalization_allowed": False,
        },
        "train": train_result,
        "untouched_holdout": {
            "n_blueprints": len(holdout),
            "first_event_signal_date": (
                str(pd.Timestamp(holdout[0]["event_signal_date"]).date()) if holdout else None
            ),
            "last_event_exit_date": (
                str(pd.Timestamp(holdout[-1]["event_exit_date"]).date()) if holdout else None
            ),
            "outcome_metrics_read": False,
            "simulation_run": False,
        },
        "option_stage": {
            "status": "NOT_RUN_PENDING_UNTOUCHED_HOLDOUT" if advanced else "NOT_RUN_TRAIN_GATE_FAILED",
            "pricing_run": False,
            "pricing_calls": 0,
            "planned_structure": "conditional_call_or_put_debit_spread",
            "planned_dte": 21,
            "planned_width_usd": 2.0,
            "option_mark_provenance": None,
        },
        "structure": "conditional_call_or_put_debit_spread_not_yet_priced",
        "capital_fit_usd": 200.0,
        "one_lot_max_loss_usd": 200.0,
        "max_loss_usd": 200.0,
        "max_lots": 1,
        "portfolio_overlap_rule": "one global earnings-risk unit; no overlapping event windows",
        "capital_basis": (
            "structural $2-width one-lot maximum debit before closing friction; not observed or simulated loss"
        ),
        "bar_claimed": "discovery",
        "confidence_stage": "F1_TRAIN/L0" if advanced else "F0_MECHANISM/L0",
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "decision": (
            "ADVANCE_POST_EARNINGS_INFORMATION_DRIFT_TO_F1_TRAIN"
            if advanced
            else "CLOSE_POST_EARNINGS_INFORMATION_DRIFT_TRAIN_FAMILY"
        ),
        "closed_family": None if advanced else FAMILY_ID,
        "dominant_failure_mechanism": dominant_failure,
        "registration_eligible": False,
        "authority": "research only; no registry, paper, shadow, funding, broker, arm, or live authority",
    }


def load_earnings_events(
    symbols: list[str],
    *,
    cache_dir: Path,
    start: str,
    end: str,
    fetcher: Callable[[str, int], pd.DataFrame | None] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Persist and replay explicit Yahoo Finance earnings timestamps with hashes."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_meta: dict[str, Any] = {}
    frames: list[pd.DataFrame] = []
    fetch = fetcher or (lambda symbol, limit: yf.Ticker(symbol).get_earnings_dates(limit=limit))
    start_stamp = pd.Timestamp(start, tz="UTC")
    end_stamp = pd.Timestamp(end, tz="UTC")
    for symbol in symbols:
        cache_path = cache_dir / f"{symbol}_{start}_{end}_earnings.csv"
        if not cache_path.exists():
            raw = fetch(symbol, 100)
            if raw is None or raw.empty:
                raise ValueError(f"{symbol} earnings download is empty")
            canonical = pd.DataFrame(
                {
                    "symbol": symbol,
                    "announcement_at": [pd.Timestamp(value).isoformat() for value in raw.index],
                    "reported_eps": pd.to_numeric(raw.get("Reported EPS"), errors="coerce"),
                }
            )
            canonical.to_csv(cache_path, index=False)
        cached = pd.read_csv(cache_path)
        if list(cached.columns) != ["symbol", "announcement_at", "reported_eps"]:
            raise ValueError(f"{symbol} earnings cache schema mismatch")
        parsed = pd.to_datetime(cached["announcement_at"], utc=True, errors="raise")
        selected = cached[(parsed >= start_stamp) & (parsed < end_stamp)].copy()
        selected["announcement_at"] = parsed[(parsed >= start_stamp) & (parsed < end_stamp)]
        selected = selected[pd.to_numeric(selected["reported_eps"], errors="coerce").notna()]
        frames.append(selected[["symbol", "announcement_at"]])
        source_meta[symbol] = {
            "path": str(cache_path),
            "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
            "rows_in_range_with_reported_eps": int(len(selected)),
            "timing_semantics": "Yahoo Finance retrospective earnings timestamp converted to UTC",
        }
    combined = pd.concat(frames, ignore_index=True)
    return _validate_events(combined, symbols), source_meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2026-07-16")
    parser.add_argument("--cache-dir", default=".cache/platform/post_earnings_information_drift")
    parser.add_argument("--train-fraction", type=float, default=0.60)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    histories: dict[str, pd.Series] = {}
    price_meta: dict[str, Any] = {}
    cache_dir = Path(args.cache_dir)
    for symbol in symbols:
        history, meta = load_adjusted_history(
            symbol,
            cache_dir=cache_dir / "prices",
            start=args.start,
            end=args.end,
        )
        histories[symbol] = history
        price_meta[symbol] = meta
    panel = pd.concat([histories[symbol].rename(symbol) for symbol in symbols], axis=1, join="outer")
    panel = _validate_panel(panel)
    events, event_meta = load_earnings_events(
        symbols,
        cache_dir=cache_dir / "events",
        start=args.start,
        end=args.end,
    )
    provenance = {
        "prices": price_meta,
        "earnings_events": event_meta,
        "panel": {
            "rows": int(len(panel)),
            "start": str(panel.index[0].date()),
            "end": str(panel.index[-1].date()),
            "join": "outer union by session; leading/trailing listing gaps only; each symbol evaluated on own history",
        },
        "selection_source": (
            "research.db run 36 current full-universe rank; eight liquid operating-company names frozen before outcomes"
        ),
    }
    payload = run_lab_from_panel(
        panel,
        events,
        symbols=symbols,
        provenance=provenance,
        train_fraction=args.train_fraction,
        bootstrap_samples=args.bootstrap_samples,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
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
                "paired_signed_excess_mean": payload["train"]["paired_signed_excess_mean"],
                "paired_signed_excess_bootstrap_lb90": payload["train"][
                    "paired_signed_excess_bootstrap_lb90"
                ],
                "continuation_hit_rate_edge": payload["train"]["continuation_hit_rate_edge"],
                "out": str(out),
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

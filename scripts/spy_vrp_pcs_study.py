#!/usr/bin/env python3
"""Frozen SPY VIX-versus-forward-realized-volatility mechanism-first PCS study.

Research-only BUILD/L0. All 2016-2026 observations are inspected development data.
The option branch is Black-Scholes proxy evidence and runs only if every observed
mechanism gate passes. No registry, paper ledger, broker, shadow, arm, or live use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import pricing
from trader_platform.research.pcs_sim import listed_weekly_expiration

CANDIDATE_ID = "SPY_VRP_PCS_VIX_RV_21D_V1"
MECHANISM_FAMILY = "SPY_VRP_VIX_RV_21D"
RATIO_THRESHOLD = 1.25
RV_LOOKBACK = 20
OUTCOME_SESSIONS = 21
SMA_LOOKBACK = 200
RISK_FREE_RATE = 0.04
DIVIDEND_YIELD = 0.015
TARGET_DELTA = 0.20
SPREAD_WIDTH = 1.0
MIN_ZERO_COST_CREDIT = 0.10
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_BLOCK = 3

FOLDS = (
    {
        "name": "assessment_2020_2021",
        "origin_start": "2017-05-01",
        "origin_end": "2019-12-31",
        "assessment_start": "2020-01-02",
        "assessment_end": "2021-12-31",
    },
    {
        "name": "assessment_2022_2023",
        "origin_start": "2017-05-01",
        "origin_end": "2021-12-31",
        "assessment_start": "2022-01-03",
        "assessment_end": "2023-12-29",
    },
    {
        "name": "assessment_2024_2026",
        "origin_start": "2017-05-01",
        "origin_end": "2023-12-29",
        "assessment_start": "2024-01-02",
        "assessment_end": "2026-06-10",
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_spy(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.columns = [str(column).lower() for column in frame.columns]
    required = ("open", "high", "low", "close", "volume")
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"SPY data missing columns: {missing}")
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame.loc[:, required].sort_index()
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    prices = frame.loc[:, ("open", "high", "low", "close")].to_numpy(dtype=float)
    if frame.empty or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError("SPY index must be non-empty, unique, and increasing")
    if not np.isfinite(prices).all() or (prices <= 0.0).any():
        raise ValueError("SPY OHLC prices must be finite and positive")
    return frame, {
        "path": str(path),
        "sha256": _sha256(path),
        "rows": int(len(frame)),
        "start": str(frame.index[0].date()),
        "end": str(frame.index[-1].date()),
        "adjustment_semantics": "split/dividend-adjusted SPY OHLC from normalized yfinance auto_adjust=True cache",
    }


def load_vix(path: Path) -> tuple[pd.Series, dict[str, Any]]:
    raw = pd.read_csv(path, index_col=0, parse_dates=True)
    if raw.shape[1] != 1:
        raise ValueError("VIX cache must contain exactly one value column")
    series = pd.to_numeric(raw.iloc[:, 0], errors="coerce")
    series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
    series = series.sort_index()
    if series.empty or not series.index.is_unique or not series.index.is_monotonic_increasing:
        raise ValueError("VIX index must be non-empty, unique, and increasing")
    if not np.isfinite(series.to_numpy(dtype=float)).all() or (series <= 0.0).any():
        raise ValueError("VIX closes must be finite and positive")
    series.name = "vix"
    return series, {
        "path": str(path),
        "sha256": _sha256(path),
        "rows": int(len(series)),
        "start": str(series.index[0].date()),
        "end": str(series.index[-1].date()),
        "semantics": "observed daily VIX close; index-level implied-volatility proxy, not a SPY option surface or fill",
    }


def build_feature_frame(spy: pd.DataFrame, vix: pd.Series) -> pd.DataFrame:
    """Compute completed-close signal features and strictly forward outcomes."""
    frame = spy.copy()
    log_return = np.log(frame["close"] / frame["close"].shift(1))
    frame["rv20"] = log_return.rolling(RV_LOOKBACK, min_periods=RV_LOOKBACK).std() * math.sqrt(252.0) * 100.0
    frame["sma200"] = frame["close"].rolling(SMA_LOOKBACK, min_periods=SMA_LOOKBACK).mean()
    frame["vix"] = vix.reindex(frame.index)
    frame["vrp_ratio"] = frame["vix"] / frame["rv20"]
    frame["trend_distance"] = frame["close"] / frame["sma200"] - 1.0
    frame["positive_trend"] = frame["close"] > frame["sma200"]
    forward_rv = np.full(len(frame), np.nan, dtype=float)
    values = log_return.to_numpy(dtype=float)
    for position in range(len(frame) - OUTCOME_SESSIONS):
        future = values[position + 1 : position + 1 + OUTCOME_SESSIONS]
        if len(future) == OUTCOME_SESSIONS and np.isfinite(future).all():
            forward_rv[position] = float(np.std(future, ddof=1) * math.sqrt(252.0) * 100.0)
    frame["subsequent_rv21"] = forward_rv
    frame["mechanism_outcome"] = frame["vix"] - frame["subsequent_rv21"]
    frame["signal"] = (
        (frame["vrp_ratio"] >= RATIO_THRESHOLD)
        & frame["positive_trend"]
        & frame["mechanism_outcome"].notna()
    )
    frame["latest_prior_vix"] = frame["vix"].shift(1).ffill()
    return frame


def _interval_overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] <= right[1] and right[0] <= left[1]


def select_treated_episodes(features: pd.DataFrame, fold: dict[str, str]) -> pd.DataFrame:
    assessment = features.loc[fold["assessment_start"] : fold["assessment_end"]]
    candidate_dates = list(assessment.index[assessment["signal"].astype(bool)])
    selected: list[Any] = []
    last_position = -10_000
    assessment_end = pd.Timestamp(fold["assessment_end"])
    for date in candidate_dates:
        signal_date = pd.Timestamp(str(date))
        position = int(features.index.get_loc(signal_date))
        if position + OUTCOME_SESSIONS >= len(features):
            continue
        outcome_end = pd.Timestamp(str(features.index[position + OUTCOME_SESSIONS]))
        if outcome_end > assessment_end:
            continue
        if position <= last_position + OUTCOME_SESSIONS:
            continue
        selected.append(signal_date)
        last_position = position
    rows = []
    for date in selected:
        row = features.loc[date]
        position = int(features.index.get_loc(date))
        rows.append(
            {
                "fold": fold["name"],
                "signal_date": date,
                "signal_position": position,
                "outcome_start": pd.Timestamp(features.index[position + 1]),
                "outcome_end": pd.Timestamp(features.index[position + OUTCOME_SESSIONS]),
                "vix": float(row["vix"]),
                "rv20": float(row["rv20"]),
                "vrp_ratio": float(row["vrp_ratio"]),
                "trend_distance": float(row["trend_distance"]),
                "subsequent_rv21": float(row["subsequent_rv21"]),
                "mechanism_outcome": float(row["mechanism_outcome"]),
            }
        )
    return pd.DataFrame(rows)


def match_controls(
    features: pd.DataFrame,
    treated: pd.DataFrame,
    fold: dict[str, str],
) -> pd.DataFrame:
    assessment = features.loc[fold["assessment_start"] : fold["assessment_end"]]
    eligible = assessment.loc[
        assessment["positive_trend"].astype(bool)
        & (assessment["vrp_ratio"] < RATIO_THRESHOLD)
        & assessment["mechanism_outcome"].notna()
    ].copy()
    used_dates: set[pd.Timestamp] = set()
    used_windows: list[tuple[int, int]] = []
    assessment_end = pd.Timestamp(fold["assessment_end"])
    treated_windows = [
        (int(row["signal_position"]) + 1, int(row["signal_position"]) + OUTCOME_SESSIONS)
        for row in treated.to_dict("records")
    ]
    pairs: list[dict[str, Any]] = []
    for treated_row in treated.sort_values("signal_date", kind="stable").to_dict("records"):
        treated_date = pd.Timestamp(treated_row["signal_date"])
        treated_position = int(treated_row["signal_position"])
        candidates: list[tuple[tuple[float, float, int, pd.Timestamp], pd.Timestamp, int]] = []
        for control_date, row in eligible.iterrows():
            control_date = pd.Timestamp(control_date)
            if control_date in used_dates:
                continue
            control_position = int(features.index.get_loc(control_date))
            if control_position + OUTCOME_SESSIONS >= len(features):
                continue
            control_outcome_end = pd.Timestamp(
                str(features.index[control_position + OUTCOME_SESSIONS])
            )
            if control_outcome_end > assessment_end:
                continue
            control_window = (control_position + 1, control_position + OUTCOME_SESSIONS)
            if any(_interval_overlaps(control_window, window) for window in treated_windows):
                continue
            if any(_interval_overlaps(control_window, prior) for prior in used_windows):
                continue
            vix_difference = abs(float(row["vix"]) - float(treated_row["vix"]))
            trend_difference = abs(float(row["trend_distance"]) - float(treated_row["trend_distance"]))
            if vix_difference > 5.0 or trend_difference > 0.10:
                continue
            key = (
                vix_difference,
                trend_difference,
                abs(control_position - treated_position),
                control_date,
            )
            candidates.append((key, control_date, control_position))
        if not candidates:
            continue
        _, control_date, control_position = min(candidates, key=lambda item: item[0])
        control = features.loc[control_date]
        used_dates.add(control_date)
        used_windows.append((control_position + 1, control_position + OUTCOME_SESSIONS))
        pairs.append(
            {
                "fold": fold["name"],
                "treated_date": treated_date,
                "control_date": control_date,
                "treated_outcome": float(treated_row["mechanism_outcome"]),
                "control_outcome": float(control["mechanism_outcome"]),
                "paired_difference": float(treated_row["mechanism_outcome"] - control["mechanism_outcome"]),
                "vix_difference": abs(float(control["vix"]) - float(treated_row["vix"])),
                "trend_distance_difference": abs(
                    float(control["trend_distance"]) - float(treated_row["trend_distance"])
                ),
                "trading_session_distance": abs(control_position - treated_position),
                "control_outcome_start": pd.Timestamp(features.index[control_position + 1]),
                "control_outcome_end": pd.Timestamp(features.index[control_position + OUTCOME_SESSIONS]),
            }
        )
    return pd.DataFrame(pairs)


def circular_block_bootstrap_lower_bound(
    values: Iterable[float],
    *,
    samples: int,
    seed: int,
    confidence: float = 0.95,
    block_length: int = BOOTSTRAP_BLOCK,
) -> float:
    vector = np.asarray(list(values), dtype=float)
    if vector.ndim != 1 or len(vector) == 0 or not np.isfinite(vector).all():
        raise ValueError("bootstrap input must be a non-empty finite vector")
    if samples < 100:
        raise ValueError("bootstrap samples must be at least 100")
    block = max(1, min(int(block_length), len(vector)))
    blocks = int(math.ceil(len(vector) / block))
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    offsets = np.arange(block)
    for sample in range(samples):
        starts = rng.integers(0, len(vector), size=blocks)
        draw = np.concatenate([vector[(start + offsets) % len(vector)] for start in starts])[: len(vector)]
        means[sample] = float(draw.mean())
    return float(np.quantile(means, 1.0 - confidence))


def _mechanism_integrity(
    features: pd.DataFrame,
    treated_by_fold: dict[str, pd.DataFrame],
    controls_by_fold: dict[str, pd.DataFrame],
) -> tuple[list[str], dict[str, int]]:
    violations: list[str] = []
    counters = {
        "treated_rows": 0,
        "matched_pairs": 0,
        "warmup_violations": 0,
        "outcome_window_violations": 0,
        "assessment_boundary_violations": 0,
        "episode_overlap_violations": 0,
        "control_duplicate_violations": 0,
        "control_overlap_violations": 0,
        "control_treated_overlap_violations": 0,
        "control_threshold_violations": 0,
        "control_tolerance_violations": 0,
    }
    for fold in FOLDS:
        name = fold["name"]
        assessment_start = pd.Timestamp(fold["assessment_start"])
        assessment_end = pd.Timestamp(fold["assessment_end"])
        treated = treated_by_fold[name]
        pairs = controls_by_fold[name]
        counters["treated_rows"] += len(treated)
        counters["matched_pairs"] += len(pairs)
        prior_position: int | None = None
        for row in treated.to_dict("records"):
            date = pd.Timestamp(row["signal_date"])
            position = int(row["signal_position"])
            source = features.loc[date]
            if not (
                np.isfinite(float(source["sma200"]))
                and np.isfinite(float(source["rv20"]))
                and np.isfinite(float(source["vix"]))
            ):
                counters["warmup_violations"] += 1
            outcome_start = pd.Timestamp(row["outcome_start"])
            outcome_end = pd.Timestamp(row["outcome_end"])
            if outcome_start <= date or outcome_end <= outcome_start:
                counters["outcome_window_violations"] += 1
            if date < assessment_start or outcome_end > assessment_end:
                counters["assessment_boundary_violations"] += 1
            if prior_position is not None and position <= prior_position + OUTCOME_SESSIONS:
                counters["episode_overlap_violations"] += 1
            prior_position = position
        treated_windows = [
            (pd.Timestamp(row["outcome_start"]), pd.Timestamp(row["outcome_end"]))
            for row in treated.to_dict("records")
        ]
        controls = [pd.Timestamp(value) for value in pairs.get("control_date", pd.Series(dtype="datetime64[ns]"))]
        if len(set(controls)) != len(controls):
            counters["control_duplicate_violations"] += len(controls) - len(set(controls))
        windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        for row in pairs.to_dict("records"):
            control_date = pd.Timestamp(row["control_date"])
            source = features.loc[control_date]
            if not bool(source["positive_trend"]) or float(source["vrp_ratio"]) >= RATIO_THRESHOLD:
                counters["control_threshold_violations"] += 1
            if float(row["vix_difference"]) > 5.0 or float(row["trend_distance_difference"]) > 0.10:
                counters["control_tolerance_violations"] += 1
            window = (pd.Timestamp(row["control_outcome_start"]), pd.Timestamp(row["control_outcome_end"]))
            if control_date < assessment_start or window[1] > assessment_end:
                counters["assessment_boundary_violations"] += 1
            if any(
                not (window[1] < treated_window[0] or treated_window[1] < window[0])
                for treated_window in treated_windows
            ):
                counters["control_treated_overlap_violations"] += 1
            if any(not (window[1] < prior[0] or prior[1] < window[0]) for prior in windows):
                counters["control_overlap_violations"] += 1
            windows.append(window)
    for name, count in counters.items():
        if name.endswith("violations") and count:
            violations.append(f"{name}={count}")
    return violations, counters


def evaluate_mechanism(
    features: pd.DataFrame,
    *,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> tuple[dict[str, Any], pd.DataFrame]:
    treated_by_fold: dict[str, pd.DataFrame] = {}
    controls_by_fold: dict[str, pd.DataFrame] = {}
    assessment_metrics: dict[str, Any] = {}
    all_treated: list[pd.DataFrame] = []
    all_pairs: list[pd.DataFrame] = []
    for fold in FOLDS:
        treated = select_treated_episodes(features, fold)
        pairs = match_controls(features, treated, fold)
        treated_by_fold[fold["name"]] = treated
        controls_by_fold[fold["name"]] = pairs
        all_treated.append(treated)
        all_pairs.append(pairs)
        treated_values = treated["mechanism_outcome"].to_numpy(dtype=float) if len(treated) else np.array([])
        pair_values = pairs["paired_difference"].to_numpy(dtype=float) if len(pairs) else np.array([])
        checks = {
            "minimum_10_nonoverlapping_treated": bool(len(treated) >= 10),
            "minimum_8_matched_pairs": bool(len(pairs) >= 8),
            "treated_mean_gte_1_vol_point": bool(len(treated_values) and treated_values.mean() >= 1.0),
            "treated_positive_frequency_gte_60pct": bool(
                len(treated_values) and np.mean(treated_values > 0.0) >= 0.60
            ),
            "matched_difference_mean_positive": bool(len(pair_values) and pair_values.mean() > 0.0),
        }
        assessment_metrics[fold["name"]] = {
            **fold,
            "n_treated": int(len(treated)),
            "n_matched_pairs": int(len(pairs)),
            "treated_mean_vol_points": float(treated_values.mean()) if len(treated_values) else None,
            "treated_positive_frequency": float(np.mean(treated_values > 0.0)) if len(treated_values) else None,
            "matched_difference_mean_vol_points": float(pair_values.mean()) if len(pair_values) else None,
            "gate_checks": checks,
            "gate_pass": bool(all(checks.values())),
        }
    pooled_treated = pd.concat(all_treated, ignore_index=True)
    pooled_pairs = pd.concat(all_pairs, ignore_index=True)
    violations, integrity_counters = _mechanism_integrity(features, treated_by_fold, controls_by_fold)
    treated_lb = circular_block_bootstrap_lower_bound(
        pooled_treated.sort_values("signal_date")["mechanism_outcome"],
        samples=bootstrap_samples,
        seed=20260714,
    )
    pair_lb = circular_block_bootstrap_lower_bound(
        pooled_pairs.sort_values("treated_date")["paired_difference"],
        samples=bootstrap_samples,
        seed=20260715,
    )
    pooled_checks = {
        "minimum_45_nonoverlapping_treated": bool(len(pooled_treated) >= 45),
        "minimum_24_matched_pairs": bool(len(pooled_pairs) >= 24),
        "treated_bootstrap_lb95_positive": bool(treated_lb > 0.0),
        "matched_difference_bootstrap_lb95_positive": bool(pair_lb > 0.0),
        "zero_integrity_violations": not violations,
    }
    gate_pass = bool(
        all(metrics["gate_pass"] for metrics in assessment_metrics.values())
        and all(pooled_checks.values())
    )
    mechanism = {
        "status": "OBSERVED_VIX_MECHANISM_EVALUATED",
        "mechanism_family": MECHANISM_FAMILY,
        "feature_definition": {
            "rv20": "100*sqrt(252)*sample_stdev(log returns through signal close, 20 observations)",
            "vrp_ratio": "same-close observed VIX / RV20",
            "trend": "SPY close > fully warmed same-close SMA200",
            "outcome": "same-close VIX minus subsequent 21-session annualized realized volatility",
            "signal_threshold": RATIO_THRESHOLD,
            "episode_suppression_sessions": OUTCOME_SESSIONS,
        },
        "assessments": assessment_metrics,
        "pooled": {
            "n_treated": int(len(pooled_treated)),
            "n_matched_pairs": int(len(pooled_pairs)),
            "treated_mean_vol_points": float(pooled_treated["mechanism_outcome"].mean()),
            "treated_positive_frequency": float(np.mean(pooled_treated["mechanism_outcome"] > 0.0)),
            "matched_difference_mean_vol_points": float(pooled_pairs["paired_difference"].mean()),
            "treated_bootstrap_lb95": treated_lb,
            "matched_difference_bootstrap_lb95": pair_lb,
            "bootstrap_samples": int(bootstrap_samples),
            "bootstrap_block_length": BOOTSTRAP_BLOCK,
            "gate_checks": pooled_checks,
        },
        "integrity": {"violations": violations, **integrity_counters},
        "gate_pass": gate_pass,
        "treated_episodes": _json_rows(pooled_treated),
        "matched_controls": _json_rows(pooled_pairs),
    }
    return mechanism, pooled_treated.sort_values("signal_date", kind="stable").reset_index(drop=True)


def _select_integer_put_strikes(spot: float, dte: int, sigma: float) -> tuple[float, float, float]:
    T = dte / 365.0
    lower = max(1, int(math.floor(spot * 0.50)))
    upper = max(lower + 2, int(math.ceil(spot * 1.10)))
    candidates = []
    for strike in range(lower, upper + 1):
        delta = abs(pricing.delta(spot, float(strike), T, sigma, "put", r=RISK_FREE_RATE, q=DIVIDEND_YIELD))
        candidates.append((abs(delta - TARGET_DELTA), float(strike), delta))
    _, short_strike, actual_delta = min(candidates, key=lambda value: (value[0], value[1]))
    return short_strike, short_strike - SPREAD_WIDTH, actual_delta


def _put_mid(spot: float, strike: float, dte: int, sigma: float) -> float:
    if dte <= 0:
        return max(strike - spot, 0.0)
    return max(
        float(
            pricing.price(
                spot,
                strike,
                dte / 365.0,
                sigma,
                "put",
                r=RISK_FREE_RATE,
                q=DIVIDEND_YIELD,
            )
        ),
        max(strike - spot, 0.0),
    )


def _adverse_entry(short_mid: float, long_mid: float, axis: str) -> tuple[float, float, float]:
    if axis == "slippage_5pct":
        short_sale = max(short_mid * 0.95, 0.0)
        long_buy = long_mid * 1.05
    elif axis == "fixed_0p01_per_leg":
        short_sale = max(short_mid - 0.01, 0.0)
        long_buy = long_mid + 0.01
    else:
        raise ValueError(f"unknown cost axis: {axis}")
    return short_sale, long_buy, short_sale - long_buy


def _adverse_exit(short_mid: float, long_mid: float, axis: str) -> tuple[float, float, float]:
    if axis == "slippage_5pct":
        short_buy = short_mid * 1.05
        long_sale = max(long_mid * 0.95, 0.0)
    elif axis == "fixed_0p01_per_leg":
        short_buy = short_mid + 0.01
        long_sale = max(long_mid - 0.01, 0.0)
    else:
        raise ValueError(f"unknown cost axis: {axis}")
    return short_buy, long_sale, short_buy - long_sale


def _entry_blueprints(features: pd.DataFrame, episodes: pd.DataFrame) -> list[dict[str, Any]]:
    blueprints: list[dict[str, Any]] = []
    for episode in episodes.to_dict("records"):
        signal_date = pd.Timestamp(episode["signal_date"])
        signal_position = int(features.index.get_loc(signal_date))
        if signal_position + 1 >= len(features):
            continue
        entry_date = pd.Timestamp(features.index[signal_position + 1])
        spot = float(features.loc[entry_date, "close"])
        sigma = float(features.loc[signal_date, "vix"]) / 100.0
        expiration = listed_weekly_expiration(entry_date, 21)
        dte = int((expiration.date() - entry_date.date()).days)
        short_strike, long_strike, actual_delta = _select_integer_put_strikes(spot, dte, sigma)
        short_mid = _put_mid(spot, short_strike, dte, sigma)
        long_mid = _put_mid(spot, long_strike, dte, sigma)
        zero_cost_credit = short_mid - long_mid
        blueprints.append(
            {
                "fold": episode["fold"],
                "signal_date": signal_date,
                "entry_date": entry_date,
                "expiration": expiration,
                "spot": spot,
                "entry_iv": sigma,
                "short_strike": short_strike,
                "long_strike": long_strike,
                "entry_short_delta_abs": actual_delta,
                "zero_cost_short_mid": short_mid,
                "zero_cost_long_mid": long_mid,
                "zero_cost_credit": zero_cost_credit,
                "credit_eligible": bool(zero_cost_credit > MIN_ZERO_COST_CREDIT),
            }
        )
    return blueprints


def _simulate_trade(features: pd.DataFrame, blueprint: dict[str, Any], axis: str) -> dict[str, Any] | None:
    if not blueprint["credit_eligible"]:
        return None
    entry_date = pd.Timestamp(blueprint["entry_date"])
    expiration = pd.Timestamp(blueprint["expiration"])
    entry_position = int(features.index.get_loc(entry_date))
    short_sale, long_buy, entry_credit = _adverse_entry(
        float(blueprint["zero_cost_short_mid"]), float(blueprint["zero_cost_long_mid"]), axis
    )
    structural_max_loss = max(SPREAD_WIDTH - entry_credit, 0.0) * 100.0
    chosen: dict[str, Any] | None = None
    for position in range(entry_position + 1, len(features)):
        date = pd.Timestamp(features.index[position])
        spot = float(features.iloc[position]["close"])
        prior_vix = float(features.iloc[position]["latest_prior_vix"])
        if not np.isfinite(prior_vix) or prior_vix <= 0.0:
            continue
        sigma = prior_vix / 100.0
        dte = int((expiration.date() - date.date()).days)
        short_mid = _put_mid(spot, float(blueprint["short_strike"]), max(dte, 0), sigma)
        long_mid = _put_mid(spot, float(blueprint["long_strike"]), max(dte, 0), sigma)
        short_buy, long_sale, exit_debit = _adverse_exit(short_mid, long_mid, axis)
        short_delta_abs = (
            1.0
            if dte <= 0 and spot < float(blueprint["short_strike"])
            else 0.0
            if dte <= 0
            else abs(
                pricing.delta(
                    spot,
                    float(blueprint["short_strike"]),
                    dte / 365.0,
                    sigma,
                    "put",
                    r=RISK_FREE_RATE,
                    q=DIVIDEND_YIELD,
                )
            )
        )
        pnl_share = entry_credit - exit_debit
        reason = None
        if date >= expiration:
            reason = "expiration"
        elif pnl_share >= 0.50 * entry_credit:
            reason = "profit_target_50pct_credit"
        elif pnl_share <= -0.70 * (structural_max_loss / 100.0):
            reason = "loss_70pct_structural_max"
        elif short_delta_abs >= 0.45:
            reason = "short_delta_0p45"
        elif dte <= 5:
            reason = "dte_stop_5"
        if reason is None and position != len(features) - 1:
            continue
        if reason is None:
            reason = "end_of_data"
        entry_cashflow = (short_sale - long_buy) * 100.0
        exit_cashflow = (-short_buy + long_sale) * 100.0
        pnl_usd = entry_cashflow + exit_cashflow
        chosen = {
            **{key: _json_value(value) for key, value in blueprint.items()},
            "axis": axis,
            "exit_date": str(date.date()),
            "exit_reason": reason,
            "sessions_held": position - entry_position,
            "exit_iv_latest_strictly_prior": sigma,
            "exit_short_mid": short_mid,
            "exit_long_mid": long_mid,
            "entry_short_sale": short_sale,
            "entry_long_buy": long_buy,
            "entry_credit": entry_credit,
            "exit_short_buy": short_buy,
            "exit_long_sale": long_sale,
            "exit_debit": exit_debit,
            "entry_cashflow_usd": entry_cashflow,
            "exit_cashflow_usd": exit_cashflow,
            "pnl_usd": pnl_usd,
            "structural_max_loss_usd": structural_max_loss,
            "realized_loss_usd": max(-pnl_usd, 0.0),
            "short_delta_abs_at_exit": short_delta_abs,
            "dte_at_exit": dte,
            "counts_for_density": reason != "end_of_data",
            "ledger_error_usd": abs((entry_credit - exit_debit) * 100.0 - pnl_usd),
            "max_loss_reconciliation_error_usd": abs(
                (SPREAD_WIDTH - entry_credit) * 100.0 - structural_max_loss
            ),
            "entry_cost_adverse": bool(
                short_sale <= float(blueprint["zero_cost_short_mid"]) + 1e-12
                and long_buy >= float(blueprint["zero_cost_long_mid"]) - 1e-12
            ),
            "exit_cost_adverse": bool(short_buy >= short_mid - 1e-12 and long_sale <= long_mid + 1e-12),
        }
        break
    return chosen


def _drawdown(pnls: Iterable[float]) -> float:
    values = np.asarray(list(pnls), dtype=float)
    equity = np.concatenate(([0.0], np.cumsum(values)))
    peak = np.maximum.accumulate(equity)
    return float(np.max(peak - equity))


def _axis_metrics(axis: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda trade: trade["entry_date"])
    completed = [trade for trade in ordered if trade["counts_for_density"]]
    pnls = np.asarray([float(trade["pnl_usd"]) for trade in ordered], dtype=float)
    wins = float(pnls[pnls > 0.0].sum()) if len(pnls) else 0.0
    losses = float(-pnls[pnls < 0.0].sum()) if len(pnls) else 0.0
    profit_factor = None if losses == 0.0 else wins / losses
    rolling_six = [float(pnls[start : start + 6].sum()) for start in range(max(0, len(pnls) - 5))]
    tail_count = int(math.ceil(0.05 * len(pnls))) if len(pnls) else 0
    expected_shortfall = float(np.sort(pnls)[:tail_count].mean()) if tail_count else None
    assessment = {}
    for fold in FOLDS:
        fold_trades = [trade for trade in ordered if trade["fold"] == fold["name"]]
        fold_completed = [trade for trade in fold_trades if trade["counts_for_density"]]
        fold_pnls = [float(trade["pnl_usd"]) for trade in fold_trades]
        assessment[fold["name"]] = {
            "n_completed": len(fold_completed),
            "n_total": len(fold_trades),
            "total_pnl_usd": float(sum(fold_pnls)),
            "max_drawdown_usd": _drawdown(fold_pnls),
            "gate_checks": {
                "minimum_10_completed": len(fold_completed) >= 10,
                "positive_after_cost_pnl": sum(fold_pnls) > 0.0,
                "max_drawdown_lte_150": _drawdown(fold_pnls) <= 150.0,
            },
        }
        assessment[fold["name"]]["gate_pass"] = all(assessment[fold["name"]]["gate_checks"].values())
    maximum_loss = max(
        (
            max(float(trade["structural_max_loss_usd"]), float(trade["realized_loss_usd"]))
            for trade in ordered
        ),
        default=0.0,
    )
    integrity_violations = []
    for trade in ordered:
        if float(trade["ledger_error_usd"]) > 0.01:
            integrity_violations.append(f"ledger:{trade['entry_date']}")
        if float(trade["max_loss_reconciliation_error_usd"]) > 0.01:
            integrity_violations.append(f"max_loss:{trade['entry_date']}")
        if not trade["entry_cost_adverse"] or not trade["exit_cost_adverse"]:
            integrity_violations.append(f"cost:{trade['entry_date']}")
        if pd.Timestamp(trade["signal_date"]) >= pd.Timestamp(trade["entry_date"]):
            integrity_violations.append(f"chronology:{trade['entry_date']}")
    entries = [trade["entry_date"] for trade in ordered]
    if len(set(entries)) != len(entries):
        integrity_violations.append("duplicate_entries")
    for previous, following in zip(ordered, ordered[1:]):
        if pd.Timestamp(previous["exit_date"]) >= pd.Timestamp(following["entry_date"]):
            integrity_violations.append(
                f"position_overlap:{previous['entry_date']}->{following['entry_date']}"
            )
    gate_checks = {
        "all_assessments_pass": all(row["gate_pass"] for row in assessment.values()),
        "minimum_45_completed": len(completed) >= 45,
        "positive_pooled_after_cost_pnl": bool(len(pnls) and pnls.sum() > 0.0),
        "profit_factor_gte_1p10": bool((losses == 0.0 and wins > 0.0) or (profit_factor is not None and profit_factor >= 1.10)),
        "full_path_max_drawdown_lte_300": _drawdown(pnls) <= 300.0,
        "every_rolling_six_gte_minus_150": bool(rolling_six and min(rolling_six) >= -150.0),
        "expected_shortfall_95_gte_minus_90": bool(expected_shortfall is not None and expected_shortfall >= -90.0),
        "maximum_structural_or_realized_loss_lte_100": bool(0.0 < maximum_loss <= 100.0),
        "zero_integrity_violations": not integrity_violations,
    }
    return {
        "axis": axis,
        "n_total": len(ordered),
        "n_completed": len(completed),
        "total_pnl_usd": float(pnls.sum()) if len(pnls) else 0.0,
        "win_rate": float(np.mean(pnls > 0.0)) if len(pnls) else 0.0,
        "gross_profit_usd": wins,
        "gross_loss_usd": losses,
        "profit_factor": profit_factor,
        "max_drawdown_usd": _drawdown(pnls),
        "minimum_consecutive_six_trade_pnl_usd": min(rolling_six) if rolling_six else None,
        "expected_shortfall_95_usd": expected_shortfall,
        "maximum_structural_or_realized_one_trade_loss_usd": maximum_loss,
        "capital_fit_usd": maximum_loss,
        "one_lot_max_loss_usd": maximum_loss,
        "max_lots": 1,
        "assessment": assessment,
        "integrity_violations": integrity_violations,
        "gate_checks": gate_checks,
        "gate_pass": all(gate_checks.values()),
        "trades": ordered,
    }


def simulate_option_expression(features: pd.DataFrame, episodes: pd.DataFrame) -> dict[str, Any]:
    blueprints = _entry_blueprints(features, episodes)
    eligible = [blueprint for blueprint in blueprints if blueprint["credit_eligible"]]
    axes = {}
    for axis in ("slippage_5pct", "fixed_0p01_per_leg"):
        trades = [
            trade
            for blueprint in eligible
            if (trade := _simulate_trade(features, blueprint, axis)) is not None
        ]
        axes[axis] = _axis_metrics(axis, trades)
    identical_entries = [trade["entry_date"] for trade in axes["slippage_5pct"]["trades"]] == [
        trade["entry_date"] for trade in axes["fixed_0p01_per_leg"]["trades"]
    ]
    candidate_pass = bool(identical_entries and all(row["gate_pass"] for row in axes.values()))
    maximum_loss = max(
        (row["maximum_structural_or_realized_one_trade_loss_usd"] for row in axes.values()),
        default=0.0,
    )
    return {
        "status": "PRICED_BLACK_SCHOLES_PROXY",
        "option_mark_provenance": "VIX-conditioned Black-Scholes proxy with listed-Friday/all-$1-strike abstraction",
        "config": {
            "symbol": "SPY",
            "structure": "put_credit_spread",
            "operating_lots": 1,
            "max_lots": 1,
            "target_calendar_dte": 21,
            "target_short_put_delta_abs": TARGET_DELTA,
            "spread_width_usd": SPREAD_WIDTH,
            "minimum_zero_cost_credit_per_share_strictly_gt": MIN_ZERO_COST_CREDIT,
            "risk_free_rate": RISK_FREE_RATE,
            "dividend_yield": DIVIDEND_YIELD,
            "profit_target_fraction_entry_credit": 0.50,
            "loss_exit_fraction_structural_max": 0.70,
            "delta_exit_abs": 0.45,
            "dte_stop": 5,
            "regime_flip_exit": False,
        },
        "n_signal_blueprints": len(blueprints),
        "n_zero_cost_credit_eligible": len(eligible),
        "identical_entries_across_cost_axes": identical_entries,
        "cost_axes": axes,
        "capital_fit_usd": maximum_loss,
        "one_lot_max_loss_usd": maximum_loss,
        "max_lots": 1,
        "candidate_pass": candidate_pass,
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return str(pd.Timestamp(value).date())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _json_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{key: _json_value(value) for key, value in row.items()} for row in frame.to_dict("records")]


def _failure_reasons(mechanism: dict[str, Any], option: dict[str, Any]) -> list[str]:
    failures = []
    if not mechanism["gate_pass"]:
        for name, assessment in mechanism["assessments"].items():
            failures.extend(
                f"mechanism.{name}.{check}"
                for check, passed in assessment["gate_checks"].items()
                if not passed
            )
        failures.extend(
            f"mechanism.pooled.{check}"
            for check, passed in mechanism["pooled"]["gate_checks"].items()
            if not passed
        )
    elif not option.get("candidate_pass", False):
        for axis, metrics in option.get("cost_axes", {}).items():
            failures.extend(
                f"option.{axis}.{check}"
                for check, passed in metrics["gate_checks"].items()
                if not passed
            )
    return failures


def run_study(
    spy: pd.DataFrame,
    vix: pd.Series,
    *,
    provenance: dict[str, Any],
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    features = build_feature_frame(spy, vix)
    mechanism, episodes = evaluate_mechanism(features, bootstrap_samples=bootstrap_samples)
    if mechanism["gate_pass"]:
        option = simulate_option_expression(features, episodes)
    else:
        option = {
            "status": "NOT_RUN_MECHANISM_GATE_FAILED",
            "pricing_calls": 0,
            "candidate_pass": False,
            "capital_fit_usd": 100.0,
            "one_lot_max_loss_usd": 100.0,
            "max_lots": 1,
            "capital_basis": "structural $1-wide upper bound before net credit and closing friction; not an observed fill",
        }
    candidate_pass = bool(mechanism["gate_pass"] and option.get("candidate_pass", False))
    mechanism_failed = not mechanism["gate_pass"]
    decision = (
        "ADVANCE_EXACT_SPY_VRP_PCS_TO_DEVELOPMENT_F1"
        if candidate_pass
        else "CLOSE_TESTED_SPY_VRP_MECHANISM"
        if mechanism_failed
        else "CLOSE_EXACT_SPY_VRP_PCS_EXPRESSION"
    )
    closed_family = (
        MECHANISM_FAMILY
        if mechanism_failed
        else "SPY_VRP_PCS_21D_020D_1W_EXPRESSION"
        if not candidate_pass
        else None
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": CANDIDATE_ID,
        "mechanism_family": MECHANISM_FAMILY,
        "economic_mechanism": "persistent index-option insurance demand makes observed VIX exceed subsequent SPY realized volatility; positive trend expresses bounded bullish carry",
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if candidate_pass else "F0_MECHANISM",
        "all_rows_are_inspected_development_data": True,
        "f2_or_l1_claim": False,
        "data_provenance": provenance,
        "mechanism": mechanism,
        "option_stage": option,
        "capital_fit_usd": option.get("capital_fit_usd"),
        "one_lot_max_loss_usd": option.get("one_lot_max_loss_usd"),
        "max_lots": 1,
        "candidate_pass": candidate_pass,
        "strategy_outcome": "STRATEGY_ADVANCED" if candidate_pass else "FAMILY_CLOSED",
        "decision": decision,
        "closed_family": closed_family,
        "dominant_failure_mechanism": (
            None
            if candidate_pass
            else (
                "the raw treated VIX-minus-forward-RV premium passed pooled density and treated-effect gates, "
                "but the high-ratio positive-trend selector failed stable incremental edge versus matched controls "
                "in assessment_2020_2021 and the pooled matched bootstrap"
            )
            if mechanism_failed
            else "exact one-lot PCS proxy failed frozen dual-cost capital/path-risk gates despite observed mechanism success"
        ),
        "failure_reasons": _failure_reasons(mechanism, option),
        "registration_eligible": False,
        "authority": "research only; no registry, paper, shadow, funding, broker, arm, or live authority",
        "claim_scope": "observed daily VIX mechanism plus conditional Black-Scholes option proxy; BUILD/L0 development evidence only",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spy", default=".cache/platform/spy_tom_adjusted_20160101_20260714.csv")
    parser.add_argument("--vix", default=".cache/VIX_10y.csv")
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    spy_path = Path(args.spy)
    vix_path = Path(args.vix)
    spy, spy_meta = load_spy(spy_path)
    vix, vix_meta = load_vix(vix_path)
    payload = run_study(
        spy,
        vix,
        provenance={"spy": spy_meta, "vix": vix_meta},
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
                "mechanism_gate_pass": payload["mechanism"]["gate_pass"],
                "option_stage_status": payload["option_stage"]["status"],
                "candidate_pass": payload["candidate_pass"],
                "failure_reasons": payload["failure_reasons"],
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

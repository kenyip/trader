#!/usr/bin/env python3
"""Leakage-safe SPY turn-of-month event study and conditional PCS experiment.

Research-only BUILD/L0. Calendar labels are outcome-independent. Option pricing is
forbidden unless the adjusted-underlying train and untouched-holdout gates pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def _validate_adjusted_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(_REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"missing adjusted OHLCV columns: {missing}")
    if frame.empty or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError("adjusted OHLCV index must be non-empty, unique, and increasing")
    prepared = frame.loc[:, _REQUIRED_COLUMNS].copy()
    for column in _REQUIRED_COLUMNS:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    prices = prepared.loc[:, ("open", "high", "low", "close")]
    if not np.isfinite(prices.to_numpy(dtype=float)).all() or (prices <= 0.0).any().any():
        raise ValueError("adjusted OHLC prices must be finite and positive")
    return prepared


def _path_metrics(frame: pd.DataFrame, entry_pos: int, hold_sessions: int = 5) -> dict[str, Any]:
    exit_pos = entry_pos + hold_sessions
    entry_close = float(frame.iloc[entry_pos]["close"])
    exit_close = float(frame.iloc[exit_pos]["close"])
    future_lows = frame.iloc[entry_pos + 1 : exit_pos + 1]["low"]
    mae = float(future_lows.min()) / entry_close - 1.0
    return {
        "entry_date": pd.Timestamp(frame.index[entry_pos]),
        "exit_date": pd.Timestamp(frame.index[exit_pos]),
        "return_5s": exit_close / entry_close - 1.0,
        "mae_5s": mae,
        "drawdown_2pct": bool(mae <= -0.02),
    }


def build_monthly_event_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Build paired month-start, tenth-session, and weekday-matched control rows."""
    prepared = _validate_adjusted_frame(frame)
    rows: list[dict[str, Any]] = []
    month_keys = prepared.index.to_period("M")
    for month, month_frame in prepared.groupby(month_keys, sort=True):
        month_positions = prepared.index.get_indexer(month_frame.index)
        if len(month_positions) < 17:
            continue
        event_pos = int(month_positions[0])
        placebo_pos = int(month_positions[9])
        event_weekday = pd.Timestamp(prepared.index[event_pos]).weekday()
        complement_candidates = [
            int(pos)
            for pos in month_positions[11:17]
            if pd.Timestamp(prepared.index[int(pos)]).weekday() == event_weekday
        ]
        complement_pos = complement_candidates[0] if complement_candidates else None
        required_positions = [event_pos, placebo_pos]
        if complement_pos is not None:
            required_positions.append(complement_pos)
        if max(required_positions) + 5 >= len(prepared):
            continue
        event = _path_metrics(prepared, event_pos)
        placebo = _path_metrics(prepared, placebo_pos)
        complement = (
            _path_metrics(prepared, complement_pos)
            if complement_pos is not None
            else {
                "entry_date": pd.NaT,
                "exit_date": pd.NaT,
                "return_5s": np.nan,
                "mae_5s": np.nan,
                "drawdown_2pct": None,
            }
        )
        rows.append(
            {
                "month": str(month),
                "event_entry_date": event["entry_date"],
                "event_exit_date": event["exit_date"],
                "event_return_5s": event["return_5s"],
                "event_mae_5s": event["mae_5s"],
                "event_drawdown_2pct": event["drawdown_2pct"],
                "placebo_entry_date": placebo["entry_date"],
                "placebo_exit_date": placebo["exit_date"],
                "placebo_return_5s": placebo["return_5s"],
                "placebo_mae_5s": placebo["mae_5s"],
                "placebo_drawdown_2pct": placebo["drawdown_2pct"],
                "complement_entry_date": complement["entry_date"],
                "complement_exit_date": complement["exit_date"],
                "complement_available": complement_pos is not None,
                "complement_return_5s": complement["return_5s"],
                "complement_mae_5s": complement["mae_5s"],
                "complement_drawdown_2pct": complement["drawdown_2pct"],
            }
        )
    return pd.DataFrame(rows)


def _block_bootstrap_mean_lower_bound(
    values: np.ndarray,
    *,
    confidence: float = 0.90,
    block_length: int = 3,
    samples: int = 5000,
    seed: int = 20260714,
) -> float:
    series = np.asarray(values, dtype=float)
    if series.ndim != 1 or len(series) == 0 or not np.isfinite(series).all():
        raise ValueError("bootstrap values must be a non-empty finite vector")
    if samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    block = max(1, min(int(block_length), len(series)))
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    n_blocks = int(np.ceil(len(series) / block))
    for sample_index in range(samples):
        starts = rng.integers(0, len(series), size=n_blocks)
        draw = np.concatenate(
            [series[(start + np.arange(block)) % len(series)] for start in starts]
        )[: len(series)]
        means[sample_index] = float(draw.mean())
    return float(np.quantile(means, 1.0 - confidence))


def _partition_metrics(
    rows: pd.DataFrame,
    *,
    min_events: int,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    event = pd.to_numeric(rows["event_return_5s"], errors="coerce").to_numpy(dtype=float)
    placebo = pd.to_numeric(rows["placebo_return_5s"], errors="coerce").to_numpy(dtype=float)
    complement = pd.to_numeric(rows["complement_return_5s"], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(event).all() or not np.isfinite(placebo).all():
        raise ValueError("event and placebo returns must be finite")
    complement_mask = np.isfinite(complement)
    if not complement_mask.any():
        raise ValueError("at least one exact weekday-matched complement is required")
    paired_placebo = event - placebo
    paired_complement = event[complement_mask] - complement[complement_mask]
    event_drawdown = rows["event_drawdown_2pct"].astype(bool).to_numpy()
    placebo_drawdown = rows["placebo_drawdown_2pct"].astype(bool).to_numpy()
    complement_drawdown = rows.loc[complement_mask, "complement_drawdown_2pct"].astype(bool).to_numpy()
    metrics: dict[str, Any] = {
        "n_events": int(len(rows)),
        "n_complement_pairs": int(complement_mask.sum()),
        "complement_unavailable_months": rows.loc[~complement_mask, "month"].astype(str).tolist(),
        "start_month": str(rows.iloc[0]["month"]) if len(rows) else None,
        "end_month": str(rows.iloc[-1]["month"]) if len(rows) else None,
        "event_mean_return": float(event.mean()) if len(event) else float("nan"),
        "event_median_return": float(np.median(event)) if len(event) else float("nan"),
        "event_positive_frequency": float(np.mean(event > 0.0)) if len(event) else float("nan"),
        "event_drawdown_2pct_frequency": float(event_drawdown.mean()) if len(rows) else float("nan"),
        "event_drawdown_2pct_frequency_complement_matched": float(event_drawdown[complement_mask].mean()),
        "placebo_mean_return": float(placebo.mean()) if len(placebo) else float("nan"),
        "placebo_drawdown_2pct_frequency": float(placebo_drawdown.mean()) if len(rows) else float("nan"),
        "complement_mean_return": float(complement[complement_mask].mean()),
        "complement_drawdown_2pct_frequency": float(complement_drawdown.mean()),
        "paired_excess_placebo_mean": float(paired_placebo.mean()) if len(rows) else float("nan"),
        "paired_excess_complement_mean": float(paired_complement.mean()) if len(rows) else float("nan"),
        "paired_excess_placebo_bootstrap_lb90": _block_bootstrap_mean_lower_bound(
            paired_placebo, samples=bootstrap_samples, seed=seed
        ),
        "paired_excess_complement_bootstrap_lb90": _block_bootstrap_mean_lower_bound(
            paired_complement, samples=bootstrap_samples, seed=seed + 1
        ),
    }
    metrics["gate_checks"] = {
        "minimum_events": bool(metrics["n_events"] >= min_events),
        "minimum_complement_pairs": bool(metrics["n_complement_pairs"] >= min_events),
        "positive_event_mean": bool(metrics["event_mean_return"] > 0.0),
        "positive_event_median": bool(metrics["event_median_return"] > 0.0),
        "positive_mean_excess_vs_placebo": bool(metrics["paired_excess_placebo_mean"] > 0.0),
        "positive_mean_excess_vs_complement": bool(metrics["paired_excess_complement_mean"] > 0.0),
        "bootstrap_lb90_vs_placebo_positive": bool(metrics["paired_excess_placebo_bootstrap_lb90"] > 0.0),
        "bootstrap_lb90_vs_complement_positive": bool(metrics["paired_excess_complement_bootstrap_lb90"] > 0.0),
        "drawdown_2pct_no_worse_than_placebo": bool(
            metrics["event_drawdown_2pct_frequency"] <= metrics["placebo_drawdown_2pct_frequency"]
        ),
        "drawdown_2pct_no_worse_than_complement": bool(
            metrics["event_drawdown_2pct_frequency_complement_matched"]
            <= metrics["complement_drawdown_2pct_frequency"]
        ),
    }
    metrics["gate_pass"] = bool(all(metrics["gate_checks"].values()))
    return metrics


def evaluate_underlying_partitions(
    rows: pd.DataFrame,
    *,
    train_fraction: float = 0.60,
    bootstrap_samples: int = 5000,
) -> dict[str, Any]:
    """Evaluate frozen 60/40 month partitions without using outcomes for selection."""
    if not 0.50 <= float(train_fraction) <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    if rows.empty or "month" not in rows.columns:
        raise ValueError("paired monthly event rows are required")
    ordered = rows.sort_values("month", kind="stable").reset_index(drop=True)
    if ordered["month"].duplicated().any():
        raise ValueError("event-study months must be unique")
    split = int(len(ordered) * train_fraction)
    train = ordered.iloc[:split].copy()
    holdout = ordered.iloc[split:].copy()
    if train.empty or holdout.empty or str(train.iloc[-1]["month"]) >= str(holdout.iloc[0]["month"]):
        raise ValueError("train and untouched holdout must be non-empty and chronological")
    train_metrics = _partition_metrics(
        train, min_events=48, bootstrap_samples=bootstrap_samples, seed=20260714
    )
    holdout_metrics = _partition_metrics(
        holdout, min_events=24, bootstrap_samples=bootstrap_samples, seed=20260716
    )
    return {
        "train_fraction": float(train_fraction),
        "train": train_metrics,
        "untouched_holdout": holdout_metrics,
        "underlying_gate_pass": bool(train_metrics["gate_pass"] and holdout_metrics["gate_pass"]),
    }


def tom_pcs_config() -> dict[str, Any]:
    """Frozen one-lot, $1-wide, 21-DTE approximately 0.20-delta PCS DNA."""
    return {
        "structure": "put_credit_spread",
        "long_dte": 21,
        "long_target_delta": 0.20,
        "spread_width": 1.0,
        "min_credit_pct": 0.0,
        "iv_rank_min": 0.0,
        "profit_target": 0.50,
        "loss_exit_multiple_of_credit": 2.0,
        "max_hold_sessions": 5,
        "max_loss_budget_usd": 125.0,
        "risk_free_rate": 0.04,
    }


def conditionally_run_option_stage(
    underlying: dict[str, Any], option_runner: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """Enforce the outcome-gated boundary: no option pricing after underlying failure."""
    if not bool(underlying.get("underlying_gate_pass", False)):
        return {
            "status": "NOT_RUN_UNDERLYING_GATE_FAILED",
            "candidate_pass": False,
            "pricing_calls": 0,
            "capital_fit_usd": 100.0,
            "one_lot_max_loss_usd": 100.0,
            "max_lots": 1,
            "capital_basis": "structural $1-wide vertical upper bound before net credit; not an observed fill",
        }
    result = option_runner()
    if not isinstance(result, dict):
        raise TypeError("option_runner must return a dictionary")
    return result


def _option_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = _validate_adjusted_frame(frame)
    log_return = np.log(prepared["close"] / prepared["close"].shift(1))
    prepared["iv_proxy"] = (
        log_return.rolling(30, min_periods=30).std().shift(1) * np.sqrt(252.0)
    )
    prepared["iv_rank"] = 100.0
    prepared["regime"] = "neutral"
    return prepared


def _serialize_event_rows(event_rows: pd.DataFrame) -> list[dict[str, Any]]:
    """Return strict-JSON rows while preserving unavailable control observations."""
    serialized = event_rows.copy()
    for column in serialized.columns:
        if column.endswith("_date"):
            serialized[column] = serialized[column].map(
                lambda value: None
                if pd.isna(value)
                else str(pd.Timestamp(value).date())
            )
    serialized = serialized.astype(object).where(pd.notna(serialized), None)
    return serialized.to_dict(orient="records")


def _spy_contract_grid(entry_date: pd.Timestamp, spot: float, target_dte: int) -> dict[str, Any]:
    from trader_platform.research.pcs_sim import listed_weekly_expiration

    expiration = listed_weekly_expiration(entry_date, target_dte)
    low = max(1, int(np.floor(spot * 0.65)))
    high = int(np.ceil(spot * 1.10))
    strikes = [float(value) for value in range(low, high + 1)]
    return {str(expiration.date()): {"put": strikes}}


def _simulate_option_axis(
    feature_frame: pd.DataFrame,
    event_rows: pd.DataFrame,
    *,
    axis: str,
    cost_config: dict[str, float],
    min_trades: int,
) -> dict[str, Any]:
    from trader_platform.research.pcs_sim import pick_pcs_entry

    config = {**tom_pcs_config(), **cost_config}
    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for raw_entry in event_rows["event_entry_date"]:
        entry_date = pd.Timestamp(raw_entry)
        if entry_date not in feature_frame.index:
            skipped.append({"entry": str(entry_date.date()), "reason": "missing_entry_bar"})
            continue
        entry_pos = int(feature_frame.index.get_loc(entry_date))
        if entry_pos + int(config["max_hold_sessions"]) >= len(feature_frame):
            skipped.append({"entry": str(entry_date.date()), "reason": "insufficient_forward_bars"})
            continue
        row = feature_frame.iloc[entry_pos]
        sigma = float(row.get("iv_proxy") or 0.0)
        if not np.isfinite(sigma) or sigma <= 0.0:
            skipped.append({"entry": str(entry_date.date()), "reason": "missing_lagged_volatility"})
            continue
        spot = float(row["close"])
        trade = pick_pcs_entry(
            row,
            spot,
            entry_date,
            config,
            contract_grid=_spy_contract_grid(entry_date, spot, int(config["long_dte"])),
            require_contract_grid=True,
        )
        if trade is None:
            skipped.append({"entry": str(entry_date.date()), "reason": "no_valid_credit_spread"})
            continue
        exit_date = entry_date
        exit_debit = trade.net_credit
        exit_reason = "mandatory_5_session"
        for hold_sessions in range(1, int(config["max_hold_sessions"]) + 1):
            current_date = pd.Timestamp(feature_frame.index[entry_pos + hold_sessions])
            current = feature_frame.iloc[entry_pos + hold_sessions]
            current_iv = float(current.get("iv_proxy") or 0.0)
            if not np.isfinite(current_iv) or current_iv <= 0.0:
                current_iv = trade.iv_at_entry
            mark = trade.mark_net_debit(
                float(current["close"]),
                current_iv,
                current_date,
                r=float(config["risk_free_rate"]),
                half_spread_per_leg=float(config.get("half_spread_per_leg", 0.0)),
            )
            exit_debit = min(
                float(trade.width),
                float(mark["net_debit"]) * (1.0 + float(config.get("slippage_pct", 0.0))),
            )
            exit_date = current_date
            pnl_share = float(trade.net_credit - exit_debit)
            if pnl_share >= float(config["profit_target"]) * float(trade.net_credit):
                exit_reason = "profit_target"
                break
            if pnl_share <= -float(config["loss_exit_multiple_of_credit"]) * float(trade.net_credit):
                exit_reason = "two_x_credit_loss"
                break
        pnl_usd = (float(trade.net_credit) - exit_debit) * 100.0
        trades.append(
            {
                "entry": str(entry_date.date()),
                "exit": str(exit_date.date()),
                "sessions_held": int(feature_frame.index.get_loc(exit_date) - entry_pos),
                "short_strike": float(trade.short_strike),
                "long_strike": float(trade.long_strike),
                "width": float(trade.width),
                "entry_credit": float(trade.net_credit),
                "exit_debit": float(exit_debit),
                "pnl_usd": float(pnl_usd),
                "max_loss_usd": float(trade.max_loss_per_share * 100.0),
                "exit_reason": exit_reason,
            }
        )
    pnl = np.asarray([trade["pnl_usd"] for trade in trades], dtype=float)
    equity = np.cumsum(pnl)
    equity_with_zero = np.concatenate(([0.0], equity))
    peak = np.maximum.accumulate(equity_with_zero)
    max_dd = float((peak - equity_with_zero).max()) if len(trades) else 0.0
    max_loss = max((float(trade["max_loss_usd"]) for trade in trades), default=0.0)
    chunks = [trades[start : start + 6] for start in range(0, len(trades), 6)]
    dense_negative = [
        chunk
        for chunk in chunks
        if len(chunk) >= 3 and sum(float(trade["pnl_usd"]) for trade in chunk) < 0.0
    ]
    integrity = bool(
        len({trade["entry"] for trade in trades}) == len(trades)
        and all(1 <= int(trade["sessions_held"]) <= 5 for trade in trades)
        and all(float(trade["max_loss_usd"]) <= 125.0 + 1e-9 for trade in trades)
        and all(
            -float(trade["max_loss_usd"]) - 1e-6 <= float(trade["pnl_usd"])
            <= float(trade["entry_credit"]) * 100.0 + 1e-6
            for trade in trades
        )
    )
    gate_checks = {
        "minimum_trades": bool(len(trades) >= min_trades),
        "positive_after_cost_pnl": bool(float(pnl.sum()) > 0.0) if len(trades) else False,
        "max_loss_usd_lte_125": bool(max_loss > 0.0 and max_loss <= 125.0),
        "max_drawdown_usd_lte_75": bool(max_dd <= 75.0),
        "dense_negative_windows_lte_5": bool(len(dense_negative) <= 5),
        "integrity": integrity,
    }
    return {
        "axis": axis,
        "n_requested_events": int(len(event_rows)),
        "n_trades": int(len(trades)),
        "n_skipped": int(len(skipped)),
        "skipped": skipped,
        "total_pnl_usd": float(pnl.sum()) if len(pnl) else 0.0,
        "win_rate": float(np.mean(pnl > 0.0)) if len(pnl) else 0.0,
        "max_drawdown_usd": max_dd,
        "one_lot_max_loss_usd": max_loss,
        "capital_fit_usd": max_loss,
        "max_lots": 1 if 0.0 < max_loss <= 125.0 else 0,
        "dense_negative_windows": int(len(dense_negative)),
        "integrity": integrity,
        "gate_checks": gate_checks,
        "gate_pass": bool(all(gate_checks.values())),
        "trades": trades,
    }


def simulate_tom_pcs(
    adjusted_frame: pd.DataFrame,
    event_rows: pd.DataFrame,
    *,
    train_fraction: float = 0.60,
) -> dict[str, Any]:
    feature_frame = _option_feature_frame(adjusted_frame)
    split = int(len(event_rows) * train_fraction)
    partitions = {
        "train": (event_rows.iloc[:split].copy(), 48),
        "untouched_holdout": (event_rows.iloc[split:].copy(), 24),
    }
    costs = {
        "slippage_5pct": {"slippage_pct": 0.05, "half_spread_per_leg": 0.0},
        "fixed_0p01_per_leg": {"slippage_pct": 0.0, "half_spread_per_leg": 0.01},
    }
    output: dict[str, Any] = {}
    for partition_name, (partition_rows, minimum) in partitions.items():
        output[partition_name] = {
            axis: _simulate_option_axis(
                feature_frame,
                partition_rows,
                axis=axis,
                cost_config=cost_config,
                min_trades=minimum,
            )
            for axis, cost_config in costs.items()
        }
    all_rows = [
        output[partition][axis]
        for partition in ("train", "untouched_holdout")
        for axis in costs
    ]
    max_loss = max((float(row["one_lot_max_loss_usd"]) for row in all_rows), default=0.0)
    candidate_pass = bool(all(row["gate_pass"] for row in all_rows))
    return {
        "status": "PRICED_BLACK_SCHOLES_PROXY",
        "option_mark_provenance": "black_scholes_proxy_realized_volatility",
        "pricing_calls": int(sum(row["n_requested_events"] for row in all_rows)),
        "config": tom_pcs_config(),
        "cost_axes": costs,
        "train": output["train"],
        "untouched_holdout": output["untouched_holdout"],
        "capital_fit_usd": max_loss,
        "one_lot_max_loss_usd": max_loss,
        "max_lots": 1 if 0.0 < max_loss <= 125.0 else 0,
        "candidate_pass": candidate_pass,
    }


def load_adjusted_spy(
    *, start: str, end: str, cache_path: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load split/dividend-adjusted SPY OHLCV and persist a normalized evidence cache."""
    source = "normalized_cache_from_yfinance_auto_adjust_true"
    if cache_path.exists():
        frame = pd.read_csv(cache_path, index_col=0, parse_dates=True)
    else:
        import yfinance as yf

        raw = yf.download(
            "SPY",
            start=start,
            end=str((pd.Timestamp(end) + pd.Timedelta(days=1)).date()),
            auto_adjust=True,
            progress=False,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        frame = raw.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
        frame.columns = list(_REQUIRED_COLUMNS)
        source = "yfinance_auto_adjust_true"
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = _validate_adjusted_frame(frame).sort_index()
    frame = frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index <= pd.Timestamp(end))]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, date_format="%Y-%m-%d", float_format="%.10f")
    data_hash = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    metadata = {
        "source": source,
        "auto_adjust": True,
        "adjustment_semantics": "yfinance split/dividend-adjusted OHLC; volume retained",
        "cache_path": str(cache_path),
        "sha256": data_hash,
        "rows": int(len(frame)),
        "start": str(frame.index[0].date()),
        "end": str(frame.index[-1].date()),
    }
    return frame, metadata


def _underlying_failure_reasons(underlying: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for partition in ("train", "untouched_holdout"):
        for check, passed in underlying[partition]["gate_checks"].items():
            if not passed:
                failures.append(f"{partition}.{check}")
    return failures


def run_lab(
    adjusted_frame: pd.DataFrame,
    *,
    data_provenance: dict[str, Any],
    train_fraction: float = 0.60,
    bootstrap_samples: int = 5000,
) -> dict[str, Any]:
    event_rows = build_monthly_event_rows(adjusted_frame)
    underlying = evaluate_underlying_partitions(
        event_rows,
        train_fraction=train_fraction,
        bootstrap_samples=bootstrap_samples,
    )
    option_stage = conditionally_run_option_stage(
        underlying,
        lambda: simulate_tom_pcs(
            adjusted_frame,
            event_rows,
            train_fraction=train_fraction,
        ),
    )
    candidate_pass = bool(
        underlying["underlying_gate_pass"] and option_stage.get("candidate_pass", False)
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_PROXY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": "SPY_TOM_PCS_21D_020D_1W",
        "hypothesis_id": "spy-turn-of-month-first-session-5day-pcs-21dte-020delta-1wide-dualcost-60-40-v1",
        "structure": "put_credit_spread",
        "economic_mechanism": "beginning-of-month retirement, payroll, and institutional allocation flows produce a short bullish SPY drift",
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F2_UNTOUCHED_HOLDOUT" if candidate_pass else "F0_MECHANISM",
        "data_provenance": data_provenance,
        "selection": {
            "event": "first completed trading session of each calendar month",
            "hold_sessions": 5,
            "placebo": "tenth completed trading session of the same month",
            "complement": "earliest session among positions 12-17 with the same weekday as the event session",
            "outcome_independent": True,
            "train_fraction": train_fraction,
            "mutation_allowed": False,
        },
        "underlying": underlying,
        "option_stage": option_stage,
        "capital_fit_usd": option_stage.get("capital_fit_usd"),
        "one_lot_max_loss_usd": option_stage.get("one_lot_max_loss_usd"),
        "max_lots": option_stage.get("max_lots", 0),
        "candidate_pass": candidate_pass,
        "decision": (
            "DISCOVERY_PASS_SPY_TOM_PCS_REQUIRES_PAPER_CALIBRATION"
            if candidate_pass
            else "REJECT_SPY_TOM_CALENDAR_FLOW_FAMILY"
        ),
        "strategy_outcome": "STRATEGY_ADVANCED" if candidate_pass else "FAMILY_CLOSED",
        "dominant_failure_mechanism": (
            None
            if candidate_pass
            else (
                "underlying calendar effect did not survive chronological paired controls"
                if not underlying["underlying_gate_pass"]
                else "conditional one-lot PCS did not survive train/holdout dual-cost and loss-quality gates"
            )
        ),
        "failure_reasons": _underlying_failure_reasons(underlying),
        "claim_scope": "adjusted SPY underlying event evidence plus conditional Black-Scholes proxy option marks only; BUILD L0; cannot earn L1 or live authority",
        "registration_eligible": False,
        "monthly_rows": _serialize_event_rows(event_rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2026-07-14")
    parser.add_argument("--train-fraction", type=float, default=0.60)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument(
        "--cache",
        default=".cache/platform/spy_tom_adjusted_20160101_20260714.csv",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    frame, provenance = load_adjusted_spy(
        start=args.start,
        end=args.end,
        cache_path=Path(args.cache),
    )
    payload = run_lab(
        frame,
        data_provenance=provenance,
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
                "decision": payload["decision"],
                "strategy_outcome": payload["strategy_outcome"],
                "underlying_gate_pass": payload["underlying"]["underlying_gate_pass"],
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

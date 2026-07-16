#!/usr/bin/env python3
"""Train-only downside-semivariance ETF barrier discovery lab.

BUILD/L0 only. The final chronological holdout remains outcome-unread and no
option pricing occurs unless a later wake earns the right to open that stage.
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
    from scripts.low_hv_cross_section_train_lab import (
        _validate_close_panel,
        assemble_close_panel,
        load_adjusted_history,
        split_blueprints,
    )
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from low_hv_cross_section_train_lab import (  # type: ignore[no-redef]
        _validate_close_panel,
        assemble_close_panel,
        load_adjusted_history,
        split_blueprints,
    )


DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "XLF", "XLE", "XLK", "XLI", "XLV"]


def build_rank_blueprints(
    close_panel: pd.DataFrame,
    *,
    symbols: list[str],
    semivariance_lookback_sessions: int = 60,
    trend_lookback_sessions: int = 100,
    momentum_lookback_sessions: int = 60,
    forward_sessions: int = 10,
) -> list[dict[str, Any]]:
    """Freeze globally non-overlapping rank dates without reading outcomes."""
    panel = _validate_close_panel(close_panel)
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if normalized != list(panel.columns) or normalized != DEFAULT_SYMBOLS:
        raise ValueError("symbols must exactly match the frozen ordered ETF panel")
    if min(
        semivariance_lookback_sessions,
        trend_lookback_sessions,
        momentum_lookback_sessions,
        forward_sessions,
    ) < 1:
        raise ValueError("lookbacks and forward horizon must be positive")

    log_returns = np.log(panel / panel.shift(1))
    downside_squared = log_returns.clip(upper=0.0).pow(2)
    semivariance = downside_squared.rolling(
        semivariance_lookback_sessions,
        min_periods=semivariance_lookback_sessions,
    ).mean() * 252.0
    hv = log_returns.rolling(
        semivariance_lookback_sessions,
        min_periods=semivariance_lookback_sessions,
    ).std() * np.sqrt(252.0)
    spy_prior_sma = panel["SPY"].shift(1).rolling(
        trend_lookback_sessions,
        min_periods=trend_lookback_sessions,
    ).mean()
    spy_momentum = panel["SPY"] / panel["SPY"].shift(momentum_lookback_sessions) - 1.0

    blueprints: list[dict[str, Any]] = []
    previous_exit_position = -1
    last_rank_position = len(panel) - forward_sessions - 2
    for rank_position in range(len(panel)):
        if rank_position > last_rank_position:
            break
        entry_position = rank_position + 1
        exit_position = entry_position + forward_sessions
        if entry_position <= previous_exit_position:
            continue
        regime = (
            float(panel["SPY"].iloc[rank_position]),
            float(spy_prior_sma.iloc[rank_position]),
            float(spy_momentum.iloc[rank_position]),
        )
        if not np.isfinite(regime).all() or not (regime[0] > regime[1] and regime[2] > 0.0):
            continue
        semivar_row = semivariance.iloc[rank_position]
        hv_row = hv.iloc[rank_position]
        if not np.isfinite(semivar_row.to_numpy(dtype=float)).all() or not np.isfinite(
            hv_row.to_numpy(dtype=float)
        ).all():
            continue
        semivar_ordered = sorted(
            ((float(value), str(symbol)) for symbol, value in semivar_row.items()),
            key=lambda item: (item[0], item[1]),
        )
        hv_ordered = sorted(
            ((float(value), str(symbol)) for symbol, value in hv_row.items()),
            key=lambda item: (item[0], item[1]),
        )
        blueprints.append(
            {
                "rank_date": pd.Timestamp(panel.index[rank_position]),
                "feature_max_date": pd.Timestamp(panel.index[rank_position]),
                "entry_date": pd.Timestamp(panel.index[entry_position]),
                "exit_date": pd.Timestamp(panel.index[exit_position]),
                "low_semivariance_symbol": semivar_ordered[0][1],
                "high_semivariance_symbol": semivar_ordered[-1][1],
                "low_semivariance_value": semivar_ordered[0][0],
                "high_semivariance_value": semivar_ordered[-1][0],
                "low_hv_symbol": hv_ordered[0][1],
                "high_hv_symbol": hv_ordered[-1][1],
                "low_hv_value": hv_ordered[0][0],
                "high_hv_value": hv_ordered[-1][0],
                "spy_trend_distance": regime[0] / regime[1] - 1.0,
                "spy_momentum_return": regime[2],
            }
        )
        previous_exit_position = exit_position
    return blueprints


def _worst_decile_mean(values: np.ndarray) -> float | None:
    vector = np.asarray(values, dtype=float)
    if not len(vector):
        return None
    count = max(1, int(np.ceil(len(vector) * 0.10)))
    return float(np.sort(vector)[:count].mean())


def _date_block_lower_bound(
    date_edges: np.ndarray,
    *,
    samples: int,
    block_length: int,
    confidence: float = 0.90,
    seed: int = 20260715,
) -> float:
    vector = np.asarray(date_edges, dtype=float)
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


def evaluate_train_partition(
    close_panel: pd.DataFrame,
    train_blueprints: list[dict[str, Any]],
    *,
    min_rank_dates: int = 60,
    min_symbols: int = 6,
    barrier_return: float = -0.05,
    max_low_breach_rate: float = 0.10,
    min_breach_rate_edge: float = 0.05,
    round_trip_cost_bps: float = 20.0,
    bootstrap_samples: int = 10_000,
    bootstrap_block_length: int = 5,
) -> dict[str, Any]:
    """Read only frozen train outcomes and apply the direct tail-hazard gate."""
    panel = _validate_close_panel(close_panel)
    if list(panel.columns) != DEFAULT_SYMBOLS:
        raise ValueError("close panel must exactly match the frozen ordered ETF panel")
    if not train_blueprints or min(min_rank_dates, min_symbols) < 1:
        raise ValueError("non-empty blueprints and positive density gates are required")
    if not -1.0 < barrier_return < 0.0:
        raise ValueError("barrier return must be negative")
    if not 0.0 <= max_low_breach_rate <= 1.0 or not 0.0 <= min_breach_rate_edge <= 1.0:
        raise ValueError("breach-rate gates must be fractions")
    if not np.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0.0:
        raise ValueError("round-trip cost must be finite and non-negative")

    rows: list[dict[str, Any]] = []
    integrity_violations: list[str] = []
    previous_exit: pd.Timestamp | None = None

    def outcome(symbol: str, entry_date: pd.Timestamp, exit_date: pd.Timestamp) -> dict[str, Any]:
        path = panel.loc[entry_date:exit_date, symbol].astype(float)
        if len(path) < 2 or path.index[0] != entry_date or path.index[-1] != exit_date:
            raise ValueError("path coverage is incomplete")
        entry = float(path.iloc[0])
        minimum_return = float(path.min() / entry - 1.0)
        terminal_after_cost = float(
            path.iloc[-1] / entry - 1.0 - round_trip_cost_bps / 10_000.0
        )
        if not np.isfinite([minimum_return, terminal_after_cost]).all():
            raise ValueError("outcome is nonfinite")
        return {
            "symbol": symbol,
            "minimum_close_return": minimum_return,
            "terminal_return_after_cost": terminal_after_cost,
            "barrier_breached": bool(minimum_return <= barrier_return),
        }

    for index, blueprint in enumerate(train_blueprints):
        rank_date = pd.Timestamp(blueprint["rank_date"])
        feature_max_date = pd.Timestamp(blueprint["feature_max_date"])
        entry_date = pd.Timestamp(blueprint["entry_date"])
        exit_date = pd.Timestamp(blueprint["exit_date"])
        low = str(blueprint["low_semivariance_symbol"]).upper()
        high = str(blueprint["high_semivariance_symbol"]).upper()
        hv_low = str(blueprint["low_hv_symbol"]).upper()
        hv_high = str(blueprint["high_hv_symbol"]).upper()
        selected = {low, high, hv_low, hv_high}
        if not (feature_max_date == rank_date < entry_date < exit_date):
            integrity_violations.append(f"chronology:{index}")
        if previous_exit is not None and entry_date <= previous_exit:
            integrity_violations.append(f"overlap:{index}")
        if low == high or hv_low == hv_high:
            integrity_violations.append(f"rank_groups:{index}")
        if not selected.issubset(panel.columns):
            integrity_violations.append(f"missing_symbol:{index}")
            previous_exit = exit_date
            continue
        if not (
            float(blueprint["low_semivariance_value"])
            < float(blueprint["high_semivariance_value"])
            and float(blueprint["low_hv_value"]) < float(blueprint["high_hv_value"])
        ):
            integrity_violations.append(f"rank_order:{index}")
        try:
            low_outcome = outcome(low, entry_date, exit_date)
            high_outcome = outcome(high, entry_date, exit_date)
            hv_low_outcome = outcome(hv_low, entry_date, exit_date)
            hv_high_outcome = outcome(hv_high, entry_date, exit_date)
        except ValueError as exc:
            integrity_violations.append(f"outcome:{index}:{exc}")
            previous_exit = exit_date
            continue
        rows.append(
            {
                "rank_date": str(rank_date.date()),
                "entry_date": str(entry_date.date()),
                "exit_date": str(exit_date.date()),
                "low_semivariance": low_outcome,
                "high_semivariance": high_outcome,
                "low_hv": hv_low_outcome,
                "high_hv": hv_high_outcome,
                "date_semivariance_breach_edge": float(
                    high_outcome["barrier_breached"] - low_outcome["barrier_breached"]
                ),
                "date_plain_hv_breach_edge": float(
                    hv_high_outcome["barrier_breached"] - hv_low_outcome["barrier_breached"]
                ),
            }
        )
        previous_exit = exit_date

    def vector(side: str, field: str) -> np.ndarray:
        return np.asarray([row[side][field] for row in rows], dtype=float)

    low_breaches = vector("low_semivariance", "barrier_breached")
    high_breaches = vector("high_semivariance", "barrier_breached")
    low_rate = float(low_breaches.mean()) if len(low_breaches) else None
    high_rate = float(high_breaches.mean()) if len(high_breaches) else None
    edge = None if low_rate is None or high_rate is None else high_rate - low_rate
    date_edges = np.asarray([row["date_semivariance_breach_edge"] for row in rows], dtype=float)
    plain_hv_edges = np.asarray([row["date_plain_hv_breach_edge"] for row in rows], dtype=float)
    edge_lb90 = (
        _date_block_lower_bound(
            date_edges,
            samples=bootstrap_samples,
            block_length=bootstrap_block_length,
        )
        if len(date_edges)
        else None
    )
    plain_hv_edge = float(plain_hv_edges.mean()) if len(plain_hv_edges) else None
    low_tail = _worst_decile_mean(vector("low_semivariance", "minimum_close_return"))
    high_tail = _worst_decile_mean(vector("high_semivariance", "minimum_close_return"))
    low_terminal = (
        float(vector("low_semivariance", "terminal_return_after_cost").mean()) if rows else None
    )
    low_symbols = sorted({row["low_semivariance"]["symbol"] for row in rows})
    high_symbols = sorted({row["high_semivariance"]["symbol"] for row in rows})
    gate_checks = {
        "minimum_rank_dates": len(rows) >= min_rank_dates,
        "minimum_low_symbol_breadth": len(low_symbols) >= min_symbols,
        "minimum_high_symbol_breadth": len(high_symbols) >= min_symbols,
        "low_breach_rate_at_most_limit": low_rate is not None and low_rate <= max_low_breach_rate,
        "semivariance_breach_edge_at_least_minimum": edge is not None and edge >= min_breach_rate_edge,
        "date_block_bootstrap_edge_lb90_positive": edge_lb90 is not None and edge_lb90 > 0.0,
        "low_tail_less_severe": low_tail is not None and high_tail is not None and low_tail > high_tail,
        "semivariance_edge_exceeds_plain_hv": edge is not None
        and plain_hv_edge is not None
        and edge > plain_hv_edge,
        "zero_integrity_violations": not integrity_violations,
    }
    return {
        "n_rank_dates": len(rows),
        "n_low_semivariance_episodes": len(rows),
        "n_high_semivariance_episodes": len(rows),
        "low_semivariance_symbols": low_symbols,
        "high_semivariance_symbols": high_symbols,
        "low_semivariance_breach_rate": low_rate,
        "high_semivariance_breach_rate": high_rate,
        "semivariance_breach_rate_edge": edge,
        "date_block_bootstrap_edge_lb90": edge_lb90,
        "plain_hv_breach_rate_edge": plain_hv_edge,
        "low_semivariance_worst_decile_mean_min_return": low_tail,
        "high_semivariance_worst_decile_mean_min_return": high_tail,
        "low_semivariance_mean_terminal_return_after_cost": low_terminal,
        "barrier_return": barrier_return,
        "round_trip_underlying_cost_bps": round_trip_cost_bps,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_block_length_rank_dates": bootstrap_block_length,
        "integrity_violations": integrity_violations,
        "gate_checks": gate_checks,
        "gate_pass": all(gate_checks.values()),
        "rank_dates": rows,
    }


def _holdout_identity(blueprints: list[dict[str, Any]]) -> dict[str, Any]:
    frozen_rows = [
        {
            "rank_date": str(pd.Timestamp(row["rank_date"]).date()),
            "feature_max_date": str(pd.Timestamp(row["feature_max_date"]).date()),
            "entry_date": str(pd.Timestamp(row["entry_date"]).date()),
            "exit_date": str(pd.Timestamp(row["exit_date"]).date()),
            "low_semivariance_symbol": row["low_semivariance_symbol"],
            "high_semivariance_symbol": row["high_semivariance_symbol"],
            "low_hv_symbol": row["low_hv_symbol"],
            "high_hv_symbol": row["high_hv_symbol"],
        }
        for row in blueprints
    ]
    encoded = json.dumps(frozen_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "n_blueprints": len(frozen_rows),
        "first_rank_date": frozen_rows[0]["rank_date"],
        "first_entry_date": frozen_rows[0]["entry_date"],
        "last_rank_date": frozen_rows[-1]["rank_date"],
        "last_exit_date": frozen_rows[-1]["exit_date"],
        "identity_sha256": hashlib.sha256(encoded).hexdigest(),
        "identity_fields": list(frozen_rows[0]),
        "outcome_metrics_read": False,
        "simulation_run": False,
    }


def _dominant_failure_mechanism(failed_gates: list[str]) -> str:
    if failed_gates == ["semivariance_edge_exceeds_plain_hv"]:
        return (
            "mechanism non-specificity only: the downside-semivariance breach edge did not exceed "
            "the same-date plain-HV breach edge; every other frozen train gate passed"
        )
    return "frozen train gate failure(s): " + ", ".join(failed_gates)


def run_lab_from_panel(
    close_panel: pd.DataFrame,
    *,
    symbols: list[str],
    provenance: dict[str, Any],
    train_fraction: float = 0.60,
    semivariance_lookback_sessions: int = 60,
    trend_lookback_sessions: int = 100,
    momentum_lookback_sessions: int = 60,
    forward_sessions: int = 10,
    min_rank_dates: int = 60,
    min_symbols: int = 6,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    panel = _validate_close_panel(close_panel)
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if normalized != list(panel.columns) or normalized != DEFAULT_SYMBOLS:
        raise ValueError("symbols must exactly match the frozen ordered ETF panel")
    blueprints = build_rank_blueprints(
        panel,
        symbols=normalized,
        semivariance_lookback_sessions=semivariance_lookback_sessions,
        trend_lookback_sessions=trend_lookback_sessions,
        momentum_lookback_sessions=momentum_lookback_sessions,
        forward_sessions=forward_sessions,
    )
    train, holdout = split_blueprints(blueprints, train_fraction=train_fraction)
    train_result = evaluate_train_partition(
        panel,
        train,
        min_rank_dates=min_rank_dates,
        min_symbols=min_symbols,
        bootstrap_samples=bootstrap_samples,
    )
    advanced = bool(train_result["gate_pass"])
    failed_gates = [name for name, passed in train_result["gate_checks"].items() if not passed]
    holdout_meta = _holdout_identity(holdout)
    candidate_id = "LOW_DOWNSIDE_SEMIVARIANCE_ETF_PCS_21D_V1"
    family_key = (
        "noncollapse|cross_section_low_downside_semivariance_60d|"
        "liquid_etfs_spy_qqq_iwm_xlf_xle_xlk_xli_xlv|"
        "spy_sma100_uptrend_positive60d|10session_close_barrier5pct|"
        "pcs21d2wide_planned"
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_UNDERLYING_DISCOVERY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": candidate_id,
        "mechanism_family": family_key,
        "economic_mechanism": (
            "persistent cross-sectional left-tail heterogeneity from sector cyclicality, "
            "concentration, and risk-transfer demand makes the lowest prior downside-semivariance "
            "ETF less likely than the highest-ranked control to breach a 5% close barrier over "
            "the next ten sessions inside a broad-market uptrend"
        ),
        "candidate_or_family_scope": (
            "single lowest versus single highest 60-session downside-semivariance rank in the fixed "
            "eight-ETF panel, globally non-overlapping ten-session close paths"
        ),
        "forecast_type": "non_collapse",
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "funnel_claim_f2": False,
        "l1_claim": False,
        "claim_scope": (
            "split/dividend-adjusted underlying closes only; fixed present-day ETF population; "
            "train-only L0 discovery; no option marks, IV, skew, credit, fill, L1, capital-seat, "
            "paper, shadow, arm, broker, or live claim"
        ),
        "falsifier": (
            "fewer than 60 train rank dates/episodes; fewer than six represented symbols on either "
            "selected side; low-rank breach rate above 10%; high-minus-low edge below five percentage "
            "points; non-positive date-block LB90; low worst-decile close path no milder than high; "
            "semivariance edge no stronger than plain-HV diagnostic; or any integrity failure"
        ),
        "config": {
            "symbols": normalized,
            "semivariance_lookback_sessions": semivariance_lookback_sessions,
            "semivariance_definition": (
                "252 times mean squared negative daily log return, with non-negative returns set to zero"
            ),
            "trend_lookback_sessions": trend_lookback_sessions,
            "momentum_lookback_sessions": momentum_lookback_sessions,
            "forward_sessions": forward_sessions,
            "train_fraction": train_fraction,
            "minimum_rank_dates": min_rank_dates,
            "minimum_symbol_breadth_each_side": min_symbols,
            "barrier_return": -0.05,
            "maximum_low_rank_breach_rate": 0.10,
            "minimum_high_minus_low_breach_edge": 0.05,
            "bootstrap_confidence": 0.90,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_block_length_rank_dates": 5,
            "underlying_sensitivity_cost_bps": 20.0,
            "global_non_overlapping_episodes": True,
        },
        "data_provenance": provenance,
        "data_window": {
            "panel_start": str(panel.index[0].date()),
            "panel_end": str(panel.index[-1].date()),
            "train_first_rank_date": str(pd.Timestamp(train[0]["rank_date"]).date()),
            "train_last_rank_date": str(pd.Timestamp(train[-1]["rank_date"]).date()),
        },
        "population_validity": {
            "population_type": "fixed present-day broad and sector ETF panel",
            "population_pure": True,
            "ranking_complete": True,
            "survivorship_bias": True,
            "listing_history_bias": True,
            "composition_change_bias": True,
            "point_in_time_composition": False,
            "generalization_allowed": False,
        },
        "train": train_result,
        "untouched_holdout": holdout_meta,
        "structure": "conditional_put_credit_spread_not_yet_priced",
        "option_entry_filter": {
            "expiration": "nearest listed expiry in range",
            "dte_range": [18, 24],
            "short_put_delta_range": [0.18, 0.25],
            "wing_width_usd": 2.0,
            "minimum_credit_usd": 0.30,
            "maximum_two_leg_nbbo_width_usd": 0.20,
            "positive_bid_required": True,
        },
        "option_stage": {
            "status": "NOT_RUN_PENDING_UNTOUCHED_HOLDOUT" if advanced else "NOT_RUN_TRAIN_GATE_FAILED",
            "pricing_run": False,
            "pricing_calls": 0,
            "option_mark_provenance": None,
        },
        "greek_exposures": {
            "intended": ["positive delta", "positive theta", "short vega", "bounded short gamma"],
            "dangerous": [
                "correlation spike",
                "gap through long wing",
                "volatility/skew expansion",
                "early assignment/dividend",
                "two-leg liquidity",
            ],
        },
        "entry_trigger": (
            "after a completed close, SPY above prior-completed SMA100 with positive 60-session "
            "return; enter next session in the single lowest downside-semivariance ETF"
        ),
        "exit_management_rule": (
            "future PCS: harvest at 50% of entry credit, close after underlying closes 5% below "
            "entry, or hard ten-session time stop"
        ),
        "stand_aside_rule": (
            "stand aside when SPY regime gates fail, rank inputs are incomplete/nonfinite, future "
            "quote/capital gates fail, or any correlated bullish risk unit is already open"
        ),
        "capital_fit_usd": 200.0,
        "one_lot_max_loss_usd": 200.0,
        "max_loss_usd": 200.0,
        "max_lots": 1,
        "portfolio_overlap": "one global correlated bullish risk unit; no simultaneous ETF positions",
        "capital_basis": (
            "structural upper bound for one future $2-wide PCS before credit and closing friction; "
            "not an observed or simulated trade loss"
        ),
        "methodology_boundaries": {
            "chronology": "features through completed rank close; entry next session",
            "bootstrap_dependence": (
                "circular date-block resampling of complete rank-date edge rows preserves the two "
                "selected symbols within each date; cross-date block length is five rank dates"
            ),
            "barrier_is_intraday_or_option_mark": False,
            "daily_close_barrier_can_miss_intraday_breaches": True,
            "underlying_cost_is_option_cost": False,
            "mean_return_is_primary_endpoint": False,
            "holdout_outcomes_read": False,
        },
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "decision": (
            "ADVANCE_LOW_DOWNSIDE_SEMIVARIANCE_ETF_NONCOLLAPSE_TO_F1_TRAIN"
            if advanced
            else "CLOSE_LOW_DOWNSIDE_SEMIVARIANCE_ETF_NONCOLLAPSE_TRAIN_FAMILY"
        ),
        "failed_gates": failed_gates,
        "closed_family": None if advanced else family_key,
        "dominant_failure_mechanism": (
            None if advanced else _dominant_failure_mechanism(failed_gates)
        ),
        "registration_eligible": False,
        "authority": "research only; no registry, paper force, shadow, funding, broker, arm, or live authority",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default="2026-07-15")
    parser.add_argument("--cache-dir", default=".cache/platform/downside_semivariance_etf")
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
    panel = assemble_close_panel(histories, symbols=symbols, min_common_rows=2_500)
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
                "train_n": payload["train"]["n_rank_dates"],
                "low_breach_rate": payload["train"]["low_semivariance_breach_rate"],
                "high_breach_rate": payload["train"]["high_semivariance_breach_rate"],
                "breach_edge": payload["train"]["semivariance_breach_rate_edge"],
                "edge_lb90": payload["train"]["date_block_bootstrap_edge_lb90"],
                "plain_hv_edge": payload["train"]["plain_hv_breach_rate_edge"],
                "failed_gates": payload["failed_gates"],
                "out": str(out),
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

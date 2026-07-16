#!/usr/bin/env python3
"""Lagged monthly cross-sectional low-realized-volatility discovery lab.

Research-only BUILD/L0. The train-only underlying mechanism is evaluated before
any option pricing; the chronological final 40% remains untouched in this wake.
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
import yfinance as yf

DEFAULT_SYMBOLS = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "AMD",
    "NFLX",
    "TSLA",
    "AVGO",
    "MU",
    "JPM",
    "XOM",
    "BAC",
)


def circular_block_bootstrap_lower_bound(
    values: np.ndarray,
    *,
    confidence: float = 0.90,
    block_length: int = 3,
    samples: int = 10_000,
    seed: int = 20260714,
) -> float:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or len(vector) == 0 or not np.isfinite(vector).all():
        raise ValueError("bootstrap input must be a non-empty finite vector")
    if samples < 100:
        raise ValueError("bootstrap samples must be at least 100")
    block = max(1, min(int(block_length), len(vector)))
    n_blocks = int(np.ceil(len(vector) / block))
    offsets = np.arange(block)
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    for sample in range(samples):
        starts = rng.integers(0, len(vector), size=n_blocks)
        draw = np.concatenate([vector[(start + offsets) % len(vector)] for start in starts])[
            : len(vector)
        ]
        means[sample] = float(draw.mean())
    return float(np.quantile(means, 1.0 - confidence))


def load_adjusted_history(
    symbol: str,
    *,
    cache_dir: Path,
    start: str,
    end: str,
    downloader: Any = yf.download,
) -> tuple[pd.Series, dict[str, Any]]:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol is required")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{normalized}_{start}_{end}_auto_adjust.csv"
    if cache_path.exists():
        raw = pd.read_csv(cache_path, index_col=0, parse_dates=True)
    else:
        downloaded = downloader(
            normalized,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
        )
        if isinstance(downloaded.columns, pd.MultiIndex):
            downloaded.columns = downloaded.columns.get_level_values(0)
        if "Close" not in downloaded.columns:
            raise ValueError(f"{normalized} adjusted download missing Close")
        raw = pd.DataFrame({"close": downloaded["Close"]})
        raw.to_csv(cache_path)
        # Claim artifacts cite the persisted cache hash, so the first run must
        # consume the exact persisted representation just like every replay.
        # Reading the downloader frame directly can differ from the CSV by a
        # few floating-point ulps and make a hash-identical replay non-exact.
        raw = pd.read_csv(cache_path, index_col=0, parse_dates=True)
    raw.columns = [str(column).strip().lower() for column in raw.columns]
    if list(raw.columns) != ["close"]:
        raise ValueError(f"{normalized} cache must contain exactly one close column")
    series = pd.to_numeric(raw["close"], errors="coerce")
    series.index = pd.DatetimeIndex(pd.to_datetime(series.index)).tz_localize(None).normalize()
    series = series.sort_index()
    original_rows = len(series)
    while len(series) and pd.isna(series.iloc[-1]):
        series = series.iloc[:-1]
    discarded_trailing_unsettled_rows = original_rows - len(series)
    series.name = normalized
    values = series.to_numpy(dtype=float)
    if (
        series.empty
        or not series.index.is_unique
        or not series.index.is_monotonic_increasing
        or not np.isfinite(values).all()
        or (values <= 0.0).any()
    ):
        raise ValueError(f"{normalized} adjusted closes must be non-empty, unique, finite, and positive")
    return series, {
        "path": str(cache_path),
        "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
        "rows": int(len(series)),
        "start": str(series.index[0].date()),
        "end": str(series.index[-1].date()),
        "adjustment_semantics": "yfinance auto_adjust=True",
        "discarded_trailing_unsettled_rows": discarded_trailing_unsettled_rows,
    }


def assemble_close_panel(
    histories: dict[str, pd.Series],
    *,
    symbols: list[str],
    min_common_rows: int = 500,
) -> pd.DataFrame:
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if len(normalized) < 4 or len(normalized) != len(set(normalized)):
        raise ValueError("at least four unique ordered symbols are required")
    missing = [symbol for symbol in normalized if symbol not in histories]
    if missing:
        raise ValueError(f"histories missing symbols: {missing}")
    panel = pd.concat(
        [histories[symbol].rename(symbol) for symbol in normalized],
        axis=1,
        join="inner",
    )
    panel = panel.dropna().sort_index()
    if len(panel) < min_common_rows:
        raise ValueError(f"close panel has {len(panel)} common rows; requires {min_common_rows}")
    return _validate_close_panel(panel)


def _validate_close_panel(close_panel: pd.DataFrame) -> pd.DataFrame:
    if close_panel.empty or close_panel.shape[1] < 4:
        raise ValueError("close panel must contain at least four symbols")
    if not close_panel.index.is_unique or not close_panel.index.is_monotonic_increasing:
        raise ValueError("close panel index must be unique and increasing")
    prepared = close_panel.copy()
    prepared.index = pd.to_datetime(prepared.index).tz_localize(None).normalize()
    prepared.columns = [str(column).strip().upper() for column in prepared.columns]
    if len(set(prepared.columns)) != len(prepared.columns):
        raise ValueError("close panel symbols must be unique")
    prepared = prepared.apply(pd.to_numeric, errors="coerce")
    values = prepared.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0.0).any():
        raise ValueError("close panel prices must be finite and positive")
    return prepared


def build_monthly_blueprints(
    close_panel: pd.DataFrame,
    *,
    hv_lookback: int = 60,
    forward_sessions: int = 21,
    quantile_count: int = 3,
) -> list[dict[str, Any]]:
    """Rank prior completed HV and reserve non-overlapping forward episodes."""
    panel = _validate_close_panel(close_panel)
    if hv_lookback < 2 or forward_sessions < 1 or quantile_count < 1:
        raise ValueError("lookback, forward sessions, and quantile count must be positive")
    if 2 * quantile_count > panel.shape[1]:
        raise ValueError("low/high groups must be disjoint")
    log_returns = np.log(panel / panel.shift(1))
    hv = log_returns.rolling(hv_lookback, min_periods=hv_lookback).std() * np.sqrt(252.0)
    month_keys = panel.index.to_period("M")
    rank_dates = panel.groupby(month_keys, sort=True).tail(1).index
    blueprints: list[dict[str, Any]] = []
    previous_exit_position = -1
    for raw_rank_date in rank_dates:
        rank_date = pd.Timestamp(raw_rank_date)
        rank_position = int(panel.index.get_loc(rank_date))
        entry_position = rank_position + 1
        exit_position = entry_position + forward_sessions
        if exit_position >= len(panel) or entry_position <= previous_exit_position:
            continue
        row = hv.loc[rank_date]
        if not np.isfinite(row.to_numpy(dtype=float)).all():
            continue
        ordered = sorted(
            ((float(value), str(symbol)) for symbol, value in row.items()),
            key=lambda item: (item[0], item[1]),
        )
        low = [symbol for _, symbol in ordered[:quantile_count]]
        high = [symbol for _, symbol in ordered[-quantile_count:]]
        blueprint = {
            "rank_date": rank_date,
            "feature_max_date": rank_date,
            "entry_date": pd.Timestamp(panel.index[entry_position]),
            "exit_date": pd.Timestamp(panel.index[exit_position]),
            "low_hv_symbols": low,
            "high_hv_symbols": high,
            "low_hv_values": {symbol: float(row[symbol]) for symbol in low},
            "high_hv_values": {symbol: float(row[symbol]) for symbol in high},
        }
        blueprints.append(blueprint)
        previous_exit_position = exit_position
    return blueprints


def split_blueprints(
    blueprints: list[dict[str, Any]], *, train_fraction: float = 0.60
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.50 <= float(train_fraction) <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    if len(blueprints) < 2:
        raise ValueError("at least two chronological blueprints are required")
    ordered = sorted(blueprints, key=lambda row: pd.Timestamp(row["rank_date"]))
    split = int(len(ordered) * train_fraction)
    train = ordered[:split]
    holdout = ordered[split:]
    if not train or not holdout:
        raise ValueError("train and untouched holdout must both be non-empty")
    if pd.Timestamp(train[-1]["rank_date"]) >= pd.Timestamp(holdout[0]["rank_date"]):
        raise ValueError("train and untouched holdout must be strictly chronological")
    return train, holdout


def evaluate_train_partition(
    close_panel: pd.DataFrame,
    train_blueprints: list[dict[str, Any]],
    *,
    min_episodes: int = 24,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    panel = _validate_close_panel(close_panel)
    if min_episodes < 1 or not train_blueprints:
        raise ValueError("non-empty train blueprints and positive min_episodes are required")
    rows: list[dict[str, Any]] = []
    prior_exit: pd.Timestamp | None = None
    integrity_violations: list[str] = []
    for index, blueprint in enumerate(train_blueprints):
        rank_date = pd.Timestamp(blueprint["rank_date"])
        feature_max_date = pd.Timestamp(blueprint["feature_max_date"])
        entry_date = pd.Timestamp(blueprint["entry_date"])
        exit_date = pd.Timestamp(blueprint["exit_date"])
        low = list(blueprint["low_hv_symbols"])
        high = list(blueprint["high_hv_symbols"])
        if not (feature_max_date == rank_date < entry_date < exit_date):
            integrity_violations.append(f"chronology:{index}")
        if prior_exit is not None and entry_date <= prior_exit:
            integrity_violations.append(f"overlap:{index}")
        if set(low) & set(high) or not low or len(low) != len(high):
            integrity_violations.append(f"groups:{index}")
        missing = sorted((set(low) | set(high)) - set(panel.columns))
        if missing or entry_date not in panel.index or exit_date not in panel.index:
            raise ValueError(f"blueprint {index} is outside the close panel: {missing}")
        low_returns = panel.loc[exit_date, low] / panel.loc[entry_date, low] - 1.0
        high_returns = panel.loc[exit_date, high] / panel.loc[entry_date, high] - 1.0
        low_mean = float(low_returns.mean())
        high_mean = float(high_returns.mean())
        rows.append(
            {
                "rank_date": str(rank_date.date()),
                "entry_date": str(entry_date.date()),
                "exit_date": str(exit_date.date()),
                "low_hv_symbols": low,
                "high_hv_symbols": high,
                "low_hv_mean_return": low_mean,
                "high_hv_mean_return": high_mean,
                "paired_excess_return": low_mean - high_mean,
            }
        )
        prior_exit = exit_date
    low_values = np.asarray([row["low_hv_mean_return"] for row in rows], dtype=float)
    high_values = np.asarray([row["high_hv_mean_return"] for row in rows], dtype=float)
    excess = low_values - high_values
    lower_bound = circular_block_bootstrap_lower_bound(
        excess,
        samples=bootstrap_samples,
        seed=20260714,
    )
    gate_checks = {
        "minimum_train_episodes": len(rows) >= min_episodes,
        "positive_low_hv_mean_return": float(low_values.mean()) > 0.0,
        "positive_paired_excess_mean": float(excess.mean()) > 0.0,
        "paired_excess_bootstrap_lb90_positive": lower_bound > 0.0,
        "zero_integrity_violations": not integrity_violations,
    }
    return {
        "n_episodes": len(rows),
        "low_hv_mean_return": float(low_values.mean()),
        "high_hv_mean_return": float(high_values.mean()),
        "paired_excess_mean": float(excess.mean()),
        "paired_excess_median": float(np.median(excess)),
        "paired_excess_positive_frequency": float(np.mean(excess > 0.0)),
        "paired_excess_bootstrap_lb90": lower_bound,
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_block_length": 3,
        "integrity_violations": integrity_violations,
        "gate_checks": gate_checks,
        "gate_pass": bool(all(gate_checks.values())),
        "episodes": rows,
    }


def run_lab_from_panel(
    close_panel: pd.DataFrame,
    *,
    symbols: list[str],
    provenance: dict[str, Any],
    train_fraction: float = 0.60,
    hv_lookback: int = 60,
    forward_sessions: int = 21,
    quantile_count: int = 3,
    min_train_episodes: int = 24,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    panel = _validate_close_panel(close_panel)
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if normalized != list(panel.columns) or len(normalized) != len(set(normalized)):
        raise ValueError("symbols must exactly match the ordered close-panel columns")
    blueprints = build_monthly_blueprints(
        panel,
        hv_lookback=hv_lookback,
        forward_sessions=forward_sessions,
        quantile_count=quantile_count,
    )
    train, holdout = split_blueprints(blueprints, train_fraction=train_fraction)
    train_result = evaluate_train_partition(
        panel,
        train,
        min_episodes=min_train_episodes,
        bootstrap_samples=bootstrap_samples,
    )
    advanced = bool(train_result["gate_pass"])
    holdout_first = holdout[0]
    holdout_last = holdout[-1]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_UNDERLYING_DISCOVERY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": "CROSS_SECTION_LOW_HV_PCS_21D_V1",
        "mechanism_family": "MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT",
        "economic_mechanism": (
            "within a fixed liquid-equity cross-section, names with the lowest prior completed "
            "60-session realized volatility retain a more stable positive 21-session drift than "
            "the contemporaneous highest-volatility control group; a later bounded bullish PCS "
            "expression would harvest that conditional drift plus time decay"
        ),
        "candidate_or_family_scope": (
            "monthly bottom-three versus top-three prior-HV ranks in a fixed 14-name present-day "
            "liquid-equity universe, non-overlapping 21-session forward episodes"
        ),
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "falsifier": (
            "on the chronological first 60% of eligible non-overlapping monthly episodes, fewer "
            "than 24 episodes, non-positive low-HV mean return, non-positive low-minus-high mean, "
            "or a non-positive one-sided 90% circular-block-bootstrap lower bound closes the exact family"
        ),
        "claim_scope": (
            "split/dividend-adjusted underlying closes only; fixed present-day universe with explicit "
            "survivorship/listing bias; train-only L0 discovery; no option marks, costs, fills, L1, "
            "capital-seat, or paper eligibility claim"
        ),
        "all_train_rows_are_inspected_development_data": True,
        "f2_or_l1_claim": False,
        "config": {
            "symbols": normalized,
            "hv_lookback_sessions": hv_lookback,
            "forward_sessions": forward_sessions,
            "quantile_count_each_side": quantile_count,
            "train_fraction": train_fraction,
            "minimum_train_episodes": min_train_episodes,
            "bootstrap_confidence": 0.90,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_block_length": 3,
            "non_overlapping_episodes": True,
        },
        "data_provenance": provenance,
        "population_validity": {
            "population_type": "fixed present-day liquid US equities only",
            "population_pure": True,
            "ranking_complete": True,
            "survivorship_bias": True,
            "listing_bias": True,
            "generalization_allowed": False,
        },
        "train": train_result,
        "untouched_holdout": {
            "n_blueprints": len(holdout),
            "first_rank_date": str(pd.Timestamp(holdout_first["rank_date"]).date()),
            "first_entry_date": str(pd.Timestamp(holdout_first["entry_date"]).date()),
            "last_rank_date": str(pd.Timestamp(holdout_last["rank_date"]).date()),
            "last_exit_date": str(pd.Timestamp(holdout_last["exit_date"]).date()),
            "outcome_metrics_read": False,
            "simulation_run": False,
        },
        "option_stage": {
            "status": "NOT_RUN_PENDING_UNTOUCHED_HOLDOUT" if advanced else "NOT_RUN_TRAIN_GATE_FAILED",
            "pricing_run": False,
            "pricing_calls": 0,
            "planned_structure": "put_credit_spread",
            "planned_width_usd": 1.0,
            "option_mark_provenance": None,
        },
        "structure": "conditional_put_credit_spread_not_yet_priced",
        "capital_fit_usd": 100.0,
        "one_lot_max_loss_usd": 100.0,
        "max_loss_usd": 100.0,
        "max_lots": 1,
        "capital_basis": (
            "structural upper bound for one future $1-wide PCS before net credit and closing friction; "
            "not an observed or simulated trade loss"
        ),
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "decision": (
            "ADVANCE_FIXED_LOW_HV_CROSS_SECTION_TO_F1_TRAIN"
            if advanced
            else "CLOSE_FIXED_LOW_HV_CROSS_SECTION_TRAIN_FAMILY"
        ),
        "closed_family": None if advanced else "MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT",
        "dominant_failure_mechanism": (
            None
            if advanced
            else "the fixed monthly low-HV group had positive absolute train drift but did not establish incremental edge over the same-date high-HV control under the frozen mean/bootstrap gate"
        ),
        "registration_eligible": False,
        "authority": "research only; no registry, paper, shadow, funding, broker, arm, or live authority",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2026-07-15")
    parser.add_argument("--cache-dir", default=".cache/platform/low_hv_cross_section")
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
                "train_n": payload["train"]["n_episodes"],
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

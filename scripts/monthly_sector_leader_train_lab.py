#!/usr/bin/env python3
"""Train-only monthly sector-leader continuation discovery lab.

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

SECTOR_SYMBOLS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def _validate_panel(close_panel: pd.DataFrame) -> pd.DataFrame:
    if close_panel.empty:
        raise ValueError("close panel must be non-empty")
    panel = close_panel.copy()
    panel.index = pd.DatetimeIndex(pd.to_datetime(panel.index)).tz_localize(None).normalize()
    panel.columns = [str(column).strip().upper() for column in panel.columns]
    if list(panel.columns) != SECTOR_SYMBOLS:
        raise ValueError("close panel columns must exactly match the frozen nine-sector order")
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


def build_monthly_leader_blueprints(
    close_panel: pd.DataFrame,
    *,
    momentum_sessions: int = 63,
    trend_sessions: int = 126,
    forward_sessions: int = 20,
    min_leader_return_63: float = 0.0,
    min_leader_median_spread: float = 0.05,
    require_above_sma: bool = True,
) -> list[dict[str, Any]]:
    """Freeze month-end leader identities using completed pre-entry fields only."""
    panel = _validate_panel(close_panel)
    if min(momentum_sessions, trend_sessions, forward_sessions) < 1:
        raise ValueError("lookbacks and forward horizon must be positive")
    if not np.isfinite([min_leader_return_63, min_leader_median_spread]).all():
        raise ValueError("signal thresholds must be finite")

    sma = panel.rolling(trend_sessions, min_periods=trend_sessions).mean()
    month_end_positions = [
        position
        for position in range(len(panel) - 1)
        if panel.index[position].month != panel.index[position + 1].month
    ]
    rows: list[dict[str, Any]] = []
    occupied: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for position in month_end_positions:
        if position < max(momentum_sessions, trend_sessions - 1):
            continue
        entry_position = position + 1
        exit_position = entry_position + forward_sessions
        if exit_position >= len(panel):
            continue
        signal_returns = panel.iloc[position] / panel.iloc[position - momentum_sessions] - 1.0
        if not np.isfinite(signal_returns.to_numpy(dtype=float)).all():
            continue
        leader = str(signal_returns.idxmax())
        leader_return = float(signal_returns[leader])
        median_return = float(signal_returns.median())
        spread = leader_return - median_return
        leader_close = float(panel.iloc[position][leader])
        leader_sma = float(sma.iloc[position][leader])
        if (
            leader_return <= min_leader_return_63
            or spread < min_leader_median_spread
            or (require_above_sma and leader_close <= leader_sma)
        ):
            continue
        window = (pd.Timestamp(panel.index[entry_position]), pd.Timestamp(panel.index[exit_position]))
        if _overlaps(window, occupied):
            continue
        peers = [symbol for symbol in SECTOR_SYMBOLS if symbol != leader]
        rows.append(
            {
                "signal_date": pd.Timestamp(panel.index[position]),
                "feature_max_date": pd.Timestamp(panel.index[position]),
                "entry_date": window[0],
                "exit_date": window[1],
                "leader": leader,
                "peers": peers,
                "leader_return_63": leader_return,
                "median_return_63": median_return,
                "leader_median_spread": spread,
                "leader_signal_close": leader_close,
                "leader_sma_126": leader_sma,
            }
        )
        occupied.append(window)
    return rows


def _date_block_lower_bound(
    values: np.ndarray,
    *,
    samples: int,
    block_length: int = 3,
    confidence: float = 0.90,
    seed: int = 20260716,
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


def evaluate_train_partition(
    close_panel: pd.DataFrame,
    train_blueprints: list[dict[str, Any]],
    *,
    min_signals: int = 60,
    min_signal_years: int = 10,
    round_trip_cost_bps: float = 10.0,
    min_leader_mean_return: float = 0.005,
    min_leader_positive_frequency: float = 0.55,
    min_paired_excess_mean: float = 0.003,
    minimum_tail_return: float = -0.08,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    """Evaluate only frozen train outcomes under absolute and peer-control gates."""
    panel = _validate_panel(close_panel)
    if not train_blueprints or min(min_signals, min_signal_years) < 1:
        raise ValueError("non-empty blueprints and positive density gates are required")
    if not np.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0.0:
        raise ValueError("round-trip cost must be finite and non-negative")
    cost = round_trip_cost_bps / 10_000.0
    rows: list[dict[str, Any]] = []
    integrity_violations: list[str] = []
    occupied: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    for index, blueprint in enumerate(train_blueprints):
        signal = pd.Timestamp(blueprint["signal_date"])
        feature_max = pd.Timestamp(blueprint["feature_max_date"])
        entry = pd.Timestamp(blueprint["entry_date"])
        exit_date = pd.Timestamp(blueprint["exit_date"])
        leader = str(blueprint["leader"])
        peers = [str(symbol) for symbol in blueprint["peers"]]
        if not (feature_max == signal < entry < exit_date):
            integrity_violations.append(f"chronology:{index}")
        required_dates = {signal, entry, exit_date}
        if not required_dates.issubset(set(panel.index)):
            raise ValueError(f"blueprint {index} dates are outside the close panel")
        signal_position = int(panel.index.get_loc(signal))
        entry_position = int(panel.index.get_loc(entry))
        exit_position = int(panel.index.get_loc(exit_date))
        if signal_position + 1 >= len(panel) or panel.index[signal_position + 1].month == signal.month:
            integrity_violations.append(f"not_month_end:{index}")
        if entry_position != signal_position + 1 or exit_position != entry_position + 20:
            integrity_violations.append(f"window_geometry:{index}")
        window = (entry, exit_date)
        if _overlaps(window, occupied):
            integrity_violations.append(f"overlap:{index}")
        occupied.append(window)
        if leader not in SECTOR_SYMBOLS or sorted(peers) != sorted(set(SECTOR_SYMBOLS) - {leader}):
            integrity_violations.append(f"population:{index}")
        if (
            float(blueprint["leader_return_63"]) <= 0.0
            or float(blueprint["leader_median_spread"]) < 0.05
            or float(blueprint["leader_signal_close"]) <= float(blueprint["leader_sma_126"])
        ):
            integrity_violations.append(f"signal_gate:{index}")
        leader_return = float(panel.loc[exit_date, leader] / panel.loc[entry, leader] - 1.0 - cost)
        peer_vector = np.asarray(
            [float(panel.loc[exit_date, peer] / panel.loc[entry, peer] - 1.0 - cost) for peer in peers],
            dtype=float,
        )
        peer_return = float(peer_vector.mean())
        if not np.isfinite([leader_return, peer_return]).all():
            raise ValueError("outcome return is nonfinite")
        rows.append(
            {
                "signal_date": str(signal.date()),
                "entry_date": str(entry.date()),
                "exit_date": str(exit_date.date()),
                "leader": leader,
                "leader_return_after_cost": leader_return,
                "nonleader_equal_weight_return_after_cost": peer_return,
                "paired_excess_return": leader_return - peer_return,
            }
        )

    leader_values = np.asarray([row["leader_return_after_cost"] for row in rows], dtype=float)
    controls = np.asarray(
        [row["nonleader_equal_weight_return_after_cost"] for row in rows], dtype=float
    )
    excess = leader_values - controls
    lower_bound = _date_block_lower_bound(excess, samples=bootstrap_samples)
    signal_years = sorted({pd.Timestamp(row["signal_date"]).year for row in rows})
    signal_year_counts = {
        str(year): sum(pd.Timestamp(row["signal_date"]).year == year for row in rows)
        for year in signal_years
    }
    leader_mean = float(leader_values.mean())
    control_mean = float(controls.mean())
    paired_mean = float(excess.mean())
    positive_frequency = float(np.mean(leader_values > 0.0))
    tail = _worst_decile_mean(leader_values)
    gate_checks = {
        "minimum_train_signals": len(rows) >= min_signals,
        "minimum_signal_years": len(signal_years) >= min_signal_years,
        "leader_mean_return_above_0_50pct": leader_mean > min_leader_mean_return,
        "leader_positive_frequency_at_least_55pct": positive_frequency >= min_leader_positive_frequency,
        "paired_excess_mean_at_least_0_30pct": paired_mean >= min_paired_excess_mean,
        "paired_excess_bootstrap_lb90_positive": lower_bound > 0.0,
        "leader_worst_decile_at_least_negative_8pct": tail >= minimum_tail_return,
        "nonleader_equal_weight_control_is_weaker": leader_mean > control_mean,
        "zero_integrity_violations": not integrity_violations,
    }
    return {
        "n_signals": len(rows),
        "signal_years": signal_years,
        "signal_year_counts": signal_year_counts,
        "round_trip_underlying_cost_bps": float(round_trip_cost_bps),
        "leader_mean_return_after_cost": leader_mean,
        "nonleader_equal_weight_mean_return_after_cost": control_mean,
        "leader_positive_frequency_after_cost": positive_frequency,
        "paired_excess_mean": paired_mean,
        "paired_excess_median": float(np.median(excess)),
        "paired_excess_positive_frequency": float(np.mean(excess > 0.0)),
        "paired_excess_bootstrap_lb90": lower_bound,
        "leader_worst_decile_return_after_cost": tail,
        "worst_decile_n": max(1, int(np.ceil(len(leader_values) * 0.10))),
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
        raise ValueError("at least two frozen signals are required")
    ordered = sorted(blueprints, key=lambda row: pd.Timestamp(row["signal_date"]))
    split = int(len(ordered) * train_fraction)
    train, holdout = ordered[:split], ordered[split:]
    if not train or not holdout:
        raise ValueError("train and holdout must both be non-empty")
    if pd.Timestamp(train[-1]["signal_date"]) >= pd.Timestamp(holdout[0]["signal_date"]):
        raise ValueError("train and holdout must be strictly chronological")
    return train, holdout


def _holdout_identity(blueprints: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        {
            "signal_date": str(pd.Timestamp(row["signal_date"]).date()),
            "entry_date": str(pd.Timestamp(row["entry_date"]).date()),
            "exit_date": str(pd.Timestamp(row["exit_date"]).date()),
            "leader": str(row["leader"]),
            "peers": list(row["peers"]),
        }
        for row in blueprints
    ]
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "n_frozen_signals": len(rows),
        "first_signal_date": rows[0]["signal_date"],
        "last_signal_date": rows[-1]["signal_date"],
        "last_exit_date": rows[-1]["exit_date"],
        "identity_sha256": hashlib.sha256(encoded).hexdigest(),
        "identity_fields": list(rows[0]),
        "outcome_metrics_read": False,
        "simulation_run": False,
    }


def _dominant_failure(failed_gates: list[str]) -> str:
    if any("paired_excess" in gate or "control" in gate for gate in failed_gates):
        return (
            "mechanism-specific paired_excess failure: monthly sector leaders did not beat the "
            "same-date equal-weight nonleader basket under the frozen magnitude/uncertainty gates"
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
    min_signals: int = 60,
    min_signal_years: int = 10,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    panel = _validate_panel(close_panel)
    blueprints = (
        build_monthly_leader_blueprints(panel)
        if frozen_blueprints is None
        else list(frozen_blueprints)
    )
    train, holdout = _split_blueprints(blueprints, train_fraction=train_fraction)
    train_result = evaluate_train_partition(
        panel,
        train,
        min_signals=min_signals,
        min_signal_years=min_signal_years,
        bootstrap_samples=bootstrap_samples,
    )
    advanced = bool(train_result["gate_pass"])
    failed_gates = [name for name, passed in train_result["gate_checks"].items() if not passed]
    common_panel_start = str(panel.index[0])[:10]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_UNDERLYING_DISCOVERY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "candidate_id": "MONTHLY_SECTOR_LEADER_CONTINUATION_BULL_CALL_35D_V1",
        "mechanism_family": "SECTOR_ALLOCATION_RELATIVE_STRENGTH_CONTINUATION",
        "novelty_key": (
            "direction_up_relative|nine_original_sector_etfs|month_end|63session_leader|"
            "positive_above_sma126|leader_minus_median_5pct|20session|same_date_nonleader_control|"
            "bull_call_debit_spread_35d_2wide_planned"
        ),
        "economic_mechanism": (
            "slow institutional and benchmark sector reallocation may sustain intermediate-term "
            "leadership for one additional trading month"
        ),
        "forecast_type": "direction_up_and_cross_sectional_outperformance",
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "claim_scope": (
            "split/dividend-adjusted daily sector-ETF closes only; frozen nine-original-SPDR panel; "
            "train-only L0 discovery; no option marks, IV, debit, fill, F2, L1, capital-seat, or paper claim"
        ),
        "f2_or_l1_claim": False,
        "f2_claim": False,
        "l1_or_capital_seat_claim": False,
        "capital_seat_claim": False,
        "all_train_rows_are_inspected_development_data": True,
        "falsifier": (
            "fewer than 60 train signals or ten years; chronology/month-end/window/overlap/population "
            "failure; leader mean after 10 bps <=0.50%; positive frequency <55%; paired excess versus "
            "equal-weight nonleaders <0.30%; paired-excess date-block LB90 <=0; worst decile <-8%; or "
            "nonleader control equal/better"
        ),
        "config": {
            "symbols": SECTOR_SYMBOLS,
            "start": "1998-12-01",
            "end_exclusive": "2026-07-16",
            "train_fraction": train_fraction,
            "momentum_sessions": 63,
            "trend_sessions": 126,
            "forward_sessions": 20,
            "min_leader_return_63": 0.0,
            "min_leader_median_spread": 0.05,
            "require_above_sma": True,
            "minimum_train_signals": min_signals,
            "minimum_signal_years": min_signal_years,
            "round_trip_underlying_cost_bps": 10.0,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_block_length_signal_dates": 3,
        },
        "layered_edge_stack": {
            "market_underlying": "dynamic leader from frozen nine original Select Sector SPDR ETFs",
            "forecast_type": "absolute upward drift and relative outperformance over 20 sessions",
            "economic_mechanism": "slow institutional/benchmark sector reallocation",
            "option_structure": "future conditional one-lot 30-45 DTE $2-wide bull call debit spread",
            "intended_greeks": ["positive_delta", "positive_gamma", "bounded_negative_theta"],
            "dangerous_greeks_and_exposures": [
                "negative_theta_if_continuation_stalls",
                "implied_volatility_contraction",
                "capped_upside",
                "gap_loss",
                "sector_concentration",
                "short_call_assignment_and_expiration_handling",
            ],
            "regime_envelope": (
                "leader positive 63-session return, close above SMA126, and at least five-percentage-point "
                "lead over panel median"
            ),
            "entry_trigger": "completed calendar month-end signal; next completed close entry",
            "exit_management": (
                "underlying discovery exits after 20 sessions; future option plan +50%/-50% debit, five DTE, "
                "trend invalidation, assignment guard, no roll"
            ),
            "capital_fit_usd": 200.0,
            "max_loss_usd": 200.0,
            "max_lots": 1,
            "portfolio_overlap": (
                "no concurrent Agentic exposure in selected sector ETF or broad-index positive-delta unit"
            ),
            "evidence_falsifier": "frozen train gates above; holdout sealed",
            "confidence_stage": "F1_TRAIN" if advanced else "F0_MECHANISM_CLOSED",
            "stand_aside": (
                "incomplete panel, failed month-end/momentum/trend/separation/path gate, option liquidity/debit "
                "or max-loss failure, or overlapping sector/index positive-delta risk"
            ),
        },
        "provenance": provenance,
        "population_purity": {
            "panel": SECTOR_SYMBOLS,
            "join": "inner join; no forward fill",
            "common_panel_start_date": common_panel_start,
            "late_listings_excluded": ["XLC", "XLRE"],
            "present_day_survivorship_bias": True,
            "historical_sector_membership_not_reconstructed": True,
            "optionability_not_historically_reconstructed": True,
        },
        "train": train_result,
        "holdout": _holdout_identity(holdout),
        "failed_gates": failed_gates,
        "dominant_failure_mechanism": _dominant_failure(failed_gates),
        "search_information": (
            "new train-only sector-allocation panel decision with same-date nonleader specificity control "
            "and sealed holdout"
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
                "formation horizons near 42-126 sessions on the same nine-sector panel",
                "leader-minus-median separation thresholds near 3-8 percentage points",
                "forward horizons from 10 through 30 sessions",
                "SMA100-SMA150 trend lookback nudges",
                "top-two or rank-weighted variants without a materially new control/evidence class",
            ],
            "reopen_condition": (
                "independent panel construction, observed option-flow evidence, or another materially new "
                "economic mechanism/evidence class; train-inspected knob polish is forbidden"
            ),
        },
        "methodology_boundaries": {
            "chronology": "features through completed month-end close; entry at next completed close",
            "control": "same-date equal-weight basket of eight nonleaders selected without outcome access",
            "dependence": "circular three-signal-date block bootstrap of complete paired-excess rows",
            "history_floor": (
                "nine original sector ETFs preserve approximately 1999-forward history but retain present-day "
                "survivorship and do not reconstruct historical sector composition"
            ),
            "horizon_option_alignment": (
                "20-session underlying continuation does not validate a full 30-45 DTE option path, implied "
                "volatility, debit fills, or early-exit economics"
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
        default=".cache/platform/monthly_sector_leader_train_2026-07-16T0335.json",
    )
    parser.add_argument("--cache-dir", default=".cache/platform/monthly_sector_leader")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    histories: dict[str, pd.Series] = {}
    provenance: dict[str, Any] = {}
    for symbol in SECTOR_SYMBOLS:
        history, source = load_adjusted_history(
            symbol,
            cache_dir=cache_dir,
            start="1998-12-01",
            end="2026-07-16",
        )
        histories[symbol] = history
        provenance[symbol] = source
    panel = assemble_close_panel(histories, symbols=SECTOR_SYMBOLS, min_common_rows=5_000)
    payload = run_lab_from_panel(
        panel,
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
                "n_signals": payload["train"]["n_signals"],
                "failed_gates": payload["failed_gates"],
                "out": str(out),
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

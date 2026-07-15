#!/usr/bin/env python3
"""One-shot untouched-holdout validator for the frozen breakout continuation family."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from scripts.breakout_continuation_train_lab import (
        build_matched_blueprints,
        circular_block_bootstrap_lower_bound,
        evaluate_train_partition,
    )
except ModuleNotFoundError:  # Direct script execution places scripts/ on sys.path.
    from breakout_continuation_train_lab import (  # type: ignore[no-redef]
        build_matched_blueprints,
        circular_block_bootstrap_lower_bound,
        evaluate_train_partition,
    )


IDENTITY_DATE_KEYS = (
    "control_signal_date",
    "control_entry_date",
    "control_exit_date",
    "treated_signal_date",
    "treated_entry_date",
    "treated_exit_date",
)
IDENTITY_NUMERIC_KEYS = (
    "calendar_distance_sessions",
    "return_20d_match_distance",
    "hv_20d_match_distance",
)


def _normalized_identity(row: dict[str, Any]) -> dict[str, Any]:
    identity: dict[str, Any] = {"symbol": str(row["symbol"]).upper()}
    for key in IDENTITY_DATE_KEYS:
        identity[key] = str(pd.Timestamp(row[key]).date())
    identity["calendar_distance_sessions"] = int(row["calendar_distance_sessions"])
    for key in IDENTITY_NUMERIC_KEYS[1:]:
        identity[key] = float(row[key])
    return identity


def _identity_hash(rows: list[dict[str, Any]]) -> str:
    normalized = [_normalized_identity(row) for row in rows]
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_frozen_population(
    frozen_payload: dict[str, Any],
    reconstructed_blueprints: list[dict[str, Any]],
    *,
    train_fraction: float,
) -> dict[str, Any]:
    """Fail closed unless the reconstructed population matches the frozen train prefix."""
    if frozen_payload.get("untouched_holdout", {}).get("outcome_metrics_read") is not False:
        raise ValueError("frozen artifact does not preserve an outcome-unread holdout")
    if frozen_payload.get("untouched_holdout", {}).get("simulation_run") is not False:
        raise ValueError("frozen artifact does not preserve an unsimulated holdout")
    ordered = sorted(
        reconstructed_blueprints,
        key=lambda row: (pd.Timestamp(row["treated_signal_date"]), str(row["symbol"])),
    )
    split = int(len(ordered) * float(train_fraction))
    train = ordered[:split]
    holdout = ordered[split:]
    selection = frozen_payload.get("selection_diagnostics", {})
    expected_counts = (
        int(selection.get("matched_blueprints", -1)),
        int(selection.get("train_blueprints", -1)),
        int(selection.get("holdout_blueprints", -1)),
        int(frozen_payload.get("untouched_holdout", {}).get("n_blueprints", -1)),
    )
    actual_counts = (len(ordered), len(train), len(holdout), len(holdout))
    if actual_counts != expected_counts:
        raise ValueError(
            f"frozen population counts changed: expected={expected_counts} actual={actual_counts}"
        )
    frozen_train = list(frozen_payload.get("train", {}).get("pairs", []))
    if len(frozen_train) != len(train):
        raise ValueError("frozen train pair count does not match reconstructed train prefix")
    for index, (expected, actual) in enumerate(zip(frozen_train, train)):
        expected_identity = _normalized_identity(expected)
        actual_identity = _normalized_identity(actual)
        for key in ("symbol", *IDENTITY_DATE_KEYS, "calendar_distance_sessions"):
            if expected_identity[key] != actual_identity[key]:
                raise ValueError(f"frozen train identity mismatch at row {index}: {key}")
        for key in IDENTITY_NUMERIC_KEYS[1:]:
            if abs(float(expected_identity[key]) - float(actual_identity[key])) > 1e-12:
                raise ValueError(f"frozen train identity mismatch at row {index}: {key}")
    return {
        "exact_population_reproduced": True,
        "matched_blueprints": len(ordered),
        "train_blueprints": len(train),
        "holdout_blueprints": len(holdout),
        "train_identity_sha256": _identity_hash(train),
        "holdout_identity_sha256": _identity_hash(holdout),
        "all_identity_sha256": _identity_hash(ordered),
    }


def _return_summary(rows: list[dict[str, Any]], *, bootstrap_samples: int) -> dict[str, Any]:
    treated = np.asarray([float(row["treated_return_after_cost"]) for row in rows], dtype=float)
    control = np.asarray([float(row["control_return_after_cost"]) for row in rows], dtype=float)
    excess = np.asarray([float(row["paired_excess_return"]) for row in rows], dtype=float)
    if not len(rows) or not np.isfinite(np.concatenate([treated, control, excess])).all():
        raise ValueError("diagnostic rows must be non-empty and finite")
    return {
        "n_pairs": len(rows),
        "treated_mean_return_after_cost": float(treated.mean()),
        "control_mean_return_after_cost": float(control.mean()),
        "paired_excess_mean": float(excess.mean()),
        "paired_excess_median": float(np.median(excess)),
        "paired_excess_positive_frequency": float(np.mean(excess > 0.0)),
        "paired_excess_bootstrap_lb90": circular_block_bootstrap_lower_bound(
            excess,
            block_length=min(5, len(excess)),
            samples=bootstrap_samples,
            seed=20260715,
        ),
    }


def build_concentration_diagnostics(
    pairs: list[dict[str, Any]],
    *,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    """Report predeclared concentration diagnostics without changing the pooled gate."""
    if not pairs or bootstrap_samples < 1:
        raise ValueError("non-empty pairs and positive bootstrap samples are required")
    ordered = sorted(
        pairs,
        key=lambda row: (pd.Timestamp(row["treated_signal_date"]), str(row["symbol"])),
    )
    symbols = sorted({str(row["symbol"]).upper() for row in ordered})
    per_symbol = {
        symbol: _return_summary(
            [row for row in ordered if str(row["symbol"]).upper() == symbol],
            bootstrap_samples=bootstrap_samples,
        )
        for symbol in symbols
    }
    leave_one_out = {
        symbol: _return_summary(
            [row for row in ordered if str(row["symbol"]).upper() != symbol],
            bootstrap_samples=bootstrap_samples,
        )
        for symbol in symbols
        if any(str(row["symbol"]).upper() != symbol for row in ordered)
    }
    tertiles = []
    for index, indices in enumerate(np.array_split(np.arange(len(ordered)), 3), start=1):
        rows = [ordered[int(position)] for position in indices]
        if not rows:
            continue
        tertiles.append(
            {
                "tertile": index,
                "first_treated_signal_date": str(pd.Timestamp(rows[0]["treated_signal_date"]).date()),
                "last_treated_signal_date": str(pd.Timestamp(rows[-1]["treated_signal_date"]).date()),
                **_return_summary(rows, bootstrap_samples=bootstrap_samples),
            }
        )
    return {
        "role": "mandatory_non_gating_context",
        "does_not_change_pooled_gate": True,
        "per_symbol": per_symbol,
        "leave_one_symbol_out": leave_one_out,
        "chronological_tertiles": tertiles,
    }


def evaluate_holdout_partition(
    close_panel: pd.DataFrame,
    holdout_blueprints: list[dict[str, Any]],
    *,
    min_pairs: int = 80,
    min_symbols: int = 6,
    round_trip_cost_bps: float = 20.0,
    bootstrap_samples: int = 10_000,
    breakout_ratio_min: float = 1.02,
    control_breakout_ratio_low: float = 0.95,
    control_breakout_ratio_high: float = 1.00,
    max_match_distance_sessions: int = 126,
    max_return_20d_distance: float = 0.08,
    max_hv_20d_distance: float = 0.25,
) -> dict[str, Any]:
    """Apply the frozen pooled discovery gate to the reserved partition."""
    result = evaluate_train_partition(
        close_panel,
        holdout_blueprints,
        min_pairs=min_pairs,
        min_symbols=min_symbols,
        round_trip_cost_bps=round_trip_cost_bps,
        bootstrap_samples=bootstrap_samples,
        breakout_ratio_min=breakout_ratio_min,
        control_breakout_ratio_low=control_breakout_ratio_low,
        control_breakout_ratio_high=control_breakout_ratio_high,
        max_match_distance_sessions=max_match_distance_sessions,
        max_return_20d_distance=max_return_20d_distance,
        max_hv_20d_distance=max_hv_20d_distance,
    )
    checks = dict(result["gate_checks"])
    checks["minimum_holdout_pairs"] = checks.pop("minimum_train_pairs")
    result["gate_checks"] = checks
    result["gate_pass"] = bool(all(checks.values()))
    return result


def _failure_mechanism(checks: dict[str, bool]) -> str | None:
    labels = {
        "minimum_holdout_pairs": "holdout sample density below the frozen discovery minimum",
        "minimum_symbol_breadth": "holdout symbol breadth below the frozen discovery minimum",
        "positive_treated_mean_after_cost": "non-positive ten-session treated mean after labeled sensitivity",
        "positive_paired_excess_mean": "non-positive matched paired excess mean",
        "paired_excess_bootstrap_lb90_positive": "one-sided 90% paired-excess block-bootstrap lower bound was non-positive",
        "population_integrity": "chronology, matching, overlap, or finite-value integrity failed",
    }
    for key, passed in checks.items():
        if not passed:
            return labels.get(key, f"frozen holdout gate failed: {key}")
    return None


def load_frozen_panel(
    frozen_payload: dict[str, Any],
    *,
    repo_root: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load only the frozen CSVs and fail closed on any provenance drift."""
    root = Path(repo_root).resolve()
    expected_symbols = [str(symbol).upper() for symbol in frozen_payload["config"]["symbols"]]
    sources = dict(frozen_payload["data_provenance"]["sources"])
    if sorted(sources) != sorted(expected_symbols):
        raise ValueError("frozen source symbols do not match frozen config")
    series: dict[str, pd.Series] = {}
    verified_sources: dict[str, Any] = {}
    for symbol in expected_symbols:
        meta = dict(sources[symbol])
        path = Path(str(meta["path"])).expanduser()
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            raise ValueError(f"frozen source missing for {symbol}: {path}")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != str(meta["sha256"]):
            raise ValueError(f"sha256 mismatch for frozen source {symbol}")
        frame = pd.read_csv(path)
        if list(frame.columns) != ["Date", "close"]:
            raise ValueError(f"unexpected frozen CSV schema for {symbol}")
        dates = pd.DatetimeIndex(pd.to_datetime(frame["Date"], errors="raise"))
        values = np.asarray(pd.to_numeric(frame["close"], errors="raise"), dtype=float)
        if dates.duplicated().any() or not dates.is_monotonic_increasing:
            raise ValueError(f"duplicate or unsorted dates in frozen source {symbol}")
        if not np.isfinite(values).all() or (values <= 0.0).any():
            raise ValueError(f"nonfinite or nonpositive close in frozen source {symbol}")
        if len(frame) != int(meta["rows"]):
            raise ValueError(f"row count mismatch for frozen source {symbol}")
        formatted_dates = dates.strftime("%Y-%m-%d")
        start = str(formatted_dates[0])
        end = str(formatted_dates[-1])
        if start != str(meta["start"]) or end != str(meta["end"]):
            raise ValueError(f"date boundary mismatch for frozen source {symbol}")
        series[symbol] = pd.Series(values, index=dates, name=symbol)
        verified_sources[symbol] = {
            "path": str(path),
            "sha256": actual_hash,
            "rows": len(frame),
            "start": start,
            "end": end,
        }
    panel = pd.concat(series.values(), axis=1, join="inner").dropna().sort_index()
    panel = panel[expected_symbols]
    common = dict(frozen_payload["data_provenance"]["common_panel"])
    actual_common = {
        "rows": len(panel),
        "start": str(pd.Timestamp(panel.index[0]).date()),
        "end": str(pd.Timestamp(panel.index[-1]).date()),
    }
    expected_common = {
        "rows": int(common["rows"]),
        "start": str(common["start"]),
        "end": str(common["end"]),
    }
    if actual_common != expected_common:
        raise ValueError(
            f"frozen common panel changed: expected={expected_common} actual={actual_common}"
        )
    return panel, {
        "all_source_hashes_match": True,
        "network_calls": 0,
        "sources": verified_sources,
        "common_panel": actual_common,
    }


def run_holdout_from_panel(
    frozen_payload: dict[str, Any],
    close_panel: pd.DataFrame,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, Any]:
    """Reproduce the frozen population and open its final chronological partition once."""
    if frozen_payload.get("candidate_id") != "MULTINAME_BREAKOUT_BULL_CALL_14D_V1":
        raise ValueError("unexpected frozen candidate id")
    if frozen_payload.get("strategy_outcome") != "STRATEGY_ADVANCED":
        raise ValueError("holdout may open only for a train-advanced candidate")
    if frozen_payload.get("funnel_stage_after") != "F1_TRAIN":
        raise ValueError("holdout may open only from F1_TRAIN")
    config = dict(frozen_payload.get("config", {}))
    bounds = list(config["control_breakout_ratio_bounds"])
    panel = close_panel.sort_index().copy()
    blueprints = build_matched_blueprints(
        panel,
        breakout_lookback_sessions=int(config["breakout_lookback_sessions"]),
        trend_lookback_sessions=int(config["trend_lookback_sessions"]),
        forward_sessions=int(config["forward_sessions"]),
        breakout_ratio_min=float(config["breakout_ratio_min"]),
        control_breakout_ratio_low=float(bounds[0]),
        control_breakout_ratio_high=float(bounds[1]),
        max_match_distance_sessions=int(config["max_match_distance_sessions"]),
        max_return_20d_distance=float(config["max_return_20d_distance"]),
        max_hv_20d_distance=float(config["max_hv_20d_distance"]),
    )
    verification = verify_frozen_population(
        frozen_payload,
        blueprints,
        train_fraction=float(config["train_fraction"]),
    )
    ordered = sorted(
        blueprints,
        key=lambda row: (pd.Timestamp(row["treated_signal_date"]), str(row["symbol"])),
    )
    split = int(len(ordered) * float(config["train_fraction"]))
    holdout_blueprints = ordered[split:]
    samples = int(bootstrap_samples or config["bootstrap_samples"])
    holdout = evaluate_holdout_partition(
        panel,
        holdout_blueprints,
        min_pairs=int(config["minimum_train_pairs"]),
        min_symbols=int(config["minimum_train_symbols"]),
        round_trip_cost_bps=float(config["round_trip_cost_bps"]),
        bootstrap_samples=samples,
        breakout_ratio_min=float(config["breakout_ratio_min"]),
        control_breakout_ratio_low=float(bounds[0]),
        control_breakout_ratio_high=float(bounds[1]),
        max_match_distance_sessions=int(config["max_match_distance_sessions"]),
        max_return_20d_distance=float(config["max_return_20d_distance"]),
        max_hv_20d_distance=float(config["max_hv_20d_distance"]),
    )
    diagnostics = build_concentration_diagnostics(
        holdout["pairs"],
        bootstrap_samples=samples,
    )
    advanced = bool(holdout["gate_pass"])
    outcome = "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED"
    stage_after = "F2_UNTOUCHED_HOLDOUT" if advanced else "F1_TRAIN"
    dominant_failure = _failure_mechanism(holdout["gate_checks"])
    payload = {
        key: value
        for key, value in frozen_payload.items()
        if key not in {
            "train",
            "untouched_holdout",
            "decision",
            "dominant_failure_mechanism",
            "f2_or_l1_claim",
        }
    }
    payload.update(
        {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase": "BUILD",
            "paper_only": True,
            "bar_claimed": "discovery_bar_L0_only",
            "strategy_outcome": outcome,
            "decision": (
                "advance F1_TRAIN to F2_UNTOUCHED_HOLDOUT under the unchanged pooled discovery gate"
                if advanced
                else "close the exact frozen breakout continuation family at the untouched holdout"
            ),
            "funnel_stage_before": "F1_TRAIN",
            "funnel_stage_after": stage_after,
            "confidence_stage": f"{stage_after}/L0",
            "funnel_claim_f2": advanced,
            "l1_claim": False,
            "closed_family": not advanced,
            "dominant_failure_mechanism": dominant_failure,
            "registration_eligible": False,
            "claim_scope": (
                "L0 underlying-only ten-session directional continuation. The holdout does not price options, "
                "measure debit-spread payoff capture, reconstruct fills, or establish L1/paper authority."
            ),
            "falsifier": (
                "On the exact final 40% frozen partition: n<80, symbols<6, non-positive treated mean after the "
                "same labeled 20-bps absolute-level sensitivity, non-positive paired excess mean, non-positive "
                "one-sided 90% five-pair circular-block bootstrap lower bound, or any population/integrity failure."
            ),
            "population_verification": verification,
            "frozen_train_reference": {
                "n_pairs": int(frozen_payload["train"]["n_pairs"]),
                "treated_mean_return_after_cost": float(
                    frozen_payload["train"]["treated_mean_return_after_cost"]
                ),
                "paired_excess_mean": float(frozen_payload["train"]["paired_excess_mean"]),
                "paired_excess_bootstrap_lb90": float(
                    frozen_payload["train"]["paired_excess_bootstrap_lb90"]
                ),
                "gate_pass": bool(frozen_payload["train"]["gate_pass"]),
            },
            "holdout": {
                **holdout,
                "outcome_metrics_read": True,
                "simulation_run": True,
                "one_shot_open": True,
                "concentration_diagnostics": diagnostics,
            },
            "option_stage": {
                "pricing_calls": 0,
                "option_payoff_simulated": False,
                "authority": "none",
                "reason": (
                    "underlying holdout is only an F2 discovery result; option payoff and cost evidence remain future work"
                    if advanced
                    else "underlying holdout falsified the family before option pricing"
                ),
            },
            "authority": {
                "l0_discovery": advanced,
                "l1_or_capital_seat": False,
                "paper_or_higher": False,
                "shadow_or_live": False,
            },
            "next_option_freeze_constraints": {
                "freeze_partition": "original_development_blueprints_only",
                "freeze_blueprints": int(verification["train_blueprints"]),
                "opened_holdout_role": "inspected_secondary_stress_only",
                "secondary_stress_blueprints": int(verification["holdout_blueprints"]),
                "retune_from_secondary_stress": False,
                "structure": "one_lot_14_dte_1_usd_wide_bull_call_debit_spread",
                "primary_metric": "absolute_after_cost_option_pnl_and_path_risk",
                "paired_underlying_excess_can_rescue_failure": False,
                "hard_time_stop_sessions": int(config["forward_sessions"]),
                "hold_to_expiry_is_primary_exit": False,
                "cost_axes": ["adverse_fixed_dollar_multileg", "adverse_percentage_multileg"],
                "listing_grid_required": True,
                "missing_listing_fails_closed": True,
                "symbol_time_concentration_required": True,
                "max_loss_usd_one_lot": 300.0,
                "window_max_drawdown_usd": 75.0,
                "authority_limit": "L0_proxy_no_L1_or_capital_seat",
            },
            "stand_aside_rule": (
                "Stand aside unless the lag-safe trigger fires and a future option package independently proves "
                "one-lot debit, cost, liquidity, and loss bounds; no option or paper authority exists now."
                if advanced
                else "Stand aside on this exact family; unchanged reruns are quarantined."
            ),
        }
    )
    json.dumps(payload, sort_keys=True, allow_nan=False)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open the frozen breakout continuation holdout exactly once."
    )
    parser.add_argument("--frozen", required=True, help="Frozen F1 train artifact JSON")
    parser.add_argument("--out", required=True, help="Strict-JSON one-shot holdout artifact")
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=None,
        help="Diagnostic override; omit to use the frozen sample count",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    frozen_path = Path(args.frozen).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    if out_path.exists():
        raise FileExistsError(f"refusing to reopen or overwrite one-shot holdout: {out_path}")
    frozen_bytes = frozen_path.read_bytes()
    frozen = json.loads(frozen_bytes)
    panel, source_verification = load_frozen_panel(frozen, repo_root=repo_root)
    payload = run_holdout_from_panel(
        frozen,
        panel,
        bootstrap_samples=args.bootstrap_samples,
    )
    payload["frozen_artifact"] = {
        "path": str(frozen_path),
        "sha256": hashlib.sha256(frozen_bytes).hexdigest(),
    }
    payload["data_provenance"] = {
        **dict(payload["data_provenance"]),
        "holdout_open_verification": source_verification,
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(encoded, encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out_path),
                "strategy_outcome": payload["strategy_outcome"],
                "funnel_stage_after": payload["funnel_stage_after"],
                "n_holdout_pairs": payload["holdout"]["n_pairs"],
                "paired_excess_mean": payload["holdout"]["paired_excess_mean"],
                "paired_excess_bootstrap_lb90": payload["holdout"][
                    "paired_excess_bootstrap_lb90"
                ],
                "pricing_calls": payload["option_stage"]["pricing_calls"],
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

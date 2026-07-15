#!/usr/bin/env python3
"""Train-only discovery of a Monday 45-DTE PCS early-exit mechanism.

Research-only BUILD/L0 experiment. It compares one fixed 21-DTE calendar stop
against an otherwise identical 5-DTE-stop control on the chronological first
60% of each symbol. The final 40% is partitioned but never simulated here.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data import build  # noqa: E402
from scripts.pcs_momentum_walkforward_lab import summarize_result  # noqa: E402
from trader_platform.research.pcs_sim import run_pcs_backtest  # noqa: E402

DEFAULT_SYMBOLS = ("BAC", "F", "SOFI", "PLTR", "TSLL", "SMCI", "AMD", "AAPL")
COST_AXES = {
    "slip_5pct": {"slippage_pct": 0.05},
    "fixed_0p01": {"half_spread_per_leg": 0.01},
}
MIN_TRADES = 8
MAX_LOSS_USD = 300.0


def early_exit_config() -> dict[str, Any]:
    """One fixed candidate DNA; no grid and no holdout-driven selection."""
    return {
        "structure": "put_credit_spread",
        "long_dte": 45,
        "long_target_delta": 0.20,
        "spread_width": 1.0,
        "min_credit_pct": 0.05,
        "iv_rank_min": 0.0,
        "profit_target": 0.40,
        "defined_loss_exit_frac": 0.70,
        "delta_breach": 0.45,
        "dte_stop": 21,
        "max_loss_budget_usd": MAX_LOSS_USD,
        "regime_flip_exit_enabled": True,
        "entry_weekdays": [0],
    }


def late_exit_control_config(candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    """Identical entry/management DNA except the late-cycle calendar stop."""
    control = dict(candidate or early_exit_config())
    control["dte_stop"] = 5
    return control


def _axis_value(row: dict[str, Any], gate_key: str, display_key: str) -> float:
    return float(row.get(gate_key, row.get(display_key) or 0.0))


def discovery_pass(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    """Predeclared F0→F1 discovery gate, deliberately weaker than the L1 bar."""
    if set(candidate) != set(COST_AXES) or set(control) != set(COST_AXES):
        return False
    for axis in COST_AXES:
        row = candidate[axis]
        control_row = control[axis]
        if not row.get("ok", False):
            return False
        if int(row.get("n_trades") or 0) < MIN_TRADES:
            return False
        if _axis_value(row, "gate_pnl", "pnl") <= 0.0:
            return False
        if _axis_value(row, "gate_max_loss_usd", "max_loss_usd") > MAX_LOSS_USD:
            return False
        if not row.get("integrity", False):
            return False
        if not control_row.get("ok", False):
            return False
        if int(control_row.get("n_trades") or 0) < MIN_TRADES:
            return False
        if not control_row.get("integrity", False):
            return False
    candidate_worst = min(_axis_value(candidate[axis], "gate_pnl", "pnl") for axis in COST_AXES)
    control_worst = min(_axis_value(control[axis], "gate_pnl", "pnl") for axis in COST_AXES)
    return candidate_worst > control_worst


def train_rank_key(row: dict[str, Any]) -> tuple[float, float, int, str]:
    """Rank eligible train rows without any holdout metric."""
    axes = row["train"]
    worst_pnl = min(_axis_value(axes[axis], "gate_pnl", "pnl") for axis in COST_AXES)
    worst_loss = max(
        _axis_value(axes[axis], "gate_max_loss_usd", "max_loss_usd") for axis in COST_AXES
    )
    minimum_n = min(int(axes[axis].get("n_trades") or 0) for axis in COST_AXES)
    return (worst_pnl, -worst_loss, minimum_n, str(row.get("symbol") or ""))


def management_diagnostics(result: Any) -> dict[str, Any]:
    """Persist proof that the candidate/control calendar stop was exercised."""
    metrics = result.metrics or {}
    exit_reasons = {
        str(reason): int(count)
        for reason, count in dict(metrics.get("exit_reasons") or {}).items()
    }
    calendar_stop_exits = int(exit_reasons.get("dte_stop", 0))
    return {
        "avg_days_held": float(metrics.get("avg_days_held") or 0.0),
        "exit_reasons": exit_reasons,
        "calendar_stop_exits": calendar_stop_exits,
        "calendar_stop_exercised": calendar_stop_exits > 0,
    }


def _operating_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Separate theoretical sleeve capacity from this experiment's one-lot cap."""
    return {
        **summary,
        "theoretical_max_lots": int(summary.get("max_lots") or 0),
        "operating_max_lots": 1,
        "max_lots": 1,
    }


def _run_axes(symbol: str, frame, config: dict[str, Any], label: str) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for axis, cost in COST_AXES.items():
        axis_config = {**config, **cost}
        result = run_pcs_backtest(
            symbol,
            period=f"{label}_{axis}",
            df=frame,
            min_bars=15,
            config=axis_config,
            structure="put_credit_spread",
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        summary = summarize_result(result, frame, axis_config)
        rows[axis] = {
            **_operating_summary(summary),
            **management_diagnostics(result),
        }
    return rows


def _capital_fields(axes: dict[str, Any]) -> dict[str, Any]:
    max_loss = max(
        _axis_value(axes[axis], "gate_max_loss_usd", "max_loss_usd") for axis in COST_AXES
    )
    capital_fit = max(
        max_loss,
        max(float(axes[axis].get("capital_fit_usd") or 0.0) for axis in COST_AXES),
    )
    return {
        "capital_fit_usd": capital_fit,
        "max_loss_usd": max_loss,
        "one_lot_max_loss_usd": max_loss,
        "operating_max_lots": 1,
        "max_lots": 1,
    }


def run_lab(*, symbols: list[str], period: str, train_fraction: float) -> dict[str, Any]:
    if not 0.50 <= float(train_fraction) <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    normalized = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    if len(normalized) < 2 or len(normalized) != len(set(normalized)):
        raise ValueError("symbols must contain at least two unique names")

    candidate_config = early_exit_config()
    control_config = late_exit_control_config(candidate_config)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for symbol in normalized:
        try:
            frame = build(symbol, period=period, use_cache=True)
            split_index = int(len(frame) * train_fraction)
            train = frame.iloc[:split_index].copy()
            holdout = frame.iloc[split_index:]
            if len(train) < 15 or len(holdout) < 15 or not train.index[-1] < holdout.index[0]:
                raise ValueError("train and holdout must be non-empty and strictly chronological")

            candidate_axes = _run_axes(symbol, train, candidate_config, "early_exit_train")
            control_axes = _run_axes(symbol, train, control_config, "late_exit_control_train")
            passed = discovery_pass(candidate_axes, control_axes)
            row = {
                "candidate_id": f"pcs_{symbol.lower()}_45dte_monday_exit21_v1",
                "symbol": symbol,
                "structure": "put_credit_spread",
                "funnel_stage_before": "F0_MECHANISM",
                "funnel_stage_after": "F1_TRAIN" if passed else "F0_MECHANISM",
                "bars": len(frame),
                "train_start": str(train.index[0].date()),
                "train_end": str(train.index[-1].date()),
                "untouched_holdout_start": str(holdout.index[0].date()),
                "untouched_holdout_end": str(holdout.index[-1].date()),
                "chronology_ok": bool(train.index[-1] < holdout.index[0]),
                "train": candidate_axes,
                "late_exit_control_train": control_axes,
                "discovery_pass": passed,
                **_capital_fields(candidate_axes),
            }
            rows.append(row)
            print(
                f"{symbol}: train_n={min(candidate_axes[a]['n_trades'] for a in COST_AXES)} "
                f"worst_pnl={min(_axis_value(candidate_axes[a], 'gate_pnl', 'pnl') for a in COST_AXES):.2f} "
                f"pass={passed}",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"symbol": symbol, "error": str(exc)})

    survivors = [row for row in rows if row["discovery_pass"]]
    survivor = max(survivors, key=train_rank_key) if survivors else None
    pooled_worst_axis_pnl = sum(
        min(_axis_value(row["train"][axis], "gate_pnl", "pnl") for axis in COST_AXES)
        for row in survivors
    )
    advanced = survivor is not None and pooled_worst_axis_pnl > 0.0
    selected_candidate_id = survivor["candidate_id"] if survivor is not None and advanced else None
    selected_symbol = survivor["symbol"] if survivor is not None and advanced else None
    ranking_complete = len(errors) == 0 and len(rows) == len(normalized)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_PROXY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "economic_mechanism": "front-loaded 45-DTE put-spread theta harvest with a 21-DTE calendar exit avoids late-cycle gamma/tail exposure versus an identical 5-DTE-stop control",
        "candidate_or_family_scope": "fixed-DNA Monday 45-DTE put credit spreads across eight outcome-rank-free symbols; one train-ranked survivor only",
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "falsifier": "no symbol has n>=8 and positive PnL on both proxy cost axes with exact integrity, one-lot max loss<=300, and strictly better worst-axis PnL than the identical 5-DTE-stop control; pooled qualifying worst-axis PnL must also be positive",
        "claim_scope": "historical underlying bars with listed-Friday/rounded-strike daily-bar Black-Scholes marks; train-only L0 discovery; untouched final 40% not simulated; cannot earn L1 or a capital seat",
        "option_mark_provenance": "black_scholes_proxy",
        "cost_axes": ["5pct adverse leg slip", "$0.01 half-spread per leg at entry and exit"],
        "candidate_config": candidate_config,
        "control_config": control_config,
        "gates": {
            "minimum_trades_each_train_cost_axis": MIN_TRADES,
            "positive_pnl_each_train_cost_axis": True,
            "max_loss_usd_one_lot": MAX_LOSS_USD,
            "exact_integrity": True,
            "candidate_worst_axis_pnl_strictly_above_control": True,
            "pooled_qualifying_worst_axis_pnl_positive": True,
        },
        "validity": {
            "selection": "one fixed candidate and one otherwise-identical control; one survivor ranked on train only",
            "holdout": "final 40% partition boundaries recorded but no holdout simulation or metric read in this wake",
            "population": normalized,
            "population_pure": all(row["structure"] == "put_credit_spread" for row in rows),
            "ranking_complete": ranking_complete,
            "registry_writes": False,
            "capital_seat_claim": False,
        },
        "train_fraction": train_fraction,
        "n_symbols": len(normalized),
        "n_completed": len(rows),
        "n_discovery_pass": len(survivors),
        "pooled_qualifying_worst_axis_pnl": pooled_worst_axis_pnl,
        "selected_candidate_id": selected_candidate_id,
        "selected_symbol": selected_symbol,
        "strategy_advanced": advanced,
        "decision": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "errors": errors,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--period", default="5y")
    parser.add_argument("--train-fraction", type=float, default=0.60)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    payload = run_lab(
        symbols=[value.strip().upper() for value in args.symbols.split(",") if value.strip()],
        period=args.period,
        train_fraction=args.train_fraction,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: payload[key]
                for key in (
                    "decision",
                    "n_completed",
                    "n_discovery_pass",
                    "pooled_qualifying_worst_axis_pnl",
                    "selected_candidate_id",
                    "errors",
                )
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0 if payload["validity"]["ranking_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

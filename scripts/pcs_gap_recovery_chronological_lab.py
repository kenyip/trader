#!/usr/bin/env python3
"""Chronological falsification of one lagged gap-recovery 21-DTE PCS family.

Research-only BUILD/L0 experiment. The economic mechanism is panic absorption:
a completed session gaps down at least 1%, recovers to close at or above its open,
and closes strictly above a 60-session EMA known before that signal session. Entry
is allowed only on the following bar. No registry, paper, broker, or live mutation.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data import build  # noqa: E402
from scripts.pcs_momentum_walkforward_lab import COST_AXES, MAX_DD, MAX_DENSE_NEG, MAX_LOSS, MIN_TRADES  # noqa: E402
from scripts.pcs_pullback_rolling_origin_lab import _holdout_windows, _run_pass, run_cost_axes  # noqa: E402
from trader_platform.research.pcs_sim import entry_filters_pass  # noqa: E402

DEFAULT_SYMBOLS = ("BAC", "F", "SOFI", "PLTR", "TSLL", "SMCI", "AMD", "AAPL")


def prepare_gap_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add no-lookahead gap, recovery, and lagged-trend features."""
    required = {"open", "close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"missing required gap feature columns: {missing}")
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError("gap feature frame index must be unique and monotonic increasing")

    prepared = frame.copy()
    open_px = pd.Series(
        pd.to_numeric(prepared["open"], errors="coerce"),
        index=prepared.index,
        dtype=float,
    )
    close_px = pd.Series(
        pd.to_numeric(prepared["close"], errors="coerce"),
        index=prepared.index,
        dtype=float,
    )
    previous_close = close_px.shift(1)
    # A 60-session state is undefined until 60 completed closes exist; shifting
    # then makes the warmed value available only before the following signal bar.
    lagged_ema = close_px.ewm(span=60, adjust=False, min_periods=60).mean().shift(1)
    prepared["gap_return"] = open_px / previous_close - 1.0
    prepared["intraday_return"] = close_px / open_px - 1.0
    prepared["lagged_ema_60"] = lagged_ema
    prepared["close_vs_lagged_ema60"] = close_px / lagged_ema - 1.0
    return prepared


def gap_recovery_config() -> dict[str, Any]:
    """One fixed, predeclared defined-risk DNA; no parameter grid."""
    return {
        "structure": "put_credit_spread",
        "long_dte": 21,
        "long_target_delta": 0.20,
        "spread_width": 1.0,
        "min_credit_pct": 0.05,
        "iv_rank_min": 0.0,
        "profit_target": 0.40,
        "defined_loss_exit_frac": 0.70,
        "delta_breach": 0.45,
        "dte_stop": 5,
        "max_loss_budget_usd": MAX_LOSS,
        "regime_flip_exit_enabled": True,
        "entry_signal_lag_bars": 1,
        "entry_gap_return_max": -0.01,
        "entry_intraday_return_min": 0.0,
        # Strictly above, while entry filters themselves remain inclusive.
        "entry_close_vs_lagged_ema60_min": float(np.nextafter(0.0, np.inf)),
    }


def failed_recovery_control(config: dict[str, Any]) -> dict[str, Any]:
    """Same downside-gap family, but a strictly negative signal-day recovery."""
    excluded = {"entry_intraday_return_min", "entry_close_vs_lagged_ema60_min"}
    control = {key: value for key, value in config.items() if key not in excluded}
    control["entry_intraday_return_max"] = float(np.nextafter(0.0, -np.inf))
    return control


def unconditional_control(config: dict[str, Any]) -> dict[str, Any]:
    """Same PCS DNA without signal selection; retain one-bar lag semantics."""
    control = {key: value for key, value in config.items() if not key.startswith("entry_")}
    control["entry_signal_lag_bars"] = 1
    return control


def _candidate_pass(
    train_axes: dict[str, Any],
    holdout_axes: dict[str, Any],
    holdout_windows: dict[str, Any],
) -> bool:
    """Conjunctive train and untouched-holdout absolute gate."""
    return bool(
        all(_run_pass(train_axes[axis]) for axis in COST_AXES)
        and all(_run_pass(holdout_axes[axis]) for axis in COST_AXES)
        and all(
            int(holdout_windows[axis]["dense_negative_n"]) <= MAX_DENSE_NEG
            and float(holdout_windows[axis]["window_max_dd"]) <= MAX_DD
            and bool(holdout_windows[axis]["integrity"])
            for axis in COST_AXES
        )
    )


def _capital_fields(
    train_axes: dict[str, Any],
    holdout_axes: dict[str, Any],
) -> dict[str, Any]:
    """Report one-lot capital from the worst observed required-capital/loss row."""
    axis_rows = [
        sample[axis]
        for sample in (train_axes, holdout_axes)
        for axis in COST_AXES
    ]
    one_lot_max_loss = max(
        float(row.get("gate_max_loss_usd", row.get("max_loss_usd") or 0.0))
        for row in axis_rows
    )
    capital_fit = max(
        one_lot_max_loss,
        max(float(row.get("capital_fit_usd") or 0.0) for row in axis_rows),
    )
    return {
        "capital_fit_usd": capital_fit,
        "one_lot_max_loss_usd": one_lot_max_loss,
        "max_lots": 1,
    }


def _signal_count(frame: pd.DataFrame, config: dict[str, Any]) -> int:
    return sum(bool(entry_filters_pass(row, config)) for _, row in frame.iterrows())


def _failure_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    failures: Counter[str] = Counter()
    for candidate in rows:
        for sample in ("train", "untouched_holdout"):
            axes = candidate[sample]
            for axis in COST_AXES:
                row = axes[axis]
                prefix = f"{sample}.{axis}"
                if not row.get("ok", False):
                    failures[f"{prefix}.not_ok"] += 1
                if int(row.get("n_trades") or 0) < MIN_TRADES:
                    failures[f"{prefix}.thin_lt_{MIN_TRADES}"] += 1
                if float(row.get("gate_pnl", row.get("pnl") or 0.0)) <= 0.0:
                    failures[f"{prefix}.nonpositive_pnl"] += 1
                if row.get("verdict") != "SHIP":
                    failures[f"{prefix}.not_ship"] += 1
                if float(row.get("gate_max_loss_usd", row.get("max_loss_usd") or 0.0)) > MAX_LOSS:
                    failures[f"{prefix}.max_loss_gt_{int(MAX_LOSS)}"] += 1
                if float(row.get("gate_dd", row.get("dd") or 0.0)) > MAX_DD:
                    failures[f"{prefix}.dd_gt_{int(MAX_DD)}"] += 1
                if not row.get("integrity", False):
                    failures[f"{prefix}.integrity"] += 1
        for axis in COST_AXES:
            window = candidate["holdout_windows"][axis]
            if int(window["dense_negative_n"]) > MAX_DENSE_NEG:
                failures[f"untouched_holdout.{axis}.dense_negative_gt_{MAX_DENSE_NEG}"] += 1
            if float(window["window_max_dd"]) > MAX_DD:
                failures[f"untouched_holdout.{axis}.window_dd_gt_{int(MAX_DD)}"] += 1
            if not window["integrity"]:
                failures[f"untouched_holdout.{axis}.window_integrity"] += 1
    return dict(sorted(failures.items(), key=lambda item: (-item[1], item[0])))


def run_lab(*, symbols: list[str], period: str, train_fraction: float) -> dict[str, Any]:
    if not 0.50 <= float(train_fraction) <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    normalized = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    if len(normalized) < 2 or len(set(normalized)) != len(normalized):
        raise ValueError("symbols must contain at least two unique names")

    config = gap_recovery_config()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for symbol in normalized:
        try:
            frame = prepare_gap_features(build(symbol, period=period, use_cache=True))
            split_index = int(len(frame) * train_fraction)
            train = frame.iloc[:split_index].copy()
            holdout = frame.iloc[split_index:].copy()
            if len(train) < 15 or len(holdout) < 15 or not train.index[-1] < holdout.index[0]:
                raise ValueError("train and holdout must be non-empty and strictly chronological")

            train_axes = run_cost_axes(symbol, train, config, "gap_recovery_train")
            holdout_axes = run_cost_axes(symbol, holdout, config, "gap_recovery_untouched_holdout")
            windows = _holdout_windows(symbol, holdout, config)
            passed = _candidate_pass(train_axes, holdout_axes, windows)
            capital = _capital_fields(train_axes, holdout_axes)
            rows.append(
                {
                    "candidate_id": f"gap_recovery_pcs_{symbol.lower()}_21dte_v1",
                    "symbol": symbol,
                    "structure": "put_credit_spread",
                    "funnel_stage_before": "F0_MECHANISM",
                    "funnel_stage_after": "F2_UNTOUCHED_HOLDOUT" if passed else "F0_MECHANISM",
                    "bars": len(frame),
                    "train_start": str(train.index[0].date()),
                    "train_end": str(train.index[-1].date()),
                    "holdout_start": str(holdout.index[0].date()),
                    "holdout_end": str(holdout.index[-1].date()),
                    "chronology_ok": bool(train.index[-1] < holdout.index[0]),
                    "signal_counts": {
                        "train": _signal_count(train, config),
                        "untouched_holdout": _signal_count(holdout, config),
                    },
                    "train": train_axes,
                    "untouched_holdout": holdout_axes,
                    "holdout_windows": windows,
                    "controls": {
                        "unconditional_pcs": run_cost_axes(
                            symbol,
                            holdout,
                            unconditional_control(config),
                            "gap_recovery_holdout_unconditional",
                        ),
                        "failed_recovery_gap_pcs": run_cost_axes(
                            symbol,
                            holdout,
                            failed_recovery_control(config),
                            "gap_recovery_holdout_failed_recovery",
                        ),
                    },
                    **capital,
                    "candidate_pass": passed,
                }
            )
            print(
                f"{symbol}: signals={rows[-1]['signal_counts']} candidate_pass={passed}",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"symbol": symbol, "error": str(exc)})

    passes = [row for row in rows if row["candidate_pass"]]
    ranking_complete = len(errors) == 0 and len(rows) == len(normalized)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_PROXY",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "open_risk_budget_usd": 750.0,
        "economic_mechanism": "confirmed panic absorption after a downside overnight gap inside a lagged long-term uptrend, harvested with next-bar 21-DTE defined-risk put premium",
        "candidate_or_family_scope": "fixed-DNA lagged gap-recovery 21-DTE put credit spread across an outcome-rank-free eight-symbol set",
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F2_UNTOUCHED_HOLDOUT" if passes else "F0_MECHANISM",
        "hypothesis": "a completed >=1% downside gap that recovers to close at or above open and strictly above a pre-signal EMA60 identifies panic absorption that improves next-bar 21-DTE PCS income after both proxy cost axes",
        "falsifier": "no named candidate passes train AND untouched holdout with n>=8 and positive SHIP on 5% slip and fixed-$0.01-per-leg axes, one-lot max loss <=300, DD and window DD <=75, dense-negative windows <=5, exact ledger/signal integrity, and complete chronology/population evidence",
        "claim_scope": "historical underlying bars with listed-Friday/rounded-strike daily-bar Black-Scholes option marks; BUILD L0 discovery/falsification only; cannot earn L1 or live authority",
        "option_mark_provenance": "black_scholes_proxy",
        "config": config,
        "controls": ["same-DTE unconditional PCS", "same-gap strictly failed-recovery PCS"],
        "gates": {
            "minimum_trades_each_train_and_holdout_cost_axis": MIN_TRADES,
            "positive_ship_each_cost_axis": True,
            "max_loss_usd": MAX_LOSS,
            "max_dd_usd": MAX_DD,
            "dense_negative_windows_each_cost_axis": MAX_DENSE_NEG,
            "train_and_untouched_holdout_required": True,
            "integrity": True,
        },
        "validity": {
            "selection": "one predeclared DNA; no parameter grid and no holdout-driven selection",
            "symbol_selection": "fixed caller-independent outcome-rank-free set",
            "signal": "gap/recovery uses one completed signal session; EMA60 is shifted one additional session; entry_signal_lag_bars=1",
            "cost_axes": ["5pct adverse leg slip", "$0.01 half-spread per leg at entry and exit"],
            "population_pure": all(row["structure"] == "put_credit_spread" for row in rows),
            "ranking_complete": ranking_complete,
            "registry_writes": False,
            "claim_limit": "L0 only; proxy result cannot earn L1",
        },
        "train_fraction": train_fraction,
        "symbols": normalized,
        "n_symbols": len(normalized),
        "n_completed": len(rows),
        "n_candidate_pass": len(passes),
        "candidate_pass_ids": [row["candidate_id"] for row in passes],
        "dominant_failure_counts": _failure_counts(rows),
        "errors": errors,
        "decision": (
            "DISCOVERY_PASS_GAP_RECOVERY_PCS_REQUIRES_PAPER_CALIBRATION"
            if passes
            else "REJECT_GAP_RECOVERY_PCS_CHRONOLOGICAL_DUAL_COST"
        ),
        "registration_eligible_ids": [],
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--period", default="5y")
    parser.add_argument("--train-fraction", type=float, default=0.60)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    payload = run_lab(symbols=symbols, period=args.period, train_fraction=args.train_fraction)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: payload[key]
                for key in (
                    "decision",
                    "n_completed",
                    "n_candidate_pass",
                    "candidate_pass_ids",
                    "errors",
                )
            },
            indent=2,
        )
    )
    return 0 if payload["validity"]["ranking_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

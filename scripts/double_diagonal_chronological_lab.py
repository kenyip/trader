#!/usr/bin/env python3
"""Reproducible L0 chronological reject-unless lab for double diagonals."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data import build  # noqa: E402
from trader_platform.research.double_diagonal_sim import (  # noqa: E402
    DoubleDiagonalSimResult,
    run_double_diagonal_backtest,
)
from trader_platform.strategy_dna import dna_from_structure  # noqa: E402

MIN_TRADES = 8
MIN_DENSE_WINDOW_TRADES = 3
MAX_LOSS_USD = 300.0
MAX_DD_USD = 75.0
MAX_DENSE_NEGATIVE_WINDOWS = 5
WINDOW_BARS = 63
COST_AXES = {
    "slip_5pct": {"slippage_pct": 0.05},
    "fixed_0p01": {"half_spread_per_leg": 0.01},
}
DEFAULT_SYMBOLS = ("BAC", "F", "SOFI", "PLTR", "TSLL", "SMCI", "AMD", "AAPL")


def summarize(result: DoubleDiagonalSimResult) -> dict[str, Any]:
    recomputed = sum(
        (((trade.exit_credit if trade.exit_credit is not None else 0.0) - trade.entry_debit) * 100.0)
        for trade in result.trades
    )
    pnl = float(result.metrics.get("total_pnl_per_contract") or 0.0)
    ledger_delta = recomputed - pnl
    same_bar_reentries = sum(
        previous.exit_date == following.entry_date
        for previous, following in zip(result.trades, result.trades[1:])
    )
    max_dd = float(result.metrics.get("max_dd_per_contract") or 0.0)
    max_loss = float(result.capital.get("max_loss_usd") or 0.0)
    gate_pass = bool(
        result.ok
        and not result.skipped
        and result.n_trades >= MIN_TRADES
        and pnl > 0.0
        and max_dd <= MAX_DD_USD
        and 0.0 < max_loss <= MAX_LOSS_USD
        and abs(ledger_delta) <= 1e-8
        and same_bar_reentries == 0
    )
    return {
        "ok": bool(result.ok),
        "reason": result.reason,
        "n_trades": int(result.n_trades),
        "pnl": pnl,
        "max_dd": max_dd,
        "max_loss_usd": max_loss,
        "structural_max_loss_usd": float(
            result.capital.get("structural_max_loss_usd") or 0.0
        ),
        "observed_path_worst_loss_usd": float(
            result.capital.get("observed_path_worst_loss_usd") or 0.0
        ),
        "capital_fit": result.capital.get("capital_fit"),
        "ledger_delta": ledger_delta,
        "same_bar_reentries": int(same_bar_reentries),
        "gate_pass": gate_pass,
    }


def summarize_windows(symbol: str, frame: Any, config: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for start in range(0, len(frame), WINDOW_BARS):
        window = frame.iloc[start : start + WINDOW_BARS]
        if len(window) < 15:
            continue
        result = run_double_diagonal_backtest(
            symbol,
            period="holdout_window",
            df=window,
            config=config,
            min_bars=15,
        )
        row = summarize(result)
        row["label"] = f"{window.index[0].date()}_{window.index[-1].date()}"
        rows.append(row)
    dense_negative = [
        row["label"]
        for row in rows
        if row["n_trades"] >= MIN_DENSE_WINDOW_TRADES and row["pnl"] < 0.0
    ]
    return {
        "n_windows": len(rows),
        "window_max_dd": max((float(row["max_dd"]) for row in rows), default=0.0),
        "dense_negative_n": len(dense_negative),
        "dense_negative_labels": dense_negative,
        "integrity": all(
            abs(float(row["ledger_delta"])) <= 1e-8
            and int(row["same_bar_reentries"]) == 0
            for row in rows
        ),
        "rows": rows,
    }


def complete_evidence_gate(
    train: dict[str, Any], holdout: dict[str, Any], windows: dict[str, Any]
) -> bool:
    """Require train AND untouched holdout AND window-integrity gates."""
    return bool(
        train.get("ok")
        and train.get("gate_pass")
        and holdout.get("ok")
        and holdout.get("gate_pass")
        and windows.get("integrity")
        and float(windows.get("window_max_dd", float("inf"))) <= MAX_DD_USD
        and int(windows.get("dense_negative_n", MAX_DENSE_NEGATIVE_WINDOWS + 1))
        <= MAX_DENSE_NEGATIVE_WINDOWS
    )


def run_lab(symbols: list[str], stamp: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for symbol in symbols:
        try:
            frame = build(symbol, period="5y", use_cache=True)
            split_index = int(len(frame) * 0.60)
            train_frame = frame.iloc[:split_index]
            holdout_frame = frame.iloc[split_index:]
            base = dna_from_structure("double_diagonal_spread", [symbol]).sim_config()
            axes: dict[str, Any] = {}
            windows_by_axis: dict[str, Any] = {}
            axis_passes: list[bool] = []
            for axis, costs in COST_AXES.items():
                config = {**base, **costs}
                train = summarize(
                    run_double_diagonal_backtest(
                        symbol, period="train", df=train_frame, config=config
                    )
                )
                holdout = summarize(
                    run_double_diagonal_backtest(
                        symbol, period="holdout", df=holdout_frame, config=config
                    )
                )
                windows = summarize_windows(symbol, holdout_frame, config)
                axes[axis] = {"train": train, "holdout": holdout}
                windows_by_axis[axis] = windows
                axis_passes.append(complete_evidence_gate(train, holdout, windows))
            rows.append(
                {
                    "symbol": symbol,
                    "bars": len(frame),
                    "split": {
                        "train_bars": len(train_frame),
                        "train_start": str(train_frame.index[0].date()),
                        "train_end": str(train_frame.index[-1].date()),
                        "holdout_bars": len(holdout_frame),
                        "holdout_start": str(holdout_frame.index[0].date()),
                        "holdout_end": str(holdout_frame.index[-1].date()),
                    },
                    "axes": axes,
                    "holdout_windows": windows_by_axis,
                    "all_axes_pass": all(axis_passes),
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"symbol": symbol, "error": str(exc)})
    passes = [row for row in rows if row["all_axes_pass"]]
    return {
        "stamp": stamp,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD",
        "paper_only": True,
        "sleeve_usd": 3000.0,
        "structure": "double_diagonal_spread",
        "population": symbols,
        "cost_axes": COST_AXES,
        "gates": {
            "min_trades": MIN_TRADES,
            "positive_pnl": True,
            "max_loss_usd": MAX_LOSS_USD,
            "max_dd_usd": MAX_DD_USD,
            "window_bars": WINDOW_BARS,
            "max_dense_negative_windows": MAX_DENSE_NEGATIVE_WINDOWS,
            "integrity": True,
            "all_train_holdout_cost_axes_required": True,
        },
        "hypothesis": (
            "one predeclared neutral-regime 14/60-DTE symmetric double-calendar proxy "
            "remains positive and bounded on both chronological train and untouched holdout "
            "under exact four-leg 5% adverse percentage slip and $0.01 half-spread per leg"
        ),
        "falsifier": (
            "reject when no symbol passes train and holdout on both costs with n>=8, "
            "positive PnL, one-lot observed-path loss<=300, max DD<=75, exact ledger/no "
            "same-bar reentry, holdout window DD<=75, and dense-negative windows<=5"
        ),
        "claim_scope": (
            "Black-Scholes daily-bar proxy discovery only; American intrinsic floor protects "
            "same/inward back legs, but signed closing friction is retained; no observed "
            "historical option surfaces, quote fills, assignment calibration, L1, "
            "registration, or capital seat"
        ),
        "n_symbols": len(symbols),
        "n_completed": len(rows),
        "n_all_axes_pass": len(passes),
        "errors": errors,
        "rows": rows,
        "decision": (
            "DOUBLE_DIAGONAL_PROXY_PASS_REQUIRES_OBSERVED_VALIDATION"
            if passes
            else "REJECT_DOUBLE_DIAGONAL_PROXY_THIS_CYCLE"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--stamp", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = run_lab([str(symbol).upper() for symbol in args.symbols], args.stamp)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "n_completed": payload["n_completed"],
                "n_all_axes_pass": payload["n_all_axes_pass"],
                "errors": payload["errors"],
            },
            indent=2,
        )
    )
    return 0 if not payload["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

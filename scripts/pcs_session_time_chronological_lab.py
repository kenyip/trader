#!/usr/bin/env python3
"""Chronological L0 session-time lab for PCS/CCS/IC on 30-minute bars."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from trader_platform.research.intraday_session_data import download_session_frame  # noqa: E402
from trader_platform.research.pcs_sim import PcsSimResult, run_pcs_backtest  # noqa: E402

BUCKETS = ("open", "midday", "late")
STRUCTURES = ("put_credit_spread", "call_credit_spread", "iron_condor")
COST_AXES = {
    "slip_5pct": {"slippage_pct": 0.05},
    "fixed_0p01": {"half_spread_per_leg": 0.01},
}
DEFAULT_SYMBOLS = ("BAC", "F", "SOFI", "PLTR", "TSLL", "SMCI", "AMD", "AAPL")
MIN_TRADES = 3
MAX_LOSS_USD = 300.0
MAX_DD_USD = 75.0
MAX_DENSE_NEGATIVE_WINDOWS = 5
MIN_DENSE_WINDOW_TRADES = 2
WINDOW_MARKET_DATES = 10


def split_by_market_date(
    frame: pd.DataFrame, *, train_fraction: float = 0.6
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "market_date" not in frame.columns:
        raise ValueError("session frame must include market_date")
    dates = list(dict.fromkeys(frame["market_date"].tolist()))
    if len(dates) < 10:
        raise ValueError("session frame needs at least 10 market dates")
    split = max(1, min(len(dates) - 1, int(len(dates) * float(train_fraction))))
    train_dates = set(dates[:split])
    holdout_dates = set(dates[split:])
    train = frame[frame["market_date"].isin(train_dates)].copy()
    holdout = frame[frame["market_date"].isin(holdout_dates)].copy()
    return train, holdout


def _config(structure: str, bucket: Optional[str]) -> dict[str, Any]:
    config: dict[str, Any] = {
        "structure": structure,
        "long_dte": 7,
        "long_target_delta": 0.20,
        "spread_width": 1.0,
        "min_credit_pct": 0.02,
        "iv_rank_min": 0.0,
        "profit_target": 0.40,
        "defined_loss_exit_frac": 0.70,
        "delta_breach": 0.45,
        "dte_stop": 2,
        "max_loss_budget_usd": MAX_LOSS_USD,
        "regime_flip_exit_enabled": True,
        "entry_signal_lag_bars": 1,
    }
    if bucket is not None:
        config["entry_session_buckets"] = [bucket]
    return config


def _bucket_for_timestamp(timestamp: pd.Timestamp) -> str:
    minute = timestamp.hour * 60 + timestamp.minute
    if minute < 11 * 60:
        return "open"
    if minute < 14 * 60:
        return "midday"
    return "late"


def summarize_result(result: PcsSimResult) -> dict[str, Any]:
    recomputed = sum(
        (trade.net_credit - float(trade.exit_debit or 0.0)) * 100.0
        for trade in result.trades
    )
    pnl = float(result.metrics.get("total_pnl_per_contract") or 0.0)
    ledger_delta = recomputed - pnl
    same_bar_reentries = sum(
        previous.exit_date == following.entry_date
        for previous, following in zip(result.trades, result.trades[1:])
    )
    same_session_bucket_reentries = sum(
        previous.exit_date is not None
        and pd.Timestamp(previous.exit_date).date() == pd.Timestamp(following.entry_date).date()
        and _bucket_for_timestamp(pd.Timestamp(previous.exit_date))
        == _bucket_for_timestamp(pd.Timestamp(following.entry_date))
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
        and same_session_bucket_reentries == 0
    )
    return {
        "ok": bool(result.ok),
        "reason": result.reason,
        "n_trades": int(result.n_trades),
        "pnl": pnl,
        "max_dd": max_dd,
        "max_loss_usd": max_loss,
        "capital_fit_usd": float(result.capital.get("capital_fit_usd") or 0.0),
        "max_lots": int(result.capital.get("max_lots") or 0),
        "ledger_delta": ledger_delta,
        "same_bar_reentries": int(same_bar_reentries),
        "same_session_bucket_reentries": int(same_session_bucket_reentries),
        "gate_pass": gate_pass,
    }


def run_cost_axes(
    symbol: str,
    structure: str,
    bucket: Optional[str],
    frame: pd.DataFrame,
    label: str,
) -> dict[str, Any]:
    base = _config(structure, bucket)
    rows: dict[str, Any] = {}
    for axis, costs in COST_AXES.items():
        result = run_pcs_backtest(
            symbol,
            period=f"session_{label}_{axis}",
            df=frame,
            min_bars=15,
            structure=structure,
            config={**base, **costs},
        )
        rows[axis] = summarize_result(result)
    return rows


def select_train_bucket(rows: dict[str, dict[str, Any]]) -> Optional[str]:
    passing = [
        bucket
        for bucket, axes in rows.items()
        if all(bool(axes[axis].get("gate_pass")) for axis in COST_AXES)
    ]
    if not passing:
        return None
    return max(
        passing,
        key=lambda bucket: (
            min(float(rows[bucket][axis]["pnl"]) for axis in COST_AXES),
            -BUCKETS.index(bucket),
        ),
    )


def _diagnostic_bucket(rows: dict[str, dict[str, Any]]) -> str:
    return max(
        rows,
        key=lambda bucket: (
            min(float(rows[bucket][axis]["pnl"]) for axis in COST_AXES),
            -BUCKETS.index(bucket),
        ),
    )


def _window_summary(
    symbol: str,
    structure: str,
    bucket: str,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    dates = list(dict.fromkeys(frame["market_date"].tolist()))
    by_axis: dict[str, Any] = {}
    for axis, costs in COST_AXES.items():
        rows = []
        for start in range(0, len(dates), WINDOW_MARKET_DATES):
            selected_dates = set(dates[start : start + WINDOW_MARKET_DATES])
            window = frame[frame["market_date"].isin(selected_dates)]
            if len(window) < 15:
                continue
            result = run_pcs_backtest(
                symbol,
                period=f"session_window_{axis}_{start}",
                df=window,
                min_bars=15,
                structure=structure,
                config={**_config(structure, bucket), **costs},
            )
            row = summarize_result(result)
            row["label"] = f"{min(selected_dates)}_{max(selected_dates)}"
            rows.append(row)
        dense_negative = [
            row["label"]
            for row in rows
            if int(row["n_trades"]) >= MIN_DENSE_WINDOW_TRADES and float(row["pnl"]) < 0.0
        ]
        by_axis[axis] = {
            "n_windows": len(rows),
            "window_max_dd": max((float(row["max_dd"]) for row in rows), default=0.0),
            "dense_negative_n": len(dense_negative),
            "dense_negative_labels": dense_negative,
            "integrity": all(
                abs(float(row["ledger_delta"])) <= 1e-8
                and int(row["same_bar_reentries"]) == 0
                and int(row["same_session_bucket_reentries"]) == 0
                for row in rows
            ),
            "rows": rows,
        }
    return by_axis


def complete_gate(
    train_axes: dict[str, Any],
    holdout_axes: dict[str, Any],
    windows: dict[str, Any],
) -> bool:
    return bool(
        all(bool(train_axes[axis].get("gate_pass")) for axis in COST_AXES)
        and all(bool(holdout_axes[axis].get("gate_pass")) for axis in COST_AXES)
        and all(
            bool(windows[axis].get("integrity"))
            and float(windows[axis].get("window_max_dd", float("inf"))) <= MAX_DD_USD
            and int(windows[axis].get("dense_negative_n", MAX_DENSE_NEGATIVE_WINDOWS + 1))
            <= MAX_DENSE_NEGATIVE_WINDOWS
            for axis in COST_AXES
        )
    )


def run_lab(symbols: list[str], structures: list[str], stamp: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    data_ranges: dict[str, Any] = {}
    raw_dir = REPO / ".cache" / "platform" / "intraday_underlying" / stamp
    for symbol in symbols:
        try:
            frame = download_session_frame(
                symbol,
                raw_out=raw_dir / f"{symbol}_60d_30m.csv",
            )
            train, holdout = split_by_market_date(frame)
            data_ranges[symbol] = {
                "bars": len(frame),
                "market_dates": int(frame["market_date"].nunique()),
                "start": str(frame.index.min()),
                "end": str(frame.index.max()),
                "train_dates": int(train["market_date"].nunique()),
                "holdout_dates": int(holdout["market_date"].nunique()),
            }
            for structure in structures:
                train_buckets = {
                    bucket: run_cost_axes(symbol, structure, bucket, train, f"train_{bucket}")
                    for bucket in BUCKETS
                }
                selected = select_train_bucket(train_buckets)
                diagnostic = _diagnostic_bucket(train_buckets)
                holdout_axes: dict[str, Any] = {}
                windows: dict[str, Any] = {}
                all_axes_pass = False
                if selected is not None:
                    holdout_axes = run_cost_axes(
                        symbol, structure, selected, holdout, f"holdout_{selected}"
                    )
                    windows = _window_summary(symbol, structure, selected, holdout)
                    all_axes_pass = complete_gate(
                        train_buckets[selected], holdout_axes, windows
                    )
                rows.append(
                    {
                        "symbol": symbol,
                        "structure": structure,
                        "train_buckets": train_buckets,
                        "selected_bucket": selected,
                        "diagnostic_best_bucket": diagnostic,
                        "train_gate_pass": selected is not None,
                        "holdout": holdout_axes,
                        "holdout_windows": windows,
                        "all_axes_pass": all_axes_pass,
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
        "structures": structures,
        "structure_risk": {
            structure: {
                "capital_fit_usd": "per train/holdout axis",
                "max_loss_usd": f"required <= {MAX_LOSS_USD:.0f}",
                "max_lots": "reported by axis; operating posture 1 lot",
            }
            for structure in structures
        },
        "population": symbols,
        "data_ranges": data_ranges,
        "hypothesis": (
            "one open/midday/late 30-minute entry bucket selected only on chronological train "
            "improves a defined-risk PCS, CCS, or IC proxy and remains positive and bounded "
            "on untouched holdout under both adverse cost axes"
        ),
        "falsifier": (
            "reject when no symbol/structure has a train-selected bucket that independently "
            "passes train and untouched holdout at 5% leg slip and $0.01 half-spread per leg "
            "with n>=3, positive PnL, max_loss<=300, max/window DD<=75, dense negatives<=5, "
            "exact ledger, and no same-bar or same-date/session-bucket reentry"
        ),
        "claim_scope": (
            "60-day yfinance 30-minute underlying history with prior-completed-session regime/IV "
            "features and synthetic listed-Friday/rounded-strike Black-Scholes option marks; "
            "L0 discovery/falsification only, no observed option fills, L1, registration, paper, "
            "shadow, arm, broker, or live claim"
        ),
        "validity": {
            "selection": "bucket selected on chronological train only; holdout is untouched unless train passes",
            "signal": "all option-entry regime/IV features come from a prior completed market date; entry_signal_lag_bars=1",
            "buckets": {"open": "09:30-10:59 ET", "midday": "11:00-13:59 ET", "late": "14:00-15:59 ET"},
            "cost_axes": COST_AXES,
            "population_pure": "only requested PCS/CCS/IC rows; no registry mutation",
            "ranking_complete": len(errors) == 0 and len(rows) == len(symbols) * len(structures),
            "source_limit": "yfinance 60d intraday retention; proxy options cannot earn L1",
        },
        "gates": {
            "min_trades_each_train_and_holdout_axis": MIN_TRADES,
            "max_loss_usd": MAX_LOSS_USD,
            "max_dd_usd": MAX_DD_USD,
            "window_market_dates": WINDOW_MARKET_DATES,
            "max_dense_negative_windows": MAX_DENSE_NEGATIVE_WINDOWS,
            "all_train_holdout_cost_axes_required": True,
        },
        "n_symbols": len(symbols),
        "n_structures": len(structures),
        "n_completed": len(rows),
        "n_train_gate_pass": sum(bool(row["train_gate_pass"]) for row in rows),
        "n_all_axes_pass": len(passes),
        "errors": errors,
        "pass_rows": passes,
        "rows": rows,
        "decision": (
            "SESSION_TIME_PROXY_PASS_REQUIRES_OBSERVED_VALIDATION"
            if passes
            else "REJECT_SESSION_TIME_PROXY_THIS_CYCLE"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--structures", nargs="+", default=list(STRUCTURES))
    parser.add_argument("--stamp", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = run_lab(
        [str(symbol).upper() for symbol in args.symbols],
        [str(structure).lower() for structure in args.structures],
        args.stamp,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: payload[key]
                for key in (
                    "decision",
                    "n_completed",
                    "n_train_gate_pass",
                    "n_all_axes_pass",
                    "errors",
                )
            },
            indent=2,
        )
    )
    return 0 if not payload["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

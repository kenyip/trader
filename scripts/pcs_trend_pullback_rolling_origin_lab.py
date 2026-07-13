#!/usr/bin/env python3
"""Rolling-origin falsification of one predeclared multi-horizon trend-pullback PCS DNA."""
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
from scripts.pcs_momentum_walkforward_lab import COST_AXES  # noqa: E402
from scripts.pcs_pullback_rolling_origin_lab import (  # noqa: E402
    MAX_DD,
    MAX_DENSE_NEG,
    MAX_LOSS,
    MIN_TRADES,
    _fold_boundaries,
    _fold_pass,
    _holdout_windows,
    _run_pass,
    run_cost_axes,
)


def trend_pullback_config() -> dict[str, Any]:
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
        "entry_ret_5d_max": 0.0,
        "entry_ret_14d_min": 0.03,
        "entry_ema_stack_min": 1.0 / 3.0,
    }


def bearish_mirror_control(config: dict[str, Any]) -> dict[str, Any]:
    control = {
        key: value
        for key, value in config.items()
        if key not in {"entry_ret_5d_max", "entry_ret_14d_min", "entry_ema_stack_min"}
    }
    control.update(
        {
            "entry_ret_5d_min": 0.0,
            "entry_ret_14d_max": -float(config["entry_ret_14d_min"]),
            "entry_ema_stack_max": -float(config["entry_ema_stack_min"]),
        }
    )
    return control


def unconditional_control(config: dict[str, Any]) -> dict[str, Any]:
    control = {key: value for key, value in config.items() if not key.startswith("entry_")}
    control["entry_signal_lag_bars"] = 1
    return control


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="BAC,F,SOFI,PLTR,TSLL,SMCI,AMD,AAPL")
    parser.add_argument("--period", default="5y")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    config = trend_pullback_config()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for symbol in symbols:
        try:
            frame = build(symbol, period=args.period, use_cache=True)
            folds = []
            for fold_index, (_, split, end) in enumerate(_fold_boundaries(len(frame))):
                train = frame.iloc[:split]
                holdout = frame.iloc[split:end]
                train_axes = run_cost_axes(symbol, train, config, f"fold_{fold_index}_train")
                holdout_axes = run_cost_axes(symbol, holdout, config, f"fold_{fold_index}_holdout")
                windows = _holdout_windows(symbol, holdout, config)
                passed = _fold_pass(train_axes, holdout_axes, windows)
                folds.append(
                    {
                        "fold": fold_index,
                        "train_start": str(train.index[0].date()),
                        "train_end": str(train.index[-1].date()),
                        "holdout_start": str(holdout.index[0].date()),
                        "holdout_end": str(holdout.index[-1].date()),
                        "train_bars": len(train),
                        "holdout_bars": len(holdout),
                        "train": train_axes,
                        "train_gate_pass": all(_run_pass(train_axes[axis]) for axis in COST_AXES),
                        "holdout": holdout_axes,
                        "holdout_windows": windows,
                        "fold_gate_pass": passed,
                        "controls": {
                            "unconditional_pcs": run_cost_axes(
                                symbol,
                                holdout,
                                unconditional_control(config),
                                f"fold_{fold_index}_unconditional_pcs",
                            ),
                            "bearish_mirror_pcs": run_cost_axes(
                                symbol,
                                holdout,
                                bearish_mirror_control(config),
                                f"fold_{fold_index}_bearish_mirror_pcs",
                            ),
                        },
                    }
                )
                print(
                    f"{symbol} fold={fold_index} train_gate={folds[-1]['train_gate_pass']} "
                    f"fold_pass={passed}",
                    file=sys.stderr,
                )
            rows.append(
                {
                    "symbol": symbol,
                    "bars": len(frame),
                    "n_folds": len(folds),
                    "n_fold_pass": sum(row["fold_gate_pass"] for row in folds),
                    "all_folds_pass": all(row["fold_gate_pass"] for row in folds),
                    "folds": folds,
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"symbol": symbol, "error": str(exc)})

    passes = [row for row in rows if row["all_folds_pass"]]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD",
        "paper_only": True,
        "sleeve_usd": 3000,
        "structure": "put_credit_spread",
        "capital_fit_usd": "per fold/axis; required <=3000",
        "max_loss_usd": "per fold/axis; required <=300",
        "max_lots": "per fold/axis; default posture 1 lot",
        "hypothesis": "a prior completed bar with a non-positive 5-day return inside a >=3% 14-day return and bullish EMA stack improves 21-DTE defined-risk PCS income after both proxy cost axes",
        "falsifier": "no symbol passes every expanding rolling-origin fold with train gate first, untouched holdout positive SHIP on both proxy cost axes, max loss <=300, holdout and chunk DD <=75, dense negatives <=5, and exact integrity",
        "claim_scope": "historical underlying bars with listed-Friday/rounded-strike daily-bar Black-Scholes option marks; discovery/falsification only, cannot earn L1",
        "validity": {
            "selection": "one predeclared DNA; no grid and no holdout-driven selection",
            "rolling_origin": "expanding train endpoints 40/60/80%; following non-overlapping 20% holdouts",
            "train_gate": "required independently before each fold can pass; holdouts persisted only for falsification diagnostics",
            "signal": "ret_5d, ret_14d, and ema_stack are read from the prior completed bar; missing/nonfinite values fail closed and entry purity is independently checked",
            "cost_axes": ["5pct adverse leg slip", "$0.01 half-spread per leg at entry and exit"],
            "negative_controls": ["same-DTE unconditional PCS", "same-DTE bearish multi-horizon mirror PCS"],
            "population": symbols,
            "population_pure": "put_credit_spread only",
            "ranking_complete": len(errors) == 0 and len(rows) == len(symbols),
        },
        "gates": {
            "min_trades_each_train_and_holdout_cost_axis": MIN_TRADES,
            "positive_ship_each_cost_axis": True,
            "max_loss_usd": MAX_LOSS,
            "max_dd_usd": MAX_DD,
            "dense_negative_windows_each_cost_axis": MAX_DENSE_NEG,
            "integrity": True,
            "all_folds_required": True,
        },
        "config": {
            "dte": 21,
            "ret_5d_max": 0.0,
            "ret_14d_min": 0.03,
            "ema_stack_min": round(1.0 / 3.0, 6),
        },
        "n_symbols": len(symbols),
        "n_completed": len(rows),
        "n_all_folds_pass": len(passes),
        "errors": errors,
        "decision": (
            "DISCOVERY_PASS_REQUIRES_OBSERVED_VALIDATION"
            if passes
            else "REJECT_MULTI_HORIZON_TREND_PULLBACK_PCS"
        ),
        "pass_rows": passes,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: payload[key] for key in ("decision", "n_completed", "n_all_folds_pass", "errors")},
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

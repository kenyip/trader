"""Shared proxy evaluation spine: StrategySpec → dual-cost train/holdout report.

Research/L0 only. Black-Scholes proxy marks. No L1, paper, or live authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

from trader_platform.research.pcs_sim import run_pcs_backtest
from trader_platform.research.regime_router_sim import run_regime_router_backtest
from trader_platform.research.strategy_spec import (
    DEFAULT_COST_AXES,
    StrategySpec,
    strategy_spec_from_mapping,
)

try:
    from data import build as build_market_frame
except Exception:  # pragma: no cover - import surface varies by cwd
    build_market_frame = None  # type: ignore[assignment]


@dataclass
class AxisSummary:
    ok: bool
    n_trades: int
    pnl: float
    dd: float
    max_loss_usd: float
    integrity: bool
    profit_factor: float | None = None
    exit_reasons: dict[str, int] = field(default_factory=dict)
    route_counts: dict[str, int] = field(default_factory=dict)
    stand_aside_count: int = 0
    route_event_count: int = 0
    stand_aside_frac: float = 0.0
    population_pure: bool | None = None
    routing_violations: int = 0
    gate_pnl: float = 0.0
    gate_dd: float = 0.0
    gate_max_loss_usd: float = 0.0
    # Experimental score only (TRADER_BUILD §6) — never a silent hard gate
    premium_per_day_mean: float | None = None
    premium_per_day_median: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def premium_per_day_stats(trades: list[Any]) -> dict[str, float | None]:
    """Per-trade credit capture efficiency: (entry_credit - exit_debit) / days_held.

    Score dimension only — not used by discovery_pass_axes.
    """
    rates: list[float] = []
    for trade in trades:
        credit = getattr(trade, "net_credit", None)
        debit = getattr(trade, "exit_debit", None)
        entry = getattr(trade, "entry_date", None)
        exit_ = getattr(trade, "exit_date", None)
        if credit is None or debit is None or entry is None or exit_ is None:
            continue
        try:
            days = max(int((pd.Timestamp(exit_) - pd.Timestamp(entry)).days), 1)
            rates.append((float(credit) - float(debit)) / float(days))
        except Exception:
            continue
    if not rates:
        return {"premium_per_day_mean": None, "premium_per_day_median": None}
    arr = np.asarray(rates, dtype=float)
    return {
        "premium_per_day_mean": round(float(np.mean(arr)), 6),
        "premium_per_day_median": round(float(np.median(arr)), 6),
    }


def stand_aside_purity(route_counts: Mapping[str, Any]) -> dict[str, float | int]:
    """Stand-aside is success: fraction of route decisions that did not open risk."""
    counts = {str(k): int(v) for k, v in dict(route_counts or {}).items()}
    stand_aside = int(counts.get("stand_aside") or 0)
    total = int(sum(counts.values()))
    frac = float(stand_aside / total) if total > 0 else 0.0
    return {
        "stand_aside_count": stand_aside,
        "route_event_count": total,
        "stand_aside_frac": round(frac, 4),
    }


def _management_exits(metrics: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(reason): int(count)
        for reason, count in dict(metrics.get("exit_reasons") or {}).items()
    }


def summarize_sim_result(result: Any, frame: pd.DataFrame) -> AxisSummary:
    """Ledger-integrity summary shared by pcs_sim and regime_router results."""
    metrics = dict(getattr(result, "metrics", None) or {})
    trades = list(getattr(result, "trades", None) or [])
    skipped = bool(getattr(result, "skipped", False))
    ok = bool(getattr(result, "ok", False) and not skipped)
    n = int(getattr(result, "n_trades", None) or metrics.get("n_trades") or len(trades) or 0)
    pnl = float(metrics.get("total_pnl_per_contract") or 0.0)
    dd = float(metrics.get("max_dd_per_contract") or 0.0)
    pf_raw = metrics.get("profit_factor")
    try:
        pf = float(pf_raw) if pf_raw is not None and np.isfinite(float(pf_raw)) else None
    except (TypeError, ValueError):
        pf = None

    ledger = np.array(
        [
            (float(trade.net_credit) - float(trade.exit_debit or 0.0)) * 100.0
            for trade in trades
        ],
        dtype=float,
    )
    equity = np.cumsum(ledger) if len(ledger) else np.array([], dtype=float)
    peaks = np.maximum.accumulate(equity) if len(equity) else np.array([], dtype=float)
    ledger_dd = float(np.max(peaks - equity)) if len(equity) else 0.0
    same_bar = sum(
        previous.exit_date is not None and previous.exit_date == following.entry_date
        for previous, following in zip(trades, trades[1:])
    )
    max_loss = max(
        (float(trade.max_loss_per_share) * 100.0 for trade in trades),
        default=0.0,
    )
    # Iron condors can have higher width accounting; still use per-trade max_loss_per_share.
    integrity = (
        ok
        and abs(float(ledger.sum()) - pnl) < 1e-6
        and abs(ledger_dd - dd) < 1e-6
        and same_bar == 0
        and n == len(trades)
    )
    route_counts = dict(getattr(result, "route_counts", None) or {})
    purity = stand_aside_purity(route_counts)
    population_pure_raw = metrics.get("population_pure")
    ppd = premium_per_day_stats(trades)
    return AxisSummary(
        ok=ok,
        n_trades=n,
        pnl=round(pnl, 2),
        dd=round(dd, 2),
        max_loss_usd=round(max_loss, 2),
        integrity=integrity,
        profit_factor=round(pf, 4) if pf is not None else None,
        exit_reasons=_management_exits(metrics),
        route_counts=route_counts,
        stand_aside_count=int(purity["stand_aside_count"]),
        route_event_count=int(purity["route_event_count"]),
        stand_aside_frac=float(purity["stand_aside_frac"]),
        population_pure=(
            bool(population_pure_raw) if population_pure_raw is not None else None
        ),
        routing_violations=int(metrics.get("routing_violations") or 0),
        gate_pnl=pnl,
        gate_dd=dd,
        gate_max_loss_usd=max_loss,
        premium_per_day_mean=ppd["premium_per_day_mean"],
        premium_per_day_median=ppd["premium_per_day_median"],
    )


def _run_one(
    spec: StrategySpec,
    *,
    symbol: str,
    frame: pd.DataFrame,
    cost: Mapping[str, float],
    label: str,
    control: bool = False,
) -> AxisSummary:
    if spec.evaluation_mode == "single_structure":
        cfg = {**spec.single_config(), **dict(cost)}
        if control:
            # Unconditional: strip entry_* keys only.
            cfg = {
                key: value
                for key, value in cfg.items()
                if not str(key).startswith("entry_")
            }
        result = run_pcs_backtest(
            symbol,
            period=label,
            df=frame,
            min_bars=15,
            config=cfg,
            structure=str(spec.structure),
            sleeve_usd=spec.sleeve_usd,
            open_risk_budget_usd=spec.open_risk_budget_usd,
        )
        return summarize_sim_result(result, frame)

    # regime_router (full multi-structure or PCS-only policies)
    configs = spec.router_configs()
    for structure, cfg in configs.items():
        merged = {**cfg, **dict(cost)}
        if control:
            merged = {
                key: value
                for key, value in merged.items()
                if not str(key).startswith("entry_")
            }
        configs[structure] = merged
    # Control: unconditional PCS every eligible bar (no regime stand-aside advantage).
    policy = (
        "put_credit_spread"
        if control
        else str(getattr(spec, "router_policy", None) or "router").strip().lower()
    )
    result = run_regime_router_backtest(
        symbol,
        df=frame,
        policy=policy,
        period=label,
        configs=configs,
        sleeve_usd=spec.sleeve_usd,
        open_risk_budget_usd=spec.open_risk_budget_usd,
        min_bars=15,
    )
    return summarize_sim_result(result, frame)


def _run_cost_axes(
    spec: StrategySpec,
    *,
    symbol: str,
    frame: pd.DataFrame,
    label: str,
    control: bool = False,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for axis, cost in DEFAULT_COST_AXES.items():
        summary = _run_one(
            spec,
            symbol=symbol,
            frame=frame,
            cost=cost,
            label=f"{label}_{axis}",
            control=control,
        )
        out[axis] = summary.to_dict()
    return out


def discovery_pass_axes(
    axes: Mapping[str, Mapping[str, Any]],
    gates: Any,
    *,
    control_axes: Mapping[str, Mapping[str, Any]] | None = None,
) -> bool:
    for axis in DEFAULT_COST_AXES:
        row = axes.get(axis) or {}
        if not row.get("ok", False):
            return False
        if int(row.get("n_trades") or 0) < int(gates.min_trades):
            return False
        if gates.require_positive_pnl and float(row.get("gate_pnl", row.get("pnl") or 0.0)) <= 0.0:
            return False
        if float(row.get("gate_max_loss_usd", row.get("max_loss_usd") or 0.0)) > float(
            gates.max_loss_usd
        ):
            return False
        if float(row.get("gate_dd", row.get("dd") or 0.0)) > float(gates.max_dd_discovery_usd):
            return False
        if gates.require_integrity and not bool(row.get("integrity", False)):
            return False
        if control_axes is not None:
            control = control_axes.get(axis) or {}
            if not control.get("ok", False):
                return False
            if int(control.get("n_trades") or 0) < int(gates.min_trades):
                return False
            if gates.require_integrity and not bool(control.get("integrity", False)):
                return False
    if control_axes is not None and gates.require_control_beat:
        cand_worst = min(
            float(axes[a].get("gate_pnl", axes[a].get("pnl") or 0.0)) for a in DEFAULT_COST_AXES
        )
        ctrl_worst = min(
            float(control_axes[a].get("gate_pnl", control_axes[a].get("pnl") or 0.0))
            for a in DEFAULT_COST_AXES
        )
        if cand_worst <= ctrl_worst:
            return False
    return True


def _load_frame(symbol: str, period: str) -> pd.DataFrame:
    if build_market_frame is None:
        raise RuntimeError("data.build unavailable; run from repo root with package path set")
    return build_market_frame(symbol, period=period, use_cache=True)


def evaluate_proxy(
    spec: StrategySpec | Mapping[str, Any],
    *,
    symbols: Optional[list[str]] = None,
    period: Optional[str] = None,
    train_fraction: Optional[float] = None,
    run_holdout_on_train_pass: bool = True,
) -> dict[str, Any]:
    """Evaluate a frozen StrategySpec on proxy marks with dual-cost train/holdout."""
    if not isinstance(spec, StrategySpec):
        spec = strategy_spec_from_mapping(spec)
    spec.validate()

    use_symbols = [s.upper() for s in (symbols or list(spec.symbols))]
    use_period = period or spec.period
    use_fraction = float(train_fraction if train_fraction is not None else spec.train_fraction)
    if not 0.50 <= use_fraction <= 0.80:
        raise ValueError("train_fraction must be in [0.50, 0.80]")
    if len(use_symbols) < 1:
        raise ValueError("at least one symbol required")

    want_control = spec.control_mode == "unconditional_same_management"
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for symbol in use_symbols:
        try:
            frame = _load_frame(symbol, use_period)
            split = int(len(frame) * use_fraction)
            train = frame.iloc[:split].copy()
            holdout = frame.iloc[split:].copy()
            if len(train) < 15 or len(holdout) < 15 or not train.index[-1] < holdout.index[0]:
                raise ValueError("invalid chronological train/holdout partition")

            train_axes = _run_cost_axes(
                spec, symbol=symbol, frame=train, label="train", control=False
            )
            control_axes = (
                _run_cost_axes(spec, symbol=symbol, frame=train, label="control", control=True)
                if want_control
                else None
            )
            train_pass = discovery_pass_axes(
                train_axes,
                spec.discovery_gates,
                control_axes=control_axes if want_control else None,
            )
            max_loss = max(
                float(train_axes[a].get("gate_max_loss_usd", train_axes[a].get("max_loss_usd") or 0.0))
                for a in DEFAULT_COST_AXES
            )
            rows.append(
                {
                    "symbol": symbol,
                    "train_start": str(train.index[0].date()),
                    "train_end": str(train.index[-1].date()),
                    "holdout_start": str(holdout.index[0].date()),
                    "holdout_end": str(holdout.index[-1].date()),
                    "chronology_ok": True,
                    "train": train_axes,
                    "control_train": control_axes,
                    "train_discovery_pass": train_pass,
                    "max_loss_usd": max_loss,
                    "funnel_stage_after_train": "F1_TRAIN" if train_pass else "F0_MECHANISM",
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"symbol": symbol, "error": str(exc)})

    train_survivors = [row for row in rows if row.get("train_discovery_pass")]
    holdout_rows: list[dict[str, Any]] = []
    if run_holdout_on_train_pass and train_survivors:
        for row in train_survivors:
            symbol = row["symbol"]
            try:
                frame = _load_frame(symbol, use_period)
                split = int(len(frame) * use_fraction)
                hold = frame.iloc[split:].copy()
                hold_axes = _run_cost_axes(
                    spec, symbol=symbol, frame=hold, label="holdout", control=False
                )
                hold_pass = discovery_pass_axes(hold_axes, spec.discovery_gates, control_axes=None)
                holdout_rows.append(
                    {
                        "symbol": symbol,
                        "holdout_start": row["holdout_start"],
                        "holdout_end": row["holdout_end"],
                        "holdout": hold_axes,
                        "holdout_dual_cost_pass": hold_pass,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                errors.append({"symbol": symbol, "error": f"holdout: {exc}"})

    any_holdout = any(r.get("holdout_dual_cost_pass") for r in holdout_rows)
    train_advanced = len(train_survivors) > 0
    if any_holdout:
        decision = "STRATEGY_ADVANCED_F2"
        funnel = "F2_UNTOUCHED_HOLDOUT"
    elif train_advanced:
        decision = "STRATEGY_ADVANCED_F1_HOLDOUT_FAILED"
        funnel = "F1_TRAIN"
    else:
        decision = "FAMILY_CLOSED"
        funnel = "F0_MECHANISM"

    living = [
        {
            "candidate_id": f"{spec.candidate_id}_{r['symbol']}",
            "symbol": r["symbol"],
            "funnel_stage": "F2_UNTOUCHED_HOLDOUT",
            "option_mark_provenance": spec.option_mark_provenance,
        }
        for r in holdout_rows
        if r.get("holdout_dual_cost_pass")
    ]

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spine": "trader_proxy_evaluate_v1",
        "phase": "BUILD_L0_PROXY",
        "paper_only": True,
        "trading_authority": False,
        "capital_seat_claim": False,
        "l1_eligible": False,
        "candidate_id": spec.candidate_id,
        "family_id": spec.family_id,
        "evaluation_mode": spec.evaluation_mode,
        "router_policy": getattr(spec, "router_policy", "router"),
        "forecast_type": spec.forecast_type,
        "economic_mechanism": spec.economic_mechanism,
        "stand_aside_rule": spec.stand_aside_rule,
        "regime_envelope": spec.regime_envelope,
        "option_mark_provenance": spec.option_mark_provenance,
        "spec": spec.to_dict(),
        "cost_axes": list(DEFAULT_COST_AXES.keys()),
        "period": use_period,
        "train_fraction": use_fraction,
        "symbols": use_symbols,
        "n_symbols": len(use_symbols),
        "n_completed": len(rows),
        "n_train_pass": len(train_survivors),
        "n_holdout_pass": sum(1 for r in holdout_rows if r.get("holdout_dual_cost_pass")),
        "strategy_advanced_train": train_advanced,
        "strategy_advanced_holdout": any_holdout,
        "funnel_stage_after": funnel,
        "decision": decision,
        "living_candidates": living,
        "train_rows": rows,
        "holdout_rows": holdout_rows,
        "errors": errors,
        "ranking_complete": len(errors) == 0 and len(rows) == len(use_symbols),
    }


def write_living_scoreboard(report: Mapping[str, Any], path: str | Path) -> dict[str, Any]:
    """Write spine living-candidate scoreboard (F2+ only)."""
    living = list(report.get("living_candidates") or [])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_candidate_id": report.get("candidate_id"),
        "source_decision": report.get("decision"),
        "living_count": len(living),
        "living_candidates": living,
        "note": "Only F2 dual-cost holdout survivors are living. Proxy cannot earn L1.",
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        __import__("json").dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload

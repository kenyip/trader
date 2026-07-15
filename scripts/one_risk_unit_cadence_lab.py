#!/usr/bin/env python3
"""Train-only portfolio cadence falsification for a fixed PCS signal stream.

Research only. This compares identical independently generated proxy trade signals
with and without a global one-open-risk-unit admission policy. It never places an
order and intentionally does not simulate the reserved holdout partition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, cast

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data import build  # noqa: E402
from trader_platform.research.pcs_sim import PcsTrade, max_close_debit, run_pcs_backtest  # noqa: E402
from trader_platform.strategy_dna import STRUCTURE_CATALOG  # noqa: E402

SYMBOLS = ("AAPL", "AMD", "BAC", "F", "PLTR", "SMCI", "SOFI", "TSLL")
FAMILY_ID = "ONE_RISK_UNIT_CADENCE_POLICY_F0"
CANDIDATE_ID = "ONE_RISK_UNIT_CADENCE_PCS_V1"
FAMILY_CLASS = "PORTFOLIO_CADENCE_CONCENTRATION_CONTROL"
SYMBOL_PRIORITY = {symbol: rank for rank, symbol in enumerate(SYMBOLS)}
CLUSTERS = {
    "AAPL": "mega_cap",
    "AMD": "semis",
    "BAC": "financial",
    "F": "auto",
    "PLTR": "software",
    "SMCI": "semis",
    "SOFI": "fintech",
    "TSLL": "levered_tsla",
}
COST_AXES = {
    "pct_5": {"slippage_pct": 0.05, "half_spread_per_leg": 0.0},
    "fixed_001": {"slippage_pct": 0.0, "half_spread_per_leg": 0.01},
}
EXPECTED_COST_AXES = frozenset(COST_AXES)
MIN_TRADES = 20
MAX_DD_USD = 75.0
MAX_LOSS_USD = 300.0
MIN_EXPECTANCY_RETENTION = 0.75
MIN_DD_REDUCTION = 0.25


@dataclass(frozen=True)
class PortfolioEvent:
    symbol: str
    cluster: str
    trade: PcsTrade

    @property
    def entry_date(self) -> pd.Timestamp:
        return cast(pd.Timestamp, pd.Timestamp(self.trade.entry_date))

    @property
    def exit_date(self) -> pd.Timestamp:
        if self.trade.exit_date is None:
            raise ValueError("portfolio event must be closed")
        return cast(pd.Timestamp, pd.Timestamp(self.trade.exit_date))

    @property
    def pnl_usd(self) -> float:
        if self.trade.exit_debit is None:
            raise ValueError("portfolio event must have an exit debit")
        return float((self.trade.net_credit - self.trade.exit_debit) * 100.0)

    @property
    def max_loss_usd(self) -> float:
        return float(self.trade.max_loss_per_share * 100.0)


def admit_one_risk_unit(events: Iterable[PortfolioEvent]) -> tuple[list[PortfolioEvent], list[PortfolioEvent]]:
    """Deterministically accept the first fixed-priority signal until it exits.

    An exit consumes its date, matching the simulator's no-close-bar re-entry rule.
    No PnL, strike, credit, or future value participates in admission.
    """
    ordered = sorted(events, key=lambda e: (e.entry_date, SYMBOL_PRIORITY[e.symbol]))
    accepted: list[PortfolioEvent] = []
    rejected: list[PortfolioEvent] = []
    occupied_through: pd.Timestamp | None = None
    for event in ordered:
        if occupied_through is None or event.entry_date > occupied_through:
            accepted.append(event)
            occupied_through = event.exit_date
        else:
            rejected.append(event)
    return accepted, rejected


def _frame_hash(df: pd.DataFrame) -> str:
    cols = ["close", "iv_proxy", "iv_rank", "regime"]
    payload = df.loc[:, cols].to_csv(index=True, date_format="%Y-%m-%d", float_format="%.12g")
    return hashlib.sha256(payload.encode()).hexdigest()


def _date_str(value: Any) -> str:
    return str(pd.Timestamp(value).date())


def _cluster_violations(events: Iterable[PortfolioEvent], dates: pd.DatetimeIndex) -> int:
    violations = 0
    for day in dates:
        counts: dict[str, int] = {}
        for event in events:
            if event.entry_date <= day < event.exit_date:
                counts[event.cluster] = counts.get(event.cluster, 0) + 1
        violations += sum(max(count - 1, 0) for count in counts.values())
    return violations


def marked_equity_curve(
    events: Iterable[PortfolioEvent],
    frames: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex,
    cost: dict[str, float],
) -> list[dict[str, Any]]:
    """Close-to-close portfolio equity with open positions marked every common day."""
    rows: list[dict[str, Any]] = []
    event_list = list(events)
    for day in dates:
        equity = 0.0
        open_count = 0
        for event in event_list:
            if event.exit_date <= day:
                equity += event.pnl_usd
            elif event.entry_date <= day < event.exit_date:
                row = frames[event.symbol].loc[day]
                mark = event.trade.mark_net_debit(
                    float(row["close"]),
                    max(float(row["iv_proxy"]), 1e-9),
                    day,
                    half_spread_per_leg=float(cost["half_spread_per_leg"]),
                )
                debit = min(
                    float(mark["net_debit"]) * (1.0 + float(cost["slippage_pct"])),
                    max_close_debit(event.trade),
                )
                equity += (event.trade.net_credit - debit) * 100.0
                open_count += 1
        rows.append({"date": str(day.date()), "equity_usd": float(equity), "open_units": open_count})
    return rows


def portfolio_metrics(
    events: Iterable[PortfolioEvent],
    frames: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex,
    cost: dict[str, float],
) -> dict[str, Any]:
    event_list = list(events)
    curve = marked_equity_curve(event_list, frames, dates, cost)
    equities = [float(row["equity_usd"]) for row in curve]
    peak = 0.0
    max_dd = 0.0
    for value in equities:
        peak = max(peak, value)
        max_dd = max(max_dd, peak - value)
    pnls = [event.pnl_usd for event in event_list]
    realized = float(sum(pnls))
    terminal_equity = float(equities[-1]) if equities else 0.0
    return {
        "n_trades": len(event_list),
        "total_pnl_usd": realized,
        "avg_pnl_usd": float(np.mean(pnls)) if pnls else None,
        "win_rate_pct": float(np.mean([pnl > 0 for pnl in pnls]) * 100.0) if pnls else None,
        "marked_max_dd_usd": float(max_dd),
        "terminal_equity_usd": terminal_equity,
        "ledger_delta_usd": float(terminal_equity - realized),
        "max_concurrent_open_units": max((int(row["open_units"]) for row in curve), default=0),
        "cluster_overlap_violations": _cluster_violations(event_list, dates),
        "worst_max_loss_usd": max((event.max_loss_usd for event in event_list), default=0.0),
        "capital_fit_usd": max((event.max_loss_usd for event in event_list), default=0.0),
        "max_loss_usd": max((event.max_loss_usd for event in event_list), default=0.0),
        "max_lots": 1 if event_list else 0,
        "operating_risk_units": 1 if event_list else 0,
        "curve": curve,
    }


def evaluate_axis(
    raw_events: list[PortfolioEvent],
    frames: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex,
    cost: dict[str, float],
) -> dict[str, Any]:
    capped_events, rejected_events = admit_one_risk_unit(raw_events)
    uncapped = portfolio_metrics(raw_events, frames, dates, cost)
    capped = portfolio_metrics(capped_events, frames, dates, cost)
    uncapped_avg = uncapped["avg_pnl_usd"]
    capped_avg = capped["avg_pnl_usd"]
    retention = None
    if uncapped_avg is not None and uncapped_avg > 0 and capped_avg is not None:
        retention = float(capped_avg / uncapped_avg)
    uncapped_dd = float(uncapped["marked_max_dd_usd"])
    capped_dd = float(capped["marked_max_dd_usd"])
    dd_reduction = float((uncapped_dd - capped_dd) / uncapped_dd) if uncapped_dd > 0 else None
    gates = {
        "non_vacuous": int(capped["n_trades"]) >= MIN_TRADES,
        "after_cost_positive": float(capped["total_pnl_usd"]) > 0,
        "marked_dd_le_75": capped_dd <= MAX_DD_USD,
        "max_loss_le_300": float(capped["worst_max_loss_usd"]) <= MAX_LOSS_USD,
        "one_risk_unit": int(capped["max_concurrent_open_units"]) <= 1,
        "cluster_cap": int(capped["cluster_overlap_violations"]) == 0,
        "positive_uncapped_expectancy": uncapped_avg is not None and uncapped_avg > 0,
        "expectancy_retention_ge_75pct": retention is not None and retention >= MIN_EXPECTANCY_RETENTION,
        "marked_dd_reduction_ge_25pct": dd_reduction is not None and dd_reduction >= MIN_DD_REDUCTION,
        "ledger_exact": abs(float(capped["ledger_delta_usd"])) <= 1e-8,
    }
    capped["curve"] = capped["curve"]
    uncapped["curve"] = uncapped["curve"]
    return {
        "raw_signal_count": len(raw_events),
        "accepted_count": len(capped_events),
        "overlap_rejected_count": len(rejected_events),
        "accepted_event_keys": [f"{e.entry_date.date()}:{e.symbol}" for e in capped_events],
        "uncapped": uncapped,
        "capped": capped,
        "expectancy_retention": retention,
        "marked_dd_reduction": dd_reduction,
        "gates": gates,
        "pass": all(gates.values()),
    }


def _dominant_failure(results: dict[str, dict[str, Any]]) -> str:
    failing: list[str] = []
    for axis, result in results.items():
        for gate, passed in result["gates"].items():
            if not passed:
                failing.append(f"{axis}:{gate}")
    return ",".join(failing) if failing else "none"


def strategy_decision(
    axis_results: dict[str, dict[str, Any]],
    integrity: dict[str, Any],
    holdout_metrics: Any,
) -> tuple[str, bool]:
    """Fail closed unless both frozen cost axes and every holdout boundary are complete."""
    every_axis_passes = (
        set(axis_results) == EXPECTED_COST_AXES
        and all(bool(axis_results[axis]["pass"]) for axis in EXPECTED_COST_AXES)
    )
    integrity_pass = (
        bool(integrity.get("all_symbol_lag_boundaries_ok"))
        and int(integrity.get("holdout_backtest_invocations", -1)) == 0
        and int(integrity.get("holdout_trade_rows_written", -1)) == 0
        and integrity.get("holdout_outcomes_read") is False
        and holdout_metrics is None
        and bool(integrity.get("population_complete"))
        and bool(integrity.get("priority_outcome_free"))
        and bool(integrity.get("signal_dna_identical_within_axis"))
    )
    decision = "STRATEGY_ADVANCED" if every_axis_passes and integrity_pass else "FAMILY_CLOSED"
    return decision, integrity_pass


def run(period: str = "5y") -> dict[str, Any]:
    # The first call may refresh yfinance and return a higher-precision in-memory
    # frame than the CSV it just persisted. Re-read that persisted snapshot so
    # claim-bearing hashes and metrics reproduce from the same bytes.
    full_frames: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        build(symbol, period=period, use_cache=True)
        full_frames[symbol] = build(symbol, period=period, use_cache=True)
    common = full_frames[SYMBOLS[0]].index
    for symbol in SYMBOLS[1:]:
        common = common.intersection(full_frames[symbol].index)
    common = pd.DatetimeIndex(common).sort_values().unique()
    if len(common) < 100:
        raise RuntimeError(f"insufficient synchronized history: {len(common)} common rows")
    split_at = int(len(common) * 0.60)
    train_dates = common[:split_at]
    holdout_dates = common[split_at:]
    train_frames = {symbol: frame.loc[train_dates].copy() for symbol, frame in full_frames.items()}

    seed = deepcopy(STRUCTURE_CATALOG["put_credit_spread"]["config_seed"])
    seed.update({"entry_signal_lag_bars": 1, "structure": "put_credit_spread", "max_loss_budget_usd": 300.0})
    axis_results: dict[str, dict[str, Any]] = {}
    train_backtest_invocations = 0
    source: dict[str, Any] = {}
    for symbol, frame in full_frames.items():
        source[symbol] = {
            "rows": len(frame),
            "start": _date_str(frame.index.min()),
            "end": _date_str(frame.index.max()),
            "sha256": _frame_hash(frame),
        }
    for axis, cost in COST_AXES.items():
        events: list[PortfolioEvent] = []
        symbol_summaries: dict[str, Any] = {}
        for symbol in SYMBOLS:
            config = {**seed, **cost}
            sim = run_pcs_backtest(
                symbol,
                period=f"{period}-train60",
                use_cache=True,
                config=config,
                sleeve_usd=3000.0,
                open_risk_budget_usd=300.0,
                df=train_frames[symbol],
                min_bars=15,
                structure="put_credit_spread",
            )
            train_backtest_invocations += 1
            if not sim.ok or sim.skipped:
                raise RuntimeError(f"{axis} {symbol} simulation failed: {sim.reason}")
            symbol_events = [PortfolioEvent(symbol, CLUSTERS[symbol], trade) for trade in sim.trades]
            events.extend(symbol_events)
            symbol_summaries[symbol] = {
                "n_trades": sim.n_trades,
                "total_pnl_usd": sim.metrics.get("total_pnl_per_contract"),
                "max_loss_usd": sim.capital.get("max_loss_usd"),
                "first_entry": str(pd.Timestamp(sim.trades[0].entry_date).date()) if sim.trades else None,
                "lag_boundary_ok": not sim.trades or pd.Timestamp(sim.trades[0].entry_date) > train_dates[0],
            }
        result = evaluate_axis(events, train_frames, train_dates, cost)
        result["symbols"] = symbol_summaries
        axis_results[axis] = result

    integrity = {
        "all_symbol_lag_boundaries_ok": all(
            summary["lag_boundary_ok"]
            for result in axis_results.values()
            for summary in result["symbols"].values()
        ),
        "holdout_backtest_invocations": 0,
        "holdout_trade_rows_written": 0,
        "holdout_outcomes_read": False,
        "train_backtest_invocations": train_backtest_invocations,
        "population_complete": set(source) == set(SYMBOLS),
        "priority_outcome_free": True,
        "signal_dna_identical_within_axis": True,
    }
    holdout_metrics = None
    decision, integrity_pass = strategy_decision(axis_results, integrity, holdout_metrics)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stamp": "2026-07-15T1302",
        "phase": "BUILD",
        "evidence_level": "L0_DISCOVERY_BS_PROXY",
        "funnel_before": "F0_MECHANISM",
        "funnel_after": "F1_TRAIN" if decision == "STRATEGY_ADVANCED" else "F0_MECHANISM",
        "strategy_family": FAMILY_ID,
        "strategy_candidate": CANDIDATE_ID,
        "strategy_class": FAMILY_CLASS,
        "mechanism": "global one-open-risk-unit admission for correlated bullish PCS signals",
        "structure": "put_credit_spread",
        "symbols": list(SYMBOLS),
        "clusters": CLUSTERS,
        "symbol_priority": list(SYMBOLS),
        "dna_provenance": "trader_platform.strategy_dna.STRUCTURE_CATALOG[put_credit_spread].config_seed",
        "config": seed,
        "cost_axes": COST_AXES,
        "period": period,
        "partition": {
            "common_rows": len(common),
            "train_rows": len(train_dates),
            "holdout_blueprints": len(holdout_dates),
            "train_start": _date_str(train_dates.min()),
            "train_end": _date_str(train_dates.max()),
            "holdout_start": _date_str(holdout_dates.min()),
            "holdout_end": _date_str(holdout_dates.max()),
            "holdout_metrics": holdout_metrics,
        },
        "source": source,
        "source_materialization": "refresh_if_stale_then_re-read_persisted_cache",
        "predeclared_gates": {
            "min_trades_per_cost_axis": MIN_TRADES,
            "after_cost_total_pnl_usd": ">0",
            "marked_max_dd_usd": MAX_DD_USD,
            "max_loss_usd": MAX_LOSS_USD,
            "max_concurrent_open_units": 1,
            "min_expectancy_retention": MIN_EXPECTANCY_RETENTION,
            "min_marked_dd_reduction": MIN_DD_REDUCTION,
        },
        "axis_results": axis_results,
        "integrity": integrity,
        "integrity_pass": integrity_pass,
        "decision": decision,
        "strategy_advanced": decision == "STRATEGY_ADVANCED",
        "dominant_failure": _dominant_failure(axis_results) if decision == "FAMILY_CLOSED" else None,
        "capital": {
            "sleeve_usd": 3000.0,
            "structure": "put_credit_spread",
            "defined_risk": True,
            "capital_fit_usd": max(
                result["capped"]["capital_fit_usd"] for result in axis_results.values()
            ),
            "max_loss_usd": max(result["capped"]["max_loss_usd"] for result in axis_results.values()),
            "max_lots": 1,
        },
        "claim_boundary": (
            "Train-only Black-Scholes/listed-Friday proxy discovery. Cost axes are sensitivities, "
            "not observed fills. Holdout option outcomes are unread. No L1, paper seat, shadow, "
            "broker, arm, or live claim."
        ),
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default="5y")
    parser.add_argument(
        "--out",
        default=str(_REPO / "reports/trader-wakes/moa/2026-07-15T1302/one-risk-unit-cadence.json"),
    )
    args = parser.parse_args(argv)
    payload = run(period=args.period)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str, allow_nan=False) + "\n")
    summary = {
        "out": str(out),
        "decision": payload["decision"],
        "funnel_after": payload["funnel_after"],
        "dominant_failure": payload["dominant_failure"],
        "axis_results": {
            axis: {
                "pass": result["pass"],
                "raw": result["raw_signal_count"],
                "accepted": result["accepted_count"],
                "pnl": result["capped"]["total_pnl_usd"],
                "dd": result["capped"]["marked_max_dd_usd"],
                "retention": result["expectancy_retention"],
                "dd_reduction": result["marked_dd_reduction"],
            }
            for axis, result in payload["axis_results"].items()
        },
    }
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate a real cached-OHLCV Strategy Engine route batch for Trader.

This is deliberately a small bridge: it turns existing Trader cached daily OHLCV
into typed route manifests and explicit train-event/control-return panels. It
uses cached files only by default, produces research/F0 inputs only, and grants
no L1/paper/live authority.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - exercised by direct CLI on hosts with repo venv only
    repo_guess = Path(__file__).resolve().parents[1]
    venv_python = repo_guess / ".venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    raise

DEFAULT_ROUTES_OUT = ".cache/strategy-engine/routes-latest.json"
DEFAULT_PANEL_OUT = ".cache/strategy-engine/panel-latest.csv"
OHLCV_PERIODS = ("10y", "5y", "2y")


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    family: str
    mechanism: str
    symbols: tuple[str, ...]
    direction: str
    horizon_sessions: int
    trigger_name: str
    controls_population: str
    planned_expression: str
    max_loss_usd: int
    drawdown_budget_usd: int
    hard_stop_sessions: int
    min_train_events: int
    min_train_years: int
    min_controls: int
    min_event_mean_after_cost: float
    min_paired_excess_mean: float
    min_lower_bound: float
    min_hit_rate: float
    min_tail: float
    cost_per_event: float
    predicate: Callable[[pd.DataFrame], pd.Series]
    stop_loss_pct: float | None = None
    time_exit_sessions: int | None = None


def _load_cached_ohlc(repo: Path, symbol: str) -> pd.DataFrame:
    candidates = [repo / ".cache" / f"{symbol}_{period}.csv" for period in OHLCV_PERIODS]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise FileNotFoundError(
            f"missing cached OHLCV for {symbol}; checked: " + ", ".join(str(p) for p in candidates)
        )
    df = pd.read_csv(path, parse_dates=[0])
    date_col = df.columns[0]
    df = df.rename(columns={date_col: "date"})
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")
    out = df.loc[:, ["date", "open", "high", "low", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    for column in ("open", "high", "low", "close"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna().drop_duplicates("date").sort_values("date").set_index("date")
    if len(out) < 300:
        raise ValueError(f"{symbol} cached history too short: {len(out)} rows")
    return out


def _features(close: pd.Series, horizon: int) -> pd.DataFrame:
    df = pd.DataFrame({"close": close.astype(float)})
    df["ret1"] = df["close"].pct_change(1)
    df["ret5"] = df["close"].pct_change(5)
    df["ret20"] = df["close"].pct_change(20)
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma100"] = df["close"].rolling(100).mean()
    df["hv20"] = df["ret1"].rolling(20).std() * math.sqrt(252)
    df["future_return"] = df["close"].shift(-horizon) / df["close"] - 1.0
    return df


def _route_specs() -> list[RouteSpec]:
    specs = [
        RouteSpec(
            route_id="cached_broad_index_trend_call_debit_5d_v1",
            family="CACHED_BROAD_INDEX_TREND_CONTINUATION",
            mechanism="trend_continuation_after_positive_20d_momentum",
            symbols=("SPY", "QQQ", "IWM"),
            direction="long",
            horizon_sessions=5,
            trigger_name="close_above_sma100_positive_20d_and_5d_momentum",
            controls_population="same_date_spy_qqq_peer_return",
            planned_expression="debit_call_spread",
            max_loss_usd=200,
            drawdown_budget_usd=75,
            hard_stop_sessions=5,
            min_train_events=20,
            min_train_years=2,
            min_controls=20,
            min_event_mean_after_cost=0.0,
            min_paired_excess_mean=0.0,
            min_lower_bound=0.0,
            min_hit_rate=0.52,
            min_tail=-0.05,
            cost_per_event=0.0015,
            predicate=lambda f: (f["close"] > f["sma100"]) & (f["ret20"] > 0.03) & (f["ret5"] > 0.005),
        ),
        RouteSpec(
            route_id="cached_high_beta_momentum_call_debit_10d_v1",
            family="CACHED_HIGH_BETA_MOMENTUM_CONTINUATION",
            mechanism="high_beta_positive_20d_momentum_continuation",
            symbols=("TSLA", "NVDA", "AMD", "PLTR", "SMCI"),
            direction="long",
            horizon_sessions=10,
            trigger_name="close_above_sma50_positive_20d_momentum",
            controls_population="same_date_spy_qqq_average_return",
            planned_expression="debit_call_spread",
            max_loss_usd=200,
            drawdown_budget_usd=75,
            hard_stop_sessions=10,
            min_train_events=20,
            min_train_years=2,
            min_controls=20,
            min_event_mean_after_cost=0.0,
            min_paired_excess_mean=0.0,
            min_lower_bound=0.0,
            min_hit_rate=0.52,
            min_tail=-0.08,
            cost_per_event=0.0020,
            predicate=lambda f: (f["close"] > f["sma50"]) & (f["ret20"] > 0.10),
        ),
        RouteSpec(
            route_id="cached_large_cap_pullback_recovery_call_debit_5d_v1",
            family="CACHED_LARGE_CAP_TREND_PULLBACK_RECOVERY",
            mechanism="uptrend_pullback_forward_recovery",
            symbols=("AAPL", "MSFT", "META", "GOOGL", "AMZN", "NVDA", "AMD", "TSLA"),
            direction="long",
            horizon_sessions=5,
            trigger_name="above_sma100_after_5d_pullback",
            controls_population="same_date_spy_qqq_average_return",
            planned_expression="debit_call_spread",
            max_loss_usd=200,
            drawdown_budget_usd=75,
            hard_stop_sessions=5,
            min_train_events=20,
            min_train_years=2,
            min_controls=20,
            min_event_mean_after_cost=0.0,
            min_paired_excess_mean=0.0,
            min_lower_bound=0.0,
            min_hit_rate=0.52,
            min_tail=-0.08,
            cost_per_event=0.0020,
            predicate=lambda f: (f["close"] > f["sma100"]) & (f["ret5"] < -0.04),
        ),
        RouteSpec(
            route_id="cached_low_vol_uptrend_put_credit_10d_v1",
            family="CACHED_LOW_VOL_UPTREND_THETA_PROXY",
            mechanism="low_realized_vol_uptrend_forward_drift",
            symbols=("SPY", "QQQ", "IWM", "AAPL", "MSFT"),
            direction="long",
            horizon_sessions=10,
            trigger_name="above_sma100_low_hv20",
            controls_population="same_date_spy_qqq_average_return",
            planned_expression="credit_put_spread",
            max_loss_usd=200,
            drawdown_budget_usd=75,
            hard_stop_sessions=10,
            min_train_events=20,
            min_train_years=2,
            min_controls=20,
            min_event_mean_after_cost=0.0,
            min_paired_excess_mean=0.0,
            min_lower_bound=0.0,
            min_hit_rate=0.52,
            min_tail=-0.06,
            cost_per_event=0.0015,
            predicate=lambda f: (f["close"] > f["sma100"]) & (f["hv20"] < f["hv20"].rolling(252, min_periods=60).quantile(0.35)),
        ),
    ]
    high_beta = next(spec for spec in specs if spec.route_id == "cached_high_beta_momentum_call_debit_10d_v1")
    specs.extend(
        [
            replace(
                high_beta,
                route_id="cached_high_beta_momentum_call_debit_stop6_10d_v1",
                mechanism="high_beta_positive_20d_momentum_with_6pct_path_stop",
                stop_loss_pct=0.06,
            ),
            replace(
                high_beta,
                route_id="cached_high_beta_momentum_call_debit_time5_v1",
                mechanism="high_beta_positive_20d_momentum_with_5_session_time_exit",
                hard_stop_sessions=5,
                time_exit_sessions=5,
            ),
            replace(
                high_beta,
                route_id="cached_high_beta_momentum_call_debit_stop6_time5_v1",
                mechanism="high_beta_positive_20d_momentum_with_6pct_stop_and_5_session_exit",
                hard_stop_sessions=5,
                stop_loss_pct=0.06,
                time_exit_sessions=5,
            ),
        ]
    )
    return specs


def _closed_family_quarantine(repo: Path) -> list[dict[str, str]]:
    items: dict[str, dict[str, str]] = {}
    for path in sorted((repo / "reports" / "trader-wakes" / "moa").glob("*/compounding.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for family in row.get("closed_families") or []:
            family_text = str(family).strip()
            if family_text:
                items[family_text.lower()] = {"family": family_text, "fingerprint": ""}
    return [items[key] for key in sorted(items)]


def _route_dict(spec: RouteSpec) -> dict[str, Any]:
    path_aware = spec.stop_loss_pct is not None or spec.time_exit_sessions is not None
    return {
        "id": spec.route_id,
        "family": spec.family,
        "mechanism": spec.mechanism,
        "symbols": list(spec.symbols),
        "direction": spec.direction,
        "horizon_sessions": spec.horizon_sessions,
        "trigger": {
            "name": spec.trigger_name,
            "source_semantics": "cached_daily_ohlcv_close_known_at_signal_close",
        },
        "controls": {
            "population": spec.controls_population,
            "pairing": "same_date_benchmark_return_explicit_on_event_row",
        },
        "risk_management": {
            "type": "path_aware" if path_aware else "terminal_close",
            "entry": "signal_close",
            "path_source": "cached_daily_ohlc_after_signal_close",
            "stop_loss_pct": spec.stop_loss_pct,
            "time_exit_sessions": spec.time_exit_sessions or spec.horizon_sessions,
            "gap_fill": "next_session_open_when_open_breaches_stop",
            "intraday_stop_fill": "stop_threshold_when_low_breaches_after_open",
            "same_bar_reentry": False,
        },
        "planned_structure": {"expression": spec.planned_expression, "risk_type": "defined"},
        "capital_bounds": {
            "max_loss_usd": spec.max_loss_usd,
            "drawdown_budget_usd": spec.drawdown_budget_usd,
            "hard_stop_sessions": spec.hard_stop_sessions,
            "same_bar_reentry": False,
            "cost_per_event": spec.cost_per_event,
        },
        "gates": {
            "min_train_events": spec.min_train_events,
            "min_train_years": spec.min_train_years,
            "min_controls": spec.min_controls,
            "min_event_mean_after_cost": spec.min_event_mean_after_cost,
            "min_paired_excess_mean": spec.min_paired_excess_mean,
            "min_lower_bound": spec.min_lower_bound,
            "min_hit_rate": spec.min_hit_rate,
            "min_tail": spec.min_tail,
            "cost_per_event": spec.cost_per_event,
        },
        "search_budget": {"max_variants": 1},
    }


def _control_symbol(symbol: str, available: set[str]) -> str:
    if symbol == "SPY" and "QQQ" in available:
        return "QQQ"
    if symbol == "QQQ" and "SPY" in available:
        return "SPY"
    return "SPY" if "SPY" in available else sorted(available)[0]


def _managed_forward_return(frame: pd.DataFrame, entry_date: pd.Timestamp, spec: RouteSpec) -> float | None:
    """Return a predeclared OHLC-path-managed long return from the signal close."""
    if spec.direction != "long":
        raise ValueError("path-managed route batch currently supports long routes only")
    if spec.stop_loss_pct is not None and not 0.0 < spec.stop_loss_pct < 1.0:
        raise ValueError(f"invalid stop_loss_pct for {spec.route_id}: {spec.stop_loss_pct}")
    exit_sessions = spec.time_exit_sessions or spec.horizon_sessions
    if not 1 <= exit_sessions <= spec.horizon_sessions:
        raise ValueError(f"invalid time exit for {spec.route_id}: {exit_sessions}")
    try:
        entry_position = int(frame.index.get_loc(entry_date))
    except KeyError:
        return None
    if entry_position + spec.horizon_sessions >= len(frame):
        return None

    entry_close = float(frame.iloc[entry_position]["close"])
    stop_price = entry_close * (1.0 - spec.stop_loss_pct) if spec.stop_loss_pct is not None else None
    for offset in range(1, exit_sessions + 1):
        row = frame.iloc[entry_position + offset]
        if stop_price is not None:
            session_open = float(row["open"])
            session_low = float(row["low"])
            if session_open <= stop_price:
                return session_open / entry_close - 1.0
            if session_low <= stop_price:
                return stop_price / entry_close - 1.0
    exit_close = float(frame.iloc[entry_position + exit_sessions]["close"])
    return exit_close / entry_close - 1.0


def _candidate_events(spec: RouteSpec, frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for symbol in spec.symbols:
        if symbol not in frames:
            continue
        f = _features(frames[symbol]["close"], spec.horizon_sessions)
        mask = spec.predicate(f).fillna(False) & f["future_return"].notna()
        for date in f.index[mask]:
            managed_return = _managed_forward_return(frames[symbol], pd.Timestamp(date), spec)
            if managed_return is not None:
                events.append({"date": pd.Timestamp(date), "symbol": symbol, "event_return": managed_return})
    events.sort(key=lambda item: (item["date"], item["symbol"]))
    return events


def _panel_rows(spec: RouteSpec, events: list[dict[str, Any]], frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    available = set(frames)
    if not events:
        return rows
    cutoff_index = max(1, int(len(events) * 0.7))
    for idx, event in enumerate(events):
        split = "train" if idx < cutoff_index else "holdout"
        symbol = str(event["symbol"])
        date = pd.Timestamp(event["date"])
        control_symbol = _control_symbol(symbol, available)
        control_return = _managed_forward_return(frames[control_symbol], date, spec)
        if control_return is None:
            continue
        date_text = date.date().isoformat()
        rows.append(
            {
                "date": date_text,
                "split": split,
                "route_id": spec.route_id,
                "is_event": 1,
                "is_control": 0,
                "event_return": f"{float(event['event_return']):.10f}",
                "control_return": f"{control_return:.10f}",
                "symbol": symbol,
            }
        )
        rows.append(
            {
                "date": date_text,
                "split": split,
                "route_id": spec.route_id,
                "is_event": 0,
                "is_control": 1,
                "event_return": "",
                "control_return": f"{control_return:.10f}",
                "symbol": control_symbol,
            }
        )
    return rows


def build_batch(repo: Path, routes_out: Path, panel_out: Path) -> dict[str, Any]:
    specs = _route_specs()
    symbols = sorted({symbol for spec in specs for symbol in spec.symbols} | {"SPY", "QQQ"})
    frames = {symbol: _load_cached_ohlc(repo, symbol) for symbol in symbols}
    routes = [_route_dict(spec) for spec in specs]
    quarantine = _closed_family_quarantine(repo)

    panel_rows: list[dict[str, Any]] = []
    route_counts: dict[str, dict[str, int]] = {}
    for spec in specs:
        events = _candidate_events(spec, frames)
        rows = _panel_rows(spec, events, frames)
        panel_rows.extend(rows)
        route_counts[spec.route_id] = {
            "candidate_events": len(events),
            "panel_event_rows": sum(1 for row in rows if row["is_event"] == 1),
            "train_events": sum(1 for row in rows if row["is_event"] == 1 and row["split"] == "train"),
            "holdout_events": sum(1 for row in rows if row["is_event"] == 1 and row["split"] == "holdout"),
        }

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Trader cached daily OHLCV; route predicates predeclared in scripts/trader_strategy_engine_route_batch.py",
        "quarantine": quarantine,
        "routes": routes,
    }
    routes_out.parent.mkdir(parents=True, exist_ok=True)
    panel_out.parent.mkdir(parents=True, exist_ok=True)
    routes_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with panel_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "split", "route_id", "is_event", "is_control", "event_return", "control_return", "symbol"],
        )
        writer.writeheader()
        writer.writerows(panel_rows)
    return {
        "ok": True,
        "routes_path": str(routes_out),
        "panel_path": str(panel_out),
        "route_count": len(routes),
        "panel_rows": len(panel_rows),
        "route_counts": route_counts,
        "quarantine_count": len(quarantine),
    }


def _repo_path(repo: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo / path
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--routes-out", default=DEFAULT_ROUTES_OUT)
    parser.add_argument("--panel-out", default=DEFAULT_PANEL_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    try:
        result = build_batch(repo, _repo_path(repo, args.routes_out), _repo_path(repo, args.panel_out))
    except Exception as exc:  # fail closed CLI receipt
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Paper-only Black-Scholes daily-bar simulator for long call diagonals."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

import pricing
from trader_platform.research.corporate_action_risk import (
    DividendEventProvider,
    assess_short_call_assignment_risk,
)
from trader_platform.research.pcs_sim import capital_fit_pcs, strike_increment_for


def _num(cfg: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return float(default)


@dataclass
class DiagonalTrade:
    entry_date: pd.Timestamp
    short_expiration: pd.Timestamp
    long_expiration: pd.Timestamp
    short_strike: float
    long_strike: float
    entry_debit: float
    short_dte_at_entry: int
    long_dte_at_entry: int
    iv_at_entry: float
    short_iv_at_entry: float
    long_iv_at_entry: float
    short_iv_multiplier: float
    long_iv_multiplier: float
    regime_at_entry: str
    closed: bool = False
    exit_date: Optional[pd.Timestamp] = None
    exit_credit: Optional[float] = None
    exit_reason: Optional[str] = None

    def mark_credit(
        self,
        spot: float,
        iv_proxy: float,
        today: pd.Timestamp,
        r: float = 0.04,
        half_spread_per_leg: float = 0.0,
    ) -> float:
        short_days = max((self.short_expiration - today).days, 0)
        long_days = max((self.long_expiration - today).days, 0)
        short_sigma = max(iv_proxy * max(self.short_iv_multiplier, 0.01), 1e-6)
        long_sigma = max(iv_proxy * max(self.long_iv_multiplier, 0.01), 1e-6)
        short_call = (
            max(spot - self.short_strike, 0.0)
            if short_days == 0
            else pricing.price(spot, self.short_strike, short_days / 365.0, short_sigma, "call", r=r)
        )
        long_call = (
            max(spot - self.long_strike, 0.0)
            if long_days == 0
            else pricing.price(spot, self.long_strike, long_days / 365.0, long_sigma, "call", r=r)
        )
        half_spread = max(float(half_spread_per_leg), 0.0)
        return max(float(long_call - short_call - 2.0 * half_spread), 0.0)


@dataclass
class DiagonalSimResult:
    symbol: str
    ok: bool
    skipped: bool = False
    reason: str = ""
    period: str = ""
    n_trades: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    trades: list[DiagonalTrade] = field(default_factory=list)
    capital: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trades"] = [
            {
                "entry": str(t.entry_date.date()),
                "exit": str(t.exit_date.date()) if t.exit_date is not None else None,
                "short_strike": t.short_strike,
                "long_strike": t.long_strike,
                "short_dte": t.short_dte_at_entry,
                "long_dte": t.long_dte_at_entry,
                "short_iv": round(t.short_iv_at_entry, 4),
                "long_iv": round(t.long_iv_at_entry, 4),
                "debit": round(t.entry_debit, 4),
                "exit_credit": None if t.exit_credit is None else round(t.exit_credit, 4),
                "pnl_share": None if t.exit_credit is None else round(t.exit_credit - t.entry_debit, 4),
                "reason": t.exit_reason,
            }
            for t in self.trades
        ]
        return data


def pick_diagonal_entry(
    row: pd.Series, spot: float, today: pd.Timestamp, cfg: dict[str, Any]
) -> Optional[DiagonalTrade]:
    sigma = float(row.get("iv_proxy") or 0.0)
    if not np.isfinite(sigma) or sigma <= 0:
        return None
    if float(row.get("iv_rank") or 0.0) < _num(cfg, "iv_rank_min", 0.0):
        return None
    if str(row.get("regime") or "").lower() in {"bearish", "huge_down", "normal_down"}:
        return None

    short_dte = max(int(round(_num(cfg, "diagonal_short_dte", 14))), 2)
    long_dte = max(int(round(_num(cfg, "diagonal_long_dte", 60))), short_dte + 14)
    short_delta = min(max(_num(cfg, "diagonal_short_delta", 0.25), 0.08), 0.45)
    long_delta = min(max(_num(cfg, "diagonal_long_delta", 0.70), 0.55), 0.90)
    r = _num(cfg, "risk_free_rate", 0.04)
    short_iv_multiplier = _num(cfg, "front_iv_multiplier", 1.05)
    long_iv_multiplier = _num(cfg, "back_iv_multiplier", 0.95)
    short_sigma = max(sigma * short_iv_multiplier, 1e-6)
    long_sigma = max(sigma * long_iv_multiplier, 1e-6)
    try:
        short_exact = pricing.strike_from_delta(
            spot, short_dte / 365.0, short_sigma, short_delta, "call", r=r
        )
        long_exact = pricing.strike_from_delta(
            spot, long_dte / 365.0, long_sigma, long_delta, "call", r=r
        )
    except ValueError:
        return None
    increment = strike_increment_for(spot)
    short_strike = pricing.round_strike(short_exact, increment)
    long_strike = pricing.round_strike(long_exact, increment)
    if long_strike >= short_strike:
        long_strike = short_strike - increment

    slip = max(_num(cfg, "slippage_pct", 0.0), 0.0)
    half_spread = max(_num(cfg, "half_spread_per_leg", 0.0), 0.0)
    short_call = max(
        pricing.price(spot, short_strike, short_dte / 365.0, short_sigma, "call", r=r)
        * (1.0 - slip)
        - half_spread,
        0.0,
    )
    long_call = (
        pricing.price(spot, long_strike, long_dte / 365.0, long_sigma, "call", r=r)
        * (1.0 + slip)
        + half_spread
    )
    debit = float(long_call - short_call)
    if debit <= 0.01 or debit * 100.0 > _num(cfg, "max_loss_budget_usd", 300.0):
        return None
    return DiagonalTrade(
        entry_date=today,
        short_expiration=pd.Timestamp(today + pd.Timedelta(days=short_dte)),
        long_expiration=pd.Timestamp(today + pd.Timedelta(days=long_dte)),
        short_strike=float(short_strike),
        long_strike=float(long_strike),
        entry_debit=debit,
        short_dte_at_entry=short_dte,
        long_dte_at_entry=long_dte,
        iv_at_entry=sigma,
        short_iv_at_entry=short_sigma,
        long_iv_at_entry=long_sigma,
        short_iv_multiplier=short_iv_multiplier,
        long_iv_multiplier=long_iv_multiplier,
        regime_at_entry=str(row.get("regime") or ""),
    )


def _metrics(trades: list[DiagonalTrade]) -> dict[str, Any]:
    if not trades:
        return {"n_trades": 0, "structure": "diagonal_spread"}
    pnl = np.array(
        [((t.exit_credit or 0.0) - t.entry_debit) * 100.0 for t in trades], dtype=float
    )
    equity = np.cumsum(pnl)
    dd = np.maximum.accumulate(equity) - equity
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    reasons: dict[str, int] = {}
    for trade in trades:
        reasons[trade.exit_reason or "unknown"] = reasons.get(trade.exit_reason or "unknown", 0) + 1
    max_losses = np.array([t.entry_debit * 100.0 for t in trades], dtype=float)
    return {
        "n_trades": len(trades),
        "win_rate_pct": float(len(wins) / len(trades) * 100.0),
        "total_pnl_per_contract": float(pnl.sum()),
        "avg_pnl_per_contract": float(pnl.mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf"),
        "max_dd_per_contract": float(dd.max()) if len(dd) else 0.0,
        "avg_days_held": float(
            np.mean([(t.exit_date - t.entry_date).days for t in trades if t.exit_date is not None])
        ),
        "exit_reasons": reasons,
        "avg_max_loss_usd": float(max_losses.mean()),
        "p95_max_loss_usd": float(np.percentile(max_losses, 95)),
        "worst_max_loss_usd": float(max_losses.max()),
        "structure": "diagonal_spread",
    }


def run_diagonal_backtest(
    symbol: str,
    *,
    period: str = "2y",
    use_cache: bool = True,
    config: Optional[dict[str, Any]] = None,
    sleeve_usd: float = 3000.0,
    open_risk_budget_usd: float = 750.0,
    df: Optional[pd.DataFrame] = None,
    min_bars: int = 15,
    dividend_event_provider: Optional[DividendEventProvider] = None,
    require_dividend_events: bool = False,
) -> DiagonalSimResult:
    """Run one-position-at-a-time long-call-diagonal research simulation."""
    cfg = dict(config or {})
    sym = symbol.upper()
    if require_dividend_events and dividend_event_provider is None:
        return DiagonalSimResult(
            sym,
            False,
            True,
            "required dividend event provider missing",
            period,
            config=cfg,
        )
    if df is None:
        try:
            from data import build

            df = build(sym, period=period, use_cache=use_cache)
        except Exception as exc:  # noqa: BLE001
            return DiagonalSimResult(sym, False, True, f"build failed: {exc}", period, config=cfg)
    if df is None or len(df) < min_bars:
        return DiagonalSimResult(sym, False, True, "insufficient history", period, config=cfg)

    trades: list[DiagonalTrade] = []
    open_trade: Optional[DiagonalTrade] = None
    r = _num(cfg, "risk_free_rate", 0.04)
    slip = max(_num(cfg, "slippage_pct", 0.0), 0.0)
    half_spread = max(_num(cfg, "half_spread_per_leg", 0.0), 0.0)
    for index_value, row in df.iterrows():
        today = pd.Timestamp(index_value)
        spot = float(row["close"])
        sigma = float(row["iv_proxy"])
        if not np.isfinite(sigma) or sigma <= 0:
            continue
        if open_trade is not None:
            credit = (
                open_trade.mark_credit(
                    spot, sigma, today, r=r, half_spread_per_leg=half_spread
                )
                * (1.0 - slip)
            )
            pnl = credit - open_trade.entry_debit
            short_days = (open_trade.short_expiration - today).days
            reason = None
            try:
                events = (
                    dividend_event_provider(sym, today, open_trade.short_expiration)
                    if dividend_event_provider is not None
                    else ()
                )
            except Exception as exc:  # noqa: BLE001
                return DiagonalSimResult(
                    sym,
                    False,
                    True,
                    f"dividend event provider failed on {today.date()}: {exc}",
                    period,
                    config=cfg,
                )
            if events is None and require_dividend_events:
                return DiagonalSimResult(
                    sym,
                    False,
                    True,
                    f"required dividend event coverage missing on {today.date()}",
                    period,
                    config=cfg,
                )
            short_mark = (
                max(spot - open_trade.short_strike, 0.0)
                if short_days <= 0
                else pricing.price(
                    spot,
                    open_trade.short_strike,
                    short_days / 365.0,
                    max(sigma * max(open_trade.short_iv_multiplier, 0.01), 1e-6),
                    "call",
                    r=r,
                )
            )
            try:
                assignment = assess_short_call_assignment_risk(
                    symbol=sym,
                    as_of=today,
                    expiration=open_trade.short_expiration,
                    spot=spot,
                    short_strike=open_trade.short_strike,
                    short_call_mark=float(short_mark),
                    events=events or (),
                    dividend_to_extrinsic_ratio=_num(
                        cfg, "assignment_dividend_to_extrinsic_ratio", 1.0
                    ),
                )
            except (TypeError, ValueError) as exc:
                return DiagonalSimResult(
                    sym,
                    False,
                    True,
                    f"invalid dividend event data on {today.date()}: {exc}",
                    period,
                    config=cfg,
                )
            if assignment.at_risk:
                reason = "early_assignment_risk"
            elif pnl >= _num(cfg, "profit_target", 0.30) * open_trade.entry_debit:
                reason = "profit_target"
            elif pnl <= -_num(cfg, "defined_loss_exit_frac", 0.65) * open_trade.entry_debit:
                reason = "defined_loss"
            elif short_days <= int(round(_num(cfg, "dte_stop", 0))):
                reason = "short_expiry"
            if reason is not None:
                open_trade.exit_date = today
                open_trade.exit_credit = max(credit, 0.0)
                open_trade.exit_reason = reason
                open_trade.closed = True
                trades.append(open_trade)
                open_trade = None
        if open_trade is None and (not trades or trades[-1].exit_date != today):
            open_trade = pick_diagonal_entry(row, spot, today, cfg)

    if open_trade is not None:
        today = pd.Timestamp(df.index[-1])
        row = df.iloc[-1]
        credit = open_trade.mark_credit(
            float(row["close"]),
            max(float(row["iv_proxy"]), 1e-6),
            today,
            r=r,
            half_spread_per_leg=half_spread,
        ) * (1.0 - slip)
        open_trade.exit_date = today
        open_trade.exit_credit = max(credit, 0.0)
        open_trade.exit_reason = "end_of_data"
        open_trade.closed = True
        trades.append(open_trade)

    metrics = _metrics(trades)
    metrics["corporate_action_mode"] = (
        "required"
        if require_dividend_events
        else "optional"
        if dividend_event_provider
        else "disabled"
    )
    metrics["early_assignment_risk_exits"] = sum(
        trade.exit_reason == "early_assignment_risk" for trade in trades
    )
    representative_loss = (
        float(np.percentile([t.entry_debit * 100.0 for t in trades], 95))
        if trades
        else _num(cfg, "max_loss_budget_usd", 300.0)
    )
    capital = capital_fit_pcs(
        max_loss_usd=representative_loss,
        sleeve_usd=sleeve_usd,
        open_risk_budget_usd=open_risk_budget_usd,
        max_loss_budget_usd=_num(cfg, "max_loss_budget_usd", 300.0),
        structure="diagonal_spread",
    )
    capital["note"] = (
        "defined_debit_risk=max_entry_debit_usd; paper BS proxy with explicit "
        "short/long expiry IV multipliers; short-call dividend assignment guard is "
        "provider-dependent; observed surfaces not modeled"
    )
    return DiagonalSimResult(sym, True, False, "ok", period, len(trades), metrics, trades, capital, cfg)

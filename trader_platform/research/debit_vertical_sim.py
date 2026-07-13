"""Paper-only Black-Scholes daily-bar simulator for debit verticals."""

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


STRUCTURES = {"bull_call_debit_spread", "bear_put_debit_spread"}


def _num(cfg: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return float(default)


@dataclass
class DebitVerticalTrade:
    entry_date: pd.Timestamp
    expiration: pd.Timestamp
    structure: str
    right: str
    long_strike: float
    short_strike: float
    width: float
    entry_debit: float
    dte_at_entry: int
    iv_at_entry: float
    regime_at_entry: str
    closed: bool = False
    exit_date: Optional[pd.Timestamp] = None
    exit_credit: Optional[float] = None
    exit_reason: Optional[str] = None

    def mark_credit(
        self,
        spot: float,
        sigma: float,
        today: pd.Timestamp,
        *,
        r: float = 0.04,
        slippage_pct: float = 0.0,
        half_spread_per_leg: float = 0.0,
    ) -> float:
        days = max((self.expiration - today).days, 0)
        if days == 0:
            if self.right == "call":
                long_value = max(spot - self.long_strike, 0.0)
                short_value = max(spot - self.short_strike, 0.0)
            else:
                long_value = max(self.long_strike - spot, 0.0)
                short_value = max(self.short_strike - spot, 0.0)
        else:
            t = days / 365.0
            long_value = pricing.price(spot, self.long_strike, t, sigma, self.right, r=r)
            short_value = pricing.price(spot, self.short_strike, t, sigma, self.right, r=r)
        slip = max(float(slippage_pct), 0.0)
        half_spread = max(float(half_spread_per_leg), 0.0)
        return max(
            float(
                long_value * (1.0 - slip)
                - short_value * (1.0 + slip)
                - 2.0 * half_spread
            ),
            0.0,
        )


@dataclass
class DebitVerticalSimResult:
    symbol: str
    ok: bool
    skipped: bool = False
    reason: str = ""
    period: str = ""
    n_trades: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    trades: list[DebitVerticalTrade] = field(default_factory=list)
    capital: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trades"] = [
            {
                "entry": str(t.entry_date.date()),
                "exit": str(t.exit_date.date()) if t.exit_date is not None else None,
                "structure": t.structure,
                "right": t.right,
                "long_strike": t.long_strike,
                "short_strike": t.short_strike,
                "width": t.width,
                "dte": t.dte_at_entry,
                "debit": round(t.entry_debit, 4),
                "exit_credit": None if t.exit_credit is None else round(t.exit_credit, 4),
                "pnl_share": None if t.exit_credit is None else round(t.exit_credit - t.entry_debit, 4),
                "reason": t.exit_reason,
            }
            for t in self.trades
        ]
        return data


def pick_debit_vertical_entry(
    row: pd.Series,
    spot: float,
    today: pd.Timestamp,
    cfg: dict[str, Any],
    structure: str,
) -> Optional[DebitVerticalTrade]:
    if structure not in STRUCTURES:
        raise ValueError(f"unsupported debit vertical structure {structure!r}")
    sigma = float(row.get("iv_proxy") or 0.0)
    if not np.isfinite(sigma) or sigma <= 0:
        return None
    if float(row.get("iv_rank") or 0.0) < _num(cfg, "iv_rank_min", 0.0):
        return None
    regime = str(row.get("regime") or "").lower()
    bearish = regime in {"bearish", "huge_down", "normal_down"}
    bullish = regime in {"bullish", "huge_up", "normal_up"}
    if structure == "bull_call_debit_spread" and bearish:
        return None
    if structure == "bear_put_debit_spread" and bullish:
        return None

    dte = max(int(round(_num(cfg, "long_dte", 21))), 3)
    long_delta = min(max(_num(cfg, "debit_long_delta", 0.55), 0.40), 0.75)
    requested_width = max(_num(cfg, "spread_width", 2.0), 0.5)
    right = "call" if structure == "bull_call_debit_spread" else "put"
    r = _num(cfg, "risk_free_rate", 0.04)
    try:
        long_exact = pricing.strike_from_delta(spot, dte / 365.0, sigma, long_delta, right, r=r)
    except ValueError:
        return None
    increment = strike_increment_for(spot)
    long_strike = pricing.round_strike(long_exact, increment)
    width = max(int(round(requested_width / increment)), 1) * increment
    short_strike = long_strike + width if right == "call" else long_strike - width
    if short_strike <= 0:
        return None

    t = dte / 365.0
    slip = max(_num(cfg, "slippage_pct", 0.0), 0.0)
    half_spread = max(_num(cfg, "half_spread_per_leg", 0.0), 0.0)
    long_price = pricing.price(spot, long_strike, t, sigma, right, r=r) * (1.0 + slip) + half_spread
    short_price = max(
        pricing.price(spot, short_strike, t, sigma, right, r=r) * (1.0 - slip) - half_spread,
        0.0,
    )
    debit = float(long_price - short_price)
    if debit <= 0.01 or debit >= width:
        return None
    if debit * 100.0 > _num(cfg, "max_loss_budget_usd", 300.0):
        return None
    return DebitVerticalTrade(
        entry_date=today,
        expiration=pd.Timestamp(today + pd.Timedelta(days=dte)),
        structure=structure,
        right=right,
        long_strike=float(long_strike),
        short_strike=float(short_strike),
        width=float(width),
        entry_debit=debit,
        dte_at_entry=dte,
        iv_at_entry=sigma,
        regime_at_entry=str(row.get("regime") or ""),
    )


def _metrics(trades: list[DebitVerticalTrade], structure: str) -> dict[str, Any]:
    if not trades:
        return {"n_trades": 0, "structure": structure}
    pnl = np.array([((t.exit_credit or 0.0) - t.entry_debit) * 100.0 for t in trades], dtype=float)
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
        "structure": structure,
    }


def run_debit_vertical_backtest(
    symbol: str,
    *,
    structure: str,
    period: str = "2y",
    use_cache: bool = True,
    config: Optional[dict[str, Any]] = None,
    sleeve_usd: float = 3000.0,
    open_risk_budget_usd: float = 750.0,
    df: Optional[pd.DataFrame] = None,
    min_bars: int = 15,
    dividend_event_provider: Optional[DividendEventProvider] = None,
    require_dividend_events: bool = False,
) -> DebitVerticalSimResult:
    """Run one-position-at-a-time bull-call or bear-put debit vertical simulation."""
    cfg = dict(config or {})
    sym = symbol.upper()
    if structure not in STRUCTURES:
        return DebitVerticalSimResult(sym, False, True, "unsupported structure", period, config=cfg)
    if (
        structure == "bull_call_debit_spread"
        and require_dividend_events
        and dividend_event_provider is None
    ):
        return DebitVerticalSimResult(
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
            return DebitVerticalSimResult(sym, False, True, f"build failed: {exc}", period, config=cfg)
    if df is None or len(df) < min_bars:
        return DebitVerticalSimResult(sym, False, True, "insufficient history", period, config=cfg)

    trades: list[DebitVerticalTrade] = []
    open_trade: Optional[DebitVerticalTrade] = None
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
            credit = open_trade.mark_credit(
                spot,
                sigma,
                today,
                r=r,
                slippage_pct=slip,
                half_spread_per_leg=half_spread,
            )
            pnl = credit - open_trade.entry_debit
            days = (open_trade.expiration - today).days
            reason = None
            assignment_risk = False
            if open_trade.right == "call":
                try:
                    events = (
                        dividend_event_provider(sym, today, open_trade.expiration)
                        if dividend_event_provider is not None
                        else ()
                    )
                except Exception as exc:  # noqa: BLE001
                    return DebitVerticalSimResult(
                        sym,
                        False,
                        True,
                        f"dividend event provider failed on {today.date()}: {exc}",
                        period,
                        config=cfg,
                    )
                if events is None and require_dividend_events:
                    return DebitVerticalSimResult(
                        sym,
                        False,
                        True,
                        f"required dividend event coverage missing on {today.date()}",
                        period,
                        config=cfg,
                    )
                short_mark = (
                    max(spot - open_trade.short_strike, 0.0)
                    if days <= 0
                    else pricing.price(
                        spot,
                        open_trade.short_strike,
                        days / 365.0,
                        sigma,
                        "call",
                        r=r,
                    )
                )
                try:
                    assignment_risk = assess_short_call_assignment_risk(
                        symbol=sym,
                        as_of=today,
                        expiration=open_trade.expiration,
                        spot=spot,
                        short_strike=open_trade.short_strike,
                        short_call_mark=float(short_mark),
                        events=events or (),
                        dividend_to_extrinsic_ratio=_num(
                            cfg, "assignment_dividend_to_extrinsic_ratio", 1.0
                        ),
                    ).at_risk
                except (TypeError, ValueError) as exc:
                    return DebitVerticalSimResult(
                        sym,
                        False,
                        True,
                        f"invalid dividend event data on {today.date()}: {exc}",
                        period,
                        config=cfg,
                    )
            if assignment_risk:
                reason = "early_assignment_risk"
            elif pnl >= _num(cfg, "profit_target", 0.50) * open_trade.entry_debit:
                reason = "profit_target"
            elif pnl <= -_num(cfg, "defined_loss_exit_frac", 0.70) * open_trade.entry_debit:
                reason = "defined_loss"
            elif days <= int(round(_num(cfg, "dte_stop", 3))):
                reason = "dte_stop"
            if reason is not None:
                open_trade.exit_date = today
                open_trade.exit_credit = credit
                open_trade.exit_reason = reason
                open_trade.closed = True
                trades.append(open_trade)
                open_trade = None
        if open_trade is None and (not trades or trades[-1].exit_date != today):
            open_trade = pick_debit_vertical_entry(row, spot, today, cfg, structure)

    if open_trade is not None:
        today = pd.Timestamp(df.index[-1])
        row = df.iloc[-1]
        credit = open_trade.mark_credit(
            float(row["close"]),
            max(float(row["iv_proxy"]), 1e-6),
            today,
            r=r,
            slippage_pct=slip,
            half_spread_per_leg=half_spread,
        )
        open_trade.exit_date = today
        open_trade.exit_credit = credit
        open_trade.exit_reason = "end_of_data"
        open_trade.closed = True
        trades.append(open_trade)

    metrics = _metrics(trades, structure)
    metrics["corporate_action_mode"] = (
        "not_applicable_put"
        if structure == "bear_put_debit_spread"
        else "required"
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
        structure=structure,
    )
    capital["note"] = (
        "defined_debit_risk=max_entry_debit_usd; paper BS same-expiry vertical; "
        "bull-call short-leg dividend assignment guard is provider-dependent; "
        "observed option surfaces and non-dividend assignment are not modeled"
    )
    return DebitVerticalSimResult(sym, True, False, "ok", period, len(trades), metrics, trades, capital, cfg)

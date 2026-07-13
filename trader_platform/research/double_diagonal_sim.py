"""Paper-only Black-Scholes daily-bar simulator for defined-debit double diagonals."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

import pricing
from trader_platform.research.pcs_sim import capital_fit_pcs, strike_increment_for


def _num(cfg: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return float(default)


@dataclass
class DoubleDiagonalTrade:
    entry_date: pd.Timestamp
    front_expiration: pd.Timestamp
    back_expiration: pd.Timestamp
    short_put_strike: float
    long_put_strike: float
    short_call_strike: float
    long_call_strike: float
    entry_debit: float
    front_dte_at_entry: int
    back_dte_at_entry: int
    iv_at_entry: float
    front_iv_multiplier: float
    back_iv_multiplier: float
    regime_at_entry: str
    closed: bool = False
    exit_date: Optional[pd.Timestamp] = None
    exit_credit: Optional[float] = None
    exit_reason: Optional[str] = None

    @property
    def defined_max_loss_usd(self) -> float:
        """Frictionless structural loss bound; closing costs can exceed the debit."""
        return self.entry_debit * 100.0

    def mark_credit(
        self,
        spot: float,
        iv_proxy: float,
        today: pd.Timestamp,
        *,
        r: float = 0.04,
        slippage_pct: float = 0.0,
        half_spread_per_leg: float = 0.0,
    ) -> float:
        front_days = max((self.front_expiration - today).days, 0)
        back_days = max((self.back_expiration - today).days, 0)
        front_sigma = max(iv_proxy * max(self.front_iv_multiplier, 0.01), 1e-6)
        back_sigma = max(iv_proxy * max(self.back_iv_multiplier, 0.01), 1e-6)

        def option_value(strike: float, days: int, sigma: float, right: str) -> float:
            intrinsic = max(strike - spot, 0.0) if right == "put" else max(spot - strike, 0.0)
            if days == 0:
                return intrinsic
            # US-listed equity options are American-style.  The BS proxy is
            # European and can mark a deep-ITM longer-dated put below intrinsic;
            # retain the exercisable intrinsic floor so protective back legs do
            # not disappear exactly when the front short expires.
            return max(
                float(pricing.price(spot, strike, days / 365.0, sigma, right, r=r)),
                intrinsic,
            )

        short_marks = (
            option_value(self.short_put_strike, front_days, front_sigma, "put"),
            option_value(self.short_call_strike, front_days, front_sigma, "call"),
        )
        long_marks = (
            option_value(self.long_put_strike, back_days, back_sigma, "put"),
            option_value(self.long_call_strike, back_days, back_sigma, "call"),
        )
        slip = max(float(slippage_pct), 0.0)
        half_spread = max(float(half_spread_per_leg), 0.0)
        long_credit = sum(
            max(mark * (1.0 - slip) - half_spread, 0.0) for mark in long_marks
        )
        short_debit = sum(mark * (1.0 + slip) + half_spread for mark in short_marks)
        # Do not clip an adverse package liquidation to zero.  Entry debit is
        # the frictionless payoff bound, but explicit per-leg exit costs can
        # produce a small additional realized loss and must remain in evidence.
        return float(long_credit - short_debit)


def pick_double_diagonal_entry(
    row: pd.Series,
    spot: float,
    today: pd.Timestamp,
    cfg: dict[str, Any],
) -> Optional[DoubleDiagonalTrade]:
    try:
        sigma = float(row.get("iv_proxy"))
        iv_rank = float(row.get("iv_rank"))
    except (TypeError, ValueError):
        return None
    if not np.isfinite(sigma) or sigma <= 0 or not np.isfinite(iv_rank):
        return None
    if iv_rank < _num(cfg, "iv_rank_min", 20.0):
        return None
    if str(row.get("regime") or "").lower() != "neutral":
        return None

    front_dte = max(int(round(_num(cfg, "double_diagonal_short_dte", 14))), 2)
    back_dte = max(
        int(round(_num(cfg, "double_diagonal_long_dte", 60))),
        front_dte + 14,
    )
    short_delta = min(max(_num(cfg, "double_diagonal_short_delta", 0.30), 0.10), 0.45)
    long_offset_steps = max(
        int(round(_num(cfg, "double_diagonal_long_offset_steps", 0))),
        0,
    )
    r = _num(cfg, "risk_free_rate", 0.04)
    front_mult = max(_num(cfg, "front_iv_multiplier", 1.05), 0.01)
    back_mult = max(_num(cfg, "back_iv_multiplier", 0.95), 0.01)
    front_sigma = max(sigma * front_mult, 1e-6)
    back_sigma = max(sigma * back_mult, 1e-6)
    try:
        short_put_exact = pricing.strike_from_delta(
            spot, front_dte / 365.0, front_sigma, short_delta, "put", r=r
        )
        short_call_exact = pricing.strike_from_delta(
            spot, front_dte / 365.0, front_sigma, short_delta, "call", r=r
        )
    except ValueError:
        return None

    increment = strike_increment_for(spot)
    short_put = min(pricing.round_strike(short_put_exact, increment), spot - increment)
    short_call = max(pricing.round_strike(short_call_exact, increment), spot + increment)
    max_inward_steps = max(int((short_call - short_put) // (2.0 * increment)) - 1, 0)
    inward_steps = min(long_offset_steps, max_inward_steps)
    long_put = short_put + inward_steps * increment
    long_call = short_call - inward_steps * increment

    slip = max(_num(cfg, "slippage_pct", 0.0), 0.0)
    half_spread = max(_num(cfg, "half_spread_per_leg", 0.0), 0.0)
    short_put_mark = pricing.price(
        spot, short_put, front_dte / 365.0, front_sigma, "put", r=r
    )
    short_call_mark = pricing.price(
        spot, short_call, front_dte / 365.0, front_sigma, "call", r=r
    )
    long_put_mark = pricing.price(
        spot, long_put, back_dte / 365.0, back_sigma, "put", r=r
    )
    long_call_mark = pricing.price(
        spot, long_call, back_dte / 365.0, back_sigma, "call", r=r
    )
    short_credit = sum(
        max(mark * (1.0 - slip) - half_spread, 0.0)
        for mark in (short_put_mark, short_call_mark)
    )
    long_debit = sum(
        mark * (1.0 + slip) + half_spread for mark in (long_put_mark, long_call_mark)
    )
    debit = float(long_debit - short_credit)
    if debit <= 0.01 or debit * 100.0 > _num(cfg, "max_loss_budget_usd", 300.0):
        return None
    return DoubleDiagonalTrade(
        entry_date=today,
        front_expiration=pd.Timestamp(today + pd.Timedelta(days=front_dte)),
        back_expiration=pd.Timestamp(today + pd.Timedelta(days=back_dte)),
        short_put_strike=float(short_put),
        long_put_strike=float(long_put),
        short_call_strike=float(short_call),
        long_call_strike=float(long_call),
        entry_debit=debit,
        front_dte_at_entry=front_dte,
        back_dte_at_entry=back_dte,
        iv_at_entry=sigma,
        front_iv_multiplier=front_mult,
        back_iv_multiplier=back_mult,
        regime_at_entry=str(row.get("regime") or ""),
    )


@dataclass
class DoubleDiagonalSimResult:
    symbol: str
    ok: bool
    skipped: bool = False
    reason: str = ""
    period: str = ""
    n_trades: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    trades: list[DoubleDiagonalTrade] = field(default_factory=list)
    capital: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trades"] = [
            {
                "entry": str(trade.entry_date.date()),
                "exit": str(trade.exit_date.date()) if trade.exit_date is not None else None,
                "front_expiration": str(trade.front_expiration.date()),
                "back_expiration": str(trade.back_expiration.date()),
                "short_put_strike": trade.short_put_strike,
                "long_put_strike": trade.long_put_strike,
                "short_call_strike": trade.short_call_strike,
                "long_call_strike": trade.long_call_strike,
                "entry_debit": round(trade.entry_debit, 6),
                "exit_credit": (
                    None if trade.exit_credit is None else round(trade.exit_credit, 6)
                ),
                "pnl_share": (
                    None
                    if trade.exit_credit is None
                    else round(trade.exit_credit - trade.entry_debit, 6)
                ),
                "reason": trade.exit_reason,
            }
            for trade in self.trades
        ]
        return data


def _metrics(trades: list[DoubleDiagonalTrade]) -> dict[str, Any]:
    if not trades:
        return {
            "n_trades": 0,
            "structure": "double_diagonal_spread",
            "option_mark_provenance": "black_scholes_proxy",
            "legs_per_trade": 4,
        }
    pnl = np.array(
        [((trade.exit_credit or 0.0) - trade.entry_debit) * 100.0 for trade in trades],
        dtype=float,
    )
    equity = np.cumsum(pnl)
    drawdown = np.maximum.accumulate(equity) - equity
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    reasons: dict[str, int] = {}
    for trade in trades:
        reason = trade.exit_reason or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
    max_losses = np.array([trade.entry_debit * 100.0 for trade in trades], dtype=float)
    worst_realized_loss = float(max(-float(pnl.min()), 0.0))
    return {
        "n_trades": len(trades),
        "win_rate_pct": float(len(wins) / len(trades) * 100.0),
        "total_pnl_per_contract": float(pnl.sum()),
        "avg_pnl_per_contract": float(pnl.mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf"),
        "max_dd_per_contract": float(drawdown.max()) if len(drawdown) else 0.0,
        "avg_days_held": float(
            np.mean(
                [
                    (trade.exit_date - trade.entry_date).days
                    for trade in trades
                    if trade.exit_date is not None
                ]
            )
        ),
        "exit_reasons": reasons,
        "avg_max_loss_usd": float(max_losses.mean()),
        "p95_max_loss_usd": float(np.percentile(max_losses, 95)),
        "worst_max_loss_usd": float(max_losses.max()),
        "worst_realized_loss_usd": worst_realized_loss,
        "structural_max_loss_scope": "entry_debit_before_closing_friction",
        "structure": "double_diagonal_spread",
        "option_mark_provenance": "black_scholes_proxy",
        "legs_per_trade": 4,
    }


def run_double_diagonal_backtest(
    symbol: str,
    *,
    period: str = "2y",
    use_cache: bool = True,
    config: Optional[dict[str, Any]] = None,
    sleeve_usd: float = 3000.0,
    open_risk_budget_usd: float = 750.0,
    df: Optional[pd.DataFrame] = None,
    min_bars: int = 15,
) -> DoubleDiagonalSimResult:
    """Run one-position-at-a-time defined-debit double-diagonal research simulation."""
    cfg = dict(config or {})
    sym = symbol.upper()
    if df is None:
        try:
            from data import build

            df = build(sym, period=period, use_cache=use_cache)
        except Exception as exc:  # noqa: BLE001
            return DoubleDiagonalSimResult(
                sym, False, True, f"build failed: {exc}", period, config=cfg
            )
    if df is None or len(df) < min_bars:
        return DoubleDiagonalSimResult(
            sym, False, True, "insufficient history", period, config=cfg
        )

    trades: list[DoubleDiagonalTrade] = []
    open_trade: Optional[DoubleDiagonalTrade] = None
    r = _num(cfg, "risk_free_rate", 0.04)
    slip = max(_num(cfg, "slippage_pct", 0.0), 0.0)
    half_spread = max(_num(cfg, "half_spread_per_leg", 0.0), 0.0)
    for index_value, row in df.iterrows():
        today = pd.Timestamp(index_value)
        try:
            spot = float(row["close"])
            sigma = float(row["iv_proxy"])
        except (TypeError, ValueError, KeyError):
            continue
        if not np.isfinite(spot) or spot <= 0 or not np.isfinite(sigma) or sigma <= 0:
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
            front_days = (open_trade.front_expiration - today).days
            reason = None
            if pnl >= _num(cfg, "profit_target", 0.30) * open_trade.entry_debit:
                reason = "profit_target"
            elif pnl <= -_num(cfg, "defined_loss_exit_frac", 0.65) * open_trade.entry_debit:
                reason = "defined_loss"
            elif front_days <= int(round(_num(cfg, "dte_stop", 0))):
                reason = "front_expiry"
            if reason is not None:
                open_trade.exit_date = today
                open_trade.exit_credit = credit
                open_trade.exit_reason = reason
                open_trade.closed = True
                trades.append(open_trade)
                open_trade = None
        if open_trade is None and (not trades or trades[-1].exit_date != today):
            open_trade = pick_double_diagonal_entry(row, spot, today, cfg)

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

    metrics = _metrics(trades)
    structural_loss = (
        max(trade.entry_debit * 100.0 for trade in trades)
        if trades
        else _num(cfg, "max_loss_budget_usd", 300.0)
    )
    worst_loss = max(structural_loss, float(metrics.get("worst_realized_loss_usd") or 0.0))
    capital = capital_fit_pcs(
        max_loss_usd=worst_loss,
        sleeve_usd=sleeve_usd,
        open_risk_budget_usd=open_risk_budget_usd,
        max_loss_budget_usd=_num(cfg, "max_loss_budget_usd", 300.0),
        structure="double_diagonal_spread",
    )
    # Generic capital-fit reports mathematical sleeve/open-risk capacity (up to
    # three lots).  This L0 four-leg proxy deliberately exposes a stricter
    # operating posture: at most one lot, while retaining the theoretical
    # capacity separately so reports do not conflate policy with arithmetic.
    theoretical_max_lots = int(capital["max_lots"])
    capital["theoretical_max_lots"] = theoretical_max_lots
    capital["max_lots"] = min(theoretical_max_lots, 1)
    capital["max_lots_policy"] = "one_lot_conservative_operating_posture"
    capital["structural_max_loss_usd"] = round(structural_loss, 2)
    capital["observed_path_worst_loss_usd"] = round(
        float(metrics.get("worst_realized_loss_usd") or 0.0), 2
    )
    capital["note"] = (
        "capital max_loss=max(structural entry debit, observed stressed realized loss); "
        "max_lots=one-lot operating cap while theoretical_max_lots retains capacity math; "
        "percentage/fixed costs are L0 sensitivities, not a hard live-fill bound; "
        "four-leg Black-Scholes proxy; observed surfaces and assignment are unmodeled"
    )
    return DoubleDiagonalSimResult(
        sym,
        True,
        False,
        "ok",
        period,
        len(trades),
        metrics,
        trades,
        capital,
        cfg,
    )

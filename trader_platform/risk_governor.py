"""Deterministic pre-trade risk checks. No network, no secrets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import yaml

_ROOT = Path(__file__).resolve().parent
_DEFAULT_LIMITS = _ROOT / "risk_limits.yaml"
_REPO_ROOT = _ROOT.parent


@dataclass
class OrderIntent:
    symbol: str
    side: str  # buy | sell
    qty: float
    order_type: str  # limit | market
    limit_price: Optional[float] = None
    strategy_id: Optional[str] = None
    notional: Optional[float] = None  # if omitted, qty * limit_price * 100 (options) or *1
    multiplier: float = 100.0  # equity options default
    tag: str = ""

    def estimated_notional(self) -> float:
        if self.notional is not None:
            return abs(float(self.notional))
        if self.limit_price is None:
            return 0.0
        return abs(float(self.qty) * float(self.limit_price) * float(self.multiplier))


@dataclass
class RiskDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)

    def deny(self, reason: str) -> "RiskDecision":
        self.allowed = False
        self.reasons.append(reason)
        return self


def load_limits(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _DEFAULT_LIMITS
    with p.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"risk limits must be a mapping: {p}")
    return data


def _kill_switch_path(limits: Mapping[str, Any], repo_root: Path = _REPO_ROOT) -> Path:
    raw = limits.get("kill_switch_file") or "agentic_kill.switch"
    p = Path(raw)
    if not p.is_absolute():
        p = repo_root / p
    return p


@dataclass
class PortfolioSnapshot:
    open_risk: float = 0.0
    open_order_count: int = 0
    daily_pnl: float = 0.0  # negative = loss


class RiskGovernor:
    def __init__(
        self,
        limits: Mapping[str, Any] | None = None,
        limits_path: Path | str | None = None,
        repo_root: Path | None = None,
    ):
        self.limits: dict[str, Any] = dict(limits) if limits is not None else load_limits(limits_path)
        self.repo_root = repo_root or _REPO_ROOT

    def check(
        self,
        intent: OrderIntent,
        *,
        portfolio: PortfolioSnapshot | None = None,
        mode: str = "paper",
        require_agentic_enabled_for_live: bool = True,
    ) -> RiskDecision:
        decision = RiskDecision(allowed=True)
        portfolio = portfolio or PortfolioSnapshot()
        order_cfg = self.limits.get("order") or {}
        port_cfg = self.limits.get("portfolio") or {}
        agentic = self.limits.get("agentic") or {}

        kill = _kill_switch_path(self.limits, self.repo_root)
        if kill.exists():
            return decision.deny(f"kill switch present: {kill}")

        if mode == "agentic_live" and require_agentic_enabled_for_live:
            if not agentic.get("enabled", False):
                return decision.deny("agentic.enabled is false; cannot agentic_live")

        side = (intent.side or "").lower()
        otype = (intent.order_type or "").lower()
        symbol = (intent.symbol or "").upper()

        allowed_sides = [s.lower() for s in (order_cfg.get("allowed_sides") or ["buy", "sell"])]
        if side not in allowed_sides:
            decision.deny(f"side {side!r} not in {allowed_sides}")

        allowed_types = [t.lower() for t in (order_cfg.get("allowed_order_types") or ["limit"])]
        if otype not in allowed_types:
            decision.deny(f"order_type {otype!r} not in {allowed_types}")

        if otype == "market" and not order_cfg.get("allow_market", False):
            decision.deny("market orders disabled (prefer working limits)")

        if otype == "limit" and (intent.limit_price is None or float(intent.limit_price) <= 0):
            decision.deny("limit order requires positive limit_price")

        max_contracts = float(order_cfg.get("max_contracts_per_order", 5))
        if float(intent.qty) <= 0:
            decision.deny("qty must be positive")
        elif float(intent.qty) > max_contracts:
            decision.deny(f"qty {intent.qty} > max_contracts_per_order {max_contracts}")

        notional = intent.estimated_notional()
        max_notional = float(order_cfg.get("max_notional_per_order", 2500))
        if notional > max_notional:
            decision.deny(f"notional {notional:.2f} > max_notional_per_order {max_notional}")

        max_open_risk = float(port_cfg.get("max_open_risk", 5000))
        if portfolio.open_risk + notional > max_open_risk:
            decision.deny(
                f"open_risk {portfolio.open_risk:.2f} + {notional:.2f} > max_open_risk {max_open_risk}"
            )

        max_open_orders = int(port_cfg.get("max_open_orders", 10))
        if portfolio.open_order_count >= max_open_orders:
            decision.deny(f"open_order_count {portfolio.open_order_count} >= max_open_orders {max_open_orders}")

        max_daily_loss = float(port_cfg.get("max_daily_loss", 750))
        if portfolio.daily_pnl <= -abs(max_daily_loss):
            decision.deny(
                f"daily loss kill: daily_pnl {portfolio.daily_pnl:.2f} <= -{max_daily_loss}"
            )

        allowlist: Sequence[str] = self.limits.get("strategy_allowlist") or []
        disabled: Sequence[str] = self.limits.get("strategy_disabled") or []
        if intent.strategy_id:
            if allowlist and intent.strategy_id not in allowlist:
                decision.deny(f"strategy {intent.strategy_id!r} not in allowlist")
            if intent.strategy_id in disabled:
                decision.deny(f"strategy {intent.strategy_id!r} is disabled")

        instruments = [s.upper() for s in (self.limits.get("instrument_allowlist") or [])]
        if instruments and symbol not in instruments:
            decision.deny(f"symbol {symbol!r} not in instrument_allowlist")

        return decision


def check_order(
    intent: OrderIntent,
    *,
    portfolio: PortfolioSnapshot | None = None,
    mode: str = "paper",
    limits_path: Path | str | None = None,
) -> RiskDecision:
    return RiskGovernor(limits_path=limits_path).check(intent, portfolio=portfolio, mode=mode)

"""Broker adapter protocol: PaperBroker + RobinhoodMcpBroker stub."""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from platform.risk_governor import OrderIntent

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_LEDGER = _ROOT.parent / ".cache" / "platform" / "paper_ledger.json"


class NotConnected(RuntimeError):
    """Raised when live broker path is used without OAuth / agentic_live arming."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class WorkingOrder:
    order_id: str
    symbol: str
    side: str
    qty: float
    order_type: str
    limit_price: Optional[float]
    status: str  # working | filled | canceled | replaced
    strategy_id: Optional[str] = None
    created: str = ""
    updated: str = ""
    tag: str = ""


@dataclass
class OrderResult:
    ok: bool
    order: Optional[WorkingOrder] = None
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class BrokerAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def place_limit(
        self, intent: OrderIntent, *, replace_order_id: Optional[str] = None
    ) -> OrderResult: ...

    @abstractmethod
    def replace_limit(
        self, order_id: str, *, qty: Optional[float] = None, limit_price: Optional[float] = None
    ) -> OrderResult: ...

    @abstractmethod
    def cancel(self, order_id: str) -> OrderResult: ...

    @abstractmethod
    def list_open_orders(self) -> list[WorkingOrder]: ...

    def is_connected(self) -> bool:
        return False


class PaperBroker(BrokerAdapter):
    """Local ledger: set / replace / cancel simulated limit orders."""

    name = "paper"

    def __init__(self, ledger_path: Path | str | None = None):
        self.ledger_path = Path(ledger_path) if ledger_path else _DEFAULT_LEDGER
        self._ensure()

    def _ensure(self) -> dict[str, Any]:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            data = {"orders": {}, "events": []}
            self._write(data)
            return data
        return self._read()

    def _read(self) -> dict[str, Any]:
        with self.ledger_path.open() as f:
            return json.load(f)

    def _write(self, data: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("w") as f:
            json.dump(data, f, indent=2)

    def _event(self, data: dict[str, Any], kind: str, payload: dict[str, Any]) -> None:
        data.setdefault("events", []).append({"ts": _now(), "kind": kind, **payload})

    def is_connected(self) -> bool:
        return True

    def place_limit(
        self, intent: OrderIntent, *, replace_order_id: Optional[str] = None
    ) -> OrderResult:
        if (intent.order_type or "").lower() != "limit":
            return OrderResult(ok=False, message="PaperBroker only accepts limit in M0–M1")
        data = self._ensure()
        if replace_order_id:
            return self.replace_limit(
                replace_order_id, qty=intent.qty, limit_price=intent.limit_price
            )
        oid = f"paper_{uuid.uuid4().hex[:12]}"
        now = _now()
        order = WorkingOrder(
            order_id=oid,
            symbol=intent.symbol.upper(),
            side=intent.side.lower(),
            qty=float(intent.qty),
            order_type="limit",
            limit_price=float(intent.limit_price) if intent.limit_price is not None else None,
            status="working",
            strategy_id=intent.strategy_id,
            created=now,
            updated=now,
            tag=intent.tag,
        )
        data["orders"][oid] = asdict(order)
        self._event(data, "place", {"order_id": oid, "symbol": order.symbol})
        self._write(data)
        return OrderResult(ok=True, order=order, message="placed")

    def replace_limit(
        self, order_id: str, *, qty: Optional[float] = None, limit_price: Optional[float] = None
    ) -> OrderResult:
        data = self._ensure()
        raw = data["orders"].get(order_id)
        if not raw:
            return OrderResult(ok=False, message=f"unknown order {order_id}")
        if raw.get("status") not in ("working", "replaced"):
            return OrderResult(ok=False, message=f"cannot replace status={raw.get('status')}")
        if qty is not None:
            raw["qty"] = float(qty)
        if limit_price is not None:
            raw["limit_price"] = float(limit_price)
        raw["status"] = "working"
        raw["updated"] = _now()
        data["orders"][order_id] = raw
        self._event(data, "replace", {"order_id": order_id})
        self._write(data)
        return OrderResult(ok=True, order=WorkingOrder(**raw), message="replaced")

    def cancel(self, order_id: str) -> OrderResult:
        data = self._ensure()
        raw = data["orders"].get(order_id)
        if not raw:
            return OrderResult(ok=False, message=f"unknown order {order_id}")
        raw["status"] = "canceled"
        raw["updated"] = _now()
        data["orders"][order_id] = raw
        self._event(data, "cancel", {"order_id": order_id})
        self._write(data)
        return OrderResult(ok=True, order=WorkingOrder(**raw), message="canceled")

    def list_open_orders(self) -> list[WorkingOrder]:
        data = self._ensure()
        out = []
        for raw in data.get("orders", {}).values():
            if raw.get("status") == "working":
                out.append(WorkingOrder(**raw))
        return out

    def simulate_fill(self, order_id: str) -> OrderResult:
        """Test helper: mark working order filled."""
        data = self._ensure()
        raw = data["orders"].get(order_id)
        if not raw:
            return OrderResult(ok=False, message=f"unknown order {order_id}")
        raw["status"] = "filled"
        raw["updated"] = _now()
        data["orders"][order_id] = raw
        self._event(data, "fill", {"order_id": order_id})
        self._write(data)
        return OrderResult(ok=True, order=WorkingOrder(**raw), message="filled")


class RobinhoodMcpBroker(BrokerAdapter):
    """Stub only. Raises NotConnected until Stage1 OAuth + agentic_live."""

    name = "robinhood_mcp"

    def __init__(self, *, connected: bool = False, mode: str = "research"):
        self._connected = connected
        self._mode = mode

    def is_connected(self) -> bool:
        return bool(self._connected) and self._mode == "agentic_live"

    def _guard(self) -> None:
        if self._mode != "agentic_live":
            raise NotConnected(
                "RobinhoodMcpBroker requires mode=agentic_live "
                "(see docs/AGENTIC_AUTONOMY_POLICY.md)"
            )
        if not self._connected:
            raise NotConnected(
                "Robinhood MCP not connected — Stage1 OAuth required on Ken's Mac. "
                "Do not place live orders from this stub."
            )

    def place_limit(
        self, intent: OrderIntent, *, replace_order_id: Optional[str] = None
    ) -> OrderResult:
        self._guard()
        raise NotImplementedError("live place_limit not implemented until Stage1 MCP wiring")

    def replace_limit(
        self, order_id: str, *, qty: Optional[float] = None, limit_price: Optional[float] = None
    ) -> OrderResult:
        self._guard()
        raise NotImplementedError("live replace_limit not implemented until Stage1 MCP wiring")

    def cancel(self, order_id: str) -> OrderResult:
        self._guard()
        raise NotImplementedError("live cancel not implemented until Stage1 MCP wiring")

    def list_open_orders(self) -> list[WorkingOrder]:
        self._guard()
        raise NotImplementedError("live list_open_orders not implemented until Stage1 MCP wiring")


def get_broker(mode: str, *, rh_connected: bool = False) -> BrokerAdapter:
    if mode == "agentic_live":
        return RobinhoodMcpBroker(connected=rh_connected, mode=mode)
    # research / paper / shadow → paper ledger (shadow does not mutate in autonomy_loop)
    return PaperBroker()

"""Broker adapter protocol: PaperBroker + RobinhoodMcpBroker (Stage2 read-only wire)."""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trader_platform.risk_governor import OrderIntent, PortfolioSnapshot
from trader_platform.rh_snapshot import (
    DEFAULT_SNAPSHOT_PATH,
    AccountView,
    RhSnapshot,
    try_load_snapshot,
)

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_LEDGER = _ROOT.parent / ".cache" / "platform" / "paper_ledger.json"


class NotConnected(RuntimeError):
    """Raised when live broker path is used without OAuth / agentic_live arming."""


class LiveOrdersBlocked(RuntimeError):
    """Raised when place/replace/cancel attempted without Stage1 arming."""


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
    structure: str = ""
    legs: Optional[list[dict[str, Any]]] = None
    max_loss_usd: Optional[float] = None
    width: Optional[float] = None
    net_credit: Optional[float] = None
    short_strike: Optional[float] = None
    long_strike: Optional[float] = None
    expiration: Optional[str] = None
    dte: Optional[int] = None


def _working_order_from_raw(raw: dict[str, Any]) -> WorkingOrder:
    """Load WorkingOrder, ignoring unknown legacy keys."""
    fields = set(WorkingOrder.__dataclass_fields__.keys())
    cleaned = {k: v for k, v in raw.items() if k in fields}
    return WorkingOrder(**cleaned)


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

    # --- Stage2 read-only surface (optional; default empty) ---
    def has_readonly_snapshot(self) -> bool:
        return False

    def get_rh_snapshot(self) -> Optional[RhSnapshot]:
        return None

    def list_account_views(self) -> list[AccountView]:
        snap = self.get_rh_snapshot()
        return list(snap.accounts) if snap else []

    def portfolio_snapshot(self) -> PortfolioSnapshot:
        snap = self.get_rh_snapshot()
        if snap:
            return snap.portfolio_for_risk(prefer_agentic=True)
        return PortfolioSnapshot()


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
        from trader_platform.execution.paper_book_guards import refuse_paper_place

        refuse = refuse_paper_place(
            symbol=str(intent.symbol or ""),
            working=self.list_open_orders(),
        )
        if refuse:
            return OrderResult(ok=False, message=refuse)
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
            structure=str(getattr(intent, "structure", "") or ""),
            legs=list(intent.legs) if getattr(intent, "legs", None) else None,
            max_loss_usd=(
                float(intent.max_loss_usd)
                if getattr(intent, "max_loss_usd", None) is not None
                else None
            ),
            width=float(intent.width) if getattr(intent, "width", None) is not None else None,
            net_credit=(
                float(intent.net_credit)
                if getattr(intent, "net_credit", None) is not None
                else None
            ),
            short_strike=(
                float(intent.short_strike)
                if getattr(intent, "short_strike", None) is not None
                else None
            ),
            long_strike=(
                float(intent.long_strike)
                if getattr(intent, "long_strike", None) is not None
                else None
            ),
            expiration=(
                str(intent.expiration)
                if getattr(intent, "expiration", None) is not None
                else None
            ),
            dte=int(intent.dte) if getattr(intent, "dte", None) is not None else None,
        )
        data["orders"][oid] = asdict(order)
        self._event(
            data,
            "place",
            {
                "order_id": oid,
                "symbol": order.symbol,
                "structure": order.structure or None,
                "max_loss_usd": order.max_loss_usd,
                "tag": order.tag,
            },
        )
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
        return OrderResult(ok=True, order=_working_order_from_raw(raw), message="replaced")

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
        return OrderResult(ok=True, order=_working_order_from_raw(raw), message="canceled")

    def close(
        self,
        order_id: str,
        *,
        reason: str,
        mark: dict[str, Any] | None = None,
    ) -> OrderResult:
        """Mark a working paper order closed (PT / stop / DTE / regime)."""
        data = self._ensure()
        raw = data["orders"].get(order_id)
        if not raw:
            return OrderResult(ok=False, message=f"unknown order {order_id}")
        if raw.get("status") not in ("working", "filled", "replaced"):
            return OrderResult(ok=False, message=f"cannot close status={raw.get('status')}")
        raw["status"] = "closed"
        raw["updated"] = _now()
        raw["close_reason"] = str(reason)
        if mark:
            raw["mark"] = mark
        data["orders"][order_id] = raw
        self._event(
            data,
            "close",
            {"order_id": order_id, "reason": reason, "symbol": raw.get("symbol")},
        )
        self._write(data)
        return OrderResult(ok=True, order=_working_order_from_raw(raw), message=f"closed:{reason}")

    def list_open_orders(self) -> list[WorkingOrder]:
        data = self._ensure()
        out = []
        for raw in data.get("orders", {}).values():
            if raw.get("status") == "working":
                out.append(_working_order_from_raw(raw))
        return out

    def portfolio_snapshot(self) -> PortfolioSnapshot:
        """Open risk from real paper orders only; smoke stubs are not sleeve risk."""
        from trader_platform.paper_filters import is_smoke_stub_tag, risk_contribution_usd

        open_orders = self.list_open_orders()
        risk = 0.0
        real_count = 0
        for o in open_orders:
            if is_smoke_stub_tag(o.tag):
                continue
            real_count += 1
            premium = 0.0
            if o.limit_price is not None:
                premium = abs(float(o.qty) * float(o.limit_price) * 100.0)
            risk += risk_contribution_usd(
                max_loss_usd=o.max_loss_usd,
                notional=premium,
                qty=o.qty,
            )
        return PortfolioSnapshot(
            open_risk=round(risk, 2),
            open_order_count=real_count,
            daily_pnl=0.0,
        )

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
        return OrderResult(ok=True, order=_working_order_from_raw(raw), message="filled")


@dataclass
class RhReviewPayload:
    """Payload a trader Hermes session would pass to review_* MCP tools (not place_*)."""

    tool: str  # review_equity_order | review_option_order
    args: dict[str, Any]
    kind: str = "equity"  # equity | option
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "kind": self.kind,
            "args": dict(self.args),
            "note": self.note,
            "places": False,
            "mcp_invoke": "trader_session_only",
        }


def build_review_equity_order(
    intent: OrderIntent,
    *,
    account_number: Optional[str] = None,
    time_in_force: str = "gfd",
    extended_hours: bool = False,
) -> RhReviewPayload:
    """Build review_equity_order args from an OrderIntent (simulation only).

    Exact RH MCP field names can differ slightly; trader session should validate
    against live tool schema before any agentic_live arming. Never maps to place_*.
    """
    args: dict[str, Any] = {
        "symbol": intent.symbol.upper(),
        "side": intent.side.lower(),
        "quantity": float(intent.qty),
        "order_type": (intent.order_type or "limit").lower(),
        "time_in_force": time_in_force,
        "extended_hours": bool(extended_hours),
        "strategy_id": intent.strategy_id,
        "tag": intent.tag,
        "estimated_notional": intent.estimated_notional(),
    }
    if intent.limit_price is not None:
        args["limit_price"] = float(intent.limit_price)
    if account_number:
        # Prefer last4-only in logs; full account_number only when caller supplies it.
        args["account_number"] = account_number
    return RhReviewPayload(
        tool="review_equity_order",
        kind="equity",
        args=args,
        note="simulate only; never place_equity_order from platform loop",
    )


def build_review_option_order(
    intent: OrderIntent,
    *,
    option_symbol: Optional[str] = None,
    legs: Optional[list[dict[str, Any]]] = None,
    account_number: Optional[str] = None,
    time_in_force: str = "gfd",
) -> RhReviewPayload:
    """Build review_option_order args. Legs/option_symbol filled by M2 signal path."""
    args: dict[str, Any] = {
        "underlying": intent.symbol.upper(),
        "side": intent.side.lower(),
        "quantity": float(intent.qty),
        "order_type": (intent.order_type or "limit").lower(),
        "time_in_force": time_in_force,
        "strategy_id": intent.strategy_id,
        "tag": intent.tag,
        "estimated_notional": intent.estimated_notional(),
        "multiplier": float(intent.multiplier),
    }
    if intent.limit_price is not None:
        args["limit_price"] = float(intent.limit_price)
    if option_symbol:
        args["option_symbol"] = option_symbol
    if legs:
        args["legs"] = legs
    if account_number:
        args["account_number"] = account_number
    return RhReviewPayload(
        tool="review_option_order",
        kind="option",
        args=args,
        note="simulate only; never place_option_order from platform loop",
    )


class RhMcpReadAdapter:
    """Read/review surface for RH MCP — no place_*/cancel_*/fund.

    Integration: Hermes profile `trader` owns OAuth tokens and tool dispatch.
    Bare Python in this repo does NOT open the MCP session (discover_mcp_tools
    under HERMES_HOME alone is not a stable client API). Call sites:

    1. autonomy_loop --mode shadow | --dry-review → build RhReviewPayload, audit JSON
    2. trader Hermes session → call MCP tool named in payload.tool with payload.args
    3. place_* only after agentic_live + agentic.enabled + rh_connected (still NotImplemented)

    Optional `mcp_call` injects a callable(tool_name, args) -> Any for tests.
    """

    name = "rh_mcp_read"

    READ_TOOLS = (
        "get_accounts",
        "get_portfolio",
        "get_equity_quotes",
        "get_equity_positions",
        "get_option_positions",
        "get_option_quotes",
        "review_equity_order",
        "review_option_order",
    )
    FORBIDDEN_TOOLS = (
        "place_equity_order",
        "place_option_order",
        "cancel_equity_order",
        "cancel_option_order",
    )

    def __init__(
        self,
        *,
        connected: bool = False,
        account_number: Optional[str] = None,
        mcp_call: Optional[Any] = None,
    ):
        self._connected = connected
        self.account_number = account_number
        self._mcp_call = mcp_call  # optional inject; default None → payload only

    def is_connected(self) -> bool:
        return bool(self._connected)

    def build_review_from_intent(
        self,
        intent: OrderIntent,
        *,
        instrument: str = "option",
        option_symbol: Optional[str] = None,
        legs: Optional[list[dict[str, Any]]] = None,
    ) -> RhReviewPayload:
        if instrument == "equity":
            return build_review_equity_order(intent, account_number=self.account_number)
        return build_review_option_order(
            intent,
            option_symbol=option_symbol,
            legs=legs,
            account_number=self.account_number,
        )

    def review_equity_order(self, intent: OrderIntent) -> dict[str, Any]:
        """Return payload; optionally invoke review_equity_order if mcp_call injected."""
        payload = build_review_equity_order(intent, account_number=self.account_number)
        return self._maybe_invoke(payload)

    def review_option_order(
        self,
        intent: OrderIntent,
        *,
        option_symbol: Optional[str] = None,
        legs: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        payload = build_review_option_order(
            intent,
            option_symbol=option_symbol,
            legs=legs,
            account_number=self.account_number,
        )
        return self._maybe_invoke(payload)

    def _maybe_invoke(self, payload: RhReviewPayload) -> dict[str, Any]:
        out = payload.as_dict()
        if self._mcp_call is None:
            out["invoked"] = False
            out["reason"] = (
                "MCP not invocable from bare platform Python; "
                "pass to hermes -p trader session or inject mcp_call= for tests"
            )
            return out
        if payload.tool in self.FORBIDDEN_TOOLS:
            raise RuntimeError(f"refusing forbidden tool {payload.tool}")
        result = self._mcp_call(payload.tool, payload.args)
        out["invoked"] = True
        out["result"] = result
        return out


class RobinhoodMcpBroker(BrokerAdapter):
    """RH MCP broker: review payloads + fail-closed place until agentic_live armed.

    Stage2 read-only: local snapshot file (see platform/rh_snapshot.py) and
    RhMcpReadAdapter review_* payloads. Place path requires mode=agentic_live
    AND connected AND agentic_enabled — still NotImplemented for real place_*.
    """

    name = "robinhood_mcp"

    def __init__(
        self,
        *,
        connected: bool = False,
        mode: str = "research",
        agentic_enabled: bool = False,
        account_number: Optional[str] = None,
        mcp_call: Optional[Any] = None,
        snapshot_path: Path | str | None = None,
    ):
        self._connected = connected
        self._mode = mode
        self._agentic_enabled = agentic_enabled
        self.snapshot_path = Path(snapshot_path) if snapshot_path else DEFAULT_SNAPSHOT_PATH
        self.read = RhMcpReadAdapter(
            connected=connected, account_number=account_number, mcp_call=mcp_call
        )

    def is_connected(self) -> bool:
        return bool(self._connected) and self._mode == "agentic_live" and self._agentic_enabled

    def has_readonly_snapshot(self) -> bool:
        return self.snapshot_path.exists()

    def get_rh_snapshot(self) -> Optional[RhSnapshot]:
        return try_load_snapshot(self.snapshot_path)

    def _guard(self) -> None:
        if self._mode != "agentic_live":
            raise NotConnected(
                "RobinhoodMcpBroker requires mode=agentic_live "
                "(see docs/AGENTIC_AUTONOMY_POLICY.md)"
            )
        if not self._agentic_enabled:
            raise NotConnected(
                "agentic.enabled is false; refuse live place/replace/cancel "
                "(see platform/risk_limits.yaml)"
            )
        if not self._connected:
            raise NotConnected(
                "Robinhood MCP not connected — Stage1 OAuth required on Ken's Mac. "
                "Do not place live orders from this stub."
            )

    def review_equity_order(self, intent: OrderIntent) -> dict[str, Any]:
        return self.read.review_equity_order(intent)

    def review_option_order(
        self,
        intent: OrderIntent,
        *,
        option_symbol: Optional[str] = None,
        legs: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        return self.read.review_option_order(
            intent, option_symbol=option_symbol, legs=legs
        )

    def place_limit(
        self, intent: OrderIntent, *, replace_order_id: Optional[str] = None
    ) -> OrderResult:
        self._guard()
        raise LiveOrdersBlocked(
            "live place_limit not implemented — Stage2 wires review_* only; "
            "place_* requires separate arming task after paper/shadow evidence"
        )

    def replace_limit(
        self, order_id: str, *, qty: Optional[float] = None, limit_price: Optional[float] = None
    ) -> OrderResult:
        self._guard()
        raise LiveOrdersBlocked("live replace_limit not implemented until place_* wiring")

    def cancel(self, order_id: str) -> OrderResult:
        self._guard()
        raise LiveOrdersBlocked("live cancel not implemented until place_* wiring")

    def list_open_orders(self) -> list[WorkingOrder]:
        # Stage2: open-order counts live on snapshot; no live order book yet
        if self.has_readonly_snapshot():
            return []
        self._guard()
        raise LiveOrdersBlocked("live list_open_orders not implemented until place_* wiring")


class PaperRhBridge(BrokerAdapter):
    """Paper→RH wire: paper ledger for mutations; RH snapshot for portfolio/readiness.

    Default Stage2 broker for paper/shadow ticks that should respect real
    agentic-account readiness without enabling live place.
    """

    name = "paper_rh_bridge"

    def __init__(
        self,
        *,
        ledger_path: Path | str | None = None,
        snapshot_path: Path | str | None = None,
        account_number: Optional[str] = None,
    ):
        self.paper = PaperBroker(ledger_path)
        self.rh = RobinhoodMcpBroker(
            connected=False,
            mode="paper",
            agentic_enabled=False,
            account_number=account_number,
            snapshot_path=snapshot_path or DEFAULT_SNAPSHOT_PATH,
        )

    def is_connected(self) -> bool:
        return True

    def has_readonly_snapshot(self) -> bool:
        return self.rh.has_readonly_snapshot()

    def get_rh_snapshot(self) -> Optional[RhSnapshot]:
        return self.rh.get_rh_snapshot()

    def place_limit(
        self, intent: OrderIntent, *, replace_order_id: Optional[str] = None
    ) -> OrderResult:
        return self.paper.place_limit(intent, replace_order_id=replace_order_id)

    def replace_limit(
        self, order_id: str, *, qty: Optional[float] = None, limit_price: Optional[float] = None
    ) -> OrderResult:
        return self.paper.replace_limit(order_id, qty=qty, limit_price=limit_price)

    def cancel(self, order_id: str) -> OrderResult:
        return self.paper.cancel(order_id)

    def list_open_orders(self) -> list[WorkingOrder]:
        return self.paper.list_open_orders()

    def portfolio_snapshot(self) -> PortfolioSnapshot:
        paper_port = self.paper.portfolio_snapshot()
        snap = self.get_rh_snapshot()
        if snap:
            port = snap.portfolio_for_risk(prefer_agentic=True)
            port.open_order_count = max(port.open_order_count, paper_port.open_order_count)
            # Paper defined-risk max_loss is real sleeve open risk until live funded path.
            port.open_risk = float(port.open_risk or 0.0) + float(paper_port.open_risk or 0.0)
            return port
        return paper_port

    def review_equity_order(self, intent: OrderIntent) -> dict[str, Any]:
        return self.rh.review_equity_order(intent)

    def review_option_order(
        self,
        intent: OrderIntent,
        *,
        option_symbol: Optional[str] = None,
        legs: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        return self.rh.review_option_order(
            intent, option_symbol=option_symbol, legs=legs
        )


def get_broker(
    mode: str,
    *,
    rh_connected: bool = False,
    agentic_enabled: bool = False,
    account_number: Optional[str] = None,
    use_rh_bridge: bool = True,
    snapshot_path: Path | str | None = None,
) -> BrokerAdapter:
    if mode == "agentic_live":
        return RobinhoodMcpBroker(
            connected=rh_connected,
            mode=mode,
            agentic_enabled=agentic_enabled,
            account_number=account_number,
            snapshot_path=snapshot_path,
        )
    # research / paper / shadow → paper ledger; Stage2 bridge attaches RH snapshot when present
    if use_rh_bridge:
        return PaperRhBridge(
            snapshot_path=snapshot_path,
            account_number=account_number,
        )
    return PaperBroker()

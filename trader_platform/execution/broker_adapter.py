"""Broker adapter protocol: PaperBroker + RobinhoodMcpBroker (Stage2 read-only wire)."""

from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_OPTION_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_AGENTIC_LAST4 = "8507"

from trader_platform.risk_governor import OrderIntent, PortfolioSnapshot
from trader_platform.rh_snapshot import (
    DEFAULT_SNAPSHOT_PATH,
    AccountView,
    RhSnapshot,
    mask_account,
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
    3. place_* only after agentic_live + agentic.enabled + rh_connected + mcp_call

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


def _num_str(value: Any) -> str:
    f = float(value)
    if f != f or f <= 0 or f == float("inf"):
        raise ValueError("numeric MCP field must be positive")
    text = f"{f:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _refuse_live_intent(intent: OrderIntent) -> Optional[str]:
    otype = (intent.order_type or "").lower()
    if otype != "limit":
        return "only limit orders allowed"
    if intent.limit_price is None:
        return "limit order requires limit_price"
    try:
        if float(intent.limit_price) <= 0:
            return "limit_price must be positive"
    except (TypeError, ValueError):
        return "limit_price must be positive"
    try:
        qty = float(intent.qty)
    except (TypeError, ValueError):
        return "qty must be 1"
    if abs(qty - 1.0) > 1e-9:
        return "qty must be 1"
    return None


def _mcp_order_args(
    intent: OrderIntent, *, account: str, legs: list[dict[str, Any]]
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "account_number": account,
        "legs": legs,
        "quantity": "1",
        "type": "limit",
        "price": _num_str(intent.limit_price),
        "time_in_force": "gfd",
    }
    if len(legs) >= 2:
        if getattr(intent, "net_credit", None) is not None and float(intent.net_credit) > 0:
            args["direction"] = "credit"
        else:
            sells = sum(1 for leg in legs if str(leg.get("side") or "").lower() == "sell")
            buys = sum(1 for leg in legs if str(leg.get("side") or "").lower() == "buy")
            args["direction"] = "credit" if sells >= buys else "debit"
    return args


def _mcp_hard_reject(result: Any) -> bool:
    if result is None:
        return True
    if isinstance(result, str):
        low = result.lower()
        return any(token in low for token in ("error", "reject", "denied", "fail"))
    if not isinstance(result, dict):
        return False
    if result.get("error") or result.get("isError") or result.get("is_error"):
        return True
    if result.get("rejected") is True:
        return True
    if result.get("ok") is False:
        return True
    state = str(result.get("state") or result.get("status") or "").lower()
    if state in {"rejected", "failed", "error", "denied"}:
        return True
    data = result.get("data")
    if isinstance(data, dict):
        if data.get("error") or data.get("rejected") or data.get("ok") is False:
            return True
    return False


def _safe_mcp_payload(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            low = str(key).lower()
            compact = low.replace("_", "")
            if "token" in low or "secret" in low or "authorization" in low:
                out[key] = "[redacted]"
            elif "accountnumber" in compact or low in {"account_number", "accountnumber"}:
                out[key] = mask_account(str(value) if value is not None else "")
            else:
                out[key] = _safe_mcp_payload(value)
        return out
    if isinstance(obj, list):
        return [_safe_mcp_payload(item) for item in obj]
    return obj


def _extract_order_id(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    for key in ("id", "order_id", "orderId"):
        val = result.get(key)
        if val:
            return str(val)
    for nest in ("order", "data", "result"):
        inner = result.get(nest)
        if isinstance(inner, dict):
            found = _extract_order_id(inner)
            if found:
                return found
    orders = result.get("orders")
    if isinstance(orders, list) and orders:
        return _extract_order_id(orders[0])
    return ""


def _iter_instruments(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []
    for key in ("results", "instruments", "option_instruments", "data"):
        val = raw.get(key)
        if isinstance(val, list):
            return [item for item in val if isinstance(item, dict)]
        if isinstance(val, dict):
            nested = _iter_instruments(val)
            if nested:
                return nested
    if raw.get("id") or raw.get("option_id"):
        return [raw]
    return []


def _extract_option_id(raw: Any, *, strike: Any, right: str) -> str:
    items = _iter_instruments(raw)
    want_right = (right or "put").lower()
    try:
        want_strike = float(strike)
    except (TypeError, ValueError):
        want_strike = None
    for item in items:
        option_id = str(item.get("id") or item.get("option_id") or item.get("instrument_id") or "")
        if not _OPTION_UUID_RE.match(option_id):
            continue
        typ = str(item.get("type") or item.get("option_type") or item.get("right") or "").lower()
        if typ and typ != want_right:
            continue
        if want_strike is not None:
            raw_strike = item.get("strike_price")
            if raw_strike is None:
                raw_strike = item.get("strike")
            if raw_strike is not None:
                try:
                    if abs(float(raw_strike) - want_strike) > 1e-6:
                        continue
                except (TypeError, ValueError):
                    pass
        return option_id
    for item in items:
        option_id = str(item.get("id") or item.get("option_id") or item.get("instrument_id") or "")
        if _OPTION_UUID_RE.match(option_id):
            return option_id
    return ""


class RobinhoodMcpBroker(BrokerAdapter):
    """RH MCP broker: review payloads + fail-closed place unless mcp_call is injected.

    Place/cancel require mode=agentic_live AND connected AND agentic_enabled
    AND an injected ``mcp_call``. Without mcp_call this still raises
    LiveOrdersBlocked (smoke + unarmed Hermes). replace_limit stays blocked.
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
        self.account_number = account_number
        self._mcp_call = mcp_call
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

    def _resolve_agentic_account(self) -> str:
        from trader_platform.execution.rh_mcp_client import resolve_agentic_account_number

        if self.account_number:
            provided = str(self.account_number).strip()
            digits = re.sub(r"\D", "", provided)
            last4 = (digits or provided)[-4:]
            if last4 != _AGENTIC_LAST4:
                raise NotConnected(
                    "refusing non-Agentic last4 — only sleeve ••••8507 is allowed"
                )
        return resolve_agentic_account_number(mcp_call=self._mcp_call)

    def place_limit(
        self, intent: OrderIntent, *, replace_order_id: Optional[str] = None
    ) -> OrderResult:
        self._guard()
        if self._mcp_call is None:
            raise LiveOrdersBlocked(
                "live place_limit blocked — no mcp_call injected "
                "(Hermes/cron must pass rh_mcp_client.call_tool when armed)"
            )
        if replace_order_id:
            raise LiveOrdersBlocked(
                "live replace_limit not implemented this slice (cancel+place later)"
            )
        blocked = _refuse_live_intent(intent)
        if blocked:
            return OrderResult(ok=False, message=blocked)
        try:
            account = self._resolve_agentic_account()
            legs = self._mcp_legs(intent)
            place_args = _mcp_order_args(intent, account=account, legs=legs)
            review_args = dict(place_args)
            if intent.symbol:
                review_args["chain_symbol"] = intent.symbol.upper()
                review_args["underlying_type"] = "equity"
            try:
                review = self._mcp_call("review_option_order", review_args)
            except Exception:  # noqa: BLE001 — never leak raw MCP/account text
                return OrderResult(ok=False, message="review failed")
            if _mcp_hard_reject(review):
                return OrderResult(
                    ok=False,
                    message="review rejected",
                    raw=_safe_mcp_payload(review),
                )
            placed = self._mcp_call("place_option_order", place_args)
            if _mcp_hard_reject(placed):
                return OrderResult(
                    ok=False,
                    message="place rejected",
                    raw=_safe_mcp_payload(placed),
                )
            oid = _extract_order_id(placed) or f"rh_{uuid.uuid4().hex[:12]}"
            now = _now()
            order = WorkingOrder(
                order_id=oid,
                symbol=(intent.symbol or "").upper(),
                side=(intent.side or "").lower(),
                qty=1.0,
                order_type="limit",
                limit_price=float(intent.limit_price) if intent.limit_price is not None else None,
                status="working",
                strategy_id=intent.strategy_id,
                created=now,
                updated=now,
                tag=intent.tag,
                structure=str(getattr(intent, "structure", "") or ""),
                legs=list(place_args["legs"]),
                max_loss_usd=(
                    float(intent.max_loss_usd)
                    if getattr(intent, "max_loss_usd", None) is not None
                    else None
                ),
                short_strike=(
                    float(intent.short_strike)
                    if getattr(intent, "short_strike", None) is not None
                    else None
                ),
                expiration=(
                    str(intent.expiration)
                    if getattr(intent, "expiration", None) is not None
                    else None
                ),
            )
            return OrderResult(
                ok=True,
                order=order,
                message="placed",
                raw=_safe_mcp_payload(placed),
            )
        except NotConnected:
            raise
        except LiveOrdersBlocked:
            raise
        except Exception as exc:  # noqa: BLE001
            return OrderResult(ok=False, message=f"place failed: {type(exc).__name__}")

    def _mcp_legs(self, intent: OrderIntent) -> list[dict[str, Any]]:
        raw_legs = list(getattr(intent, "legs", None) or [])
        if raw_legs:
            out: list[dict[str, Any]] = []
            for raw in raw_legs:
                if not isinstance(raw, dict):
                    raise ValueError("each intent.leg must be a mapping")
                option_id = str(raw.get("option_id") or raw.get("id") or "").strip()
                if not _OPTION_UUID_RE.match(option_id):
                    option_id = self._resolve_option_id(
                        symbol=intent.symbol,
                        expiration=str(
                            raw.get("expiration") or raw.get("expiration_date") or intent.expiration or ""
                        ),
                        strike=raw.get("strike") or raw.get("strike_price") or intent.short_strike,
                        right=str(
                            raw.get("right")
                            or raw.get("type")
                            or raw.get("option_right")
                            or intent.option_right
                            or "put"
                        ),
                    )
                side = str(raw.get("side") or raw.get("action") or intent.side or "").lower()
                effect = str(raw.get("position_effect") or "open").lower()
                if side not in ("buy", "sell") or effect not in ("open", "close"):
                    raise ValueError("leg requires side buy|sell and position_effect open|close")
                leg: dict[str, Any] = {
                    "option_id": option_id,
                    "side": side,
                    "position_effect": effect,
                }
                if raw.get("ratio_quantity") is not None:
                    leg["ratio_quantity"] = int(raw["ratio_quantity"])
                elif len(raw_legs) == 1:
                    leg["ratio_quantity"] = 1
                out.append(leg)
            return out
        expiration = str(getattr(intent, "expiration", None) or "").strip()
        strike = getattr(intent, "short_strike", None)
        right = str(getattr(intent, "option_right", None) or "put").lower() or "put"
        if not expiration or strike is None:
            raise ValueError(
                "need intent.legs or CSP fields (expiration + short_strike, option_right=put)"
            )
        option_id = self._resolve_option_id(
            symbol=intent.symbol,
            expiration=expiration,
            strike=strike,
            right=right,
        )
        return [
            {
                "option_id": option_id,
                "side": (intent.side or "sell").lower(),
                "position_effect": "open",
                "ratio_quantity": 1,
            }
        ]

    def _resolve_option_id(
        self,
        *,
        symbol: str,
        expiration: str,
        strike: Any,
        right: str,
    ) -> str:
        if self._mcp_call is None:
            raise LiveOrdersBlocked("no mcp_call to resolve option_id")
        if not symbol or not expiration or strike is None:
            raise ValueError("get_option_instruments needs symbol, expiration, strike")
        args: dict[str, Any] = {
            "symbol": str(symbol).upper(),
            "expiration_dates": str(expiration),
            "type": str(right or "put").lower(),
            "strike_price": _num_str(strike),
        }
        raw = self._mcp_call("get_option_instruments", args)
        option_id = _extract_option_id(raw, strike=strike, right=right)
        if not option_id:
            raise ValueError("get_option_instruments returned no matching option_id")
        return option_id

    def replace_limit(
        self, order_id: str, *, qty: Optional[float] = None, limit_price: Optional[float] = None
    ) -> OrderResult:
        self._guard()
        raise LiveOrdersBlocked("live replace_limit not implemented this slice (cancel+place later)")

    def cancel(self, order_id: str) -> OrderResult:
        self._guard()
        if self._mcp_call is None or not order_id:
            raise LiveOrdersBlocked(
                "live cancel blocked — no mcp_call injected or missing order_id"
            )
        try:
            account = self._resolve_agentic_account()
            result = self._mcp_call(
                "cancel_option_order",
                {"account_number": account, "order_id": str(order_id)},
            )
        except NotConnected:
            raise
        except Exception:  # noqa: BLE001
            return OrderResult(ok=False, message="cancel failed")
        if _mcp_hard_reject(result):
            return OrderResult(
                ok=False,
                message="cancel rejected",
                raw=_safe_mcp_payload(result),
            )
        now = _now()
        order = WorkingOrder(
            order_id=str(order_id),
            symbol="",
            side="",
            qty=0.0,
            order_type="limit",
            limit_price=None,
            status="canceled",
            created=now,
            updated=now,
        )
        return OrderResult(
            ok=True,
            order=order,
            message="canceled",
            raw=_safe_mcp_payload(result),
        )

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
    mcp_call: Optional[Any] = None,
) -> BrokerAdapter:
    if mode == "agentic_live":
        return RobinhoodMcpBroker(
            connected=rh_connected,
            mode=mode,
            agentic_enabled=agentic_enabled,
            account_number=account_number,
            snapshot_path=snapshot_path,
            mcp_call=mcp_call,
        )
    # research / paper / shadow → paper ledger; Stage2 bridge attaches RH snapshot when present
    if use_rh_bridge:
        return PaperRhBridge(
            snapshot_path=snapshot_path,
            account_number=account_number,
        )
    return PaperBroker()

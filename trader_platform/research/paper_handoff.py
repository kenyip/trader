"""Desk B paper handoff: enrich PAPER_PACKET_READY → risk check → optional paper place.

Never live. F2 seats may dry-run; only paper_eligible seats may mutate paper ledger
when execute_paper=True.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import pandas as pd

from trader_platform.execution.broker_adapter import PaperBroker, get_broker
from trader_platform.research.living_registry import LivingRegistry, load_living_registry
from trader_platform.research.opportunity_watcher import WatchResult, watch_once
from trader_platform.research.pcs_sim import pick_structure_entry
from trader_platform.research.strategy_spec import StrategySpec, load_strategy_spec
from trader_platform.risk_governor import OrderIntent, PortfolioSnapshot, RiskGovernor

try:
    from data import build as build_market_frame
except Exception:  # pragma: no cover
    build_market_frame = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parents[2]
_HANDOFF_AUDIT = _REPO / ".cache" / "platform" / "paper_handoff.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _audit(event: str, payload: dict[str, Any]) -> None:
    _HANDOFF_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with _HANDOFF_AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "event": event, **payload}, default=str) + "\n")


@dataclass
class PaperHandoffResult:
    status: str
    trading_authority: bool = False
    live_authority: bool = False
    watch_status: str = ""
    reason: str = ""
    intent: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    paper_action: str = "none"
    paper_order_id: str = ""
    packet: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_spec(path: str) -> StrategySpec | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return load_strategy_spec(p)


def intent_from_watch(
    watch: WatchResult,
    *,
    registry: LivingRegistry | None = None,
    registry_path: str | Path | None = None,
) -> tuple[Optional[OrderIntent], str, dict[str, Any]]:
    """Build a defined-risk OrderIntent from a PAPER_PACKET_READY watch result."""
    if watch.status not in {"PAPER_PACKET_READY", "GATED_LIVE_PACKET"}:
        return None, f"watch_status={watch.status} is not paper-ready", {}

    reg = registry if registry is not None else load_living_registry(registry_path)
    seat = reg.get(watch.seat_id) if watch.seat_id else None
    if seat is None:
        return None, "living seat not found for watch result", {}

    symbol = str(watch.symbol or "").upper()
    structure = str(watch.selected_structure or "").strip().lower()
    if not symbol or not structure:
        return None, "watch missing symbol or structure", {}

    if build_market_frame is None:
        return None, "data.build unavailable", {}

    frame = build_market_frame(symbol, period="3mo", use_cache=True)
    if frame is None or len(frame) < 5:
        return None, f"insufficient market data for {symbol}", {}
    row = frame.iloc[-1]
    today = pd.Timestamp(str(frame.index[-1]))
    spot = float(row.get("close") or 0.0)
    if spot <= 0:
        return None, "invalid spot", {}

    spec = _load_spec(seat.spec_path)
    if spec is None:
        # Minimal fallback config for defined-risk verticals.
        cfg: dict[str, Any] = {
            "structure": structure,
            "long_dte": 21,
            "long_target_delta": 0.20,
            "spread_width": 1.0,
            "min_credit_pct": 0.08,
            "profit_target": 0.50,
            "max_loss_budget_usd": 300.0,
            "bear_dte": 0,
        }
    else:
        cfg = spec.sim_config_for_structure(structure)

    trade = pick_structure_entry(row, spot, today, cfg, structure=structure)
    if trade is None:
        return None, "pick_structure_entry returned None (filters/credit/max-loss)", {"cfg": cfg}

    max_loss_usd = float(trade.max_loss_per_share) * 100.0
    legs: list[dict[str, Any]] = []
    if trade.right == "iron_condor":
        legs = [
            {
                "right": "put",
                "action": "sell",
                "strike": trade.short_strike,
                "qty": 1,
            },
            {
                "right": "put",
                "action": "buy",
                "strike": trade.long_strike,
                "qty": 1,
            },
            {
                "right": "call",
                "action": "sell",
                "strike": trade.call_short_strike,
                "qty": 1,
            },
            {
                "right": "call",
                "action": "buy",
                "strike": trade.call_long_strike,
                "qty": 1,
            },
        ]
    else:
        right = "put" if trade.right == "put" else "call"
        legs = [
            {"right": right, "action": "sell", "strike": trade.short_strike, "qty": 1},
            {"right": right, "action": "buy", "strike": trade.long_strike, "qty": 1},
        ]

    intent = OrderIntent(
        symbol=symbol,
        side="sell",
        qty=1.0,
        order_type="limit",
        limit_price=float(trade.net_credit),
        strategy_id=seat.candidate_id,
        multiplier=100.0,
        tag=(
            f"spine:{seat.seat_id}|{structure}|w={trade.width}|"
            f"Ks={trade.short_strike}|Kl={trade.long_strike}|ml={max_loss_usd:.2f}"
        ),
        max_loss_usd=max_loss_usd,
        structure=structure,
        defined_risk=True,
        option_right=str(trade.right),
        legs=legs,
        short_strike=float(trade.short_strike),
        long_strike=float(trade.long_strike),
        expiration=str(trade.expiration.date()),
        dte=int(trade.dte_at_entry),
        width=float(trade.width),
        net_credit=float(trade.net_credit),
    )
    meta = {
        "seat_id": seat.seat_id,
        "seat_status": seat.status,
        "regime": watch.regime,
        "expiration": intent.expiration,
        "net_credit": intent.net_credit,
        "max_loss_usd": max_loss_usd,
        "legs": legs,
    }
    return intent, "ok", meta


def run_paper_handoff(
    *,
    watch: WatchResult | None = None,
    registry_path: str | Path | None = None,
    execute_paper: bool = False,
    dry_run: bool = True,
) -> PaperHandoffResult:
    """Enrich watch → risk → optional paper ledger mutate.

    Defaults to dry_run=True (propose + risk only). execute_paper only applies when
    the living seat is paper_eligible (F2 seats stay dry-run only).
    """
    generated = _now()
    reg = load_living_registry(registry_path)
    if watch is None:
        watch = watch_once(registry=reg, registry_path=registry_path)

    if watch.status in {"NO_QUALIFIED_STRATEGY", "NO_SETUP"}:
        result = PaperHandoffResult(
            status=watch.status,
            watch_status=watch.status,
            reason=watch.reason,
            packet=watch.packet,
            generated_at=generated,
        )
        _audit("handoff_stand_aside", result.to_dict())
        return result

    intent, reason, meta = intent_from_watch(watch, registry=reg, registry_path=registry_path)
    if intent is None:
        result = PaperHandoffResult(
            status="NO_SETUP",
            watch_status=watch.status,
            reason=reason,
            packet={**watch.packet, "handoff_meta": meta},
            generated_at=generated,
        )
        _audit("handoff_no_intent", result.to_dict())
        return result

    governor = RiskGovernor()
    portfolio = PortfolioSnapshot()
    try:
        broker = get_broker("paper", rh_connected=False, agentic_enabled=False)
        if hasattr(broker, "portfolio_snapshot"):
            portfolio = broker.portfolio_snapshot()  # type: ignore[assignment]
    except Exception:
        broker = PaperBroker()

    decision = governor.check(intent, portfolio=portfolio, mode="paper")
    risk_info = {
        "allowed": bool(decision.allowed),
        "reasons": list(decision.reasons or []),
        "risk_amount": intent.risk_amount(),
    }
    packet = {
        **watch.packet,
        "legs": meta.get("legs") or intent.legs,
        "limit_price": intent.limit_price,
        "net_credit": intent.net_credit,
        "max_loss_usd": intent.max_loss_usd,
        "expiration": intent.expiration,
        "dte": intent.dte,
        "tag": intent.tag,
        "risk": risk_info,
        "intent_ready": True,
    }

    if not decision.allowed:
        result = PaperHandoffResult(
            status="RISK_DENIED",
            watch_status=watch.status,
            reason="risk governor denied: " + "; ".join(decision.reasons or []),
            intent={
                "symbol": intent.symbol,
                "structure": intent.structure,
                "limit_price": intent.limit_price,
                "max_loss_usd": intent.max_loss_usd,
                "tag": intent.tag,
            },
            risk=risk_info,
            packet=packet,
            generated_at=generated,
        )
        _audit("handoff_risk_denied", result.to_dict())
        return result

    seat = reg.get(watch.seat_id) if watch.seat_id else None
    seat_status = seat.status if seat else ""
    can_execute = bool(execute_paper and not dry_run and seat_status == "paper_eligible")

    paper_action = "dry_run_only"
    order_id = ""
    status = "PAPER_INTENT_READY"

    if can_execute:
        try:
            if not hasattr(broker, "place_limit"):
                raise RuntimeError("paper broker has no place_limit")
            place_result = broker.place_limit(intent)  # type: ignore[attr-defined]
            # OrderResult dataclass or plain id
            if hasattr(place_result, "ok") and not bool(place_result.ok):
                raise RuntimeError(getattr(place_result, "message", "paper place rejected"))
            order_obj = getattr(place_result, "order", None)
            order_id = str(
                getattr(order_obj, "order_id", None)
                or getattr(place_result, "order_id", None)
                or getattr(place_result, "id", None)
                or ""
            )
            paper_action = "paper_place"
            status = "PAPER_PLACED"
            reason = f"paper limit placed order_id={order_id}"
        except Exception as exc:  # noqa: BLE001
            paper_action = "paper_place_failed"
            status = "PAPER_PLACE_FAILED"
            reason = f"paper place failed: {exc}"
            result = PaperHandoffResult(
                status=status,
                watch_status=watch.status,
                reason=reason,
                intent={
                    "symbol": intent.symbol,
                    "structure": intent.structure,
                    "limit_price": intent.limit_price,
                    "max_loss_usd": intent.max_loss_usd,
                    "tag": intent.tag,
                },
                risk=risk_info,
                paper_action=paper_action,
                packet=packet,
                generated_at=generated,
            )
            _audit("handoff_paper_failed", result.to_dict())
            return result
    elif execute_paper and seat_status != "paper_eligible":
        paper_action = "blocked_not_paper_eligible"
        reason = (
            f"execute_paper requested but seat status={seat_status!r}; "
            "only paper_eligible may mutate paper ledger (F2 stays dry-run)."
        )
    else:
        reason = "intent built and risk-allowed; dry-run (no paper ledger mutate)"

    result = PaperHandoffResult(
        status=status,
        watch_status=watch.status,
        reason=reason,
        intent={
            "symbol": intent.symbol,
            "structure": intent.structure,
            "limit_price": intent.limit_price,
            "max_loss_usd": intent.max_loss_usd,
            "net_credit": intent.net_credit,
            "expiration": intent.expiration,
            "legs": intent.legs,
            "tag": intent.tag,
            "strategy_id": intent.strategy_id,
        },
        risk=risk_info,
        paper_action=paper_action,
        paper_order_id=order_id,
        packet=packet,
        generated_at=generated,
    )
    _audit("handoff_ok", result.to_dict())
    return result


def write_handoff_result(result: PaperHandoffResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def run_paper_plumbing_smoke(
    *,
    registry_path: str | Path | None = None,
    seat_id: str | None = None,
) -> PaperHandoffResult:
    """Force one paper ledger place for a paper_eligible seat (plumbing check).

    Ignores regime stand-aside so we can verify OPEN path without waiting for a
    bullish bar. Still never live. Tag includes plumbing_smoke.
    """
    generated = _now()
    reg = load_living_registry(registry_path)
    seats = [s for s in reg.seats if s.status == "paper_eligible"]
    if seat_id:
        seats = [s for s in seats if s.seat_id == seat_id]
    if not seats:
        return PaperHandoffResult(
            status="NO_SETUP",
            reason="no paper_eligible seats — run trader_promote_paper first",
            generated_at=generated,
        )
    seat = seats[0]
    symbol = (seat.symbols or ["SPY"])[0].upper()
    structure = "put_credit_spread"
    if build_market_frame is None:
        return PaperHandoffResult(
            status="NO_SETUP",
            reason="data.build unavailable",
            generated_at=generated,
        )
    frame = None
    for period in ("1y", "2y", "5y"):
        frame = build_market_frame(symbol, period=period, use_cache=True)
        if frame is not None and len(frame) >= 5:
            break
    if frame is None or len(frame) < 5:
        return PaperHandoffResult(
            status="NO_SETUP",
            reason=f"insufficient bars for {symbol}",
            generated_at=generated,
        )
    row = frame.iloc[-1].copy()
    # Force a regime that allows PCS so plumbing can run regardless of true regime.
    row["regime"] = "bullish"
    today = pd.Timestamp(str(frame.index[-1]))
    spot = float(row.get("close") or 0.0)
    spec = _load_spec(seat.spec_path)
    cfg = (
        spec.sim_config_for_structure(structure)
        if spec is not None
        else {
            "structure": structure,
            "long_dte": 21,
            "long_target_delta": 0.18,
            "spread_width": 1.0,
            "min_credit_pct": 0.08,
            "max_loss_budget_usd": 300.0,
            "bear_dte": 0,
            "iv_rank_min": 0.0,
        }
    )
    cfg = {**cfg, "iv_rank_min": 0.0, "bear_dte": 0}
    trade = pick_structure_entry(row, spot, today, cfg, structure=structure)
    if trade is None:
        return PaperHandoffResult(
            status="NO_SETUP",
            reason="plumbing smoke: pick_structure_entry failed even with forced bullish",
            generated_at=generated,
        )
    max_loss_usd = float(trade.max_loss_per_share) * 100.0
    legs = [
        {"right": "put", "action": "sell", "strike": trade.short_strike, "qty": 1},
        {"right": "put", "action": "buy", "strike": trade.long_strike, "qty": 1},
    ]
    intent = OrderIntent(
        symbol=symbol,
        side="sell",
        qty=1.0,
        order_type="limit",
        limit_price=float(trade.net_credit),
        strategy_id=seat.candidate_id,
        multiplier=100.0,
        tag=f"plumbing_smoke:{seat.seat_id}|pcs|ml={max_loss_usd:.2f}",
        max_loss_usd=max_loss_usd,
        structure=structure,
        defined_risk=True,
        option_right="put",
        legs=legs,
        short_strike=float(trade.short_strike),
        long_strike=float(trade.long_strike),
        expiration=str(trade.expiration.date()),
        dte=int(trade.dte_at_entry),
        width=float(trade.width),
        net_credit=float(trade.net_credit),
    )
    governor = RiskGovernor()
    broker = PaperBroker()
    portfolio = (
        broker.portfolio_snapshot()
        if hasattr(broker, "portfolio_snapshot")
        else PortfolioSnapshot()
    )
    decision = governor.check(intent, portfolio=portfolio, mode="paper")
    risk_info = {
        "allowed": bool(decision.allowed),
        "reasons": list(decision.reasons or []),
        "risk_amount": intent.risk_amount(),
    }
    if not decision.allowed:
        return PaperHandoffResult(
            status="RISK_DENIED",
            reason="plumbing smoke risk denied: " + "; ".join(decision.reasons or []),
            intent={
                "symbol": intent.symbol,
                "structure": intent.structure,
                "limit_price": intent.limit_price,
                "max_loss_usd": intent.max_loss_usd,
                "tag": intent.tag,
            },
            risk=risk_info,
            paper_action="blocked",
            generated_at=generated,
        )
    place_result = broker.place_limit(intent)
    if hasattr(place_result, "ok") and not place_result.ok:
        return PaperHandoffResult(
            status="PAPER_PLACE_FAILED",
            reason=getattr(place_result, "message", "place failed"),
            risk=risk_info,
            paper_action="paper_place_failed",
            generated_at=generated,
        )
    order_obj = getattr(place_result, "order", None)
    order_id = str(getattr(order_obj, "order_id", None) or "")
    result = PaperHandoffResult(
        status="PAPER_PLACED",
        reason=f"plumbing smoke paper order placed (forced bullish); order_id={order_id}",
        intent={
            "symbol": intent.symbol,
            "structure": intent.structure,
            "limit_price": intent.limit_price,
            "max_loss_usd": intent.max_loss_usd,
            "net_credit": intent.net_credit,
            "expiration": intent.expiration,
            "legs": intent.legs,
            "tag": intent.tag,
            "strategy_id": intent.strategy_id,
        },
        risk=risk_info,
        paper_action="plumbing_smoke_place",
        paper_order_id=order_id,
        packet={
            "plumbing_smoke": True,
            "forced_regime": "bullish",
            "seat_id": seat.seat_id,
            "note": "Not a real setup — ledger path verification only",
        },
        generated_at=generated,
    )
    _audit("plumbing_smoke_ok", result.to_dict())
    return result

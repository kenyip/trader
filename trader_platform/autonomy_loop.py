"""Autonomy loop: scout → propose → risk_check → paper_execute (default).

M2: scan_proposals uses premium_scout (regime→strategy→symbol→premium).
Paper-first: default mode is paper; agentic_live blocked until Stage1+arming.

Event/cron ready. Do NOT register live Hermes cron that places orders until Stage1+.

Usage:
  .venv/bin/python -m trader_platform.autonomy_loop --mode paper --once
  .venv/bin/python -m trader_platform.autonomy_loop --mode shadow --once
  .venv/bin/python -m trader_platform.autonomy_loop --mode paper --dry-review --once
  .venv/bin/python -m trader_platform.autonomy_loop --stub-proposals --once  # offline
  .venv/bin/python -m trader_platform.autonomy_loop --mode agentic_live --once  # blocked until arming
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trader_platform.execution.broker_adapter import (
    LiveOrdersBlocked,
    NotConnected,
    PaperBroker,
    PaperRhBridge,
    RhMcpReadAdapter,
    RobinhoodMcpBroker,
    get_broker,
)
from trader_platform.hypothesis_registry import HypothesisRegistry
from trader_platform.modes import Mode, parse_mode
from trader_platform.premium_scout import run_premium_scout
from trader_platform.risk_governor import OrderIntent, PortfolioSnapshot, RiskGovernor, load_limits
from trader_platform.rh_snapshot import try_load_snapshot

_REPO = Path(__file__).resolve().parents[1]
_AUDIT = _REPO / ".cache" / "platform" / "autonomy_audit.jsonl"


@dataclass
class Proposal:
    intent: OrderIntent
    reason: str
    event: str = "scan"
    scout_meta: Optional[dict[str, Any]] = None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def audit(event: str, payload: dict[str, Any]) -> None:
    _AUDIT.parent.mkdir(parents=True, exist_ok=True)
    line = {"ts": _now(), "event": event, **payload}
    with _AUDIT.open("a") as f:
        f.write(json.dumps(line, default=str) + "\n")


def scan_proposals_stub(
    registry: HypothesisRegistry,
    *,
    event: str = "manual_tick",
) -> list[Proposal]:
    """Offline structural proposal (CI / no market data). Prefer scan_proposals."""
    registry.ensure_seeded()
    proposals: list[Proposal] = []
    for h in registry.list():
        if h.status not in ("testing", "paper", "shadow", "live"):
            continue
        if h.sleeve == "cash":
            continue
        if not h.instruments:
            continue
        symbol = h.instruments[0]
        proposals.append(
            Proposal(
                intent=OrderIntent(
                    symbol=symbol,
                    side="sell",
                    qty=1,
                    order_type="limit",
                    limit_price=1.50,
                    strategy_id=h.id,
                    multiplier=100.0,
                    tag=f"m0_stub:{event}",
                ),
                reason=f"stub proposal from hypothesis {h.id} ({h.name})",
                event=event,
                scout_meta={"source": "stub"},
            )
        )
        break
    if not proposals:
        audit("stand_aside", {"event": event, "reason": "no eligible hypotheses"})
    return proposals


def scan_proposals(
    registry: HypothesisRegistry,
    *,
    event: str = "manual_tick",
    symbols: Optional[list[str]] = None,
    stub: bool = False,
    max_intents: int = 3,
) -> list[Proposal]:
    """M2 research loop: regime → strategy → symbol → premium scout → intents.

    paper-first: this only builds Proposal intents; risk + paper/shadow execute
    elsewhere in run_tick. Stand-aside is audited and is not an error.
    """
    if stub:
        return scan_proposals_stub(registry, event=event)

    report = run_premium_scout(
        registry=registry,
        symbols=symbols,
        event=event,
        max_intents=max_intents,
        audit=True,
    )
    proposals: list[Proposal] = []
    for c in report.candidates:
        if c.intent is None:
            continue
        proposals.append(
            Proposal(
                intent=c.intent,
                reason=c.reason,
                event=event,
                scout_meta=c.to_dict(),
            )
        )
    if not proposals:
        audit(
            "stand_aside",
            {
                "event": event,
                "reason": "premium_scout produced no sell intents",
                "n_stand_asides": len(report.stand_asides),
                "n_skipped": len(report.skipped),
                "actions": [c.action for c in report.candidates],
            },
        )
    else:
        audit(
            "scout_proposals",
            {
                "event": event,
                "n": len(proposals),
                "symbols": [p.intent.symbol for p in proposals],
            },
        )
    return proposals


def _agentic_enabled_from_limits() -> bool:
    try:
        limits = load_limits()
        return bool((limits.get("agentic") or {}).get("enabled", False))
    except Exception:  # noqa: BLE001
        return False


def _rh_review_bundle(
    intent: OrderIntent,
    *,
    account_number: Optional[str] = None,
    dry_review: bool = False,
    broker: Any = None,
) -> dict[str, Any]:
    """Build RH review_* payloads for shadow / dry-review (never place_*)."""
    if broker is not None and hasattr(broker, "review_option_order"):
        option_payload = broker.review_option_order(intent)
        equity_payload = (
            broker.review_equity_order(intent)
            if hasattr(broker, "review_equity_order")
            else {}
        )
    else:
        reader = RhMcpReadAdapter(connected=False, account_number=account_number)
        option_payload = reader.review_option_order(intent)
        equity_payload = reader.review_equity_order(intent)
    return {
        "dry_review": dry_review,
        "review_option_order": option_payload,
        "review_equity_order": equity_payload,
        "places": False,
    }


def run_tick(
    *,
    mode: Mode | str = Mode.PAPER,
    event: str = "manual_tick",
    portfolio: Optional[PortfolioSnapshot] = None,
    rh_connected: bool = False,
    dry_run: bool = False,
    dry_review: bool = False,
    account_number: Optional[str] = None,
    stub_proposals: bool = False,
    symbols: Optional[list[str]] = None,
    max_intents: int = 3,
) -> dict[str, Any]:
    mode = parse_mode(mode.value if isinstance(mode, Mode) else mode)
    registry = HypothesisRegistry()
    registry.ensure_seeded()
    governor = RiskGovernor()
    results: list[dict[str, Any]] = []
    agentic_enabled = _agentic_enabled_from_limits()
    readiness_blockers: list[str] = []

    if mode == Mode.AGENTIC_LIVE and not rh_connected:
        msg = "agentic_live blocked: Robinhood MCP not connected (Stage1 OAuth gate)"
        audit("blocked_live", {"reason": msg, "event": event})
        return {
            "ok": False,
            "mode": mode.value,
            "event": event,
            "error": msg,
            "results": [],
            "audit_path": str(_AUDIT),
        }

    if mode == Mode.AGENTIC_LIVE and not agentic_enabled:
        msg = "agentic_live blocked: agentic.enabled is false (risk_limits.yaml soft kill)"
        audit("blocked_live", {"reason": msg, "event": event})
        return {
            "ok": False,
            "mode": mode.value,
            "event": event,
            "error": msg,
            "results": [],
            "audit_path": str(_AUDIT),
        }

    broker = get_broker(
        mode.value,
        rh_connected=rh_connected,
        agentic_enabled=agentic_enabled,
        account_number=account_number,
    )

    if portfolio is None:
        portfolio = (
            broker.portfolio_snapshot()
            if hasattr(broker, "portfolio_snapshot")
            else PortfolioSnapshot()
        )

    # Stage2 readiness: refuse agentic_live when RH snapshot shows unfunded / no options
    snap = try_load_snapshot()
    if snap is not None:
        ready = snap.readiness()
        readiness_blockers = list(ready.blockers)
        if mode == Mode.AGENTIC_LIVE and not ready.ok:
            msg = "agentic_live blocked by Stage2 RH readiness: " + "; ".join(ready.blockers)
            audit(
                "blocked_live_readiness",
                {"reason": msg, "event": event, "blockers": ready.blockers},
            )
            return {
                "ok": False,
                "mode": mode.value,
                "event": event,
                "error": msg,
                "readiness": {
                    "ok": ready.ok,
                    "blockers": ready.blockers,
                    "warnings": ready.warnings,
                    "agentic_account_masked": ready.agentic_account_masked,
                    "agentic_total_value": ready.agentic_total_value,
                    "agentic_option_level": ready.agentic_option_level,
                },
                "results": [],
                "audit_path": str(_AUDIT),
            }

    proposals = scan_proposals(
        registry,
        event=event,
        symbols=symbols,
        stub=stub_proposals,
        max_intents=max_intents,
    )

    for prop in proposals:
        intent = prop.intent
        decision = governor.check(intent, portfolio=portfolio, mode=mode.value)
        entry: dict[str, Any] = {
            "proposal": prop.reason,
            "event": prop.event,
            "intent": {
                "symbol": intent.symbol,
                "side": intent.side,
                "qty": intent.qty,
                "order_type": intent.order_type,
                "limit_price": intent.limit_price,
                "strategy_id": intent.strategy_id,
                "notional": intent.estimated_notional(),
                "tag": intent.tag,
            },
            "risk": {"allowed": decision.allowed, "reasons": decision.reasons},
            "scout": prop.scout_meta,
        }

        if not decision.allowed:
            audit("risk_deny", entry)
            entry["action"] = "denied"
            results.append(entry)
            continue

        # --dry-review: build RH review_* payloads without paper mutate or live place
        if dry_review:
            entry["action"] = "dry_review"
            entry["rh_review"] = _rh_review_bundle(
                intent,
                account_number=account_number,
                dry_review=True,
                broker=broker,
            )
            if readiness_blockers:
                entry["readiness_blockers"] = readiness_blockers
            audit("dry_review", entry)
            results.append(entry)
            continue

        if mode == Mode.RESEARCH or dry_run:
            entry["action"] = "research_only"
            audit("research_propose", entry)
            results.append(entry)
            continue

        if mode == Mode.SHADOW:
            entry["action"] = "shadow_log_only"
            entry["rh_review"] = _rh_review_bundle(
                intent,
                account_number=account_number,
                dry_review=False,
                broker=broker,
            )
            if readiness_blockers:
                entry["readiness_blockers"] = readiness_blockers
            audit("shadow_propose", entry)
            results.append(entry)
            continue

        if mode == Mode.PAPER:
            try:
                open_orders = (
                    broker.list_open_orders()
                    if isinstance(broker, (PaperBroker, PaperRhBridge))
                    else []
                )
                existing = next(
                    (
                        o
                        for o in open_orders
                        if o.symbol == intent.symbol.upper()
                        and o.strategy_id == intent.strategy_id
                    ),
                    None,
                )
                if existing:
                    res = broker.replace_limit(
                        existing.order_id, qty=intent.qty, limit_price=intent.limit_price
                    )
                    entry["action"] = "paper_replace"
                else:
                    res = broker.place_limit(intent)
                    entry["action"] = "paper_place"
                entry["broker"] = {
                    "ok": res.ok,
                    "message": res.message,
                    "order_id": res.order.order_id if res.order else None,
                    "bridge": getattr(broker, "name", ""),
                    "rh_snapshot": bool(
                        getattr(broker, "has_readonly_snapshot", lambda: False)()
                    ),
                }
                audit(entry["action"], entry)
            except Exception as exc:  # noqa: BLE001 — tick must not crash cron
                entry["action"] = "error"
                entry["error"] = str(exc)
                audit("error", entry)
            results.append(entry)
            continue

        if mode == Mode.AGENTIC_LIVE:
            try:
                if isinstance(broker, RobinhoodMcpBroker):
                    entry["rh_review"] = broker.review_option_order(intent)
                res = broker.place_limit(intent)
                entry["action"] = "live_place"
                entry["broker"] = {"ok": res.ok, "message": res.message}
                audit("live_place", entry)
            except (NotConnected, LiveOrdersBlocked) as exc:
                entry["action"] = "not_connected"
                entry["error"] = str(exc)
                audit("not_connected", entry)
            except NotImplementedError as exc:
                entry["action"] = "not_implemented"
                entry["error"] = str(exc)
                audit("not_implemented", entry)
            except Exception as exc:  # noqa: BLE001
                entry["action"] = "error"
                entry["error"] = str(exc)
                audit("error", entry)
            results.append(entry)

    summary = {
        "ok": True,
        "mode": mode.value,
        "event": event,
        "n_proposals": len(proposals),
        "results": results,
        "audit_path": str(_AUDIT),
        "agentic_enabled": agentic_enabled,
        "rh_snapshot_loaded": try_load_snapshot() is not None,
        "readiness_blockers": readiness_blockers,
        "broker": getattr(broker, "name", ""),
        "stub_proposals": stub_proposals,
    }
    audit("tick_complete", {"mode": mode.value, "n": len(results), "stub": stub_proposals})
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Income platform autonomy tick (paper default)")
    p.add_argument(
        "--mode",
        default="paper",
        choices=["research", "paper", "shadow", "agentic_live"],
        help="execution mode (default: paper)",
    )
    p.add_argument("--once", action="store_true", help="run a single tick (default behavior)")
    p.add_argument("--event", default="manual_tick", help="event driver label")
    p.add_argument(
        "--rh-connected",
        action="store_true",
        help="claim RH MCP connected (still requires real Stage1 wiring; place remains blocked)",
    )
    p.add_argument("--dry-run", action="store_true", help="propose + risk only, no paper mutate")
    p.add_argument(
        "--dry-review",
        action="store_true",
        help="build RH review_* payloads (no place_*, no paper mutate); for trader-session handoff",
    )
    p.add_argument(
        "--account-number",
        default=None,
        help="optional RH account id for review payloads (prefer Agentic sleeve; redact in logs)",
    )
    p.add_argument(
        "--stub-proposals",
        action="store_true",
        help="use offline M0 stub proposals (no live.py / market data)",
    )
    p.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="limit premium scout to these underlyings",
    )
    p.add_argument("--max-intents", type=int, default=3, help="cap sell intents per tick")
    p.add_argument("--json", action="store_true", help="print JSON summary")
    args = p.parse_args(argv)

    summary = run_tick(
        mode=args.mode,
        event=args.event,
        rh_connected=args.rh_connected,
        dry_run=args.dry_run,
        dry_review=args.dry_review,
        account_number=args.account_number,
        stub_proposals=args.stub_proposals,
        symbols=args.symbols,
        max_intents=args.max_intents,
    )
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"mode={summary.get('mode')} ok={summary.get('ok')} event={summary.get('event')}")
        if summary.get("error"):
            print(f"error: {summary['error']}")
        if summary.get("broker"):
            print(f"broker={summary.get('broker')} rh_snapshot={summary.get('rh_snapshot_loaded')}")
        if summary.get("readiness_blockers"):
            print(f"readiness_blockers={summary.get('readiness_blockers')}")
        for r in summary.get("results") or []:
            intent = r.get("intent") or {}
            risk = r.get("risk") or {}
            print(
                f"  {r.get('action')}: {intent.get('symbol')} "
                f"{intent.get('side')} {intent.get('qty')} @ {intent.get('limit_price')} "
                f"risk_ok={risk.get('allowed')} {risk.get('reasons')}"
            )
            if r.get("broker"):
                print(f"    broker={r['broker']}")
            if r.get("rh_review"):
                tools = []
                rr = r["rh_review"]
                if "review_option_order" in rr:
                    tools.append(rr["review_option_order"].get("tool"))
                if "review_equity_order" in rr:
                    tools.append(rr["review_equity_order"].get("tool"))
                if rr.get("tool"):
                    tools.append(rr.get("tool"))
                print(f"    rh_review tools={tools} places={rr.get('places', False)}")
        print(f"audit: {summary.get('audit_path')}")
    return 0 if summary.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())

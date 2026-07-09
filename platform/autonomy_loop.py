"""Autonomy loop: scan → propose → risk_check → paper_execute (default).

Event/cron ready. Do NOT register live Hermes cron that places orders until Stage1.

Usage:
  .venv/bin/python -m platform.autonomy_loop --mode paper --once
  .venv/bin/python -m platform.autonomy_loop --mode shadow --once
  .venv/bin/python -m platform.autonomy_loop --mode agentic_live --once  # blocked until connected
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from platform.execution.broker_adapter import NotConnected, PaperBroker, get_broker
from platform.hypothesis_registry import HypothesisRegistry
from platform.modes import Mode, parse_mode
from platform.risk_governor import OrderIntent, PortfolioSnapshot, RiskGovernor

_REPO = Path(__file__).resolve().parents[1]
_AUDIT = _REPO / ".cache" / "platform" / "autonomy_audit.jsonl"


@dataclass
class Proposal:
    intent: OrderIntent
    reason: str
    event: str = "scan"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def audit(event: str, payload: dict[str, Any]) -> None:
    _AUDIT.parent.mkdir(parents=True, exist_ok=True)
    line = {"ts": _now(), "event": event, **payload}
    with _AUDIT.open("a") as f:
        f.write(json.dumps(line, default=str) + "\n")


def scan_proposals(
    registry: HypothesisRegistry,
    *,
    event: str = "manual_tick",
) -> list[Proposal]:
    """Minimal proposal generator for M0–M1.

    Reuses hypothesis registry; does not call live.py network path by default.
    Emits a conservative demo limit only for testing-status premium sleeves so the
    paper path exercises risk + broker without pretending it's a live signal.
    """
    registry.ensure_seeded()
    proposals: list[Proposal] = []
    for h in registry.list():
        if h.status not in ("testing", "paper", "shadow", "live"):
            continue
        if h.sleeve == "cash":
            continue
        if not h.instruments:
            continue
        # Dry structural proposal: 1-lot limit, tiny credit-style price placeholder.
        # Real signal wiring is M2 (live.py / pick_entry / pmcc scan).
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
            )
        )
        break  # one proposal per tick in M0–M1
    if not proposals:
        # Stand-aside path
        audit("stand_aside", {"event": event, "reason": "no eligible hypotheses"})
    return proposals


def run_tick(
    *,
    mode: Mode | str = Mode.PAPER,
    event: str = "manual_tick",
    portfolio: Optional[PortfolioSnapshot] = None,
    rh_connected: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    mode = parse_mode(mode.value if isinstance(mode, Mode) else mode)
    portfolio = portfolio or PortfolioSnapshot()
    registry = HypothesisRegistry()
    registry.ensure_seeded()
    governor = RiskGovernor()
    results: list[dict[str, Any]] = []

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

    broker = get_broker(mode.value, rh_connected=rh_connected)
    proposals = scan_proposals(registry, event=event)

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
            },
            "risk": {"allowed": decision.allowed, "reasons": decision.reasons},
        }

        if not decision.allowed:
            audit("risk_deny", entry)
            entry["action"] = "denied"
            results.append(entry)
            continue

        if mode == Mode.RESEARCH or dry_run:
            entry["action"] = "research_only"
            audit("research_propose", entry)
            results.append(entry)
            continue

        if mode == Mode.SHADOW:
            entry["action"] = "shadow_log_only"
            audit("shadow_propose", entry)
            results.append(entry)
            continue

        if mode == Mode.PAPER:
            try:
                open_orders = broker.list_open_orders() if isinstance(broker, PaperBroker) else []
                existing = next(
                    (
                        o
                        for o in open_orders
                        if o.symbol == intent.symbol.upper() and o.strategy_id == intent.strategy_id
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
                res = broker.place_limit(intent)
                entry["action"] = "live_place"
                entry["broker"] = {"ok": res.ok, "message": res.message}
                audit("live_place", entry)
            except NotConnected as exc:
                entry["action"] = "not_connected"
                entry["error"] = str(exc)
                audit("not_connected", entry)
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
    }
    audit("tick_complete", {"mode": mode.value, "n": len(results)})
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
        help="claim RH MCP connected (still requires real Stage1 wiring; stub will NotImplemented)",
    )
    p.add_argument("--dry-run", action="store_true", help="propose + risk only, no paper mutate")
    p.add_argument("--json", action="store_true", help="print JSON summary")
    args = p.parse_args(argv)

    summary = run_tick(
        mode=args.mode,
        event=args.event,
        rh_connected=args.rh_connected,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"mode={summary.get('mode')} ok={summary.get('ok')} event={summary.get('event')}")
        if summary.get("error"):
            print(f"error: {summary['error']}")
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
        print(f"audit: {summary.get('audit_path')}")
    return 0 if summary.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())

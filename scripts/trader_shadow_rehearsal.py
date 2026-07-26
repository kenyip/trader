#!/usr/bin/env python3
"""Shadow rehearsal: propose → risk_check → log only (no paper mutate, no live).

Writes .cache/platform/shadow/LATEST.json so go-live B7 can graduate from
PARTIAL → PASS once multi-session window evidence exists.

Usage:
  just trader-shadow-rehearsal
  just trader-shadow-rehearsal --ticks 2 --stub
  .venv/bin/python scripts/trader_shadow_rehearsal.py --symbols TSLL SMCI BAC
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.trader_go_live_status import market_session_days_spanned

_SHADOW_DIR = _REPO / ".cache" / "platform" / "shadow"
_LATEST = _SHADOW_DIR / "LATEST.json"
_HISTORY = _SHADOW_DIR / "history.jsonl"
_REPORT = _REPO / "reports" / "bootstrap" / "SHADOW_REHEARSAL_LATEST.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_history(path: Path | None = None) -> list[dict[str, Any]]:
    p = path if path is not None else _HISTORY
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _append_history(row: dict[str, Any], path: Path | None = None) -> None:
    p = path if path is not None else _HISTORY
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _session_days_from_history(history: list[dict[str, Any]]) -> list[str]:
    stamps: list[datetime] = []
    for row in history:
        ts = row.get("ts") or row.get("generated_at")
        if not ts:
            continue
        try:
            s = str(ts).replace("Z", "+00:00")
            stamps.append(datetime.fromisoformat(s))
        except Exception:
            continue
    if not stamps:
        return []
    stamps.sort()
    # span first→last so overnight multi-day history counts market sessions
    days = market_session_days_spanned(stamps[0], stamps[-1])
    # also include each individual stamp's NY day so same-week sparse ticks count
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    for dt in stamps:
        local = dt.astimezone(ny)
        if local.weekday() < 5:
            days.add(local.date().isoformat())
    return sorted(days)


def run_shadow_tick(
    *,
    event: str,
    stub: bool,
    symbols: Optional[list[str]],
    max_intents: int,
) -> dict[str, Any]:
    from trader_platform.autonomy_loop import run_tick

    return run_tick(
        mode="shadow",
        event=event,
        stub_proposals=stub,
        symbols=symbols,
        max_intents=max_intents,
        dry_run=False,
        dry_review=False,
    )


def _summarize_tick(summary: dict[str, Any]) -> dict[str, Any]:
    results = list(summary.get("results") or [])
    n_allow = 0
    n_deny = 0
    n_shadow = 0
    n_stand_aside = 0
    places = 0
    place_actions = {"paper_place", "paper_replace", "live_place"}
    for r in results:
        action = str(r.get("action") or "")
        if action == "shadow_log_only":
            n_shadow += 1
            n_allow += 1
        elif action == "denied":
            n_deny += 1
        elif action in ("stand_aside",) or r.get("stand_aside"):
            n_stand_aside += 1
        # Authority creep: only real place/replace actions (not rh_review payload shape)
        if action in place_actions:
            places += 1
        br = r.get("broker") or {}
        if action not in ("shadow_log_only", "denied", "dry_review", "research_only") and br.get(
            "order_id"
        ):
            places += 1
        rh = r.get("rh_review") or {}
        # Explicit places=True flag from review bundle means "would call place_*"
        if isinstance(rh, dict) and rh.get("places") is True and action != "shadow_log_only":
            places += 1
    return {
        "n_proposals": int(summary.get("n_proposals") or len(results)),
        "n_shadow_log": n_shadow,
        "n_risk_allow": n_allow,
        "n_risk_deny": n_deny,
        "n_stand_aside": n_stand_aside,
        "n_place_attempts": places,
        "broker": summary.get("broker"),
        "ok": bool(summary.get("ok")),
        "authority_creep": places > 0,
    }


def run_rehearsal(
    *,
    ticks: int = 1,
    stub: bool = False,
    symbols: Optional[list[str]] = None,
    max_intents: int = 3,
    event: str = "shadow_rehearsal",
    min_session_days_for_pass: int = 2,
) -> dict[str, Any]:
    tick_summaries: list[dict[str, Any]] = []
    for i in range(max(1, int(ticks))):
        summary = run_shadow_tick(
            event=f"{event}_{i+1}",
            stub=stub,
            symbols=symbols,
            max_intents=max_intents,
        )
        stats = _summarize_tick(summary)
        row = {
            "ts": _now(),
            "event": f"{event}_{i+1}",
            "stub": stub,
            "symbols": symbols,
            **stats,
            "mode": "shadow",
            "live_authority": False,
            "trading_authority": False,
        }
        _append_history(row)
        tick_summaries.append(row)
        if stats.get("authority_creep"):
            break

    history = _load_history()
    # Ignore zero-activity ticks for session/pass accounting
    active_history = [
        h
        for h in history
        if int(h.get("n_shadow_log") or 0) + int(h.get("n_risk_deny") or 0) > 0
        or int(h.get("n_proposals") or 0) > 0
    ]
    live_history = [h for h in active_history if not h.get("stub")]
    stub_history = [h for h in active_history if h.get("stub")]
    session_days = _session_days_from_history(live_history or active_history)
    live_session_days = _session_days_from_history(live_history)
    n_ticks = len(history)
    creep = any(t.get("authority_creep") for t in tick_summaries) or any(
        h.get("authority_creep") for h in history
    )
    n_shadow_total = sum(int(h.get("n_shadow_log") or 0) for h in history)
    n_deny_total = sum(int(h.get("n_risk_deny") or 0) for h in history)
    n_live_ticks = len(live_history)
    n_stub_ticks = len(stub_history)

    status = "FAIL"
    if creep:
        status = "FAIL"
        detail = "authority creep: place attempted during shadow — fix before arm"
    elif n_live_ticks >= 1 and (n_shadow_total + n_deny_total) >= 1:
        if len(live_session_days) >= min_session_days_for_pass:
            status = "PASS"
            detail = (
                f"multi-session live-scout shadow window: sessions={len(live_session_days)} "
                f"live_ticks={n_live_ticks} shadow_logs={n_shadow_total}"
            )
        else:
            status = "PARTIAL"
            detail = (
                f"live-scout path exercised (live_ticks={n_live_ticks}, "
                f"sessions={len(live_session_days)}/{min_session_days_for_pass}, "
                f"shadow_logs={n_shadow_total}) — need multi-session non-stub window"
            )
    elif n_stub_ticks >= 1 or n_ticks >= 1:
        status = "PARTIAL"
        detail = (
            f"stub/plumbing path only (stub_ticks={n_stub_ticks}, live_ticks={n_live_ticks}) — "
            "PASS requires non-stub multi-session propose→risk→log"
        )
    else:
        status = "FAIL"
        detail = "no proposals logged — stand-aside or scout empty; re-run RTH"

    latest = {
        "generated_at": _now(),
        "mode": "shadow_rehearsal",
        "ok": not creep and status != "FAIL",
        "status": status,
        "window_complete": status == "PASS",
        "session_days": len(live_session_days) if live_session_days else len(session_days),
        "session_day_list": live_session_days or session_days,
        "min_session_days_for_pass": min_session_days_for_pass,
        "n_history_ticks": n_ticks,
        "n_live_scout_ticks": n_live_ticks,
        "n_stub_ticks": n_stub_ticks,
        "n_shadow_log_total": n_shadow_total,
        "n_risk_deny_total": n_deny_total,
        "authority_creep": creep,
        "live_authority": False,
        "trading_authority": False,
        "stub_used": stub,
        "this_run_ticks": tick_summaries,
        "detail": detail,
        "honesty": (
            "Shadow only: propose→risk→log. No paper ledger mutate, no place_*. "
            "PASS requires multi-session *non-stub* window without authority creep. "
            "Stub ticks only prove plumbing (PARTIAL)."
        ),
    }

    _SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    _LATEST.write_text(json.dumps(latest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(latest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest["report_path"] = str(_REPORT)
    latest["latest_path"] = str(_LATEST)
    latest["history_path"] = str(_HISTORY)
    return latest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Shadow propose→risk→log rehearsal")
    p.add_argument("--ticks", type=int, default=1, help="Shadow ticks this run")
    p.add_argument(
        "--stub",
        action="store_true",
        help="Offline stub proposals (CI / no market data)",
    )
    p.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Limit scout underlyings (e.g. TSLL SMCI BAC)",
    )
    p.add_argument("--max-intents", type=int, default=3)
    p.add_argument("--event", default="shadow_rehearsal")
    p.add_argument(
        "--min-sessions",
        type=int,
        default=2,
        help="Session days required for PASS",
    )
    args = p.parse_args(argv)

    report = run_rehearsal(
        ticks=args.ticks,
        stub=args.stub,
        symbols=args.symbols,
        max_intents=args.max_intents,
        event=args.event,
        min_session_days_for_pass=args.min_sessions,
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "session_days": report.get("session_days"),
                "window_complete": report.get("window_complete"),
                "n_history_ticks": report.get("n_history_ticks"),
                "n_shadow_log_total": report.get("n_shadow_log_total"),
                "authority_creep": report.get("authority_creep"),
                "stub_used": report.get("stub_used"),
                "this_run": report.get("this_run_ticks"),
                "detail": report.get("detail"),
                "latest_path": report.get("latest_path"),
                "live_authority": False,
            },
            indent=2,
        )
    )
    # never fail CI solely on PARTIAL — only authority creep is hard fail
    if report.get("authority_creep"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

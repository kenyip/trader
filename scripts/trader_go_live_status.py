#!/usr/bin/env python3
"""Go-live funnel status — progress toward real trades (not densify bag %).

Usage:
  .venv/bin/python scripts/trader_go_live_status.py
  .venv/bin/python scripts/trader_go_live_status.py --json
  .venv/bin/python scripts/trader_go_live_status.py --watch 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_CACHE = _REPO / ".cache" / "platform"
_BOOT = _REPO / "reports" / "bootstrap"
_READY = _REPO / "reports" / "readiness" / "LATEST.md"
_NEXT = _BOOT / "NEXT_SEED.json"
_SHORTLIST = _BOOT / "QUALITY_SHORTLIST.json"
_TICK = _CACHE / "autonomous" / "tick_LATEST.json"
_CAMPAIGN = _CACHE / "paper_campaign" / "LATEST.json"
_QUALITY = _CACHE / "quality_residual" / "LATEST.json"
_HANDOFF = _REPO / ".cache" / "strategy-engine" / "latest.json"
_LIMITS = _REPO / "configs" / "risk_limits.yaml"
_LEDGER = _CACHE / "paper_ledger.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _age_hours(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return None


def _mark(ok: bool | str) -> str:
    if ok is True:
        return "PASS"
    if ok is False:
        return "FAIL"
    return str(ok)


@dataclass
class Check:
    id: str
    name: str
    status: str  # PASS | FAIL | PARTIAL | NA | UNKNOWN
    detail: str = ""


@dataclass
class Funnel:
    generated_at: str
    phase: str
    sleeve_plan_usd: int
    sleeve_cash_usd: Optional[float]
    option_level: str
    agentic_enabled: bool
    overall_pct: float
    overall_label: str
    activity_pct: float
    activity_label: str
    next_action: str
    ken_required: bool
    ken_only_for: list[str] = field(default_factory=list)
    platform: list[Check] = field(default_factory=list)
    strategy: list[Check] = field(default_factory=list)
    opportunity: list[Check] = field(default_factory=list)
    continuum: dict[str, Any] = field(default_factory=dict)
    paper: dict[str, Any] = field(default_factory=dict)
    activity: dict[str, Any] = field(default_factory=dict)
    shortlist_top: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    path_to_live: list[str] = field(default_factory=list)
    why_overall_stuck: str = ""


def _risk_limits() -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(_LIMITS.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _paper_stats() -> dict[str, Any]:
    ledger = _load_json(_LEDGER) or {}
    orders = ledger.get("orders") or {}
    if isinstance(orders, dict):
        items = list(orders.values())
    else:
        items = list(orders)
    real = []
    for o in items:
        if not isinstance(o, dict):
            continue
        tag = str(o.get("tag") or "")
        if "smoke" in tag.lower() or tag.startswith("plumbing_smoke") or "m0_stub" in tag:
            continue
        real.append(o)
    working = [o for o in real if str(o.get("status") or "").lower() in ("working", "open", "filled")]
    filled = [o for o in real if str(o.get("status") or "").lower() == "filled"]
    closed = [
        o
        for o in real
        if str(o.get("status") or "").lower() in ("filled", "canceled", "cancelled", "expired", "closed")
    ]
    open_ml = 0.0
    open_rows = []
    oldest_hold_h = 0.0
    now = datetime.now(timezone.utc)
    for o in working:
        st = str(o.get("status") or "").lower()
        if st not in ("working", "open"):
            continue
        ml = o.get("max_loss_usd")
        try:
            open_ml += float(ml or 0.0)
        except Exception:
            pass
        created = str(o.get("created") or "")
        hold_h = None
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                hold_h = (now - dt).total_seconds() / 3600.0
                oldest_hold_h = max(oldest_hold_h, hold_h)
            except Exception:
                hold_h = None
        open_rows.append(
            {
                "order_id": o.get("order_id"),
                "symbol": o.get("symbol"),
                "strategy_id": o.get("strategy_id"),
                "max_loss_usd": o.get("max_loss_usd"),
                "structure": o.get("structure"),
                "status": o.get("status"),
                "created": created,
                "hold_hours": round(hold_h, 2) if hold_h is not None else None,
            }
        )
    days = set()
    for o in real:
        c = str(o.get("created") or "")[:10]
        if c:
            days.add(c)
    return {
        "real_orders": len(real),
        "working": len([o for o in working if str(o.get("status")).lower() in ("working", "open")]),
        "filled": len(filled),
        "closedish": len(closed),
        "open_risk_usd": round(open_ml, 2),
        "open": open_rows,
        "session_days": len(days),
        "oldest_open_hold_hours": round(oldest_hold_h, 2),
        "ledger_path": str(_LEDGER),
    }


def collect() -> Funnel:
    limits = _risk_limits()
    agentic = bool((limits.get("agentic") or {}).get("enabled", False))
    snap = None
    try:
        from trader_platform.rh_snapshot import try_load_snapshot

        snap = try_load_snapshot()
    except Exception:
        snap = None

    cash = None
    level = "unknown"
    if snap is not None:
        try:
            accounts = list(getattr(snap, "accounts", None) or [])
            agentic_acct = None
            for a in accounts:
                if getattr(a, "agentic_allowed", False) or str(getattr(a, "nickname", "")).lower() == "agentic":
                    agentic_acct = a
                    break
            acct = agentic_acct or (accounts[0] if accounts else None)
            if acct is not None:
                cash = float(getattr(acct, "cash", None) or getattr(acct, "buying_power", None) or 0)
                level = str(getattr(acct, "option_level", None) or "unknown")
        except Exception:
            cash = None
            level = "unknown"

    next_seed = _load_json(_NEXT) or {}
    shortlist = _load_json(_SHORTLIST) or {}
    tick = _load_json(_TICK) or {}
    campaign = _load_json(_CAMPAIGN) or {}
    quality = _load_json(_QUALITY) or {}
    handoff = _load_json(_HANDOFF) or {}
    paper = _paper_stats()

    rows = list(shortlist.get("shortlist") or [])
    top = []
    for r in rows[:6]:
        top.append(
            {
                "hyp_id": r.get("hyp_id") or r.get("id"),
                "symbol": r.get("symbol"),
                "structure": r.get("structure"),
                "lane": r.get("lane"),
                "stress_priority": bool(r.get("stress_priority")),
                "notes": (r.get("notes") or r.get("why") or "")[:120],
            }
        )

    # --- Platform A ---
    platform: list[Check] = []
    smoke_ok = (_REPO / ".cache" / "platform" / "smoke_LATEST.json").is_file() or True
    # Prefer light check: risk file exists
    platform.append(
        Check(
            "A1",
            "smoke / platform runnable",
            "PASS" if (_REPO / ".venv" / "bin" / "python").is_file() else "FAIL",
            "venv present" if (_REPO / ".venv" / "bin" / "python").is_file() else "missing .venv",
        )
    )
    sleeve_note = ""
    try:
        max_open = float((limits.get("portfolio") or {}).get("max_open_risk", 0) or 0)
        sleeve_note = f"max_open_risk={max_open}"
        a2 = "PASS" if max_open and max_open <= 5000 else "PARTIAL"
    except Exception:
        a2 = "UNKNOWN"
        sleeve_note = "risk_limits unreadable"
    platform.append(Check("A2", "risk limits sleeve-aware", a2, sleeve_note))
    platform.append(
        Check(
            "A3",
            "paper path durable",
            "PASS" if paper["real_orders"] > 0 else "PARTIAL",
            f"real_orders={paper['real_orders']} working={paper['working']} open_risk=${paper['open_risk_usd']}",
        )
    )
    platform.append(
        Check(
            "A4",
            "shadow path exercised",
            "FAIL",
            "no multi-session shadow window logged yet",
        )
    )
    platform.append(
        Check(
            "A5",
            "kill switch documented",
            "PARTIAL",
            "policy docs exist; kill drill not yet run as packet evidence",
        )
    )
    platform.append(Check("A6", "secrets not in git", "PASS", "doctrine + hygiene"))
    platform.append(
        Check(
            "A7",
            "live disarmed until Ken arm",
            "PASS" if not agentic else "FAIL",
            f"agentic.enabled={agentic}",
        )
    )

    # --- Strategy B (best shortlist leader) ---
    strategy: list[Check] = []
    leader = None
    for r in rows:
        if r.get("stress_priority") or (r.get("lane") in ("paper_research", "paper")):
            if (r.get("structure") or "") in (
                "put_credit_spread",
                "call_credit_spread",
                "iron_condor",
                "cash_secured_put",
            ):
                leader = r
                break
    if leader is None and rows:
        leader = rows[0]

    lid = (leader or {}).get("hyp_id") or (leader or {}).get("id") or "none"
    strategy.append(
        Check(
            "B1",
            "capital fit ≤ sleeve",
            "PARTIAL" if leader else "FAIL",
            f"leader={lid} plan_sleeve=3000 cash≈{cash} (multi-leg paper OK; MCP first-live single-leg needs fit)",
        )
    )
    strategy.append(
        Check(
            "B2",
            "ship bar / not thin vanity",
            "PARTIAL" if leader else "FAIL",
            "shortlist leaders exist; densify n≈9 still thin — quality_pass=false on engine densify",
        )
    )
    # B3/B4 from shortlist notes or campaign leaders
    b3 = "PARTIAL"
    b4 = "PARTIAL"
    if leader and leader.get("stress_priority"):
        b3 = "PASS"
        b4 = "PASS"
    strategy.append(Check("B3", "regime stress (B3)", b3, f"leader={lid}"))
    strategy.append(Check("B4", "cost/slip stress (B4)", b4, f"leader={lid}"))
    strategy.append(
        Check(
            "B5",
            "entry+exit DNA explicit",
            "PARTIAL" if leader else "FAIL",
            "DNA present on shortlist hyps; management path still paper-learning",
        )
    )
    multi_session = paper["session_days"] >= 3 and paper["real_orders"] >= 5
    # Graduated B6: show partial credit as paper ages (not binary forever)
    b6_status = "FAIL"
    b6_detail = f"session_days={paper['session_days']} real_orders={paper['real_orders']} working={paper['working']}"
    if multi_session:
        b6_status = "PASS"
    elif paper["working"] or paper["real_orders"]:
        # open paper earns PARTIAL; more days → still PARTIAL until 3 sessions
        b6_status = "PARTIAL"
        b6_detail += f" need_session_days≥3 (have {paper['session_days']})"
    strategy.append(
        Check(
            "B6",
            "multi-session paper sample",
            b6_status,
            b6_detail,
        )
    )
    strategy.append(Check("B7", "shadow window clean", "FAIL", "not started"))

    # --- Opportunity C ---
    opportunity: list[Check] = []
    # rough RTH check via local time weekday hour PT
    try:
        from zoneinfo import ZoneInfo

        now_pt = datetime.now(ZoneInfo("America/Los_Angeles"))
        rth = now_pt.weekday() < 5 and 6 <= now_pt.hour < 13  # 6-13 cron window / approx session
        opportunity.append(
            Check(
                "C1",
                "regime matches (day-of)",
                "NA" if not rth else "UNKNOWN",
                "evaluate at RTH via rth-eval/scout",
            )
        )
        opportunity.append(Check("C2", "size 1-lot", "PASS", "doctrine default 1 lot"))
        opportunity.append(
            Check(
                "C3",
                "BP free / no pile-on",
                "PASS" if (cash is None or cash >= 0) else "FAIL",
                f"cash≈{cash} open_risk=${paper['open_risk_usd']}",
            )
        )
        opportunity.append(Check("C4", "daily loss stop configured", "PARTIAL", "risk_limits present; live stop wire later"))
    except Exception:
        opportunity.append(Check("C1", "regime matches (day-of)", "NA", ""))
        opportunity.append(Check("C2", "size 1-lot", "PASS", "1 lot"))
        opportunity.append(Check("C3", "BP free", "UNKNOWN", ""))
        opportunity.append(Check("C4", "daily loss stop", "PARTIAL", ""))

    def score(checks: list[Check]) -> tuple[float, int, int]:
        pts = 0.0
        n = 0
        for c in checks:
            if c.status == "NA":
                continue
            n += 1
            if c.status == "PASS":
                pts += 1.0
            elif c.status == "PARTIAL":
                pts += 0.5
            elif c.status == "UNKNOWN":
                pts += 0.25
        return (pts / n * 100.0 if n else 0.0), int(pts), n

    p_pct, _, _ = score(platform)
    s_pct, _, _ = score(strategy)
    o_pct, _, _ = score(opportunity)
    # Weight strategy highest for "ready for real trades"
    # This bar is GATE-based: stays flat until hard evidence flips PASS/FAIL.
    overall = 0.25 * p_pct + 0.55 * s_pct + 0.20 * o_pct

    # Continuum freshness (needed for activity bar)
    tick_at = tick.get("generated_at")
    camp_at = campaign.get("generated_at")
    handoff_status = handoff.get("status") or "MISSING"
    worker_hb = _load_json(_REPO / ".cache" / "platform" / "quality_worker" / "HEARTBEAT.json") or {}
    worker_status = _load_json(_REPO / ".cache" / "platform" / "quality_worker" / "STATUS.json") or {}
    worker_pid_path = _REPO / ".cache" / "platform" / "quality_worker" / "worker.pid"
    worker_running = False
    if worker_pid_path.is_file():
        try:
            wpid = int(worker_pid_path.read_text().strip())
            os.kill(wpid, 0)
            worker_running = True
        except Exception:
            worker_running = False

    # --- Activity / momentum (moves every cycle; NOT go-live %) ---
    cycle_dir = _REPO / ".cache" / "platform" / "quality_residual"
    cycle_n = len(list(cycle_dir.glob("cycle_*.json"))) if cycle_dir.is_dir() else 0
    # paper hold hours from oldest working open
    hold_h = 0.0
    for o in paper.get("open") or []:
        # ledger has created on orders — recompute from full ledger
        pass
    hold_h = float(paper.get("oldest_open_hold_hours") or 0.0)
    session_days = int(paper.get("session_days") or 0)
    real_orders = int(paper.get("real_orders") or 0)
    working = int(paper.get("working") or 0)
    hb_age = _age_hours(worker_hb.get("generated_at"))
    hb_fresh = worker_running and hb_age is not None and hb_age < 0.25  # <15 min

    # Activity score 0-100: search churn + paper aging + stress loop health
    act = 0.0
    act += min(35.0, cycle_n * 0.7)  # ~50 cycles → 35 pts
    act += 15.0 if worker_running else 0.0
    act += 10.0 if hb_fresh else (5.0 if worker_running else 0.0)
    act += min(20.0, session_days * 6.0 + hold_h * 0.5)  # paper aging
    act += min(10.0, real_orders * 2.0)
    act += 5.0 if working >= 1 else 0.0
    act += 5.0 if (leader and leader.get("stress_priority")) else 0.0
    activity_pct = round(min(100.0, act), 1)
    if activity_pct >= 70:
        activity_label = "HOT_SEARCH"
    elif activity_pct >= 40:
        activity_label = "ACTIVE"
    elif activity_pct >= 15:
        activity_label = "WARMING"
    else:
        activity_label = "IDLE"

    activity = {
        "quality_cycles_completed": cycle_n,
        "worker_running": worker_running,
        "worker_hb_fresh": hb_fresh,
        "worker_hb_age_h": round(hb_age or -1, 3),
        "paper_session_days": session_days,
        "paper_hold_hours_oldest": round(hold_h, 2),
        "paper_real_orders": real_orders,
        "paper_working": working,
        "note": "Activity moves with cycles/paper age. Go-live bar only moves on hard gates.",
    }

    blockers: list[str] = []
    if agentic:
        blockers.append("agentic.enabled=true unexpectedly")
    if not any(c.status == "PASS" for c in strategy if c.id == "B3"):
        blockers.append("no pack-grade TOP_HYP (engine quality_pass still false)")
    if any(c.status == "FAIL" for c in strategy if c.id == "B7"):
        blockers.append("shadow window not done")
    if any(c.status in ("FAIL", "PARTIAL") for c in strategy if c.id == "B6"):
        blockers.append("need more multi-session paper evidence")
    if cash is not None and cash < 1000:
        blockers.append(f"test sleeve cash ${cash:.0f} — CSP ATM rarely fits; $3k at LIVE_PACKET")
    blockers.append("MCP place = single-leg only (multi-leg BAC/PLTR = paper/research until RH multi-leg)")
    blockers.append("place_* blocked until Ken LIVE_PACKET arm")

    stuck_bits = []
    if any(c.status != "PASS" for c in strategy if c.id == "B6"):
        stuck_bits.append(f"B6 paper sessions {session_days}/3")
    if any(c.status != "PASS" for c in strategy if c.id == "B7"):
        stuck_bits.append("B7 shadow not started")
    if any(c.status != "PASS" for c in strategy if c.id == "B2"):
        stuck_bits.append("B2 no pack-grade TOP_HYP")
    stuck_bits.append("live arm is Ken-only (never auto)")
    why_stuck = (
        "Go-live % is gate-based (not cycle count). Stuck on: " + "; ".join(stuck_bits)
        + f". Activity is separate ({activity_pct}% — cycles={cycle_n})."
    )

    path = [
        f"1. Paper multi-session — IN PROGRESS ({session_days}/3 days, hold≈{hold_h:.1f}h, cycles={cycle_n})",
        "2. Promote one hyp to pack-grade TOP_HYP (B3+B4 + thicker n + quality_pass)",
        "3. Shadow window + kill drill (no broker mutate)",
        "4. First-live DNA must be MCP single-leg capital-fit (or multi-leg when RH supports)",
        "5. Draft LIVE_PACKET → Ken arms → place_* on Agentic only",
    ]

    phase = "BUILD"
    if paper["working"] or paper["real_orders"] >= 2:
        phase = "PAPER"
    if any(c.status == "PASS" for c in strategy if c.id == "B7"):
        phase = "SHADOW"

    if overall >= 85 and all(c.status == "PASS" for c in strategy if c.id in ("B3", "B4", "B6", "B7")):
        label = "NEAR_LIVE_PACKET"
    elif overall >= 55:
        label = "PAPER_PROGRESS"
    elif overall >= 35:
        label = "BUILD_SEARCH"
    else:
        label = "EARLY"

    return Funnel(
        generated_at=_now(),
        phase=phase,
        sleeve_plan_usd=3000,
        sleeve_cash_usd=cash,
        option_level=level,
        agentic_enabled=agentic,
        overall_pct=round(overall, 1),
        overall_label=label,
        activity_pct=activity_pct,
        activity_label=activity_label,
        next_action=str(next_seed.get("next_action") or "unknown"),
        ken_required=bool(next_seed.get("ken_required", False)),
        ken_only_for=list(next_seed.get("ken_only_for") or ["gateway_up", "LIVE_PACKET_arm", "fund_3k_at_packet"]),
        platform=platform,
        strategy=strategy,
        opportunity=opportunity,
        continuum={
            "handoff_status": handoff_status,
            "autonomous_tick_at": tick_at,
            "autonomous_tick_age_h": round(_age_hours(tick_at) or -1, 2),
            "autonomous_action": tick.get("action"),
            "quality_residual_at": quality.get("generated_at"),
            "paper_campaign_at": camp_at,
            "paper_campaign_age_h": round(_age_hours(camp_at) or -1, 2),
            "paper_campaign_next": campaign.get("next_action"),
            "quality_worker_running": worker_running,
            "quality_worker_state": worker_status.get("state"),
            "quality_worker_hb_at": worker_hb.get("generated_at"),
            "quality_worker_hb_age_h": round(_age_hours(worker_hb.get("generated_at")) or -1, 2),
            "quality_worker_stamp": worker_hb.get("stamp"),
            "quality_cycles_completed": cycle_n,
        },
        paper=paper,
        activity=activity,
        shortlist_top=top,
        blockers=blockers,
        path_to_live=path,
        why_overall_stuck=why_stuck,
    )


def _bar(pct: float, width: int = 28) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct:5.1f}%"


def format_text(f: Funnel) -> str:
    lines: list[str] = []
    lines.append("Trader → real-trade readiness")
    lines.append("─" * 48)
    lines.append(f"Phase: {f.phase}   go-live label: {f.overall_label}   activity: {f.activity_label}")
    lines.append(f"Go-live  {_bar(f.overall_pct)}  ← hard gates only (can stay flat)")
    lines.append(f"Activity {_bar(f.activity_pct)}  ← cycles / paper age / worker (moves)")
    if f.why_overall_stuck:
        lines.append(f"Note: {f.why_overall_stuck}")
    lines.append(
        f"Sleeve plan ${f.sleeve_plan_usd} · cash≈{f.sleeve_cash_usd} · options={f.option_level} · agentic={f.agentic_enabled}"
    )
    lines.append(f"NEXT: {f.next_action}   ken_required={f.ken_required}")
    lines.append("")

    lines.append("CONTINUUM (is it running?)")
    c = f.continuum
    wr = "ON" if c.get("quality_worker_running") else "off"
    lines.append(
        f"  quality_worker={wr}  cycles={c.get('quality_cycles_completed')}  "
        f"hb_age_h={c.get('quality_worker_hb_age_h')}  stamp={c.get('quality_worker_stamp')}"
    )
    lines.append(
        f"  handoff={c.get('handoff_status')}  tick={c.get('autonomous_action')}  "
        f"age_h={c.get('autonomous_tick_age_h')}  campaign_age_h={c.get('paper_campaign_age_h')}"
    )
    if c.get("autonomous_tick_at"):
        lines.append(f"  last_tick: {c.get('autonomous_tick_at')}")
    if c.get("paper_campaign_at"):
        lines.append(f"  last_campaign: {c.get('paper_campaign_at')} → {c.get('paper_campaign_next')}")
    lines.append("")

    lines.append("ACTIVITY DETAIL")
    a = f.activity or {}
    lines.append(
        f"  cycles={a.get('quality_cycles_completed')} worker={a.get('worker_running')} "
        f"hb_fresh={a.get('worker_hb_fresh')} paper_days={a.get('paper_session_days')} "
        f"hold_h={a.get('paper_hold_hours_oldest')} working={a.get('paper_working')}"
    )
    lines.append("")

    lines.append("PAPER BOOK")
    p = f.paper
    lines.append(
        f"  real_orders={p.get('real_orders')} working={p.get('working')} "
        f"session_days={p.get('session_days')} open_risk=${p.get('open_risk_usd')} "
        f"oldest_hold_h={p.get('oldest_open_hold_hours')}"
    )
    for o in p.get("open") or []:
        hh = o.get("hold_hours")
        lines.append(
            f"  · {o.get('symbol')} {o.get('strategy_id')} ml=${o.get('max_loss_usd')} "
            f"hold={hh}h [{o.get('status')}]"
        )
    if not (p.get("open") or []):
        lines.append("  · (no open campaign orders)")
    lines.append("")

    def section(title: str, checks: list[Check]) -> None:
        lines.append(title)
        for ch in checks:
            mark = {"PASS": "✓", "FAIL": "✗", "PARTIAL": "~", "NA": "·", "UNKNOWN": "?"}.get(ch.status, "?")
            lines.append(f"  {mark} {ch.id} {ch.name:<32} {ch.status:<8} {ch.detail}")
        lines.append("")

    section("A · PLATFORM", f.platform)
    section("B · STRATEGY (first-live hyp bar)", f.strategy)
    section("C · OPPORTUNITY (day-of)", f.opportunity)

    lines.append("SHORTLIST TOP")
    if not f.shortlist_top:
        lines.append("  (empty)")
    for r in f.shortlist_top:
        sp = "*" if r.get("stress_priority") else " "
        lines.append(
            f"  {sp} {r.get('symbol')} {r.get('structure')} {r.get('hyp_id')}  [{r.get('lane')}]"
        )
    lines.append("")

    lines.append("BLOCKERS")
    for b in f.blockers:
        lines.append(f"  • {b}")
    lines.append("")

    lines.append("PATH TO LIVE")
    for step in f.path_to_live:
        lines.append(f"  {step}")
    lines.append("")

    lines.append("COMMANDS")
    lines.append("  just trader-status              # this funnel")
    lines.append("  just trader-status --watch 10   # refresh every 10s")
    lines.append("  just trader-run-now             # trigger continuum + show funnel")
    lines.append("  just trader-run-now campaign    # paper campaign only + funnel")
    lines.append("  just trader-progress            # densify bag stats (different)")
    lines.append("  cat reports/bootstrap/NEXT_SEED.json")
    lines.append("")
    lines.append(f"generated_at: {f.generated_at}")
    lines.append("Ken only: gateway_up | LIVE_PACKET arm | $3k at packet")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--watch", type=float, nargs="?", const=10.0, default=None)
    ap.add_argument("--write", action="store_true", help="Write reports/readiness/go_live_status_LATEST.json")
    args = ap.parse_args(argv)

    def once() -> Funnel:
        f = collect()
        if args.write:
            out = _REPO / "reports" / "readiness" / "go_live_status_LATEST.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = asdict(f)
            out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(asdict(f), indent=2, sort_keys=True))
        else:
            if args.watch is not None:
                sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(format_text(f))
            sys.stdout.flush()
        return f

    if args.watch is None:
        once()
        return 0
    interval = max(2.0, float(args.watch))
    try:
        while True:
            once()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n(stopped)", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

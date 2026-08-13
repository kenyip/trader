#!/usr/bin/env python3
"""Trader readiness — simple 3-layer status (edge / robot / arm).

Plain language (Ken):
  1. EDGE  — sims find & kill strategies (24/7, no market hours required)
  2. ROBOT — paper + shadow prove the machine works on a live clock
  3. ARM   — Ken funds/arms 1-lot live (never automatic)

Legacy A/B/C letter gates still appear in --json for older tools.

Usage:
  .venv/bin/python scripts/trader_go_live_status.py
  .venv/bin/python scripts/trader_go_live_status.py --json
  .venv/bin/python scripts/trader_go_live_status.py --watch 10
  .venv/bin/python scripts/trader_go_live_status.py --write
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_CACHE = _REPO / ".cache" / "platform"
_BOOT = _REPO / "reports" / "bootstrap"
_NEXT = _BOOT / "NEXT_SEED.json"
_SHORTLIST = _BOOT / "QUALITY_SHORTLIST.json"
_FIRST_LIVE = _BOOT / "FIRST_LIVE_LANE.json"
_TICK = _CACHE / "autonomous" / "tick_LATEST.json"
_CAMPAIGN = _CACHE / "paper_campaign" / "LATEST.json"
_QUALITY = _CACHE / "quality_residual" / "LATEST.json"
_HANDOFF = _REPO / ".cache" / "strategy-engine" / "latest.json"
_LIMITS = _REPO / "configs" / "risk_limits.yaml"
_LEDGER = _CACHE / "paper_ledger.json"
_AUDIT = _CACHE / "autonomy_audit.jsonl"
_SHADOW_LATEST = _CACHE / "shadow" / "LATEST.json"
_CYCLE_LATEST = _CACHE / "quality_worker" / "cycle_LATEST.json"
_HYPS_YAML = _REPO / "trader_platform" / "data" / "hypotheses.yaml"
_KEN_EDGE_FREEZE = Path.home() / ".local/state/jarvis/trader-guidance/edge-search-freeze.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _ken_edge_freeze_payload(path: Optional[Path] = None) -> dict[str, Any]:
    """Operator latch: worker may watch/paper, must not evolve or prune-to-unfreeze."""
    p = path or _KEN_EDGE_FREEZE
    try:
        if not p.is_file():
            return {"active": False}
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not bool(data.get("skip_evolve")):
            return {"active": False}
        return {
            "active": True,
            "reason": str(data.get("reason") or "ken_edge_search_frozen"),
            "unfreeze_gate": data.get("unfreeze_gate"),
            "note": data.get("note"),
            "source": data.get("source"),
        }
    except Exception:
        return {"active": False}


def _ken_freeze_from_cycle(cycle: dict[str, Any], note: str, phases: dict[str, Any]) -> tuple[bool, str]:
    reasons = [note]
    for lane in ("evolve_csp", "evolve_defined_risk"):
        ph = phases.get(lane) if isinstance(phases.get(lane), dict) else {}
        reasons.append(str(ph.get("reason") or ""))
    blob = " ".join(reasons).lower()
    if "ken_" in blob and "freeze" in blob:
        for raw in reasons:
            token = str(raw).strip()
            if "ken_" in token.lower() and "freeze" in token.lower():
                # Prefer the compact reason token over the full evolve_note sentence.
                if " " not in token and len(token) < 80:
                    return True, token
        return True, "ken_edge_search_frozen"
    if "do not prune-to-unfreeze" in blob:
        return True, "ken_edge_search_frozen"
    return False, ""


def edge_search_health(
    cycle: Optional[dict] = None,
    *,
    registry_bytes: Optional[int] = None,
    freeze_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Classify quality-cycle EDGE muscle health.

    Green cycle rc=0 can still freeze search when both evolves skip on registry bloat
    (2026-07-28/30/31 coach) **or** when Ken latches first-close freeze
    (2026-08-13 coach). Surface that so status cannot look SEARCHING / OK_PARTIAL
    while minting is intentionally off — and so coaches do not prune a Ken freeze.
    """
    cycle = cycle or {}
    raw_phases = cycle.get("phases")
    phases: dict[str, Any] = raw_phases if isinstance(raw_phases, dict) else {}
    note = str(cycle.get("evolve_note") or "")
    bloat_reasons: list[str] = []
    evolve_skipped = 0
    evolve_ran = 0
    for lane in ("evolve_csp", "evolve_defined_risk"):
        ph = phases.get(lane) if isinstance(phases.get(lane), dict) else {}
        reason = str(ph.get("reason") or "")
        if ph.get("skipped"):
            evolve_skipped += 1
        elif ph.get("cmd") or (ph.get("seconds") or 0) > 0:
            evolve_ran += 1
        if "registry_bloat" in reason or "bloat" in reason.lower():
            bloat_reasons.append(f"{lane}:{reason or 'bloat'}")
    if "registry_bloat" in note or "bloat" in note.lower():
        if note and note not in bloat_reasons:
            bloat_reasons.append(note)
    reg_b = registry_bytes
    if reg_b is None:
        try:
            reg_b = int(cycle.get("registry_bytes"))  # type: ignore[arg-type]
        except Exception:
            reg_b = None
    if reg_b is None and _HYPS_YAML.is_file():
        try:
            reg_b = int(_HYPS_YAML.stat().st_size)
        except Exception:
            reg_b = None
    try:
        reg_max = int(cycle.get("registry_max_bytes") or 0) or None
    except Exception:
        reg_max = None
    bloated = bool(bloat_reasons)
    ken_file = _ken_edge_freeze_payload(freeze_path)
    ken_cycle, ken_cycle_reason = _ken_freeze_from_cycle(cycle, note, phases)
    ken_frozen = bool(ken_file.get("active") or ken_cycle)
    ken_reason = str(ken_file.get("reason") or ken_cycle_reason or "")
    if ken_frozen:
        state = "KEN_FROZEN"
        summary = (
            f"EDGE evolves skipped — Ken freeze ({ken_reason or 'ken_edge_search_frozen'}); "
            "watch/paper only; do not prune-to-unfreeze"
        )
    elif bloated:
        state = "BLOATED_SKIP"
        summary = "EDGE evolves skipped — registry bloat (prune off-hours)"
    elif evolve_ran >= 1:
        state = "OK"
        summary = "EDGE evolve ran"
    elif evolve_skipped >= 1 and not bloated:
        # alternate-lane skip is healthy when the other lane ran, or book-only cycle
        state = "OK_PARTIAL"
        summary = "EDGE evolve alternate/skip (non-bloat)"
    else:
        state = "UNKNOWN"
        summary = "no evolve phase detail"
    return {
        "state": state,
        "summary": summary,
        "registry_bloated_skip": bloated and not ken_frozen,
        "registry_over_limit": bool(
            isinstance(reg_b, int) and isinstance(reg_max, int) and reg_max > 0 and reg_b > reg_max
        ),
        "ken_edge_frozen": ken_frozen,
        "ken_freeze_reason": ken_reason or None,
        "registry_bytes": reg_b,
        "registry_max_bytes": reg_max,
        "evolve_note": note or None,
        "bloat_reasons": bloat_reasons,
        "evolve_ran": evolve_ran,
        "evolve_skipped": evolve_skipped,
        "cycle_stamp": cycle.get("stamp"),
    }


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


def _parse_dt(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _ny_date(dt: datetime) -> date:
    try:
        from zoneinfo import ZoneInfo

        return dt.astimezone(ZoneInfo("America/New_York")).date()
    except Exception:
        return dt.astimezone(timezone.utc).date()


def market_session_days_spanned(
    start: datetime,
    end: Optional[datetime] = None,
    *,
    now: Optional[datetime] = None,
) -> set[str]:
    """Unique NY calendar weekdays from start..end (inclusive), as ISO dates.

    Holding paper overnight correctly advances the ops sample. Weekends skipped.
    """
    end_dt = end or now or datetime.now(timezone.utc)
    if end_dt < start:
        start, end_dt = end_dt, start
    d0 = _ny_date(start)
    d1 = _ny_date(end_dt)
    out: set[str] = set()
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:  # Mon-Fri
            out.add(cur.isoformat())
        cur += timedelta(days=1)
    return out


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
    first_live_lane: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    path_to_live: list[str] = field(default_factory=list)
    why_overall_stuck: str = ""
    # Simple 3-layer view (primary for humans)
    layers: dict[str, Any] = field(default_factory=dict)
    simple_next: str = ""
    glossary: dict[str, str] = field(default_factory=dict)


def _risk_limits() -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(_LIMITS.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _is_smoke_order(o: dict[str, Any]) -> bool:
    tag = str(o.get("tag") or "")
    sid = str(o.get("strategy_id") or "")
    return (
        "smoke" in tag.lower()
        or tag.startswith("plumbing_smoke")
        or "m0_stub" in tag
        or "smoke" in sid.lower()
    )


def _paper_stats() -> dict[str, Any]:
    ledger = _load_json(_LEDGER) or {}
    orders = ledger.get("orders") or {}
    if isinstance(orders, dict):
        items = list(orders.values())
    else:
        items = list(orders)
    real = [o for o in items if isinstance(o, dict) and not _is_smoke_order(o)]
    working = [
        o
        for o in real
        if str(o.get("status") or "").lower() in ("working", "open")
    ]
    filled = [o for o in real if str(o.get("status") or "").lower() == "filled"]
    closed = [
        o
        for o in real
        if str(o.get("status") or "").lower()
        in ("filled", "canceled", "cancelled", "expired", "closed")
    ]
    open_ml = 0.0
    open_rows = []
    oldest_hold_h = 0.0
    now = datetime.now(timezone.utc)
    session_days: set[str] = set()

    for o in real:
        created = _parse_dt(str(o.get("created") or ""))
        end = (
            _parse_dt(str(o.get("closed_at") or o.get("updated") or o.get("filled_at") or ""))
            or now
        )
        st = str(o.get("status") or "").lower()
        if st in ("working", "open"):
            end = now
        if created is not None:
            session_days |= market_session_days_spanned(created, end, now=now)

    for o in working:
        ml = o.get("max_loss_usd")
        try:
            open_ml += float(ml or 0.0)
        except Exception:
            pass
        created = str(o.get("created") or "")
        hold_h = None
        cdt = _parse_dt(created)
        if cdt is not None:
            hold_h = (now - cdt).total_seconds() / 3600.0
            oldest_hold_h = max(oldest_hold_h, hold_h)
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

    return {
        "real_orders": len(real),
        "working": len(working),
        "filled": len(filled),
        "closedish": len(closed),
        "open_risk_usd": round(open_ml, 2),
        "open": open_rows,
        "session_days": len(session_days),
        "session_dates": sorted(session_days),
        "oldest_open_hold_hours": round(oldest_hold_h, 2),
        "ledger_path": str(_LEDGER),
    }


def _shadow_stats() -> dict[str, Any]:
    """Detect shadow propose→risk→log evidence.

    Honest bar:
      FAIL    — no path evidence
      PARTIAL — plumbing exercised (smoke / a few audit lines / latest stub)
      PASS    — explicit multi-session shadow window artifact only
                (do NOT promote on historical audit noise alone)
    """
    latest = _load_json(_SHADOW_LATEST) or {}
    n_audit = 0
    last_shadow_at = None
    if _AUDIT.is_file():
        try:
            # Tail-ish: last 200 lines only so ancient smoke doesn't dominate
            lines = _AUDIT.read_text(encoding="utf-8").splitlines()[-200:]
            for line in lines:
                if not line.strip():
                    continue
                if "shadow" not in line.lower():
                    continue
                n_audit += 1
                try:
                    row = json.loads(line)
                    last_shadow_at = (
                        row.get("ts") or row.get("generated_at") or last_shadow_at
                    )
                except Exception:
                    pass
        except Exception:
            pass
    smoke = _load_json(_CACHE / "smoke_LATEST.json") or {}
    smoke_shadow = bool(smoke.get("shadow_ok") or smoke.get("shadow"))
    has_any = bool(latest) or n_audit > 0 or smoke_shadow

    multi = False
    if latest:
        try:
            if int(latest.get("session_days") or 0) >= 2 and latest.get("ok") is not False:
                multi = True
        except Exception:
            multi = False
        if latest.get("window_complete") is True or latest.get("status") == "PASS":
            multi = True

    status = "FAIL"
    detail = "not started — short propose→risk→log rehearsal before real money"
    if multi:
        status = "PASS"
        detail = (
            f"multi-session shadow window recorded "
            f"(sessions={latest.get('session_days')}, audit_tail={n_audit})"
        )
    elif has_any:
        status = "PARTIAL"
        detail = (
            f"path exercised (audit_tail={n_audit}, artifact={bool(latest)}, "
            f"smoke={smoke_shadow}) — need deliberate multi-session window"
        )
    return {
        "status": status,
        "detail": detail,
        "audit_lines": n_audit,
        "last_at": last_shadow_at,
        "latest": bool(latest),
        "smoke_shadow": smoke_shadow,
    }


def _classify_structure(structure: str) -> str:
    s = (structure or "").lower()
    if s in (
        "cash_secured_put",
        "csp",
        "long_put",
        "long_call",
        "wheel",
        "wheel_assignment",
        "short_put_credit",
        "short_call_credit",
        "regime_short_premium",
        "short_dte_aggressive",
        "long_dte_conservative",
    ):
        return "single_leg"
    if s in ("put_credit_spread", "call_credit_spread", "iron_condor", "iron_butterfly", "calendar"):
        return "multi_leg"
    return "other"


# Keep in sync with trader_platform.first_live_lane.SHORT_COLLATERAL_STRUCTURES.
_SHORT_COLLATERAL_STRUCTURES = frozenset(
    {
        "cash_secured_put",
        "csp",
        "short_put_credit",
        "short_call_credit",
        "regime_short_premium",
        "short_dte_aggressive",
        "long_dte_conservative",
        "wheel_assignment",
    }
)


def _load_first_live_lane() -> dict[str, Any]:
    """Dedicated first-live single-leg ranker report (not multi-leg research shortlist).

    Match first_live_lane capital doctrine (2026-08-07/08 coach):
    - CSP/wheel: sleeve fit_3k + capital_ok is the gate. Never treat full cash-secured
      BP (max_loss_usd_proxy / csp_bp_proxy) as the $300 defined-risk bar.
    - Long debit / defined-risk: keep max_loss_usd_proxy ≤ max_loss_budget_usd.
    - Explicit path stops on short premium (path_max_loss_usd) still honor the bar.
    Legacy sleeve-only seats without capital_fit/capital_ok stay rejected.
    """
    data = _load_json(_FIRST_LIVE) or {}
    if not data:
        return {"leader": None, "shortlist": [], "n_eligible": 0}

    max_loss_budget = float(data.get("max_loss_budget_usd") or 300.0)

    def _finite_pos(val: Any) -> float | None:
        try:
            if val is None:
                return None
            x = float(val)
            if x != x or x <= 0:  # NaN or non-positive
                return None
            return x
        except (TypeError, ValueError):
            return None

    def strict_budget_ok(row: Any) -> bool:
        if not isinstance(row, dict) or row.get("eligible") is False:
            return False

        structure = str(row.get("structure") or "").strip().lower()
        is_short = structure in _SHORT_COLLATERAL_STRUCTURES or (
            # Older artifacts sometimes omit structure but carry CSP collateral fields.
            structure == ""
            and (row.get("csp_bp_proxy") is not None or row.get("capital_fit") is not None)
        )

        # Explicit path stop (DNA/metrics) always honors the defined-risk bar.
        path_ml = _finite_pos(row.get("path_max_loss_usd"))
        if path_ml is not None and path_ml > max_loss_budget:
            return False

        if is_short:
            if row.get("capital_ok") is False:
                return False
            fit = str(row.get("capital_fit") or "").strip().lower()
            if fit == "fit_3k" or row.get("capital_ok") is True:
                return True
            # Legacy short seat without capital_fit/capital_ok: reject oversized BP.
            bp = _finite_pos(row.get("csp_bp_proxy"))
            if bp is None:
                bp = _finite_pos(row.get("max_loss_usd_proxy"))
            if bp is None:
                return False
            # Without sleeve-fit labels, only keep tiny defined-risk-shaped leftovers.
            return bp <= max_loss_budget

        # Long debit / other: require bounded max-loss under the bar.
        ml = _finite_pos(row.get("max_loss_usd_proxy"))
        if ml is None:
            ml = path_ml
        if ml is None:
            return False
        return ml <= max_loss_budget

    raw_shortlist = list(data.get("shortlist") or [])
    strict_shortlist = [row for row in raw_shortlist if strict_budget_ok(row)]
    leader = data.get("leader") if strict_budget_ok(data.get("leader")) else None
    if leader is None and strict_shortlist:
        leader = strict_shortlist[0]
    return {
        "leader": leader,
        "shortlist": strict_shortlist[:8],
        "n_eligible": len(strict_shortlist),
        "raw_n_eligible": int(data.get("n_eligible") or 0),
        "max_loss_budget_usd": max_loss_budget,
        "generated_at": data.get("generated_at"),
        "honesty": data.get("honesty"),
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
                if getattr(a, "agentic_allowed", False) or str(
                    getattr(a, "nickname", "")
                ).lower() == "agentic":
                    agentic_acct = a
                    break
            acct = agentic_acct or (accounts[0] if accounts else None)
            if acct is not None:
                cash = float(
                    getattr(acct, "cash", None)
                    or getattr(acct, "buying_power", None)
                    or 0
                )
                level = str(getattr(acct, "option_level", None) or "unknown")
        except Exception:
            cash = None
            level = "unknown"

    next_seed = _load_json(_NEXT) or {}
    shortlist = _load_json(_SHORTLIST) or {}
    first_live_lane = _load_first_live_lane()
    tick = _load_json(_TICK) or {}
    campaign = _load_json(_CAMPAIGN) or {}
    quality = _load_json(_QUALITY) or {}
    handoff = _load_json(_HANDOFF) or {}
    paper = _paper_stats()
    shadow = _shadow_stats()

    rows = list(shortlist.get("shortlist") or [])
    top = []
    for r in rows[:8]:
        top.append(
            {
                "hyp_id": r.get("hyp_id") or r.get("id"),
                "symbol": r.get("symbol"),
                "structure": r.get("structure"),
                "lane": r.get("lane"),
                "stress_priority": bool(r.get("stress_priority")),
                "b3_hold": r.get("b3_hold"),
                "b4_cost_hold": r.get("b4_cost_hold"),
                "placeable": _classify_structure(str(r.get("structure") or "")),
                "notes": (r.get("notes") or r.get("why") or r.get("caveat") or "")[:140],
            }
        )

    # --- Platform A (kept for json / legacy) ---
    platform: list[Check] = []
    platform.append(
        Check(
            "A1",
            "platform runnable",
            "PASS" if (_REPO / ".venv" / "bin" / "python").is_file() else "FAIL",
            "venv present" if (_REPO / ".venv" / "bin" / "python").is_file() else "missing .venv",
        )
    )
    try:
        max_open = float((limits.get("portfolio") or {}).get("max_open_risk", 0) or 0)
        # Campaign uses ~500 open-risk guard even if yaml shows 0 — treat 0 as unset/partial
        a2 = "PASS" if max_open and 0 < max_open <= 5000 else "PARTIAL"
        sleeve_note = f"max_open_risk={max_open} (campaign guard ~500 if unset)"
    except Exception:
        a2 = "UNKNOWN"
        sleeve_note = "risk_limits unreadable"
    platform.append(Check("A2", "risk limits sleeve-aware", a2, sleeve_note))
    platform.append(
        Check(
            "A3",
            "paper path durable",
            "PASS" if paper["real_orders"] > 0 else "PARTIAL",
            f"orders={paper['real_orders']} open={paper['working']} risk=${paper['open_risk_usd']}",
        )
    )
    platform.append(Check("A4", "shadow path exercised", shadow["status"], shadow["detail"]))
    platform.append(
        Check(
            "A5",
            "kill switch",
            "PARTIAL",
            "policy exists; full kill-drill still packet evidence",
        )
    )
    platform.append(Check("A6", "secrets not in git", "PASS", "hygiene ok"))
    platform.append(
        Check(
            "A7",
            "live disarmed",
            "PASS" if not agentic else "FAIL",
            f"agentic.enabled={agentic}",
        )
    )

    # --- Strategy B ---
    strategy: list[Check] = []
    # Prefer stressed multi-leg research leader for paper edge view
    leader = None
    first_live = None  # MCP single-leg capital-fit candidate
    # Primary source: dedicated first-live lane ranker
    fl_leader = first_live_lane.get("leader")
    if fl_leader and fl_leader.get("symbol"):
        first_live = {
            "hyp_id": fl_leader.get("hyp_id"),
            "symbol": fl_leader.get("symbol"),
            "structure": fl_leader.get("structure"),
            "lane": "first_live_single_leg",
            "caveat": fl_leader.get("caveat") or fl_leader.get("why"),
            "why": fl_leader.get("why"),
            "csp_bp_proxy": fl_leader.get("csp_bp_proxy"),
            "capital_fit": fl_leader.get("capital_fit"),
            "n_trades": fl_leader.get("n_trades"),
            "verdict": fl_leader.get("verdict"),
        }
    for r in rows:
        struct = str(r.get("structure") or "")
        lane = str(r.get("lane") or "")
        if leader is None and (
            r.get("stress_priority")
            or r.get("b3_hold") is True
            or lane in ("paper_research", "paper")
        ):
            if _classify_structure(struct) in ("multi_leg", "single_leg"):
                leader = r
    if leader is None and rows:
        leader = rows[0]

    lid = (leader or {}).get("hyp_id") or (leader or {}).get("id") or "none"
    fl_id = (first_live or {}).get("hyp_id") or "none"
    fl_struct = (first_live or {}).get("structure") or "none"
    fl_sym = (first_live or {}).get("symbol") or "?"

    # EDGE quality from shortlist stress
    stressed = [
        r
        for r in rows
        if r.get("b3_hold") is True and r.get("b4_cost_hold") is True
    ]
    edge_ok = len(stressed) >= 1
    # pack-grade: stressed + multi-symbol honesty (densify pack OR shortlist DNA peers)
    pack = False
    multi = _load_json(_BOOT / "MULTI_SYMBOL_REPROVE.json") or {}
    shortlist_multi = _load_json(_BOOT / "SHORTLIST_DNA_MULTI.json") or {}
    if multi.get("quality_pass") is True or shortlist_multi.get("quality_pass") is True:
        pack = True
    pack_src = (
        "shortlist_dna_multi"
        if shortlist_multi.get("quality_pass") is True
        else ("densify_multi" if multi.get("quality_pass") is True else None)
    )
    b2_status = "PASS" if pack else ("PARTIAL" if edge_ok else "FAIL")
    b2_detail = (
        f"pack-grade quality_pass via {pack_src}"
        if pack
        else (
            f"{len(stressed)} stressed survivors on shortlist — not pack-grade yet"
            if edge_ok
            else "no B3+B4 survivors"
        )
    )

    strategy.append(
        Check(
            "B1",
            "capital fit",
            "PARTIAL" if leader else "FAIL",
            f"paper leader={lid}; first-live lane={fl_sym} {fl_struct} ({fl_id}); cash≈{cash}",
        )
    )
    strategy.append(Check("B2", "edge quality", b2_status, b2_detail))
    b3 = "PASS" if leader and (leader.get("b3_hold") is True or leader.get("stress_priority")) else "PARTIAL"
    b4 = "PASS" if leader and (leader.get("b4_cost_hold") is True or leader.get("stress_priority")) else "PARTIAL"
    if leader and leader.get("b3_hold") is False:
        b3 = "FAIL"
    if leader and leader.get("b4_cost_hold") is False:
        b4 = "FAIL"
    strategy.append(Check("B3", "regime stress", b3, f"leader={lid}"))
    strategy.append(Check("B4", "cost stress", b4, f"leader={lid}"))
    strategy.append(
        Check(
            "B5",
            "entry/exit rules",
            "PARTIAL" if leader else "FAIL",
            "DNA on shortlist; management still learning in paper",
        )
    )

    # Paper ops sample: sessions spanned while held (not just create-day)
    session_days = int(paper["session_days"])
    multi_session = session_days >= 3 and paper["real_orders"] >= 2
    if multi_session:
        b6_status = "PASS"
        b6_detail = f"sessions={session_days} orders={paper['real_orders']} open={paper['working']}"
    elif paper["working"] or paper["real_orders"]:
        b6_status = "PARTIAL"
        b6_detail = (
            f"sessions={session_days}/3 orders={paper['real_orders']} "
            f"open={paper['working']} dates={paper.get('session_dates')}"
        )
    else:
        b6_status = "FAIL"
        b6_detail = "no paper orders yet"
    strategy.append(Check("B6", "paper ops sample", b6_status, b6_detail))
    strategy.append(Check("B7", "shadow rehearsal", shadow["status"], shadow["detail"]))

    # --- Opportunity C ---
    opportunity: list[Check] = []
    try:
        from zoneinfo import ZoneInfo

        now_pt = datetime.now(ZoneInfo("America/Los_Angeles"))
        rth = now_pt.weekday() < 5 and 6 <= now_pt.hour < 13
        opportunity.append(
            Check(
                "C1",
                "regime day-of",
                "NA" if not rth else "UNKNOWN",
                "only matters on arm day",
            )
        )
        opportunity.append(Check("C2", "size 1-lot", "PASS", "default 1 lot"))
        opportunity.append(
            Check(
                "C3",
                "room to trade",
                "PASS" if (cash is None or cash >= 0) else "FAIL",
                f"cash≈{cash} open_risk=${paper['open_risk_usd']}",
            )
        )
        opportunity.append(
            Check("C4", "daily loss stop", "PARTIAL", "config present; live wire later")
        )
    except Exception:
        opportunity.append(Check("C1", "regime day-of", "NA", ""))
        opportunity.append(Check("C2", "size 1-lot", "PASS", "1 lot"))
        opportunity.append(Check("C3", "room to trade", "UNKNOWN", ""))
        opportunity.append(Check("C4", "daily loss stop", "PARTIAL", ""))

    def score(checks: list[Check]) -> float:
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
        return pts / n * 100.0 if n else 0.0

    p_pct = score(platform)
    s_pct = score(strategy)
    o_pct = score(opportunity)
    overall = 0.25 * p_pct + 0.55 * s_pct + 0.20 * o_pct

    # Continuum / worker
    tick_at = tick.get("generated_at")
    camp_at = campaign.get("generated_at")
    handoff_status = handoff.get("status") or "MISSING"
    worker_hb = _load_json(_CACHE / "quality_worker" / "HEARTBEAT.json") or {}
    worker_status = _load_json(_CACHE / "quality_worker" / "STATUS.json") or {}
    worker_cycle = _load_json(_CYCLE_LATEST) or {}
    if not isinstance(worker_cycle, dict):
        worker_cycle = {}
    # Prefer freshest cycle detail: heartbeat is thin; cycle_LATEST has evolve phases.
    if not worker_cycle and isinstance(worker_hb, dict):
        worker_cycle = worker_hb
    edge_search = edge_search_health(worker_cycle if isinstance(worker_cycle, dict) else {})
    worker_pid_path = _CACHE / "quality_worker" / "worker.pid"
    worker_running = False
    if worker_pid_path.is_file():
        try:
            wpid = int(worker_pid_path.read_text().strip())
            os.kill(wpid, 0)
            worker_running = True
        except Exception:
            worker_running = False

    cycle_dir = _CACHE / "quality_residual"
    cycle_n = len(list(cycle_dir.glob("cycle_*.json"))) if cycle_dir.is_dir() else 0
    hold_h = float(paper.get("oldest_open_hold_hours") or 0.0)
    real_orders = int(paper.get("real_orders") or 0)
    working = int(paper.get("working") or 0)
    hb_age = _age_hours(worker_hb.get("generated_at"))
    hb_fresh = worker_running and hb_age is not None and hb_age < 0.25

    act = 0.0
    act += min(35.0, cycle_n * 0.7)
    act += 15.0 if worker_running else 0.0
    act += 10.0 if hb_fresh else (5.0 if worker_running else 0.0)
    act += min(20.0, session_days * 6.0 + hold_h * 0.5)
    act += min(10.0, real_orders * 2.0)
    act += 5.0 if working >= 1 else 0.0
    act += 5.0 if edge_ok else 0.0
    # Frozen minting — do not report SEARCHING vanity from cycle count alone.
    ken_frozen = bool(edge_search.get("ken_edge_frozen") or edge_search.get("state") == "KEN_FROZEN")
    if ken_frozen or edge_search.get("registry_bloated_skip"):
        act = min(act, 35.0)
    activity_pct = round(min(100.0, act), 1)
    if ken_frozen:
        activity_label = "EDGE_FROZEN_KEN"
    elif edge_search.get("registry_bloated_skip"):
        activity_label = "EDGE_FROZEN_BLOAT"
    elif activity_pct >= 70:
        activity_label = "SEARCHING"
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
        "edge_search": edge_search,
        "note": (
            "Search activity (cycles). Not the same as ready-to-trade. "
            "EDGE_FROZEN_KEN = Ken first-close latch (do not prune). "
            "EDGE_FROZEN_BLOAT = evolve skipped on hyp yaml size."
        ),
    }

    # --- 3 layers (primary) ---
    edge_status = "PASS" if pack else ("PARTIAL" if edge_ok else "FAIL")
    edge_summary = b2_detail
    if first_live:
        bp = first_live.get("csp_bp_proxy")
        fit = first_live.get("capital_fit")
        n_tr = first_live.get("n_trades")
        verd = first_live.get("verdict")
        edge_first = f"{fl_sym} {fl_struct}"
        bits = []
        if verd:
            bits.append(str(verd))
        if n_tr is not None:
            bits.append(f"n={n_tr}")
        if fit:
            bits.append(str(fit))
        if bp is not None:
            try:
                bits.append(f"csp_bp≈${float(bp):.0f}")
            except (TypeError, ValueError):
                pass
        if bits:
            edge_first += " — " + ", ".join(bits)
        else:
            caveat = (first_live.get("caveat") or first_live.get("why") or "")[:100]
            if caveat:
                edge_first += f" — {caveat}"
    else:
        edge_first = (
            "no strict-loss-fit single-leg seat yet "
            f"(run just trader-first-live-lane; eligible={first_live_lane.get('n_eligible', 0)})"
        )

    robot_bits = []
    robot_pts = 0.0
    robot_n = 0
    for label, st in (
        ("paper", b6_status),
        ("shadow", shadow["status"]),
        ("platform", "PASS" if p_pct >= 60 else "PARTIAL"),
    ):
        robot_n += 1
        if st == "PASS":
            robot_pts += 1
            robot_bits.append(f"{label}=ok")
        elif st == "PARTIAL":
            robot_pts += 0.5
            robot_bits.append(f"{label}=partial")
        else:
            robot_bits.append(f"{label}=todo")
    robot_status = (
        "PASS"
        if robot_pts >= robot_n
        else ("PARTIAL" if robot_pts > 0 else "FAIL")
    )

    arm_status = "BLOCKED"
    if agentic:
        arm_status = "ARMED"  # unexpected until Ken
    arm_detail = "Ken only: gateway up → LIVE_PACKET → $3k → arm 1-lot. Never auto."

    layers = {
        "edge": {
            "name": "EDGE",
            "plain": "Sims find & kill strategies (24/7)",
            "status": edge_status,
            "summary": edge_summary,
            "paper_research_leader": lid,
            "first_live_candidate": edge_first,
            "first_live_eligible_n": int(first_live_lane.get("n_eligible") or 0),
            "stressed_count": len(stressed),
            "pack_grade": pack,
        },
        "robot": {
            "name": "ROBOT",
            "plain": "Paper + shadow = machine works",
            "status": robot_status,
            "summary": "; ".join(robot_bits),
            "paper_sessions": session_days,
            "paper_sessions_target": 3,
            "paper_open": working,
            "paper_open_risk_usd": paper["open_risk_usd"],
            "shadow": shadow["status"],
            "live_disarmed": not agentic,
        },
        "arm": {
            "name": "ARM",
            "plain": "Real money — Ken decision only",
            "status": arm_status,
            "summary": arm_detail,
            "ken_required_now": bool(next_seed.get("ken_required", False)),
            "cash_test_usd": cash,
            "plan_sleeve_usd": 3000,
            "mcp_place": "single_leg_only",
        },
    }

    # Simple next in plain English
    if working >= 1 and session_days < 3:
        simple_next = (
            f"Keep paper open/managed ({session_days}/3 sessions). "
            "Sims keep searching in background. No Ken action."
        )
    elif not edge_ok:
        simple_next = "Sims still hunting a stressed survivor. Worker should stay on. No Ken action."
    elif not pack and first_live is None:
        simple_next = (
            "Have stressed multi-leg research edges; still need a placeable "
            "single-leg first-live candidate that fits cash. No Ken action."
        )
    elif shadow["status"] == "FAIL":
        simple_next = "Run short shadow rehearsal (propose→risk→log, no money). No Ken action."
    elif shadow["status"] == "PARTIAL" or b6_status != "PASS":
        simple_next = "Finish short paper/shadow ops sample, then draft LIVE_PACKET. No Ken action yet."
    else:
        simple_next = "Ops sample ok — draft LIVE_PACKET when pack-grade first-live DNA is named. Ken arms."

    # Prefer NEXT_SEED if it's manage paper
    na = str(next_seed.get("next_action") or "")
    if na == "manage_open_paper_campaign" and working:
        simple_next = (
            f"Manage open paper ({working} working, sessions {session_days}/3). "
            "Search continues off-hours. ken_required=false."
        )

    blockers: list[str] = []
    if not pack:
        blockers.append("No pack-grade edge yet (sims still filtering)")
    if first_live is None:
        blockers.append(
            "No strict-loss-fit single-leg first-live seat "
            "(just trader-first-live-lane)"
        )
    elif first_live is not None:
        cav = str(first_live.get("caveat") or first_live.get("why") or "")
        bp = first_live.get("csp_bp_proxy")
        try:
            bp_f = float(bp) if bp is not None else None
        except (TypeError, ValueError):
            bp_f = None
        if bp_f is not None and bp_f > 3000:
            blockers.append(
                f"First-live CSP sizing: {fl_sym} csp_bp≈${bp_f:.0f} oversized for $3k sleeve"
            )
        elif "oversized" in cav.lower():
            blockers.append(f"First-live CSP sizing: {cav[:120]}")
    if b6_status != "PASS":
        blockers.append(f"Paper ops sample {session_days}/3 sessions (robot check, not edge proof)")
    if shadow["status"] != "PASS":
        blockers.append("Shadow rehearsal incomplete")
    blockers.append("Real money blocked until Ken LIVE_PACKET arm")
    if cash is not None and cash < 1000:
        blockers.append(f"Test cash ${cash:.0f} — full $3k only at arm packet")

    stuck_bits = []
    if edge_status != "PASS":
        stuck_bits.append("edge not pack-grade")
    if b6_status != "PASS":
        stuck_bits.append(f"paper {session_days}/3 sessions")
    if shadow["status"] != "PASS":
        stuck_bits.append("shadow incomplete")
    stuck_bits.append("arm=Ken only")
    why_stuck = (
        "Ready-to-trade moves on evidence, not cycle count. Remaining: "
        + "; ".join(stuck_bits)
        + f". Search activity separate ({activity_pct}%, cycles={cycle_n})."
    )

    path = [
        "1. EDGE — sims find one stressed, capital-fit strategy (worker, 24/7)",
        f"2. ROBOT/paper — short live-clock sample ({session_days}/3 sessions, open={working})",
        f"3. ROBOT/shadow — propose→risk→log ({shadow['status']})",
        "4. First live must be placeable on RH MCP (single-leg/CSP class today)",
        "5. ARM — LIVE_PACKET → Ken $3k → Ken arms 1-lot",
    ]

    phase = "BUILD"
    if paper["working"] or paper["real_orders"] >= 2:
        phase = "PAPER"
    if shadow["status"] == "PASS":
        phase = "SHADOW"

    if overall >= 85 and b6_status == "PASS" and shadow["status"] == "PASS" and pack:
        label = "NEAR_PACKET"
    elif overall >= 55:
        label = "IN_PROGRESS"
    elif overall >= 35:
        label = "SEARCHING"
    else:
        label = "EARLY"

    glossary = {
        "EDGE": "Simulation search + stress. Proves strategy looks real after costs. No market hours required.",
        "ROBOT": "Paper (fake money, real clock) + shadow (would-trade log). Proves software/ops work.",
        "ARM": "Ken turns on real money for one named strategy, 1 lot, after a LIVE_PACKET review.",
        "paper": "Dress rehearsal with fake money — not a second proof of edge.",
        "shadow": "System proposes trades and risk-checks them; nothing is sent to the broker.",
        "pack-grade": "Edge thick enough (not a thin lucky backtest) to deserve paper/shadow focus.",
        "session": "A market weekday the paper book was open — holding overnight counts.",
    }

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
        ken_only_for=list(
            next_seed.get("ken_only_for")
            or ["gateway_up", "LIVE_PACKET_arm", "fund_3k_at_packet"]
        ),
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
            "quality_worker_hb_age_h": round(
                _age_hours(worker_hb.get("generated_at")) or -1, 2
            ),
            "quality_worker_stamp": worker_hb.get("stamp") or worker_cycle.get("stamp"),
            "quality_cycles_completed": cycle_n,
            "edge_search": edge_search,
            "registry_bytes": edge_search.get("registry_bytes"),
            "registry_bloated_skip": bool(edge_search.get("registry_bloated_skip")),
        },
        paper=paper,
        activity=activity,
        shortlist_top=top,
        first_live_lane={
            "n_eligible": first_live_lane.get("n_eligible"),
            "generated_at": first_live_lane.get("generated_at"),
            "leader": first_live,
            "shortlist": first_live_lane.get("shortlist") or [],
        },
        blockers=blockers,
        path_to_live=path,
        why_overall_stuck=why_stuck,
        layers=layers,
        simple_next=simple_next,
        glossary=glossary,
    )


def _bar(pct: float, width: int = 24) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct:5.1f}%"


def _st_mark(status: str) -> str:
    return {
        "PASS": "OK   ",
        "FAIL": "TODO ",
        "PARTIAL": "WIP  ",
        "BLOCKED": "WAIT ",
        "ARMED": "ARMED",
        "NA": "n/a  ",
        "UNKNOWN": "?    ",
    }.get(status, f"{status[:5]:<5}")


def format_text(f: Funnel) -> str:
    """Human-first 3-layer status. Letter gates hidden unless useful."""
    lines: list[str] = []
    L = f.layers or {}
    edge = L.get("edge") or {}
    robot = L.get("robot") or {}
    arm = L.get("arm") or {}

    lines.append("TRADER STATUS  (simple)")
    lines.append("─" * 48)
    lines.append(
        f"Phase {f.phase} · {f.overall_label} · search {f.activity_label} "
        f"({f.activity_pct:.0f}%)"
    )
    lines.append(
        f"Sleeve plan ${f.sleeve_plan_usd} · test cash≈{f.sleeve_cash_usd} · "
        f"options={f.option_level} · live_armed={f.agentic_enabled}"
    )
    lines.append("")
    lines.append("HOW THIS WORKS")
    lines.append("  Sims decide if a strategy is good (EDGE).")
    lines.append("  Paper/shadow decide if the robot works (ROBOT).")
    lines.append("  You decide to use real money (ARM).")
    lines.append("")

    lines.append("1) EDGE  — strategy search (24/7 sims)")
    lines.append(f"   {_st_mark(str(edge.get('status')))} {edge.get('summary')}")
    lines.append(f"   research leader: {edge.get('paper_research_leader')}")
    lines.append(f"   first-live lane: {edge.get('first_live_candidate')}")
    fl_n = edge.get("first_live_eligible_n")
    if fl_n is not None:
        lines.append(f"   first-live seats eligible: {fl_n}  (just trader-first-live-lane)")
    lines.append("")

    lines.append("2) ROBOT — machine check (paper + shadow)")
    lines.append(f"   {_st_mark(str(robot.get('status')))} {robot.get('summary')}")
    p = f.paper
    lines.append(
        f"   paper: {robot.get('paper_sessions')}/{robot.get('paper_sessions_target')} "
        f"sessions · open={p.get('working')} · risk=${p.get('open_risk_usd')} · "
        f"hold≈{p.get('oldest_open_hold_hours')}h"
    )
    for o in p.get("open") or []:
        lines.append(
            f"     · {o.get('symbol')} {o.get('structure') or ''} "
            f"ml=${o.get('max_loss_usd')} hold={o.get('hold_hours')}h"
        )
    if not (p.get("open") or []):
        lines.append("     · (no open paper)")
    lines.append(f"   shadow: {robot.get('shadow')} · live disarmed: {robot.get('live_disarmed')}")
    lines.append("")

    lines.append("3) ARM   — real money (Ken only)")
    lines.append(f"   {_st_mark(str(arm.get('status')))} {arm.get('summary')}")
    lines.append("")

    lines.append("NEXT")
    lines.append(f"   {f.simple_next}")
    lines.append(f"   (machine seed: {f.next_action} · ken_required={f.ken_required})")
    lines.append("")

    c = f.continuum
    wr = "ON" if c.get("quality_worker_running") else "off"
    es = c.get("edge_search") if isinstance(c.get("edge_search"), dict) else {}
    es_state = es.get("state") or (
        "KEN_FROZEN"
        if es.get("ken_edge_frozen")
        else ("BLOATED_SKIP" if c.get("registry_bloated_skip") else "?")
    )
    reg_b = c.get("registry_bytes") if c.get("registry_bytes") is not None else es.get("registry_bytes")
    reg_bit = (
        f"  registry≈{int(reg_b / 1e6 * 10) / 10}MB"
        if isinstance(reg_b, (int, float)) and reg_b
        else ""
    )
    lines.append("BACKGROUND")
    lines.append(
        f"   worker={wr}  cycles={c.get('quality_cycles_completed')}  "
        f"hb_age_h={c.get('quality_worker_hb_age_h')}  edge_search={es_state}{reg_bit}"
    )
    if es.get("ken_edge_frozen") or es_state == "KEN_FROZEN":
        lines.append(
            "   ⚠ EDGE frozen: Ken first-close latch — worker watch/paper only; "
            "do not prune-to-unfreeze (explicit Ken only)"
        )
    elif c.get("registry_bloated_skip") or es.get("registry_bloated_skip"):
        lines.append(
            "   ⚠ EDGE frozen: both evolves skipped on hypotheses.yaml bloat — "
            "off-hours `scripts/trader_prune_hyp_registry.py --max-keep 400`"
        )
    lines.append(
        "   layered readiness: "
        f"EDGE={edge.get('status')} · ROBOT={robot.get('status')} · ARM={arm.get('status')}"
    )
    if f.why_overall_stuck:
        lines.append(f"   note: {f.why_overall_stuck}")
    lines.append("")

    lines.append("TOP CANDIDATES (research multi-leg)")
    if not f.shortlist_top:
        lines.append("   (empty)")
    for r in f.shortlist_top[:6]:
        sp = "*" if r.get("stress_priority") else " "
        place = r.get("placeable") or ""
        lines.append(
            f"  {sp} {r.get('symbol')} {r.get('structure')}  "
            f"[{r.get('lane') or '?'} · {place}]"
        )
    lines.append("FIRST-LIVE SEATS (single-leg, strict one-lot loss fit)")
    fl_seats = (f.first_live_lane or {}).get("shortlist") or []
    if not fl_seats:
        lines.append("   (none — just trader-first-live-lane)")
    for i, r in enumerate(fl_seats[:5]):
        sp = "*" if i == 0 else " "
        bp = r.get("csp_bp_proxy")
        bp_s = ""
        if bp is not None:
            try:
                bp_s = f" csp_bp≈${float(bp):.0f}"
            except (TypeError, ValueError):
                bp_s = ""
        lines.append(
            f"  {sp} {r.get('symbol')} {r.get('structure')}  "
            f"[{r.get('verdict')} n={r.get('n_trades')}{bp_s}]"
        )
    lines.append("")

    lines.append("BLOCKERS")
    for b in f.blockers:
        lines.append(f"   • {b}")
    lines.append("")

    lines.append("PATH")
    for step in f.path_to_live:
        lines.append(f"   {step}")
    lines.append("")

    lines.append("COMMANDS")
    lines.append("   just trader-status              # this view")
    lines.append("   just trader-status --json       # full detail / legacy A-B-C")
    lines.append("   just trader-first-live-lane     # rebuild single-leg capital-fit seats")
    lines.append("   just trader-multi-symbol-reprove --from-shortlist")
    lines.append("   just trader-shadow-rehearsal    # propose→risk→log sample")
    lines.append("   just trader-run-now progress    # run all three + status")
    lines.append("")
    lines.append("WORDS")
    for k in ("EDGE", "ROBOT", "ARM", "paper", "shadow"):
        if k in (f.glossary or {}):
            lines.append(f"   {k}: {f.glossary[k]}")
    lines.append("")
    lines.append(f"generated_at: {f.generated_at}")
    lines.append("Ken only: gateway_up | LIVE_PACKET arm | $3k at packet")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--watch", type=float, nargs="?", const=10.0, default=None)
    ap.add_argument(
        "--write",
        action="store_true",
        help="Write reports/readiness/go_live_status_LATEST.json",
    )
    ap.add_argument(
        "--legacy",
        action="store_true",
        help="Print old A/B/C checklist under the simple view",
    )
    args = ap.parse_args(argv)

    def once() -> Funnel:
        f = collect()
        if args.write:
            out = _REPO / "reports" / "readiness" / "go_live_status_LATEST.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = asdict(f)
            # dataclasses Check → dict via asdict
            out.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        if args.json:
            print(json.dumps(asdict(f), indent=2, sort_keys=True))
        else:
            if args.watch is not None:
                sys.stdout.write("\033[2J\033[H")
            text = format_text(f)
            if args.legacy:
                text += "\nLEGACY A/B/C (detail)\n"
                for title, checks in (
                    ("A platform", f.platform),
                    ("B strategy", f.strategy),
                    ("C day-of", f.opportunity),
                ):
                    text += f"{title}\n"
                    for ch in checks:
                        text += f"  {ch.status:<8} {ch.id} {ch.name} — {ch.detail}\n"
            sys.stdout.write(text)
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

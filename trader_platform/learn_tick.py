"""Learn tick v0 — evaluate hypotheses from outcomes and improve the registry.

Pipeline (paper / research only):
  1. Gather outcomes: paper ledger + autonomy audit + last research run
  2. Score each eligible hypothesis → verdict + recommended status
  3. Optionally apply safe status transitions (never live / never shadow auto)
  4. Append durable learn audit + optional RESEARCH_SCOREBOARD row

Ownership:
  - CoS worker lane: multi-symbol research rank + promote-top → candidates
  - This module: outcome evaluation + self-learning transitions (candidate/testing/paper)

Hard rules:
  - Never place_* / agentic_live / fund
  - Never auto-transition to live or shadow
  - Stand-aside is success, not failure
  - Prefer NULL / NEEDS_MORE_DATA over optimistic SHIP

Usage:
  .venv/bin/python -m trader_platform.learn_tick --once
  .venv/bin/python -m trader_platform.learn_tick --once --apply
  .venv/bin/python -m trader_platform.learn_tick --once --apply --append-scoreboard
  .venv/bin/python -m trader_platform.learn_tick --once --json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trader_platform.hypothesis_registry import Hypothesis, HypothesisRegistry, TRANSITIONS

_REPO = Path(__file__).resolve().parents[1]
_CACHE = _REPO / ".cache" / "platform"
_LEDGER = _CACHE / "paper_ledger.json"
_AUDIT = _CACHE / "autonomy_audit.jsonl"
_RESEARCH_DB = _CACHE / "research.db"
_LEARN_AUDIT = _CACHE / "learn_audit.jsonl"
_SCOREBOARD = _REPO / "docs" / "RESEARCH_SCOREBOARD.md"

# Auto-apply ceiling: learn tick may move within this set only.
SAFE_STATUSES = frozenset({"candidate", "testing", "paper", "rejected", "retired"})
FORBIDDEN_AUTO = frozenset({"shadow", "live"})


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _today() -> str:
    return datetime.now().date().isoformat()


@dataclass
class HypOutcome:
    hypothesis_id: str
    name: str
    status: str
    sleeve: str
    instruments: list[str]
    paper_orders: int = 0
    paper_working: int = 0
    paper_filled: int = 0
    paper_cancelled: int = 0
    audit_intents: int = 0
    audit_stand_asides: int = 0
    audit_risk_blocks: int = 0
    research_rank: Optional[int] = None
    research_composite: Optional[float] = None
    research_capital_fit: str = ""
    evidence_n: int = 0
    null_n: int = 0
    verdict: str = "NEEDS_MORE_DATA"  # SHIP|NULL|REJECT|NEEDS_MORE_DATA|SHADOW|BASELINE
    recommended_status: Optional[str] = None  # None = no change
    reason: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LearnReport:
    ts: str
    applied: bool
    dry_run: bool
    n_hyps: int
    outcomes: list[HypOutcome] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    scoreboard_appended: bool = False
    audit_path: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "applied": self.applied,
            "dry_run": self.dry_run,
            "n_hyps": self.n_hyps,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "transitions": list(self.transitions),
            "scoreboard_appended": self.scoreboard_appended,
            "audit_path": self.audit_path,
            "errors": list(self.errors),
        }


def load_paper_ledger(path: Path | None = None) -> dict[str, Any]:
    p = path or _LEDGER
    if not p.exists():
        return {"orders": {}, "events": []}
    with p.open() as f:
        return json.load(f) or {"orders": {}, "events": []}


def load_audit_tail(path: Path | None = None, max_lines: int = 500) -> list[dict[str, Any]]:
    p = path or _AUDIT
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def load_latest_research_by_symbol(db_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Map symbol → best row from latest research run (if any)."""
    db = db_path or _RESEARCH_DB
    if not db.exists():
        return {}
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        rid = cur.execute(
            "SELECT id FROM research_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not rid:
            con.close()
            return {}
        run_id = int(rid[0])
        # Prefer opportunities rank; fall back to symbol_scores
        rows = cur.execute(
            "SELECT * FROM opportunities WHERE run_id=? ORDER BY rank ASC",
            (run_id,),
        ).fetchall()
        by: dict[str, dict[str, Any]] = {}
        if rows:
            for r in rows:
                d = dict(r)
                sym = str(d.get("symbol") or "").upper()
                if sym and sym not in by:
                    by[sym] = d
        else:
            scores = cur.execute(
                "SELECT * FROM symbol_scores WHERE run_id=? AND (error IS NULL OR error='') "
                "ORDER BY composite DESC",
                (run_id,),
            ).fetchall()
            for i, r in enumerate(scores, start=1):
                d = dict(r)
                d.setdefault("rank", i)
                sym = str(d.get("symbol") or "").upper()
                if sym and sym not in by:
                    by[sym] = d
        con.close()
        return by
    except sqlite3.Error:
        return {}


def _paper_stats_for_hyp(ledger: dict[str, Any], hyp_id: str) -> dict[str, int]:
    orders = (ledger.get("orders") or {}).values()
    n = w = f = c = 0
    for o in orders:
        if str(o.get("strategy_id") or "") != hyp_id:
            continue
        n += 1
        st = str(o.get("status") or "").lower()
        if st in ("working", "open", "partial"):
            w += 1
        elif st in ("filled", "done"):
            f += 1
        elif st in ("cancelled", "canceled", "rejected"):
            c += 1
    return {"orders": n, "working": w, "filled": f, "cancelled": c}


def _audit_stats_for_hyp(events: list[dict[str, Any]], hyp_id: str) -> dict[str, int]:
    intents = stand = blocks = 0
    for e in events:
        intent = e.get("intent") or {}
        sid = str(intent.get("strategy_id") or e.get("strategy_id") or "")
        ev = str(e.get("event") or "")
        if sid == hyp_id:
            if ev in ("paper_place", "shadow_propose", "risk_check", "smoke_test") or intent:
                intents += 1
            risk = e.get("risk") or {}
            if risk.get("allowed") is False:
                blocks += 1
        if ev == "stand_aside" and (
            sid == hyp_id or hyp_id in str(e.get("reason") or "")
        ):
            stand += 1
        # scout stand_asides often lack strategy_id — count global lightly via tag
        if ev == "stand_aside" and not sid:
            stand += 0  # global only; don't attribute
    return {"intents": intents, "stand_asides": stand, "risk_blocks": blocks}


def evaluate_hypothesis(
    h: Hypothesis,
    *,
    ledger: dict[str, Any],
    audit: list[dict[str, Any]],
    research_by_sym: dict[str, dict[str, Any]],
) -> HypOutcome:
    paper = _paper_stats_for_hyp(ledger, h.id)
    au = _audit_stats_for_hyp(audit, h.id)
    rank = None
    composite = None
    cap_fit = ""
    for inst in h.instruments:
        row = research_by_sym.get(inst.upper())
        if row:
            rank = int(row.get("rank") or rank or 0) or None
            try:
                composite = float(row.get("composite") or 0) or None
            except (TypeError, ValueError):
                composite = None
            cap_fit = str(row.get("capital_fit") or row.get("capital_fit_long") or "")
            break
    # Research hyp ids embed symbol
    if rank is None and h.id.startswith("hyp_research_"):
        m = re.match(r"hyp_research_([a-z0-9]+)_", h.id)
        if m:
            sym = m.group(1).upper()
            row = research_by_sym.get(sym)
            if row:
                rank = int(row.get("rank") or 0) or None
                try:
                    composite = float(row.get("composite") or 0) or None
                except (TypeError, ValueError):
                    composite = None
                cap_fit = str(row.get("capital_fit") or "")

    out = HypOutcome(
        hypothesis_id=h.id,
        name=h.name,
        status=h.status,
        sleeve=h.sleeve,
        instruments=list(h.instruments),
        paper_orders=paper["orders"],
        paper_working=paper["working"],
        paper_filled=paper["filled"],
        paper_cancelled=paper["cancelled"],
        audit_intents=au["intents"],
        audit_stand_asides=au["stand_asides"],
        audit_risk_blocks=au["risk_blocks"],
        research_rank=rank,
        research_composite=composite,
        research_capital_fit=cap_fit,
        evidence_n=len(h.evidence_links or []),
        null_n=len(h.null_results or []),
    )

    # Cash sleeve: stand-aside success
    if h.sleeve == "cash":
        out.verdict = "BASELINE"
        out.recommended_status = None
        out.reason = "cash/stand-aside sleeve — keep as testing baseline; not a ship path"
        return out

    # Already terminal
    if h.status in ("rejected", "retired", "live"):
        out.verdict = "BASELINE" if h.status == "live" else "NULL"
        out.recommended_status = None
        out.reason = f"status={h.status} — learn tick does not auto-change terminal/live"
        return out

    if h.status == "shadow":
        out.verdict = "SHADOW"
        out.recommended_status = None
        out.reason = "shadow is human/gated — learn tick never auto-promotes to/from shadow→live"
        return out

    # --- Decision policy (conservative) ---
    # candidate → testing when research ranks in top band OR has evidence + capital fit
    if h.status == "candidate":
        strong_research = (
            rank is not None
            and rank <= 10
            and (composite is None or composite >= 50)
            and cap_fit not in ("oversized",)
        )
        if strong_research or (out.evidence_n >= 1 and out.paper_orders + out.audit_intents > 0):
            out.verdict = "NEEDS_MORE_DATA"
            out.recommended_status = "testing"
            out.reason = (
                f"promote candidate→testing: research_rank={rank} composite={composite} "
                f"cap_fit={cap_fit} evidence_n={out.evidence_n}"
            )
        else:
            out.verdict = "NEEDS_MORE_DATA"
            out.recommended_status = None
            out.reason = "candidate stays — weak/absent research rank or evidence"
        return out

    # testing → paper only with real paper activity + evidence (still not live)
    if h.status == "testing":
        if out.audit_risk_blocks >= 3 and out.paper_orders == 0 and out.audit_intents == 0:
            out.verdict = "REJECT"
            out.recommended_status = None  # do not auto-reject without --allow-reject
            out.reason = "repeated risk blocks with no paper activity — flag only (use --allow-reject)"
            out.notes.append("manual review recommended")
            return out
        if out.paper_orders >= 1 and out.evidence_n >= 1:
            out.verdict = "NEEDS_MORE_DATA"
            out.recommended_status = "paper"
            out.reason = (
                f"testing→paper: paper_orders={out.paper_orders} evidence_n={out.evidence_n} "
                "(paper sleeve only; no live)"
            )
            return out
        if out.paper_orders == 0 and out.audit_intents == 0 and rank is None and out.evidence_n == 0:
            out.verdict = "NULL"
            out.recommended_status = None
            out.reason = "no activity and no research signal — log null; no status change"
            return out
        out.verdict = "NEEDS_MORE_DATA"
        out.recommended_status = None
        out.reason = (
            f"testing hold: paper_orders={out.paper_orders} intents={out.audit_intents} "
            f"rank={rank} — need more evidence for paper promotion"
        )
        return out

    # paper — gather more data; never auto shadow/live
    if h.status == "paper":
        if out.paper_filled >= 3 and out.paper_cancelled == 0:
            out.verdict = "SHADOW"
            out.recommended_status = None
            out.reason = (
                f"paper showing fills={out.paper_filled} — human gate to shadow "
                "(run scenarios + promotion_gates; learn tick will not auto-shadow)"
            )
            return out
        out.verdict = "NEEDS_MORE_DATA"
        out.recommended_status = None
        out.reason = "paper sleeve collecting outcomes; no auto-escalation"
        return out

    out.verdict = "NEEDS_MORE_DATA"
    out.reason = f"unhandled status={h.status}"
    return out


def apply_transition(
    reg: HypothesisRegistry,
    outcome: HypOutcome,
    *,
    allow_reject: bool = False,
    force: bool = False,
) -> Optional[dict[str, Any]]:
    target = outcome.recommended_status
    if target is None:
        if outcome.verdict == "REJECT" and allow_reject and outcome.status in ("candidate", "testing"):
            target = "rejected"
        else:
            return None
    if target in FORBIDDEN_AUTO:
        return {
            "hypothesis_id": outcome.hypothesis_id,
            "from": outcome.status,
            "to": target,
            "ok": False,
            "error": "forbidden auto target",
        }
    if target not in SAFE_STATUSES:
        return {
            "hypothesis_id": outcome.hypothesis_id,
            "from": outcome.status,
            "to": target,
            "ok": False,
            "error": "target not in SAFE_STATUSES",
        }
    if target == outcome.status:
        return None
    allowed = TRANSITIONS.get(outcome.status, set())
    if not force and target not in allowed:
        return {
            "hypothesis_id": outcome.hypothesis_id,
            "from": outcome.status,
            "to": target,
            "ok": False,
            "error": f"illegal transition; allowed={sorted(allowed)}",
        }
    try:
        evidence = (
            f"learn_tick:{_today()}:{outcome.verdict}:{outcome.reason[:120]}"
        )
        h = reg.transition(
            outcome.hypothesis_id,
            target,
            evidence_link=evidence,
            force=force,
            allow_live_without_evidence=False,
        )
        # Append null when NULL/REJECT
        if outcome.verdict in ("NULL", "REJECT"):
            store = reg.load()
            for i, raw in enumerate(store["hypotheses"]):
                if raw.get("id") == outcome.hypothesis_id:
                    nulls = list(raw.get("null_results") or [])
                    note = f"{_today()} learn_tick {outcome.verdict}: {outcome.reason[:200]}"
                    if note not in nulls:
                        nulls.append(note)
                    raw["null_results"] = nulls
                    store["hypotheses"][i] = raw
                    reg.save(store)
                    break
        return {
            "hypothesis_id": outcome.hypothesis_id,
            "from": outcome.status,
            "to": h.status,
            "ok": True,
            "evidence": evidence,
        }
    except Exception as exc:  # noqa: BLE001 — tick must not crash cron
        return {
            "hypothesis_id": outcome.hypothesis_id,
            "from": outcome.status,
            "to": target,
            "ok": False,
            "error": str(exc),
        }


def append_learn_audit(report: LearnReport, path: Path | None = None) -> Path:
    p = path or _LEARN_AUDIT
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report.to_dict(), default=str) + "\n")
    report.audit_path = str(p)
    return p


def append_scoreboard_rows(outcomes: list[HypOutcome]) -> bool:
    """Append one markdown table row per actionable outcome (idempotent by day+id+verdict)."""
    if not _SCOREBOARD.exists():
        return False
    text = _SCOREBOARD.read_text(encoding="utf-8")
    # Find the SHIP/NULL log table — append before section 5 if possible
    rows: list[str] = []
    for o in outcomes:
        if o.verdict == "BASELINE" and o.recommended_status is None and o.sleeve == "cash":
            continue
        marker = f"| {_today()} | learn_tick:{o.hypothesis_id} |"
        if marker in text:
            continue
        surfaces = []
        if o.research_rank is not None:
            surfaces.append(f"research_rank={o.research_rank}")
        if o.paper_orders:
            surfaces.append(f"paper_orders={o.paper_orders}")
        if o.audit_intents:
            surfaces.append(f"audit_intents={o.audit_intents}")
        surf = ", ".join(surfaces) or "learn_tick outcomes"
        metrics = (
            f"status={o.status}→{o.recommended_status or o.status}; "
            f"comp={o.research_composite}; cap={o.research_capital_fit}"
        )
        row = (
            f"| {_today()} | learn_tick:{o.hypothesis_id} | {surf} | "
            f"**{o.verdict}** | {metrics} | learn_audit.jsonl |"
        )
        rows.append(row)
    if not rows:
        return False
    # Insert before "## 5." if present, else append
    block = "\n".join(rows) + "\n"
    if "\n## 5." in text:
        text = text.replace("\n## 5.", "\n" + block + "\n## 5.", 1)
    else:
        text = text.rstrip() + "\n\n" + block
    _SCOREBOARD.write_text(text, encoding="utf-8")
    return True


def run_learn_tick(
    *,
    apply: bool = False,
    append_scoreboard: bool = False,
    allow_reject: bool = False,
    statuses: Optional[set[str]] = None,
    registry_path: Optional[Path | str] = None,
) -> LearnReport:
    reg = HypothesisRegistry(registry_path)
    reg.ensure_seeded()
    ledger = load_paper_ledger()
    audit = load_audit_tail()
    research = load_latest_research_by_symbol()
    want = statuses or {"candidate", "testing", "paper", "shadow"}
    hyps = [h for h in reg.list() if h.status in want]

    report = LearnReport(
        ts=_now(),
        applied=apply,
        dry_run=not apply,
        n_hyps=len(hyps),
    )

    for h in hyps:
        try:
            out = evaluate_hypothesis(
                h, ledger=ledger, audit=audit, research_by_sym=research
            )
            report.outcomes.append(out)
            if apply and (
                out.recommended_status
                or (allow_reject and out.verdict == "REJECT")
            ):
                tr = apply_transition(
                    reg, out, allow_reject=allow_reject
                )
                if tr:
                    report.transitions.append(tr)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{h.id}: {exc}")

    if append_scoreboard:
        try:
            report.scoreboard_appended = append_scoreboard_rows(report.outcomes)
        except OSError as exc:
            report.errors.append(f"scoreboard: {exc}")

    append_learn_audit(report)
    return report


def format_report(report: LearnReport) -> str:
    lines = [
        f"learn_tick ts={report.ts} apply={report.applied} hyps={report.n_hyps}",
        f"audit: {report.audit_path or _LEARN_AUDIT}",
        "",
        f"{'ID':<42} {'status':<10} {'verdict':<16} {'→':<10} reason",
        "-" * 110,
    ]
    for o in report.outcomes:
        arrow = o.recommended_status or "-"
        lines.append(
            f"{o.hypothesis_id:<42} {o.status:<10} {o.verdict:<16} {arrow:<10} {o.reason[:60]}"
        )
    if report.transitions:
        lines.append("")
        lines.append("=== TRANSITIONS ===")
        for t in report.transitions:
            lines.append(json.dumps(t, default=str))
    if report.errors:
        lines.append("")
        lines.append("=== ERRORS ===")
        for e in report.errors:
            lines.append(f"  {e}")
    lines.append("")
    lines.append(
        "hard_rules: never_auto_live=true never_auto_shadow=true "
        f"scoreboard_appended={report.scoreboard_appended}"
    )
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    # just recipes often inject a literal "--" separator anywhere in *ARGS
    if argv is None:
        import sys

        argv = sys.argv[1:]
    argv = [a for a in argv if a != "--"]

    p = argparse.ArgumentParser(
        description="Learn tick: evaluate hyps from outcomes; safe self-improve (no live)."
    )
    p.add_argument("--once", action="store_true", help="run one learn tick (default)")
    p.add_argument(
        "--apply",
        action="store_true",
        help="apply safe status transitions (default: dry-run evaluate only)",
    )
    p.add_argument(
        "--append-scoreboard",
        action="store_true",
        help="append actionable rows to docs/RESEARCH_SCOREBOARD.md",
    )
    p.add_argument(
        "--allow-reject",
        action="store_true",
        help="allow auto transition to rejected on REJECT verdict",
    )
    p.add_argument("--registry", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    report = run_learn_tick(
        apply=args.apply,
        append_scoreboard=args.append_scoreboard,
        allow_reject=args.allow_reject,
        registry_path=args.registry,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(format_report(report))
    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

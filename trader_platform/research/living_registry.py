"""Living strategy registry for Desk B (autonomy path).

Only spine evaluation outcomes update seats. Proxy F2+ can be living research seats;
L1/paper/live still require separate gates. No trading authority is granted here.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = _ROOT / "data" / "living_registry.json"

# Funnel seats Desk B may hold.
LIVING_STATUSES = (
    "research_park",  # explicit L0 park; not capital path
    "f1_train",  # train dual-cost only — not enough to trade
    "f2_holdout",  # sealed holdout pass — may feed watcher research packets
    "paper_eligible",  # promoted for paper path (still not live)
    "quarantined",  # closed / failed; blocked from re-entry without new family id
)

ACTIVE_WATCH_STATUSES = frozenset({"f2_holdout", "paper_eligible"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class LivingSeat:
    seat_id: str
    candidate_id: str
    family_id: str
    status: str
    symbols: list[str] = field(default_factory=list)
    evaluation_mode: str = ""
    router_policy: str = ""
    spec_path: str = ""
    evidence_report_path: str = ""
    funnel_stage: str = "F0_MECHANISM"
    option_mark_provenance: str = "black_scholes_proxy"
    decision: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_eval_at: str = ""
    quarantine_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LivingSeat":
        data = dict(raw)
        data.setdefault("symbols", [])
        data.setdefault("evaluation_mode", "")
        data.setdefault("router_policy", "")
        data.setdefault("spec_path", "")
        data.setdefault("evidence_report_path", "")
        data.setdefault("funnel_stage", "F0_MECHANISM")
        data.setdefault("option_mark_provenance", "black_scholes_proxy")
        data.setdefault("decision", "")
        data.setdefault("notes", "")
        data.setdefault("created_at", "")
        data.setdefault("updated_at", "")
        data.setdefault("last_eval_at", "")
        data.setdefault("quarantine_reason", "")
        status = str(data.get("status") or "research_park")
        if status not in LIVING_STATUSES:
            raise ValueError(f"invalid living status {status!r}")
        data["status"] = status
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    @property
    def watchable(self) -> bool:
        return self.status in ACTIVE_WATCH_STATUSES


@dataclass
class LivingRegistry:
    version: int = 1
    desk: str = "B_agentic"
    updated_at: str = ""
    seats: list[LivingSeat] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "desk": self.desk,
            "updated_at": self.updated_at,
            "seats": [s.to_dict() for s in self.seats],
            "watchable_count": sum(1 for s in self.seats if s.watchable),
            "quarantined_count": sum(1 for s in self.seats if s.status == "quarantined"),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LivingRegistry":
        seats = [LivingSeat.from_dict(s) for s in (raw.get("seats") or [])]
        return cls(
            version=int(raw.get("version") or 1),
            desk=str(raw.get("desk") or "B_agentic"),
            updated_at=str(raw.get("updated_at") or ""),
            seats=seats,
        )

    def get(self, seat_id: str) -> Optional[LivingSeat]:
        for seat in self.seats:
            if seat.seat_id == seat_id:
                return seat
        return None

    def upsert(self, seat: LivingSeat) -> LivingSeat:
        now = _now_iso()
        if not seat.created_at:
            seat.created_at = now
        seat.updated_at = now
        for i, existing in enumerate(self.seats):
            if existing.seat_id == seat.seat_id:
                if not seat.created_at:
                    seat.created_at = existing.created_at
                self.seats[i] = seat
                self.updated_at = now
                return seat
        self.seats.append(seat)
        self.updated_at = now
        return seat

    def watchable_seats(self) -> list[LivingSeat]:
        return [s for s in self.seats if s.watchable]

    def quarantine_family(self, family_id: str, reason: str) -> int:
        n = 0
        now = _now_iso()
        for seat in self.seats:
            if seat.family_id == family_id and seat.status != "quarantined":
                seat.status = "quarantined"
                seat.quarantine_reason = reason
                seat.updated_at = now
                n += 1
        if n:
            self.updated_at = now
        return n


def load_living_registry(path: str | Path | None = None) -> LivingRegistry:
    path = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not path.exists():
        # Bootstrap from committed example when present (local runtime file is gitignored).
        example = path.parent / "living_registry.example.json"
        if example.exists() and path == DEFAULT_REGISTRY_PATH:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                return LivingRegistry(updated_at=_now_iso())
        else:
            return LivingRegistry(updated_at=_now_iso())
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("living registry root must be an object")
    return LivingRegistry.from_dict(raw)


def save_living_registry(registry: LivingRegistry, path: str | Path | None = None) -> Path:
    path = Path(path) if path else DEFAULT_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    registry.updated_at = _now_iso()
    path.write_text(
        json.dumps(registry.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def seat_id_for(candidate_id: str, symbol: str | None = None) -> str:
    base = str(candidate_id).strip()
    if symbol:
        return f"{base}:{str(symbol).strip().upper()}"
    return base


def ingest_evaluate_report(
    report: Mapping[str, Any],
    *,
    registry: LivingRegistry | None = None,
    registry_path: str | Path | None = None,
    spec_path: str = "",
    report_path: str = "",
) -> LivingRegistry:
    """Update registry from an evaluate_proxy report.

    - F2 living_candidates → f2_holdout seats
    - train-only advance without holdout → f1_train (not watchable)
    - FAMILY_CLOSED → quarantine family
    """
    reg = registry if registry is not None else load_living_registry(registry_path)
    candidate_id = str(report.get("candidate_id") or "unknown")
    family_id = str(report.get("family_id") or candidate_id)
    decision = str(report.get("decision") or "")
    mode = str(report.get("evaluation_mode") or "")
    policy = str(report.get("router_policy") or "")
    provenance = str(report.get("option_mark_provenance") or "black_scholes_proxy")
    now = _now_iso()

    living = list(report.get("living_candidates") or [])
    if living:
        for item in living:
            symbol = str(item.get("symbol") or "").upper() or None
            sid = str(item.get("candidate_id") or seat_id_for(candidate_id, symbol))
            seat = LivingSeat(
                seat_id=sid,
                candidate_id=candidate_id,
                family_id=family_id,
                status="f2_holdout",
                symbols=[symbol] if symbol else list(report.get("symbols") or []),
                evaluation_mode=mode,
                router_policy=policy,
                spec_path=spec_path,
                evidence_report_path=report_path,
                funnel_stage=str(item.get("funnel_stage") or "F2_UNTOUCHED_HOLDOUT"),
                option_mark_provenance=str(
                    item.get("option_mark_provenance") or provenance
                ),
                decision=decision,
                notes="ingested from spine evaluate_proxy F2 survivor",
                last_eval_at=now,
            )
            reg.upsert(seat)
        save_living_registry(reg, registry_path)
        return reg

    if decision == "STRATEGY_ADVANCED_F1_HOLDOUT_FAILED":
        symbols = [
            str(r.get("symbol")).upper()
            for r in (report.get("train_rows") or [])
            if r.get("train_discovery_pass")
        ] or list(report.get("symbols") or [])
        for symbol in symbols:
            seat = LivingSeat(
                seat_id=seat_id_for(candidate_id, symbol),
                candidate_id=candidate_id,
                family_id=family_id,
                status="f1_train",
                symbols=[str(symbol).upper()],
                evaluation_mode=mode,
                router_policy=policy,
                spec_path=spec_path,
                evidence_report_path=report_path,
                funnel_stage="F1_TRAIN",
                option_mark_provenance=provenance,
                decision=decision,
                notes="train dual-cost only; not watchable until F2",
                last_eval_at=now,
            )
            reg.upsert(seat)
        save_living_registry(reg, registry_path)
        return reg

    if decision == "FAMILY_CLOSED":
        reg.quarantine_family(
            family_id,
            reason=f"spine_decision={decision}; report={report_path or 'inline'}",
        )
        # Also record a family-level quarantine seat for audit if none exists.
        if not any(s.family_id == family_id for s in reg.seats):
            reg.upsert(
                LivingSeat(
                    seat_id=seat_id_for(candidate_id),
                    candidate_id=candidate_id,
                    family_id=family_id,
                    status="quarantined",
                    symbols=[str(s).upper() for s in (report.get("symbols") or [])],
                    evaluation_mode=mode,
                    router_policy=policy,
                    spec_path=spec_path,
                    evidence_report_path=report_path,
                    funnel_stage=str(report.get("funnel_stage_after") or "F0_MECHANISM"),
                    option_mark_provenance=provenance,
                    decision=decision,
                    quarantine_reason="FAMILY_CLOSED with no prior seats",
                    last_eval_at=now,
                )
            )
        save_living_registry(reg, registry_path)
        return reg

    save_living_registry(reg, registry_path)
    return reg


def summary_lines(registry: LivingRegistry) -> list[str]:
    lines = [
        f"desk={registry.desk} seats={len(registry.seats)} "
        f"watchable={sum(1 for s in registry.seats if s.watchable)} "
        f"quarantined={sum(1 for s in registry.seats if s.status == 'quarantined')}"
    ]
    for seat in registry.seats:
        lines.append(
            f"- {seat.seat_id} status={seat.status} family={seat.family_id} "
            f"stage={seat.funnel_stage}"
        )
    return lines

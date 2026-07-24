"""Durable hypothesis registry (YAML). Seed strategies are hypotheses, not the ceiling."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

_ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY_PATH = _ROOT / "data" / "hypotheses.yaml"

SLEEVES = ("premium", "tactical", "core_long", "cash")
STATUSES = (
    "candidate",
    "testing",
    "paper",
    "shadow",
    "live",
    "retired",
    "rejected",
)

# Allowed status transitions (explicit graph; no auto-jump to live from candidate).
TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"testing", "rejected", "retired"},
    "testing": {"paper", "candidate", "rejected", "retired"},
    "paper": {"shadow", "testing", "rejected", "retired"},
    "shadow": {"live", "paper", "rejected", "retired"},
    "live": {"shadow", "retired", "rejected"},
    "retired": {"candidate"},
    "rejected": {"candidate"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Hypothesis:
    id: str
    name: str
    thesis: str
    sleeve: str
    instruments: list[str] = field(default_factory=list)
    entry_logic_ref: str = ""
    exit_logic_ref: str = ""
    status: str = "candidate"
    evidence_links: list[str] = field(default_factory=list)
    null_results: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""
    notes: str = ""
    # Full free strategy genome (structure + entry/exit/management + sim). Optional.
    dna: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: MappingLike) -> "Hypothesis":
        data = dict(d)
        data.setdefault("instruments", [])
        data.setdefault("evidence_links", [])
        data.setdefault("null_results", [])
        data.setdefault("entry_logic_ref", "")
        data.setdefault("exit_logic_ref", "")
        data.setdefault("notes", "")
        data.setdefault("status", "candidate")
        data.setdefault("dna", None)
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


# typing without importing Mapping only for annotation clarity
MappingLike = dict[str, Any]


class HypothesisRegistry:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DEFAULT_REGISTRY_PATH

    def _empty_store(self) -> dict[str, Any]:
        return {"version": 1, "hypotheses": []}

    def load(self, *, retries: int = 8, retry_sleep_s: float = 0.05) -> dict[str, Any]:
        """Load registry YAML.

        Retries on mid-write parse errors. Writers must use :meth:`save` (atomic
        replace); concurrent readers can still race a long dump, so retry briefly
        before failing closed.
        """
        if not self.path.exists():
            return self._empty_store()
        last_err: Exception | None = None
        attempts = max(1, int(retries))
        for i in range(attempts):
            try:
                with self.path.open() as f:
                    data = yaml.safe_load(f) or {}
                if not isinstance(data, dict):
                    raise ValueError(f"registry must be a mapping: {self.path}")
                data.setdefault("version", 1)
                data.setdefault("hypotheses", [])
                return data
            except yaml.YAMLError as e:
                last_err = e
                if i + 1 >= attempts:
                    break
                time.sleep(retry_sleep_s * (i + 1))
        assert last_err is not None
        raise last_err

    def save(self, store: dict[str, Any]) -> None:
        """Atomically persist registry YAML (temp file + os.replace).

        Non-atomic open('w') previously truncated the live path mid-dump, which
        raced quality_worker evolve ticks against autonomy/shadow readers and
        produced ScannerError thrash on large hypotheses.yaml files.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with tmp_path.open("w") as f:
                yaml.safe_dump(store, f, sort_keys=False, default_flow_style=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def list(self, status: Optional[str] = None) -> list[Hypothesis]:
        store = self.load()
        out = [Hypothesis.from_dict(h) for h in store.get("hypotheses") or []]
        if status:
            out = [h for h in out if h.status == status]
        return out

    def get(self, hypothesis_id: str) -> Hypothesis:
        for h in self.list():
            if h.id == hypothesis_id:
                return h
        raise KeyError(f"hypothesis not found: {hypothesis_id}")

    def add(
        self,
        *,
        name: str,
        thesis: str,
        sleeve: str,
        instruments: Iterable[str] | None = None,
        entry_logic_ref: str = "",
        exit_logic_ref: str = "",
        status: str = "candidate",
        evidence_links: Iterable[str] | None = None,
        null_results: Iterable[str] | None = None,
        notes: str = "",
        hypothesis_id: str | None = None,
        dna: Optional[dict[str, Any]] = None,
    ) -> Hypothesis:
        if sleeve not in SLEEVES:
            raise ValueError(f"sleeve must be one of {SLEEVES}")
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        now = _now_iso()
        h = Hypothesis(
            id=hypothesis_id or f"hyp_{uuid.uuid4().hex[:10]}",
            name=name,
            thesis=thesis,
            sleeve=sleeve,
            instruments=[s.upper() for s in (instruments or [])],
            entry_logic_ref=entry_logic_ref,
            exit_logic_ref=exit_logic_ref,
            status=status,
            evidence_links=list(evidence_links or []),
            null_results=list(null_results or []),
            created=now,
            updated=now,
            notes=notes,
            dna=dna,
        )
        store = self.load()
        if any(x.get("id") == h.id for x in store["hypotheses"]):
            raise ValueError(f"duplicate id: {h.id}")
        store["hypotheses"].append(h.to_dict())
        self.save(store)
        return h

    def transition(
        self,
        hypothesis_id: str,
        new_status: str,
        *,
        evidence_link: str | None = None,
        force: bool = False,
        allow_live_without_evidence: bool = False,
    ) -> Hypothesis:
        if new_status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        store = self.load()
        found = None
        for i, raw in enumerate(store["hypotheses"]):
            if raw.get("id") == hypothesis_id:
                found = i
                break
        if found is None:
            raise KeyError(f"hypothesis not found: {hypothesis_id}")

        h = Hypothesis.from_dict(store["hypotheses"][found])
        if not force and new_status not in TRANSITIONS.get(h.status, set()):
            raise ValueError(
                f"illegal transition {h.status!r} → {new_status!r}; "
                f"allowed={sorted(TRANSITIONS.get(h.status, set()))}"
            )

        if new_status == "live" and not allow_live_without_evidence:
            links = list(h.evidence_links)
            if evidence_link:
                links.append(evidence_link)
            if not links:
                raise ValueError(
                    "no auto-promote to live without evidence_links "
                    "(pass --evidence or add evidence first)"
                )

        h.status = new_status
        h.updated = _now_iso()
        if evidence_link:
            if evidence_link not in h.evidence_links:
                h.evidence_links.append(evidence_link)
        store["hypotheses"][found] = h.to_dict()
        self.save(store)
        return h

    def ensure_seeded(self) -> list[Hypothesis]:
        """Idempotent seed of 4 example hypotheses from existing strategy work."""
        store = self.load()
        if store.get("hypotheses"):
            return self.list()

        self.add(
            hypothesis_id="hyp_short_premium_tsla",
            name="TSLA short premium (regime-directed)",
            thesis=(
                "Sell OTM puts in bullish/neutral regimes and OTM calls in confirmed "
                "bearish regimes; stand aside when credit floor fails. Edge is short-horizon "
                "premium decay with strict entry filters and exit ladder."
            ),
            sleeve="premium",
            instruments=["TSLA"],
            entry_logic_ref="strategies.pick_entry",
            exit_logic_ref="strategies.check_exits",
            status="testing",
            evidence_links=["STRATEGY.md#current-approach", "just scenarios"],
            notes="Seed from v1.13/v1.14 baseline — still a hypothesis, not ceiling.",
        )
        self.add(
            hypothesis_id="hyp_short_premium_tsll",
            name="TSLL short premium (levered ETF)",
            thesis=(
                "Same engine as TSLA with per-ticker knobs (shorter put DTE, adaptive skip "
                "rules). Levered-ETF path risk means stand-aside and adaptive filters matter more."
            ),
            sleeve="premium",
            instruments=["TSLL"],
            entry_logic_ref="strategies.pick_entry",
            exit_logic_ref="strategies.check_exits",
            status="testing",
            evidence_links=["STRATEGY.md#current-approach"],
            null_results=["TSLL wheel underperforms cash (STRATEGY.md history)"],
        )
        self.add(
            hypothesis_id="hyp_pmcc_income",
            name="PMCC income sleeve",
            thesis=(
                "Long LEAP call + short near-term call for defined-structure upside with "
                "premium harvest; manage rolls and income vs core long bias separately."
            ),
            sleeve="premium",
            instruments=["TSLA"],
            entry_logic_ref="pmcc/",
            exit_logic_ref="pmcc_manage / manage playbook",
            status="candidate",
            evidence_links=["docs/TRADER_KNOWLEDGE_MAP.md", "pmcc/"],
        )
        self.add(
            hypothesis_id="hyp_stand_aside",
            name="Stand-aside cash sleeve",
            thesis=(
                "No trade is a valid action when credit floor, regime, or risk envelope fails. "
                "Cash sleeve is success, not a broken signal."
            ),
            sleeve="cash",
            instruments=["TSLA", "TSLL"],
            entry_logic_ref="strategies.pick_entry → STAND_ASIDE",
            exit_logic_ref="n/a",
            status="testing",
            evidence_links=["GOAL.md cost function", "live.py STAND_ASIDE"],
        )
        return self.list()

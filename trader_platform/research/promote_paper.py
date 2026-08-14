"""Promote best F2 living seats to paper_eligible for plumbing / paper ticks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trader_platform.research.identity import coarse_dna_key, diversify_rows
from trader_platform.research.living_registry import (
    DEFAULT_REGISTRY_PATH,
    load_living_registry,
    save_living_registry,
)
from trader_platform.research.pack_grade import is_pack_grade, load_quality_pass_cells, quality_pass_index
from trader_platform.research.progress_dashboard import collect_progress
from trader_platform.research.strategy_spec import load_strategy_spec


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _enrich_dna(row: dict[str, Any], seat: Any | None) -> dict[str, Any]:
    """Attach coarse_dna_key for diversify (best-effort from seat + optional spec)."""
    out = dict(row)
    mgmt: dict[str, Any] = {}
    structure = ""
    evaluation_mode = ""
    if seat is not None and getattr(seat, "spec_path", None):
        try:
            from pathlib import Path as _P

            p = _P(seat.spec_path)
            if p.exists():
                spec = load_strategy_spec(p)
                mgmt = dict(spec.management or {})
                structure = str(spec.structure or "")
                evaluation_mode = str(spec.evaluation_mode or "")
        except Exception:
            pass
    out["coarse_dna_key"] = coarse_dna_key(
        family_id=str(out.get("family_id") or (seat.family_id if seat else "")),
        candidate_id=str(out.get("candidate_id") or (seat.candidate_id if seat else "")),
        router_policy=str(
            out.get("router_policy") or (getattr(seat, "router_policy", "") if seat else "")
        ),
        structure=structure,
        management=mgmt,
        evaluation_mode=evaluation_mode,
    )
    return out


def promote_top_f2_to_paper(
    *,
    top_n: int = 5,
    registry_path: str | Path | None = None,
    diversify_symbols: bool = True,
    diversify_dna: bool = True,
) -> dict[str, Any]:
    """Promote top holdout F2 seats to paper_eligible.

    Ranking reuses progress dashboard enrichment (worst-axis holdout PnL).
    Diversify by symbol and/or coarse DNA key (thesis family + DTE/pt/iv bands).
    """
    registry_path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    snap = collect_progress(registry_path=registry_path)
    ranked = list(snap.f2_seats)  # already best-first
    if not ranked:
        return {
            "promoted": [],
            "already_paper": [],
            "n_promoted": 0,
            "reason": "no F2 seats to promote",
        }

    reg = load_living_registry(registry_path)
    by_id = {s.seat_id: s for s in reg.seats}
    enriched = [
        _enrich_dna(dict(row), by_id.get(str(row.get("seat_id") or "")))
        for row in ranked
    ]
    if diversify_symbols or diversify_dna:
        chosen = diversify_rows(
            enriched,
            top_n=top_n,
            by_symbol=diversify_symbols,
            by_dna=diversify_dna,
        )
    else:
        chosen = [dict(r) for r in enriched[:top_n]]

    promoted: list[str] = []
    already: list[str] = []
    now = _now()
    for row in chosen:
        sid = str(row.get("seat_id") or "")
        seat = by_id.get(sid)
        if seat is None:
            # try match candidate_id + symbol
            for s in reg.seats:
                if s.candidate_id == row.get("candidate_id") and s.status in {
                    "f2_holdout",
                    "paper_eligible",
                }:
                    seat = s
                    break
        if seat is None:
            continue
        if seat.status == "paper_eligible":
            already.append(seat.seat_id)
            continue
        if seat.status != "f2_holdout":
            continue
        seat.status = "paper_eligible"
        seat.funnel_stage = "F3_ROBUST_PAPER_PLAN"
        dna = row.get("coarse_dna_key") or ""
        seat.notes = (seat.notes or "") + f" | promoted_to_paper@{now}"
        if dna:
            seat.notes += f" | dna={dna}"
        seat.updated_at = now
        reg.upsert(seat)
        promoted.append(seat.seat_id)

    save_living_registry(reg, registry_path)
    return {
        "promoted": promoted,
        "already_paper": already,
        "n_promoted": len(promoted),
        "diversify_symbols": diversify_symbols,
        "diversify_dna": diversify_dna,
        "chosen_dna": [c.get("coarse_dna_key") for c in chosen],
        "top_n": top_n,
        "diversify_symbols": diversify_symbols,
        "registry_path": str(registry_path),
        "note": "paper_eligible enables paper ledger mutate via handoff --execute-paper; still no live",
    }


def promote_pack_grade_to_paper(
    *,
    registry_path: str | Path | None = None,
    multi_path: str | Path | None = None,
    demote_non_pack: bool = True,
) -> dict[str, Any]:
    """Promote exact MULTI quality_pass living seats to paper_eligible.

    Does not invent DNA. Only flips status on existing f2_holdout seats whose
    candidate_id+symbol match a fresh quality_pass cell. Optionally demotes
    leftover paper_eligible seats so the watcher tries pack-grade first even
    before selector preference is live.
    """
    registry_path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    cells = load_quality_pass_cells(multi_path)
    index = quality_pass_index(cells)
    if not index:
        return {
            "promoted": [],
            "already_paper": [],
            "demoted": [],
            "n_promoted": 0,
            "n_quality_pass": 0,
            "reason": "no MULTI quality_pass cells",
            "registry_path": str(registry_path),
            "note": "no DNA invented; missing/empty MULTI is fail-closed",
        }

    reg = load_living_registry(registry_path)
    promoted: list[str] = []
    already: list[str] = []
    demoted: list[str] = []
    now = _now()
    for seat in list(reg.seats):
        symbols = [str(s).upper() for s in (seat.symbols or []) if str(s).strip()]
        pack = any(
            is_pack_grade(
                candidate_id=seat.candidate_id,
                seat_id=seat.seat_id,
                symbol=sym,
                index=index,
            )
            for sym in (symbols or [""])
        )
        if pack:
            if seat.status == "paper_eligible":
                already.append(seat.seat_id)
                continue
            if seat.status != "f2_holdout":
                continue
            seat.status = "paper_eligible"
            seat.funnel_stage = "F3_ROBUST_PAPER_PLAN"
            seat.notes = (seat.notes or "") + f" | promoted_pack_grade_paper@{now}"
            seat.updated_at = now
            reg.upsert(seat)
            promoted.append(seat.seat_id)
            continue
        if demote_non_pack and seat.status == "paper_eligible":
            seat.status = "f2_holdout"
            seat.notes = (seat.notes or "") + f" | demoted_legacy_for_pack_grade@{now}"
            seat.updated_at = now
            reg.upsert(seat)
            demoted.append(seat.seat_id)

    save_living_registry(reg, registry_path)
    return {
        "promoted": promoted,
        "already_paper": already,
        "demoted": demoted,
        "n_promoted": len(promoted),
        "n_demoted": len(demoted),
        "n_quality_pass": len(index),
        "quality_pass_ids": sorted(index),
        "registry_path": str(registry_path),
        "note": "pack-grade paper_eligible only; leftover demoted to f2_holdout; still no live",
    }

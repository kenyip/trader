"""Promote best F2 living seats to paper_eligible for plumbing / paper ticks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trader_platform.research.living_registry import (
    DEFAULT_REGISTRY_PATH,
    load_living_registry,
    save_living_registry,
)
from trader_platform.research.progress_dashboard import collect_progress


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def promote_top_f2_to_paper(
    *,
    top_n: int = 5,
    registry_path: str | Path | None = None,
    diversify_symbols: bool = True,
) -> dict[str, Any]:
    """Promote top holdout F2 seats to paper_eligible.

    Ranking reuses progress dashboard enrichment (worst-axis holdout PnL).
    If diversify_symbols, prefer at most one seat per symbol among the top N
    until the list is filled (then fill remaining by rank).
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

    chosen: list[dict[str, Any]] = []
    seen_sym: set[str] = set()
    if diversify_symbols:
        for row in ranked:
            syms = [str(s).upper() for s in (row.get("symbols") or [])]
            key = syms[0] if syms else row.get("seat_id")
            if key in seen_sym:
                continue
            seen_sym.add(str(key))
            chosen.append(row)
            if len(chosen) >= top_n:
                break
    if len(chosen) < top_n:
        have = {c.get("seat_id") for c in chosen}
        for row in ranked:
            if row.get("seat_id") in have:
                continue
            chosen.append(row)
            if len(chosen) >= top_n:
                break

    reg = load_living_registry(registry_path)
    promoted: list[str] = []
    already: list[str] = []
    now = _now()
    by_id = {s.seat_id: s for s in reg.seats}
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
        seat.notes = (seat.notes or "") + f" | promoted_to_paper@{now}"
        seat.updated_at = now
        reg.upsert(seat)
        promoted.append(seat.seat_id)

    save_living_registry(reg, registry_path)
    return {
        "promoted": promoted,
        "already_paper": already,
        "n_promoted": len(promoted),
        "top_n": top_n,
        "diversify_symbols": diversify_symbols,
        "registry_path": str(registry_path),
        "note": "paper_eligible enables paper ledger mutate via handoff --execute-paper; still no live",
    }

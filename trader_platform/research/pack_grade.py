"""Fresh MULTI quality_pass match key (candidate stem + f2 symbol).

Does not invent DNA. Missing/unreadable MULTI → empty set (no pack-grade claim).
When quality_pass cells exist, paper consumption should prefer those cells and
fail closed on leftover shortlist / near-miss family seats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_MULTI_PATH = _REPO / "reports" / "bootstrap" / "MULTI_SYMBOL_REPROVE.json"


def load_quality_pass_cells(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else DEFAULT_MULTI_PATH
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("results") or raw.get("rows") or []
    cells: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("quality_pass") is not True:
            continue
        cid = str(row.get("candidate_id") or "").strip()
        if not cid:
            continue
        symbols = [
            str(sym).upper()
            for sym in (row.get("f2_symbols") or row.get("thick_f2_symbols") or [])
            if str(sym).strip()
        ]
        if not symbols:
            continue
        cells.append(
            {
                "candidate_id": cid,
                "f2_symbols": symbols,
                "family_id": str(row.get("family_id") or ""),
            }
        )
    return cells


def quality_pass_index(
    cells: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for cell in cells if cells is not None else load_quality_pass_cells():
        cid = str(cell.get("candidate_id") or "").strip()
        if not cid:
            continue
        out.setdefault(cid, set()).update(
            str(sym).upper() for sym in (cell.get("f2_symbols") or []) if str(sym).strip()
        )
    return out


def seat_stem(seat_id: str, candidate_id: str = "") -> str:
    """Watcher seats are ``{stem}_{SYMBOL}``. Prefer explicit candidate_id."""
    if candidate_id:
        return str(candidate_id)
    sid = str(seat_id or "")
    if "_" not in sid:
        return sid
    head, tail = sid.rsplit("_", 1)
    if tail.isalpha() and tail.isupper() and 1 <= len(tail) <= 5:
        return head
    return sid


def is_pack_grade(
    *,
    candidate_id: str = "",
    seat_id: str = "",
    symbol: str = "",
    cells: Iterable[Mapping[str, Any]] | None = None,
    index: Mapping[str, set[str]] | None = None,
) -> bool:
    idx = index if index is not None else quality_pass_index(cells)
    if not idx:
        return False
    stem = str(candidate_id or seat_stem(seat_id) or "").strip()
    if stem not in idx:
        return False
    sym = str(symbol or "").upper()
    if not sym and "_" in str(seat_id):
        tail = str(seat_id).rsplit("_", 1)[-1].upper()
        if tail.isalpha() and 1 <= len(tail) <= 5:
            sym = tail
    if not sym:
        return False
    return sym in idx[stem]


def watch_sort_key(seat: Any, index: Mapping[str, set[str]] | None = None) -> tuple[int, str]:
    """0 = pack-grade, 1 = paper_eligible, 2 = other watchable; then seat_id."""
    idx = index if index is not None else quality_pass_index()
    symbols = list(getattr(seat, "symbols", None) or [])
    cid = str(getattr(seat, "candidate_id", "") or "")
    sid = str(getattr(seat, "seat_id", "") or "")
    pack = False
    if idx:
        if symbols:
            pack = any(
                is_pack_grade(candidate_id=cid, seat_id=sid, symbol=str(sym), index=idx)
                for sym in symbols
            )
        else:
            pack = is_pack_grade(candidate_id=cid, seat_id=sid, index=idx)
    if pack:
        tier = 0
    elif str(getattr(seat, "status", "") or "") == "paper_eligible":
        tier = 1
    else:
        tier = 2
    return (tier, sid)

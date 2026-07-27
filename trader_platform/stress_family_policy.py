"""Shared symbol×structure family cool/toxic policy from STRESS_ROTATION ledger.

Used by stress selector (queue) and evolve apply (registry create) so toxic
families do not burn create slots or B3/B4 budget. Selector remains authoritative
for challenge slots; evolve refuses *new registry rows* for toxic families.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROTATION = _REPO / "reports" / "bootstrap" / "STRESS_ROTATION.json"


def load_rotation(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_ROTATION
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def _parse_iso_ts(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        t = str(s).replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def family_window_fail_ok(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    window_hours: float = 6.0,
) -> tuple[int, int]:
    """Recent fail/ok counts for symbol×structure from rotation ledger."""
    if not symbol or not structure:
        return 0, 0
    by = (rotation or load_rotation()).get("by_hyp_id") or {}
    if not isinstance(by, dict):
        return 0, 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=float(window_hours))
    fails = 0
    oks = 0
    sym_u = str(symbol).upper()
    struct = str(structure).strip().lower()
    for row in by.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("symbol") or "").upper() != sym_u:
            continue
        if str(row.get("structure") or "").strip().lower() != struct:
            continue
        ts = _parse_iso_ts(row.get("stressed_at"))
        if ts is None or ts < cutoff:
            continue
        if row.get("capital_path_ok"):
            oks += 1
        else:
            fails += 1
    return fails, oks


def family_lifetime_fail_ok(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
) -> tuple[int, int]:
    if not symbol or not structure:
        return 0, 0
    by = (rotation or load_rotation()).get("by_hyp_id") or {}
    if not isinstance(by, dict):
        return 0, 0
    fails = 0
    oks = 0
    sym_u = str(symbol).upper()
    struct = str(structure).strip().lower()
    for row in by.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("symbol") or "").upper() != sym_u:
            continue
        if str(row.get("structure") or "").strip().lower() != struct:
            continue
        if row.get("capital_path_ok"):
            oks += 1
        else:
            fails += 1
    return fails, oks


def family_challenge_toxic(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    window_hours: float = 6.0,
    toxic_fail_min: int = 8,
    lifetime_fail_min: int = 20,
) -> bool:
    """Hard-block hopeless symbol×structure families (same thresholds as selector).

    Toxic = recent fails>=toxic_fail_min & 0 ok, OR lifetime fails>=lifetime_fail_min & 0 ok.
    """
    if not symbol or not structure:
        return False
    rot = rotation if rotation is not None else load_rotation()
    if toxic_fail_min > 0 and window_hours > 0:
        fails, oks = family_window_fail_ok(
            symbol, structure, rotation=rot, window_hours=window_hours
        )
        if fails >= int(toxic_fail_min) and oks == 0:
            return True
    if lifetime_fail_min > 0:
        lf, lo = family_lifetime_fail_ok(symbol, structure, rotation=rot)
        if lf >= int(lifetime_fail_min) and lo == 0:
            return True
    return False


def dna_primary_symbol(dna: Any) -> str | None:
    """Best-effort symbol from StrategyDNA or mapping."""
    if dna is None:
        return None
    symbols = getattr(dna, "symbols", None)
    if symbols is None and isinstance(dna, dict):
        symbols = dna.get("symbols")
    if isinstance(symbols, (list, tuple)) and symbols:
        s = str(symbols[0] or "").strip().upper()
        return s or None
    return None


def dna_structure(dna: Any) -> str | None:
    if dna is None:
        return None
    s = getattr(dna, "structure", None)
    if s is None and isinstance(dna, dict):
        s = dna.get("structure")
    if not s:
        return None
    return str(s).strip().lower() or None

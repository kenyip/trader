"""Coarse DNA identity for living seats — collapse clone floods.

Preference (TRADER_BUILD §4): thesis_id + symbol + coarse DNA over mutant suffixes.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional


def _band_dte(dte: Any) -> str:
    try:
        v = int(float(dte))
    except (TypeError, ValueError):
        return "dte?"
    if v <= 10:
        return "dte_s"
    if v <= 21:
        return "dte_m"
    if v <= 35:
        return "dte_l"
    return "dte_xl"


def _band_pt(pt: Any) -> str:
    try:
        v = float(pt)
    except (TypeError, ValueError):
        return "pt?"
    if v < 0.40:
        return "pt_lo"
    if v < 0.55:
        return "pt_mid"
    return "pt_hi"


def _band_iv(iv: Any) -> str:
    try:
        v = float(iv)
    except (TypeError, ValueError):
        return "iv0"
    if v <= 0:
        return "iv0"
    if v < 20:
        return "iv_lo"
    if v < 35:
        return "iv_mid"
    return "iv_hi"


def _band_delta(delta: Any) -> str:
    try:
        v = float(delta)
    except (TypeError, ValueError):
        return "dlt?"
    if v < 0.15:
        return "dlt_lo"
    if v < 0.22:
        return "dlt_mid"
    return "dlt_hi"


def _family_root(family_id: str) -> str:
    """Strip densify/grid mutant suffixes from family ids."""
    fid = str(family_id or "").strip()
    if not fid:
        return "unknown"
    # Common patterns: FAMILY__g_d14_pt50... or FAMILY__dn_...
    parts = re.split(r"__", fid, maxsplit=1)
    return parts[0] if parts else fid


def coarse_dna_key(
    *,
    thesis_id: str = "",
    family_id: str = "",
    candidate_id: str = "",
    router_policy: str = "",
    structure: str = "",
    management: Optional[Mapping[str, Any]] = None,
    evaluation_mode: str = "",
) -> str:
    """Stable coarse identity for diversify/dedupe (not a unique seat id)."""
    mgmt = dict(management or {})
    root = (
        str(thesis_id).strip()
        or _family_root(family_id)
        or _family_root(candidate_id)
        or "unknown"
    )
    pol = str(router_policy or "router").strip().lower() or "router"
    struct = str(structure or "router").strip().lower() or "router"
    mode = str(evaluation_mode or "").strip().lower()
    dte = _band_dte(mgmt.get("long_dte"))
    pt = _band_pt(mgmt.get("profit_target"))
    iv = _band_iv(mgmt.get("iv_rank_min"))
    dlt = _band_delta(mgmt.get("long_target_delta"))
    return f"{root}|{mode or 'any'}|{pol}|{struct}|{dte}|{pt}|{iv}|{dlt}"


def coarse_dna_from_spec(spec: Any) -> str:
    """Extract coarse DNA from a StrategySpec-like object."""
    structure = getattr(spec, "structure", None) or ""
    if getattr(spec, "evaluation_mode", "") == "regime_router":
        structure = "router"
    return coarse_dna_key(
        thesis_id=getattr(spec, "thesis_id", "") or "",
        family_id=getattr(spec, "family_id", "") or "",
        candidate_id=getattr(spec, "candidate_id", "") or "",
        router_policy=getattr(spec, "router_policy", "") or "",
        structure=str(structure or ""),
        management=getattr(spec, "management", None) or {},
        evaluation_mode=getattr(spec, "evaluation_mode", "") or "",
    )


def diversify_rows(
    rows: list[Mapping[str, Any]],
    *,
    top_n: int,
    by_symbol: bool = True,
    by_dna: bool = True,
    dna_key_field: str = "coarse_dna_key",
    fill_remainder: bool = True,
) -> list[dict[str, Any]]:
    """Prefer one seat per symbol and/or coarse DNA among a pre-ranked list.

    When ``fill_remainder`` is True (default, used by promote), backfill by rank
    if diversity constraints leave the list short. Set False for strict shortlists.
    """
    chosen: list[dict[str, Any]] = []
    seen_sym: set[str] = set()
    seen_dna: set[str] = set()
    for row in rows:
        r = dict(row)
        syms = [str(s).upper() for s in (r.get("symbols") or []) if str(s).strip()]
        sym = syms[0] if syms else str(r.get("seat_id") or "")
        dna = str(r.get(dna_key_field) or r.get("family_id") or r.get("seat_id") or "")
        if by_symbol and sym in seen_sym:
            continue
        if by_dna and dna and dna in seen_dna:
            continue
        if by_symbol:
            seen_sym.add(sym)
        if by_dna and dna:
            seen_dna.add(dna)
        chosen.append(r)
        if len(chosen) >= top_n:
            break
    # fill remaining by rank if still short
    if fill_remainder and len(chosen) < top_n:
        have = {c.get("seat_id") for c in chosen}
        for row in rows:
            if row.get("seat_id") in have:
                continue
            chosen.append(dict(row))
            if len(chosen) >= top_n:
                break
    return chosen

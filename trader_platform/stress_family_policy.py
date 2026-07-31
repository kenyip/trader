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
    by = (rotation if rotation is not None else load_rotation()).get("by_hyp_id") or {}
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
    by = (rotation if rotation is not None else load_rotation()).get("by_hyp_id") or {}
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


def _hopeless_fail_ok(
    fails: int,
    oks: int,
    *,
    fail_min: int,
    max_ok_rate: float,
) -> bool:
    """True when fails dominate and residual oks look like soft/legacy flukes.

    2026-07-28 coach: NFLX CCS had lifetime fails≈583 with only ~4 capital_path_ok
    (legacy soft holds). Zero-ok toxic never tripped, so selector kept burning
    B3/B4 on vanity CCS clones every cycle. Treat low ok-rate as toxic once
    fail_min is met — empty queue beats toxic thrash.
    """
    if fail_min <= 0 or fails < int(fail_min):
        return False
    total = int(fails) + int(oks)
    if total <= 0:
        return False
    if oks <= 0:
        return True
    try:
        rate = float(oks) / float(total)
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    return rate <= float(max_ok_rate)


def family_recent_capital_path_outcomes(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    lookback: int = 8,
    window_hours: float = 24.0,
) -> list[bool]:
    """Newest-first capital_path_ok outcomes for symbol×structure (bounded).

    Used for hot fail-streak toxic: lifetime ok-rate can stay healthy while the
    last N create→B3/B4 attempts all die at soft NULL@5% (AAL CCS 2026-07-29).
    """
    if not symbol or not structure or lookback <= 0:
        return []
    by = (rotation if rotation is not None else load_rotation()).get("by_hyp_id") or {}
    if not isinstance(by, dict):
        return []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=float(window_hours)) if window_hours > 0 else None
    sym_u = str(symbol).upper()
    struct = str(structure).strip().lower()
    rows: list[tuple[datetime, bool]] = []
    for row in by.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("symbol") or "").upper() != sym_u:
            continue
        if str(row.get("structure") or "").strip().lower() != struct:
            continue
        ts = _parse_iso_ts(row.get("stressed_at"))
        if ts is None:
            continue
        if cutoff is not None and ts < cutoff:
            continue
        rows.append((ts, bool(row.get("capital_path_ok"))))
    rows.sort(key=lambda t: t[0], reverse=True)
    return [ok for _, ok in rows[: int(lookback)]]


def family_hot_fail_streak_toxic(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    lookback: int = 8,
    window_hours: float = 24.0,
    fail_min: int = 6,
    max_ok_in_lookback: int = 1,
) -> bool:
    """True when the newest lookback stresses are almost all capital_path fails.

    Complements lifetime/window ok-rate toxic: a family with historic oks can still
    mint full-history SHIP clones that burn B3/B4 every cycle while soft-failing @5%.
    Default: ≥6 fails and ≤1 ok in the last 8 stresses (24h window).
    """
    if not symbol or not structure or fail_min <= 0:
        return False
    outcomes = family_recent_capital_path_outcomes(
        symbol,
        structure,
        rotation=rotation,
        lookback=lookback,
        window_hours=window_hours,
    )
    if len(outcomes) < int(fail_min):
        return False
    oks = sum(1 for ok in outcomes if ok)
    fails = len(outcomes) - oks
    return fails >= int(fail_min) and oks <= int(max_ok_in_lookback)


def family_challenge_toxic(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    window_hours: float = 6.0,
    toxic_fail_min: int = 8,
    lifetime_fail_min: int = 20,
    max_ok_rate: float = 0.05,
    streak_lookback: int = 8,
    streak_window_hours: float = 24.0,
    streak_fail_min: int = 6,
    streak_max_ok: int = 1,
) -> bool:
    """Hard-block hopeless symbol×structure families (same thresholds as selector).

    Toxic when:
    - (recent or lifetime) fails meet the floor AND oks are zero or a tiny residual
      rate (default ≤5% oks); or
    - the newest stress streak is almost all capital_path fails (hot fail streak),
      even if lifetime ok-rate still looks healthy.

    Zero-ok remains the hard case; low ok-rate catches legacy soft capital_path
    flukes (NFLX CCS 583f/4ok). Hot streak catches AAL CCS clone thrash where
    full-history SHIP dies at B4 soft NULL@5% repeatedly (2026-07-29 coach).
    """
    if not symbol or not structure:
        return False
    rot = rotation if rotation is not None else load_rotation()
    if toxic_fail_min > 0 and window_hours > 0:
        fails, oks = family_window_fail_ok(
            symbol, structure, rotation=rot, window_hours=window_hours
        )
        if _hopeless_fail_ok(
            fails, oks, fail_min=int(toxic_fail_min), max_ok_rate=max_ok_rate
        ):
            return True
    if lifetime_fail_min > 0:
        lf, lo = family_lifetime_fail_ok(symbol, structure, rotation=rot)
        if _hopeless_fail_ok(
            lf, lo, fail_min=int(lifetime_fail_min), max_ok_rate=max_ok_rate
        ):
            return True
    if streak_fail_min > 0 and streak_lookback > 0:
        if family_hot_fail_streak_toxic(
            symbol,
            structure,
            rotation=rot,
            lookback=int(streak_lookback),
            window_hours=float(streak_window_hours),
            fail_min=int(streak_fail_min),
            max_ok_in_lookback=int(streak_max_ok),
        ):
            return True
    return False


def family_create_saturated(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    min_capital_path_ok: int = 25,
) -> bool:
    """True when symbol×structure already has enough capital_path_ok survivors.

    Complementary to toxic (hopeless fails): *successful* families can still thrash
    evolve max_create with dens2 metric clones (AAL PCS ~280 ok) while unsaturated
    multi-leg SHIPs (F CCS, SNAP PCS, …) never get a registry row. Skip *new*
    creates once lifetime capital_path_ok ≥ min (default 25); updates allowed.
    2026-07-29 continuum coach.
    """
    if not symbol or not structure or min_capital_path_ok <= 0:
        return False
    rot = rotation if rotation is not None else load_rotation()
    _fails, oks = family_lifetime_fail_ok(symbol, structure, rotation=rot)
    return int(oks) >= int(min_capital_path_ok)


_DEFAULT_ML_STRUCTURES: tuple[str, ...] = (
    "put_credit_spread",
    "call_credit_spread",
    "iron_condor",
)


def unsaturated_discovery_symbols(
    *,
    limit: int = 6,
    rotation: dict[str, Any] | None = None,
    structures: tuple[str, ...] | list[str] | None = None,
    exclude: set[str] | None = None,
    universe: list[str] | None = None,
    min_capital_path_ok_sat: int = 25,
    recent_window_hours: float = 6.0,
    recent_fail_thrash_min: int = 6,
) -> list[str]:
    """Symbols with ≥1 multi-leg family that is neither toxic nor create-saturated.

    Research-ranked evolve tops often tunnel into AAL/NFLX/PLTR while SNAP/CCL/PFE/KO
    stay off the board — then every multi-leg registry row is already stressed and the
    B3/B4 selector stays empty (2026-07-30 continuum coach). Prefer names that can still
    accept *new* creates under family policy.

    2026-07-30T1500 coach: also demote *recent fail thrash* cold names (AAPL/AMD/ARM/COIN
    with ≥6 recent fails and 0 recent oks) so unsat inject does not refill B3/B4 with the
    same doomed mega-cap clones while F/CCL/SNAP/KO starve. Proven unsaturated (lifetime
    capital_path_ok > 0) still ranks first even if recent stress mixed.
    """
    if limit <= 0:
        return []
    rot = rotation if rotation is not None else load_rotation()
    structs = tuple(structures or _DEFAULT_ML_STRUCTURES)
    ex = {str(s).strip().upper() for s in (exclude or set()) if s}
    if universe is None:
        try:
            from trader_platform.research.universe import load_universe

            universe = list(load_universe() or [])
        except Exception:  # noqa: BLE001
            universe = [
                "IWM",
                "F",
                "SOFI",
                "AAL",
                "PFE",
                "SNAP",
                "CCL",
                "BAC",
                "TSLL",
                "KO",
                "XOM",
                "PLTR",
                "NFLX",
                "SMCI",
            ]
    # Prefer proven-unsaturated (1..sat-1 lifetime oks) over cold names; within each
    # tier prefer recent capital_path oks and fewer recent fails (not pure ok_mass).
    scored: list[tuple[int, int, int, int, int, str]] = []
    for raw in universe:
        sym = str(raw or "").strip().upper()
        if not sym or sym in ex:
            continue
        open_structs = 0
        ok_mass = 0
        # Recent window across *all* candidate structs (incl. toxic/sat) so a toxic
        # PCS thrash + cold empty CCS cannot disguise the symbol as fresh (AMD 2026-07-30).
        recent_fail_mass = 0
        recent_ok_mass = 0
        for st in structs:
            rf, ro = family_window_fail_ok(
                sym, st, rotation=rot, window_hours=float(recent_window_hours)
            )
            recent_fail_mass += int(rf)
            recent_ok_mass += int(ro)
        for st in structs:
            if family_challenge_toxic(sym, st, rotation=rot):
                continue
            if family_create_saturated(
                sym, st, rotation=rot, min_capital_path_ok=min_capital_path_ok_sat
            ):
                continue
            open_structs += 1
            _f, oks = family_lifetime_fail_ok(sym, st, rotation=rot)
            ok_mass += int(oks)
        if open_structs <= 0:
            continue
        # Cold pure-fail thrash: skip inject (selector would B3/B4 burn again).
        if (
            ok_mass <= 0
            and recent_ok_mass <= 0
            and recent_fail_thrash_min > 0
            and recent_fail_mass >= int(recent_fail_thrash_min)
        ):
            continue
        # tier0 = has some capital_path survivors but room to create; tier1 = cold
        tier = 0 if 0 < ok_mass < int(min_capital_path_ok_sat) else 1
        scored.append(
            (
                tier,
                -int(recent_ok_mass),
                int(recent_fail_mass),
                -int(open_structs),
                int(ok_mass),
                sym,
            )
        )
    scored.sort()
    out: list[str] = []
    for _t, _ro, _rf, _os, _ok, sym in scored:
        out.append(sym)
        if len(out) >= int(limit):
            break
    return out


def unsaturated_discovery_families(
    *,
    limit: int = 8,
    rotation: dict[str, Any] | None = None,
    structures: tuple[str, ...] | list[str] | None = None,
    exclude_symbols: set[str] | None = None,
    universe: list[str] | None = None,
    min_capital_path_ok_sat: int = 25,
    recent_window_hours: float = 6.0,
    recent_fail_thrash_min: int = 6,
) -> list[dict[str, Any]]:
    """Open (symbol, structure) pairs that may still accept *new* creates.

    Symbol-only ``unsaturated_discovery_symbols`` can inject F while F PCS is toxic
    and only F CCS is open — DR then wastes the pop on doomed F PCS / NFLX CCS SHIPs
    and max_create stays 0 because every positive SHIP is toxic/saturated (2026-07-31
    continuum coach: unstressed multi-leg registry count=0, stress queue empty).
    """
    if limit <= 0:
        return []
    rot = rotation if rotation is not None else load_rotation()
    structs = tuple(structures or _DEFAULT_ML_STRUCTURES)
    ex = {str(s).strip().upper() for s in (exclude_symbols or set()) if s}
    if universe is None:
        try:
            from trader_platform.research.universe import load_universe

            universe = list(load_universe() or [])
        except Exception:  # noqa: BLE001
            universe = [
                "IWM",
                "F",
                "SOFI",
                "AAL",
                "PFE",
                "SNAP",
                "CCL",
                "BAC",
                "TSLL",
                "KO",
                "XOM",
                "PLTR",
                "NFLX",
                "SMCI",
            ]

    scored: list[tuple[int, int, int, int, str, str]] = []
    for raw in universe:
        sym = str(raw or "").strip().upper()
        if not sym or sym in ex:
            continue
        # Symbol-level recent thrash (all structs) — same guard as symbol inject.
        recent_fail_mass = 0
        recent_ok_mass = 0
        for st in structs:
            rf, ro = family_window_fail_ok(
                sym, st, rotation=rot, window_hours=float(recent_window_hours)
            )
            recent_fail_mass += int(rf)
            recent_ok_mass += int(ro)
        for st in structs:
            if family_challenge_toxic(sym, st, rotation=rot):
                continue
            if family_create_saturated(
                sym, st, rotation=rot, min_capital_path_ok=min_capital_path_ok_sat
            ):
                continue
            _f, oks = family_lifetime_fail_ok(sym, st, rotation=rot)
            ok_i = int(oks)
            # Skip cold pure-fail thrash at symbol level when this family also has 0 oks.
            if (
                ok_i <= 0
                and recent_ok_mass <= 0
                and recent_fail_thrash_min > 0
                and recent_fail_mass >= int(recent_fail_thrash_min)
            ):
                continue
            tier = 0 if 0 < ok_i < int(min_capital_path_ok_sat) else 1
            # Prefer proven-open families, then recent ok mass, fewer fails, more lifetime ok.
            scored.append(
                (
                    tier,
                    -int(recent_ok_mass),
                    int(recent_fail_mass),
                    -ok_i,
                    sym,
                    str(st),
                )
            )
    scored.sort()
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    per_sym: dict[str, int] = {}
    for tier, _ro, _rf, neg_ok, sym, st in scored:
        key = (sym, st)
        if key in seen:
            continue
        # Cap 2 open structures per symbol so one name cannot fill the whole inject.
        if per_sym.get(sym, 0) >= 2:
            continue
        seen.add(key)
        per_sym[sym] = per_sym.get(sym, 0) + 1
        out.append(
            {
                "symbol": sym,
                "structure": st,
                "tier": int(tier),
                "lifetime_ok": int(-neg_ok),
                "source": "unsaturated_discovery_family",
            }
        )
        if len(out) >= int(limit):
            break
    return out


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

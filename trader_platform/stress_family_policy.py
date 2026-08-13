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


def family_reopen_sample_exhausted(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    lookback: int = 6,
    window_hours: float = 4.0,
    fail_min: int = 4,
    max_ok_in_lookback: int = 0,
) -> bool:
    """True when a short-window post-reopen sample is already all fails.

    Thin/moderate living reopen (``streak_min_living``) exists so leftover 24h
    fail streaks after prune/sat floors do not freeze EDGE. It is not a license
    to burn B3/B4 all night on the same CCS family (2026-08-12T2100 coach:
    F/CCL/SNAP CCS 10–11 recent fails / 0–1 ok after create-sat unlock). A 4h
    burst of ≥4 capital_path fails and 0 oks re-arms hot-streak even when
    ``living_count`` is still below ``streak_min_living``.
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
    living_count: int | None = None,
    streak_min_living: int = 12,
    streak_reopen_min_lifetime_ok: int = 3,
    reopen_lookback: int = 6,
    reopen_window_hours: float = 4.0,
    reopen_fail_min: int = 4,
    reopen_max_ok: int = 0,
) -> bool:
    """Hard-block hopeless symbol×structure families (same thresholds as selector).

    Toxic when:
    - (recent or lifetime) fails meet the floor AND oks are zero or a tiny residual
      rate (default ≤5% oks); or
    - the newest stress streak is almost all capital_path fails (hot fail streak),
      even if lifetime ok-rate still looks healthy — **only when living dens is thick**.

    Zero-ok remains the hard case; low ok-rate catches legacy soft capital_path
    flukes (NFLX CCS 583f/4ok). Hot streak catches AAL CCS clone thrash where
    full-history SHIP dies at B4 soft NULL@5% repeatedly (2026-07-29 coach).

    Thin-living hot-streak reopen (2026-08-11 continuum coach): after prune /
    saturation floors, preferred families can show lifetime capital_path_ok≫0 with
    living_count 0–5 while a recent fail streak still trips hot toxic. That froze
    both evolve creates and B3/B4 on F CCS / IWM PCS-class DNA and left unsat
    inject on mega-cap CCS zero_trades with unstressed_ml=0. When ``living_count``
    is provided and below ``streak_min_living``
    **and** lifetime capital_path_ok ≥ ``streak_reopen_min_lifetime_ok`` (default 3),
    skip the hot-streak arm only — lifetime/window hopeless toxic still hard-blocks,
    and zero-ok / fluke families stay streak-toxic even at living=0 (INTC PCS).
    ``living_count=None`` keeps legacy streak behavior (unit tests / callers without
    registry context).

    Moderate-living reopen floor (2026-08-12 continuum coach): default
    ``streak_min_living`` raised 6→12. After sat floors, preferred CCS twins often
    sit at living dens 6–8 (F/PFE/SNAP/CCL CCS) with lifetime capital_path_ok≫0 while
    hot-streak still blocked creates. Unsat then fell through to cold mega-cap
    CCS/IC (AAPL/AMD/AMZN/XOM zero_trades), DR created 0 multi-leg, and the stress
    selector stayed n=0 (TTL leaders + toxic-only unstressed). Keep thick dens
    (AAL CCS living≫12) hot-toxic; reopen moderate dens so B3/B4 can rotate again.

    Post-reopen exhaust (2026-08-12T2100 coach): the living-floor skip applies
    only while the *short* 4h sample is not already a fail burst. After unlock,
    F/CCL/SNAP CCS minted all night (55 stresses / ~6h) with 0–1 capital_path
    oks while CCL PCS quietly printed 11/12 SHIP@5%. Once ≥4 fails and 0 oks
    land inside 4h, fall through to hot-streak even at living 6–8 so search
    budget moves to unsaturated survivors instead of vanity CCS clones.
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
        # Thin living + proven lifetime oks → allow fresh DNA after prune.
        # Thin living + zero/fluke oks → keep hot-streak block (no INTC reopen).
        if living_count is not None and int(living_count) < int(streak_min_living):
            _lf2, lo2 = family_lifetime_fail_ok(symbol, structure, rotation=rot)
            if int(lo2) >= int(streak_reopen_min_lifetime_ok):
                # Leftover 24h streak after prune/sat may still reopen — unless
                # the post-reopen 4h sample already failed (coach 2026-08-12T2100).
                if not family_reopen_sample_exhausted(
                    symbol,
                    structure,
                    rotation=rot,
                    lookback=int(reopen_lookback),
                    window_hours=float(reopen_window_hours),
                    fail_min=int(reopen_fail_min),
                    max_ok_in_lookback=int(reopen_max_ok),
                ):
                    return False
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


def living_multi_leg_family_counts(
    hypotheses: list[dict[str, Any]] | None = None,
) -> dict[tuple[str, str], int]:
    """Count living registry rows per (symbol, structure).

    Used to reopen *ghost-saturated* families after prune removed capital_path
    survivors from hypotheses.yaml while STRESS_ROTATION still shows ≥25 oks
    (2026-08-10 continuum coach: SNAP/TSLL CCS SHIP + empty stress queue).
    """
    rows = hypotheses
    if rows is None:
        try:
            from trader_platform.hypothesis_registry import HypothesisRegistry

            store = HypothesisRegistry().load()
            rows = list(store.get("hypotheses") or [])
        except Exception:  # noqa: BLE001
            return {}
    counts: dict[tuple[str, str], int] = {}
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        sym = dna_primary_symbol(raw.get("dna") or raw)
        if not sym:
            instruments = raw.get("instruments") or []
            if isinstance(instruments, (list, tuple)) and instruments:
                sym = str(instruments[0] or "").strip().upper() or None
        st = dna_structure(raw.get("dna") or raw)
        if not st:
            st = str(raw.get("structure") or "").strip().lower() or None
        if not sym or not st:
            continue
        key = (str(sym).strip().upper(), str(st).strip().lower())
        counts[key] = int(counts.get(key, 0)) + 1
    return counts


def family_create_saturated(
    symbol: str | None,
    structure: str | None,
    *,
    rotation: dict[str, Any] | None = None,
    min_capital_path_ok: int = 25,
    living_count: int | None = None,
    min_living: int = 6,
) -> bool:
    """True when symbol×structure already has enough capital_path_ok survivors.

    Complementary to toxic (hopeless fails): *successful* families can still thrash
    evolve max_create with dens2 metric clones (AAL PCS ~280 ok) while unsaturated
    multi-leg SHIPs (F CCS, SNAP PCS, …) never get a registry row. Skip *new*
    creates once lifetime capital_path_ok ≥ min (default 25); updates allowed.
    2026-07-29 continuum coach.

    Ghost-prune reopen (2026-08-10 continuum coach): after hard-cap prune, rotation
    can still show ≥25 capital_path_ok while living registry DNA for the family is
    0 (SNAP/TSLL/CCL CCS etc.). Ledger-only saturation then freezes creates forever
    and the B3/B4 queue stays empty even when DR re-discovers SHIP. When
    ``living_count`` is provided and below ``min_living``, do **not** treat the
    family as saturated. ``living_count=None`` keeps legacy ledger-only behavior
    (unit tests / callers without registry context).

    Thin-living floor (2026-08-11 continuum coach): default ``min_living`` raised
    3→6. After prune, preferred families often retain only 3–4 living rows while
    ledger oks ≥25 (SNAP/F/PFE/CCL CCS). That tripped sat, unsat inject fell
    through to cold mega-cap CCS (AVGO/DIA/META) with zero_trades, and the stress
    queue stayed empty except toxic KO/NFLX/AAPL. Require a thicker living dens
    before freezing creates; F IC-style monocultures with living≫6 stay saturated.

    Edge-freeze reopen (2026-08-12 continuum coach): when the *global* open create
    surface collapses (only toxic unstressed multi-leg left; preferred CCS/IC sit at
    living 6–7 with oks≥25), callers pass a higher ``min_living`` (default freeze
    floor 12 via ``resolve_create_sat_min_living`` / unsat auto-relax). Thick
    monocultures (AAL PCS hundreds living) stay saturated; moderate preferred dens
    can mint novel DNA again so B3/B4 is not stuck on NFLX/PLTR/SNAP toxic-only.
    """
    if not symbol or not structure or min_capital_path_ok <= 0:
        return False
    if living_count is not None and int(living_count) < int(min_living):
        return False
    rot = rotation if rotation is not None else load_rotation()
    _fails, oks = family_lifetime_fail_ok(symbol, structure, rotation=rot)
    return int(oks) >= int(min_capital_path_ok)


# Edge-freeze defaults: reopen moderate living sat when open create families collapse.
_EDGE_FREEZE_OPEN_FAMILY_MAX = 2
_EDGE_FREEZE_MIN_LIVING = 12
_NORMAL_CREATE_SAT_MIN_LIVING = 6


_DEFAULT_ML_STRUCTURES: tuple[str, ...] = (
    "put_credit_spread",
    "call_credit_spread",
    "iron_condor",
)

# Cheap/liquid $3k-sleeve discovery names preferred when tier-0 proven-open is empty.
# Without this, cold inject sorts alphabetically through universe and burns cycles on
# AVGO/AMD/GOOGL zero-trade SHIPs while F IC / KO PCS / IWM PCS stay uncreated
# (2026-08-03 continuum coach: unsat_fams → AMD+AVGO only; stress queue empty).
_PREFERRED_COLD_DISCOVERY: tuple[str, ...] = (
    "F",
    "KO",
    "IWM",
    "SOFI",
    "PFE",
    "SNAP",
    "CCL",
    "TSLL",
    "BAC",
    "AAL",
    "SMCI",
    "XOM",
    "PLTR",
    "NFLX",
    "INTC",
    # MU removed from preferred 2026-08-08 coach: cold MU CCS/IC zero_trades thrash
    # led unsat inject every cycle once F/KO/SNAP families were toxic/saturated.
)
_PREFERRED_COLD_RANK: dict[str, int] = {
    s: i for i, s in enumerate(_PREFERRED_COLD_DISCOVERY)
}
_MEGA_CAP_COLD_DEMOTE: frozenset[str] = frozenset(
    {
        "AVGO",
        "GOOGL",
        "GOOG",
        "META",
        "MSFT",
        "NVDA",
        "AMD",
        "AMZN",
        "AAPL",
        "DIA",
        "QQQ",
        "SPY",
        "JPM",
        "NIO",
        "COIN",
        "ARM",
        "TSM",
        "QCOM",
        "CRM",
        "TSLA",  # 2026-08-08: zero-trade cold twin with MU on DR inject
        "MU",  # expensive; zero synthetic multi-leg trades in residual evolve
    }
)


def _cold_symbol_rank(sym: str) -> tuple[int, int, int]:
    """Lower is better: preferred bucket, preferred index, mega demote."""
    s = str(sym or "").strip().upper()
    pref = _PREFERRED_COLD_RANK.get(s)
    preferred_bucket = 0 if pref is not None else 1
    pref_idx = int(pref) if pref is not None else 999
    mega = 1 if s in _MEGA_CAP_COLD_DEMOTE else 0
    return preferred_bucket, pref_idx, mega


def _default_research_universe() -> list[str]:
    try:
        from trader_platform.research.universe import load_universe

        return list(load_universe() or [])
    except Exception:  # noqa: BLE001
        return [
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
            "INTC",
            "XOM",
            "PLTR",
            "NFLX",
            "SMCI",
        ]


def _effective_discovery_universe(universe: list[str] | None) -> list[str]:
    """Research universe ∪ preferred cold discovery names (order preserved).

    2026-08-07 continuum coach: preferred cold listed KO/INTC but ``universe.yaml``
    omitted them, so unsat inject never saw tier-0 KO PCS and burned DR slots on
    MU/TSLA/AAPL zero-trade thrash while stress queue stayed empty. Always union
    preferred names so a stale research universe cannot starve EDGE inject.
    """
    base = list(universe) if universe is not None else _default_research_universe()
    out: list[str] = []
    seen: set[str] = set()
    for raw in list(base) + list(_PREFERRED_COLD_DISCOVERY):
        s = str(raw or "").strip().upper()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def resolve_create_sat_min_living(
    *,
    rotation: dict[str, Any] | None = None,
    structures: tuple[str, ...] | list[str] | None = None,
    universe: list[str] | None = None,
    living_family_counts: dict[tuple[str, str], int] | None = None,
    use_registry_living_counts: bool = True,
    open_family_max: int = _EDGE_FREEZE_OPEN_FAMILY_MAX,
    normal_min_living: int = _NORMAL_CREATE_SAT_MIN_LIVING,
    freeze_min_living: int = _EDGE_FREEZE_MIN_LIVING,
    min_capital_path_ok_sat: int = 25,
) -> int:
    """Return ``min_living`` for create-sat checks under edge-freeze policy.

    When ≤ ``open_family_max`` multi-leg families remain open at the normal sat
    floor, raise the living floor so moderate preferred dens (6–11) can create
    again. Thick monocultures stay blocked. Does not recurse into auto-relax.
    """
    open_fams = unsaturated_discovery_families(
        limit=int(open_family_max) + 1,
        rotation=rotation,
        structures=structures,
        universe=universe,
        min_capital_path_ok_sat=min_capital_path_ok_sat,
        living_family_counts=living_family_counts,
        use_registry_living_counts=use_registry_living_counts,
        min_living_for_sat=int(normal_min_living),
        auto_edge_freeze=False,
    )
    if len(open_fams) <= int(open_family_max):
        return int(freeze_min_living)
    return int(normal_min_living)


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
    living_family_counts: dict[tuple[str, str], int] | None = None,
    use_registry_living_counts: bool = False,
    min_living_for_sat: int | None = None,
    auto_edge_freeze: bool = True,
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

    2026-08-07 coach: effective universe always unions preferred cold discovery so
    KO/INTC cannot disappear when research universe drifts.

    2026-08-10 coach: optional living registry counts reopen ghost-saturated families
    (ledger oks ≥ sat but living DNA pruned). Default off so unit tests stay
    ledger-pure; evolve_tick enables registry-aware counts in production.

    2026-08-12 evening coach: hard-skip cold mega symbols (not mere rank demote) and
    auto edge-freeze raise of create-sat ``min_living`` when open surface collapses.
    """
    if limit <= 0:
        return []
    rot = rotation if rotation is not None else load_rotation()
    structs = tuple(structures or _DEFAULT_ML_STRUCTURES)
    ex = {str(s).strip().upper() for s in (exclude or set()) if s}
    # Default path: research universe ∪ preferred cold. Explicit universe= keeps caller control (tests).
    if universe is None:
        universe = _effective_discovery_universe(None)
    else:
        universe = [str(s or "").strip().upper() for s in universe if str(s or "").strip()]
    live_map = living_family_counts
    if live_map is None and use_registry_living_counts:
        live_map = living_multi_leg_family_counts()
    sat_ml = (
        int(min_living_for_sat)
        if min_living_for_sat is not None
        else int(_NORMAL_CREATE_SAT_MIN_LIVING)
    )
    if auto_edge_freeze and min_living_for_sat is None:
        sat_ml = resolve_create_sat_min_living(
            rotation=rot,
            structures=structs,
            universe=universe,
            living_family_counts=live_map,
            use_registry_living_counts=False,
            min_capital_path_ok_sat=min_capital_path_ok_sat,
        )
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
            living = None
            if live_map is not None:
                living = int(live_map.get((sym, str(st).strip().lower()), 0))
            if family_challenge_toxic(sym, st, rotation=rot, living_count=living):
                continue
            if family_create_saturated(
                sym,
                st,
                rotation=rot,
                min_capital_path_ok=min_capital_path_ok_sat,
                living_count=living,
                min_living=sat_ml,
            ):
                continue
            open_structs += 1
            _f, oks = family_lifetime_fail_ok(sym, st, rotation=rot)
            ok_mass += int(oks)
        if open_structs <= 0:
            continue
        # Cold pure-fail thrash: skip whole-symbol inject (selector would B3/B4 burn).
        # Family-level inject uses a sibling-safe thrash rule separately.
        if (
            ok_mass <= 0
            and recent_ok_mass <= 0
            and recent_fail_thrash_min > 0
            and recent_fail_mass >= int(recent_fail_thrash_min)
        ):
            continue
        # tier0 = any proven capital_path history with create room (includes ghost-prune
        # reopen where ok_mass ≥ sat but living DNA was pruned); tier1 = cold.
        tier = 0 if ok_mass > 0 else 1
        pref_b, pref_i, mega = _cold_symbol_rank(sym)
        # Hard-skip cold mega-cap symbols (2026-08-12 evening coach) — same as families.
        if tier >= 1 and sym in _MEGA_CAP_COLD_DEMOTE:
            continue
        scored.append(
            (
                tier,
                -int(recent_ok_mass),
                int(recent_fail_mass),
                # Cold: preferred liquid before alphabetical mega-caps (2026-08-03).
                pref_b if tier >= 1 else 0,
                pref_i if tier >= 1 else 0,
                mega if tier >= 1 else 0,
                -int(open_structs),
                int(ok_mass),
                sym,
            )
        )
    scored.sort()
    out: list[str] = []
    for row in scored:
        sym = row[-1]
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
    living_family_counts: dict[tuple[str, str], int] | None = None,
    use_registry_living_counts: bool = True,
    min_living_for_sat: int | None = None,
    auto_edge_freeze: bool = True,
) -> list[dict[str, Any]]:
    """Open (symbol, structure) pairs that may still accept *new* creates.

    Symbol-only ``unsaturated_discovery_symbols`` can inject F while F PCS is toxic
    and only F CCS is open — DR then wastes the pop on doomed F PCS / NFLX CCS SHIPs
    and max_create stays 0 because every positive SHIP is toxic/saturated (2026-07-31
    continuum coach: unstressed multi-leg registry count=0, stress queue empty).

    2026-08-10 coach: optional living registry counts reopen ghost-saturated families.

    2026-08-12 evening coach: ``auto_edge_freeze`` raises create-sat living floor when
    ≤2 families open at normal floor so moderate preferred dens can mint again.
    """
    if limit <= 0:
        return []
    rot = rotation if rotation is not None else load_rotation()
    structs = tuple(structures or _DEFAULT_ML_STRUCTURES)
    ex = {str(s).strip().upper() for s in (exclude_symbols or set()) if s}
    # Default path unions preferred cold (KO/INTC…). Explicit universe= keeps tests pure.
    if universe is None:
        universe = _effective_discovery_universe(None)
    else:
        universe = [str(s or "").strip().upper() for s in universe if str(s or "").strip()]
    live_map = living_family_counts
    if live_map is None and use_registry_living_counts:
        live_map = living_multi_leg_family_counts()
    sat_ml = (
        int(min_living_for_sat)
        if min_living_for_sat is not None
        else int(_NORMAL_CREATE_SAT_MIN_LIVING)
    )
    if auto_edge_freeze and min_living_for_sat is None:
        # Avoid recursion: resolve uses auto_edge_freeze=False + normal floor scan.
        sat_ml = resolve_create_sat_min_living(
            rotation=rot,
            structures=structs,
            universe=universe,
            living_family_counts=live_map,
            use_registry_living_counts=False,
            min_capital_path_ok_sat=min_capital_path_ok_sat,
        )

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
            living = None
            if live_map is not None:
                living = int(live_map.get((sym, str(st).strip().lower()), 0))
            if family_challenge_toxic(sym, st, rotation=rot, living_count=living):
                continue
            if family_create_saturated(
                sym,
                st,
                rotation=rot,
                min_capital_path_ok=min_capital_path_ok_sat,
                living_count=living,
                min_living=sat_ml,
            ):
                continue
            _f, oks = family_lifetime_fail_ok(sym, st, rotation=rot)
            ok_i = int(oks)
            fam_rf, fam_ro = family_window_fail_ok(
                sym, st, rotation=rot, window_hours=float(recent_window_hours)
            )
            # Family-scoped thrash only. Symbol-level fail mass used to zero out the
            # last open preferred family (INTC IC) while sibling PCS was toxic
            # (2026-08-08 coach: unsat → MU/TSLA zero_trades; stress queue empty).
            if (
                ok_i <= 0
                and int(fam_ro) <= 0
                and recent_fail_thrash_min > 0
                and int(fam_rf) >= int(recent_fail_thrash_min)
            ):
                continue
            # Still demote families on symbols with pure symbol thrash via score —
            # do not hard-skip an open sibling structure.
            # tier0 includes ghost-prune reopen (ok_i ≥ sat, living below floor).
            tier = 0 if ok_i > 0 else 1
            pref_b, pref_i, mega = _cold_symbol_rank(sym)
            # Hard-skip cold mega-cap families (2026-08-12 continuum coach).
            # Rank demote alone still let AAPL/AMD/AMZN/AVGO CCS fill unsat when
            # every preferred multi-leg family was sat or hot-toxic — DR then burned
            # pop on zero_trades and stress queue stayed empty. Prefer empty inject
            # (or preferred cold like XOM/INTC) over mega zero-trade thrash.
            if tier >= 1 and sym in _MEGA_CAP_COLD_DEMOTE:
                continue
            # Prefer proven-open families, then recent ok mass, fewer fails, more lifetime ok.
            # Cold tier: preferred liquid $3k names before alphabetical mega-caps.
            scored.append(
                (
                    tier,
                    -int(recent_ok_mass),
                    int(fam_rf),  # family fails, not whole-symbol burn
                    pref_b if tier >= 1 else 0,
                    pref_i if tier >= 1 else 0,
                    mega if tier >= 1 else 0,
                    -ok_i,
                    sym,
                    str(st),
                )
            )
    scored.sort()
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    per_sym: dict[str, int] = {}
    # Fill tier-0 (proven unsaturated) first. Cap *non-preferred* cold mega-caps so
    # AVGO/DIA/GOOGL cannot crowd inject (2026-07-31). When tier-0 is empty (all
    # proven families toxic-hot or saturated), allow full limit of preferred cold
    # opens (F IC, KO PCS, IWM PCS, …) — 2026-08-03 coach.
    n_tier0 = sum(1 for row in scored if int(row[0]) == 0)
    cold_cap_nonpreferred = max(2, int(limit) // 3)
    cold_cap_preferred = int(limit) if n_tier0 == 0 else max(cold_cap_nonpreferred, int(limit) // 2)
    n_cold_pref = 0
    n_cold_other = 0
    for row in scored:
        tier = int(row[0])
        neg_ok = int(row[6])
        sym = str(row[7])
        st = str(row[8])
        key = (sym, st)
        if key in seen:
            continue
        if tier >= 1:
            pref_b, _pref_i, _mega = _cold_symbol_rank(sym)
            if pref_b == 0:
                if n_cold_pref >= cold_cap_preferred:
                    continue
            else:
                if n_cold_other >= cold_cap_nonpreferred:
                    continue
        # Cap 2 open structures per symbol so one name cannot fill the whole inject.
        if per_sym.get(sym, 0) >= 2:
            continue
        seen.add(key)
        per_sym[sym] = per_sym.get(sym, 0) + 1
        if tier >= 1:
            pref_b, _pi, _mg = _cold_symbol_rank(sym)
            if pref_b == 0:
                n_cold_pref += 1
            else:
                n_cold_other += 1
        out.append(
            {
                "symbol": sym,
                "structure": st,
                "tier": tier,
                "lifetime_ok": int(-neg_ok),
                "source": "unsaturated_discovery_family",
                "create_sat_min_living": sat_ml,
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

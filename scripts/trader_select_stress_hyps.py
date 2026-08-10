#!/usr/bin/env python3
"""Select multi-leg hyps for B3/B4 quality-cycle stress.

Problem this fixes:
  QUALITY_SHORTLIST stress_priority leaders alone were re-stressed every cycle
  (identical regime/cost artifacts) while evolve minted dozens of unstressed SHIPs.

Policy:
  - Keep up to `n_leaders` shortlist stress_priority multi-leg leaders (regression),
    but **skip** leaders already capital_path_ok in STRESS_ROTATION with a fresh
    stressed_at inside leader_ttl_hours (default 24h) so B3/B4 budget goes to new DNA.
  - Fill remaining slots with unstressed multi-leg SHIP-ish hyps from the registry
    (or evolve_dr logs as fallback), preferring higher evolve scores / trade counts
    and symbol diversity. Prefer n_trades >= min_fresh_trades when known.
  - Never include CSP/wheel single-leg here (pcs_* stress scripts are multi-leg).

Prints comma-separated hyp ids on stdout. JSON summary with --json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SHORTLIST = _REPO / "reports" / "bootstrap" / "QUALITY_SHORTLIST.json"
_HYPS = _REPO / "trader_platform" / "data" / "hypotheses.yaml"
_EVOLVE_LOG_DIR = _REPO / ".cache" / "platform" / "quality_residual"
_ROTATION = _REPO / "reports" / "bootstrap" / "STRESS_ROTATION.json"
_ML = frozenset({"put_credit_spread", "call_credit_spread", "iron_condor"})
# Markers must NOT false-match evolve DNA hashes. Bare "b3:" / "b4:" matched
# hex suffixes like "...89b3:verdict=SHIP" and starved the unstressed queue
# (only F/CCL IC left outside rotation but both ended in b3 — 2026-08-07 coach).
# Loose "regime_" / "cost_" also over-match paths; keep explicit stress tokens.
_STRESS_MARKERS = (
    "regime_stress",
    "cost_stress",
    "pcs_regime",
    "pcs_cost",
    "stress_regime",
    "stress_cost",
    "dense_neg",
    "b3_hold",
    "b4_cost",
    "b4_slip",
    "capital_path_ok",
    "window_max_dd",
    "stress_rotation",
)


def _load_rotation() -> dict[str, Any]:
    if not _ROTATION.is_file():
        return {}
    try:
        d = json.loads(_ROTATION.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def _rotation_stressed_ids() -> set[str]:
    """Hyp ids already B3/B4'd via rotation ledger (avoids hyp yaml write races)."""
    d = _load_rotation()
    by = d.get("by_hyp_id") or {}
    return {str(k) for k in by.keys()}


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


def _leader_freshly_capital_ok(hid: str, *, ttl_hours: float) -> bool:
    """True when leader already has a fresh capital_path_ok B3/B4 on the ledger."""
    if ttl_hours <= 0:
        return False
    by = (_load_rotation().get("by_hyp_id") or {})
    row = by.get(hid) or by.get(str(hid))
    if not isinstance(row, dict):
        return False
    if not row.get("capital_path_ok"):
        return False
    ts = _parse_iso_ts(row.get("stressed_at"))
    if ts is None:
        return False
    age = datetime.now(timezone.utc) - ts
    return age <= timedelta(hours=float(ttl_hours))


def _metric_twin_key(row: dict[str, Any]) -> tuple[Any, ...]:
    """Evolve-score fingerprint — identical twins burn B3/B4 slots without new info."""
    sym = str(row.get("symbol") or "?").upper()
    st = str(row.get("structure") or "")
    sc_r: float | None = None
    raw_sc = row.get("score")
    if raw_sc is not None:
        try:
            sc = float(raw_sc)
            if sc > -1e8:
                sc_r = round(sc, 1)
        except (TypeError, ValueError):
            sc_r = None
    try:
        n = int(row.get("n_trades") or 0)
    except (TypeError, ValueError):
        n = 0
    return (sym, st, sc_r, n)


def _family_window_fail_ok(
    symbol: str | None,
    structure: str | None,
    *,
    window_hours: float = 6.0,
) -> tuple[int, int]:
    """Return (fails, oks) for symbol×structure inside the recent stress window."""
    if not symbol or not structure or window_hours <= 0:
        return 0, 0
    sym_u = str(symbol).upper()
    st = str(structure)
    by = _load_rotation().get("by_hyp_id") or {}
    now = datetime.now(timezone.utc)
    fails = 0
    oks = 0
    for row in by.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("symbol") or "").upper() != sym_u:
            continue
        if str(row.get("structure") or "") != st:
            continue
        ts = _parse_iso_ts(row.get("stressed_at"))
        if ts is None:
            continue
        if (now - ts) > timedelta(hours=float(window_hours)):
            continue
        if row.get("capital_path_ok"):
            oks += 1
        else:
            fails += 1
    return fails, oks


def _family_lifetime_fail_ok(symbol: str | None, structure: str | None) -> tuple[int, int]:
    """Return lifetime (fails, oks) for symbol×structure on the rotation ledger."""
    if not symbol or not structure:
        return 0, 0
    sym_u = str(symbol).upper()
    st = str(structure)
    by = _load_rotation().get("by_hyp_id") or {}
    fails = 0
    oks = 0
    for row in by.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("symbol") or "").upper() != sym_u:
            continue
        if str(row.get("structure") or "") != st:
            continue
        if row.get("capital_path_ok"):
            oks += 1
        else:
            fails += 1
    return fails, oks


def _family_recent_fail_cooled(
    symbol: str | None,
    structure: str | None,
    *,
    window_hours: float = 6.0,
    min_fails: int = 2,
) -> bool:
    """Cool symbol×structure after repeated recent B3/B4 fails with zero capital_path_ok.

    Observed 2026-07-24 coach: NFLX CCS 32 fails / 0 ok in 6h while selector kept
    queueing score-twin clones (n=46 score=475.65 × many hyp_ids).

    Cool means *spray block*, not permanent quarantine: select_stress_hyps still
    allows one highest-score unstressed challenge per cooled family so evolve SHIP
    progress is not starved (2026-07-24T1500 coach: queue n=0 while XOM/PLTR/NFLX
    positive multi-leg SHIPs sat only on cooled families).

    Escalation (2026-07-24T2100 coach): when recent fails hit toxic_fail_min with 0 ok,
    or lifetime fails are hopeless (many fails, 0 ok ever), challenges are hard-blocked
    via `_family_challenge_toxic` — empty queue beats burning B3/B4 on PLTR/NFLX CCS.
    """
    if min_fails <= 0:
        return False
    fails, oks = _family_window_fail_ok(symbol, structure, window_hours=window_hours)
    return fails >= int(min_fails) and oks == 0


def _family_challenge_toxic(
    symbol: str | None,
    structure: str | None,
    *,
    window_hours: float = 6.0,
    toxic_fail_min: int = 8,
    lifetime_fail_min: int = 20,
    max_ok_rate: float = 0.05,
) -> bool:
    """Hard-block cooled-family challenge slots for hopeless families.

    Delegates to shared stress_family_policy so evolve apply and selector agree.
    2026-07-28 coach: also treat low residual ok-rate as toxic (NFLX CCS ~583f/4ok
    never tripped zero-ok toxic and burned every B3/B4 cycle).
    """
    if not symbol or not structure:
        return False
    try:
        sys.path.insert(0, str(_REPO))
        from trader_platform.stress_family_policy import (  # noqa: WPS433
            family_challenge_toxic,
            load_rotation,
        )

        return bool(
            family_challenge_toxic(
                symbol,
                structure,
                rotation=load_rotation(_ROTATION),
                window_hours=window_hours,
                toxic_fail_min=toxic_fail_min,
                lifetime_fail_min=lifetime_fail_min,
                max_ok_rate=max_ok_rate,
            )
        )
    except Exception:
        # Fallback mirrors shared policy (incl. low ok-rate) if import path fails.
        if toxic_fail_min > 0 and window_hours > 0:
            fails, oks = _family_window_fail_ok(
                symbol, structure, window_hours=window_hours
            )
            total = fails + oks
            if fails >= int(toxic_fail_min) and (
                oks <= 0 or (total > 0 and oks / total <= float(max_ok_rate))
            ):
                return True
        if lifetime_fail_min > 0:
            lf, lo = _family_lifetime_fail_ok(symbol, structure)
            total = lf + lo
            if lf >= int(lifetime_fail_min) and (
                lo <= 0 or (total > 0 and lo / total <= float(max_ok_rate))
            ):
                return True
        return False


def _hyp_ids_in_registry(ids: list[str]) -> set[str]:
    """Return subset of hyp ids present in living registry (ghost filter).

    2026-07-28 coach: evolve-log / thrash can queue hyp_ids deleted before B3/B4;
    pcs_* stress then fail-closed the *whole* batch (missing XOM 54c72849 for ~11 cycles).
    Fast path: substring scan of yaml bytes — avoid full HypothesisRegistry load when
    only presence matters.
    """
    if not ids or not _HYPS.is_file():
        return set()
    try:
        sz = _HYPS.stat().st_size
        if sz < 10_000:
            return set()
        blob = _HYPS.read_bytes()
    except Exception:
        return set()
    present: set[str] = set()
    for hid in ids:
        token = hid.encode("utf-8", errors="ignore")
        if not token:
            continue
        # Match common yaml shapes: "id: hyp_..." or bare id token
        if token in blob:
            present.add(hid)
    return present


def _family_capital_path_prior(symbol: str | None, structure: str | None) -> int:
    """Lifetime capital_path_ok count — prefer families that have proven at least once."""
    _fails, oks = _family_lifetime_fail_ok(symbol, structure)
    return int(oks)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _structure_of(h: Any) -> str | None:
    dna = getattr(h, "dna", None) or {}
    if isinstance(dna, dict) and dna.get("structure"):
        return str(dna["structure"])
    # id heuristic
    hid = str(getattr(h, "id", "") or "")
    for st in _ML:
        if st in hid:
            return st
    return None


def _symbol_of(h: Any) -> str | None:
    dna = getattr(h, "dna", None) or {}
    if isinstance(dna, dict):
        if dna.get("symbol"):
            return str(dna["symbol"]).upper()
        # StrategyDNA serializes primary under symbols: [SYM, ...]
        syms = dna.get("symbols") or []
        if isinstance(syms, (list, tuple)) and syms:
            return str(syms[0]).upper()
    instruments = list(getattr(h, "instruments", None) or [])
    if instruments:
        return str(instruments[0]).upper()
    hid = str(getattr(h, "id", "") or "")
    # hyp_dna_bac_put_credit_spread_...
    m = re.match(r"hyp_dna_([a-z0-9]+)_", hid)
    if m:
        return m.group(1).upper()
    return None


def _is_stressed(h: Any) -> bool:
    blob = " ".join(str(x) for x in (getattr(h, "evidence_links", None) or [])).lower()
    blob += " " + str(getattr(h, "notes", "") or "").lower()
    return any(m in blob for m in _STRESS_MARKERS)


def _parse_score_n(h: Any) -> tuple[float | None, int | None]:
    score = None
    n = None
    texts = list(getattr(h, "evidence_links", None) or []) + [str(getattr(h, "notes", "") or "")]
    for t in texts:
        if score is None:
            m = re.search(r"(?:score|ship_score|composite)=([-\d.]+)", str(t), re.I)
            if m:
                try:
                    score = float(m.group(1))
                except ValueError:
                    pass
        if n is None:
            m = re.search(r"(?:n_trades|trades|n)=(\d+)", str(t), re.I)
            if m:
                try:
                    n = int(m.group(1))
                except ValueError:
                    pass
    return score, n


def _shortlist_leaders(limit: int) -> list[dict[str, Any]]:
    if not _SHORTLIST.is_file():
        return []
    try:
        d = json.loads(_SHORTLIST.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in d.get("shortlist") or []:
        hid = row.get("hyp_id") or row.get("id")
        st = row.get("structure")
        if not hid or st not in _ML:
            continue
        if not row.get("stress_priority", True):
            continue
        out.append(
            {
                "hyp_id": str(hid),
                "source": "shortlist_leader",
                "structure": st,
                "symbol": row.get("symbol"),
                "score": row.get("full_pnl") or row.get("ship_score"),
            }
        )
        if len(out) >= limit:
            break
    return out


def _registry_unstressed(
    limit: int, exclude: set[str], *, min_fresh_trades: int = 0
) -> list[dict[str, Any]]:
    if not _HYPS.is_file():
        return []
    already = _rotation_stressed_ids()
    try:
        sz = _HYPS.stat().st_size
        if sz < 10_000:
            return []
        # local import — keep script usable when package path is odd
        sys.path.insert(0, str(_REPO))
        from trader_platform.hypothesis_registry import HypothesisRegistry

        reg = HypothesisRegistry(_HYPS)
        hyps = reg.list()
    except Exception:
        return []

    cands: list[dict[str, Any]] = []
    for h in hyps:
        hid = str(h.id)
        if hid in exclude or hid in already:
            continue
        if h.status in ("rejected", "retired"):
            continue
        st = _structure_of(h)
        if st not in _ML:
            continue
        if _is_stressed(h):
            continue
        score, n = _parse_score_n(h)
        # Prefer SHIP-tagged or positive score; still allow unscored fresh DNA.
        # Known non-positive composite is vanity SHIP (positive_sim + DD penalty) — do not B3/B4 burn.
        if score is not None and score <= 0:
            continue
        # Skip thin known n when configured (n=1 CCS twins waste stress slots).
        if min_fresh_trades > 0 and n is not None and n < min_fresh_trades:
            continue
        blob = " ".join(str(x) for x in (h.evidence_links or [])).upper() + " " + str(h.notes or "").upper()
        shipish = "SHIP" in blob or (score is not None and score > 0)
        if not shipish and score is None:
            # fresh evolve often leaves score only in evolve logs; keep candidate status DNA
            if h.status not in ("candidate", "testing", "paper"):
                continue
        cands.append(
            {
                "hyp_id": hid,
                "source": "registry_unstressed",
                "structure": st,
                "symbol": _symbol_of(h),
                "score": score if score is not None else -1e9,
                "n_trades": n or 0,
                "status": h.status,
                "shipish": shipish,
            }
        )

    # rank: shipish first, score desc, n desc, prefer testing/paper lightly
    status_boost = {"paper": 3, "testing": 2, "candidate": 1}

    def key(r: dict[str, Any]) -> tuple:
        return (
            1 if r.get("shipish") else 0,
            status_boost.get(str(r.get("status")), 0),
            float(r.get("score") or -1e9),
            int(r.get("n_trades") or 0),
        )

    cands.sort(key=key, reverse=True)

    # symbol diversity greedy
    picked: list[dict[str, Any]] = []
    per_sym: dict[str, int] = defaultdict(int)
    for r in cands:
        sym = str(r.get("symbol") or "?")
        if per_sym[sym] >= 2:
            continue
        picked.append(r)
        per_sym[sym] += 1
        if len(picked) >= limit:
            break
    return picked


def _evolve_log_fresh(
    limit: int, exclude: set[str], *, min_fresh_trades: int = 0
) -> list[dict[str, Any]]:
    """Map positive DR SHIP rows in recent evolve_dr logs to created hyp ids (best-effort)."""
    if not _EVOLVE_LOG_DIR.is_dir():
        return []
    already = _rotation_stressed_ids()
    logs = sorted(_EVOLVE_LOG_DIR.glob("evolve_dr_*.log"))[-12:]
    # Parse each log: SHIP lines + created ids (order-correlated best-effort)
    scored: list[tuple[float, int, str, str, str]] = []  # score,n,struct,sym,hid
    for log in logs:
        text = log.read_text(encoding="utf-8", errors="ignore")
        ships: list[tuple[float, int, str, str]] = []
        for m in re.finditer(
            r"^SHIP\s+([-\d.]+)\s+(\d+)\s+(put_credit_spread|call_credit_spread|iron_condor)/(\S+)",
            text,
            re.M,
        ):
            score = float(m.group(1))
            if score <= 0:
                continue
            n_tr = int(m.group(2))
            if min_fresh_trades > 0 and n_tr < min_fresh_trades:
                continue
            ships.append((score, n_tr, m.group(3), m.group(4).upper()))
        created: list[str] = []
        for m in re.finditer(r"^created:\s*(.+)$", text, re.M):
            for part in m.group(1).split(","):
                hid = part.strip()
                if hid.startswith("hyp_dna_"):
                    created.append(hid)
        # pair SHIP rows to created multi-leg ids by structure/symbol in id
        used: set[str] = set()
        for score, n, st, sym in ships:
            hit = None
            needle = f"_{st}_"
            sym_l = sym.lower()
            for hid in created:
                if hid in used or hid in exclude or hid in already:
                    continue
                if needle in hid and f"_{sym_l}_" in hid:
                    hit = hid
                    break
            if hit is None:
                # looser: symbol only + structure token
                for hid in created:
                    if hid in used or hid in exclude or hid in already:
                        continue
                    if f"hyp_dna_{sym_l}_" in hid and st.split("_")[0] in hid:
                        hit = hid
                        break
            if hit:
                used.add(hit)
                scored.append((score, n, st, sym, hit))

    # unique by hyp_id keep best score
    best: dict[str, dict[str, Any]] = {}
    for score, n, st, sym, hid in scored:
        prev = best.get(hid)
        if prev is None or score > float(prev["score"]):
            best[hid] = {
                "hyp_id": hid,
                "source": "evolve_log",
                "structure": st,
                "symbol": sym,
                "score": score,
                "n_trades": n,
            }
    rows = sorted(best.values(), key=lambda r: (-float(r["score"]), -int(r.get("n_trades") or 0)))
    # diversity
    picked: list[dict[str, Any]] = []
    per_sym: dict[str, int] = defaultdict(int)
    for r in rows:
        sym = str(r.get("symbol") or "?")
        if per_sym[sym] >= 2:
            continue
        picked.append(r)
        per_sym[sym] += 1
        if len(picked) >= limit:
            break
    return picked


def select_stress_hyps(
    *,
    limit: int = 6,
    n_leaders: int = 2,
    include_logs: bool = True,
    leader_ttl_hours: float = 48.0,
    min_fresh_trades: int = 6,
    family_fail_window_hours: float = 6.0,
    family_fail_min: int = 2,
    toxic_fail_min: int = 8,
    lifetime_fail_min: int = 20,
    max_ok_rate: float = 0.05,
) -> dict[str, Any]:
    leaders = _shortlist_leaders(n_leaders)
    ids: list[str] = []
    rows: list[dict[str, Any]] = []
    skipped_fresh_leaders: list[str] = []
    skipped_metric_twins: list[str] = []
    skipped_family_cooled: list[str] = []
    skipped_family_toxic: list[str] = []
    skipped_missing_hyps: list[str] = []
    challenged_cooled_families: list[str] = []
    for r in leaders:
        hid = r["hyp_id"]
        if _leader_freshly_capital_ok(hid, ttl_hours=leader_ttl_hours):
            skipped_fresh_leaders.append(hid)
            continue
        if hid not in ids:
            ids.append(hid)
            rows.append(r)
    exclude = set(ids) | set(skipped_fresh_leaders)
    need = max(0, limit - len(ids))

    # Prefer registry unstressed; supplement with evolve-log mapping
    fresh = (
        _registry_unstressed(need * 4, exclude, min_fresh_trades=min_fresh_trades)
        if need
        else []
    )
    if include_logs and len(fresh) < need * 2:
        for r in _evolve_log_fresh(
            need * 4, exclude | {x["hyp_id"] for x in fresh}, min_fresh_trades=min_fresh_trades
        ):
            if r["hyp_id"] not in {x["hyp_id"] for x in fresh}:
                fresh.append(r)

    # re-rank combined fresh: prior capital_path families before raw vanity score
    def fkey(r: dict[str, Any]) -> tuple:
        sc = r.get("score")
        try:
            sc_f = float(sc) if sc is not None else -1e9
        except (TypeError, ValueError):
            sc_f = -1e9
        try:
            n_i = int(r.get("n_trades") or 0)
        except (TypeError, ValueError):
            n_i = 0
        prior = _family_capital_path_prior(r.get("symbol"), r.get("structure"))
        # prior>0 beats prior==0; then score/n
        return (1 if prior > 0 else 0, sc_f, n_i)

    fresh.sort(key=fkey, reverse=True)

    # Collapse evolve-score twins (same symbol/structure/score/n, different hyp_id)
    deduped: list[dict[str, Any]] = []
    seen_metric: set[tuple[Any, ...]] = set()
    for r in fresh:
        key = _metric_twin_key(r)
        # Only collapse when score+n known (avoid collapsing unscored unknowns)
        if key[2] is not None and key[3] > 0:
            if key in seen_metric:
                skipped_metric_twins.append(str(r.get("hyp_id")))
                continue
            seen_metric.add(key)
        deduped.append(r)
    fresh = deduped

    per_sym: dict[str, int] = defaultdict(int)
    per_family: dict[tuple[str, str], int] = defaultdict(int)
    cooled_challenge_used: set[tuple[str, str]] = set()
    # count leaders toward diversity soft-cap
    for r in rows:
        per_sym[str(r.get("symbol") or "?")] += 1
        per_family[(str(r.get("symbol") or "?").upper(), str(r.get("structure") or ""))] += 1

    def _try_add(
        r: dict[str, Any],
        *,
        max_per_sym: int,
        max_per_family: int,
        allow_cooled_challenge: bool,
    ) -> bool:
        if len(ids) >= limit:
            return False
        hid = r["hyp_id"]
        if hid in exclude:
            return False
        sym = str(r.get("symbol") or "?")
        st = str(r.get("structure") or "")
        fam = (sym.upper(), st)
        toxic = _family_challenge_toxic(
            sym,
            st,
            window_hours=family_fail_window_hours,
            toxic_fail_min=toxic_fail_min,
            lifetime_fail_min=lifetime_fail_min,
            max_ok_rate=max_ok_rate,
        )
        cooled = _family_recent_fail_cooled(
            sym,
            st,
            window_hours=family_fail_window_hours,
            min_fails=family_fail_min,
        )
        if toxic:
            skipped_family_toxic.append(hid)
            exclude.add(hid)
            return False
        if cooled:
            if not allow_cooled_challenge:
                return False
            # One challenge per cooled family — else spray-block.
            if fam in cooled_challenge_used:
                skipped_family_cooled.append(hid)
                exclude.add(hid)
                return False
        if per_sym[sym] >= max_per_sym:
            return False
        if st and per_family[fam] >= max_per_family:
            return False
        if cooled:
            cooled_challenge_used.add(fam)
            challenged_cooled_families.append(f"{fam[0]}:{fam[1]}:{hid}")
            r = {**r, "cooled_family_challenge": True}
        ids.append(hid)
        rows.append(r)
        exclude.add(hid)
        per_sym[sym] += 1
        per_family[fam] += 1
        return True

    # Pass 1–2: non-cooled / non-toxic first (breadth, then second slot).
    # High-score toxic cooled DNA must not crowd out lower-score proven families.
    for r in fresh:
        if len(ids) >= limit:
            break
        _try_add(r, max_per_sym=1, max_per_family=1, allow_cooled_challenge=False)
    for r in fresh:
        if len(ids) >= limit:
            break
        _try_add(r, max_per_sym=2, max_per_family=2, allow_cooled_challenge=False)

    # Pass 3–4: only then one challenge per non-toxic cooled family.
    for r in fresh:
        if len(ids) >= limit:
            break
        _try_add(r, max_per_sym=1, max_per_family=1, allow_cooled_challenge=True)
    for r in fresh:
        if len(ids) >= limit:
            break
        _try_add(r, max_per_sym=2, max_per_family=2, allow_cooled_challenge=True)

    # Drop ghost hyp_ids (deleted between evolve-log map and stress) so B3/B4
    # does not fail-closed the whole batch.
    if ids:
        present = _hyp_ids_in_registry(ids)
        if present:
            kept_ids: list[str] = []
            kept_rows: list[dict[str, Any]] = []
            for r in rows:
                hid = str(r.get("hyp_id") or "")
                if hid in present:
                    kept_ids.append(hid)
                    kept_rows.append(r)
                else:
                    skipped_missing_hyps.append(hid)
            ids, rows = kept_ids, kept_rows

    return {
        "generated_at": _now(),
        "hyp_ids": ids,
        "csv": ",".join(ids),
        "n": len(ids),
        "rows": rows,
        "skipped_fresh_leaders": skipped_fresh_leaders,
        "skipped_metric_twins": skipped_metric_twins[:40],
        "skipped_family_cooled": sorted(set(skipped_family_cooled))[:40],
        "skipped_family_toxic": sorted(set(skipped_family_toxic))[:40],
        "skipped_missing_hyps": sorted(set(skipped_missing_hyps))[:40],
        "challenged_cooled_families": challenged_cooled_families[:40],
        "policy": {
            "limit": limit,
            "n_leaders": n_leaders,
            "include_logs": include_logs,
            "leader_ttl_hours": leader_ttl_hours,
            "min_fresh_trades": min_fresh_trades,
            "family_fail_window_hours": family_fail_window_hours,
            "family_fail_min": family_fail_min,
            "toxic_fail_min": toxic_fail_min,
            "lifetime_fail_min": lifetime_fail_min,
            "max_ok_rate": max_ok_rate,
            "cooled_family_challenge_slots": 1,
            "note": (
                "mix shortlist leaders (skip fresh capital_path_ok within TTL) + "
                "unstressed multi-leg SHIPs score>0 / n>=min_fresh when known; "
                "prefer families with prior capital_path_ok; fill non-cooled first; "
                "dedupe evolve metric twins; cool symbol×structure after recent fail streak "
                "with 1 challenge/family unless toxic (fails>=floor with ok-rate<=max_ok_rate, "
                "incl. zero-ok); drop ghost hyp_ids missing from registry; "
                "empty queue beats toxic B3/B4 burn; no densify bag"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--n-leaders", type=int, default=2)
    ap.add_argument(
        "--leader-ttl-hours",
        type=float,
        default=48.0,
        help="Skip shortlist leaders already capital_path_ok within this many hours (0=always include).",
    )
    ap.add_argument(
        "--min-fresh-trades",
        type=int,
        default=6,
        help="When n_trades known on unstressed DNA, require at least this many (0=off).",
    )
    ap.add_argument(
        "--family-fail-window-hours",
        type=float,
        default=6.0,
        help="Cool symbol×structure after repeated fails with zero capital_path_ok in this window (0=off).",
    )
    ap.add_argument(
        "--family-fail-min",
        type=int,
        default=2,
        help="Min recent fails (with 0 ok) to cool a symbol×structure family.",
    )
    ap.add_argument(
        "--toxic-fail-min",
        type=int,
        default=8,
        help="Recent fails (0 ok) that hard-block cooled-family challenges (0=off).",
    )
    ap.add_argument(
        "--lifetime-fail-min",
        type=int,
        default=20,
        help="Lifetime fails meeting floor with ok-rate<=max-ok-rate → hard-block (0=off).",
    )
    ap.add_argument(
        "--max-ok-rate",
        type=float,
        default=0.05,
        help="Max capital_path_ok rate still treated as toxic once fail floors met (default 0.05).",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-logs", action="store_true")
    ap.add_argument(
        "--write-latest",
        action="store_true",
        default=True,
        help="Write .cache/platform/quality_residual/stress_selection_LATEST.json (default on).",
    )
    ap.add_argument(
        "--no-write-latest",
        action="store_true",
        help="Skip writing stress_selection_LATEST.json.",
    )
    args = ap.parse_args(argv)
    res = select_stress_hyps(
        limit=int(args.limit),
        n_leaders=int(args.n_leaders),
        include_logs=not args.no_logs,
        leader_ttl_hours=float(args.leader_ttl_hours),
        min_fresh_trades=int(args.min_fresh_trades),
        family_fail_window_hours=float(args.family_fail_window_hours),
        family_fail_min=int(args.family_fail_min),
        toxic_fail_min=int(args.toxic_fail_min),
        lifetime_fail_min=int(args.lifetime_fail_min),
        max_ok_rate=float(args.max_ok_rate),
    )
    if args.write_latest and not args.no_write_latest:
        out_dir = _REPO / ".cache" / "platform" / "quality_residual"
        out_dir.mkdir(parents=True, exist_ok=True)
        latest = out_dir / "stress_selection_LATEST.json"
        latest.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(res["csv"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

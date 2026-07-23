#!/usr/bin/env python3
"""Select multi-leg hyps for B3/B4 quality-cycle stress.

Problem this fixes:
  QUALITY_SHORTLIST stress_priority leaders alone were re-stressed every cycle
  (identical regime/cost artifacts) while evolve minted dozens of unstressed SHIPs.

Policy:
  - Keep up to `n_leaders` shortlist stress_priority multi-leg leaders (regression).
  - Fill remaining slots with unstressed multi-leg SHIP-ish hyps from the registry
    (or evolve_dr logs as fallback), preferring higher evolve scores / trade counts
    and symbol diversity.
  - Never include CSP/wheel single-leg here (pcs_* stress scripts are multi-leg).

Prints comma-separated hyp ids on stdout. JSON summary with --json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SHORTLIST = _REPO / "reports" / "bootstrap" / "QUALITY_SHORTLIST.json"
_HYPS = _REPO / "trader_platform" / "data" / "hypotheses.yaml"
_EVOLVE_LOG_DIR = _REPO / ".cache" / "platform" / "quality_residual"
_ROTATION = _REPO / "reports" / "bootstrap" / "STRESS_ROTATION.json"
_ML = frozenset({"put_credit_spread", "call_credit_spread", "iron_condor"})
_STRESS_MARKERS = (
    "regime_stress",
    "cost_stress",
    "pcs_regime",
    "pcs_cost",
    "b3:",
    "b4:",
    "stress_regime",
    "stress_cost",
    "regime_",
    "cost_",
    "dense_neg",
    "b3_hold",
    "b4_cost",
)


def _rotation_stressed_ids() -> set[str]:
    """Hyp ids already B3/B4'd via rotation ledger (avoids hyp yaml write races)."""
    if not _ROTATION.is_file():
        return set()
    try:
        d = json.loads(_ROTATION.read_text(encoding="utf-8"))
    except Exception:
        return set()
    by = d.get("by_hyp_id") or {}
    return {str(k) for k in by.keys()}


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
    if isinstance(dna, dict) and dna.get("symbol"):
        return str(dna["symbol"]).upper()
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


def _registry_unstressed(limit: int, exclude: set[str]) -> list[dict[str, Any]]:
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


def _evolve_log_fresh(limit: int, exclude: set[str]) -> list[dict[str, Any]]:
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
            ships.append((score, int(m.group(2)), m.group(3), m.group(4).upper()))
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
) -> dict[str, Any]:
    leaders = _shortlist_leaders(n_leaders)
    ids: list[str] = []
    rows: list[dict[str, Any]] = []
    for r in leaders:
        hid = r["hyp_id"]
        if hid not in ids:
            ids.append(hid)
            rows.append(r)
    exclude = set(ids)
    need = max(0, limit - len(ids))

    # Prefer registry unstressed; supplement with evolve-log mapping
    fresh = _registry_unstressed(need * 3, exclude) if need else []
    if include_logs and len(fresh) < need:
        for r in _evolve_log_fresh(need * 3, exclude | {x["hyp_id"] for x in fresh}):
            if r["hyp_id"] not in {x["hyp_id"] for x in fresh}:
                fresh.append(r)

    # re-rank combined fresh
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
        return (sc_f, n_i)

    fresh.sort(key=fkey, reverse=True)
    per_sym: dict[str, int] = defaultdict(int)
    # count leaders toward diversity soft-cap
    for r in rows:
        per_sym[str(r.get("symbol") or "?")] += 1

    # Pass 1: max 1 fresh hyp per symbol (breadth over vanity twins)
    for r in fresh:
        if len(ids) >= limit:
            break
        hid = r["hyp_id"]
        if hid in exclude:
            continue
        sym = str(r.get("symbol") or "?")
        if per_sym[sym] >= 1:
            continue
        ids.append(hid)
        rows.append(r)
        exclude.add(hid)
        per_sym[sym] += 1

    # Pass 2: allow a second per symbol only if still under limit
    for r in fresh:
        if len(ids) >= limit:
            break
        hid = r["hyp_id"]
        if hid in exclude:
            continue
        sym = str(r.get("symbol") or "?")
        if per_sym[sym] >= 2:
            continue
        ids.append(hid)
        rows.append(r)
        exclude.add(hid)
        per_sym[sym] += 1

    return {
        "generated_at": _now(),
        "hyp_ids": ids,
        "csv": ",".join(ids),
        "n": len(ids),
        "rows": rows,
        "policy": {
            "limit": limit,
            "n_leaders": n_leaders,
            "include_logs": include_logs,
            "note": "mix shortlist leaders + unstressed multi-leg SHIPs (score>0 when known); no densify bag",
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--n-leaders", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-logs", action="store_true")
    args = ap.parse_args(argv)
    res = select_stress_hyps(
        limit=int(args.limit),
        n_leaders=int(args.n_leaders),
        include_logs=not args.no_logs,
    )
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(res["csv"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Append B3/B4 outcomes into the stress-rotation ledger + refresh QUALITY_SHORTLIST.

Used by continuum coach and (optionally) quality residual after stress.
Never touches live/arm. Does not rewrite hypotheses.yaml (worker owns that).

Capital-path policy (risk profile, not vanity full-history SHIP $):
  - B3 regime_hold required
  - B4 cost_hold not false
  - Soft NULL@5% with missing/≤0 slip PnL is NOT capital-path (edge vanished)
  - Soft-loss at 5% (slip5_pnl < 0 even if cost_hold/NEEDS_MORE_DATA) is NOT capital-path
  - Full-history non-positive PnL is NOT capital-path
  - Extreme dense-neg + high window DD rejected vs leader bar
  - Rank: dense_neg → slip verdict quality (SHIP < NEEDS < NULL) → max_dd → slip5 pnl → full pnl
    (verdict before DD so NULL@slightly-tighter-DD cannot outrank SHIP@5%)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_LEDGER = _REPO / "reports" / "bootstrap" / "STRESS_ROTATION.json"
_SHORTLIST = _REPO / "reports" / "bootstrap" / "QUALITY_SHORTLIST.json"

# Soft NULL with edge essentially gone (survives_5pct_slip + pnl~0 trap).
_SLIP_EDGE_EPS = 0.01


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _f(x: Any, default: float | None = None) -> float | None:
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def capital_path_decision(
    *,
    b3: bool,
    b4: bool | None,
    slip5_v: Any,
    slip5_pnl: Any,
    dense_neg: Any,
    max_dd: Any,
    full_pnl: Any,
) -> tuple[bool, str | None]:
    """Return (capital_path_ok, reject_reason). Pure; safe to re-run on ledger rows."""
    slip5_pnl_f = _f(slip5_pnl)
    full_pnl_f = _f(full_pnl)
    dense = int(dense_neg or 0)
    dd = _f(max_dd, 0.0) or 0.0
    slip_v = str(slip5_v or "").upper() or None

    if not b3:
        return False, f"B3 hold=false dense_neg={dense_neg} dd={max_dd}"
    if b4 is False:
        return False, f"B4 cost_hold=false slip5={slip5_v} pnl={slip5_pnl}"
    if full_pnl_f is not None and full_pnl_f <= 0:
        return False, f"full_history non-positive pnl={full_pnl_f}"
    # Soft cost_hold can still be soft_loss / vanished edge under 5% slip.
    # Negative slip PnL is never capital-path (soft_loss_at_5pct / fragile edge).
    if slip5_pnl_f is not None and slip5_pnl_f < 0:
        return (
            False,
            f"B4 slip5 soft_loss/neg pnl={slip5_pnl} v={slip5_v} (not capital-path)",
        )
    if slip_v == "NULL":
        if slip5_pnl_f is None or slip5_pnl_f <= _SLIP_EDGE_EPS:
            return (
                False,
                f"B4 slip5 NULL/~0 pnl={slip5_pnl} (soft cost only; edge vanished)",
            )
    if dense >= 4 and dd > 200:
        return (
            False,
            f"risk profile worse than leader bar: dense_neg={dense_neg} dd={max_dd}",
        )
    if b4 is False:  # pragma: no cover - already handled
        return False, "B4 cost_hold=false"
    return True, None


def apply_capital_path_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Mutate entry with reject_reason + capital_path_ok from stored metrics."""
    ok, reason = capital_path_decision(
        b3=bool(entry.get("b3_hold")),
        b4=entry.get("b4_cost_hold") if entry.get("b4_cost_hold") is not None else None,
        slip5_v=entry.get("b4_slip5_verdict"),
        slip5_pnl=entry.get("b4_slip5_pnl"),
        dense_neg=entry.get("dense_neg_ge3"),
        max_dd=entry.get("max_dd"),
        full_pnl=entry.get("full_pnl"),
    )
    entry["reject_reason"] = reason
    entry["capital_path_ok"] = bool(ok and reason is None)
    return entry


def _slip_verdict_rank(v: Any) -> int:
    """Lower is better for shortlist rank."""
    s = str(v or "").upper()
    if s == "SHIP":
        return 0
    if s == "NEEDS_MORE_DATA":
        return 1
    if s == "NULL":
        return 2
    if s in ("REJECT", "FAIL"):
        return 4
    return 3


def ingest_pair(regime_path: Path, cost_path: Path, *, source: str = "coach") -> dict[str, Any]:
    reg = json.loads(regime_path.read_text(encoding="utf-8"))
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    cost_by = {r.get("hyp_id"): r for r in (cost.get("results") or [])}
    # also summaries list shape
    if not cost_by and cost.get("summaries"):
        for s in cost["summaries"]:
            hid = s.get("hyp") or s.get("hyp_id")
            if hid:
                cost_by[hid] = {"hyp_id": hid, "summary": s}

    ledger = _load_json(_LEDGER)
    by_id: dict[str, Any] = dict(ledger.get("by_hyp_id") or {})
    stamp = Path(regime_path).stem

    rows_out: list[dict[str, Any]] = []
    for r in reg.get("results") or []:
        hid = r.get("hyp_id")
        if not hid:
            continue
        s = r.get("summary") or {}
        fh = r.get("full_history") or {}
        c = cost_by.get(hid) or {}
        cs = c.get("summary") or {}
        if not cs and c:
            # flatten
            cs = {
                "baseline_verdict": c.get("baseline_verdict"),
                "baseline_pnl": c.get("baseline_pnl"),
                "slip_5_verdict": c.get("slip_5_verdict"),
                "slip_5_pnl": c.get("slip_5_pnl"),
                "cost_hold": c.get("cost_hold"),
                "note": c.get("note"),
            }
            # try by_slip
            if cs.get("cost_hold") is None:
                for slip_row in c.get("by_slip") or []:
                    if abs(float(slip_row.get("slippage_pct") or -1) - 0.05) < 1e-9:
                        cs["slip_5_verdict"] = slip_row.get("verdict")
                        cs["slip_5_pnl"] = slip_row.get("pnl")
                        cs["slip_5_dd"] = slip_row.get("dd")
                        cs["slip_5_n"] = slip_row.get("n_trades")
                # cost_hold from preferred summary in parent
        # recover cost_hold from sibling summaries if needed
        if cs.get("cost_hold") is None:
            for srow in cost.get("summaries") or []:
                if (srow.get("hyp") or srow.get("hyp_id")) == hid:
                    cs = {**cs, **srow}
                    break

        b3 = bool(s.get("regime_hold"))
        b4 = bool(cs.get("cost_hold")) if cs.get("cost_hold") is not None else None
        slip5_v = cs.get("slip_5_verdict")
        slip5_pnl = cs.get("slip_5_pnl")

        entry = {
            "hyp_id": hid,
            "symbol": r.get("symbol"),
            "structure": r.get("structure"),
            "stressed_at": _now(),
            "source": source,
            "regime_path": str(regime_path),
            "cost_path": str(cost_path),
            "b3_hold": b3,
            "dense_neg_ge3": s.get("n_negative_n_ge_3"),
            "max_dd": s.get("max_dd_across_windows"),
            "worst_window_pnl": s.get("worst_window_pnl"),
            "full_pnl": fh.get("pnl"),
            "full_n": fh.get("n_trades"),
            "full_verdict": fh.get("verdict"),
            "max_loss_usd": fh.get("max_loss_usd"),
            "b4_cost_hold": b4,
            "b4_slip5_verdict": slip5_v,
            "b4_slip5_pnl": slip5_pnl,
            "b4_note": cs.get("note"),
        }
        apply_capital_path_fields(entry)
        by_id[hid] = entry
        rows_out.append(entry)

    ledger = {
        "generated_at": _now(),
        "schema_version": 1,
        "note": "Rotation ledger for quality-cycle B3/B4 — prevents re-stress thrash; not TOP_HYP.",
        "last_ingest": {
            "source": source,
            "stamp": stamp,
            "regime_path": str(regime_path),
            "cost_path": str(cost_path),
            "n": len(rows_out),
        },
        "by_hyp_id": by_id,
    }
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ledger_path": str(_LEDGER), "rows": rows_out, "n_ledger": len(by_id)}


def rescore_ledger(*, source: str = "coach_rescore") -> dict[str, Any]:
    """Re-apply capital-path policy to every ledger row (no new B3/B4 sims)."""
    ledger = _load_json(_LEDGER)
    by_id: dict[str, Any] = dict(ledger.get("by_hyp_id") or {})
    n_flipped_off = 0
    n_flipped_on = 0
    for hid, entry in list(by_id.items()):
        if not isinstance(entry, dict):
            continue
        prev_ok = bool(entry.get("capital_path_ok"))
        apply_capital_path_fields(entry)
        entry["rescored_at"] = _now()
        entry["rescore_source"] = source
        by_id[hid] = entry
        now_ok = bool(entry.get("capital_path_ok"))
        if prev_ok and not now_ok:
            n_flipped_off += 1
        elif not prev_ok and now_ok:
            n_flipped_on += 1

    n_ok = sum(1 for e in by_id.values() if isinstance(e, dict) and e.get("capital_path_ok"))
    ledger = {
        "generated_at": _now(),
        "schema_version": 1,
        "note": "Rotation ledger for quality-cycle B3/B4 — prevents re-stress thrash; not TOP_HYP.",
        "last_rescore": {
            "source": source,
            "n": len(by_id),
            "n_capital_path_ok": n_ok,
            "n_flipped_off": n_flipped_off,
            "n_flipped_on": n_flipped_on,
        },
        "last_ingest": ledger.get("last_ingest"),
        "by_hyp_id": by_id,
    }
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ledger_path": str(_LEDGER),
        "n_ledger": len(by_id),
        "n_capital_path_ok": n_ok,
        "n_flipped_off": n_flipped_off,
        "n_flipped_on": n_flipped_on,
    }


def refresh_shortlist_from_ledger() -> dict[str, Any]:
    ledger = _load_json(_LEDGER)
    by_id = dict(ledger.get("by_hyp_id") or {})
    # Ensure current policy is applied even if ledger rows predate gate tightening.
    for hid, e in list(by_id.items()):
        if isinstance(e, dict):
            apply_capital_path_fields(e)
            by_id[hid] = e
    prev = _load_json(_SHORTLIST)

    # Rank capital-path-ok multi-leg by risk profile (not vanity SHIP $).
    # Verdict quality before DD: SHIP@5% must beat NULL@slightly-tighter-DD.
    # IMPORTANT: dense_neg=0 / max_dd=0 / slip=0 are valid bests — never use `x or default`
    # (Python treats 0 as falsy; dens=0 was ranked as 99 until 2026-07-23 coach).
    def rank_key(e: dict[str, Any]) -> tuple:
        dense_raw = e.get("dense_neg_ge3")
        dense = int(dense_raw) if dense_raw is not None else 99
        dd_raw = e.get("max_dd")
        dd = float(dd_raw) if dd_raw is not None else 1e9
        slip_raw = e.get("b4_slip5_pnl")
        slip = float(slip_raw) if slip_raw is not None else -1e9
        pnl_raw = e.get("full_pnl")
        pnl = float(pnl_raw) if pnl_raw is not None else -1e9
        vrank = _slip_verdict_rank(e.get("b4_slip5_verdict"))
        return (-int(bool(e.get("capital_path_ok"))), dense, vrank, dd, -slip, -pnl)

    multi = [
        e
        for e in by_id.values()
        if isinstance(e, dict)
        and e.get("structure") in ("put_credit_spread", "call_credit_spread", "iron_condor")
    ]
    multi_sorted = sorted(multi, key=rank_key)

    shortlist: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = list(prev.get("rejected_tonight") or [])
    seen_reject = {r.get("hyp_id") for r in rejected}

    # Keep MCP-native rows from previous shortlist (CSP/wheel) — not restressed here
    mcp_prev = [
        r
        for r in (prev.get("shortlist") or [])
        if r.get("lane") == "mcp_native_live_candidate_path"
        or r.get("structure")
        in ("cash_secured_put", "wheel_assignment", "short_put_credit")
    ]

    for i, e in enumerate(multi_sorted):
        hid = e["hyp_id"]
        if e.get("reject_reason") or not e.get("capital_path_ok"):
            if hid not in seen_reject:
                rejected.append(
                    {"hyp_id": hid, "reason": e.get("reject_reason") or "failed quality bar"}
                )
                seen_reject.add(hid)
            continue
        # stress_priority: top 2 capital-path ok
        shortlist.append(
            {
                "hyp_id": hid,
                "structure": e.get("structure"),
                "symbol": e.get("symbol"),
                "status": "testing" if i < 2 else "candidate",
                "lane": "paper_research",
                "stress_priority": i < 2,
                "b3_hold": e.get("b3_hold"),
                "dense_neg_ge3": e.get("dense_neg_ge3"),
                "full_pnl": e.get("full_pnl"),
                "max_dd": e.get("max_dd"),
                "max_loss_usd_approx": e.get("max_loss_usd"),
                "b4_cost_hold": e.get("b4_cost_hold"),
                "b4_note": (
                    f"{e.get('b4_slip5_verdict')}@5pct pnl~{e.get('b4_slip5_pnl')} "
                    f"{e.get('b4_note') or ''}"
                ).strip(),
                "why": (
                    "Best risk profile among rotated B3/B4"
                    if i == 0
                    else "Rotated stress survivor; secondary to tighter-DD leader"
                ),
                "caveat": (
                    "Proxy BS + B3/B4 only. Multi-leg not MCP placeable. "
                    "Not pack multi-symbol quality_pass."
                ),
                "stress_source": e.get("source"),
                "stressed_at": e.get("stressed_at"),
            }
        )
        if len(shortlist) >= 6:
            break

    # Append MCP toys (capped)
    for r in mcp_prev[:3]:
        if not any(x.get("hyp_id") == r.get("hyp_id") for x in shortlist):
            shortlist.append(r)

    out = {
        "generated_at": _now(),
        "phase": "BUILD_PAPER_SEARCH",
        "authority": "research_paper_only",
        "honesty": (
            "Proxy BS sims + B3/B4 only. Not TOP_HYP. Multi-leg not MCP-live. "
            "Stress rotation ledger drives shortlist; quality_cycle mixes leaders+fresh. "
            "Capital-path rejects: soft NULL@~0, soft-loss/neg@5%, non-pos full PnL. "
            "Rank dens → slip verdict (SHIP>NEEDS>NULL) → dd → slip pnl."
        ),
        "agentic": prev.get("agentic")
        or {
            "cash_usd": 500,
            "option_level": 2,
            "type": "cash",
            "mcp_place": "single_leg_only",
        },
        "shortlist": shortlist,
        "rejected_tonight": rejected[-40:],
        "densify_pack": prev.get("densify_pack")
        or {"quality_pass": False, "note": "plumbing only"},
        "stress_rotation_ledger": str(_LEDGER),
        "capital_note_500": prev.get("capital_note_500")
        or "CSP ATM rarely fits $500 cash; $3k at LIVE_PACKET.",
        "next": [
            "Manage open paper campaign (BAC/PLTR) through multi-session B6",
            "Quality cycles rotate unstressed multi-leg SHIPs into B3/B4",
            "Shortlist prefers SHIP@5% over NULL@positive; reject soft-loss@5%",
            "Do not arm multi-leg; MCP lane remains CSP sized to cash",
            "No densify bag thrash",
        ],
    }
    _SHORTLIST.write_text(json.dumps(out, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return {
        "shortlist_path": str(_SHORTLIST),
        "n_shortlist": len(shortlist),
        "n_rejected": len(rejected),
        "top_ids": [r.get("hyp_id") for r in shortlist[:6]],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regime", type=Path, default=None)
    ap.add_argument("--cost", type=Path, default=None)
    ap.add_argument("--source", default="coach")
    ap.add_argument(
        "--rescore-only",
        action="store_true",
        help="Re-apply capital-path policy to existing ledger rows (no new stress).",
    )
    ap.add_argument("--refresh-shortlist", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    res: dict[str, Any] = {}
    if args.rescore_only:
        res = rescore_ledger(source=args.source or "coach_rescore")
    else:
        if not args.regime or not args.cost:
            ap.error("--regime and --cost are required unless --rescore-only")
        res = ingest_pair(args.regime, args.cost, source=args.source)

    if args.refresh_shortlist:
        # Persist any in-memory rescoring done during refresh when ledger path used.
        if args.rescore_only:
            # already wrote ledger; refresh re-applies policy again (idempotent)
            res["shortlist"] = refresh_shortlist_from_ledger()
        else:
            res["shortlist"] = refresh_shortlist_from_ledger()

    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        if args.rescore_only:
            print(
                f"rescore n={res.get('n_ledger')} ok={res.get('n_capital_path_ok')} "
                f"flipped_off={res.get('n_flipped_off')} wrote {res.get('ledger_path')}"
            )
        else:
            print(f"ledger n={res['n_ledger']} wrote {res['ledger_path']}")
        if "shortlist" in res:
            sl = res["shortlist"]
            print(f"shortlist n={sl.get('n_shortlist')} top={sl.get('top_ids')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

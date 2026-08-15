#!/usr/bin/env python3
"""Multi-symbol honesty for QUALITY_SHORTLIST / capital_path_ok multi-leg DNA.

Densify MULTI_SYMBOL_REPROVE only re-proves bootstrap densify seeds (AMZN/IWM).
Research leaders (AAL/BAC PCS) never got peer-symbol honesty, so quality_pass
stayed 0 forever while EDGE had real B3/B4 survivors.

This script takes top capital_path_ok multi-leg DNA configs from STRESS_ROTATION
(+ shortlist order), runs the *same knobs* via pcs_sim on peer symbols, and
writes reports/bootstrap/SHORTLIST_DNA_MULTI.json.

Pack signal: quality_pass when ≥1 DNA has ≥min_peer_pass peer symbols with
positive after-cost proxy PnL and min trades (not live edge; L0 proxy).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_ROTATION = _REPO / "reports" / "bootstrap" / "STRESS_ROTATION.json"
_SHORTLIST = _REPO / "reports" / "bootstrap" / "QUALITY_SHORTLIST.json"
_HYPS = _REPO / "trader_platform" / "data" / "hypotheses.yaml"
_OUT = _REPO / "reports" / "bootstrap" / "SHORTLIST_DNA_MULTI.json"
_ML = frozenset({"put_credit_spread", "call_credit_spread", "iron_condor"})
_DEFAULT_PEERS = ["AAL", "BAC", "F", "CCL", "TSLL", "XOM", "SNAP", "KO", "IWM"]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def _rank_ok(row: dict[str, Any]) -> tuple[Any, ...]:
    dens = row.get("dense_neg_ge3")
    dens_i = 99 if dens is None else int(dens)
    bucket = 0 if dens_i <= 1 else dens_i
    verd = str(row.get("b4_slip5_verdict") or "")
    vord = 0 if verd == "SHIP" else 1
    dd = row.get("max_dd")
    dd_f = 9999.0 if dd is None else float(dd)
    slip = row.get("b4_slip5_pnl")
    slip_f = -9999.0 if slip is None else float(slip)
    pnl = row.get("full_pnl")
    pnl_f = -9999.0 if pnl is None else float(pnl)
    return (bucket, vord, dd_f, -slip_f, -pnl_f)


def _config_fp(cfg: dict[str, Any], structure: str) -> str:
    keys = (
        "long_dte",
        "long_target_delta",
        "spread_width",
        "min_credit_pct",
        "profit_target",
        "defined_loss_exit_frac",
        "dte_stop",
        "delta_breach",
        "iv_rank_min",
        "bear_dte",
        "max_loss_budget_usd",
    )
    parts = [structure]
    for k in keys:
        if k in cfg and cfg[k] is not None:
            parts.append(f"{k}={cfg[k]}")
    return "|".join(parts)


def _shortlist_rows(shortlist_path: Path | None = None) -> dict[str, dict[str, Any]]:
    sl = _load_json(shortlist_path or _SHORTLIST)
    out: dict[str, dict[str, Any]] = {}
    for row in sl.get("shortlist") or []:
        hid = str(row.get("hyp_id") or "")
        if hid and isinstance(row, dict):
            out[hid] = row
    return out


def select_pinned_hyps(
    hyp_ids: list[str],
    *,
    rotation_path: Path | None = None,
    shortlist_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Pin existing living catalog ids. Does not invent DNA."""
    rot = _load_json(rotation_path or _ROTATION)
    by = rot.get("by_hyp_id") or {}
    sl_rows = _shortlist_rows(shortlist_path)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in hyp_ids:
        hid = str(raw or "").strip()
        if not hid or hid in seen:
            continue
        seen.add(hid)
        row: dict[str, Any] = {}
        if isinstance(by.get(hid), dict):
            row.update(by[hid])
        if isinstance(sl_rows.get(hid), dict):
            for k, v in sl_rows[hid].items():
                if row.get(k) in (None, ""):
                    row[k] = v
        row["hyp_id"] = hid
        out.append(row)
    return out


def select_leader_hyps(
    *,
    top_n: int = 3,
    rotation_path: Path | None = None,
    shortlist_path: Path | None = None,
    hyp_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if hyp_ids:
        return select_pinned_hyps(
            hyp_ids,
            rotation_path=rotation_path,
            shortlist_path=shortlist_path,
        )
    rot = _load_json(rotation_path or _ROTATION)
    by = rot.get("by_hyp_id") or {}
    ok = [
        dict(v, hyp_id=k)
        for k, v in by.items()
        if isinstance(v, dict)
        and v.get("capital_path_ok")
        and str(v.get("structure") or "").lower() in _ML
    ]
    ok.sort(key=_rank_ok)
    # Prefer shortlist order tie-break: boost shortlist ids
    sl = _load_json(shortlist_path or _SHORTLIST)
    sl_ids = [
        str(r.get("hyp_id"))
        for r in (sl.get("shortlist") or [])
        if r.get("hyp_id")
    ]
    sl_rank = {hid: i for i, hid in enumerate(sl_ids)}

    def key2(row: dict[str, Any]) -> tuple[Any, ...]:
        hid = str(row.get("hyp_id") or "")
        return (_rank_ok(row), sl_rank.get(hid, 999))

    ok.sort(key=key2)
    # Dedupe by origin symbol×structure keeping best ranked
    seen_fam: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in ok:
        fam = (
            str(row.get("symbol") or "").upper(),
            str(row.get("structure") or "").lower(),
        )
        if not fam[0] or not fam[1] or fam in seen_fam:
            continue
        seen_fam.add(fam)
        out.append(row)
        if len(out) >= top_n:
            break
    return out


def load_hyp_dna(hyp_id: str, hyps_path: Path | None = None) -> dict[str, Any] | None:
    from trader_platform.hypothesis_registry import HypothesisRegistry

    reg = HypothesisRegistry(hyps_path or _HYPS)
    try:
        h = reg.get(hyp_id)
    except Exception:
        return None
    if h is None:
        return None
    dna = h.dna if hasattr(h, "dna") else None
    if not isinstance(dna, dict):
        return None
    return dna


def peer_symbols(
    origin: str,
    *,
    shortlist_path: Path | None = None,
    extra: list[str] | None = None,
    max_peers: int = 6,
    exclusive: bool = False,
) -> list[str]:
    """Build peer list. Default: other shortlist names, then extra or _DEFAULT_PEERS.

    exclusive=True: only ``extra`` (unused-universe hunt). Shortlist leftovers
    otherwise consume every max_peers=6 slot, so SOFI/PFE/NIO never get honesty.
    """
    peers: list[str] = []
    if not exclusive:
        sl = _load_json(shortlist_path or _SHORTLIST)
        for row in sl.get("shortlist") or []:
            s = str(row.get("symbol") or "").upper()
            if s and s != origin.upper() and s not in peers:
                peers.append(s)
    fill = extra if (exclusive or extra is not None) else _DEFAULT_PEERS
    for s in fill or []:
        su = str(s or "").upper()
        if su and su != origin.upper() and su not in peers:
            peers.append(su)
    cap = max(1, int(max_peers))
    return peers[:cap]


def run_peer_sims(
    *,
    structure: str,
    config: dict[str, Any],
    origin: str,
    peers: list[str],
    period: str = "2y",
    sleeve_usd: float = 3000.0,
    min_trades: int = 15,
) -> list[dict[str, Any]]:
    from trader_platform.research.pcs_sim import run_pcs_backtest

    rows: list[dict[str, Any]] = []
    cfg = dict(config or {})
    # origin first for baseline
    for sym in [origin.upper()] + [p.upper() for p in peers if p.upper() != origin.upper()]:
        try:
            res = run_pcs_backtest(
                sym,
                period=period,
                config=cfg,
                sleeve_usd=sleeve_usd,
                structure=structure,
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "symbol": sym,
                    "ok": False,
                    "reason": f"error:{exc}",
                    "peer_pass": False,
                }
            )
            continue
        metrics = getattr(res, "metrics", None) or {}
        if not isinstance(metrics, dict):
            metrics = {}
        n = int(getattr(res, "n_trades", None) or metrics.get("n_trades") or 0)
        pnl = metrics.get("total_pnl_per_contract")
        try:
            pnl_f = float(pnl) if pnl is not None else None
        except (TypeError, ValueError):
            pnl_f = None
        dd = metrics.get("max_dd_per_contract")
        try:
            dd_f = float(dd) if dd is not None else None
        except (TypeError, ValueError):
            dd_f = None
        ml = metrics.get("avg_max_loss_usd") or metrics.get("p95_max_loss_usd")
        try:
            ml_f = float(ml) if ml is not None else None
        except (TypeError, ValueError):
            ml_f = None
        ok = bool(getattr(res, "ok", False)) and not bool(getattr(res, "skipped", False))
        peer_pass = bool(
            ok and n >= int(min_trades) and pnl_f is not None and pnl_f > 0
        )
        rows.append(
            {
                "symbol": sym,
                "ok": ok,
                "skipped": bool(getattr(res, "skipped", False)),
                "reason": getattr(res, "reason", None),
                "n_trades": n,
                "total_pnl_per_contract": pnl_f,
                "max_dd_per_contract": dd_f,
                "max_loss_usd": ml_f,
                "is_origin": sym == origin.upper(),
                "peer_pass": peer_pass and sym != origin.upper(),
                "origin_pass": peer_pass and sym == origin.upper(),
            }
        )
    return rows


def run_shortlist_dna_multi(
    *,
    top_n: int = 3,
    max_peers: int = 6,
    min_trades: int = 15,
    min_peer_pass: int = 2,
    period: str = "2y",
    sleeve_usd: float = 3000.0,
    report_path: Path | None = None,
    rotation_path: Path | None = None,
    shortlist_path: Path | None = None,
    hyps_path: Path | None = None,
    extra_peers: list[str] | None = None,
    exclusive_peers: bool = False,
    hyp_ids: list[str] | None = None,
) -> dict[str, Any]:
    pinned = [str(h).strip() for h in (hyp_ids or []) if str(h).strip()]
    leaders = select_leader_hyps(
        top_n=max(int(top_n) * 4, 8) if not pinned else max(len(pinned), 1),
        rotation_path=rotation_path,
        shortlist_path=shortlist_path,
        hyp_ids=pinned or None,
    )
    results: list[dict[str, Any]] = []
    n_living = 0
    living_cap = len(pinned) if pinned else int(top_n)
    for lead in leaders:
        hid = str(lead.get("hyp_id") or "")
        origin = str(lead.get("symbol") or "").upper()
        structure = str(lead.get("structure") or "").lower()
        dna = load_hyp_dna(hid, hyps_path=hyps_path)
        if not dna:
            results.append(
                {
                    "hyp_id": hid,
                    "symbol": origin,
                    "structure": structure,
                    "ok": False,
                    "reason": "hyp_dna_missing",
                }
            )
            continue
        if n_living >= living_cap:
            break
        n_living += 1
        cfg = dict(dna.get("config") or {})
        peers = peer_symbols(
            origin,
            shortlist_path=shortlist_path,
            extra=extra_peers,
            max_peers=max_peers,
            exclusive=bool(exclusive_peers),
        )
        per = run_peer_sims(
            structure=structure,
            config=cfg,
            origin=origin,
            peers=peers,
            period=period,
            sleeve_usd=sleeve_usd,
            min_trades=min_trades,
        )
        peer_pass_syms = [r["symbol"] for r in per if r.get("peer_pass")]
        origin_ok = any(r.get("origin_pass") for r in per)
        n_peer = len(peer_pass_syms)
        multi_ok = origin_ok and n_peer >= int(min_peer_pass)
        results.append(
            {
                "hyp_id": hid,
                "dna_id": dna.get("dna_id"),
                "symbol": origin,
                "structure": structure,
                "config_fp": _config_fp(cfg, structure),
                "config": cfg,
                "peers_tested": peers,
                "per_symbol": per,
                "origin_ok": origin_ok,
                "peer_pass_symbols": peer_pass_syms,
                "n_peer_pass": n_peer,
                "multi_symbol_ok": multi_ok,
                "ledger": {
                    "dense_neg_ge3": lead.get("dense_neg_ge3"),
                    "max_dd": lead.get("max_dd"),
                    "b4_slip5_verdict": lead.get("b4_slip5_verdict"),
                    "b4_slip5_pnl": lead.get("b4_slip5_pnl"),
                    "full_pnl": lead.get("full_pnl"),
                    "capital_path_ok": lead.get("capital_path_ok"),
                },
                "ok": True,
            }
        )

    n_multi = sum(1 for r in results if r.get("multi_symbol_ok"))
    quality_pass = n_multi >= 1
    payload = {
        "generated_at": _now(),
        "mode": "shortlist_dna_multi_symbol",
        "n_leaders": len(leaders),
        "n_multi_symbol_ok": n_multi,
        "n_quality_pass": int(quality_pass),
        "quality_pass": quality_pass,
        "min_trades": min_trades,
        "min_peer_pass": min_peer_pass,
        "period": period,
        "sleeve_usd": sleeve_usd,
        "results": results,
        "trading_authority": False,
        "live_authority": False,
        "exclusive_peers": bool(exclusive_peers),
        "extra_peers": [str(s).upper() for s in (extra_peers or [])],
        "hyp_ids": pinned,
        "honesty": (
            "Shortlist capital_path_ok multi-leg DNA re-run on peer symbols via "
            "pcs_sim proxy (L0). quality_pass requires origin + ≥min_peer_pass "
            "peers with n_trades≥min and positive total_pnl_per_contract. "
            "Not densify-seed multi; not live edge; not MCP first-live. "
            "exclusive_peers hunts unused universe names without leftover fill. "
            "hyp_ids pins existing living catalog DNA so leftover leader order "
            "cannot consume the hunt."
        ),
    }
    out = Path(report_path) if report_path else _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["report_path"] = str(out)
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--top-n", type=int, default=3)
    p.add_argument("--max-peers", type=int, default=6)
    p.add_argument("--min-trades", type=int, default=15)
    p.add_argument("--min-peer-pass", type=int, default=2)
    p.add_argument("--period", default="2y")
    p.add_argument("--sleeve-usd", type=float, default=3000.0)
    p.add_argument("--report", default=None)
    p.add_argument(
        "--extra-peers",
        default="",
        help="Comma-separated symbols appended after shortlist fill (or exclusive with --peers-only).",
    )
    p.add_argument(
        "--peers-only",
        action="store_true",
        help="Use --extra-peers as the exclusive peer set (skip leftover shortlist fill).",
    )
    p.add_argument(
        "--hyp-ids",
        default="",
        help="Comma-separated existing living hyp ids to pin (skip leftover leader order).",
    )
    args = p.parse_args(argv)
    extra = [s.strip().upper() for s in str(args.extra_peers or "").split(",") if s.strip()]
    pinned = [s.strip() for s in str(args.hyp_ids or "").split(",") if s.strip()]
    rep = run_shortlist_dna_multi(
        top_n=int(args.top_n),
        max_peers=int(args.max_peers),
        min_trades=int(args.min_trades),
        min_peer_pass=int(args.min_peer_pass),
        period=str(args.period),
        sleeve_usd=float(args.sleeve_usd),
        report_path=Path(args.report) if args.report else None,
        extra_peers=extra or None,
        exclusive_peers=bool(args.peers_only),
        hyp_ids=pinned or None,
    )
    print(
        json.dumps(
            {
                "n_leaders": rep.get("n_leaders"),
                "n_multi_symbol_ok": rep.get("n_multi_symbol_ok"),
                "quality_pass": rep.get("quality_pass"),
                "report_path": rep.get("report_path"),
                "results": [
                    {
                        "hyp_id": r.get("hyp_id"),
                        "symbol": r.get("symbol"),
                        "structure": r.get("structure"),
                        "origin_ok": r.get("origin_ok"),
                        "n_peer_pass": r.get("n_peer_pass"),
                        "peer_pass_symbols": r.get("peer_pass_symbols"),
                        "multi_symbol_ok": r.get("multi_symbol_ok"),
                        "reason": r.get("reason"),
                    }
                    for r in (rep.get("results") or [])
                ],
                "live_authority": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

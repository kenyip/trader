"""First-live lane: RH MCP placeable single-leg seats that fit the $3k sleeve.

Research shortlist is mostly multi-leg PCS (paper/research only until multi-leg
place exists). This module ranks **single-leg** DNA from evolve sims against
capital proxies so go-live status can name a real first-money candidate.

Honesty: sim scores + spot BP proxies — not observed chains, not live authority.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from trader_platform.research.capital import SLEEVE_3K, compute_capital

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_EVOLVE_DB = _REPO / ".cache" / "platform" / "evolve_sim.sqlite"
DEFAULT_RESEARCH_DB = _REPO / ".cache" / "platform" / "research.db"
DEFAULT_REPORT = _REPO / "reports" / "bootstrap" / "FIRST_LIVE_LANE.json"

# Structures RH MCP can place today (single-leg class). Multi-leg stays research.
SINGLE_LEG_STRUCTURES = frozenset(
    {
        "cash_secured_put",
        "csp",
        "short_put_credit",
        "short_call_credit",
        "regime_short_premium",
        "short_dte_aggressive",
        "long_dte_conservative",
        "wheel_assignment",
        "long_put",
        "long_call",
    }
)

# Cash-secured / short premium needs full collateral; long debit is separate path.
SHORT_COLLATERAL_STRUCTURES = frozenset(
    {
        "cash_secured_put",
        "csp",
        "short_put_credit",
        "short_call_credit",
        "regime_short_premium",
        "short_dte_aggressive",
        "long_dte_conservative",
        "wheel_assignment",
    }
)

VERDICT_RANK = {
    "SHIP": 4,
    "NULL": 2,
    "NEEDS_MORE_DATA": 1,
    "REJECT": 0,
}

STATUS_RANK = {
    "paper": 4,
    "testing": 3,
    "candidate": 2,
    "shadow": 5,
    "live": 6,
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _finite(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def classify_place_shape(structure: str) -> str:
    s = (structure or "").strip().lower()
    if s in SINGLE_LEG_STRUCTURES:
        return "single_leg"
    if s in {
        "put_credit_spread",
        "call_credit_spread",
        "iron_condor",
        "iron_butterfly",
        "calendar",
        "diagonal",
    }:
        return "multi_leg"
    return "other"


def load_symbol_capital(
    research_db: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    """Latest research run: spot + capital tiers per symbol."""
    path = Path(research_db) if research_db else DEFAULT_RESEARCH_DB
    out: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return out
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rid_row = con.execute("SELECT MAX(id) FROM research_runs").fetchone()
        rid = rid_row[0] if rid_row else None
        if rid is None:
            return out
        # Prefer opportunities capital_fit when present; always recompute from spot.
        spots: dict[str, float] = {}
        for sym, spot in con.execute(
            "SELECT symbol, spot FROM symbol_scores WHERE run_id=?",
            (rid,),
        ):
            spots[str(sym).upper()] = float(spot or 0.0)
        opp_fit: dict[str, str] = {}
        opp_bp: dict[str, float] = {}
        try:
            for sym, fit, bp in con.execute(
                "SELECT symbol, capital_fit, short_premium_bp_proxy "
                "FROM opportunities WHERE run_id=?",
                (rid,),
            ):
                opp_fit[str(sym).upper()] = str(fit or "unknown")
                opp_bp[str(sym).upper()] = float(bp or 0.0)
        except sqlite3.Error:
            pass
        for sym, spot in spots.items():
            cap = compute_capital(spot)
            d = cap.to_dict()
            d["symbol"] = sym
            d["research_run_id"] = rid
            if sym in opp_fit and opp_fit[sym] not in ("", "unknown"):
                # Keep recomputed fit as source of truth; note research label.
                d["research_capital_fit_label"] = opp_fit[sym]
            if sym in opp_bp and opp_bp[sym] > 0:
                d["research_bp_label"] = opp_bp[sym]
            out[sym] = d
    finally:
        con.close()
    return out


def load_single_leg_sim_rows(
    evolve_db: Path | str | None = None,
    *,
    min_trades: int = 8,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Best recent sim rows per (structure, symbol, dna_id) for single-leg DNA."""
    path = Path(evolve_db) if evolve_db else DEFAULT_EVOLVE_DB
    if not path.is_file():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        structures = sorted(SINGLE_LEG_STRUCTURES - {"csp"})  # csp alias only
        placeholders = ",".join("?" * len(structures))
        rows = con.execute(
            f"""
            SELECT dna_id, structure, symbol, generation, verdict, score,
                   n_trades, metrics_json, config_json, parent_id, ts
            FROM sim_runs
            WHERE structure IN ({placeholders})
              AND n_trades >= ?
              AND verdict IN ('SHIP', 'NEEDS_MORE_DATA', 'NULL')
            ORDER BY id DESC
            LIMIT ?
            """,
            (*structures, int(min_trades), int(limit)),
        ).fetchall()
    finally:
        con.close()

    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for (
        dna_id,
        structure,
        symbol,
        generation,
        verdict,
        score,
        n_trades,
        metrics_json,
        config_json,
        parent_id,
        ts,
    ) in rows:
        key = (str(dna_id or ""), str(structure or ""), str(symbol or "").upper())
        metrics: dict[str, Any] = {}
        config: dict[str, Any] = {}
        try:
            metrics = json.loads(metrics_json or "{}")
        except Exception:
            metrics = {}
        try:
            config = json.loads(config_json or "{}")
        except Exception:
            config = {}
        score_f = _finite(score, default=-1e9)
        cand = {
            "dna_id": key[0],
            "structure": key[1],
            "symbol": key[2],
            "generation": int(generation or 0),
            "verdict": str(verdict or ""),
            "score": score_f,
            "n_trades": int(n_trades or 0),
            "metrics": metrics,
            "config": config,
            "parent_id": parent_id or "",
            "sim_ts": ts,
            "hyp_id": f"hyp_dna_{key[2].lower()}_{key[1]}_{str(key[0])[:8]}"
            if key[0]
            else None,
        }
        prev = best.get(key)
        if prev is None:
            best[key] = cand
            continue
        # Prefer higher verdict rank, then more trades, then higher finite score
        prev_key = (
            VERDICT_RANK.get(prev["verdict"], -1),
            int(prev["n_trades"]),
            _finite(prev["score"], -1e9),
        )
        new_key = (
            VERDICT_RANK.get(cand["verdict"], -1),
            int(cand["n_trades"]),
            score_f,
        )
        if new_key > prev_key:
            best[key] = cand
    return list(best.values())


def _max_loss_proxy(row: Mapping[str, Any], capital: Mapping[str, Any] | None) -> float:
    metrics = row.get("metrics") or {}
    for k in ("max_loss_usd", "max_loss", "max_dd", "window_max_dd"):
        if metrics.get(k) is not None:
            v = _finite(metrics.get(k), default=-1.0)
            if v >= 0:
                return v
    cfg = row.get("config") or {}
    if cfg.get("max_loss_budget_usd") is not None:
        return _finite(cfg.get("max_loss_budget_usd"), 300.0)
    # CSP worst case is collateral; use short BP as upper bound for sizing honesty
    if capital and capital.get("short_premium_bp_proxy"):
        return float(capital["short_premium_bp_proxy"])
    return 0.0


def rank_first_live_seats(
    *,
    sim_rows: Sequence[Mapping[str, Any]] | None = None,
    capital_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
    sleeve_usd: float = SLEEVE_3K,
    max_loss_budget_usd: float = 300.0,
    min_trades: int = 15,
    top_n: int = 12,
    require_fit_3k_short: bool = True,
) -> dict[str, Any]:
    """Rank single-leg sim seats that are capital-fit for first live on RH MCP."""
    sims = list(sim_rows) if sim_rows is not None else load_single_leg_sim_rows(min_trades=8)
    caps = dict(capital_by_symbol) if capital_by_symbol is not None else load_symbol_capital()

    ranked: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for row in sims:
        structure = str(row.get("structure") or "")
        symbol = str(row.get("symbol") or "").upper()
        if classify_place_shape(structure) != "single_leg":
            continue
        cap = caps.get(symbol) or {}
        n_trades = int(row.get("n_trades") or 0)
        verdict = str(row.get("verdict") or "")
        score = _finite(row.get("score"), -1e9)
        ml = _max_loss_proxy(row, cap)
        short_bp = float(cap.get("short_premium_bp_proxy") or 0.0)
        fit_short = str(cap.get("capital_fit") or "unknown")
        fit_long = str(cap.get("capital_fit_long") or "unknown")
        is_short = structure in SHORT_COLLATERAL_STRUCTURES

        reasons: list[str] = []
        if n_trades < min_trades:
            reasons.append(f"thin_n={n_trades}<{min_trades}")
        if verdict not in ("SHIP", "NEEDS_MORE_DATA"):
            reasons.append(f"verdict={verdict}")
        if is_short:
            if short_bp <= 0:
                reasons.append("no_spot_bp")
            elif short_bp > sleeve_usd:
                reasons.append(f"csp_bp={short_bp:.0f}>sleeve={sleeve_usd:.0f}")
            elif require_fit_3k_short and fit_short != "fit_3k":
                reasons.append(f"capital_fit={fit_short}")
            # CSP max loss is large by nature; gate on BP fit, not $300 defined risk
        else:
            # long debit path: max loss should be bounded
            if ml <= 0:
                reasons.append("max_loss_unknown")
            elif ml > max_loss_budget_usd:
                reasons.append(f"max_loss={ml:.0f}>{max_loss_budget_usd:.0f}")
            if fit_long not in ("fit_3k", "fit_5k") and short_bp > sleeve_usd:
                reasons.append(f"long_fit={fit_long}")

        placeable = True
        capital_ok = not any(
            r.startswith("csp_bp=") or r.startswith("capital_fit=") or r.startswith("max_loss=")
            for r in reasons
        )
        sim_ok = not any(r.startswith("thin_n") or r.startswith("verdict=") for r in reasons)

        seat = {
            "hyp_id": row.get("hyp_id") or f"dna:{row.get('dna_id')}",
            "dna_id": row.get("dna_id"),
            "structure": structure,
            "symbol": symbol,
            "place_shape": "single_leg",
            "mcp_placeable": True,
            "verdict": verdict,
            "score": score if math.isfinite(score) else None,
            "n_trades": n_trades,
            "max_loss_usd_proxy": round(ml, 2) if ml else None,
            "csp_bp_proxy": round(short_bp, 2) if short_bp else None,
            "capital_fit": fit_short,
            "capital_fit_long": fit_long,
            "spot": cap.get("spot"),
            "lane": "first_live_single_leg",
            "status_hint": "testing",
            "reject_reasons": reasons,
            "capital_ok": capital_ok,
            "sim_ok": sim_ok,
            "eligible": capital_ok and sim_ok and placeable,
            "why": (
                f"single-leg {structure} on {symbol}; "
                f"{'fits $3k CSP BP' if capital_ok and is_short else 'capital check'}; "
                f"sim {verdict} n={n_trades}"
            ),
            "caveat": (
                "Proxy sim + spot BP only. Not pack-grade multi-symbol edge. "
                "RH MCP single-leg place still requires Ken arm for live."
            ),
        }

        if seat["eligible"]:
            ranked.append(seat)
        else:
            rejected.append(seat)

    def sort_key(s: Mapping[str, Any]) -> tuple:
        score = _finite(s.get("score"), -1e9)
        # Prefer non-negative sim scores among equal verdict/n (avoid SHIP@loss leaders)
        score_sign = 1 if score >= 0 else 0
        return (
            1 if s.get("eligible") else 0,
            VERDICT_RANK.get(str(s.get("verdict")), -1),
            score_sign,
            int(s.get("n_trades") or 0),
            -float(s.get("csp_bp_proxy") or 1e9),  # cheaper collateral first
            score,
        )

    ranked.sort(key=sort_key, reverse=True)
    rejected.sort(key=sort_key, reverse=True)

    # Diversify shortlist by symbol so clones don't monopolize the board
    top: list[dict[str, Any]] = []
    seen_sym: set[str] = set()
    for s in ranked:
        sym = str(s.get("symbol") or "")
        if sym in seen_sym:
            continue
        seen_sym.add(sym)
        top.append(s)
        if len(top) >= top_n:
            break
    # If fewer symbols than top_n, fill with next-best DNA (including clones)
    if len(top) < top_n:
        for s in ranked:
            if s in top:
                continue
            top.append(s)
            if len(top) >= top_n:
                break
    leader = top[0] if top else None
    # Near-misses: capital_ok failed but sim SHIP (e.g. NFLX CSP) for honesty
    near = [
        r
        for r in rejected
        if r.get("sim_ok") and str(r.get("verdict")) == "SHIP" and not r.get("capital_ok")
    ][:8]

    return {
        "generated_at": _now(),
        "mode": "first_live_lane",
        "sleeve_usd": sleeve_usd,
        "max_loss_budget_usd": max_loss_budget_usd,
        "min_trades": min_trades,
        "mcp_place": "single_leg_only",
        "live_authority": False,
        "trading_authority": False,
        "n_sim_rows": len(sims),
        "n_eligible": len(ranked),
        "n_rejected": len(rejected),
        "leader": leader,
        "shortlist": top,
        "near_miss_oversized": near,
        "honesty": (
            "First-live lane ranks RH-placeable single-leg DNA with capital-fit "
            "CSP BP (or bounded long debit). Multi-leg PCS research leaders are "
            "intentionally excluded. Proxy sim + spot BP — not live edge."
        ),
    }


def write_first_live_report(
    report: Mapping[str, Any],
    path: Path | str | None = None,
) -> Path:
    p = Path(path) if path else DEFAULT_REPORT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def build_and_write_first_live_lane(
    *,
    report_path: Path | str | None = None,
    sleeve_usd: float = SLEEVE_3K,
    min_trades: int = 15,
    top_n: int = 12,
    evolve_db: Path | str | None = None,
    research_db: Path | str | None = None,
) -> dict[str, Any]:
    report = rank_first_live_seats(
        sim_rows=load_single_leg_sim_rows(evolve_db, min_trades=max(8, min_trades // 2)),
        capital_by_symbol=load_symbol_capital(research_db),
        sleeve_usd=sleeve_usd,
        min_trades=min_trades,
        top_n=top_n,
    )
    path = write_first_live_report(report, report_path)
    out = dict(report)
    out["report_path"] = str(path)
    return out

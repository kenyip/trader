"""Evolve tick v0 — free strategy search via DNA mutation + simulation.

Pipeline (paper / research only):
  1. Pull top research symbols (capital-aware) — freedom of *where*
  2. Build population: structure catalog × symbols + mutations — freedom of *what*
  3. Simulate each DNA via engine backtest with StrategyConfig overrides
  4. Score sims → SHIP / NULL / REJECT / NEEDS_MORE_DATA
  5. Optionally write candidate hypotheses carrying full DNA (entry+exit+mgmt)
  6. Persist evolve_audit.jsonl + evolve_sim.sqlite

Hard rules:
  - Never place_* / agentic_live / fund
  - Never auto-edit strategies.py / live.py (code patches Ken-gated)
  - Never auto → shadow/live
  - Stand-aside / zero-trade sim is valid evidence (often NULL not SHIP)

Usage:
  .venv/bin/python -m trader_platform.evolve_tick --once
  .venv/bin/python -m trader_platform.evolve_tick --once --apply --top-symbols 4 --mutants 2
  .venv/bin/python -m trader_platform.evolve_tick --once --apply --seed 7 --json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from trader_platform.hypothesis_registry import HypothesisRegistry
from trader_platform.research.store import default_db_path, load_run_scores, latest_run_id
from trader_platform.strategy_dna import (
    STRUCTURE_CATALOG,
    StrategyDNA,
    dna_from_structure,
    family_to_structure,
    mutate_dna,
    seed_population,
)

_REPO = Path(__file__).resolve().parents[1]
_CACHE = _REPO / ".cache" / "platform"
_EVOLVE_AUDIT = _CACHE / "evolve_audit.jsonl"
_EVOLVE_DB = _CACHE / "evolve_sim.sqlite"
_BT_DUMP = _CACHE / "evolve_backtests"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip().lower()).strip("_")
    return s[:40] or "x"


@dataclass
class SimVerdict:
    dna: StrategyDNA
    ok: bool
    skipped: bool
    reason: str
    n_trades: int
    metrics: dict[str, Any]
    score: float
    verdict: str  # SHIP | NULL | REJECT | NEEDS_MORE_DATA
    evidence_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna": self.dna.to_dict(),
            "ok": self.ok,
            "skipped": self.skipped,
            "reason": self.reason,
            "n_trades": self.n_trades,
            "metrics": self.metrics,
            "score": self.score,
            "verdict": self.verdict,
            "evidence_path": self.evidence_path,
        }


@dataclass
class EvolveReport:
    ts: str
    applied: bool
    dry_run: bool
    symbols: list[str]
    n_population: int
    results: list[SimVerdict] = field(default_factory=list)
    created_hyps: list[str] = field(default_factory=list)
    updated_hyps: list[str] = field(default_factory=list)
    audit_path: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "applied": self.applied,
            "dry_run": self.dry_run,
            "symbols": self.symbols,
            "n_population": self.n_population,
            "results": [r.to_dict() for r in self.results],
            "created_hyps": self.created_hyps,
            "updated_hyps": self.updated_hyps,
            "audit_path": self.audit_path,
            "errors": self.errors,
            "n_ship": sum(1 for r in self.results if r.verdict == "SHIP"),
            "n_null": sum(1 for r in self.results if r.verdict == "NULL"),
            "n_reject": sum(1 for r in self.results if r.verdict == "REJECT"),
        }


def _ensure_evolve_db(path: Path = _EVOLVE_DB) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sim_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            dna_id TEXT,
            structure TEXT,
            symbol TEXT,
            generation INTEGER,
            verdict TEXT,
            score REAL,
            n_trades INTEGER,
            metrics_json TEXT,
            config_json TEXT,
            parent_id TEXT
        )
        """
    )
    con.commit()
    con.close()


def _persist_sim(v: SimVerdict, ts: str, path: Path = _EVOLVE_DB) -> None:
    _ensure_evolve_db(path)
    con = sqlite3.connect(str(path))
    sym = (v.dna.symbols or ["?"])[0]
    con.execute(
        """
        INSERT INTO sim_runs
        (ts, dna_id, structure, symbol, generation, verdict, score, n_trades, metrics_json, config_json, parent_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            v.dna.ensure_id(),
            v.dna.structure,
            sym,
            int(v.dna.generation or 0),
            v.verdict,
            _finite(v.score, default=-1e9),
            int(v.n_trades),
            json.dumps(v.metrics, default=str),
            json.dumps(v.dna.config, default=str),
            v.dna.parent_id or "",
        ),
    )
    con.commit()
    con.close()


def top_research_symbols(
    *,
    top_n: int = 5,
    sleeve_usd: Optional[float] = 3000.0,
    prefer_fit: bool = True,
    db_path: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Latest research run symbols with composite + family + capital fit."""
    db = Path(db_path) if db_path else default_db_path()
    rid = latest_run_id(db)
    if rid is None:
        return []
    rows = [r for r in load_run_scores(rid, db) if not r.get("error")]
    rows.sort(key=lambda r: float(r.get("composite") or 0), reverse=True)
    if prefer_fit and sleeve_usd:
        fit_ok = []
        rest = []
        for r in rows:
            fit = str(r.get("capital_fit") or "")
            # fit_3k / fit_5k / fit_15k depending on sleeve
            if sleeve_usd <= 3500 and fit in {"fit_3k", "fit_5k", "fit_15k"}:
                fit_ok.append(r)
            elif sleeve_usd <= 6000 and fit in {"fit_3k", "fit_5k", "fit_15k"}:
                fit_ok.append(r)
            elif fit != "oversized":
                fit_ok.append(r)
            else:
                rest.append(r)
        # still allow some oversized for research freedom, but rank fit first
        rows = fit_ok + rest
    return rows[:top_n]


# Ship bar (v0.1, 2026-07-09 wake): thin perfect samples must not outrank real edges.
# Historical bug: zero-loss PF → inf score → NFLX n=7 @ 100% WR ranked above multi-trade edges.
MIN_TRADES_SHIP = 15
MIN_TRADES_SIGNAL = 8
PF_CAP = 10.0
MAX_ABS_SCORE = 1e6
# Higher first when sorting. Score alone is not enough: thin-perfect samples can
# still print large raw scores from lucky small n.
VERDICT_RANK: dict[str, int] = {
    "SHIP": 4,
    "NULL": 2,
    "NEEDS_MORE_DATA": 1,
    "REJECT": 0,
}


def _finite(x: float, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def score_sim_metrics(
    *,
    n_trades: int,
    pnl: float,
    win_rate: float,
    max_dd: float,
    profit_factor: float,
    skipped: bool = False,
    ok: bool = True,
    skip_reason: str = "",
) -> tuple[str, float, str, float]:
    """Map sim metrics → (verdict, finite_score, reason, capped_pf).

    Pure / network-free so wake + smoke can assert the ship bar without yfinance.
    """
    n = int(n_trades or 0)
    pnl = _finite(pnl)
    wr = _finite(win_rate)
    if wr > 1.0:  # allow 0–100 inputs
        wr = wr / 100.0
    wr = min(max(wr, 0.0), 1.0)
    dd = abs(_finite(max_dd))
    try:
        raw_pf = float(profit_factor) if profit_factor is not None else 0.0
    except (TypeError, ValueError):
        raw_pf = 0.0
    # non-finite raw PF (all wins / zero losses) → optimistic cap, never inf score
    pf = PF_CAP if not math.isfinite(raw_pf) else min(max(raw_pf, 0.0), PF_CAP)

    # Cost-function-aligned core (GOAL.md): pnl − dd, with modest WR/PF bonuses.
    core = pnl - dd * 1.0 + wr * 50.0 + max(pf - 1.0, 0.0) * 20.0
    core = _finite(core, default=-1e9)
    core = max(min(core, MAX_ABS_SCORE), -MAX_ABS_SCORE)

    if skipped or not ok:
        verdict = "NEEDS_MORE_DATA" if "unavailable" in (skip_reason or "") else "NULL"
        return verdict, -1.0, (skip_reason or "sim_skipped"), pf
    if n <= 0:
        return "NULL", 0.0, "zero_trades", pf
    if pnl < -500 or dd > 800:
        return "REJECT", _finite(pnl - dd * 0.5, default=-1e9), "poor_risk_or_pnl", pf
    if n < MIN_TRADES_SIGNAL:
        # Cap so sparse luck cannot dominate denser SHIP scores in mixed lists.
        return "NEEDS_MORE_DATA", min(_finite(core * 0.05), 25.0), "few_trades", pf
    # Perfect thin sample (0 DD, ~100% WR) is sampling luck until denser — not SHIP.
    if n < MIN_TRADES_SHIP and wr >= 0.95 and dd < 1e-6:
        return (
            "NEEDS_MORE_DATA",
            min(_finite(core * 0.05), 40.0),
            "thin_perfect_sample",
            pf,
        )
    if n >= MIN_TRADES_SHIP and pnl > 0 and wr >= 0.50 and pf >= 1.05:
        return "SHIP", core, "positive_sim", pf
    if n >= MIN_TRADES_SIGNAL and pnl > 0 and wr >= 0.45:
        return "NULL", core, "borderline_not_ship_bar", pf
    return "NULL", core, "weak_edge", pf


def assert_ship_bar() -> None:
    """Offline regression for the ship bar. No network / no engine.

    Historical failure mode: NFLX n=7 @ 100% WR with PF=inf produced score=inf
    and outranked denser multi-trade edges. This must never ship on thin samples,
    and scores/PF must always be finite.
    """
    # Thin perfect + inf PF → NEEDS_MORE_DATA, finite score, PF capped
    for n, want_reason in (
        (7, "few_trades"),  # below MIN_TRADES_SIGNAL
        (8, "thin_perfect_sample"),
        (10, "thin_perfect_sample"),
        (14, "thin_perfect_sample"),
    ):
        v, s, r, pf = score_sim_metrics(
            n_trades=n,
            pnl=400.0 + n * 10,
            win_rate=1.0,
            max_dd=0.0,
            profit_factor=float("inf"),
        )
        assert v == "NEEDS_MORE_DATA", (n, v, r)
        assert r == want_reason, (n, r, want_reason)
        assert math.isfinite(s) and abs(s) <= MAX_ABS_SCORE, s
        assert pf == PF_CAP, pf

    # n=12 positive but under MIN_TRADES_SHIP → not SHIP
    v, s, r, pf = score_sim_metrics(
        n_trades=12, pnl=150.0, win_rate=0.66, max_dd=80.0, profit_factor=1.4
    )
    assert v == "NULL" and r == "borderline_not_ship_bar", (v, r)
    assert math.isfinite(s)

    # Dense positive edge → SHIP and outranks thin-perfect score
    thin_s = score_sim_metrics(
        n_trades=10, pnl=623.0, win_rate=1.0, max_dd=0.0, profit_factor=float("inf")
    )[1]
    v, dense_s, r, pf = score_sim_metrics(
        n_trades=30, pnl=480.0, win_rate=0.70, max_dd=130.0, profit_factor=1.68
    )
    assert v == "SHIP" and r == "positive_sim", (v, r)
    assert dense_s > thin_s, (dense_s, thin_s)

    # Non-finite PF inputs never leak into score/pf
    for pf_in in (float("nan"), float("inf"), float("-inf"), 1e300):
        v, s, r, pf = score_sim_metrics(
            n_trades=20, pnl=100.0, win_rate=0.55, max_dd=40.0, profit_factor=pf_in
        )
        assert math.isfinite(s) and math.isfinite(pf), (pf_in, s, pf)
        assert pf <= PF_CAP
        assert abs(s) <= MAX_ABS_SCORE

    # WR as 0–100 percent
    v, s, r, pf = score_sim_metrics(
        n_trades=10, pnl=100.0, win_rate=100.0, max_dd=0.0, profit_factor=float("inf")
    )
    assert v == "NEEDS_MORE_DATA" and r == "thin_perfect_sample", (v, r)

    # Zero trades / reject risk
    v, s, r, _ = score_sim_metrics(
        n_trades=0, pnl=0.0, win_rate=0.0, max_dd=0.0, profit_factor=0.0
    )
    assert v == "NULL" and r == "zero_trades" and s == 0.0, (v, s, r)
    v, s, r, _ = score_sim_metrics(
        n_trades=40, pnl=-600.0, win_rate=0.6, max_dd=900.0, profit_factor=0.5
    )
    assert v == "REJECT" and r == "poor_risk_or_pnl" and math.isfinite(s)


def sim_dna(
    dna: StrategyDNA,
    *,
    period: str = "2y",
    use_cache: bool = True,
    dump_dir: Optional[Path] = None,
) -> SimVerdict:
    """Run engine/PCS backtest with DNA config (paper evidence only)."""
    from trader_platform.research.backtest_hooks import run_symbol_backtest

    sym = (dna.symbols or [""])[0].upper()
    if not sym:
        return SimVerdict(
            dna=dna,
            ok=False,
            skipped=True,
            reason="no symbol on DNA",
            n_trades=0,
            metrics={},
            score=-1e9,
            verdict="REJECT",
        )

    capital_meta: dict = {}
    if dna.uses_collar_sim():
        from trader_platform.research.collar_sim import run_collar_backtest

        collar = run_collar_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config=dna.sim_config(),
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(collar.metrics or {})
        n = int(collar.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(collar.skipped)
        ok = bool(collar.ok)
        skip_reason = collar.reason or ""
        capital_meta = dict(collar.capital or {})
        evidence_path = ""
        if dump_dir and collar.trades:
            path = Path(dump_dir) / f"{sym}_collar_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(collar.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_put_ratio_backspread_sim():
        from trader_platform.research.put_ratio_backspread_sim import run_put_ratio_backspread_backtest

        ratio = run_put_ratio_backspread_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config=dna.sim_config(),
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(ratio.metrics or {})
        n = int(ratio.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(ratio.skipped)
        ok = bool(ratio.ok)
        skip_reason = ratio.reason or ""
        capital_meta = dict(ratio.capital or {})
        evidence_path = ""
        if dump_dir and ratio.trades:
            path = Path(dump_dir) / f"{sym}_put_ratio_backspread_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(ratio.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_iron_butterfly_sim():
        from trader_platform.research.iron_butterfly_sim import run_iron_butterfly_backtest

        iron_butterfly = run_iron_butterfly_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config={**dna.sim_config(), "structure": dna.structure},
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(iron_butterfly.metrics or {})
        n = int(iron_butterfly.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(iron_butterfly.skipped)
        ok = bool(iron_butterfly.ok)
        skip_reason = iron_butterfly.reason or ""
        capital_meta = dict(iron_butterfly.capital or {})
        evidence_path = ""
        if dump_dir and iron_butterfly.trades:
            path = Path(dump_dir) / f"{sym}_iron_butterfly_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(iron_butterfly.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_debit_vertical_sim():
        from trader_platform.research.debit_vertical_sim import run_debit_vertical_backtest

        debit_vertical = run_debit_vertical_backtest(
            sym,
            structure=dna.structure,
            period=period,
            use_cache=use_cache,
            config=dna.sim_config(),
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(debit_vertical.metrics or {})
        n = int(debit_vertical.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(debit_vertical.skipped)
        ok = bool(debit_vertical.ok)
        skip_reason = debit_vertical.reason or ""
        capital_meta = dict(debit_vertical.capital or {})
        evidence_path = ""
        if dump_dir and debit_vertical.trades:
            path = Path(dump_dir) / f"{sym}_debit_vertical_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(debit_vertical.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_butterfly_sim():
        from trader_platform.research.butterfly_sim import run_butterfly_backtest

        butterfly = run_butterfly_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config=dna.sim_config(),
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(butterfly.metrics or {})
        n = int(butterfly.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(butterfly.skipped)
        ok = bool(butterfly.ok)
        skip_reason = butterfly.reason or ""
        capital_meta = dict(butterfly.capital or {})
        evidence_path = ""
        if dump_dir and butterfly.trades:
            path = Path(dump_dir) / f"{sym}_butterfly_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(butterfly.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_double_diagonal_sim():
        from trader_platform.research.double_diagonal_sim import run_double_diagonal_backtest

        double_diagonal = run_double_diagonal_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config=dna.sim_config(),
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(double_diagonal.metrics or {})
        n = int(double_diagonal.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(double_diagonal.skipped)
        ok = bool(double_diagonal.ok)
        skip_reason = double_diagonal.reason or ""
        capital_meta = dict(double_diagonal.capital or {})
        evidence_path = ""
        if dump_dir and double_diagonal.trades:
            path = Path(dump_dir) / f"{sym}_double_diagonal_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(double_diagonal.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_diagonal_sim():
        from trader_platform.research.diagonal_sim import run_diagonal_backtest

        diagonal = run_diagonal_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config=dna.sim_config(),
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(diagonal.metrics or {})
        n = int(diagonal.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(diagonal.skipped)
        ok = bool(diagonal.ok)
        skip_reason = diagonal.reason or ""
        capital_meta = dict(diagonal.capital or {})
        evidence_path = ""
        if dump_dir and diagonal.trades:
            path = Path(dump_dir) / f"{sym}_diagonal_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(diagonal.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_calendar_sim():
        from trader_platform.research.calendar_sim import run_calendar_backtest

        cal = run_calendar_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config=dna.sim_config(),
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
        )
        metrics = dict(cal.metrics or {})
        n = int(cal.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(cal.skipped)
        ok = bool(cal.ok)
        skip_reason = cal.reason or ""
        capital_meta = dict(cal.capital or {})
        evidence_path = ""
        if dump_dir and cal.trades:
            path = Path(dump_dir) / f"{sym}_calendar_trades.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cal.to_dict(), default=str, indent=2))
            evidence_path = str(path)
    elif dna.uses_pcs_sim():
        from trader_platform.research.pcs_sim import run_pcs_backtest

        pcs_cfg = dna.pcs_config()
        pcs_cfg.setdefault("structure", dna.structure)
        pcs = run_pcs_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            config=pcs_cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            structure=dna.structure,
        )
        metrics = dict(pcs.metrics or {})
        n = int(pcs.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(pcs.skipped)
        ok = bool(pcs.ok)
        skip_reason = pcs.reason or ""
        capital_meta = dict(pcs.capital or {})
        evidence_path = ""
        if dump_dir and pcs.trades:
            out_dir = Path(dump_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{sym}_pcs_trades.json"
            try:
                path.write_text(json.dumps(pcs.to_dict(), default=str, indent=2))
                evidence_path = str(path)
            except Exception:  # noqa: BLE001
                evidence_path = ""
    else:
        res = run_symbol_backtest(
            sym,
            period=period,
            use_cache=use_cache,
            dump_dir=dump_dir or _BT_DUMP,
            config_overrides=dna.config_overrides(),
        )
        metrics = dict(res.metrics or {})
        n = int(res.n_trades or metrics.get("n_trades") or 0)
        skipped = bool(res.skipped)
        ok = bool(res.ok)
        skip_reason = res.reason or ""
        evidence_path = res.evidence_path or ""

    # Engine/PCS keys: total_pnl_per_contract, win_rate_pct (0–100), max_dd_per_contract ($).
    pnl = float(
        metrics.get("total_pnl_per_contract")
        if metrics.get("total_pnl_per_contract") is not None
        else (metrics.get("total_pnl") or 0.0)
    )
    if metrics.get("win_rate_pct") is not None:
        wr = float(metrics["win_rate_pct"]) / 100.0
    else:
        wr_raw = float(metrics.get("win_rate") or 0.0)
        wr = wr_raw / 100.0 if wr_raw > 1.0 else wr_raw
    dd = float(metrics.get("max_dd_per_contract") or metrics.get("max_drawdown") or 0.0)
    pf_raw = metrics.get("profit_factor")
    try:
        pf_in = float(pf_raw) if pf_raw is not None else 0.0
    except (TypeError, ValueError):
        pf_in = float("nan")

    verdict, score, reason, pf = score_sim_metrics(
        n_trades=n,
        pnl=pnl,
        win_rate=wr,
        max_dd=dd,
        profit_factor=pf_in,
        skipped=skipped,
        ok=ok,
        skip_reason=skip_reason,
    )
    score = _finite(score, default=-1e9)

    dna.last_sim = {
        "ok": ok,
        "skipped": skipped,
        "reason": reason if ok and not skipped else skip_reason or reason,
        "n_trades": n,
        "metrics": metrics,
        "verdict": verdict,
        "score": score,
        "period": period,
        "pnl_per_contract": pnl,
        "win_rate": wr,
        "max_dd_per_contract": dd,
        "profit_factor": pf,
        "ship_bar": {
            "min_trades_ship": MIN_TRADES_SHIP,
            "min_trades_signal": MIN_TRADES_SIGNAL,
            "pf_cap": PF_CAP,
        },
        "sim_engine": (
            f"collar_sim:{dna.structure}"
            if dna.uses_collar_sim()
            else (
                f"put_ratio_backspread_sim:{dna.structure}"
                if dna.uses_put_ratio_backspread_sim()
                else (
                    f"iron_butterfly_sim:{dna.structure}"
                    if dna.uses_iron_butterfly_sim()
                    else (
                        f"debit_vertical_sim:{dna.structure}"
                        if dna.uses_debit_vertical_sim()
                        else (
                            f"butterfly_sim:{dna.structure}"
                            if dna.uses_butterfly_sim()
                            else (
                                f"double_diagonal_sim:{dna.structure}"
                                if dna.uses_double_diagonal_sim()
                                else (
                                    f"diagonal_sim:{dna.structure}"
                                    if dna.uses_diagonal_sim()
                                    else (
                                        f"calendar_sim:{dna.structure}"
                                        if dna.uses_calendar_sim()
                                        else (f"pcs_sim:{dna.structure}" if dna.uses_pcs_sim() else "single_leg")
                                    )
                                )
                            )
                        )
                    )
                )
            )
        ),
        "capital": capital_meta,
    }
    return SimVerdict(
        dna=dna,
        ok=ok,
        skipped=skipped,
        reason=str(reason),
        n_trades=n,
        metrics=metrics,
        score=float(score),
        verdict=verdict,
        evidence_path=evidence_path,
    )


def build_population(
    symbol_rows: Sequence[dict[str, Any]],
    *,
    structures: Optional[Sequence[str]] = None,
    mutants_per_seed: int = 2,
    seed: Optional[int] = None,
    include_family_seed: bool = True,
) -> list[StrategyDNA]:
    rng = random.Random(seed)
    structs = list(structures) if structures else list(STRUCTURE_CATALOG.keys())
    pop: list[StrategyDNA] = []
    for row in symbol_rows:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        if include_family_seed:
            fam = str(row.get("strategy_family") or "")
            st = family_to_structure(fam)
            if st not in structs:
                structs_local = [st] + structs
            else:
                structs_local = structs
        else:
            structs_local = structs
        # unique preserve order
        seen: set[str] = set()
        ordered = []
        for s in structs_local:
            if s not in seen:
                seen.add(s)
                ordered.append(s)
        pop.extend(
            seed_population(
                [sym],
                structures=ordered,
                rng=rng,
                mutants_per_seed=mutants_per_seed,
            )
        )
    # de-dupe by dna_id
    uniq: dict[str, StrategyDNA] = {}
    for d in pop:
        uniq[d.ensure_id()] = d
    population = list(uniq.values())
    if structures:
        allowed = set(structures)
        population = [dna for dna in population if dna.structure in allowed]
    return population


def hyp_id_for_dna(dna: StrategyDNA) -> str:
    sym = (dna.symbols or ["x"])[0]
    return f"hyp_dna_{_slug(sym)}_{_slug(dna.structure)}_{dna.ensure_id()[-8:]}"


def apply_results(
    results: Sequence[SimVerdict],
    *,
    registry: HypothesisRegistry,
    max_create: int = 5,
    ship_only: bool = False,
) -> tuple[list[str], list[str]]:
    """Write SHIP (and optionally strong NEEDS_MORE_DATA) as candidates with DNA."""
    created: list[str] = []
    updated: list[str] = []
    reg = registry
    reg.ensure_seeded()
    store = reg.load()
    by_id = {h.get("id"): h for h in store.get("hypotheses") or []}

    def _rank_key(r: SimVerdict) -> tuple[int, float]:
        # SHIP before NEEDS_MORE_DATA/NULL even if raw score is lower.
        return (VERDICT_RANK.get(r.verdict, 0), _finite(r.score, default=-1e9))

    ranked = sorted(
        [
            r
            for r in results
            if r.verdict in {"SHIP", "NEEDS_MORE_DATA"}
            or (
                not ship_only
                and r.verdict == "NULL"
                and r.n_trades >= MIN_TRADES_SIGNAL
                and _finite(r.score) > 0
            )
        ],
        key=_rank_key,
        reverse=True,
    )
    if ship_only:
        ranked = [r for r in results if r.verdict == "SHIP"]
        ranked.sort(key=_rank_key, reverse=True)

    for r in ranked[:max_create]:
        if r.verdict == "REJECT":
            continue
        dna = r.dna
        hid = hyp_id_for_dna(dna)
        score_s = f"{_finite(r.score):.2f}"
        evidence = [
            f"evolve_sim:{dna.ensure_id()}:verdict={r.verdict}:score={score_s}:trades={r.n_trades}",
        ]
        if r.evidence_path:
            evidence.append(r.evidence_path)
        if r.metrics:
            evidence.append(f"metrics:{json.dumps(r.metrics, default=str)[:200]}")

        thesis = dna.thesis_text()
        if hid in by_id:
            raw = by_id[hid]
            raw["dna"] = dna.to_dict()
            raw["thesis"] = thesis
            raw["updated"] = _now()
            for e in evidence:
                if e not in (raw.get("evidence_links") or []):
                    raw.setdefault("evidence_links", []).append(e)
            if r.verdict == "NULL":
                note = f"evolve NULL score={r.score:.1f}"
                if note not in (raw.get("null_results") or []):
                    raw.setdefault("null_results", []).append(note)
            # never auto escalate status here
            updated.append(hid)
        else:
            # only create on SHIP or NEEDS_MORE_DATA with trades
            if r.verdict not in {"SHIP", "NEEDS_MORE_DATA"} and not (r.n_trades >= 8 and r.score > 50):
                continue
            try:
                h = reg.add(
                    hypothesis_id=hid,
                    name=f"DNA:{dna.structure} {(dna.symbols or ['?'])[0]} g{dna.generation}",
                    thesis=thesis,
                    sleeve="premium",
                    instruments=list(dna.symbols),
                    entry_logic_ref=f"strategies.pick_entry+dna:{dna.ensure_id()}",
                    exit_logic_ref=f"strategies.check_exits+dna:{dna.ensure_id()}",
                    status="candidate",
                    evidence_links=evidence,
                    notes=f"source=evolve_tick; structure={dna.structure}; never_auto_live=true",
                    dna=dna.to_dict(),
                )
                created.append(h.id)
                by_id[h.id] = {"id": h.id}
            except ValueError:
                # race/dup
                updated.append(hid)

    # persist updates for existing
    if updated:
        store = reg.load()
        idset = set(updated)
        # re-apply from results for those ids
        res_by_hid = {hyp_id_for_dna(r.dna): r for r in results}
        for raw in store["hypotheses"]:
            if raw.get("id") not in idset:
                continue
            r = res_by_hid.get(raw["id"])
            if not r:
                continue
            raw["dna"] = r.dna.to_dict()
            raw["thesis"] = r.dna.thesis_text()
            raw["updated"] = _now()
        reg.save(store)

    return created, updated


def run_evolve_tick(
    *,
    apply: bool = False,
    top_symbols: int = 8,
    mutants_per_seed: int = 2,
    structures: Optional[Sequence[str]] = None,
    seed: Optional[int] = None,
    period: str = "2y",
    sleeve_usd: float = 3000.0,
    max_population: int = 48,
    max_create: int = 8,
    ship_only: bool = False,
    research_db: Optional[Path | str] = None,
    registry_path: Optional[Path | str] = None,
) -> EvolveReport:
    ts = _now()
    report = EvolveReport(
        ts=ts,
        applied=apply,
        dry_run=not apply,
        symbols=[],
        n_population=0,
        audit_path=str(_EVOLVE_AUDIT),
    )

    rows = top_research_symbols(
        top_n=top_symbols,
        sleeve_usd=sleeve_usd,
        db_path=research_db,
    )
    if not rows:
        # Fallback free search: sample multi-name universe — never TSLA/TSLL-only.
        try:
            from trader_platform.research.universe import load_universe

            uni = load_universe()
        except Exception:  # noqa: BLE001
            uni = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMZN", "META", "AMD", "SMCI", "PLTR", "COIN", "TSLA", "TSLL"]
        rng = random.Random(seed)
        pick_n = max(top_symbols, 6)
        if len(uni) > pick_n:
            # Prefer diversified sample; always keep a couple indexes if present.
            anchors = [s for s in ("SPY", "QQQ", "IWM") if s in uni]
            rest = [s for s in uni if s not in anchors]
            rng.shuffle(rest)
            chosen = (anchors + rest)[:pick_n]
        else:
            chosen = list(uni)
        families = [
            "short_put_cautious",
            "short_strangle_candidate",
            "defined_risk_put_spread",
            "premium_rich_short_dte",
            "wheel_assignment",
        ]
        rows = [
            {"symbol": sym, "strategy_family": families[i % len(families)], "composite": 0}
            for i, sym in enumerate(chosen)
        ]
        report.errors.append("no research.db scores; using multi-symbol universe fallback")

    report.symbols = [str(r["symbol"]) for r in rows]
    pop = build_population(
        rows,
        structures=structures,
        mutants_per_seed=mutants_per_seed,
        seed=seed,
    )
    if len(pop) > max_population:
        rng = random.Random(seed)
        pop = rng.sample(pop, max_population)
    report.n_population = len(pop)

    for dna in pop:
        try:
            v = sim_dna(dna, period=period, dump_dir=_BT_DUMP)
            report.results.append(v)
            _persist_sim(v, ts)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{dna.ensure_id()}: {exc}")

    report.results.sort(
        key=lambda r: (VERDICT_RANK.get(r.verdict, 0), _finite(r.score, default=-1e9)),
        reverse=True,
    )

    if apply and report.results:
        reg = HypothesisRegistry(registry_path)
        created, updated = apply_results(
            report.results,
            registry=reg,
            max_create=max_create,
            ship_only=ship_only,
        )
        report.created_hyps = created
        report.updated_hyps = updated

    # audit
    _CACHE.mkdir(parents=True, exist_ok=True)
    with _EVOLVE_AUDIT.open("a") as f:
        f.write(json.dumps(report.to_dict(), default=str) + "\n")

    return report


def format_report(report: EvolveReport) -> str:
    lines = [
        f"evolve_tick ts={report.ts} apply={report.applied} pop={report.n_population} "
        f"symbols={report.symbols}",
        f"audit: {report.audit_path}",
        "",
        f"{'verdict':<16} {'score':>10} {'trades':>6}  structure/symbol  reason",
        "-" * 90,
    ]
    for r in report.results[:20]:
        sym = (r.dna.symbols or ["?"])[0]
        sc = _finite(r.score, default=-1e9)
        lines.append(
            f"{r.verdict:<16} {sc:10.2f} {r.n_trades:6d}  "
            f"{r.dna.structure}/{sym}  {r.reason[:40]}"
        )
    if report.created_hyps:
        lines.append("")
        lines.append("created: " + ", ".join(report.created_hyps))
    if report.updated_hyps:
        lines.append("updated: " + ", ".join(report.updated_hyps))
    if report.errors:
        lines.append("errors: " + "; ".join(report.errors[:5]))
    lines.append("")
    lines.append(
        "hard_rules: never_auto_live=true never_edit_strategies_py=true "
        f"structures={len(STRUCTURE_CATALOG)} dna_search=true"
    )
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Evolve tick: free DNA search + sim (paper only)")
    p.add_argument("--once", action="store_true", help="run one evolve pass (default)")
    p.add_argument("--apply", action="store_true", help="write SHIP/strong DNA hyps as candidates")
    p.add_argument("--top-symbols", type=int, default=8)
    p.add_argument("--mutants", type=int, default=2, help="mutants per structure seed")
    p.add_argument("--max-population", type=int, default=48)
    p.add_argument("--max-create", type=int, default=8)
    p.add_argument("--sleeve-usd", type=float, default=3000.0,
                   help="Agentic sleeve capital for capital-fit ranking (default 3000)")
    p.add_argument("--period", default="2y")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--ship-only", action="store_true")
    p.add_argument(
        "--structures",
        nargs="*",
        default=None,
        help=f"subset of {sorted(STRUCTURE_CATALOG)}",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    report = run_evolve_tick(
        apply=args.apply,
        top_symbols=args.top_symbols,
        mutants_per_seed=args.mutants,
        structures=args.structures,
        seed=args.seed,
        period=args.period,
        sleeve_usd=args.sleeve_usd,
        max_population=args.max_population,
        max_create=args.max_create,
        ship_only=args.ship_only,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(format_report(report))
    return 0 if not report.errors else 0  # research soft-fail


if __name__ == "__main__":
    raise SystemExit(main())

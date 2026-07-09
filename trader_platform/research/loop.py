"""One research tick: score entire multi-symbol universe, capital-size, rank, persist."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from trader_platform.research.capital import (
    attach_capital_to_score,
    filter_by_sleeve,
    format_capital_table,
)
from trader_platform.research.scorer import SymbolScore, score_symbol
from trader_platform.research.store import (
    default_db_path,
    default_reports_dir,
    format_report_table,
    load_opportunities,
    load_run_meta,
    load_run_scores,
    latest_run_id,
    save_run,
    write_dated_report,
)
from trader_platform.research.universe import default_universe_path, load_universe, load_universe_meta


@dataclass
class ResearchReport:
    run_id: int
    symbols: list[str]
    scores: list[SymbolScore]
    top_composite: list[SymbolScore]
    top_vol: list[SymbolScore]
    top_premium: list[SymbolScore]
    top_alpha: list[SymbolScore]
    db_path: str
    period: str
    errors: list[SymbolScore] = field(default_factory=list)
    universe_path: str = ""
    sleeve_usd: Optional[float] = None
    report_path: str = ""
    top_n_used: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "n_symbols": len(self.symbols),
            "n_scored": len(self.scores) - len(self.errors),
            "n_errors": len(self.errors),
            "symbols": self.symbols,
            "period": self.period,
            "db_path": self.db_path,
            "universe_path": self.universe_path,
            "sleeve_usd": self.sleeve_usd,
            "report_path": self.report_path,
            "top_composite": [s.to_dict() for s in self.top_composite],
            "top_vol": [s.to_dict() for s in self.top_vol],
            "top_premium": [s.to_dict() for s in self.top_premium],
            "top_alpha": [s.to_dict() for s in self.top_alpha],
            "errors": [{"symbol": e.symbol, "error": e.error} for e in self.errors],
        }


def run_research_tick(
    *,
    universe_path: Optional[Path | str] = None,
    symbols: Optional[Sequence[str]] = None,
    only: Optional[Sequence[str]] = None,
    period: str = "2y",
    use_cache: bool = True,
    top_n: int = 10,
    db_path: Optional[Path | str] = None,
    max_workers: int = 6,
    notes: str = "",
    score_fn: Optional[Callable[..., SymbolScore]] = None,
    persist: bool = True,
    sleeve_usd: Optional[float] = None,
    sleeve_mode: str = "either",
    write_report: bool = False,
    reports_dir: Optional[Path | str] = None,
) -> ResearchReport:
    """Rank ALL universe symbols by composite + component scores. Paper research only.

    sleeve_usd: optional pilot capital filter for *top-N ranking* (full universe still scored).
    """
    uni_path = Path(universe_path) if universe_path else default_universe_path()
    if symbols is not None:
        syms = [s.upper() for s in symbols]
        if len(syms) < 2:
            raise ValueError("research tick requires ≥2 symbols (multi-symbol mandatory)")
    else:
        syms = load_universe(uni_path, only=only)

    # Guard: research must not collapse to TSLA/TSLL-only by default path
    if set(syms) <= {"TSLA", "TSLL"} and only is None and symbols is None:
        raise ValueError(
            "Research universe collapsed to TSLA/TSLL only — fix universe.yaml. "
            "Live allowlist is separate; research must stay multi-name."
        )

    scorer = score_fn or score_symbol
    scores: list[SymbolScore] = []

    def _one(sym: str) -> SymbolScore:
        sc = scorer(sym, period=period, use_cache=use_cache)
        if not sc.error and getattr(sc, "capital_fit", None) in (None, "", "unknown") and sc.spot > 0:
            attach_capital_to_score(sc)
        return sc

    if max_workers <= 1 or len(syms) == 1:
        scores = [_one(s) for s in syms]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_one, s): s for s in syms}
            by_sym: dict[str, SymbolScore] = {}
            for fut in as_completed(futs):
                sc = fut.result()
                by_sym[sc.symbol] = sc
            scores = [by_sym[s] for s in syms if s in by_sym]
            for s, sc in by_sym.items():
                if sc not in scores:
                    scores.append(sc)

    ok = [s for s in scores if not s.error]
    errs = [s for s in scores if s.error]

    # Full-universe ranking base; optional sleeve filter for pilot top-N only
    rank_pool = ok
    if sleeve_usd is not None and float(sleeve_usd) > 0:
        rank_pool = filter_by_sleeve(ok, float(sleeve_usd), mode=sleeve_mode)
        # If filter empties (all mega-cap CSPs too big), fall back to long-debit fit
        if not rank_pool and sleeve_mode == "either":
            rank_pool = filter_by_sleeve(ok, float(sleeve_usd), mode="long")
        if not rank_pool:
            rank_pool = ok  # never return empty tops silently — annotate in meta

    top_c = sorted(rank_pool, key=lambda s: s.composite, reverse=True)[:top_n]
    top_v = sorted(rank_pool, key=lambda s: s.vol_score, reverse=True)[:top_n]
    top_p = sorted(rank_pool, key=lambda s: s.premium_score, reverse=True)[:top_n]
    top_a = sorted(rank_pool, key=lambda s: s.alpha_score, reverse=True)[:top_n]

    db = Path(db_path) if db_path else default_db_path()
    run_id = 0
    if persist:
        meta = {
            "universe_path": str(uni_path),
            "symbols": syms,
            "top_symbols": [s.symbol for s in top_c],
            "sleeve_usd": sleeve_usd,
            "sleeve_mode": sleeve_mode,
            "n_rank_pool": len(rank_pool),
        }
        run_id = save_run(
            scores,
            top_n=top_n,
            period=period,
            notes=notes or "research_tick",
            meta=meta,
            db_path=db,
        )

    report = ResearchReport(
        run_id=run_id,
        symbols=syms,
        scores=scores,
        top_composite=top_c,
        top_vol=top_v,
        top_premium=top_p,
        top_alpha=top_a,
        db_path=str(db),
        period=period,
        errors=errs,
        universe_path=str(uni_path),
        sleeve_usd=sleeve_usd,
        top_n_used=top_n,
    )

    if write_report:
        path = write_dated_report(report, reports_dir=reports_dir or default_reports_dir())
        report.report_path = str(path)

    return report


def report_from_db(
    run_id: Optional[int] = None,
    *,
    top_n: int = 10,
    db_path: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Load latest (or given) run and format component tables."""
    db = Path(db_path) if db_path else default_db_path()
    rid = run_id if run_id is not None else latest_run_id(db)
    if rid is None:
        return {"error": "no research runs in db", "db_path": str(db)}
    meta = load_run_meta(rid, db)
    scores = load_run_scores(rid, db)
    opps = load_opportunities(rid, db)
    return {
        "run_id": rid,
        "meta": meta,
        "n_scores": len(scores),
        "opportunities": opps,
        "table_composite": format_report_table(scores, top_n=top_n, by="composite"),
        "table_vol": format_report_table(scores, top_n=top_n, by="vol"),
        "table_premium": format_report_table(scores, top_n=top_n, by="premium"),
        "table_alpha": format_report_table(scores, top_n=top_n, by="alpha"),
        "table_capital": format_capital_table(
            # lightweight adapters for capital table from dict rows
            [_score_proxy(r) for r in scores if not r.get("error")],
            top_n=top_n,
        ),
        "db_path": str(db),
        "universe_meta": load_universe_meta(),
    }


class _ScoreProxy:
    """Minimal attribute object for format_capital_table from DB rows."""

    def __init__(self, d: dict[str, Any]):
        self.__dict__.update(d)
        if not getattr(self, "error", None):
            self.error = None


def _score_proxy(d: dict[str, Any]) -> _ScoreProxy:
    return _ScoreProxy(d)

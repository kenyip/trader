"""Bootstrap shortlist tooling: re-prove candidates, diversify, write honest report.

Does not hard-code "winning" strategies. Prove results select the pack.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from trader_platform.research.identity import coarse_dna_key, diversify_rows
from trader_platform.research.living_registry import (
    DEFAULT_REGISTRY_PATH,
    LivingRegistry,
    load_living_registry,
)
from trader_platform.research.opportunity import load_thesis, list_thesis_paths
from trader_platform.research.progress_dashboard import collect_progress
from trader_platform.research.strategy_spec import (
    StrategySpec,
    load_strategy_spec,
    strategy_spec_from_mapping,
)

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_BOOTSTRAP_CONFIG = _REPO / "configs" / "bootstrap_strategies.json"
DEFAULT_BOOTSTRAP_REPORT = _REPO / "reports" / "bootstrap" / "LATEST.json"
DEFAULT_QUALITY_BARS = _REPO / "configs" / "quality_bars.json"
DEFAULT_MULTI_SYMBOL_REPORT = _REPO / "reports" / "bootstrap" / "MULTI_SYMBOL_REPROVE.json"

# Default book for multi-symbol DNA stress (liquid / capital-fit core+growth)
DEFAULT_MULTI_SYMBOL_BOOK = ("BAC", "KO", "IWM", "AMZN", "AAPL", "QQQ", "INTC")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_quality_bars(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_QUALITY_BARS
    if not p.exists():
        return {
            "bootstrap": {
                "min_trades_per_passing_axis": 12,
                "min_symbols_with_f2": 2,
            }
        }
    raw = json.loads(p.read_text(encoding="utf-8"))
    return dict(raw) if isinstance(raw, Mapping) else {}

@dataclass
class BootstrapCandidate:
    thesis_id: str = ""
    candidate_id: str = ""
    family_id: str = ""
    symbols: list[str] = field(default_factory=list)
    seat_id: str = ""
    spec_path: str = ""
    source: str = ""  # thesis_file | living_f2 | seed_spec
    coarse_dna_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_bootstrap_config(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_BOOTSTRAP_CONFIG
    if not p.exists():
        return {
            "version": 1,
            "description": "empty bootstrap config",
            "candidates": [],
            "selection": {
                "top_n": 5,
                "diversify_symbols": True,
                "diversify_dna": True,
            },
        }
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("bootstrap config must be a JSON object")
    return dict(raw)


def save_bootstrap_config(cfg: Mapping[str, Any], path: str | Path | None = None) -> Path:
    p = Path(path) if path else DEFAULT_BOOTSTRAP_CONFIG
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(cfg), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def collect_bootstrap_candidates(
    *,
    registry_path: str | Path | None = None,
    include_theses: bool = True,
    include_f2: bool = True,
    max_f2: int = 40,
) -> list[BootstrapCandidate]:
    """Gather candidates for re-prove (not yet selected pack)."""
    out: list[BootstrapCandidate] = []
    if include_theses:
        for path in list_thesis_paths():
            try:
                thesis = load_thesis(path)
            except Exception:
                continue
            source_spec = thesis.source_spec_path or ""
            if source_spec and not Path(source_spec).is_absolute():
                sp = _REPO / source_spec
            else:
                sp = Path(source_spec) if source_spec else Path()
            mgmt = dict(thesis.management or {})
            # Prefer explicit thesis symbols; else inherit from linked StrategySpec seed.
            symbols = [str(s).upper() for s in (thesis.symbols or []) if str(s).strip()]
            if not symbols and sp.exists():
                try:
                    seed = load_strategy_spec(sp)
                    symbols = [str(s).upper() for s in seed.symbols]
                    if not mgmt:
                        mgmt = dict(seed.management or {})
                except Exception:
                    symbols = []
            # Prefer liquid core names for bootstrap speed / capital fit.
            core_prefer = ["BAC", "KO", "IWM", "AAPL", "QQQ", "INTC", "XOM"]
            if symbols:
                ranked = [s for s in core_prefer if s in symbols] + [
                    s for s in symbols if s not in core_prefer
                ]
                symbols = ranked
            out.append(
                BootstrapCandidate(
                    thesis_id=thesis.thesis_id,
                    candidate_id=thesis.thesis_id,
                    family_id=thesis.family_id or thesis.thesis_id,
                    symbols=symbols,
                    seat_id=f"thesis:{thesis.thesis_id}",
                    spec_path=str(sp) if sp.exists() else str(path),
                    source="thesis_file",
                    coarse_dna_key=coarse_dna_key(
                        thesis_id=thesis.thesis_id,
                        family_id=thesis.family_id,
                        router_policy=thesis.router_policy,
                        management=mgmt,
                        evaluation_mode="regime_router",
                    ),
                )
            )
    if include_f2:
        reg = load_living_registry(registry_path or DEFAULT_REGISTRY_PATH)
        by_id = {s.seat_id: s for s in reg.seats}
        snap = collect_progress(registry_path=registry_path or DEFAULT_REGISTRY_PATH)
        for row in list(snap.f2_seats)[: max(0, int(max_f2))]:
            seat_id = str(row.get("seat_id") or "")
            seat = by_id.get(seat_id)
            mgmt: dict[str, Any] = {}
            evaluation_mode = ""
            structure = ""
            spec_path = getattr(seat, "spec_path", "") if seat else ""
            if spec_path and Path(spec_path).exists():
                try:
                    spec = load_strategy_spec(spec_path)
                    mgmt = dict(spec.management or {})
                    evaluation_mode = str(spec.evaluation_mode or "")
                    structure = str(spec.structure or "")
                except Exception:
                    pass
            out.append(
                BootstrapCandidate(
                    thesis_id=str(row.get("family_id") or "")[:80],
                    candidate_id=str(row.get("candidate_id") or ""),
                    family_id=str(row.get("family_id") or ""),
                    symbols=list(row.get("symbols") or []),
                    seat_id=seat_id,
                    spec_path=str(spec_path or ""),
                    source="living_f2",
                    coarse_dna_key=coarse_dna_key(
                        family_id=str(row.get("family_id") or ""),
                        candidate_id=str(row.get("candidate_id") or ""),
                        router_policy=str(row.get("router_policy") or ""),
                        structure=structure,
                        management=mgmt,
                        evaluation_mode=evaluation_mode,
                    ),
                )
            )
    return out


def select_shortlist(
    candidates: Sequence[BootstrapCandidate | Mapping[str, Any]],
    *,
    top_n: int = 5,
    diversify_symbols: bool = True,
    diversify_dna: bool = True,
) -> list[dict[str, Any]]:
    rows = [
        c.to_dict() if isinstance(c, BootstrapCandidate) else dict(c) for c in candidates
    ]
    return diversify_rows(
        rows,
        top_n=top_n,
        by_symbol=diversify_symbols,
        by_dna=diversify_dna,
        fill_remainder=False,
    )


def _spec_for_candidate(cand: Mapping[str, Any]) -> StrategySpec | None:
    path = str(cand.get("spec_path") or "")
    if path and Path(path).exists():
        try:
            return load_strategy_spec(path)
        except Exception:
            pass
    return None


def re_prove_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    run_holdout: bool = True,
    evaluate_fn: Any = None,
) -> dict[str, Any]:
    """Re-prove each candidate under dual-cost evaluate_proxy.

    ``evaluate_fn`` is injectable for unit tests (defaults to evaluate_proxy).
    Real-data prove is research outcome — failures are recorded, not forced green.
    """
    if evaluate_fn is None:
        from trader_platform.research.evaluate_proxy import evaluate_proxy

        evaluate_fn = evaluate_proxy

    results: list[dict[str, Any]] = []
    for cand in candidates:
        c = dict(cand)
        symbols = [str(s).upper() for s in (c.get("symbols") or []) if str(s).strip()]
        spec = _spec_for_candidate(c)
        if spec is None:
            results.append(
                {
                    **c,
                    "ok": False,
                    "decision": "NO_SPEC",
                    "reason": "spec_path missing or unloadable",
                }
            )
            continue
        if not symbols:
            symbols = list(spec.symbols)
        # Narrow to first symbol for bootstrap speed if many
        # Bootstrap proves a small symbol slice for wall-time; full multi-name
        # claims remain a discovery concern.
        prove_symbols = symbols[:2] if symbols else list(spec.symbols)[:1]
        raw = spec.to_dict()
        raw["symbols"] = prove_symbols
        try:
            narrowed = strategy_spec_from_mapping(raw)
            report = evaluate_fn(
                narrowed, run_holdout_on_train_pass=run_holdout
            )
            decision = str(report.get("decision") or "")
            n_hold = int(report.get("n_holdout_pass") or 0)
            n_train = int(report.get("n_train_pass") or 0)
            # F2 only on sealed dual-cost holdout advance — not train-only.
            is_f2 = decision == "STRATEGY_ADVANCED_F2"
            results.append(
                {
                    **c,
                    "ok": True,
                    "decision": decision,
                    "n_train_pass": n_train,
                    "n_holdout_pass": n_hold,
                    "f2": is_f2,
                    "symbols_proved": prove_symbols,
                    "option_mark_provenance": report.get(
                        "option_mark_provenance", "black_scholes_proxy"
                    ),
                    "l1_eligible": report.get("l1_eligible", False),
                    "control_mode": getattr(narrowed, "control_mode", ""),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    **c,
                    "ok": False,
                    "decision": "EVAL_ERROR",
                    "reason": str(exc),
                }
            )

    passed = [r for r in results if r.get("f2")]
    failed = [r for r in results if not r.get("f2")]
    # Final pack: diversify symbols + DNA among dual-cost F2 survivors only.
    shortlist = (
        select_shortlist(
            passed,
            top_n=5,
            diversify_symbols=True,
            diversify_dna=True,
        )
        if passed
        else []
    )
    payload = {
        "generated_at": _now(),
        "mode": "bootstrap_reprove",
        "option_mark_provenance": "black_scholes_proxy",
        "honesty": (
            "L0 Black-Scholes proxy only. Dual-cost F2 is research plumbing, "
            "not L1 observed edge or live authority."
        ),
        "n_candidates": len(results),
        "n_passed_f2": len(passed),
        "n_failed": len(failed),
        "shortlist": shortlist,
        "results": results,
        "trading_authority": False,
        "live_authority": False,
        "discovery_policy": "densify_winners_only_wave_A_default",
    }
    return payload


def multi_symbol_reprove(
    *,
    spec_path: str | Path,
    symbols: Sequence[str],
    evaluate_fn: Any = None,
    run_holdout: bool = True,
    quality_bars: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-prove one DNA across many symbols — kill single-name luck.

    Returns per-symbol dual-cost decisions plus quality_pass when enough
    symbols independently clear F2 under quality bars.
    """
    if evaluate_fn is None:
        from trader_platform.research.evaluate_proxy import evaluate_proxy

        evaluate_fn = evaluate_proxy

    bars = dict((quality_bars or load_quality_bars()).get("bootstrap") or {})
    min_syms = int(bars.get("min_symbols_with_f2") or 2)
    min_trades = int(bars.get("min_trades_per_passing_axis") or 12)

    spec = load_strategy_spec(spec_path)
    per_symbol: list[dict[str, Any]] = []
    f2_symbols: list[str] = []

    for sym in [str(s).upper() for s in symbols if str(s).strip()]:
        raw = spec.to_dict()
        raw["symbols"] = [sym]
        try:
            narrowed = strategy_spec_from_mapping(raw)
            report = evaluate_fn(narrowed, run_holdout_on_train_pass=run_holdout)
            decision = str(report.get("decision") or "")
            is_f2 = decision == "STRATEGY_ADVANCED_F2"
            # Extract worst-axis holdout n_trades when present
            n_trades_hold = None
            for hrow in report.get("holdout_rows") or []:
                if hrow.get("symbol") != sym:
                    continue
                axes = hrow.get("holdout") or {}
                ns = [
                    int((axes.get(a) or {}).get("n_trades") or 0)
                    for a in ("slip_5pct", "fixed_0p01")
                ]
                if ns:
                    n_trades_hold = min(ns)
            thick = n_trades_hold is not None and n_trades_hold >= min_trades
            row = {
                "symbol": sym,
                "decision": decision,
                "f2": is_f2,
                "n_train_pass": report.get("n_train_pass"),
                "n_holdout_pass": report.get("n_holdout_pass"),
                "n_trades_holdout_worst_axis": n_trades_hold,
                "thick_enough": thick,
            }
            if is_f2:
                f2_symbols.append(sym)
            per_symbol.append(row)
        except Exception as exc:  # noqa: BLE001
            per_symbol.append(
                {
                    "symbol": sym,
                    "decision": "EVAL_ERROR",
                    "f2": False,
                    "reason": str(exc),
                }
            )

    multi_f2 = len(f2_symbols) >= min_syms
    thick_f2 = [
        r["symbol"]
        for r in per_symbol
        if r.get("f2") and r.get("thick_enough")
    ]
    quality_pass = multi_f2 and len(thick_f2) >= min_syms

    return {
        "generated_at": _now(),
        "mode": "multi_symbol_reprove",
        "candidate_id": spec.candidate_id,
        "family_id": spec.family_id,
        "spec_path": str(spec_path),
        "symbols_tested": [str(s).upper() for s in symbols],
        "per_symbol": per_symbol,
        "f2_symbols": f2_symbols,
        "n_f2_symbols": len(f2_symbols),
        "thick_f2_symbols": thick_f2,
        "min_symbols_with_f2": min_syms,
        "min_trades_per_passing_axis": min_trades,
        "multi_symbol_f2": multi_f2,
        "quality_pass": quality_pass,
        "option_mark_provenance": "black_scholes_proxy",
        "trading_authority": False,
        "live_authority": False,
        "honesty": (
            "Per-symbol dual-cost re-prove. quality_pass requires ≥min_symbols "
            "independent F2 with holdout n_trades ≥ bar on worst cost axis."
        ),
    }


DEFAULT_QUALITY_SHORTLIST = _REPO / "reports" / "bootstrap" / "QUALITY_SHORTLIST.json"
DEFAULT_SEED_SPECS = _REPO / "configs" / "strategy_specs"


def symbols_from_quality_shortlist(
    path: str | Path | None = None,
    *,
    top_n: int = 12,
) -> list[str]:
    """Extract leader symbols from QUALITY_SHORTLIST (AAL/BAC/… research leaders)."""
    p = Path(path) if path else DEFAULT_QUALITY_SHORTLIST
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[str] = []
    for row in list(data.get("shortlist") or [])[: max(1, int(top_n))]:
        sym = str(row.get("symbol") or "").strip().upper()
        if sym and sym not in out:
            out.append(sym)
    return out


def load_dna_items_for_multi_symbol(
    *,
    shortlist: Sequence[Mapping[str, Any]] | None = None,
    include_seed_specs: bool = False,
    seed_specs_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Bootstrap densify DNA (+ optional frozen seed StrategySpecs) for multi-symbol re-prove."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    if shortlist is None:
        if DEFAULT_BOOTSTRAP_REPORT.is_file():
            boot = json.loads(DEFAULT_BOOTSTRAP_REPORT.read_text(encoding="utf-8"))
            shortlist = list(boot.get("shortlist") or [])
        else:
            shortlist = []

    for item in shortlist:
        sp = str(item.get("spec_path") or "")
        cid = str(item.get("candidate_id") or sp)
        if cid in seen:
            continue
        seen.add(cid)
        items.append(dict(item))

    if include_seed_specs:
        sdir = Path(seed_specs_dir) if seed_specs_dir else DEFAULT_SEED_SPECS
        if sdir.is_dir():
            for path in sorted(sdir.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                cid = str(raw.get("candidate_id") or path.stem)
                if cid in seen:
                    continue
                seen.add(cid)
                items.append(
                    {
                        "candidate_id": cid,
                        "spec_path": str(path.resolve()),
                        "symbols": list(raw.get("symbols") or []),
                        "symbols_proved": [],
                        "source": "seed_spec",
                    }
                )
    return items


def run_multi_symbol_pack(
    *,
    shortlist: Sequence[Mapping[str, Any]] | None = None,
    symbols: Sequence[str] | None = None,
    report_path: str | Path | None = None,
    evaluate_fn: Any = None,
    include_seed_specs: bool = False,
    from_quality_shortlist: bool = False,
    quality_shortlist_path: str | Path | None = None,
    quality_top_n: int = 12,
) -> dict[str, Any]:
    """Multi-symbol re-prove densify DNA (+ optional seeds) across a symbol book.

    When ``from_quality_shortlist`` is set, leader symbols from QUALITY_SHORTLIST
    (e.g. AAL/BAC densify research leaders) are prepended to the multi-symbol book
    so single-name luck is stress-tested on the names the continuum actually ranks.
    """
    items = load_dna_items_for_multi_symbol(
        shortlist=shortlist,
        include_seed_specs=include_seed_specs,
    )
    book = [str(s).upper() for s in (symbols or DEFAULT_MULTI_SYMBOL_BOOK) if str(s).strip()]
    quality_syms: list[str] = []
    if from_quality_shortlist:
        quality_syms = symbols_from_quality_shortlist(
            quality_shortlist_path, top_n=quality_top_n
        )
        book = list(dict.fromkeys(quality_syms + book))

    rows: list[dict[str, Any]] = []
    for item in items:
        sp = item.get("spec_path")
        if not sp or not Path(str(sp)).exists():
            rows.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "ok": False,
                    "reason": "missing_spec",
                }
            )
            continue
        # Include original symbol first
        orig = [
            str(s).upper()
            for s in (item.get("symbols_proved") or item.get("symbols") or [])
            if str(s).strip()
        ]
        test_syms = list(dict.fromkeys(orig + book))
        rows.append(
            multi_symbol_reprove(
                spec_path=sp,
                symbols=test_syms,
                evaluate_fn=evaluate_fn,
            )
        )
    payload = {
        "generated_at": _now(),
        "mode": "multi_symbol_pack",
        "n_dna": len(rows),
        "n_quality_pass": sum(1 for r in rows if r.get("quality_pass")),
        "n_multi_f2": sum(1 for r in rows if r.get("multi_symbol_f2")),
        "book_symbols": book,
        "quality_shortlist_symbols": quality_syms,
        "from_quality_shortlist": bool(from_quality_shortlist),
        "include_seed_specs": bool(include_seed_specs),
        "results": rows,
        "trading_authority": False,
        "live_authority": False,
        "honesty": (
            "Multi-symbol densify DNA stress — single-name F2 alone is not pack-grade. "
            "Quality-shortlist symbols expand the book so research leaders (AAL/BAC/…) "
            "are included in the re-prove, not only default core names."
        ),
    }
    path = write_bootstrap_report(payload, report_path or DEFAULT_MULTI_SYMBOL_REPORT)
    payload["report_path"] = str(path)
    return payload


def write_bootstrap_report(
    report: Mapping[str, Any],
    path: str | Path | None = None,
) -> Path:
    p = Path(path) if path else DEFAULT_BOOTSTRAP_REPORT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def run_bootstrap_prove(
    *,
    config_path: str | Path | None = None,
    registry_path: str | Path | None = None,
    report_path: str | Path | None = None,
    max_f2: int = 20,
    run_holdout: bool = True,
    evaluate_fn: Any = None,
    dry_candidates_only: bool = False,
) -> dict[str, Any]:
    """CLI entry: collect → optional re-prove → write report."""
    cfg = load_bootstrap_config(config_path)
    selection = dict(cfg.get("selection") or {})
    top_n = int(selection.get("top_n") or 5)

    configured = list(cfg.get("candidates") or [])
    if configured:
        candidates = [dict(c) for c in configured]
    else:
        candidates = [
            c.to_dict()
            for c in collect_bootstrap_candidates(
                registry_path=registry_path,
                include_theses=True,
                include_f2=True,
                max_f2=max_f2,
            )
        ]
        # Pre-prove pool: diversify by DNA so multi-thesis same-symbol seeds
        # both get re-proved. Symbol diversify applies to the post-prove pack.
        candidates = select_shortlist(
            candidates,
            top_n=max(top_n * 3, 10),
            diversify_symbols=False,
            diversify_dna=bool(selection.get("diversify_dna", True)),
        )

    if dry_candidates_only:
        report = {
            "generated_at": _now(),
            "mode": "bootstrap_candidates_only",
            "n_candidates": len(candidates),
            "candidates": candidates,
            "honesty": "No prove run — candidate selection only.",
            "trading_authority": False,
            "live_authority": False,
        }
        write_bootstrap_report(report, report_path)
        return report

    report = re_prove_candidates(
        candidates,
        run_holdout=run_holdout,
        evaluate_fn=evaluate_fn,
    )
    report["config_path"] = str(config_path or DEFAULT_BOOTSTRAP_CONFIG)
    path = write_bootstrap_report(report, report_path)
    report["report_path"] = str(path)
    return report

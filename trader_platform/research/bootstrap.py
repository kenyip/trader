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


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
            out.append(
                BootstrapCandidate(
                    thesis_id=thesis.thesis_id,
                    candidate_id=thesis.thesis_id,
                    family_id=thesis.family_id or thesis.thesis_id,
                    symbols=list(thesis.symbols) if thesis.symbols else [],
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
        snap = collect_progress(registry_path=registry_path or DEFAULT_REGISTRY_PATH)
        for row in list(snap.f2_seats)[: max(0, int(max_f2))]:
            seat_id = str(row.get("seat_id") or "")
            reg = load_living_registry(registry_path)
            seat = next((s for s in reg.seats if s.seat_id == seat_id), None)
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
        prove_symbols = symbols[:3] if symbols else list(spec.symbols)[:1]
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
            results.append(
                {
                    **c,
                    "ok": True,
                    "decision": decision,
                    "n_train_pass": n_train,
                    "n_holdout_pass": n_hold,
                    "f2": decision == "STRATEGY_ADVANCED_F2" or n_hold > 0,
                    "symbols_proved": prove_symbols,
                    "option_mark_provenance": report.get(
                        "option_mark_provenance", "black_scholes_proxy"
                    ),
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
    shortlist = select_shortlist(passed, top_n=5) if passed else []
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
    }
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
        candidates = select_shortlist(
            candidates,
            top_n=max(top_n * 3, 10),
            diversify_symbols=bool(selection.get("diversify_symbols", True)),
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

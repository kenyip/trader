"""Tight simulation discovery loop (Desk B).

Separates **strategy search/proof** (fast, sim-only, progress-gated) from
**opportunity waiting** (patient market watch).

Forward progress means at least one of:
  - new F2 living seat
  - new F1 train survivor
  - new quarantined/evaluated family not seen before
  - novel mutant evaluation (new candidate_id)

No live trading. No waiting on RTH for discovery.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from trader_platform.research.evolve_strategy_spec import (
    DEFAULT_MUTANTS,
    MutantPlan,
    apply_mutant,
    evolve_from_seed,
)
from trader_platform.research.evaluate_proxy import evaluate_proxy
from trader_platform.research.living_registry import (
    DEFAULT_REGISTRY_PATH,
    load_living_registry,
    save_living_registry,
    summary_lines,
    ingest_evaluate_report,
)
from trader_platform.research.strategy_spec import (
    load_strategy_spec,
    save_strategy_spec,
    strategy_spec_from_mapping,
)

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = _REPO / "configs" / "strategy_specs"
DEFAULT_OUT = _REPO / ".cache" / "platform" / "spine" / "discovery"
DEFAULT_STATE = _REPO / ".cache" / "platform" / "spine" / "discovery_state.json"

# Broader mutant waves rotated by generation — still bounded, not free optimizer.
WAVE_MUTANTS: tuple[tuple[MutantPlan, ...], ...] = (
    DEFAULT_MUTANTS,
    (
        MutantPlan(
            "iv40_dte21",
            {"long_dte": 21, "dte_stop": 7, "iv_rank_min": 40.0, "profit_target": 0.50},
            router_policy="pcs_non_bear",
            notes="higher IV rank gate",
        ),
        MutantPlan(
            "iv25_dte30",
            {"long_dte": 30, "dte_stop": 10, "iv_rank_min": 25.0, "profit_target": 0.50},
            router_policy="pcs_non_bear",
            notes="mid IV + 30d",
        ),
        MutantPlan(
            "bull_only_21",
            {"long_dte": 21, "dte_stop": 7, "profit_target": 0.50, "min_credit_pct": 0.12},
            router_policy="pcs_bull_only",
            notes="bullish-only PCS",
        ),
        MutantPlan(
            "router_dte30_iv20",
            {"long_dte": 30, "dte_stop": 10, "iv_rank_min": 20.0, "profit_target": 0.55},
            router_policy="router",
            notes="full router mid DTE",
        ),
    ),
    (
        MutantPlan(
            "dte14_pt50",
            {"long_dte": 14, "dte_stop": 5, "profit_target": 0.50, "long_target_delta": 0.16},
            router_policy="pcs_non_bear",
        ),
        MutantPlan(
            "dte21_delta14",
            {"long_dte": 21, "dte_stop": 7, "long_target_delta": 0.14, "min_credit_pct": 0.12},
            router_policy="pcs_non_bear",
        ),
        MutantPlan(
            "dte45_pt40",
            {"long_dte": 45, "dte_stop": 14, "profit_target": 0.40},
            router_policy="pcs_non_bear",
            notes="earlier profit take",
        ),
        MutantPlan(
            "router_dte21_pt50",
            {"long_dte": 21, "dte_stop": 7, "profit_target": 0.50},
            router_policy="router",
        ),
    ),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def list_seed_specs(spec_dir: str | Path | None = None) -> list[Path]:
    d = Path(spec_dir) if spec_dir else DEFAULT_SPEC_DIR
    if not d.is_dir():
        return []
    return sorted(d.glob("*.json"))


def known_ids(registry_path: str | Path | None = None) -> set[str]:
    reg = load_living_registry(registry_path)
    ids: set[str] = set()
    for seat in reg.seats:
        ids.add(seat.candidate_id)
        ids.add(seat.family_id)
        ids.add(seat.seat_id)
    return ids


def _is_novel(candidate_id: str, family_id: str, known: set[str]) -> bool:
    return candidate_id not in known and family_id not in known


DEFAULT_GRID_PATH = _REPO / "configs" / "discovery_grid.json"


def load_grid_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load expandable grid axes from JSON (fallback to built-in defaults)."""
    p = Path(path) if path else DEFAULT_GRID_PATH
    defaults = {
        "dtes": [14, 21, 30, 45],
        "profit_targets": [0.40, 0.50, 0.60],
        "deltas": [0.14, 0.18, 0.22],
        "iv_rank_mins": [0.0, 20.0, 30.0, 40.0],
        "policies": ["pcs_non_bear", "pcs_bull_only", "router"],
        "min_credit_pcts": [0.08, 0.12],
        # Optional axes: empty list means "don't override seed default"
        "spread_widths": [],
    }
    if not p.exists():
        return defaults
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return defaults
        out = dict(defaults)
        for key in defaults:
            if key not in raw:
                continue
            if isinstance(raw[key], list):
                # Allow empty list for optional axes (e.g. no width sweep)
                out[key] = list(raw[key])
        return out
    except Exception:
        return defaults


def _combinatorial_mutants(grid_path: str | Path | None = None) -> list[MutantPlan]:
    """Dense deterministic grid for continuous discovery (finite; expand via discovery_grid.json)."""
    cfg = load_grid_config(grid_path)
    plans: list[MutantPlan] = []
    dtes = [int(x) for x in cfg["dtes"]]
    pts = [float(x) for x in cfg["profit_targets"]]
    deltas = [float(x) for x in cfg["deltas"]]
    ivs = [float(x) for x in cfg["iv_rank_mins"]]
    policies = [str(x) for x in cfg["policies"]]
    credits = [float(x) for x in cfg["min_credit_pcts"]]
    widths_raw = cfg.get("spread_widths") or []
    widths: list[float | None] = [float(x) for x in widths_raw] if widths_raw else [None]
    for dte in dtes:
        for pt in pts:
            for delta in deltas:
                for iv in ivs:
                    for pol in policies:
                        for cred in credits:
                            for width in widths:
                                stop = max(3, int(dte) // 3)
                                w_tag = f"_w{int(width)}" if width is not None else ""
                                suffix = (
                                    f"g_d{int(dte)}_pt{int(pt * 100)}_dl{int(delta * 100)}"
                                    f"_iv{int(iv)}_c{int(cred * 100)}{w_tag}_{pol[:6]}"
                                )
                                patch: dict[str, Any] = {
                                    "long_dte": int(dte),
                                    "dte_stop": stop,
                                    "profit_target": float(pt),
                                    "long_target_delta": float(delta),
                                    "iv_rank_min": float(iv),
                                    "min_credit_pct": float(cred),
                                }
                                if width is not None:
                                    patch["spread_width"] = float(width)
                                plans.append(
                                    MutantPlan(
                                        suffix=suffix[:80],
                                        management_patch=patch,
                                        router_policy=str(pol),
                                        notes="grid",
                                    )
                                )
    return plans


# Full finite grid cached once (invalidate by process restart after editing JSON)
_GRID_MUTANTS: list[MutantPlan] | None = None
_GRID_SOURCE: str | None = None


def all_grid_mutants(grid_path: str | Path | None = None) -> list[MutantPlan]:
    global _GRID_MUTANTS, _GRID_SOURCE
    source = str(Path(grid_path) if grid_path else DEFAULT_GRID_PATH)
    if _GRID_MUTANTS is None or _GRID_SOURCE != source:
        curated: list[MutantPlan] = []
        for wave in WAVE_MUTANTS:
            curated.extend(wave)
        _GRID_MUTANTS = curated + _combinatorial_mutants(grid_path)
        _GRID_SOURCE = source
    return _GRID_MUTANTS


def generation_mutants(gen_index: int, max_mutants: int) -> list[MutantPlan]:
    """Slice the finite search space by generation for tight continuous runs."""
    grid = all_grid_mutants()
    n = max(1, int(max_mutants))
    start = (gen_index * n) % len(grid)
    out: list[MutantPlan] = []
    for i in range(n):
        out.append(grid[(start + i) % len(grid)])
    return out


def default_workers(requested: int | None = None) -> int:
    """CPU-bound eval pool size (use almost all cores by default)."""
    cpu = os.cpu_count() or 2
    if requested is not None and int(requested) > 0:
        return max(1, min(int(requested), cpu))
    # Leave one core free for UI/OS when possible
    return max(1, cpu - 1 if cpu > 2 else cpu)


def _evaluate_one_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Worker entrypoint: evaluate one mutant (process-safe; no registry writes)."""
    # Local imports keep spawn-on-macOS workers light and picklable.
    from trader_platform.research.evaluate_proxy import evaluate_proxy as _eval
    from trader_platform.research.strategy_spec import (
        save_strategy_spec as _save,
        strategy_spec_from_mapping as _from_map,
    )

    mutant = _from_map(payload["mutant"])
    gen_out = Path(payload["gen_out"])
    gen_out.mkdir(parents=True, exist_ok=True)
    spec_out = gen_out / f"{mutant.candidate_id}.json"
    _save(mutant, spec_out)
    report = _eval(mutant, run_holdout_on_train_pass=bool(payload["run_holdout"]))
    report_path = gen_out / f"{mutant.candidate_id}_eval.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "candidate_id": mutant.candidate_id,
        "family_id": mutant.family_id,
        "suffix": payload.get("suffix", ""),
        "decision": report.get("decision"),
        "n_train_pass": report.get("n_train_pass"),
        "n_holdout_pass": report.get("n_holdout_pass"),
        "spec_path": str(spec_out),
        "report_path": str(report_path),
        "report": report,
    }


def run_generation(
    *,
    seed_path: Path,
    gen_index: int,
    max_mutants: int,
    symbols: Optional[list[str]],
    out_dir: Path,
    registry_path: Path,
    run_holdout: bool,
    known: set[str],
    workers: int = 1,
) -> dict[str, Any]:
    """One discovery generation: evaluate novel mutants (optionally in parallel)."""
    seed = load_strategy_spec(seed_path)
    plans = generation_mutants(gen_index, max_mutants)
    stamp = _now_stamp()
    gen_out = out_dir / f"gen_{gen_index:04d}_{stamp}"
    gen_out.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    progress_bits: list[str] = []

    before = known_ids(registry_path)

    # Phase 1: build novel mutant payloads
    jobs: list[dict[str, Any]] = []
    for plan in plans:
        mutant = apply_mutant(seed, plan)
        if symbols:
            raw = mutant.to_dict()
            raw["symbols"] = [s.upper() for s in symbols]
            mutant = strategy_spec_from_mapping(raw)

        if not _is_novel(mutant.candidate_id, mutant.family_id, known | before):
            skipped.append(
                {
                    "candidate_id": mutant.candidate_id,
                    "reason": "already_evaluated_or_quarantined",
                }
            )
            continue
        # Reserve ids so parallel siblings in this gen don't duplicate work
        known.add(mutant.candidate_id)
        known.add(mutant.family_id)
        jobs.append(
            {
                "mutant": mutant.to_dict(),
                "gen_out": str(gen_out),
                "run_holdout": run_holdout,
                "suffix": plan.suffix,
            }
        )

    # Phase 2: evaluate (parallel CPU pool or sequential)
    worker_n = default_workers(workers)
    completed: list[dict[str, Any]] = []
    if not jobs:
        pass
    elif worker_n <= 1 or len(jobs) == 1:
        for job in jobs:
            completed.append(_evaluate_one_job(job))
    else:
        # Process pool: sims are CPU-bound (pandas/numpy). Registry writes stay serial.
        with ProcessPoolExecutor(max_workers=min(worker_n, len(jobs))) as pool:
            futures = [pool.submit(_evaluate_one_job, job) for job in jobs]
            for fut in as_completed(futures):
                completed.append(fut.result())

    # Phase 3: stable order + serial registry ingest (file-safe)
    completed.sort(key=lambda r: str(r.get("candidate_id") or ""))
    for item in completed:
        report = item.pop("report")
        ingest_evaluate_report(
            report,
            registry_path=registry_path,
            spec_path=str(item.get("spec_path") or ""),
            report_path=str(item.get("report_path") or ""),
        )
        row = {
            "candidate_id": item.get("candidate_id"),
            "family_id": item.get("family_id"),
            "suffix": item.get("suffix"),
            "decision": item.get("decision"),
            "n_train_pass": item.get("n_train_pass"),
            "n_holdout_pass": item.get("n_holdout_pass"),
            "spec_path": item.get("spec_path"),
            "report_path": item.get("report_path"),
        }
        results.append(row)
        if int(row.get("n_holdout_pass") or 0) > 0:
            progress_bits.append(f"F2:{row['candidate_id']}")
        elif int(row.get("n_train_pass") or 0) > 0:
            progress_bits.append(f"F1:{row['candidate_id']}")
        else:
            progress_bits.append(f"CLOSED:{row['family_id']}")

    after = known_ids(registry_path)
    new_ids = after - before
    # Progress: any evaluation of novel DNA, or new registry seats, or F1/F2
    progressed = bool(results) or bool(new_ids)
    any_f2 = any(int(r.get("n_holdout_pass") or 0) > 0 for r in results)
    any_f1 = any(int(r.get("n_train_pass") or 0) > 0 for r in results)

    summary = {
        "gen_index": gen_index,
        "seed": str(seed_path),
        "seed_candidate_id": seed.candidate_id,
        "n_evaluated": len(results),
        "n_skipped": len(skipped),
        "workers": worker_n if jobs else 0,
        "results": results,
        "skipped": skipped,
        "progressed": progressed,
        "progress_bits": progress_bits,
        "any_f1": any_f1,
        "any_f2": any_f2,
        "new_registry_ids": sorted(new_ids)[:50],
        "generated_at": _now_iso(),
        "out_dir": str(gen_out),
    }
    (gen_out / "generation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def run_discovery_loop(
    *,
    seeds: Optional[Sequence[str | Path]] = None,
    spec_dir: str | Path | None = None,
    max_generations: int = 20,
    max_mutants_per_gen: int = 3,
    max_seconds: float = 0.0,
    max_no_progress_generations: int = 3,
    symbols: Optional[list[str]] = None,
    run_holdout: bool = True,
    stop_on_f2: bool = True,
    registry_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    state_path: str | Path | None = None,
    workers: int | None = None,
) -> dict[str, Any]:
    """Run a tight multi-generation simulation discovery campaign.

    Stops when:
      - max_generations reached
      - max_seconds elapsed (if > 0)
      - max_no_progress_generations with no novel evaluations
      - F2 living seat found (if stop_on_f2)

    ``workers`` > 1 evaluates mutants in a process pool (CPU parallel).
    """
    started = time.monotonic()
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    registry_path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    state_path = Path(state_path) if state_path else DEFAULT_STATE
    worker_n = default_workers(workers)

    if seeds:
        seed_paths = [Path(s) for s in seeds]
    else:
        seed_paths = list_seed_specs(spec_dir)
    if not seed_paths:
        return {
            "ok": False,
            "error": "no seed StrategySpec files found",
            "trading_authority": False,
        }

    known = known_ids(registry_path)
    generations: list[dict[str, Any]] = []
    no_progress = 0
    stop_reason = "max_generations"
    total_f2 = 0
    total_f1 = 0
    total_eval = 0

    for gen in range(int(max_generations)):
        if max_seconds > 0 and (time.monotonic() - started) >= max_seconds:
            stop_reason = "max_seconds"
            break

        seed = seed_paths[gen % len(seed_paths)]
        gen_summary = run_generation(
            seed_path=seed,
            gen_index=gen,
            max_mutants=max_mutants_per_gen,
            symbols=symbols,
            out_dir=out,
            registry_path=registry_path,
            run_holdout=run_holdout,
            known=known,
            workers=worker_n,
        )
        generations.append(gen_summary)
        total_eval += int(gen_summary.get("n_evaluated") or 0)
        if gen_summary.get("any_f2"):
            total_f2 += 1
        if gen_summary.get("any_f1"):
            total_f1 += 1

        if gen_summary.get("progressed"):
            no_progress = 0
        else:
            no_progress += 1

        # Update state for external monitors
        state = {
            "updated_at": _now_iso(),
            "running": True,
            "gen_index": gen,
            "total_eval": total_eval,
            "total_f1_gens": total_f1,
            "total_f2_gens": total_f2,
            "no_progress_streak": no_progress,
            "last_seed": str(seed),
            "last_progress_bits": gen_summary.get("progress_bits"),
            "living_watchable": [
                s.seat_id for s in load_living_registry(registry_path).watchable_seats()
            ],
        }
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        if stop_on_f2 and gen_summary.get("any_f2"):
            stop_reason = "f2_found"
            break
        if no_progress >= int(max_no_progress_generations):
            # Try rotating to next unused seed wave before hard stop
            if gen + 1 < max_generations and (gen + 1) % len(seed_paths) != 0:
                # continue once more on next seed; only stop if streak persists across seeds
                pass
            if no_progress >= int(max_no_progress_generations):
                stop_reason = "no_progress_stall"
                break

    reg = load_living_registry(registry_path)
    elapsed = time.monotonic() - started
    report = {
        "ok": True,
        "mode": "tight_simulation_discovery",
        "generated_at": _now_iso(),
        "stop_reason": stop_reason,
        "elapsed_seconds": round(elapsed, 2),
        "n_generations": len(generations),
        "n_seeds": len(seed_paths),
        "seeds": [str(s) for s in seed_paths],
        "workers": worker_n,
        "total_evaluated": total_eval,
        "generations_with_f1": total_f1,
        "generations_with_f2": total_f2,
        "living": summary_lines(reg),
        "living_watchable": [s.seat_id for s in reg.watchable_seats()],
        "generations": generations,
        "trading_authority": False,
        "live_authority": False,
        "note": (
            "Discovery is pure Python simulation (not LLM). "
            "Mutants within a generation evaluate in a process pool when workers>1. "
            "Opportunity watching remains a separate patient loop."
        ),
    }
    stamp = _now_stamp()
    report_path = out / f"discovery_campaign_{stamp}.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    latest = out / "discovery_LATEST.json"
    latest.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    # final state
    state_path.write_text(
        json.dumps(
            {
                "updated_at": _now_iso(),
                "running": False,
                "stop_reason": stop_reason,
                "elapsed_seconds": round(elapsed, 2),
                "n_generations": len(generations),
                "total_eval": total_eval,
                "living_watchable": report["living_watchable"],
                "latest_report": str(report_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    report["latest_path"] = str(latest)
    report["state_path"] = str(state_path)
    return report

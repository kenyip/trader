#!/usr/bin/env python3
"""Chronological pre-registration screen for dry free defined-risk evolve DNA.

Research-only L0 adapter. Population construction and candidate selection use only the
chronological train slice. Exact selected DNA is then evaluated on the untouched
holdout. This first pass never writes the hypothesis registry or grants L1 readiness.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data import build  # noqa: E402
from scripts.defined_risk_fixed_cost_stress import _run as run_defined_risk_sim  # noqa: E402
from scripts.evolve_pre_registration_stress import (
    MAX_DENSE_NEGATIVE_WINDOWS,
    MAX_LOSS_USD,
    MAX_WINDOW_DD_USD,
    SUPPORTED_STRUCTURES,
    stress_candidate,
)
from scripts.pcs_cost_stress import _metrics_row  # noqa: E402
from trader_platform.evolve_tick import MIN_TRADES_SHIP, build_population  # noqa: E402
from trader_platform.research.universe import load_universe  # noqa: E402
from trader_platform.strategy_dna import StrategyDNA  # noqa: E402


def sample_universe_rows(
    symbols: Sequence[str],
    *,
    top_symbols: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Sample a pre-outcome symbol set deterministically from the liquid universe."""
    normalized = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    if top_symbols < 2:
        raise ValueError("top_symbols must be at least 2")
    if len(normalized) < top_symbols:
        raise ValueError("universe has fewer symbols than top_symbols")
    picked = random.Random(seed).sample(normalized, top_symbols)
    return [
        {
            "symbol": symbol,
            "strategy_family": "",
            "selection": "fixed_seed_uniform_universe",
        }
        for symbol in picked
    ]


def split_frame(frame: Any, train_fraction: float, *, min_bars: int = 15):
    """Return strict chronological train/holdout slices and fail closed on bad indexes."""
    if not 0.50 <= float(train_fraction) <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    if not frame.index.is_unique:
        raise ValueError("frame index must be unique")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("frame index must be monotonic increasing")
    split_index = int(len(frame) * float(train_fraction))
    train = frame.iloc[:split_index].copy()
    holdout = frame.iloc[split_index:].copy()
    if len(train) < min_bars or len(holdout) < min_bars:
        raise ValueError(f"train and holdout must each contain at least {min_bars} bars")
    chronology_ok = bool(train.index[-1] < holdout.index[0])
    if not chronology_ok:
        raise ValueError("train/holdout chronology must be strictly disjoint")
    metadata = {
        "train_fraction": float(train_fraction),
        "train_bars": len(train),
        "train_start": str(train.index[0].date()),
        "train_end": str(train.index[-1].date()),
        "holdout_bars": len(holdout),
        "holdout_start": str(holdout.index[0].date()),
        "holdout_end": str(holdout.index[-1].date()),
        "chronology_ok": chronology_ok,
    }
    return train, holdout, metadata


def train_selection_ship(row: dict[str, Any]) -> bool:
    """Select dense positive raw train SHIPs using unrounded gate PnL."""
    return bool(
        row.get("ok")
        and row.get("verdict") == "SHIP"
        and int(row.get("n_trades") or 0) >= MIN_TRADES_SHIP
        and float(row.get("gate_pnl") or 0.0) > 0.0
    )


def chronological_complete_gate(
    train: dict[str, Any],
    holdout: dict[str, Any],
    *,
    chronology_ok: bool,
) -> dict[str, Any]:
    """Require conjunctive train and untouched-holdout proxy gates; never register."""
    complete = bool(
        chronology_ok
        and train.get("complete_proxy_gates")
        and holdout.get("complete_proxy_gates")
    )
    return {
        "complete_chronological_proxy_gates": complete,
        "registration_eligible": False,
        "registration_blocker": (
            "first_pass_black_scholes_proxy_only; no registry write or L1 authority"
        ),
    }


def build_fixed_population(
    symbol_rows: Sequence[dict[str, Any]],
    *,
    structures: Sequence[str],
    mutants_per_seed: int,
    seed: int,
    max_population: int,
) -> list[StrategyDNA]:
    """Build a deterministic capped single-symbol population from explicit structures."""
    unsupported = sorted(set(structures) - SUPPORTED_STRUCTURES)
    if unsupported:
        raise ValueError(f"unsupported chronological structures: {unsupported}")
    population = build_population(
        symbol_rows,
        structures=structures,
        mutants_per_seed=mutants_per_seed,
        seed=seed,
    )
    if len(population) > max_population:
        population = random.Random(seed).sample(population, max_population)
    return population


def _default_baseline_runner(dna: StrategyDNA, frame: Any, label: str) -> dict[str, Any]:
    config = dict(dna.pcs_config() if hasattr(dna, "pcs_config") else (dna.config or {}))
    config.update(
        {
            "structure": dna.structure,
            "slippage_pct": 0.0,
            "half_spread_per_leg": 0.0,
        }
    )
    sim = run_defined_risk_sim(dna, frame, config, label)
    row = _metrics_row(sim, 0.0)
    metrics = sim.metrics or {}
    row.update(
        {
            "dna_id": dna.ensure_id(),
            "symbol": dna.symbols[0].upper(),
            "structure": dna.structure,
            "gate_pnl": float(metrics.get("total_pnl_per_contract") or 0.0),
            "gate_dd": float(metrics.get("max_dd_per_contract") or 0.0),
            "gate_max_loss_usd": float((sim.capital or {}).get("max_loss_usd") or 0.0),
        }
    )
    return row


def _default_stress_runner(hyp: dict[str, Any], frame: Any, label: str) -> dict[str, Any]:
    return stress_candidate(hyp, frame, label)


def run_lab(
    *,
    symbol_rows: Sequence[dict[str, Any]],
    frames: dict[str, Any],
    structures: Sequence[str],
    mutants_per_seed: int,
    seed: int,
    max_population: int,
    train_fraction: float,
    period: str,
    population: Sequence[StrategyDNA] | None = None,
    baseline_runner: Callable[[StrategyDNA, Any, str], dict[str, Any]] | None = None,
    stress_runner: Callable[[dict[str, Any], Any, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run train-only DNA selection then exact-DNA untouched-holdout stress."""
    baseline_runner = baseline_runner or _default_baseline_runner
    stress_runner = stress_runner or _default_stress_runner
    errors: list[dict[str, str]] = []
    splits: dict[str, tuple[Any, Any, dict[str, Any]]] = {}
    for raw_symbol, frame in frames.items():
        symbol = str(raw_symbol).upper()
        try:
            splits[symbol] = split_frame(frame, train_fraction, min_bars=15)
        except Exception as exc:  # noqa: BLE001
            errors.append({"stage": "split", "symbol": symbol, "error": str(exc)})

    actual_population = list(population) if population is not None else build_fixed_population(
        symbol_rows,
        structures=structures,
        mutants_per_seed=mutants_per_seed,
        seed=seed,
        max_population=max_population,
    )
    population_rows: list[dict[str, Any]] = []
    dna_by_id: dict[str, StrategyDNA] = {}
    for dna in actual_population:
        dna_id = dna.ensure_id()
        dna_by_id[dna_id] = dna
        symbol = (dna.symbols or [""])[0].upper()
        if len(dna.symbols or []) != 1 or symbol not in splits:
            errors.append(
                {
                    "stage": "train_selection",
                    "dna_id": dna_id,
                    "symbol": symbol,
                    "error": "single-symbol DNA with a valid split is required",
                }
            )
            continue
        train, _, _ = splits[symbol]
        try:
            population_rows.append(baseline_runner(dna, train, "train_selection"))
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "stage": "train_selection",
                    "dna_id": dna_id,
                    "symbol": symbol,
                    "error": str(exc),
                }
            )

    selected_rows = [row for row in population_rows if train_selection_ship(row)]
    selected_results: list[dict[str, Any]] = []
    for source in selected_rows:
        dna_id = str(source["dna_id"])
        dna = dna_by_id[dna_id]
        symbol = dna.symbols[0].upper()
        train, holdout, split = splits[symbol]
        hyp = {
            "id": f"transient_{dna_id}",
            "status": "research_transient",
            "dna": dna.to_dict(),
            "source_result": source,
        }
        try:
            train_stress = stress_runner(hyp, train, "train_stress")
            holdout_stress = stress_runner(hyp, holdout, "untouched_holdout")
            gate = chronological_complete_gate(
                train_stress,
                holdout_stress,
                chronology_ok=bool(split["chronology_ok"]),
            )
            selected_results.append(
                {
                    "dna_id": dna_id,
                    "symbol": symbol,
                    "structure": dna.structure,
                    "source_train_selection": source,
                    "split": split,
                    "train": train_stress,
                    "untouched_holdout": holdout_stress,
                    "capital_fit_usd": max(
                        float((train_stress.get("capital") or {}).get("capital_fit_usd") or 0.0),
                        float((holdout_stress.get("capital") or {}).get("capital_fit_usd") or 0.0),
                    ),
                    "one_lot_max_loss_usd": max(
                        float((train_stress.get("capital") or {}).get("one_lot_max_loss_usd") or 0.0),
                        float((holdout_stress.get("capital") or {}).get("one_lot_max_loss_usd") or 0.0),
                    ),
                    "max_lots": 1,
                    **gate,
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "stage": "chronological_stress",
                    "dna_id": dna_id,
                    "symbol": symbol,
                    "error": str(exc),
                }
            )

    passes = [
        row for row in selected_results if row["complete_chronological_proxy_gates"]
    ]
    ranking_complete = not errors and len(population_rows) == len(actual_population)
    evaluated_structure_counts = {
        structure: sum(1 for dna in actual_population if dna.structure == structure)
        for structure in structures
    }
    structures_evaluated = sorted(
        structure for structure, count in evaluated_structure_counts.items() if count > 0
    )
    structures_not_evaluated = sorted(
        structure for structure, count in evaluated_structure_counts.items() if count == 0
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_PROXY",
        "paper_only": True,
        "period": period,
        "seed": seed,
        "train_fraction": train_fraction,
        "structures": list(structures),
        "structures_eligible": list(structures),
        "structures_evaluated": structures_evaluated,
        "structures_not_evaluated": structures_not_evaluated,
        "evaluated_structure_counts": evaluated_structure_counts,
        "symbols": [str(row.get("symbol") or "").upper() for row in symbol_rows],
        "population_n": len(actual_population),
        "population_evaluated_n": len(population_rows),
        "selected_train_ship_n": len(selected_rows),
        "complete_chronological_proxy_gate_n": len(passes),
        "complete_chronological_proxy_gate_ids": [row["dna_id"] for row in passes],
        "registration_eligible_ids": [],
        "option_mark_provenance": "black_scholes_proxy",
        "absolute_gates": {
            "minimum_trades_each_cost_axis": MIN_TRADES_SHIP,
            "positive_ship_each_cost_axis": True,
            "max_loss_usd": MAX_LOSS_USD,
            "window_max_dd_usd": MAX_WINDOW_DD_USD,
            "dense_negative_windows_n_ge_3": MAX_DENSE_NEGATIVE_WINDOWS,
            "train_and_untouched_holdout_required": True,
        },
        "validity": {
            "selection": "population and raw SHIP selection consume train slices only",
            "holdout": "exact selected DNA is evaluated only after train selection",
            "population_pure": all(
                len(dna.symbols or []) == 1 and dna.structure in set(structures)
                for dna in actual_population
            ),
            "ranking_complete": ranking_complete,
            "all_eligible_structures_evaluated": not structures_not_evaluated,
            "structure_coverage_note": (
                "ranking is complete for the capped sampled population; eligible structures "
                "with zero evaluated rows are explicit and this is not a balanced structure stress"
            ),
            "registry_writes": False,
            "claim_limit": "L0 discovery/falsification only; cannot earn L1",
        },
        "split_metadata": {symbol: split[2] for symbol, split in splits.items()},
        "population_train_selection": population_rows,
        "selected_results": selected_results,
        "errors": errors,
        "decision": (
            "CHRONOLOGICAL_PROXY_PASS_REQUIRES_PAPER_CALIBRATION"
            if passes
            else "REJECT_ALL_TRAIN_SELECTED_DNA_ON_CONJUNCTIVE_HOLDOUT_GATES"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default="5y")
    parser.add_argument("--top-symbols", type=int, default=8)
    parser.add_argument("--mutants", type=int, default=2)
    parser.add_argument("--max-population", type=int, default=36)
    parser.add_argument("--seed", type=int, default=1754)
    parser.add_argument("--train-fraction", type=float, default=0.60)
    parser.add_argument(
        "--structures",
        default=",".join(sorted(SUPPORTED_STRUCTURES)),
        help="comma-separated supported defined-risk structures",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    structures = [value.strip() for value in args.structures.split(",") if value.strip()]
    symbol_rows = sample_universe_rows(
        load_universe(),
        top_symbols=args.top_symbols,
        seed=args.seed,
    )
    frames: dict[str, Any] = {}
    load_errors: list[dict[str, str]] = []
    for row in symbol_rows:
        symbol = row["symbol"]
        try:
            print(f"loading {symbol} {args.period}…", file=sys.stderr)
            frames[symbol] = build(symbol, period=args.period, use_cache=True)
        except Exception as exc:  # noqa: BLE001
            load_errors.append({"stage": "data_load", "symbol": symbol, "error": str(exc)})

    payload = run_lab(
        symbol_rows=symbol_rows,
        frames=frames,
        structures=structures,
        mutants_per_seed=args.mutants,
        seed=args.seed,
        max_population=args.max_population,
        train_fraction=args.train_fraction,
        period=args.period,
    )
    payload.update(
        {
            "sleeve_usd": 3000.0,
            "open_risk_budget_usd": 750.0,
            "hypothesis": (
                "fixed-seed, outcome-rank-free universe sampling plus train-only free "
                "defined-risk evolve selection can produce at least one exact DNA that "
                "also passes the same non-vacuous after-cost absolute gates on a strictly "
                "later untouched holdout"
            ),
            "falsifier": (
                "zero train-selected SHIPs pass train AND untouched-holdout baseline/B3/5% "
                "slip/fixed-$0.01/max-loss<=300/window-DD<=75/dense-negative<=5 gates, "
                "or any data/population/ranking/chronology boundary is incomplete"
            ),
            "claim_scope": (
                "historical underlying bars with synthetic listed-expiry/rounded-strike "
                "Black-Scholes option marks; L0 discovery/falsification only; no observed "
                "historical option edge, L1, paper promotion, registry write, shadow, arm, or live"
            ),
            "symbol_selection": {
                "method": "fixed_seed_uniform_universe",
                "outcome_rank_used": False,
                "rows": symbol_rows,
            },
        }
    )
    if load_errors:
        payload["errors"] = load_errors + list(payload["errors"])
        payload["validity"]["ranking_complete"] = False
        payload["decision"] = "BLOCKED_INCOMPLETE_POPULATION"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out),
                "decision": payload["decision"],
                "symbols": payload["symbols"],
                "structures": payload["structures"],
                "population_n": payload["population_n"],
                "selected_train_ship_n": payload["selected_train_ship_n"],
                "complete_chronological_proxy_gate_n": payload[
                    "complete_chronological_proxy_gate_n"
                ],
                "errors": payload["errors"],
            },
            indent=2,
        )
    )
    return 0 if payload["validity"]["ranking_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

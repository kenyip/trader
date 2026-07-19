#!/usr/bin/env python3
"""Tight simulation discovery campaign (Desk B) — not market-wait.

Run many generations of StrategySpec mutate→evaluate until F2, stall, or budget.
Opportunity watching is separate (`trader_watcher` / desk-b opportunity).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.discovery_loop import run_discovery_loop  # noqa: E402
from trader_platform.research.living_registry import DEFAULT_REGISTRY_PATH  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--seeds",
        default="",
        help="Comma paths to StrategySpec JSON; default=all configs/strategy_specs/*.json",
    )
    p.add_argument(
        "--max-generations",
        type=int,
        default=30,
        help="Generation cap (use high value with --until-f2 for marathon runs)",
    )
    p.add_argument("--max-mutants-per-gen", type=int, default=3)
    p.add_argument(
        "--max-minutes",
        type=float,
        default=0.0,
        help="Wall-clock budget (0 = no time limit besides generations/stall)",
    )
    p.add_argument(
        "--max-no-progress",
        type=int,
        default=4,
        help="Stop after this many generations with zero novel evaluations",
    )
    p.add_argument(
        "--until-f2",
        action="store_true",
        help="Marathon: high gen cap, long wall time, stop primarily on F2 or true stall",
    )
    p.add_argument(
        "--keep-going",
        action="store_true",
        help="With --until-f2, do not stop on first F2 (keep filling living seats)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Parallel process workers for mutant evals (0 = auto: cpu-1)",
    )
    p.add_argument("--symbols", default="", help="Optional comma symbol subset (faster)")
    p.add_argument(
        "--train-only",
        action="store_true",
        help="Skip holdout (faster screen; cannot prove F2 this run)",
    )
    p.add_argument(
        "--no-stop-on-f2",
        action="store_true",
        help="Keep searching even after first F2 (default: stop on F2)",
    )
    p.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    p.add_argument(
        "--out-dir",
        default=str(_REPO / ".cache/platform/spine/discovery"),
    )
    p.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact summary instead of full generation dump",
    )
    args = p.parse_args(argv)

    seeds = (
        [s.strip() for s in args.seeds.split(",") if s.strip()]
        if args.seeds.strip()
        else None
    )
    symbols = (
        [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        if args.symbols.strip()
        else None
    )
    max_gens = args.max_generations
    max_minutes = args.max_minutes
    max_no_progress = args.max_no_progress
    stop_on_f2 = not args.no_stop_on_f2
    if args.until_f2:
        max_gens = max(max_gens, 500)
        max_minutes = max_minutes if max_minutes > 0 else 12 * 60  # 12h default marathon
        max_no_progress = max(max_no_progress, 25)  # allow dense grid to drain
        stop_on_f2 = not args.keep_going
        # Parallel: evaluate more mutants per generation to feed the pool
        if args.max_mutants_per_gen <= 3:
            args.max_mutants_per_gen = 8
    max_seconds = float(max_minutes) * 60.0 if max_minutes > 0 else 0.0
    workers = args.workers if args.workers > 0 else None

    report = run_discovery_loop(
        seeds=seeds,
        max_generations=max_gens,
        max_mutants_per_gen=args.max_mutants_per_gen,
        max_seconds=max_seconds,
        max_no_progress_generations=max_no_progress,
        symbols=symbols,
        run_holdout=not args.train_only,
        stop_on_f2=stop_on_f2,
        registry_path=args.registry,
        out_dir=args.out_dir,
        workers=workers,
    )
    if args.summary_only:
        print(
            json.dumps(
                {
                    "ok": report.get("ok"),
                    "stop_reason": report.get("stop_reason"),
                    "elapsed_seconds": report.get("elapsed_seconds"),
                    "n_generations": report.get("n_generations"),
                    "total_evaluated": report.get("total_evaluated"),
                    "workers": report.get("workers"),
                    "generations_with_f1": report.get("generations_with_f1"),
                    "generations_with_f2": report.get("generations_with_f2"),
                    "living_watchable": report.get("living_watchable"),
                    "latest_path": report.get("latest_path"),
                },
                indent=2,
                allow_nan=False,
            )
        )
    else:
        # omit huge nested dumps in stdout if many gens — keep generations brief
        slim = dict(report)
        slim["generations"] = [
            {
                "gen_index": g.get("gen_index"),
                "seed_candidate_id": g.get("seed_candidate_id"),
                "n_evaluated": g.get("n_evaluated"),
                "n_skipped": g.get("n_skipped"),
                "progressed": g.get("progressed"),
                "progress_bits": g.get("progress_bits"),
                "any_f1": g.get("any_f1"),
                "any_f2": g.get("any_f2"),
            }
            for g in (report.get("generations") or [])
        ]
        print(json.dumps(slim, indent=2, allow_nan=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

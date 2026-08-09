#!/usr/bin/env python3
"""Ingest discovery F2 prove_evals into reports/bootstrap/DISCOVERY_F2_CANDIDATES.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.discovery_f2_handoff import (  # noqa: E402
    DEFAULT_DISCOVERY_ROOT,
    DEFAULT_OUT,
    ingest_discovery_f2,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--discovery-root",
        default=str(DEFAULT_DISCOVERY_ROOT),
        help="Root containing gen_*/**/*__prove_eval.json",
    )
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    p.add_argument(
        "--min-generated-at",
        default="2026-08-05",
        help="Skip prove_evals older than this ISO prefix (empty = no filter)",
    )
    p.add_argument(
        "--min-dual-cost-symbols",
        type=int,
        default=1,
        help="Minimum thick dual-cost symbols to admit a candidate",
    )
    p.add_argument(
        "--min-trades",
        type=int,
        default=12,
        help="Minimum worst-axis holdout trades for a thick symbol",
    )
    p.add_argument("--json", action="store_true", help="Print compact JSON summary")
    args = p.parse_args(argv)

    min_gen = args.min_generated_at.strip() or None
    payload = ingest_discovery_f2(
        discovery_root=args.discovery_root,
        out_path=args.out,
        min_generated_at=min_gen,
        min_dual_cost_symbols=args.min_dual_cost_symbols,
        min_trades_worst_axis=args.min_trades,
    )
    summary = {
        "ok": True,
        "n_candidates": payload.get("n_candidates"),
        "n_pack_grade_shaped": payload.get("n_pack_grade_shaped"),
        "n_new_axis": payload.get("n_new_axis"),
        "report_path": payload.get("report_path"),
        "live_authority": False,
        "capital_path_ok": False,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"discovery_f2_handoff n={summary['n_candidates']} "
            f"pack_shaped={summary['n_pack_grade_shaped']} "
            f"new_axis={summary['n_new_axis']} → {summary['report_path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

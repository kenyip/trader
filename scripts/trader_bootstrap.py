#!/usr/bin/env python3
"""Bootstrap shortlist tooling for Desk B.

Examples:
  just trader-bootstrap --candidates-only
  just trader-bootstrap --max-f2 10
  python scripts/trader_bootstrap.py --candidates-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.bootstrap import run_bootstrap_prove


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Desk B bootstrap re-prove / shortlist")
    p.add_argument("--config", default=None, help="bootstrap_strategies.json path")
    p.add_argument("--registry", default=None, help="living registry path")
    p.add_argument("--report", default=None, help="output report path")
    p.add_argument("--max-f2", type=int, default=20, help="max living F2 candidates")
    p.add_argument(
        "--candidates-only",
        action="store_true",
        help="select candidates without running dual-cost prove",
    )
    p.add_argument(
        "--no-holdout",
        action="store_true",
        help="train-only prove (faster; not bootstrap F2 claim)",
    )
    args = p.parse_args(argv)

    report = run_bootstrap_prove(
        config_path=args.config,
        registry_path=args.registry,
        report_path=args.report,
        max_f2=args.max_f2,
        run_holdout=not args.no_holdout,
        dry_candidates_only=args.candidates_only,
    )
    print(json.dumps({k: report[k] for k in report if k != "results"}, indent=2, default=str))
    if report.get("results") is not None:
        print(f"\n# results: {len(report.get('results') or [])}")
        print(f"# passed_f2: {report.get('n_passed_f2')}")
        print(f"# shortlist: {len(report.get('shortlist') or [])}")
        if report.get("report_path"):
            print(f"# report: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

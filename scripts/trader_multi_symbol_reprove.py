#!/usr/bin/env python3
"""Multi-symbol re-prove densify DNA (kill single-name luck).

Default: bootstrap densify shortlist × core multi-symbol book.
With --from-shortlist: prepend QUALITY_SHORTLIST leader symbols (AAL/BAC/…).
With --include-seed-specs: also re-prove configs/strategy_specs/*.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.bootstrap import (
    DEFAULT_MULTI_SYMBOL_BOOK,
    run_multi_symbol_pack,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Multi-symbol dual-cost re-prove")
    p.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated symbols to test each DNA on (default: core book)",
    )
    p.add_argument(
        "--from-shortlist",
        action="store_true",
        help="Prepend QUALITY_SHORTLIST leader symbols (AAL/BAC/…) to the book",
    )
    p.add_argument(
        "--quality-shortlist",
        default=None,
        help="Path to QUALITY_SHORTLIST.json",
    )
    p.add_argument(
        "--quality-top",
        type=int,
        default=12,
        help="How many shortlist rows to take symbols from",
    )
    p.add_argument(
        "--include-seed-specs",
        action="store_true",
        help="Also re-prove configs/strategy_specs/*.json DNA",
    )
    p.add_argument("--report", default=None)
    args = p.parse_args(argv)

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = list(DEFAULT_MULTI_SYMBOL_BOOK)

    report = run_multi_symbol_pack(
        symbols=symbols,
        report_path=args.report,
        include_seed_specs=args.include_seed_specs,
        from_quality_shortlist=args.from_shortlist,
        quality_shortlist_path=args.quality_shortlist,
        quality_top_n=args.quality_top,
    )
    print(
        json.dumps(
            {
                "n_dna": report.get("n_dna"),
                "n_quality_pass": report.get("n_quality_pass"),
                "n_multi_f2": report.get("n_multi_f2"),
                "n_discovery_f2": report.get("n_discovery_f2"),
                "discovery_f2_candidate_ids": report.get("discovery_f2_candidate_ids"),
                "book_symbols": report.get("book_symbols"),
                "quality_shortlist_symbols": report.get("quality_shortlist_symbols"),
                "from_quality_shortlist": report.get("from_quality_shortlist"),
                "include_discovery_f2": report.get("include_discovery_f2"),
                "include_seed_specs": report.get("include_seed_specs"),
                "report_path": report.get("report_path"),
                "results": [
                    {
                        "candidate_id": r.get("candidate_id"),
                        "source": r.get("source"),
                        "f2_symbols": r.get("f2_symbols"),
                        "thick_f2_symbols": r.get("thick_f2_symbols"),
                        "multi_symbol_f2": r.get("multi_symbol_f2"),
                        "quality_pass": r.get("quality_pass"),
                        "per_symbol": [
                            {
                                "symbol": x.get("symbol"),
                                "decision": x.get("decision"),
                                "f2": x.get("f2"),
                                "n_trades": x.get("n_trades_holdout_worst_axis"),
                                "thick": x.get("thick_enough"),
                            }
                            for x in (r.get("per_symbol") or [])
                        ],
                    }
                    for r in (report.get("results") or [])
                ],
                "honesty": report.get("honesty"),
                "live_authority": False,
            },
            indent=2,
        )
    )
    # quality_pass count is research outcome — do not fail CI solely on 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

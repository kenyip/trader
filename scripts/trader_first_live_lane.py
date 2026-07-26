#!/usr/bin/env python3
"""Rank RH MCP first-live single-leg capital-fit seats (separate from multi-leg research)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.first_live_lane import build_and_write_first_live_lane


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Build first-live single-leg capital-fit shortlist"
    )
    p.add_argument("--report", default=None, help="Output JSON path")
    p.add_argument("--sleeve-usd", type=float, default=3000.0)
    p.add_argument("--min-trades", type=int, default=15)
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--json", action="store_true", help="Print full JSON")
    args = p.parse_args(argv)

    report = build_and_write_first_live_lane(
        report_path=args.report,
        sleeve_usd=args.sleeve_usd,
        min_trades=args.min_trades,
        top_n=args.top,
    )
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    leader = report.get("leader") or {}
    print(
        json.dumps(
            {
                "generated_at": report.get("generated_at"),
                "n_eligible": report.get("n_eligible"),
                "n_rejected": report.get("n_rejected"),
                "leader": {
                    "hyp_id": leader.get("hyp_id"),
                    "symbol": leader.get("symbol"),
                    "structure": leader.get("structure"),
                    "verdict": leader.get("verdict"),
                    "n_trades": leader.get("n_trades"),
                    "csp_bp_proxy": leader.get("csp_bp_proxy"),
                    "capital_fit": leader.get("capital_fit"),
                    "why": leader.get("why"),
                }
                if leader
                else None,
                "shortlist": [
                    {
                        "symbol": s.get("symbol"),
                        "structure": s.get("structure"),
                        "verdict": s.get("verdict"),
                        "n_trades": s.get("n_trades"),
                        "csp_bp": s.get("csp_bp_proxy"),
                        "capital_fit": s.get("capital_fit"),
                    }
                    for s in (report.get("shortlist") or [])[:8]
                ],
                "near_miss_oversized": [
                    {
                        "symbol": s.get("symbol"),
                        "structure": s.get("structure"),
                        "csp_bp": s.get("csp_bp_proxy"),
                        "reasons": s.get("reject_reasons"),
                    }
                    for s in (report.get("near_miss_oversized") or [])[:5]
                ],
                "report_path": report.get("report_path"),
                "honesty": report.get("honesty"),
                "live_authority": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

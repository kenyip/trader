#!/usr/bin/env python3
"""Desk B paper handoff CLI: watch → intent → risk → optional paper place."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.living_registry import DEFAULT_REGISTRY_PATH  # noqa: E402
from trader_platform.research.paper_handoff import (  # noqa: E402
    run_paper_handoff,
    write_handoff_result,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument(
        "--execute-paper",
        action="store_true",
        help="Mutate paper ledger only if living seat is paper_eligible",
    )
    parser.add_argument(
        "--plumbing-smoke",
        action="store_true",
        help="Force one paper place for a paper_eligible seat (ignore regime; plumbing only)",
    )
    parser.add_argument(
        "--out",
        default=str(_REPO / ".cache/platform/spine/paper_handoff_LATEST.json"),
    )
    args = parser.parse_args(argv)
    if args.plumbing_smoke:
        from trader_platform.research.paper_handoff import run_paper_plumbing_smoke

        result = run_paper_plumbing_smoke(registry_path=args.registry)
    else:
        result = run_paper_handoff(
            registry_path=args.registry,
            execute_paper=bool(args.execute_paper),
            dry_run=not bool(args.execute_paper),
        )
    path = write_handoff_result(result, args.out)
    print(
        json.dumps(
            {
                "status": result.status,
                "watch_status": result.watch_status,
                "reason": result.reason,
                "paper_action": result.paper_action,
                "paper_order_id": result.paper_order_id,
                "intent": result.intent,
                "risk": result.risk,
                "out": str(path),
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

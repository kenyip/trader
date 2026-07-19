#!/usr/bin/env python3
"""Promote top F2 living seats to paper_eligible (plumbing / paper path)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.living_registry import DEFAULT_REGISTRY_PATH  # noqa: E402
from trader_platform.research.promote_paper import promote_top_f2_to_paper  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    p.add_argument(
        "--no-diversify",
        action="store_true",
        help="Allow multiple seats on the same symbol in the top N",
    )
    args = p.parse_args(argv)
    result = promote_top_f2_to_paper(
        top_n=args.top,
        registry_path=args.registry,
        diversify_symbols=not args.no_diversify,
    )
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CLI: restore RTH NEXT_SEED marks after paper_campaign thins them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trader_platform.execution.preserve_rth_next_seed import (
    DEFAULT_MARKS,
    DEFAULT_SEED,
    DEFAULT_SIDECAR,
    apply_preserve,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    ap.add_argument("--marks", type=Path, default=DEFAULT_MARKS)
    ap.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    result = apply_preserve(seed_path=args.seed, marks_path=args.marks, sidecar_path=args.sidecar)
    result["trading_authority"] = False
    result["live_authority"] = False
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

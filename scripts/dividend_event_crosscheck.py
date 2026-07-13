#!/usr/bin/env python3
"""Cross-check an AAPL Nasdaq dividend archive against Apple issuer releases."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.dividend_event_archive import (  # noqa: E402
    load_dividend_event_archive,
)
from trader_platform.research.dividend_event_crosscheck import (  # noqa: E402
    crosscheck_apple_dividends,
    snapshot_apple_dividend_releases,
)


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasdaq-archive", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    archive = load_dividend_event_archive(args.nasdaq_archive)
    releases = snapshot_apple_dividend_releases()
    result = crosscheck_apple_dividends(archive, releases)
    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        **result.to_dict(),
    }
    _atomic_write_json(Path(args.out), payload)
    print(json.dumps(payload, indent=2))
    return 0 if result.provider_status == "partial_issuer_corroboration" else 1


if __name__ == "__main__":
    raise SystemExit(main())

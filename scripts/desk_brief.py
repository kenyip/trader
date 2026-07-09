#!/usr/bin/env python3
"""Income Engine desk brief — raw data gather only (no orders, no synthesis).

Usage (from repo root):
  just desk-brief
  just desk-brief --full
  just desk-brief --no-live
  .venv/bin/python scripts/desk_brief.py --full

Prints a session/data-quality banner, then runs:
  - pmcc_manage.py (--monitor by default, full with --full)
  - live.py short-premium recs unless --no-live
  - manage_positions.py if positions.yaml exists

Agent or human synthesizes the trading-partner output shape from this dump.
See docs/DESK_BRIEF.md.

Note: income package is trader_platform/ (renamed from platform/ so the
stdlib platform module is not shadowed). Seal logic for child gathers is
retained as defense-in-depth for any residual path issues.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = REPO / ".venv" / "bin" / "python"
if not PY.exists():
    PY = Path(sys.executable)

POSITIONS_PATH = REPO / "positions.yaml"
PMCC_POSITIONS_PATH = REPO / "pmcc_positions.yaml"


def _seal_stdlib_platform_then_import_market_hours():
    """Import pmcc.market_hours without letting repo `platform/` shadow stdlib."""
    import importlib
    import sys as _sys
    from pathlib import Path as _Path

    repo = REPO.resolve()
    # Drop repo/cwd entries, import true stdlib platform, then restore repo path.
    original = list(_sys.path)
    cleaned = []
    for p in original:
        try:
            if p in ("", ".") or _Path(p).resolve() == repo:
                continue
        except Exception:
            pass
        cleaned.append(p)
    _sys.path[:] = cleaned
    import platform as stdlib_platform  # noqa: F401 — seal stdlib

    _sys.modules["platform"] = stdlib_platform
    if str(repo) not in _sys.path:
        _sys.path.insert(0, str(repo))
    # Prefer sealed stdlib for any later re-import.
    return importlib.import_module("pmcc.market_hours")


def _run_project_script(script: Path, args: list[str], *, heading: str) -> int:
    """Run a repo-root script with stdlib platform sealed (avoids platform/ shadow)."""
    print()
    print("=" * 72)
    print(heading)
    print("CMD:", PY.name, script.name, *args)
    print("=" * 72)
    print(flush=True)

    # Bootstrap runs in the child interpreter so pandas/scipy see stdlib platform.
    bootstrap = r"""
import runpy
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
script = Path(sys.argv[2]).resolve()
script_args = sys.argv[3:]

# Remove repo/cwd path entries, seal stdlib platform, then put repo back.
original = list(sys.path)
cleaned = []
for p in original:
    try:
        if p in ("", ".") or Path(p).resolve() == repo:
            continue
    except Exception:
        pass
    cleaned.append(p)
sys.path[:] = cleaned
import platform as stdlib_platform
sys.modules["platform"] = stdlib_platform
sys.path.insert(0, str(repo))

sys.argv = [str(script), *script_args]
runpy.run_path(str(script), run_name="__main__")
"""
    cmd = [str(PY), "-c", bootstrap, str(REPO), str(script), *args]
    try:
        proc = subprocess.run(cmd, cwd=str(REPO), check=False)
        return int(proc.returncode)
    except OSError as exc:
        print(f"ERROR: failed to run {script.name!r}: {exc}", file=sys.stderr)
        return 1


def _session_banner() -> None:
    mh = _seal_stdlib_platform_then_import_market_hours()
    now_utc = datetime.now(timezone.utc)
    now_et = mh.to_et(now_utc)
    rth = mh.is_regular_trading_session(now_utc)
    if rth:
        quality = "LIVE RTH — chain marks preferred for ticket-level decisions"
    else:
        quality = (
            "AFTER-HOURS / CLOSED — yfinance chains can be corrupted; "
            "treat $0 short marks, junk greeks, and auto-HARVEST from zero bid as SUSPECT until RTH recheck"
        )

    print("# Income Engine Desk Brief — RAW GATHER")
    print(f"Timestamp local/ET: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Timestamp UTC:      {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Regular trading session (approx, no holiday calendar): {'YES' if rth else 'NO'}")
    print(f"Cache policy: {mh.cache_policy_label(now_utc)}")
    print(f"DATA QUALITY: {quality}")
    print(f"Repo: {REPO}")
    print(f"pmcc_positions.yaml: {'present' if PMCC_POSITIONS_PATH.exists() else 'MISSING'}")
    print(
        f"positions.yaml:      {'present' if POSITIONS_PATH.exists() else 'MISSING (short-premium book empty on disk)'}"
    )
    if (REPO / "trader_platform").is_dir():
        print(
            "NOTE: income package is trader_platform/ (stdlib platform unshadowed)."
        )
    print()
    print("NOTE: This script only gathers. Synthesize stance with trading-partner checklist.")
    print("      Do not place trades. Do not commit private position files.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Income Engine desk brief raw gather")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pmcc-manage dashboard instead of --monitor",
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Skip short-premium live.py recommendation",
    )
    parser.add_argument(
        "--no-pmcc",
        action="store_true",
        help="Skip PMCC manage section",
    )
    args = parser.parse_args(argv)

    _session_banner()
    rc = 0

    if not args.no_pmcc:
        if not PMCC_POSITIONS_PATH.exists():
            print()
            print("=" * 72)
            print("PMCC")
            print("=" * 72)
            print("No pmcc_positions.yaml — PMCC book not loaded. Copy example or transfer privately.")
        else:
            pmcc_args = [] if args.full else ["--monitor"]
            r = _run_project_script(
                REPO / "pmcc_manage.py",
                pmcc_args,
                heading="PMCC " + ("FULL MANAGE" if args.full else "MONITOR"),
            )
            rc = rc or r

    if POSITIONS_PATH.exists():
        r = _run_project_script(
            REPO / "manage_positions.py",
            [],
            heading="SHORT-PREMIUM OPEN POSITIONS (positions.yaml)",
        )
        rc = rc or r
    else:
        print()
        print("=" * 72)
        print("SHORT-PREMIUM OPEN POSITIONS")
        print("=" * 72)
        print("No positions.yaml on disk — no open short-premium book to mark.")
        print("Create with `just positions example` only if you will track live shorts here.")

    if not args.no_live:
        r = _run_project_script(
            REPO / "live.py",
            [],
            heading="SHORT-PREMIUM LIVE RECOMMENDATION (just test / live.py)",
        )
        rc = rc or r

    print()
    print("=" * 72)
    print("RAW GATHER COMPLETE")
    print("=" * 72)
    print("Next: agent/human synthesizes docs/DESK_BRIEF.md §4 output shape.")
    print("Action types: HARVEST | ROLL | FORCE-CLOSE | RELOAD | DO NOTHING | WARN/NEEDS RTH RECHECK")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

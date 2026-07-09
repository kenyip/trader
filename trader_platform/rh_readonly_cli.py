"""CLI: validate RH read-only snapshot + print readiness / capital plan.

Usage:
  .venv/bin/python -m platform.rh_readonly_cli
  .venv/bin/python -m platform.rh_readonly_cli --json
  .venv/bin/python -m platform.rh_readonly_cli --path .cache/platform/rh_readonly_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from trader_platform.rh_snapshot import (
    DEFAULT_SNAPSHOT_PATH,
    capital_plan_tiers,
    load_snapshot,
    recommend_risk_limits,
    try_load_snapshot,
)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Stage2 RH read-only readiness + capital plan")
    p.add_argument("--path", default=str(DEFAULT_SNAPSHOT_PATH), help="snapshot JSON path")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when readiness blockers present (default: exit 0 after report)",
    )
    args = p.parse_args(argv)

    path = Path(args.path)
    snap = try_load_snapshot(path)
    if snap is None:
        print(f"NO_SNAPSHOT: {path} missing — run trader RH MCP read-only smoke first")
        print("Then write masked snapshot via platform.rh_snapshot.save_snapshot(...)")
        return 2

    ready = snap.readiness()
    capital = 0.0
    for a in snap.agentic_accounts():
        capital = max(capital, float(a.total_value), float(a.cash), float(a.buying_power))
    rec = recommend_risk_limits(capital)
    out = {
        "path": str(path),
        "fetched_at": snap.fetched_at,
        "data_quality": snap.data_quality,
        "readiness": {
            "ok": ready.ok,
            "blockers": ready.blockers,
            "warnings": ready.warnings,
            "agentic_account_masked": ready.agentic_account_masked,
            "agentic_total_value": ready.agentic_total_value,
            "agentic_option_level": ready.agentic_option_level,
            "agentic_allowed": ready.agentic_allowed,
        },
        "accounts": [
            {
                "masked": a.account_number_masked,
                "nickname": a.nickname,
                "agentic_allowed": a.agentic_allowed,
                "option_level": a.option_level,
                "total_value": a.total_value,
                "n_equities": len(a.equities),
                "n_options": len(a.options),
            }
            for a in snap.accounts
        ],
        "risk_limit_recommendations": rec,
        "capital_plan_tiers": capital_plan_tiers(),
        "notes": snap.notes,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"snapshot: {path}")
        print(f"fetched_at={snap.fetched_at} data_quality={snap.data_quality}")
        print(f"readiness_ok={ready.ok}")
        for b in ready.blockers:
            print(f"  BLOCKER: {b}")
        for w in ready.warnings:
            print(f"  WARN: {w}")
        for a in snap.accounts:
            print(
                f"  account {a.account_number_masked} nick={a.nickname!r} "
                f"agentic={a.agentic_allowed} opt={a.option_level or '-'} "
                f"total=${a.total_value:,.2f} eq={len(a.equities)} opt_pos={len(a.options)}"
            )
        print("risk_recommendations:", json.dumps(rec, indent=2))
        print("capital_tiers:")
        for t in capital_plan_tiers():
            print(f"  {t['tier']}: capital=${t['capital']} arm={t.get('arm_agentic_live')}")
    if args.strict and not ready.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

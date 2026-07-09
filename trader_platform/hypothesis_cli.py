"""CLI for hypothesis registry: list / show / add / status."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from trader_platform.hypothesis_registry import SLEEVES, STATUSES, HypothesisRegistry
from trader_platform.promotion_gates import can_promote


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="platform.hypothesis_cli", description="Hypothesis registry CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed", help="ensure seed hypotheses exist")

    p_list = sub.add_parser("list", help="list hypotheses")
    p_list.add_argument("--status", choices=STATUSES, default=None)
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="show one hypothesis")
    p_show.add_argument("id")
    p_show.add_argument("--json", action="store_true")

    p_add = sub.add_parser("add", help="add hypothesis")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--thesis", required=True)
    p_add.add_argument("--sleeve", required=True, choices=SLEEVES)
    p_add.add_argument("--instruments", default="", help="comma-separated")
    p_add.add_argument("--entry", default="")
    p_add.add_argument("--exit", default="")
    p_add.add_argument("--status", default="candidate", choices=STATUSES)
    p_add.add_argument("--id", default=None)

    p_status = sub.add_parser("status", help="transition status")
    p_status.add_argument("id")
    p_status.add_argument("new_status", choices=STATUSES)
    p_status.add_argument("--evidence", default=None, help="evidence link for promotion")
    p_status.add_argument("--force", action="store_true")
    p_status.add_argument(
        "--check-only",
        action="store_true",
        help="run promotion gate report without transitioning",
    )

    p_gate = sub.add_parser("gate", help="promotion gate report")
    p_gate.add_argument("id")
    p_gate.add_argument("--target", default="live", choices=STATUSES)

    args = p.parse_args(argv)
    reg = HypothesisRegistry()

    if args.cmd == "seed":
        hyps = reg.ensure_seeded()
        print(f"seeded/loaded {len(hyps)} hypotheses → {reg.path}")
        return 0

    if args.cmd == "list":
        reg.ensure_seeded()
        hyps = reg.list(status=args.status)
        if args.json:
            print(json.dumps([h.to_dict() for h in hyps], indent=2))
        else:
            for h in hyps:
                print(f"{h.id:28} {h.status:10} {h.sleeve:10} {h.name}")
        return 0

    if args.cmd == "show":
        h = reg.get(args.id)
        if args.json:
            print(json.dumps(h.to_dict(), indent=2))
        else:
            for k, v in h.to_dict().items():
                print(f"{k}: {v}")
        return 0

    if args.cmd == "add":
        instruments = [x.strip() for x in args.instruments.split(",") if x.strip()]
        h = reg.add(
            name=args.name,
            thesis=args.thesis,
            sleeve=args.sleeve,
            instruments=instruments,
            entry_logic_ref=args.entry,
            exit_logic_ref=args.exit,
            status=args.status,
            hypothesis_id=args.id,
        )
        print(f"added {h.id}")
        return 0

    if args.cmd == "status":
        if args.check_only:
            report = can_promote(reg, args.id, args.new_status)
            print(json.dumps(report.to_dict(), indent=2))
            return 0 if report.allowed else 2
        try:
            h = reg.transition(
                args.id,
                args.new_status,
                evidence_link=args.evidence,
                force=args.force,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"{h.id} → {h.status}")
        return 0

    if args.cmd == "gate":
        report = can_promote(reg, args.id, args.target)
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.allowed else 2

    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""CLI for the active-positions tracker.

Default action: read positions.yaml and print today's status for each.

Usage:
    just positions                          # status of all open positions
    just positions add ...                  # append a new position
    just positions close TICKER STRIKE      # remove a position from the file
    just positions example                  # write a sample positions.yaml (no overwrite)
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd

from positions import (
    POSITIONS_PATH, load_positions, load_closed_positions, save_positions,
    check_position, format_all, next_group_id,
    get_config,
)


SAMPLE = """# positions.yaml — your live open option positions
# Edit by hand or via `just positions add`. Gitignored — never committed.
#
# Required fields: ticker, side ('put'|'call'), strike, entry_date, expiration, credit
# Optional: contracts (default 1), current_price_override, notes, group_id (chain id)

positions:
  - ticker: TSLA
    side: put
    strike: 385
    entry_date: 2026-05-08
    expiration: 2026-05-15
    credit: 4.40
    contracts: 1
    group_id: 1
    notes: "example — replace with your real position"

# v1.10: closed_positions retains the chain history so `just positions` can
# surface cumulative P/L for any still-open group. Populated automatically by
# `just positions close` and `just positions roll`.
closed_positions: []
"""


def cmd_check() -> int:
    records = load_positions()
    closed = load_closed_positions()
    if not records:
        print(f"No positions in {POSITIONS_PATH}. Run `just positions example` for a template.")
        return 0

    statuses = []
    errors = []
    for r in records:
        try:
            statuses.append(check_position(r, closed_positions=closed))
        except Exception as e:
            errors.append((r, e))

    print(format_all(statuses))
    for r, e in errors:
        print(f"\n  ERROR on position {r}: {e}", file=sys.stderr)
    return 0 if not errors else 1


def cmd_whatif() -> int:
    """Phase C demo: force enable_model_management + debug on current positions and surface advisor proposals.
    The underlying ladder (check_exits) and Position state are untouched; this is pure read-only what-if.
    """
    records = load_positions()
    closed = load_closed_positions()
    if not records:
        print(f"No positions in {POSITIONS_PATH}. Run `just positions example` for a template.")
        return 0
    print("=== WHAT-IF (model management advisor shadow mode) ===")
    print("enable_model_management=True, model_debug=True (rule ladder still executes unchanged)")
    statuses = []
    for r in records:
        try:
            cfg = get_config(r['ticker'], enable_model_management=True, model_debug=True)
            st = check_position(r, cfg=cfg, closed_positions=closed)
            statuses.append(st)
            advice = st.get('model_management_advice', {})
            if advice:
                print(f"\n[whatif {r['ticker']}] advisor: {advice.get('reason', 'n/a')}")
                print(f"  close={advice.get('close')} conf={advice.get('confidence',0):.2f} overrides={advice.get('overrides')}")
        except Exception as e:
            print(f"  ERROR whatif on {r}: {e}", file=sys.stderr)
    if statuses:
        print("\n" + format_all(statuses))
    return 0


def cmd_add(args) -> int:
    records = load_positions()
    closed = load_closed_positions()
    group_id = args.group if getattr(args, 'group', None) is not None else next_group_id(records, closed)
    record = {
        'ticker': args.ticker.upper(),
        'side': args.side.lower(),
        'strike': args.strike,
        'entry_date': str(pd.Timestamp(args.entry_date).date()),
        'expiration': str(pd.Timestamp(args.expiration).date()),
        'credit': args.credit,
        'group_id': int(group_id),
    }
    if args.contracts != 1:
        record['contracts'] = args.contracts
    if args.notes:
        record['notes'] = args.notes
    records.append(record)
    save_positions(records)
    print(f"Added: {record}")
    print(f"Total positions: {len(records)}")
    return 0


def _pop_position(records: list[dict], ticker: str, strike: float) -> tuple[dict | None, list[dict]]:
    """Remove and return the first matching position from records. Returns
    (matched_record_or_None, remaining_records)."""
    matched = None
    remaining = []
    for r in records:
        if matched is None and r['ticker'].upper() == ticker.upper() and float(r['strike']) == strike:
            matched = r
        else:
            remaining.append(r)
    return matched, remaining


def cmd_close(args) -> int:
    """v1.10 — close moves the position into closed_positions with exit info so
    chain P/L stays inspectable. The closed record gains exit_date, exit_price,
    exit_reason. The position is removed from the open list."""
    records = load_positions()
    closed = load_closed_positions()
    matched, remaining = _pop_position(records, args.ticker, args.strike)
    if matched is None:
        print(f"No open position matches {args.ticker} ${args.strike}.")
        return 1
    matched_closed = dict(matched)
    matched_closed['exit_date'] = str(pd.Timestamp(args.exit_date).date()) if args.exit_date else str(pd.Timestamp.today().date())
    matched_closed['exit_price'] = float(args.exit_price) if args.exit_price is not None else 0.0
    matched_closed['exit_reason'] = args.reason or 'closed'
    closed.append(matched_closed)
    save_positions(remaining, closed_positions=closed)
    gid = matched_closed.get('group_id')
    pnl = float(matched_closed['credit']) - float(matched_closed['exit_price'])
    print(f"Closed: {matched['ticker']} ${matched['strike']} {matched['side']} "
          f"(group {gid}) at ${matched_closed['exit_price']:.2f}  "
          f"P/L ${pnl:+.2f}/share  reason={matched_closed['exit_reason']}")
    print(f"Open: {len(remaining)}.  Closed history: {len(closed)}.")
    return 0


def cmd_roll(args) -> int:
    """v1.10 — roll closes one open position and opens a new one in the same
    group_id. The chain's cumulative P/L surfaces in `just positions` status."""
    records = load_positions()
    closed = load_closed_positions()
    matched, remaining = _pop_position(records, args.ticker, args.strike)
    if matched is None:
        print(f"No open position matches {args.ticker} ${args.strike} to roll.")
        return 1
    group_id = matched.get('group_id') or next_group_id(records, closed)
    # Record the closed leg
    matched_closed = dict(matched)
    matched_closed['exit_date'] = str(pd.Timestamp(args.exit_date).date()) if args.exit_date else str(pd.Timestamp.today().date())
    matched_closed['exit_price'] = float(args.close_price)
    matched_closed['exit_reason'] = 'rolled'
    matched_closed['group_id'] = int(group_id)
    closed.append(matched_closed)
    # Open the new leg in the same group
    new_record = {
        'ticker': matched['ticker'],
        'side': matched['side'],     # same side; user picks new strike/expiration/credit
        'strike': float(args.new_strike),
        'entry_date': str(pd.Timestamp(args.exit_date).date()) if args.exit_date else str(pd.Timestamp.today().date()),
        'expiration': str(pd.Timestamp(args.new_expiration).date()),
        'credit': float(args.new_credit),
        'group_id': int(group_id),
    }
    if matched.get('contracts'):
        new_record['contracts'] = matched['contracts']
    new_record['notes'] = f"rolled from ${matched['strike']:.2f}"
    remaining.append(new_record)
    save_positions(remaining, closed_positions=closed)
    leg_pnl = float(matched['credit']) - float(args.close_price)
    print(f"Rolled: closed {matched['ticker']} ${matched['strike']} "
          f"at ${args.close_price:.2f} (leg P/L ${leg_pnl:+.2f}/sh, group {group_id}),")
    print(f"        opened {new_record['ticker']} ${new_record['strike']} {new_record['side']} "
          f"exp {new_record['expiration']} credit ${new_record['credit']:.2f}")
    print(f"Open: {len(remaining)}.  Closed history: {len(closed)}.")
    return 0


def cmd_example() -> int:
    if POSITIONS_PATH.exists():
        print(f"{POSITIONS_PATH} already exists — not overwriting.")
        return 1
    POSITIONS_PATH.write_text(SAMPLE)
    print(f"Wrote sample {POSITIONS_PATH}. Edit it with your real positions, then run `just positions`.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='Active-position tracker CLI')
    sub = ap.add_subparsers(dest='cmd')

    sub.add_parser('check', help='Run exit ladder on all open positions (default)')
    sub.add_parser('whatif', help='Phase C: what-if close/roll using model mgmt advisor (enable_model_management + debug; read-only shadow, no ladder change)')
    sub.add_parser('example', help='Write a sample positions.yaml (no overwrite)')

    a = sub.add_parser('add', help='Append a position to positions.yaml')
    a.add_argument('ticker')
    a.add_argument('side', choices=['put', 'call'])
    a.add_argument('strike', type=float)
    a.add_argument('entry_date', help='YYYY-MM-DD')
    a.add_argument('expiration', help='YYYY-MM-DD')
    a.add_argument('credit', type=float, help='per share')
    a.add_argument('--contracts', type=int, default=1)
    a.add_argument('--notes', default=None)
    a.add_argument('--group', type=int, default=None,
                   help='v1.10: attach to an existing chain id (default: new chain)')

    c = sub.add_parser('close', help='Close a position; retains chain history in closed_positions')
    c.add_argument('ticker')
    c.add_argument('strike', type=float)
    c.add_argument('exit_price', type=float, nargs='?', default=0.0,
                   help='per-share cost to close (0.0 = expired worthless)')
    c.add_argument('--exit-date', default=None, help='YYYY-MM-DD (default: today)')
    c.add_argument('--reason', default=None, help='free-form exit reason tag')

    r = sub.add_parser('roll', help='v1.10: close + open new in same group (chain it)')
    r.add_argument('ticker')
    r.add_argument('strike', type=float, help='strike of the position to close')
    r.add_argument('close_price', type=float, help='per-share cost to close the old leg')
    r.add_argument('new_strike', type=float)
    r.add_argument('new_expiration', help='YYYY-MM-DD')
    r.add_argument('new_credit', type=float)
    r.add_argument('--exit-date', default=None, help='YYYY-MM-DD (default: today)')

    args = ap.parse_args()

    if args.cmd is None or args.cmd == 'check':
        return cmd_check()
    if args.cmd == 'whatif':
        return cmd_whatif()
    if args.cmd == 'add':
        return cmd_add(args)
    if args.cmd == 'close':
        return cmd_close(args)
    if args.cmd == 'roll':
        return cmd_roll(args)
    if args.cmd == 'example':
        return cmd_example()
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

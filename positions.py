#!/usr/bin/env python3
"""
Active-position tracking: take user-supplied open positions and run the engine's
exit ladder against today's market.

YAML schema (positions.yaml at the repo root, gitignored):

    positions:
      - ticker: TSLA
        side: put                       # 'put' or 'call'
        strike: 385
        entry_date: 2026-05-08
        expiration: 2026-05-15
        credit: 4.40                    # per share, what we collected
        contracts: 1                    # optional, default 1 (display only)
        current_price_override: 0.55    # optional — actual broker mark if you
                                        # want to override the engine's BSM estimate
        notes: "took the live rec"      # optional, free-form
        group_id: 3                     # v1.10: chain id. Auto-assigned on add
                                        # if absent. Rolls inherit. A "trade
                                        # group" = original entry + any rolls.
      - ...
    closed_positions:                   # v1.10: positions that have been closed
      - ticker: TSLA                    # or rolled; retained so chain P/L stays
        side: put                       # inspectable for any still-open group.
        strike: 385
        entry_date: ...
        expiration: ...
        credit: 4.40
        exit_date: 2026-05-12
        exit_price: 2.10
        exit_reason: rolled             # or 'closed', 'max_loss', etc.
        group_id: 3

`check_position(pos_dict)` constructs a Position from the dict (using the
per-ticker `get_config(ticker)` defaults), pulls today's data, and runs
`backtest.Position.mark` + `strategies.check_exits`. Returns a status dict the
CLI and dashboard can render.

This module is *read-only* against trading state — it never sends orders.
"""

from __future__ import annotations
from pathlib import Path
import yaml
import pandas as pd

from backtest import Position
from data import build
from strategies import StrategyConfig, check_exits, get_config, recommend_management_advisor


REPO_ROOT = Path(__file__).resolve().parent
POSITIONS_PATH = REPO_ROOT / "positions.yaml"


def load_positions(path: Path | str = POSITIONS_PATH) -> list[dict]:
    """Load the positions YAML. Returns an empty list if the file is missing/empty."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"positions.yaml parse error: {e}") from e
    return list(data.get('positions') or [])


def load_closed_positions(path: Path | str = POSITIONS_PATH) -> list[dict]:
    """v1.10 — load the closed_positions history. Used to compute chain P/L for
    any still-open group. Returns empty list if absent."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError:
        return []
    return list(data.get('closed_positions') or [])


def save_positions(positions: list[dict], path: Path | str = POSITIONS_PATH,
                   closed_positions: list[dict] | None = None) -> None:
    """v1.10 — also writes the closed_positions history if provided. If omitted,
    preserves whatever closed_positions is already on disk (don't accidentally
    erase chain history when only the open set is being updated)."""
    p = Path(path)
    if closed_positions is None:
        closed_positions = load_closed_positions(path)
    payload = {'positions': positions, 'closed_positions': closed_positions}
    p.write_text(yaml.safe_dump(payload, sort_keys=False))


def next_group_id(open_positions: list[dict], closed_positions: list[dict] | None = None) -> int:
    """v1.10 — return the next free group_id across open + closed records."""
    ids = [int(r['group_id']) for r in open_positions if 'group_id' in r and r['group_id'] is not None]
    if closed_positions:
        ids += [int(r['group_id']) for r in closed_positions if 'group_id' in r and r['group_id'] is not None]
    return (max(ids) + 1) if ids else 1


def chain_realized_pnl(group_id: int, closed_positions: list[dict]) -> tuple[int, float]:
    """v1.10 — return (n_closed_in_chain, realized_pnl_per_share) for a group."""
    chain = [r for r in closed_positions if r.get('group_id') == group_id]
    pnl = sum(float(r.get('credit', 0.0)) - float(r.get('exit_price', 0.0)) for r in chain)
    return len(chain), pnl


def _position_from_dict(d: dict, cfg: StrategyConfig) -> Position:
    """Build a backtest.Position from a yaml record + the per-ticker config."""
    entry = pd.Timestamp(d['entry_date'])
    expiration = pd.Timestamp(d['expiration'])
    dte_at_entry = max((expiration - entry).days, 1)
    credit = float(d['credit'])

    if dte_at_entry <= 7:
        dcm = cfg.daily_capture_mult_short
    elif dte_at_entry <= 15:
        dcm = cfg.daily_capture_mult_mid
    else:
        dcm = cfg.daily_capture_mult_long

    return Position(
        side=str(d['side']),
        entry_date=entry,
        expiration=expiration,
        strike=float(d['strike']),
        credit=credit,
        dte_at_entry=dte_at_entry,
        iv_at_entry=0.0,                     # not used by check_exits
        regime_at_entry='live',
        daily_theta_target=credit / dte_at_entry,
        daily_capture_mult=dcm,
        group_id=int(d.get('group_id', -1)) if d.get('group_id') is not None else -1,
    )


def check_position(d: dict, cfg: StrategyConfig | None = None, df: pd.DataFrame | None = None,
                   closed_positions: list[dict] | None = None) -> dict:
    """Run the exit ladder against today's market state for one position record."""
    ticker = d['ticker']
    cfg = cfg or get_config(ticker)
    if df is None:
        df = build(ticker, period='2y')

    today = df.index[-1]
    row = df.iloc[-1]
    spot = float(row['close'])
    sigma = float(row['iv_proxy'])

    pos = _position_from_dict(d, cfg)
    mark = pos.mark(spot, sigma, today)

    override = d.get('current_price_override')
    if override is not None:
        mark = {**mark, 'price': float(override)}

    decision = check_exits(pos, mark, row, cfg)
    pnl_share = pos.credit - mark['price']
    pnl_pct = (pnl_share / pos.credit) * 100 if pos.credit > 0 else 0.0
    contracts = int(d.get('contracts', 1))

    # v1.10 — chain context: if this position is part of a multi-leg trade group,
    # surface the cumulative chain P/L so the user can see whether the chain is
    # net positive even when this leg is red.
    chain_n_closed = 0
    chain_realized = 0.0
    chain_total = pnl_share
    if pos.group_id >= 0 and closed_positions:
        chain_n_closed, chain_realized = chain_realized_pnl(pos.group_id, closed_positions)
        chain_total = chain_realized + pnl_share

    # Phase C: thin safe model management advisor (read-only surface when cfg.enable_model_management)
    # Always calls the guard fn (which is zero-cost when disabled). Adds 'model_management_advice' to status.
    # The real ladder (decision) is never altered here; advice may be used by user or future adapt hook.
    mgmt_advice = recommend_management_advisor(row, d, cfg, mark={"pnl_per_share": pnl_share, **mark})
    return {
        'record': d,
        'ticker': ticker,
        'today': today,
        'spot': spot,
        'sigma': sigma,
        'position': pos,
        'mark': mark,
        'override_used': override is not None,
        'pnl_per_share': pnl_share,
        'pnl_per_contract': pnl_share * 100,
        'pnl_total': pnl_share * 100 * contracts,
        'pnl_pct_credit': pnl_pct,
        'days_held': max((today - pos.entry_date).days, 0),
        'dte_remaining': mark['dte_remaining'],
        'exit_decision': decision,
        'cfg': cfg,
        'group_id': pos.group_id,
        'chain_n_closed': chain_n_closed,
        'chain_realized_pnl_per_share': chain_realized,
        'chain_total_pnl_per_share': chain_total,
        'features': {
            'iv_rank': float(row['iv_rank']),
            'regime': str(row['regime']),
            'reversal': bool(row['reversal']),
            'high_iv': bool(row['high_iv']),
        },
        'model_management_advice': mgmt_advice,
    }


def _exit_target_dollars(pos: Position, cfg: StrategyConfig) -> dict:
    """Re-derive the exit-ladder thresholds in $ terms for display."""
    return {
        'profit_target_buyback': pos.credit * (1.0 - cfg.profit_target),
        'profit_target_pnl':     pos.credit * cfg.profit_target,
        'daily_capture_rate':    pos.daily_theta_target * pos.daily_capture_mult,
        'max_loss_buyback':      pos.credit * (1.0 + cfg.max_loss_mult),
        'max_loss_pnl':         -pos.credit * cfg.max_loss_mult,
        'delta_breach':          cfg.delta_breach,
    }


_DECISION_ACTION = {
    'expired': 'EXPIRED — settle at intrinsic',
    'max_loss': 'CLOSE — max-loss stop hit',
    'daily_capture': 'CLOSE — daily-capture pace hit',
    'profit_target': 'CLOSE — profit target hit',
    'delta_breach': 'CLOSE — delta past breach threshold',
    'dte_stop': 'CLOSE — DTE stop',
    'regime_flip': 'CLOSE — regime flipped against the side',
}


def format_status(status: dict) -> str:
    """Human-readable terminal output for a single position."""
    pos = status['position']
    rec = status['record']
    cfg = status['cfg']
    mark = status['mark']
    tgt = _exit_target_dollars(pos, cfg)

    contracts = int(rec.get('contracts', 1))
    side_label = 'short put' if pos.side == 'put' else 'short call'
    days_held = status['days_held']
    dte_left = status['dte_remaining']
    override = status['override_used']

    pnl_share = status['pnl_per_share']
    pnl_total = status['pnl_total']
    pnl_pct = status['pnl_pct_credit']
    decision = status['exit_decision']
    action_line = _DECISION_ACTION.get(decision, 'HOLD — no exit rung firing today')
    daily_rate = pnl_share / days_held if days_held > 0 else 0.0

    lines = []
    lines.append(f"{status['ticker']}  {side_label} ${pos.strike:.2f}  (exp {pos.expiration.date()})")
    contracts_str = f"  ·  {contracts} contract{'s' if contracts != 1 else ''}" if contracts != 1 else ""
    lines.append(f"  entered {pos.entry_date.date()} for ${pos.credit:.2f} credit  ·  {days_held}d held  ·  {dte_left}d remaining{contracts_str}")
    px_label = "broker override" if override else "BSM estimate"
    lines.append(f"  today: spot ${status['spot']:.2f}  ·  option {px_label} ${mark['price']:.2f}  ·  Δ {mark['delta']:+.2f}  ·  IV proxy {status['sigma']*100:.0f}%")
    lines.append(f"  P/L: ${pnl_share:+.2f}/share  (${pnl_total:+.0f} total, {pnl_pct:+.1f}% of credit)")
    if status.get('chain_n_closed', 0) > 0:
        gid = status['group_id']
        n_prior = status['chain_n_closed']
        chain_realized = status['chain_realized_pnl_per_share']
        chain_total = status['chain_total_pnl_per_share']
        chain_total_dollars = chain_total * 100 * contracts
        lines.append(f"  chain (group {gid}, {n_prior} prior leg{'s' if n_prior != 1 else ''}): "
                     f"realized ${chain_realized:+.2f}/sh  "
                     f"·  chain total ${chain_total:+.2f}/sh  (${chain_total_dollars:+.0f})")
    lines.append(f"  >>> {action_line}")
    lines.append("  ladder targets:")
    lines.append(f"    profit_target  buyback ≤ ${tgt['profit_target_buyback']:.2f}  ({'HIT' if pnl_share >= tgt['profit_target_pnl'] else 'not hit'})")
    lines.append(f"    daily_capture  pace ≥ ${tgt['daily_capture_rate']:.3f}/sh/day  (current ${daily_rate:.3f}/day)")
    lines.append(f"    max_loss       buyback ≥ ${tgt['max_loss_buyback']:.2f}  ({'HIT' if pnl_share <= tgt['max_loss_pnl'] else 'safe'})")
    lines.append(f"    delta_breach   |Δ| > {tgt['delta_breach']}  (current {abs(mark['delta']):.2f})")
    flag_bits = []
    f = status['features']
    if f['regime'] == 'bearish':
        flag_bits.append("regime BEARISH")
    if f['reversal']:
        flag_bits.append("reversal flagged")
    if f['high_iv']:
        flag_bits.append("high_iv flagged")
    lines.append(f"    regime_flip    today: regime={f['regime']}, reversal={f['reversal']}  ({'/'.join(flag_bits) or 'no flags'})")
    # Phase C surface (read-only, zero effect on real decision unless user acts or future distillation)
    advice = status.get('model_management_advice') or {}
    if advice and (advice.get('close') or advice.get('overrides') or advice.get('confidence', 0) > 0.1):
        ov = advice.get('overrides', {})
        ov_str = f" overrides={ov}" if ov else ""
        lines.append(f"  MODEL MGMT (shadow): close={advice.get('close')} conf={advice.get('confidence',0):.2f}{ov_str}")
        lines.append(f"    reason: {advice.get('reason', '')[:90]}")
    if rec.get('notes'):
        lines.append(f"  notes: {rec['notes']}")
    return '\n'.join(lines)


def format_all(statuses: list[dict]) -> str:
    if not statuses:
        return "No active positions. Edit positions.yaml or use `just positions add` to add one."

    header = f"=== ACTIVE POSITIONS — {statuses[0]['today'].date()} ===\n"
    blocks = [format_status(s) for s in statuses]
    summary_line = _summary_line(statuses)
    return header + '\n\n'.join(blocks) + '\n\n' + summary_line


def _summary_line(statuses: list[dict]) -> str:
    n = len(statuses)
    to_close = sum(1 for s in statuses if s['exit_decision'] is not None)
    total_pnl = sum(s['pnl_total'] for s in statuses)
    return f"summary: {n} open · {to_close} flagged to close · total live P/L ${total_pnl:+.0f}"

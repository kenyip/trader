"""PMCC diagonal position tracker — multiple LEAPS + short legs."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pricing
import yaml

from pmcc.chain_data import fetch_call_chain
from pmcc.daily_playthrough import daily_policy
from pmcc.income import income_metrics
from pmcc.playbook import evaluate_live_status, _roll_target
from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy
from pmcc.scenarios import PmccPair
from pmcc.tune import load_tuned_policy

REPO_ROOT = Path(__file__).resolve().parent.parent
PMCC_POSITIONS_PATH = REPO_ROOT / "pmcc_positions.yaml"

_LEVEL_ORDER = {"alert": 0, "warn": 1, "ok": 2, "info": 3}


def _parse_date(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def _calendar_dte(exp: str | date, *, as_of: date | None = None) -> int:
    as_of = as_of or datetime.now(timezone.utc).date()
    return max((_parse_date(exp) - as_of).days, 0)


def load_pmcc_positions(path: Path | str = PMCC_POSITIONS_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    return list(data.get("pmcc_positions") or [])


def save_pmcc_positions(records: list[dict], path: Path | str = PMCC_POSITIONS_PATH) -> None:
    p = Path(path)
    p.write_text(yaml.dump({"pmcc_positions": records}, default_flow_style=False, sort_keys=False))


def _has_open_short(record: dict) -> bool:
    return (
        record.get("open_short", True) is not False
        and record.get("short_strike") is not None
        and record.get("short_expiration") is not None
        and record.get("short_credit") is not None
    )


def _closed_short_realized_total(record: dict) -> float:
    """Realized short P/L across all closed short entries, total dollars."""
    total = 0.0
    for sh in record.get("closed_shorts") or []:
        contracts = int(sh.get("contracts", 1))
        credit = float(sh.get("credit", sh.get("short_credit", 0.0)))
        close_debit = float(sh.get("close_debit", sh.get("debit", 0.0)))
        total += (credit - close_debit) * contracts
    return total


def _closed_short_clock(record: dict) -> dict | None:
    """Premium-clock budget after shorts are closed and before the next reload."""
    closed = list(record.get("closed_shorts") or [])
    if not closed:
        return None
    today = datetime.now().astimezone().date()
    realized = _closed_short_realized_total(record)
    short_contracts = sum(int(sh.get("contracts", 1)) for sh in closed)
    long_contracts = int(record.get("contracts", 1))
    opened_dates = [_parse_date(sh.get("opened") or record.get("entry_date") or today) for sh in closed]
    closed_dates = [_parse_date(sh.get("closed") or today) for sh in closed]
    first_open = min(opened_dates)
    last_close = max(closed_dates)
    days_since_open = max((today - first_open).days, 1)
    days_since_close = max((today - last_close).days, 0)

    def target_block(label: str, target_per_contract: float) -> dict:
        one_short_target = target_per_contract * max(short_contracts, 1)
        portfolio_target = target_per_contract * max(long_contracts, 1)
        one_short_days = realized / one_short_target if one_short_target else 0.0
        portfolio_days = realized / portfolio_target if portfolio_target else 0.0
        one_short_wait = max(0.0, one_short_days - days_since_open)
        portfolio_wait = max(0.0, portfolio_days - days_since_open)
        return {
            "label": label,
            "target_per_contract": target_per_contract,
            "one_short_target_daily": one_short_target,
            "portfolio_target_daily": portfolio_target,
            "one_short_days_covered": one_short_days,
            "portfolio_days_covered": portfolio_days,
            "one_short_wait_days": one_short_wait,
            "portfolio_wait_days": portfolio_wait,
            "one_short_budget_until": (today + timedelta(days=round(one_short_wait))).isoformat(),
            "portfolio_budget_until": (today + timedelta(days=round(portfolio_wait))).isoformat(),
        }

    target_floor = float(record.get("income_floor_daily", 10.0))
    target_good = float(record.get("income_good_daily", 15.0))
    target_strong = float(record.get("income_strong_daily", 20.0))
    blocks = {
        "floor": target_block("floor", target_floor),
        "good": target_block("good", target_good),
        "strong": target_block("strong", target_strong),
    }
    avg_since_open = realized / days_since_open
    avg_per_long_since_open = avg_since_open / max(long_contracts, 1)
    good_wait = blocks["good"]["portfolio_wait_days"]
    if good_wait >= 7:
        reload_mode = "patient — aim wider/higher strike; bank still covers good portfolio pace"
    elif good_wait > 0:
        reload_mode = "selective — start accepting balanced premium if setup is safe"
    else:
        reload_mode = "income needed — prioritize restarting premium clock over perfect upside"
    return {
        "realized": realized,
        "short_contracts": short_contracts,
        "long_contracts": long_contracts,
        "first_open": first_open.isoformat(),
        "last_close": last_close.isoformat(),
        "days_since_open": days_since_open,
        "days_since_close": days_since_close,
        "avg_since_open": avg_since_open,
        "avg_per_long_since_open": avg_per_long_since_open,
        "targets": blocks,
        "reload_mode": reload_mode,
    }


def _call_mark(spot: float, strike: float, dte: int, iv: float, r: float) -> dict:
    if dte <= 0:
        px = max(spot - strike, 0.0)
        delta = 1.0 if spot > strike else 0.0
    else:
        T = dte / 365.0
        px = max(pricing.price(spot, strike, T, iv, "call", r=r), 0.0)
        delta = pricing.delta(spot, strike, T, iv, "call", r=r)
    return {"price": px, "delta": delta, "source": "model", "iv": iv}


def _chain_call_mark(chain, expiration: str, strike: float) -> dict | None:
    """Exact contract mark from live/cached chain, dollars per share."""
    if chain is None or chain.empty:
        return None
    sub = chain[
        (chain["expiration"].astype(str) == str(expiration)[:10])
        & (chain["strike"].astype(float) == float(strike))
    ]
    if sub.empty:
        return None
    row = sub.iloc[0]
    mid = float(row.get("mid") or 0.0)
    bid = float(row.get("bid") or 0.0)
    ask = float(row.get("ask") or 0.0)
    last = float(row.get("last") or 0.0)
    if mid <= 0:
        if bid > 0 and ask > 0:
            mid = (bid + ask) / 2.0
        elif last > 0:
            mid = last
    if mid <= 0:
        return None
    return {
        "price": mid,
        "delta": float(row.get("delta") or 0.0),
        "source": "chain",
        "iv": float(row.get("iv") or 0.0),
        "bid": bid,
        "ask": ask,
        "last": last,
        "expiration": str(row.get("expiration")),
    }


def record_to_pair(record: dict, spot_now: float, *, r: float = 0.04) -> PmccPair:
    leaps_dte = _calendar_dte(record["leaps_expiration"])
    short_dte = _calendar_dte(record["short_expiration"])
    leaps_debit = float(record["leaps_debit"])
    short_credit = float(record["short_credit"])
    spot_entry = float(record.get("spot_at_entry", spot_now))
    leaps_iv = float(record.get("leaps_iv", 0.55))
    short_iv = float(record.get("short_iv", 0.45))
    return PmccPair(
        spot_entry=spot_entry,
        leaps_strike=float(record["leaps_strike"]),
        leaps_exp=str(record["leaps_expiration"]),
        leaps_dte=leaps_dte,
        leaps_iv=leaps_iv,
        leaps_debit=leaps_debit,
        short_strike=float(record["short_strike"]),
        short_exp=str(record["short_expiration"]),
        short_dte=short_dte,
        short_iv=short_iv,
        short_credit=short_credit,
        leaps_delta_target=float(record.get("leaps_delta", 0.65)),
        short_delta_target=float(record.get("short_delta", 0.30)),
    )


def check_pmcc_position(
    record: dict,
    spot_now: float,
    *,
    preset: str = "managed",
    r: float = 0.04,
) -> dict:
    """Mark PMCC diagonal and evaluate playbook triggers."""
    if not _has_open_short(record):
        return check_leaps_only_position(record, spot_now, preset=preset, r=r)

    pair = record_to_pair(record, spot_now, r=r)
    chain = None
    ticker = str(record.get("ticker", "TSLA"))
    try:
        _, chain = fetch_call_chain(ticker, r=r, min_dte=1)
    except Exception:
        chain = None
    tune_preset = preset if preset in POLICY_BY_PRESET else "balanced"
    base = POLICY_BY_PRESET.get(tune_preset, PlayPolicy())
    policy = daily_policy(load_tuned_policy(
        tune_preset, pair.leaps_strike, pair.short_strike, base,
    ))
    leaps_m = _chain_call_mark(chain, pair.leaps_exp, pair.leaps_strike) or _call_mark(
        spot_now, pair.leaps_strike, pair.leaps_dte, pair.leaps_iv, r,
    )
    short_m = _chain_call_mark(chain, pair.short_exp, pair.short_strike) or _call_mark(
        spot_now, pair.short_strike, pair.short_dte, pair.short_iv, r,
    )
    if leaps_m.get("iv", 0) > 0:
        pair.leaps_iv = float(leaps_m["iv"])
    if short_m.get("iv", 0) > 0:
        pair.short_iv = float(short_m["iv"])
    leaps_leg = leaps_m["price"] * 100 - pair.leaps_debit
    short_mark = short_m["price"] * 100
    leaps_mark = leaps_m["price"] * 100
    short_leg = pair.short_credit - short_mark
    net_pnl = leaps_leg + short_leg
    carry = income_metrics(record, pair, spot_now, short_mark, leaps_mark, r=r)
    roll_k = _roll_target(spot_now, pair.short_strike, pair.leaps_strike, policy)
    checks = evaluate_live_status(pair, policy, spot_now, r=r)

    # Force close check: short ITM at <= force_close_dte
    if pair.short_dte <= policy.force_close_dte and spot_now >= pair.short_strike:
        checks.append({
            "level": "alert",
            "rule": "FORCE CLOSE (ITM near expiry)",
            "detail": f"Short {pair.short_dte}d left, spot ${spot_now:,.0f} ≥ ${pair.short_strike:.0f} — "
                      f"buy back NOW, roll to ~${roll_k:.0f} {policy.short_dte_new}d. Never let expire ITM.",
        })

    # LEAPS conditional roll check
    moneyness = spot_now / pair.leaps_strike
    if pair.leaps_dte <= policy.leaps_roll_dte:
        if moneyness >= policy.leaps_extreme_itm_threshold:
            checks.append({
                "level": "alert",
                "rule": "LEAPS EXTREME ITM — close short",
                "detail": f"LEAPS {pair.leaps_dte}d left, spot/strike={moneyness:.2f} — "
                          f"close short, LEAPS naked. Position is capped.",
            })
        elif moneyness >= policy.leaps_deep_itm_threshold:
            checks.append({
                "level": "info",
                "rule": "LEAPS DEEP ITM — hold",
                "detail": f"LEAPS {pair.leaps_dte}d left, spot/strike={moneyness:.2f} — "
                          f"hold LEAPS, keep selling shorts.",
            })
        else:
            leaps_mark_now = leaps_m["price"] * 100
            checks.append({
                "level": "warn",
                "rule": "LEAPS ROLL TIME",
                "detail": f"LEAPS {pair.leaps_dte}d left, spot/strike={moneyness:.2f} — "
                          f"sell LEAPS (${leaps_mark_now:,.0f}), buy new 727d. Avoid theta cliff.",
            })

    top = sorted(checks, key=lambda c: _LEVEL_ORDER.get(c["level"], 9))[0]
    contracts = int(record.get("contracts", 1))
    return {
        "record": record,
        "pair": pair,
        "policy": policy,
        "spot_now": spot_now,
        "checks": checks,
        "primary_action": top["rule"],
        "primary_level": top["level"],
        "primary_detail": top["detail"],
        "leaps_mark": leaps_m,
        "short_mark": short_m,
        "leaps_leg_pnl": leaps_leg,
        "short_leg_pnl": short_leg,
        "net_pnl": net_pnl,
        "net_pnl_total": net_pnl * contracts,
        "spread_width": pair.short_strike - pair.leaps_strike,
        "roll_target": roll_k,
        "contracts": contracts,
        "carry": carry,
    }


def check_leaps_only_position(
    record: dict,
    spot_now: float,
    *,
    preset: str = "managed",
    r: float = 0.04,
) -> dict:
    """Mark a LEAPS-only PMCC state after the short has been closed."""
    ticker = str(record.get("ticker", "TSLA"))
    chain = None
    try:
        _, chain = fetch_call_chain(ticker, r=r, min_dte=1)
    except Exception:
        chain = None

    leaps_strike = float(record["leaps_strike"])
    leaps_exp = str(record["leaps_expiration"])
    leaps_dte = _calendar_dte(leaps_exp)
    leaps_debit = float(record["leaps_debit"])
    leaps_m = _chain_call_mark(chain, leaps_exp, leaps_strike) or _call_mark(
        spot_now, leaps_strike, leaps_dte, float(record.get("leaps_iv", 0.55)), r,
    )
    leaps_mark = leaps_m["price"] * 100
    leaps_leg_pnl = leaps_mark - leaps_debit
    contracts = int(record.get("contracts", 1))
    realized_short_total = _closed_short_realized_total(record)
    realized_short_per_long = realized_short_total / max(contracts, 1)
    net_pnl = leaps_leg_pnl + realized_short_per_long

    tune_preset = preset if preset in POLICY_BY_PRESET else "managed"
    policy = daily_policy(POLICY_BY_PRESET.get(tune_preset, PlayPolicy()))

    pair = PmccPair(
        spot_entry=float(record.get("spot_at_entry", spot_now)),
        leaps_strike=leaps_strike,
        leaps_exp=leaps_exp,
        leaps_dte=leaps_dte,
        leaps_iv=float(leaps_m.get("iv") or record.get("leaps_iv", 0.55)),
        leaps_debit=leaps_debit,
        short_strike=float(record.get("last_short_strike") or record.get("short_strike") or max(leaps_strike + 90, spot_now * 1.25)),
        short_exp=str(record.get("last_short_expiration") or record.get("short_expiration") or ""),
        short_dte=60,
        short_iv=float(record.get("short_iv", 0.45)),
        short_credit=0.0,
        leaps_delta_target=float(record.get("leaps_delta", 0.65)),
        short_delta_target=float(record.get("short_delta", 0.30)),
    )

    checks = [{
        "level": "info",
        "rule": "LEAPS ONLY — no open short",
        "detail": "Short leg is closed. Monitor for a quality reload; do not stay naked by default unless TSLA is in an extreme rip.",
    }]

    moneyness = spot_now / leaps_strike
    if leaps_dte <= policy.leaps_roll_dte:
        if moneyness >= policy.leaps_extreme_itm_threshold:
            checks.append({
                "level": "info",
                "rule": "LEAPS EXTREME ITM — naked OK",
                "detail": f"LEAPS {leaps_dte}d left, spot/strike={moneyness:.2f}; staying naked can be justified for upside.",
            })
        elif moneyness < policy.leaps_deep_itm_threshold:
            checks.append({
                "level": "warn",
                "rule": "LEAPS ROLL TIME",
                "detail": f"LEAPS {leaps_dte}d left, spot/strike={moneyness:.2f}; plan LEAPS roll before theta cliff.",
            })

    top = sorted(checks, key=lambda c: _LEVEL_ORDER.get(c["level"], 9))[0]
    return {
        "record": record,
        "pair": pair,
        "policy": policy,
        "spot_now": spot_now,
        "checks": checks,
        "primary_action": top["rule"],
        "primary_level": top["level"],
        "primary_detail": top["detail"],
        "leaps_mark": leaps_m,
        "short_mark": None,
        "leaps_leg_pnl": leaps_leg_pnl,
        "short_leg_pnl": realized_short_per_long,
        "realized_short_total": realized_short_total,
        "closed_short_clock": _closed_short_clock(record),
        "net_pnl": net_pnl,
        "net_pnl_total": net_pnl * contracts,
        "spread_width": None,
        "roll_target": None,
        "contracts": contracts,
        "carry": None,
        "no_open_short": True,
    }


def format_pmcc_portfolio(rows: list[dict]) -> str:
    lines = []
    for s in rows:
        p = s["pair"]
        if s.get("no_open_short"):
            lines.append(
                f"{s['record'].get('ticker', 'TSLA')} "
                f"LEAPS {int(p.leaps_strike)} x{s['contracts']} "
                f"[INFO LEAPS ONLY] P/L ${s['net_pnl']:+,.0f}/long"
            )
        else:
            lines.append(
                f"{s['record'].get('ticker', 'TSLA')} "
                f"{int(p.leaps_strike)}/{int(p.short_strike)} "
                f"[{s['primary_level'].upper()} {s['primary_action']}] "
                f"P/L ${s['net_pnl']:+,.0f}/ct"
            )
    return "\n".join(lines)


PMCC_SAMPLE = """# pmcc_positions.yaml — live PMCC diagonals (gitignored)
pmcc_positions:
  - ticker: TSLA
    leaps_strike: 380
    leaps_expiration: 2028-01-21
    leaps_debit: 11695
    short_strike: 490
    short_expiration: 2026-08-21
    short_credit: 745
    entry_date: 2026-06-20
    spot_at_entry: 400.49
    contracts: 1
    notes: "example — replace with your position"
"""
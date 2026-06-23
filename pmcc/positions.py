"""PMCC diagonal position tracker — multiple LEAPS + short legs."""

from __future__ import annotations

from datetime import date, datetime, timezone
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


def format_pmcc_portfolio(rows: list[dict]) -> str:
    lines = []
    for s in rows:
        p = s["pair"]
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
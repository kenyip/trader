from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd

import pricing

INITIAL_LEGS = (450, 450, 500)
HIGHER_LEGS = (470, 470, 520)
ADD_ON_LEGS = (500, 500)
WIDER_ADD_ON_LEGS = (500, 520)

# These are package-level targets. They intentionally map to the user's staged
# plan rather than generic per-contract defaults: 3 shorts first, then 2 more.
INITIAL_DAILY_TARGETS = {"floor": 30.0, "good": 35.0, "strong": 45.0}
HIGHER_DAILY_TARGETS = {"floor": 30.0, "good": 33.0, "strong": 43.0}
ADD_ON_DAILY_TARGETS = {"floor": 15.0, "good": 20.0, "strong": 23.0}
FULL_DAILY_TARGETS = {"floor": 50.0, "good": 60.0, "strong": 70.0}


def _today(value: date | None = None) -> date:
    return value or datetime.now().astimezone().date()


def _fmt_legs(legs: Iterable[int]) -> str:
    counts = Counter(int(x) for x in legs)
    return " + ".join(f"{n}x ${strike}" for strike, n in sorted(counts.items()))


def _target_credits(dte: int, daily_targets: dict[str, float]) -> dict[str, float]:
    return {f"target_credit_{k}": round(v * dte, 2) for k, v in daily_targets.items()}


def _option_row(
    chain: pd.DataFrame,
    expiration: str,
    strike: float,
    *,
    spot: float,
    dte: int = 60,
    iv: float = 0.45,
    r: float = 0.04,
) -> pd.Series:
    sub = chain[
        (chain["expiration"].astype(str) == str(expiration)[:10])
        & (chain["strike"].astype(float) == float(strike))
    ]
    if not sub.empty:
        return sub.iloc[0]
    T = max(dte, 1) / 365.0
    bid = pricing.price(spot, strike, T, iv, "call", r=r) * 0.97
    return pd.Series({
        "expiration": expiration,
        "dte": dte,
        "strike": float(strike),
        "bid": bid,
        "ask": bid * 1.02,
        "mid": bid,
        "iv": iv,
        "delta": pricing.delta(spot, strike, T, iv, "call", r=r),
        "source": "model",
    })


def _choose_short_expiration(chain: pd.DataFrame, target_dte: int = 60) -> str:
    if chain.empty:
        raise ValueError("empty chain")
    expirations = (
        chain[["expiration", "dte"]]
        .drop_duplicates()
        .assign(dte=lambda df: df["dte"].astype(int))
    )
    candidates = expirations[(expirations.dte >= 45) & (expirations.dte <= 75)]
    if candidates.empty:
        candidates = expirations
    candidates = candidates.assign(_dist=lambda df: (df["dte"].astype(int) - target_dte).abs())
    row = candidates.sort_values("_dist").iloc[0]
    return str(row["expiration"])


def _package_quote(
    chain: pd.DataFrame,
    expiration: str,
    legs: tuple[int, ...],
    *,
    label: str,
    daily_targets: dict[str, float],
    spot: float,
    order_style: str,
) -> dict:
    exp_rows = chain[chain["expiration"].astype(str) == str(expiration)[:10]]
    default_dte = int(exp_rows.iloc[0]["dte"]) if not exp_rows.empty else 60
    rows = [_option_row(chain, expiration, k, spot=spot, dte=default_dte) for k in legs]
    dte = int(rows[0]["dte"])
    bid_credit = sum(float(r["bid"]) * 100 for r in rows)
    mid_credit = sum(float(r.get("mid", (float(r["bid"]) + float(r["ask"])) / 2)) * 100 for r in rows)
    nearest = min(legs)
    out = {
        "label": label,
        "expiration": expiration,
        "dte": dte,
        "legs": _fmt_legs(legs),
        "short_count": len(legs),
        "nearest_short": nearest,
        "nearest_upside_pct": round((nearest / spot - 1) * 100, 1),
        "bid_credit": round(bid_credit, 2),
        "mid_credit": round(mid_credit, 2),
        "bid_per_day": bid_credit / dte if dte else 0.0,
        "mid_per_day": mid_credit / dte if dte else 0.0,
        "daily_floor": daily_targets["floor"],
        "daily_good": daily_targets["good"],
        "daily_strong": daily_targets["strong"],
    }
    out.update(_target_credits(dte, daily_targets))
    out["order_limit_text"] = (
        f"{out['legs']} @ ${out['target_credit_good'] / 100:.2f} package credit {order_style}"
    )
    if out["bid_credit"] >= out["target_credit_good"]:
        out["status"] = "good now"
    elif out["bid_credit"] >= out["target_credit_floor"]:
        out["status"] = "acceptable now"
    else:
        out["status"] = "wait"
    return out


def _event_window(today: date) -> dict:
    delivery_start = date(2026, 7, 1)
    delivery_end = date(2026, 7, 3)
    earnings = date(2026, 7, 22)
    return {
        "delivery_window": f"{delivery_start.isoformat()} to {delivery_end.isoformat()} (estimate)",
        "days_to_delivery_window": max((delivery_start - today).days, 0),
        "earnings_date": earnings.isoformat(),
        "days_to_earnings": max((earnings - today).days, 0),
        "headline_risk": "high — robotaxi/Cybercab chatter + delivery numbers + earnings window",
    }


def _summarize_position(records: list[dict]) -> dict:
    tsla = [r for r in records if str(r.get("ticker", "TSLA")).upper() == "TSLA"]
    leaps_contracts = sum(int(r.get("contracts", 1)) for r in tsla)
    total_debit = sum(float(r.get("leaps_debit", 0.0)) * int(r.get("contracts", 1)) for r in tsla)
    open_short_contracts = sum(
        int(r.get("contracts", 1))
        for r in tsla
        if r.get("open_short", True) is not False and r.get("short_strike") is not None
    )
    target_short_contracts = round(leaps_contracts * 0.714285714)
    return {
        "leaps_contracts": leaps_contracts,
        "open_short_contracts": open_short_contracts,
        "target_short_contracts": target_short_contracts,
        "remaining_short_contracts": max(target_short_contracts - open_short_contracts, 0),
        "total_leaps_debit": total_debit,
        "avg_leaps_debit": total_debit / leaps_contracts if leaps_contracts else 0.0,
        "coverage_target_pct": round(target_short_contracts / leaps_contracts * 100, 1) if leaps_contracts else 0.0,
    }


def _next_step(spot: float, packages: dict[str, dict], events: dict) -> dict:
    initial = packages["initial"]
    higher = packages["higher"]
    if spot >= 390:
        return {
            "action": "Shift higher before selling shorts; avoid starting the stack too close to $450 after a green/rip move.",
            "preferred_package": "higher",
            "target": higher["order_limit_text"],
            "wait_for": "green day / IV pop, but use higher strikes if spot is already near $390-$400",
        }
    if initial["bid_credit"] >= initial["target_credit_good"]:
        return {
            "action": "Sell initial stack now if fills are near good target.",
            "preferred_package": "initial",
            "target": initial["order_limit_text"],
            "wait_for": "no wait needed",
        }
    return {
        "action": "Wait for a green day / IV pop, then sell the initial 3-short stack.",
        "preferred_package": "initial",
        "target": initial["order_limit_text"],
        "wait_for": f"up to delivery-number setup window (~{events['days_to_delivery_window']} calendar days), then reassess",
    }


def _estimate_roll(
    chain: pd.DataFrame,
    expiration: str,
    *,
    old_strike: int,
    new_strike: int,
    trigger_spot: float,
    elapsed_days: int,
    r: float = 0.04,
) -> dict:
    old = _option_row(chain, expiration, old_strike, spot=trigger_spot, dte=57)
    original_credit = float(old["bid"]) * 100
    original_dte = int(old["dte"])
    remaining_dte = max(original_dte - elapsed_days, 1)
    iv = float(old.get("iv", 0.50)) * (1.05 if trigger_spot >= old_strike else 1.0)
    close_cost = pricing.price(trigger_spot, old_strike, remaining_dte / 365, iv, "call", r=r) * 100 * 1.01
    new_credit = pricing.price(trigger_spot, new_strike, 60 / 365, iv, "call", r=r) * 100 * 0.97
    return {
        "est_close_cost_per_short": round(close_cost),
        "est_roll_credit_per_short": round(new_credit),
        "est_net_debit_per_short": round(close_cost - new_credit),
        "est_short_pnl_before_roll": round(original_credit - close_cost),
    }


def _management_rows(chain: pd.DataFrame, expiration: str) -> list[dict]:
    rows = [
        {
            "trigger": "$450",
            "target_short": "hold / prepare",
            "action": "Do not auto-roll; wait unless move is violent.",
            "premium_target": "keep initial target unless IV expands",
        },
        {
            "trigger": "$470",
            "target_short": "$525-$545",
            "action": "Prepare/proactive roll of 2x $450 if the move is fast.",
            "premium_target": "prefer roll credit that keeps net debit manageable",
        },
    ]
    row_490 = {
        "trigger": "$490",
        "target_short": "$545-$550",
        "action": "Roll 2x $450 to roughly $545-$550; consider trimming 1x $410 LEAPS if total roll debit is meaningful.",
        "premium_target": "target ~$2k+ credit per new $545 short if IV is elevated",
    }
    row_490.update(_estimate_roll(chain, expiration, old_strike=450, new_strike=545, trigger_spot=490, elapsed_days=30))
    row_500 = {
        "trigger": "$500+",
        "target_short": "$590",
        "action": "If pushing through $500, roll $500 shorts toward ~$590.",
        "premium_target": "target ~$1k+ credit per $590 roll short",
    }
    row_500.update(_estimate_roll(chain, expiration, old_strike=500, new_strike=590, trigger_spot=490, elapsed_days=30))
    row_520 = {
        "trigger": "$520",
        "target_short": "$590/$620",
        "action": "Roll $500/$520 shorts wider; prioritize upside room over max premium.",
        "premium_target": "do not chase tight premium; keep enough room for catalyst continuation",
    }
    row_520.update(_estimate_roll(chain, expiration, old_strike=500, new_strike=590, trigger_spot=520, elapsed_days=35))
    rows.extend([row_490, row_500, row_520])
    return rows


def build_tsla_staged_entry_plan(
    records: list[dict],
    chain: pd.DataFrame,
    *,
    spot: float,
    today: date | None = None,
) -> dict:
    today = _today(today)
    exp = _choose_short_expiration(chain)
    events = _event_window(today)
    packages = {
        "initial": _package_quote(
            chain,
            exp,
            INITIAL_LEGS,
            label="Initial 3-short stack",
            daily_targets=INITIAL_DAILY_TARGETS,
            spot=spot,
            order_style="good-till-green-day",
        ),
        "higher": _package_quote(
            chain,
            exp,
            HIGHER_LEGS,
            label="Higher-strike green-day stack",
            daily_targets=HIGHER_DAILY_TARGETS,
            spot=spot,
            order_style="only if TSLA is already green/near $390-$400",
        ),
        "add_on": _package_quote(
            chain,
            exp,
            ADD_ON_LEGS,
            label="Add-on 2-short stack",
            daily_targets=ADD_ON_DAILY_TARGETS,
            spot=spot,
            order_style="add later on green/IV-pop day",
        ),
        "wider_add_on": _package_quote(
            chain,
            exp,
            WIDER_ADD_ON_LEGS,
            label="Wider add-on stack",
            daily_targets=ADD_ON_DAILY_TARGETS,
            spot=spot,
            order_style="add later if rip risk is elevated",
        ),
    }
    position = _summarize_position(records)
    full_bid = packages["initial"]["bid_credit"] + packages["add_on"]["bid_credit"]
    full_dte = packages["initial"]["dte"]
    full = {
        "label": "Full staged 5-short stack",
        "legs": f"{packages['initial']['legs']} then {packages['add_on']['legs']}",
        "bid_credit": round(full_bid, 2),
        "bid_per_day": full_bid / full_dte if full_dte else 0.0,
        "dte": full_dte,
        "daily_floor": FULL_DAILY_TARGETS["floor"],
        "daily_good": FULL_DAILY_TARGETS["good"],
        "daily_strong": FULL_DAILY_TARGETS["strong"],
    }
    full.update(_target_credits(full_dte, FULL_DAILY_TARGETS))
    packages["full"] = full
    return {
        "as_of": today.isoformat(),
        "spot": float(spot),
        "short_expiration": exp,
        "position": position,
        "events": events,
        "packages": packages,
        "next_step": _next_step(spot, packages, events),
        "management": _management_rows(chain, exp),
    }

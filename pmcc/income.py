from __future__ import annotations

from datetime import date, datetime, timezone

import pricing

from pmcc.scenarios import PmccPair


def _parse_date(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def _calendar_dte(exp: str | date, *, as_of: date | None = None) -> int:
    as_of = as_of or datetime.now(timezone.utc).date()
    return max((_parse_date(exp) - as_of).days, 0)


def _call_mark(spot: float, strike: float, dte: int, iv: float, r: float) -> dict:
    if dte <= 0:
        px = max(spot - strike, 0.0)
        delta = 1.0 if spot > strike else 0.0
    else:
        T = dte / 365.0
        px = max(pricing.price(spot, strike, T, iv, "call", r=r), 0.0)
        delta = pricing.delta(spot, strike, T, iv, "call", r=r)
    return {"price": px, "delta": delta}


def classify_daily_pace(x: float) -> str:
    if x < 10:
        return "too slow"
    if x < 15:
        return "carry only"
    if x < 20:
        return "good"
    return "excellent"


def income_metrics(
    record: dict,
    pair: PmccPair,
    spot_now: float,
    short_mark: float,
    leaps_mark: float,
    *,
    r: float = 0.04,
    target_floor: float = 10.0,
    target_good: float = 15.0,
    target_strong: float = 20.0,
) -> dict:
    """Return short-income pace and LEAPS carry metrics, dollars per contract."""
    today = datetime.now(timezone.utc).date()
    target_floor = float(record.get("income_floor_daily", target_floor))
    target_good = float(record.get("income_good_daily", target_good))
    target_strong = float(record.get("income_strong_daily", target_strong))
    short_open_date = _parse_date(record.get("short_open_date") or record.get("entry_date") or today)
    days_held = max((today - short_open_date).days, 1)
    short_open_dte = int(record.get("short_open_dte") or _calendar_dte(pair.short_exp, as_of=short_open_date))
    short_open_dte = max(short_open_dte, 1)

    short_credit = pair.short_credit
    current_short_profit = short_credit - short_mark
    harvest_profit = short_credit * 0.50
    harvest_mark = short_credit - harvest_profit

    full_credit_daily = short_credit / short_open_dte
    current_profit_daily = current_short_profit / days_held
    harvest_profit_daily_if_today = harvest_profit / days_held

    floor_days_covered = harvest_profit / target_floor
    good_days_covered = harvest_profit / target_good
    strong_days_covered = harvest_profit / target_strong
    wait_floor = max(0.0, floor_days_covered - days_held)
    wait_good = max(0.0, good_days_covered - days_held)
    wait_strong = max(0.0, strong_days_covered - days_held)

    if pair.leaps_dte > 365:
        roll_dte = 365
    else:
        roll_dte = max(pair.leaps_dte - 90, 1)
    try:
        roll_mark = _call_mark(spot_now, pair.leaps_strike, roll_dte, pair.leaps_iv, r)["price"] * 100
        days_to_roll = max(pair.leaps_dte - roll_dte, 1)
        leaps_decay_to_roll = max(leaps_mark - roll_mark, 0.0)
        leaps_decay_daily = leaps_decay_to_roll / days_to_roll
    except Exception:
        roll_mark = 0.0
        days_to_roll = 0
        leaps_decay_to_roll = 0.0
        leaps_decay_daily = 0.0

    net_full_credit_daily = full_credit_daily - leaps_decay_daily
    net_current_profit_daily = current_profit_daily - leaps_decay_daily
    net_harvest_daily_if_today = harvest_profit_daily_if_today - leaps_decay_daily

    return {
        "short_open_date": short_open_date.isoformat(),
        "days_held": days_held,
        "short_open_dte": short_open_dte,
        "short_credit": short_credit,
        "short_mark": short_mark,
        "current_short_profit": current_short_profit,
        "harvest_profit": harvest_profit,
        "harvest_mark": harvest_mark,
        "full_credit_daily": full_credit_daily,
        "current_profit_daily": current_profit_daily,
        "harvest_profit_daily_if_today": harvest_profit_daily_if_today,
        "floor_target_daily": target_floor,
        "good_target_daily": target_good,
        "strong_target_daily": target_strong,
        "floor_days_covered": floor_days_covered,
        "good_days_covered": good_days_covered,
        "strong_days_covered": strong_days_covered,
        "wait_floor_days_after_harvest": wait_floor,
        "wait_good_days_after_harvest": wait_good,
        "wait_strong_days_after_harvest": wait_strong,
        "leaps_decay_daily": leaps_decay_daily,
        "leaps_decay_to_roll": leaps_decay_to_roll,
        "leaps_mark_at_roll_dte": roll_mark,
        "roll_dte_for_decay": roll_dte,
        "days_to_roll_dte": days_to_roll,
        "net_full_credit_daily": net_full_credit_daily,
        "net_current_profit_daily": net_current_profit_daily,
        "net_harvest_daily_if_today": net_harvest_daily_if_today,
        "full_credit_pace_label": classify_daily_pace(full_credit_daily),
        "current_profit_pace_label": classify_daily_pace(current_profit_daily),
        "harvest_pace_label_if_today": classify_daily_pace(harvest_profit_daily_if_today),
    }


def reentry_candidates(
    spot_now: float,
    pair: PmccPair,
    *,
    dte: int = 60,
    iv: float | None = None,
    r: float = 0.04,
) -> list[dict]:
    """Model next-short candidates around the current safe range."""
    iv = float(iv or pair.short_iv or 0.45)
    strikes = sorted(set(
        [round(x / 5) * 5 for x in [spot_now * m for m in (1.15, 1.18, 1.20, 1.23, 1.25, 1.30)]]
        + [480, 490, 500, 510, 520, 530, 540, 550]
    ))
    out = []
    for strike in strikes:
        if strike <= pair.leaps_strike:
            continue
        T = dte / 365.0
        try:
            price = pricing.price(spot_now, strike, T, iv, "call", r=r) * 100
            delta = pricing.delta(spot_now, strike, T, iv, "call", r=r)
        except Exception:
            continue
        upside_pct = (strike / spot_now - 1) * 100
        daily = price / dte
        if upside_pct < 15:
            risk = "too tight"
        elif upside_pct < 20:
            risk = "aggressive"
        elif upside_pct < 28:
            risk = "balanced"
        else:
            risk = "wide"
        if daily < 10:
            income = "low"
        elif daily < 15:
            income = "carry"
        elif daily < 20:
            income = "good"
        else:
            income = "strong"
        out.append({
            "strike": float(strike),
            "dte": dte,
            "credit": price,
            "daily": daily,
            "delta": delta,
            "upside_pct": upside_pct,
            "risk": risk,
            "income": income,
        })
    return out

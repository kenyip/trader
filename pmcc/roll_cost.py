from __future__ import annotations

import pricing


def _call_px(S: float, K: float, dte: int, iv: float, r: float) -> float:
    if dte <= 0:
        return max(S - K, 0.0)
    return max(pricing.price(S, K, dte / 365.0, iv, "call", r=r), 0.0)


def estimate_challenge_roll(
    *,
    spot_entry: float,
    leaps_strike: float,
    short_strike: float,
    short_dte: int,
    short_iv: float,
    short_credit: float,
    challenge_day_frac: float = 0.5,
    roll_dte: int = 75,
    roll_delta_target: float = 0.30,
    r: float = 0.04,
) -> dict:
    """Model first rip to short strike: close short + roll up/out."""
    challenge_spot = short_strike
    days_in = max(int(short_dte * challenge_day_frac), 1)
    short_dte_left = max(short_dte - days_in, 1)

    short_close_px = _call_px(challenge_spot, short_strike, short_dte_left, short_iv, r)
    short_close = short_close_px * 100.0

    # Reopen meaningful upside (not a token $20 bump) — ~8% above challenge or +$35
    roll_strike = pricing.round_strike(
        max(challenge_spot * 1.08, short_strike + 35, leaps_strike + 10),
        5.0,
    )
    roll_iv = short_iv * 0.98
    roll_px = _call_px(challenge_spot, roll_strike, roll_dte, roll_iv, r)
    roll_credit = roll_px * 0.97 * 100.0

    net_roll_cost = short_close - roll_credit
    roll_tax_ratio = net_roll_cost / short_credit if short_credit > 0 else 99.0
    roll_recovery = roll_credit / short_close if short_close > 0 else 0.0
    first_cycle_net_after_roll = short_credit - net_roll_cost
    challenge_pct = (short_strike - spot_entry) / spot_entry if spot_entry > 0 else 0.0

    return {
        "challenge_spot": challenge_spot,
        "challenge_pct": challenge_pct,
        "challenge_days_in": days_in,
        "short_close_at_challenge": short_close,
        "roll_strike": roll_strike,
        "roll_dte": roll_dte,
        "roll_credit_est": roll_credit,
        "net_roll_cost": net_roll_cost,
        "roll_tax_ratio": roll_tax_ratio,
        "roll_recovery": roll_recovery,
        "first_cycle_net_after_roll": first_cycle_net_after_roll,
    }


def estimate_drop_scenario(
    *,
    spot_entry: float,
    short_strike: float,
    short_dte: int,
    short_iv: float,
    short_credit: float,
    drop_pct: float = -0.10,
    challenge_day_frac: float = 0.5,
    r: float = 0.04,
) -> dict:
    """Short-leg win if spot drops mid-cycle."""
    spot_drop = spot_entry * (1.0 + drop_pct)
    days_in = max(int(short_dte * challenge_day_frac), 1)
    short_dte_left = max(short_dte - days_in, 1)
    short_close = _call_px(spot_drop, short_strike, short_dte_left, short_iv, r) * 100.0
    drop_short_profit = short_credit - short_close
    drop_profit_ratio = drop_short_profit / short_credit if short_credit > 0 else 0.0
    return {
        "drop_pct": drop_pct,
        "drop_spot": spot_drop,
        "drop_short_close": short_close,
        "drop_short_profit": drop_short_profit,
        "drop_profit_ratio": drop_profit_ratio,
    }
from __future__ import annotations

import pricing
from pmcc.roll_cost import _call_px


def simulate_path_to_target(
    *,
    spot_entry: float,
    target_spot: float,
    leaps_strike: float,
    short_strike: float,
    short_dte: int,
    short_iv: float,
    short_credit: float,
    roll_dte: int = 75,
    challenge_day_frac: float = 0.5,
    r: float = 0.04,
    max_rolls: int = 8,
) -> dict:
    """Estimate short-leg economics if spot grinds up to target."""
    if target_spot <= short_strike:
        return {
            "rolls_to_target": 0,
            "path_short_net": short_credit,
            "final_short_cap": short_strike,
            "clears_target": True,
            "target_spot": target_spot,
        }

    cumulative = short_credit
    cap = short_strike
    rolls = 0
    days_in = max(int(short_dte * challenge_day_frac), 1)
    dte_left = max(short_dte - days_in, 1)

    while cap < target_spot and rolls < max_rolls:
        spot = cap
        close_cost = _call_px(spot, cap, dte_left, short_iv, r) * 100.0
        roll_k = pricing.round_strike(max(spot * 1.08, cap + 35, leaps_strike + 10), 5.0)
        roll_cred = _call_px(spot, roll_k, roll_dte, short_iv * 0.98, r) * 0.97 * 100.0
        cumulative += roll_cred - close_cost
        cap = roll_k
        rolls += 1

    return {
        "rolls_to_target": rolls,
        "path_short_net": cumulative,
        "final_short_cap": cap,
        "clears_target": cap >= target_spot,
        "target_spot": target_spot,
    }
"""Strategy DNA — free hypothesis representation (not just a symbol).

A strategy is:
  structure + symbols + entry plan (what to buy/sell) + exit/management plan
  + optional sim evidence.

Seed TSLA/TSLL short-premium configs are *starting genes*, not the ceiling.
Evolve ticks mutate DNA within safe numeric bounds and re-sim. They do **not**
auto-edit strategies.py / live.py (code patches stay Ken-gated).
"""

from __future__ import annotations

import copy
import hashlib
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# Numeric mutation bounds for StrategyConfig-compatible knobs.
BOUNDS: dict[str, tuple[float, float]] = {
    "iv_rank_min": (0.0, 40.0),
    # Single-leg: min credit / strike. PCS (put_credit_spread): min credit / width.
    "min_credit_pct": (0.004, 0.50),
    "long_target_delta": (0.08, 0.35),
    "long_dte": (3, 45),
    "short_target_delta": (0.10, 0.35),
    "short_dte": (2, 14),
    "bear_dte": (0, 14),  # 0 = disabled bear call branch
    "bear_target_delta": (0.10, 0.35),
    "profit_target": (0.25, 0.80),
    # Single-leg: multiple of credit.
    "max_loss_mult": (1.2, 12.0),
    # PCS only: exit when loss reaches this fraction of defined max loss.
    "defined_loss_exit_frac": (0.3, 1.0),
    "delta_breach": (0.25, 0.60),
    "dte_stop": (3, 30),
    "dte_stop_min_entry": (5, 21),
    "daily_capture_mult_short": (0.75, 3.0),
    "daily_capture_mult_mid": (0.75, 2.5),
    "daily_capture_mult_long": (0.75, 2.5),
    "cc_dte": (5, 30),
    "cc_target_delta": (0.15, 0.45),
    "wheel_put_dte": (3, 21),
    "wheel_put_max_loss_mult": (1.5, 12.0),
    "roll_dte": (5, 30),
    "roll_target_delta": (0.08, 0.30),
    "roll_credit_ratio": (0.7, 1.3),
    "max_rolls_per_group": (0, 3),
    "max_chain_loss_mult": (1.0, 5.0),
    # Defined-risk vertical (put credit spread)
    "spread_width": (0.5, 15.0),
    "far_wing_width": (1.0, 15.0),
    "max_loss_budget_usd": (50.0, 500.0),
    "front_iv_multiplier": (0.75, 1.25),
    "back_iv_multiplier": (0.75, 1.25),
    "put_skew_per_moneyness": (0.0, 1.0),
    "diagonal_short_dte": (7, 30),
    "diagonal_long_dte": (35, 120),
    "diagonal_short_delta": (0.10, 0.40),
    "diagonal_long_delta": (0.55, 0.90),
    "debit_long_delta": (0.40, 0.75),
    "collar_put_delta": (0.10, 0.40),
    "collar_call_delta": (0.10, 0.40),
}

# Catalog of structure templates. Each is a full trade plan skeleton.
# Single-leg structures map to StrategyConfig + pick_entry/check_exits.
# Defined-risk multi-leg (pcs_sim): put_credit_spread, call_credit_spread, iron_condor.
# Catalog is intentionally broader than wheel/PMCC — Ken freedom pin.
STRUCTURE_CATALOG: dict[str, dict[str, Any]] = {
    "regime_short_premium": {
        "description": "Sell OTM put (bull/neutral) or call (bear if enabled); stand aside on thin credit",
        "entry_plan": {
            "side_policy": "regime_directed",
            "legs": [{"action": "sell", "right": "put_or_call_by_regime", "qty": 1}],
            "filters": ["iv_rank_min", "min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "delta_breach", "dte_stop", "regime_flip"],
            "management": ["optional_roll", "optional_wheel"],
        },
        "config_seed": {
            "long_dte": 7,
            "long_target_delta": 0.20,
            "min_credit_pct": 0.010,
            "delta_breach": 0.45,
            "profit_target": 0.55,
            "max_loss_mult": 1.8,
            "bear_dte": 3,
            "bear_target_delta": 0.20,
            "regime_flip_exit_enabled": True,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
    },
    "short_put_credit": {
        "description": "Bullish/neutral short put premium (bear branch off)",
        "entry_plan": {
            "side_policy": "prefer_put",
            "legs": [{"action": "sell", "right": "put", "qty": 1}],
            "filters": ["iv_rank_min", "min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "delta_breach", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 14,
            "long_target_delta": 0.18,
            "min_credit_pct": 0.012,
            "delta_breach": 0.40,
            "profit_target": 0.50,
            "max_loss_mult": 2.0,
            "bear_dte": 0,  # no short-call in bear
            "regime_flip_exit_enabled": True,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
    },
    "short_dte_aggressive": {
        "description": "Short-dated higher-delta premium harvest",
        "entry_plan": {
            "side_policy": "regime_directed",
            "legs": [{"action": "sell", "right": "put_or_call_by_regime", "qty": 1}],
            "filters": ["min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "delta_breach"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 3,
            "long_target_delta": 0.28,
            "short_dte": 3,
            "short_target_delta": 0.28,
            "min_credit_pct": 0.012,
            "delta_breach": 0.50,
            "profit_target": 0.45,
            "max_loss_mult": 2.5,
            "daily_capture_mult_short": 2.0,
            "bear_dte": 3,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
    },
    "long_dte_conservative": {
        "description": "Longer DTE lower delta; patient premium",
        "entry_plan": {
            "side_policy": "regime_directed",
            "legs": [{"action": "sell", "right": "put_or_call_by_regime", "qty": 1}],
            "filters": ["iv_rank_min", "min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "delta_breach", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 30,
            "long_target_delta": 0.12,
            "min_credit_pct": 0.008,
            "delta_breach": 0.35,
            "profit_target": 0.60,
            "max_loss_mult": 1.6,
            "dte_stop": 14,
            "bear_dte": 7,
            "regime_flip_exit_enabled": True,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
    },
    "wheel_assignment": {
        "description": "Accept put assignment; cycle covered calls",
        "entry_plan": {
            "side_policy": "prefer_put",
            "legs": [
                {"action": "sell", "right": "put", "qty": 1},
                {"action": "sell", "right": "call", "qty": 1, "when": "assigned"},
            ],
            "filters": ["min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "wheel_cycle"],
            "management": ["wheel"],
        },
        "config_seed": {
            "long_dte": 14,
            "long_target_delta": 0.22,
            "min_credit_pct": 0.010,
            "max_loss_mult": 3.0,
            "wheel_enabled": True,
            "wheel_put_dte": 14,
            "wheel_put_max_loss_mult": 3.0,
            "wheel_skip_regime_flip": True,
            "cc_dte": 14,
            "cc_target_delta": 0.30,
            "cc_strike_mode": "basis",
            "bear_dte": 0,
            "roll_on_max_loss": False,
            "regime_flip_exit_enabled": False,
        },
    },
    "put_credit_spread": {
        "description": (
            "Defined-risk bull put vertical: sell OTM put + buy further OTM put. "
            "max_loss_usd=(width-credit)*100; BP≈max_loss. Fits $3k open-risk when width small."
        ),
        "entry_plan": {
            "side_policy": "prefer_put",
            "legs": [
                {"action": "sell", "right": "put", "qty": 1, "role": "short"},
                {"action": "buy", "right": "put", "qty": 1, "role": "long_protection"},
            ],
            "filters": ["iv_rank_min", "min_credit_pct_of_width", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_defined_loss", "delta_breach", "dte_stop", "regime_flip"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 14,
            "long_target_delta": 0.20,
            "spread_width": 2.0,
            "min_credit_pct": 0.18,  # of width
            "profit_target": 0.50,
            "defined_loss_exit_frac": 0.85,
            "max_loss_mult": 2.0,  # unused by pcs_sim; kept for DNA schema compatibility
            "delta_breach": 0.45,
            "dte_stop": 3,
            "iv_rank_min": 0.0,
            "max_loss_budget_usd": 250.0,
            "bear_dte": 0,
            "regime_flip_exit_enabled": True,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "pcs_sim",
    },
    "call_credit_spread": {
        "description": (
            "Defined-risk bear call vertical: sell OTM call + buy further OTM call. "
            "max_loss_usd=(width-credit)*100; BP≈max_loss. Good for bear/neutral or high IV range."
        ),
        "entry_plan": {
            "side_policy": "prefer_call",
            "legs": [
                {"action": "sell", "right": "call", "qty": 1, "role": "short"},
                {"action": "buy", "right": "call", "qty": 1, "role": "long_protection"},
            ],
            "filters": ["iv_rank_min", "min_credit_pct_of_width", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_defined_loss", "delta_breach", "dte_stop", "regime_flip"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 14,
            "long_target_delta": 0.20,
            "spread_width": 2.0,
            "min_credit_pct": 0.18,
            "profit_target": 0.50,
            "defined_loss_exit_frac": 0.85,
            "max_loss_mult": 2.0,
            "delta_breach": 0.45,
            "dte_stop": 3,
            "iv_rank_min": 0.0,
            "max_loss_budget_usd": 250.0,
            "bear_dte": 0,
            "call_in_bull_ok": False,
            "regime_flip_exit_enabled": True,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "pcs_sim",
    },
    "iron_condor": {
        "description": (
            "Defined-risk short iron condor: OTM put credit wing + OTM call credit wing. "
            "Collect both sides; max_loss≈max(wing_width)-total_credit. Neutral/high-IV range structure."
        ),
        "entry_plan": {
            "side_policy": "range_bound",
            "legs": [
                {"action": "sell", "right": "put", "qty": 1, "role": "short_put"},
                {"action": "buy", "right": "put", "qty": 1, "role": "long_put"},
                {"action": "sell", "right": "call", "qty": 1, "role": "short_call"},
                {"action": "buy", "right": "call", "qty": 1, "role": "long_call"},
            ],
            "filters": ["iv_rank_min", "min_credit_pct_of_width", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_defined_loss", "delta_breach", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 21,
            "long_target_delta": 0.16,
            "spread_width": 2.0,
            "min_credit_pct": 0.14,
            "profit_target": 0.50,
            "defined_loss_exit_frac": 0.80,
            "max_loss_mult": 2.0,
            "delta_breach": 0.40,
            "dte_stop": 5,
            "iv_rank_min": 15.0,
            "max_loss_budget_usd": 300.0,
            "bear_dte": 1,
            "call_in_bull_ok": True,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "pcs_sim",
    },
    "iron_butterfly": {
        "description": (
            "Defined-risk credit iron butterfly: buy OTM put/call wings and sell the ATM straddle. "
            "Max loss is symmetric wing width minus credit; research-only BS same-expiry scaffold."
        ),
        "entry_plan": {
            "side_policy": "neutral_pin_credit",
            "legs": [
                {"action": "buy", "right": "put", "qty": 1, "role": "lower_wing"},
                {"action": "sell", "right": "put", "qty": 1, "role": "short_body_put"},
                {"action": "sell", "right": "call", "qty": 1, "role": "short_body_call"},
                {"action": "buy", "right": "call", "qty": 1, "role": "upper_wing"},
            ],
            "filters": ["neutral_regime", "iv_rank_min", "min_credit_pct_of_width", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_defined_loss", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 21,
            "spread_width": 2.0,
            "min_credit_pct": 0.25,
            "iv_rank_min": 20.0,
            "profit_target": 0.40,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "iron_butterfly_sim",
    },
    "broken_wing_iron_butterfly": {
        "description": (
            "Defined-risk bullish broken-wing credit iron butterfly: sell the ATM straddle, "
            "buy a wider put wing and a narrower call wing. Max loss is the wider wing minus credit."
        ),
        "entry_plan": {
            "side_policy": "bullish_not_bearish_credit",
            "legs": [
                {"action": "buy", "right": "put", "qty": 1, "role": "wide_lower_wing"},
                {"action": "sell", "right": "put", "qty": 1, "role": "short_body_put"},
                {"action": "sell", "right": "call", "qty": 1, "role": "short_body_call"},
                {"action": "buy", "right": "call", "qty": 1, "role": "narrow_upper_wing"},
            ],
            "filters": ["not_bearish", "iv_rank_min", "min_credit_pct_of_wide_wing", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_defined_loss", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 21,
            "spread_width": 1.0,
            "far_wing_width": 2.0,
            "min_credit_pct": 0.18,
            "iv_rank_min": 15.0,
            "profit_target": 0.40,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "iron_butterfly_sim",
    },
    "put_ratio_backspread": {
        "description": (
            "Defined-risk bearish 1x2 put ratio backspread: sell one higher-strike put and buy two "
            "lower-strike puts. Worst loss is the strike width plus entry debit at the long strike."
        ),
        "entry_plan": {
            "side_policy": "bearish_convexity",
            "legs": [
                {"action": "sell", "right": "put", "qty": 1, "role": "higher_short"},
                {"action": "buy", "right": "put", "qty": 2, "role": "lower_crash_wing"},
            ],
            "filters": ["not_bullish", "iv_rank_min", "max_loss_budget_usd"],
        },
        "exit_plan": {"ladder": ["profit_target", "max_defined_loss", "dte_stop"], "management": []},
        "config_seed": {
            "long_dte": 21,
            "short_target_delta": 0.30,
            "spread_width": 1.0,
            "iv_rank_min": 0.0,
            "profit_target": 0.50,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "put_ratio_backspread_sim",
    },
    "calendar_spread": {
        "description": (
            "Long same-strike put calendar: buy back-month put and sell front-month put. "
            "Debit paid is the defined 1-lot max loss; research-only BS daily-bar scaffold."
        ),
        "entry_plan": {
            "side_policy": "time_decay_neutral_to_bullish",
            "legs": [
                {"action": "sell", "right": "put", "qty": 1, "role": "front_month"},
                {"action": "buy", "right": "put", "qty": 1, "role": "back_month"},
            ],
            "filters": ["iv_rank_min", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "defined_loss", "front_expiry"],
            "management": [],
        },
        "config_seed": {
            "short_dte": 14,
            "long_dte": 35,
            "long_target_delta": 0.30,
            "iv_rank_min": 0.0,
            "profit_target": 0.30,
            "defined_loss_exit_frac": 0.65,
            "dte_stop": 0,
            "max_loss_budget_usd": 300.0,
            "front_iv_multiplier": 1.05,
            "back_iv_multiplier": 0.95,
            "put_skew_per_moneyness": 0.25,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "calendar_sim",
    },
    "diagonal_spread": {
        "description": (
            "Long call diagonal: buy a back-month higher-delta call and sell a front-month "
            "lower-delta call. Debit is defined 1-lot max loss; research-only BS scaffold "
            "with an opt-in, provider-dependent dividend assignment guard."
        ),
        "entry_plan": {
            "side_policy": "bullish_time_decay",
            "legs": [
                {"action": "buy", "right": "call", "qty": 1, "role": "back_month_long"},
                {"action": "sell", "right": "call", "qty": 1, "role": "front_month_short"},
            ],
            "filters": ["not_bearish", "iv_rank_min", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": [
                "early_assignment_risk",
                "profit_target",
                "defined_loss",
                "short_expiry",
            ],
            "management": [],
            "limitations": [
                "dividend_events_provider_dependent",
                "honest_known_at_required",
                "non_dividend_assignment_unmodeled",
            ],
        },
        "config_seed": {
            "diagonal_short_dte": 14,
            "diagonal_long_dte": 60,
            "diagonal_short_delta": 0.25,
            "diagonal_long_delta": 0.70,
            "iv_rank_min": 0.0,
            "profit_target": 0.30,
            "defined_loss_exit_frac": 0.65,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "front_iv_multiplier": 1.05,
            "back_iv_multiplier": 0.95,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "diagonal_sim",
    },
    "butterfly_spread": {
        "description": (
            "Long symmetric call butterfly: buy lower call, sell two middle calls, buy upper call. "
            "Debit is defined 1-lot max loss; research-only BS same-expiry scaffold."
        ),
        "entry_plan": {
            "side_policy": "neutral_to_bullish_pin",
            "legs": [
                {"action": "buy", "right": "call", "qty": 1, "role": "lower_wing"},
                {"action": "sell", "right": "call", "qty": 2, "role": "body"},
                {"action": "buy", "right": "call", "qty": 1, "role": "upper_wing"},
            ],
            "filters": ["not_bearish", "iv_rank_min", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "defined_loss", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 21,
            "long_target_delta": 0.35,
            "spread_width": 1.0,
            "iv_rank_min": 0.0,
            "profit_target": 0.40,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "butterfly_sim",
    },
    "bull_call_debit_spread": {
        "description": (
            "Defined-debit bullish call vertical: buy a call and sell a higher-strike call. "
            "Debit is the 1-lot max loss; research-only BS same-expiry scaffold with an "
            "opt-in, provider-dependent dividend assignment guard."
        ),
        "entry_plan": {
            "side_policy": "bullish_not_bearish",
            "legs": [
                {"action": "buy", "right": "call", "qty": 1, "role": "long"},
                {"action": "sell", "right": "call", "qty": 1, "role": "short_cap"},
            ],
            "filters": ["not_bearish", "iv_rank_min", "max_loss_budget_usd"],
        },
        "exit_plan": {
            "ladder": [
                "early_assignment_risk",
                "profit_target",
                "defined_loss",
                "dte_stop",
            ],
            "management": [],
            "limitations": [
                "dividend_events_provider_dependent",
                "honest_known_at_required",
                "non_dividend_assignment_unmodeled",
            ],
        },
        "config_seed": {
            "long_dte": 21,
            "debit_long_delta": 0.55,
            "spread_width": 2.0,
            "iv_rank_min": 0.0,
            "profit_target": 0.50,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "debit_vertical_sim",
    },
    "bear_put_debit_spread": {
        "description": (
            "Defined-debit bearish put vertical: buy a put and sell a lower-strike put. "
            "Debit is the 1-lot max loss; research-only BS same-expiry scaffold."
        ),
        "entry_plan": {
            "side_policy": "bearish_not_bullish",
            "legs": [
                {"action": "buy", "right": "put", "qty": 1, "role": "long"},
                {"action": "sell", "right": "put", "qty": 1, "role": "short_cap"},
            ],
            "filters": ["not_bullish", "iv_rank_min", "max_loss_budget_usd"],
        },
        "exit_plan": {"ladder": ["profit_target", "defined_loss", "dte_stop"], "management": []},
        "config_seed": {
            "long_dte": 21,
            "debit_long_delta": 0.55,
            "spread_width": 2.0,
            "iv_rank_min": 0.0,
            "profit_target": 0.50,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "debit_vertical_sim",
    },
    "collared_covered_call": {
        "description": (
            "Paper-only collared covered-call: long 100 shares + long protective put + short call. "
            "capital_fit_usd=full share notional (+ net option debit); max_loss is downside floor "
            "to put strike. Non-levered names with spot*100≤sleeve only — never default TSLL share-hold."
        ),
        "entry_plan": {
            "side_policy": "bullish_income_collar",
            "legs": [
                {"action": "buy", "right": "stock", "qty": 100, "role": "shares"},
                {"action": "buy", "right": "put", "qty": 1, "role": "protective_put"},
                {"action": "sell", "right": "call", "qty": 1, "role": "covered_call"},
            ],
            "filters": [
                "non_levered",
                "share_lot_fits_sleeve",
                "not_bearish",
                "iv_rank_min",
                "max_loss_budget_usd",
            ],
        },
        "exit_plan": {
            "ladder": ["profit_target", "defined_loss", "dte_stop"],
            "management": [],
            "limitations": ["dividends_unmodeled", "early_assignment_unmodeled"],
        },
        "config_seed": {
            "long_dte": 21,
            "collar_put_delta": 0.25,
            "collar_call_delta": 0.25,
            "iv_rank_min": 0.0,
            "profit_target": 0.40,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
            "regime_flip_exit_enabled": False,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
        "sim_engine": "collar_sim",
    },
    "short_call_credit": {
        "description": "Bearish/neutral short call premium (single-leg; undefined risk)",
        "entry_plan": {
            "side_policy": "prefer_call",
            "legs": [{"action": "sell", "right": "call", "qty": 1}],
            "filters": ["iv_rank_min", "min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "delta_breach", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 14,
            "long_target_delta": 0.18,
            "short_dte": 14,
            "short_target_delta": 0.18,
            "min_credit_pct": 0.012,
            "delta_breach": 0.40,
            "profit_target": 0.50,
            "max_loss_mult": 2.0,
            "bear_dte": 14,
            "bear_target_delta": 0.18,
            "regime_flip_exit_enabled": True,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
    },
    "cash_secured_put": {
        "description": "Cash-secured short put (single-leg CSP; undefined risk, cash collateral)",
        "entry_plan": {
            "side_policy": "prefer_put",
            "legs": [{"action": "sell", "right": "put", "qty": 1}],
            "filters": ["iv_rank_min", "min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "delta_breach", "dte_stop"],
            "management": [],
        },
        "config_seed": {
            "long_dte": 21,
            "long_target_delta": 0.16,
            "min_credit_pct": 0.010,
            "delta_breach": 0.38,
            "profit_target": 0.55,
            "max_loss_mult": 2.2,
            "bear_dte": 0,
            "regime_flip_exit_enabled": True,
            "wheel_enabled": False,
            "roll_on_max_loss": False,
        },
    },
    "roll_defend": {
        "description": "Short premium with credit roll on max loss",
        "entry_plan": {
            "side_policy": "regime_directed",
            "legs": [{"action": "sell", "right": "put_or_call_by_regime", "qty": 1}],
            "filters": ["min_credit_pct"],
        },
        "exit_plan": {
            "ladder": ["profit_target", "max_loss_mult", "delta_breach"],
            "management": ["roll_on_max_loss"],
        },
        "config_seed": {
            "long_dte": 10,
            "long_target_delta": 0.18,
            "min_credit_pct": 0.010,
            "max_loss_mult": 1.8,
            "delta_breach": 0.42,
            "roll_on_max_loss": True,
            "roll_dte": 14,
            "roll_target_delta": 0.15,
            "roll_credit_ratio": 1.0,
            "max_rolls_per_group": 1,
            "max_chain_loss_mult": 2.0,
            "wheel_enabled": False,
            "bear_dte": 3,
        },
    },
}


def _clamp(key: str, val: Any) -> Any:
    if key not in BOUNDS:
        return val
    lo, hi = BOUNDS[key]
    if isinstance(lo, int) and isinstance(hi, int) and not isinstance(val, bool):
        try:
            return int(max(lo, min(hi, int(round(float(val))))))
        except (TypeError, ValueError):
            return int(lo)
    try:
        return float(max(lo, min(hi, float(val))))
    except (TypeError, ValueError):
        return lo


@dataclass
class StrategyDNA:
    """Portable strategy genome used by evolve/learn/promote."""

    structure: str
    symbols: list[str] = field(default_factory=list)
    entry_plan: dict[str, Any] = field(default_factory=dict)
    exit_plan: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    parent_id: str = ""
    generation: int = 0
    dna_id: str = ""
    notes: str = ""
    last_sim: dict[str, Any] = field(default_factory=dict)

    def ensure_id(self) -> str:
        if self.dna_id:
            return self.dna_id
        blob = f"{self.structure}|{sorted(self.symbols)}|{sorted(self.config.items())}"
        self.dna_id = "dna_" + hashlib.sha1(blob.encode()).hexdigest()[:12]
        return self.dna_id

    def to_dict(self) -> dict[str, Any]:
        self.ensure_id()
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Optional["StrategyDNA"]:
        if not d or not isinstance(d, dict):
            return None
        data = dict(d)
        data.setdefault("symbols", [])
        data.setdefault("entry_plan", {})
        data.setdefault("exit_plan", {})
        data.setdefault("config", {})
        data.setdefault("parent_id", "")
        data.setdefault("generation", 0)
        data.setdefault("dna_id", "")
        data.setdefault("notes", "")
        data.setdefault("last_sim", {})
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    def uses_pcs_sim(self) -> bool:
        """True when DNA uses defined-risk multi-leg pcs_sim (PCS/CCS/iron)."""
        if self.structure in {"put_credit_spread", "call_credit_spread", "iron_condor"}:
            return True
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "pcs_sim"

    def uses_calendar_sim(self) -> bool:
        """True when DNA uses the defined-debit calendar simulator."""
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "calendar_sim"

    def uses_diagonal_sim(self) -> bool:
        """True when DNA uses the defined-debit diagonal simulator."""
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "diagonal_sim"

    def uses_butterfly_sim(self) -> bool:
        """True when DNA uses the defined-debit butterfly simulator."""
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "butterfly_sim"

    def uses_iron_butterfly_sim(self) -> bool:
        """True when DNA uses the defined-risk credit iron-butterfly simulator."""
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "iron_butterfly_sim"

    def uses_put_ratio_backspread_sim(self) -> bool:
        """True when DNA uses the defined-risk 1x2 put ratio simulator."""
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "put_ratio_backspread_sim"

    def uses_debit_vertical_sim(self) -> bool:
        """True when DNA uses the defined-debit vertical simulator."""
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "debit_vertical_sim"

    def uses_collar_sim(self) -> bool:
        """True when DNA uses the collared covered-call (stock+put+call) simulator."""
        tmpl = STRUCTURE_CATALOG.get(self.structure) or {}
        return str(tmpl.get("sim_engine") or "") == "collar_sim"

    def config_overrides(self) -> dict[str, Any]:
        """Map DNA → StrategyConfig kwargs (safe subset only).

        PCS-only knobs are excluded — they are not StrategyConfig fields;
        pcs_sim reads dna.config / pcs_config() directly.
        """
        # defined_loss_exit_frac lives in BOUNDS for mutation but is PCS-sim only.
        pcs_only = {"spread_width", "max_loss_budget_usd", "defined_loss_exit_frac"}
        out: dict[str, Any] = {}
        for k, v in (self.config or {}).items():
            if k in pcs_only:
                continue
            if k in BOUNDS or k in {
                "regime_flip_exit_enabled",
                "wheel_enabled",
                "wheel_skip_regime_flip",
                "roll_on_max_loss",
                "cc_strike_mode",
            }:
                if k in BOUNDS:
                    out[k] = _clamp(k, v)
                else:
                    out[k] = v
        # adaptive rule names not auto-mutated (code-bound); pass through if present
        if "adaptive_rules" in (self.config or {}):
            out["adaptive_rules"] = tuple(self.config["adaptive_rules"] or ())
        if "exit_rules" in (self.config or {}):
            out["exit_rules"] = tuple(self.config["exit_rules"] or ())
        return out

    def pcs_config(self) -> dict[str, Any]:
        """Full config dict for pcs_sim (clamped DNA knobs)."""
        out: dict[str, Any] = {}
        for k, v in (self.config or {}).items():
            if k in BOUNDS:
                out[k] = _clamp(k, v)
            else:
                out[k] = v
        return out

    def sim_config(self) -> dict[str, Any]:
        """Full clamped config for non-StrategyConfig research simulators."""
        return self.pcs_config()

    def thesis_text(self) -> str:
        legs = (self.entry_plan or {}).get("legs") or []
        exit_l = (self.exit_plan or {}).get("ladder") or []
        mgmt = (self.exit_plan or {}).get("management") or []
        cfg = self.config or {}
        extra = ""
        if self.structure in {
            "put_credit_spread",
            "call_credit_spread",
            "iron_condor",
            "iron_butterfly",
            "put_ratio_backspread",
            "butterfly_spread",
            "bull_call_debit_spread",
            "bear_put_debit_spread",
        } or cfg.get("spread_width") is not None:
            extra = (
                f" width={cfg.get('spread_width')}, max_loss_budget_usd={cfg.get('max_loss_budget_usd')},"
            )
        return (
            f"Structure={self.structure}. Symbols={','.join(self.symbols) or 'TBD'}. "
            f"Entry: side_policy={(self.entry_plan or {}).get('side_policy')}, "
            f"legs={legs}, dte={cfg.get('long_dte')}, delta={cfg.get('long_target_delta')}, "
            f"min_credit_pct={cfg.get('min_credit_pct')},{extra} "
            f"Exit ladder={exit_l}; management={mgmt}; "
            f"profit_target={cfg.get('profit_target')}, max_loss_mult={cfg.get('max_loss_mult')}, "
            f"delta_breach={cfg.get('delta_breach')}. "
            f"PAPER/SIM ONLY — never auto-live."
        )


def dna_from_structure(
    structure: str,
    symbols: list[str],
    *,
    parent_id: str = "",
    generation: int = 0,
    config_overrides: Optional[dict[str, Any]] = None,
) -> StrategyDNA:
    if structure not in STRUCTURE_CATALOG:
        raise ValueError(f"unknown structure {structure!r}; catalog={sorted(STRUCTURE_CATALOG)}")
    tmpl = STRUCTURE_CATALOG[structure]
    cfg = copy.deepcopy(tmpl["config_seed"])
    if config_overrides:
        for k, v in config_overrides.items():
            cfg[k] = _clamp(k, v) if k in BOUNDS else v
    dna = StrategyDNA(
        structure=structure,
        symbols=[s.upper() for s in symbols],
        entry_plan=copy.deepcopy(tmpl["entry_plan"]),
        exit_plan=copy.deepcopy(tmpl["exit_plan"]),
        config=cfg,
        parent_id=parent_id,
        generation=generation,
        notes=str(tmpl.get("description") or ""),
    )
    dna.ensure_id()
    return dna


def mutate_dna(
    dna: StrategyDNA,
    *,
    rng: Optional[random.Random] = None,
    n_knobs: int = 3,
    scale: float = 0.25,
) -> StrategyDNA:
    """Return a child DNA with n_knobs numeric fields jittered within BOUNDS."""
    r = rng or random.Random()
    child = StrategyDNA.from_dict(dna.to_dict())
    assert child is not None
    child.parent_id = dna.dna_id or dna.ensure_id()
    child.generation = int(dna.generation or 0) + 1
    child.dna_id = ""  # recompute after mutation
    child.last_sim = {}

    keys = [k for k in child.config.keys() if k in BOUNDS]
    if not keys:
        keys = list(BOUNDS.keys())[:8]
        for k in keys:
            lo, hi = BOUNDS[k]
            child.config[k] = (lo + hi) / 2.0
    pick = r.sample(keys, k=min(n_knobs, len(keys)))
    for k in pick:
        lo, hi = BOUNDS[k]
        cur = float(child.config.get(k, (lo + hi) / 2.0))
        span = (hi - lo) * scale
        child.config[k] = _clamp(k, cur + r.uniform(-span, span))
    # occasional management / structure exploration (do NOT monomania wheel)
    if r.random() < 0.06:
        child.config["wheel_enabled"] = not bool(child.config.get("wheel_enabled"))
        if child.config["wheel_enabled"]:
            child.structure = "wheel_assignment"
            child.exit_plan = copy.deepcopy(STRUCTURE_CATALOG["wheel_assignment"]["exit_plan"])
            child.entry_plan = copy.deepcopy(STRUCTURE_CATALOG["wheel_assignment"]["entry_plan"])
    if r.random() < 0.12:
        # hop among defined-risk multi-leg structures when already multi-leg-ish
        defined = ["put_credit_spread", "call_credit_spread", "iron_condor"]
        if child.structure in defined or r.random() < 0.35:
            st = r.choice(defined)
            tmpl = STRUCTURE_CATALOG[st]
            child.structure = st
            child.entry_plan = copy.deepcopy(tmpl["entry_plan"])
            child.exit_plan = copy.deepcopy(tmpl["exit_plan"])
            for k, v in (tmpl.get("config_seed") or {}).items():
                child.config.setdefault(k, v)
            child.config["wheel_enabled"] = False
    if r.random() < 0.12:
        child.config["roll_on_max_loss"] = not bool(child.config.get("roll_on_max_loss"))
    if r.random() < 0.10:
        child.config["regime_flip_exit_enabled"] = not bool(
            child.config.get("regime_flip_exit_enabled", True)
        )
    child.ensure_id()
    child.notes = f"mutate from {child.parent_id} knobs={pick}"
    return child


def seed_population(
    symbols: list[str],
    *,
    structures: Optional[list[str]] = None,
    rng: Optional[random.Random] = None,
    mutants_per_seed: int = 2,
) -> list[StrategyDNA]:
    """Build a free search population: catalog seeds × symbols + mutations."""
    r = rng or random.Random()
    structs = structures or list(STRUCTURE_CATALOG.keys())
    out: list[StrategyDNA] = []
    for sym in symbols:
        for st in structs:
            base = dna_from_structure(st, [sym])
            out.append(base)
            for _ in range(mutants_per_seed):
                out.append(mutate_dna(base, rng=r))
    return out


def family_to_structure(strategy_family: str) -> str:
    """Map research family hint → catalog structure (starting gene only)."""
    f = (strategy_family or "").lower()
    if "wheel" in f:
        return "wheel_assignment"
    if "iron" in f or "condor" in f:
        return "iron_condor"
    if "call_credit" in f or "bear_call" in f or "call_spread" in f:
        return "call_credit_spread"
    if "put_credit" in f or "put_spread" in f or "bull_put" in f or "pcs" in f:
        return "put_credit_spread"
    if "credit_spread" in f or "vertical" in f or "defined" in f:
        return "put_credit_spread"
    if "strangle" in f:
        return "iron_condor"  # defined-risk stand-in until naked strangle sim exists
    if "csp" in f or "cash_secured" in f:
        return "cash_secured_put"
    if "short_put" in f or "put_trend" in f or "put_cautious" in f:
        return "short_put_credit"
    if "short_call" in f:
        return "short_call_credit"
    if "stand_aside" in f:
        return "regime_short_premium"
    if "rich" in f or "premium" in f:
        return "short_dte_aggressive"
    return "regime_short_premium"

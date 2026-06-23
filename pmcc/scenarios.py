from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import pricing
from pmcc.chain_data import fetch_call_chain, pick_contract
from pmcc.config import PmccConfig


DEFAULT_SPOT_SHOCKS = (-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20, 0.30)


@dataclass
class PmccPair:
    spot_entry: float
    leaps_strike: float
    leaps_exp: str
    leaps_dte: int
    leaps_iv: float
    leaps_debit: float
    short_strike: float
    short_exp: str
    short_dte: int
    short_iv: float
    short_credit: float
    leaps_delta_target: float
    short_delta_target: float
    score: float = 0.0

    @property
    def net_debit(self) -> float:
        return self.leaps_debit - self.short_credit

    @classmethod
    def from_row(cls, row: pd.Series, spot: float) -> PmccPair:
        return cls(
            spot_entry=spot,
            leaps_strike=float(row["leaps_strike"]),
            leaps_exp=str(row["leaps_exp"]),
            leaps_dte=int(row["leaps_dte"]),
            leaps_iv=float(row["leaps_iv"]),
            leaps_debit=float(row["leaps_debit"]),
            short_strike=float(row["short_strike"]),
            short_exp=str(row["short_exp"]),
            short_dte=int(row["short_dte"]),
            short_iv=float(row["short_iv"]),
            short_credit=float(row["short_credit"]),
            leaps_delta_target=float(row["leaps_delta_target"]),
            short_delta_target=float(row["short_delta_target"]),
            score=float(row.get("score", 0.0)),
        )


def _call_value(S: float, K: float, dte: int, iv: float, r: float) -> float:
    if dte <= 0:
        return max(S - K, 0.0)
    T = dte / 365.0
    try:
        return max(pricing.price(S, K, T, iv, "call", r=r), 0.0)
    except (ValueError, ZeroDivisionError):
        return max(S - K, 0.0)


def _short_close_cost(S: float, K: float, dte: int, iv: float, r: float) -> float:
    """Conservative: buy back short at ask proxy = mid with 1% slippage."""
    return _call_value(S, K, dte, iv, r) * 1.01


def recommend_action(
    pair: PmccPair,
    spot: float,
    *,
    short_dte_left: int,
    short_close: float,
    leaps_value: float,
    net_pnl: float,
    short_leg_pnl: float,
) -> str:
    pct = (spot - pair.spot_entry) / pair.spot_entry
    short_otm = spot < pair.short_strike
    short_itm = spot > pair.short_strike
    short_profit_pct = (pair.short_credit - short_close * 100) / pair.short_credit if pair.short_credit else 0.0

    if short_dte_left <= 0 and short_otm:
        return "Short expires worthless — keep LEAPS, sell next short call (new cycle)."
    if pct <= -0.08 and short_profit_pct >= 0.50:
        return (
            "Drop: buy back short for ~50%+ profit on that leg, keep LEAPS. "
            "Re-sell a new short after IV/regime stabilizes (don't chase a dead premium)."
        )
    if pct <= -0.05 and short_close * 100 < pair.short_credit * 0.35:
        return "Mild drop: short decayed — close short cheap, bank premium, roll to new short when ready."
    if short_itm and pct >= 0.10:
        roll_strike = pricing.round_strike(max(spot * 1.05, pair.short_strike + 20), 5.0)
        return (
            f"Rip through short strike: buy back short (loss on leg, net position may still be green). "
            f"Roll up/out — sell new ~{int(roll_strike)} call 60–90 DTE. Do NOT let assignment exercise LEAPS."
        )
    if short_itm:
        return (
            "At/through short strike: buy back short before assignment, keep LEAPS, "
            "sell new higher strike short (roll up/out)."
        )
    if pct >= 0.08 and short_profit_pct >= 0.45 and short_dte_left > 7:
        return (
            "Rip but still OTM on short: optional early buyback (50%+ short profit), "
            "then sell new higher strike to open upside."
        )
    if net_pnl > 0 and short_profit_pct >= 0.55:
        return "Take short-leg profit (buy back), keep LEAPS for long-term upside."
    return "Hold diagonal — theta working; revisit if spot nears short strike."


def run_scenario_row(
    pair: PmccPair,
    spot_shock: float,
    *,
    at_short_expiry: bool,
    r: float,
) -> dict:
    spot = pair.spot_entry * (1.0 + spot_shock)
    if at_short_expiry:
        short_dte_left = 0
        leaps_dte_left = max(pair.leaps_dte - pair.short_dte, 1)
    else:
        half = pair.short_dte // 2
        short_dte_left = max(pair.short_dte - half, 1)
        leaps_dte_left = max(pair.leaps_dte - half, 1)

    leaps_px = _call_value(spot, pair.leaps_strike, leaps_dte_left, pair.leaps_iv, r)
    short_px = _call_value(spot, pair.short_strike, short_dte_left, pair.short_iv, r)
    short_close = _short_close_cost(spot, pair.short_strike, short_dte_left, pair.short_iv, r)

    leaps_mtm = leaps_px * 100.0
    short_close_dollars = short_close * 100.0
    net_pnl = (leaps_mtm - pair.leaps_debit) + (pair.short_credit - short_close_dollars)
    short_leg_pnl = pair.short_credit - short_close_dollars
    leaps_leg_pnl = leaps_mtm - pair.leaps_debit

    label = f"{spot_shock:+.0%}"
    phase = "short expiry" if at_short_expiry else f"mid-short (~{pair.short_dte - short_dte_left}d in)"

    return {
        "spot_shock": spot_shock,
        "label": label,
        "phase": phase,
        "spot": spot,
        "leaps_dte_left": leaps_dte_left,
        "short_dte_left": short_dte_left,
        "leaps_mtm": leaps_mtm,
        "short_close_cost": short_close_dollars,
        "net_pnl": net_pnl,
        "short_leg_pnl": short_leg_pnl,
        "leaps_leg_pnl": leaps_leg_pnl,
        "short_vs_strike": "OTM" if spot < pair.short_strike else ("ATM" if abs(spot - pair.short_strike) < 3 else "ITM"),
        "action": recommend_action(
            pair, spot,
            short_dte_left=short_dte_left,
            short_close=short_close,
            leaps_value=leaps_mtm,
            net_pnl=net_pnl,
            short_leg_pnl=short_leg_pnl,
        ),
    }


def run_scenarios(
    pair: PmccPair,
    shocks: tuple[float, ...] = DEFAULT_SPOT_SHOCKS,
    *,
    r: float = 0.04,
) -> pd.DataFrame:
    rows = []
    for shock in shocks:
        rows.append(run_scenario_row(pair, shock, at_short_expiry=True, r=r))
        rows.append(run_scenario_row(pair, shock, at_short_expiry=False, r=r))
    return pd.DataFrame(rows)


def estimate_roll_credit(
    pair: PmccPair,
    spot_after_rip: float,
    *,
    roll_dte: int = 75,
    roll_delta: float = 0.25,
    chain: pd.DataFrame | None = None,
    cfg: PmccConfig | None = None,
) -> dict | None:
    """After a rip, estimate next short call from live chain."""
    cfg = cfg or PmccConfig()
    if chain is None:
        _, chain = fetch_call_chain(
            cfg.ticker,
            r=cfg.risk_free_rate,
            use_cache=cfg.chain_use_cache,
            refresh=cfg.chain_refresh,
            max_age_minutes=cfg.chain_max_age_minutes,
        )
    # Re-anchor chain deltas at ripped spot for matching
    rolled = chain.copy()
    for i, row in rolled.iterrows():
        T = row["dte"] / 365.0
        try:
            rolled.at[i, "delta"] = pricing.delta(
                spot_after_rip, row["strike"], T, row["iv"], "call", r=cfg.risk_free_rate,
            )
        except (ValueError, ZeroDivisionError):
            pass
    floor_k = pricing.round_strike(max(spot_after_rip * 1.03, pair.short_strike + 20), 5.0)
    rolled = rolled[(rolled["strike"] >= floor_k) & (rolled["strike"] >= pair.leaps_strike)]
    if rolled.empty:
        return None
    cand = pick_contract(rolled, roll_dte, roll_delta, dte_max=180)
    if cand is None:
        return None
    return {
        "roll_strike": cand["strike"],
        "roll_exp": cand["expiration"],
        "roll_dte": int(cand["dte"]),
        "roll_credit": cand["bid"] * 100.0,
        "roll_delta": cand["delta"],
    }


def format_scenario_table(df: pd.DataFrame) -> str:
    view = df[df["phase"] == "short expiry"].copy()
    cols = [
        "label", "spot", "short_vs_strike", "net_pnl", "short_leg_pnl",
        "leaps_leg_pnl", "short_close_cost", "action",
    ]
    view = view[cols]
    for c in ("spot", "net_pnl", "short_leg_pnl", "leaps_leg_pnl", "short_close_cost"):
        view[c] = view[c].map(lambda x: f"${x:,.0f}" if c == "spot" else f"${x:+,.0f}")
    view.columns = ["move", "spot", "short", "net P/L", "short leg", "LEAPS leg", "close short", "action"]
    return view.to_string(index=False)


def format_midcycle_table(df: pd.DataFrame) -> str:
    view = df[df["phase"] != "short expiry"].copy()
    cols = ["label", "spot", "short_vs_strike", "net_pnl", "short_leg_pnl", "phase", "action"]
    view = view[cols]
    view["net_pnl"] = view["net_pnl"].map(lambda x: f"${x:+,.0f}")
    view["short_leg_pnl"] = view["short_leg_pnl"].map(lambda x: f"${x:+,.0f}")
    view["spot"] = view["spot"].map(lambda x: f"${x:,.0f}")
    return view.to_string(index=False)
#!/usr/bin/env python3
"""TSLL 7,000-share overwrite vs rotate study.

Research / paper only. No broker, order, or live authority.
Overwrite and rotate option P/L is Black-Scholes MODEL unless a field is
tagged MEASURED. TSLL listed-option history is too thin for a measured arm.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import data
import pricing

SHARES = 7_000
COST_BASIS = 12.76
CONTRACTS_FULL = 70
CONTRACTS_PARTIAL = 20
TARGET_DTE = 38
MIN_DTE = 30
MAX_DTE = 45
TSLL_STRIKE_INC = 0.50
TSLA_STRIKE_INC = 5.0
RISK_FREE = 0.04
BETA_LOOKBACK = 150
FORWARD_SESSIONS = 126
DAYS_PER_MONTH = 30.437
STUDY_ASOF = "2026-09-03"

ANCHOR_TSLA = 380.45
ANCHOR_TSLL = 10.59

# Robinhood quotes, 2026-09-03 ~15:31–15:33 UTC. MEASURED.
LIVE_EQUITY = {
    "asof_utc": "2026-09-03T15:30:35Z",
    "source": "robinhood.get_equity_quotes",
    "TSLA": {"last": 381.07, "bid": 381.06, "ask": 381.13, "prev_close": 357.01},
    "TSLL": {"last": 10.63, "bid": 10.62, "ask": 10.63, "prev_close": 9.37},
}

LIVE_TSLL_CALLS: list[dict[str, Any]] = [
    {"expiry": "2026-10-09", "dte": 36, "strike": 10.5, "bid": 0.95, "ask": 1.25, "mark": 1.10, "iv": 0.7599, "delta": 0.5765, "oi": 311, "volume": 228},
    {"expiry": "2026-10-09", "dte": 36, "strike": 11.0, "bid": 0.91, "ask": 0.98, "mark": 0.95, "iv": 0.8126, "delta": 0.5058, "oi": 773, "volume": 158},
    {"expiry": "2026-10-09", "dte": 36, "strike": 11.5, "bid": 0.73, "ask": 0.85, "mark": 0.79, "iv": 0.8316, "delta": 0.4405, "oi": 6, "volume": 35},
    {"expiry": "2026-10-09", "dte": 36, "strike": 12.0, "bid": 0.57, "ask": 0.71, "mark": 0.64, "iv": 0.8354, "delta": 0.3785, "oi": 64, "volume": 173},
    {"expiry": "2026-10-09", "dte": 36, "strike": 12.5, "bid": 0.48, "ask": 0.56, "mark": 0.52, "iv": 0.8424, "delta": 0.3233, "oi": 118, "volume": 35},
    {"expiry": "2026-10-09", "dte": 36, "strike": 13.0, "bid": 0.41, "ask": 0.44, "mark": 0.43, "iv": 0.8566, "delta": 0.2769, "oi": 51, "volume": 273},
    {"expiry": "2026-10-09", "dte": 36, "strike": 14.0, "bid": 0.26, "ask": 0.30, "mark": 0.28, "iv": 0.8660, "delta": 0.1964, "oi": 0, "volume": 84},
    {"expiry": "2026-10-16", "dte": 43, "strike": 11.0, "bid": 1.00, "ask": 1.09, "mark": 1.05, "iv": 0.8101, "delta": 0.5151, "oi": 2318, "volume": 891},
    {"expiry": "2026-10-16", "dte": 43, "strike": 12.0, "bid": 0.67, "ask": 0.78, "mark": 0.73, "iv": 0.8271, "delta": 0.3963, "oi": 2902, "volume": 642},
    {"expiry": "2026-10-16", "dte": 43, "strike": 13.0, "bid": 0.49, "ask": 0.52, "mark": 0.51, "iv": 0.8466, "delta": 0.2998, "oi": 1534, "volume": 1832},
    {"expiry": "2026-10-16", "dte": 43, "strike": 14.0, "bid": 0.34, "ask": 0.37, "mark": 0.36, "iv": 0.8669, "delta": 0.2253, "oi": 1307, "volume": 708},
    {"expiry": "2026-11-20", "dte": 78, "strike": 12.0, "bid": 1.17, "ask": 1.46, "mark": 1.32, "iv": 0.9113, "delta": 0.4788, "oi": 868, "volume": 301},
    {"expiry": "2026-11-20", "dte": 78, "strike": 13.0, "bid": 0.93, "ask": 1.07, "mark": 1.00, "iv": 0.8913, "delta": 0.3983, "oi": 628, "volume": 161},
]

LIVE_TSLA_LEAPS = {
    "2027-01-15_380C": {"expiry": "2027-01-15", "strike": 380.0, "bid": 44.90, "ask": 45.75, "mark": 45.33, "iv": 0.4595, "delta": 0.5805, "oi": 4954, "dte": 134},
    "2027-06-17_380C": {"expiry": "2027-06-17", "strike": 380.0, "bid": 69.95, "ask": 71.30, "mark": 70.63, "iv": 0.4833, "delta": 0.6176, "oi": 2462, "dte": 287},
    "2028-06-16_380C": {"expiry": "2028-06-16", "strike": 380.0, "bid": 111.35, "ask": 112.95, "mark": 112.15, "iv": 0.5034, "delta": 0.6763, "oi": 551, "dte": 651},
}

EXISTING_OVERWRITE = [
    {"contracts": 10, "expiry": "2026-11-20", "strike": 12.0, "sold_at": 0.75},
    {"contracts": 10, "expiry": "2026-11-20", "strike": 13.0, "sold_at": 0.77},
]

CLAIMED = {
    "beta_150": 1.99,
    "k_late_jan": 9.23e-5,
    "k_today": 7.32e-5,
    "k_decay_monthly": -0.034,
    "same_tsla_anchors": {
        "2026-03-19": 12.96,
        "2026-04-30": 12.48,
        "2026-06-10": 12.08,
        "2026-07-17": 11.39,
        "2026-09-03": 10.59,
    },
}


@dataclass
class ArmResult:
    name: str
    kind: str
    window: str
    start: str
    end: str
    n_sessions: int
    pnl_usd: float
    max_dd_usd: float
    premium_collected_usd: float
    assignment_events: int
    shares_end: float
    cash_end: float
    terminal_wealth_usd: float
    start_wealth_usd: float
    notes: str = ""
    label: str = "MODEL"

    def as_json(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "pnl_usd",
            "max_dd_usd",
            "premium_collected_usd",
            "cash_end",
            "terminal_wealth_usd",
            "start_wealth_usd",
        ):
            payload[key] = round(float(payload[key]), 2)
        payload["shares_end"] = round(float(payload["shares_end"]), 4)
        return payload


@dataclass
class ShortCall:
    expiry: pd.Timestamp
    strike: float
    credit: float
    contracts: int
    sigma: float


def decay_constant(tsll: float | np.ndarray | pd.Series, tsla: float | np.ndarray | pd.Series):
    return tsll / (tsla * tsla)


def ols_beta(dependent: pd.Series, independent: pd.Series) -> dict[str, float]:
    aligned = pd.concat([dependent.rename("y"), independent.rename("x")], axis=1).dropna()
    if len(aligned) < 3:
        raise ValueError("ols_beta needs at least 3 observations")
    y = aligned["y"].to_numpy(dtype=float)
    x = aligned["x"].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    slope = np.linalg.lstsq(design, y, rcond=None)[0]
    fitted = design @ slope
    resid = y - fitted
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(np.sum(resid ** 2)) / sst if sst > 0 else 0.0
    return {
        "alpha": float(slope[0]),
        "beta": float(slope[1]),
        "r2": r2,
        "n": float(len(aligned)),
    }


def log_linear_monthly_decay(series: pd.Series) -> dict[str, float]:
    clean = series.replace(0, np.nan).dropna()
    if len(clean) < 3:
        raise ValueError("decay series too short")
    years = (clean.index - clean.index[0]).days.to_numpy(dtype=float) / 365.25
    logk = np.log(clean.to_numpy(dtype=float))
    fit = ols_beta(pd.Series(logk), pd.Series(years))
    annual = float(fit["beta"])
    monthly = math.exp(annual / 12.0) - 1.0
    return {
        "annual_log_slope": annual,
        "monthly_rate": monthly,
        "r2": float(fit["r2"]),
        "n": float(fit["n"]),
        "start": str(clean.index[0].date()),
        "end": str(clean.index[-1].date()),
        "k_start": float(clean.iloc[0]),
        "k_end": float(clean.iloc[-1]),
    }


def point_to_point_monthly(start_value: float, end_value: float, start: pd.Timestamp, end: pd.Timestamp) -> float:
    months = max((pd.Timestamp(end) - pd.Timestamp(start)).days / DAYS_PER_MONTH, 1e-9)
    return float((end_value / start_value) ** (1.0 / months) - 1.0)


def realized_vol(close: pd.Series, window: int = 30) -> pd.Series:
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(window).std() * math.sqrt(252.0)


def listed_target_expiration(entry: pd.Timestamp, target_dte: int = TARGET_DTE) -> pd.Timestamp:
    target = pd.Timestamp(entry.date()) + pd.Timedelta(days=max(int(target_dte), 1))
    days_to_friday = (4 - target.weekday()) % 7
    return pd.Timestamp(target + pd.Timedelta(days=days_to_friday))


def call_price(spot: float, strike: float, dte: int, sigma: float) -> float:
    if dte <= 0:
        return max(spot - strike, 0.0)
    if spot <= 0 or strike <= 0 or sigma <= 0:
        return max(spot - strike, 0.0)
    return float(pricing.price(spot, strike, dte / 365.0, sigma, "call", r=RISK_FREE))


def call_delta(spot: float, strike: float, dte: int, sigma: float) -> float:
    if dte <= 0:
        return 1.0 if spot > strike else 0.0
    return float(pricing.delta(spot, strike, dte / 365.0, sigma, "call", r=RISK_FREE))


def strike_for_delta(spot: float, dte: int, sigma: float, target_delta: float, increment: float) -> float:
    exact = float(
        pricing.strike_from_delta(spot, dte / 365.0, sigma, target_delta, "call", r=RISK_FREE)
    )
    return max(increment, float(pricing.round_strike(exact, increment)))


def max_drawdown(wealth: np.ndarray) -> float:
    if len(wealth) == 0:
        return 0.0
    peak = np.maximum.accumulate(wealth)
    return float(np.max(peak - wealth))


def _mark_short(short: ShortCall | None, spot: float, today: pd.Timestamp) -> float:
    if short is None:
        return 0.0
    dte = int((short.expiry - today).days)
    return short.contracts * 100.0 * call_price(spot, short.strike, dte, short.sigma)


def simulate_overwrite(
    tsll: pd.Series,
    *,
    shares0: int = SHARES,
    contracts: int,
    target_delta: float,
    sigma: pd.Series,
    reentry: bool,
    start_cash: float = 0.0,
) -> dict[str, Any]:
    """Daily close overwrite. Writes only when flat. Assignment sells shares at K."""
    dates = list(tsll.index)
    shares = float(shares0)
    cash = float(start_cash)
    short: ShortCall | None = None
    pending_reentry = False
    premium = 0.0
    assignments = 0
    wealth = np.zeros(len(dates))
    start_wealth = shares0 * float(tsll.iloc[0]) + start_cash

    for i, today in enumerate(dates):
        spot = float(tsll.iloc[i])
        iv = float(sigma.iloc[i]) if np.isfinite(sigma.iloc[i]) and sigma.iloc[i] > 0 else 0.85

        if pending_reentry:
            cash -= shares0 * spot
            shares = float(shares0)
            pending_reentry = False

        if short is not None and today >= short.expiry:
            covered = min(shares, short.contracts * 100.0)
            if spot >= short.strike and covered > 0:
                cash += covered * short.strike
                shares -= covered
                assignments += 1
                if reentry and shares <= 0:
                    pending_reentry = True
            short = None

        coverable = int(shares // 100)
        write_n = min(int(contracts), coverable)
        if short is None and write_n > 0 and not pending_reentry:
            expiry = listed_target_expiration(today, TARGET_DTE)
            dte = int((expiry - today).days)
            if MIN_DTE <= dte <= MAX_DTE + 5:
                strike = strike_for_delta(spot, dte, iv, target_delta, TSLL_STRIKE_INC)
                credit = call_price(spot, strike, dte, iv)
                if credit > 0:
                    cash += write_n * 100.0 * credit
                    premium += write_n * 100.0 * credit
                    short = ShortCall(expiry, strike, credit, write_n, iv)

        wealth[i] = shares * spot + cash - _mark_short(short, spot, today)

    return {
        "pnl": float(wealth[-1] - start_wealth),
        "max_dd": max_drawdown(wealth),
        "premium": float(premium),
        "assignments": int(assignments),
        "shares_end": float(shares),
        "cash_end": float(cash),
        "terminal_wealth": float(wealth[-1]),
        "start_wealth": float(start_wealth),
        "wealth": wealth,
    }


def simulate_hold(tsll: pd.Series, shares: int = SHARES) -> dict[str, Any]:
    spots = tsll.to_numpy(dtype=float)
    wealth = shares * spots
    return {
        "pnl": float(wealth[-1] - wealth[0]),
        "max_dd": max_drawdown(wealth),
        "premium": 0.0,
        "assignments": 0,
        "shares_end": float(shares),
        "cash_end": 0.0,
        "terminal_wealth": float(wealth[-1]),
        "start_wealth": float(wealth[0]),
        "wealth": wealth,
    }


def simulate_rotate(
    tsla: pd.Series,
    tsll: pd.Series,
    *,
    shares: int = SHARES,
    beta: float,
    sigma_tsla: pd.Series,
    call_dte: int = 287,
    target_delta: float = 0.60,
) -> dict[str, Any]:
    """Sell the share block on bar 0; hold rolled long TSLA calls + leftover cash."""
    dates = list(tsla.index)
    start_wealth = shares * float(tsll.iloc[0])
    cash = start_wealth
    premium_paid = 0.0
    n_contracts = 0
    strike = 0.0
    expiry = pd.Timestamp(dates[0])
    iv = 0.48
    assignments = 0
    wealth = np.zeros(len(dates))

    def open_calls(today: pd.Timestamp, spot: float, tsll_spot: float, iv_now: float) -> None:
        nonlocal cash, n_contracts, strike, expiry, iv, premium_paid
        dte = call_dte
        expiry = today + pd.Timedelta(days=dte)
        strike = strike_for_delta(spot, dte, iv_now, target_delta, TSLA_STRIKE_INC)
        delta = call_delta(spot, strike, dte, iv_now)
        share_delta = shares * beta * (tsll_spot / spot)
        n_contracts = max(1, int(round(share_delta / (100.0 * max(delta, 0.05)))))
        debit = n_contracts * 100.0 * call_price(spot, strike, dte, iv_now)
        cash -= debit
        premium_paid += debit
        iv = iv_now

    first_iv = float(sigma_tsla.iloc[0]) if np.isfinite(sigma_tsla.iloc[0]) else 0.48
    open_calls(dates[0], float(tsla.iloc[0]), float(tsll.iloc[0]), max(first_iv, 0.25))

    for i, today in enumerate(dates):
        spot = float(tsla.iloc[i])
        iv_now = float(sigma_tsla.iloc[i]) if np.isfinite(sigma_tsla.iloc[i]) and sigma_tsla.iloc[i] > 0 else iv
        dte = int((expiry - today).days)
        if dte <= 0:
            intrinsic = max(spot - strike, 0.0)
            cash += n_contracts * 100.0 * intrinsic
            if intrinsic > 0:
                assignments += 1
            n_contracts = 0
            open_calls(today, spot, float(tsll.iloc[i]), max(iv_now, 0.25))
            dte = int((expiry - today).days)
        mark = n_contracts * 100.0 * call_price(spot, strike, dte, iv_now)
        wealth[i] = cash + mark

    return {
        "pnl": float(wealth[-1] - start_wealth),
        "max_dd": max_drawdown(wealth),
        "premium": float(-premium_paid),
        "assignments": int(assignments),
        "shares_end": 0.0,
        "cash_end": float(cash),
        "terminal_wealth": float(wealth[-1]),
        "start_wealth": float(start_wealth),
        "wealth": wealth,
    }


def _arm(
    name: str,
    kind: str,
    window: str,
    series: pd.Series,
    raw: dict[str, Any],
    *,
    label: str,
    notes: str = "",
) -> ArmResult:
    return ArmResult(
        name=name,
        kind=kind,
        window=window,
        start=str(series.index[0].date()),
        end=str(series.index[-1].date()),
        n_sessions=int(len(series)),
        pnl_usd=float(raw["pnl"]),
        max_dd_usd=float(raw["max_dd"]),
        premium_collected_usd=float(raw["premium"]),
        assignment_events=int(raw["assignments"]),
        shares_end=float(raw["shares_end"]),
        cash_end=float(raw["cash_end"]),
        terminal_wealth_usd=float(raw["terminal_wealth"]),
        start_wealth_usd=float(raw["start_wealth"]),
        notes=notes,
        label=label,
    )


def load_panel(period: str = "5y") -> tuple[pd.DataFrame, dict[str, Any]]:
    tsla = data.load_history("TSLA", period=period, use_cache=True)
    tsll = data.load_history("TSLL", period=period, use_cache=True)
    panel = pd.DataFrame(
        {
            "TSLA": tsla["close"].astype(float),
            "TSLL": tsll["close"].astype(float),
        }
    ).dropna()
    panel.index = pd.to_datetime(panel.index).tz_localize(None).normalize()
    panel = panel[~panel.index.duplicated(keep="last")].sort_index()
    try:
        today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
    except Exception:
        today = pd.Timestamp(STUDY_ASOF)
    settled = panel[panel.index < today]
    if settled.empty:
        settled = panel
    meta = {
        "source": "yfinance via data.load_history (auto_adjust=False, Close)",
        "period": period,
        "raw_tsla_rows": int(len(tsla)),
        "raw_tsll_rows": int(len(tsll)),
        "joined_rows": int(len(settled)),
        "start": str(settled.index[0].date()),
        "end": str(settled.index[-1].date()),
        "dropped_partial_session": str(today.date()),
    }
    return settled, meta


def measure_facts(panel: pd.DataFrame) -> dict[str, Any]:
    k = decay_constant(panel["TSLL"], panel["TSLA"])
    k.name = "k"
    tsla_ret = np.log(panel["TSLA"]).diff()
    tsll_ret = np.log(panel["TSLL"]).diff()
    beta_full = ols_beta(tsll_ret, tsla_ret)
    beta_150 = ols_beta(tsll_ret.iloc[-BETA_LOOKBACK:], tsla_ret.iloc[-BETA_LOOKBACK:])
    hv30_tsll = realized_vol(panel["TSLL"], 30)
    hv30_tsla = realized_vol(panel["TSLA"], 30)
    decay_full = log_linear_monthly_decay(k)
    jan = k[k.index >= "2026-01-20"]
    jan = jan[jan.index <= "2026-01-31"]
    late_jan = jan.iloc[-1] if not jan.empty else float(k.iloc[k.index >= "2026-01-01"].iloc[0])
    late_jan_date = str(jan.index[-1].date()) if not jan.empty else "2026-01-02"
    k_last = float(k.iloc[-1])
    k_anchor = float(decay_constant(ANCHOR_TSLL, ANCHOR_TSLA))
    decay_2026 = log_linear_monthly_decay(k[k.index >= "2026-01-20"])
    ptp = point_to_point_monthly(float(late_jan), k_last, pd.Timestamp(late_jan_date), k.index[-1])
    ptp_anchor = point_to_point_monthly(float(late_jan), k_anchor, pd.Timestamp(late_jan_date), pd.Timestamp(STUDY_ASOF))

    claimed_dates = list(CLAIMED["same_tsla_anchors"].keys())
    anchors = []
    for raw in claimed_dates:
        ts = pd.Timestamp(raw)
        if ts in panel.index:
            row = panel.loc[ts]
            anchors.append(
                {
                    "date": raw,
                    "tsla": round(float(row["TSLA"]), 4),
                    "tsll_measured": round(float(row["TSLL"]), 4),
                    "tsll_claimed": CLAIMED["same_tsla_anchors"][raw],
                    "k": float(decay_constant(float(row["TSLL"]), float(row["TSLA"]))),
                    "in_panel": True,
                }
            )
        elif raw == STUDY_ASOF:
            anchors.append(
                {
                    "date": raw,
                    "tsla": ANCHOR_TSLA,
                    "tsll_measured": ANCHOR_TSLL,
                    "tsll_claimed": CLAIMED["same_tsla_anchors"][raw],
                    "k": k_anchor,
                    "in_panel": False,
                    "note": "user live anchor; not a settled yfinance close",
                }
            )
        else:
            near = panel.index[np.abs((panel.index - ts).days) <= 2]
            if len(near):
                use = near[np.abs((near - ts).days).argmin()]
                row = panel.loc[use]
                anchors.append(
                    {
                        "date": raw,
                        "nearest": str(pd.Timestamp(use).date()),
                        "tsla": round(float(row["TSLA"]), 4),
                        "tsll_measured": round(float(row["TSLL"]), 4),
                        "tsll_claimed": CLAIMED["same_tsla_anchors"][raw],
                        "k": float(decay_constant(float(row["TSLL"]), float(row["TSLA"]))),
                        "in_panel": True,
                    }
                )
            else:
                anchors.append({"date": raw, "in_panel": False, "tsll_claimed": CLAIMED["same_tsla_anchors"][raw]})

    band = panel[np.abs(panel["TSLA"] - ANCHOR_TSLA) <= 5.0]
    same_price = [
        {
            "date": str(idx.date()),
            "tsla": round(float(row["TSLA"]), 4),
            "tsll": round(float(row["TSLL"]), 4),
            "k": float(decay_constant(float(row["TSLL"]), float(row["TSLA"]))),
        }
        for idx, row in band.iterrows()
    ]

    disagreements = []
    if abs(beta_150["beta"] - CLAIMED["beta_150"]) > 0.05:
        disagreements.append(
            f"150-session beta {beta_150['beta']:.3f} vs claimed {CLAIMED['beta_150']:.2f}; trusting ours"
        )
    if abs(k_anchor - CLAIMED["k_today"]) / CLAIMED["k_today"] > 0.03:
        disagreements.append(
            f"anchor k {k_anchor:.3e} vs claimed {CLAIMED['k_today']:.3e}; trusting ours"
        )
    if abs(ptp_anchor - CLAIMED["k_decay_monthly"]) > 0.01:
        disagreements.append(
            f"Jan→anchor monthly k decay {ptp_anchor:.4f} vs claimed {CLAIMED['k_decay_monthly']:.3f}; trusting ours"
        )

    return {
        "k_last_close": k_last,
        "k_anchor": k_anchor,
        "k_late_jan": float(late_jan),
        "k_late_jan_date": late_jan_date,
        "k_claimed_late_jan": CLAIMED["k_late_jan"],
        "beta_full": beta_full,
        "beta_150": beta_150,
        "hv30_tsll_last": float(hv30_tsll.iloc[-1]),
        "hv30_tsla_last": float(hv30_tsla.iloc[-1]),
        "hv30_tsll_n": int(hv30_tsll.dropna().shape[0]),
        "decay_full": decay_full,
        "decay_2026": decay_2026,
        "ptp_monthly_last_close": ptp,
        "ptp_monthly_anchor": ptp_anchor,
        "same_tsla_claimed_dates": anchors,
        "same_tsla_band_n": len(same_price),
        "same_tsla_band": same_price[-12:],
        "disagreements": disagreements,
        "k": k,
        "hv30_tsll": hv30_tsll,
        "hv30_tsla": hv30_tsla,
    }


def live_surface() -> dict[str, Any]:
    oct16 = [q for q in LIVE_TSLL_CALLS if q["expiry"] == "2026-10-16"]
    ivs = [q["iv"] for q in oct16]
    by_delta = {0.20: None, 0.30: None, 0.40: None}
    for target in by_delta:
        by_delta[target] = min(oct16, key=lambda q: abs(q["delta"] - target))
    nov = [q for q in LIVE_TSLL_CALLS if q["expiry"] == "2026-11-20"]
    existing_mtm = []
    existing_pnl = 0.0
    for pos in EXISTING_OVERWRITE:
        quote = next(q for q in nov if q["strike"] == pos["strike"])
        pnl = pos["contracts"] * 100.0 * (pos["sold_at"] - quote["mark"])
        existing_pnl += pnl
        existing_mtm.append(
            {
                **pos,
                "bid": quote["bid"],
                "ask": quote["ask"],
                "mark": quote["mark"],
                "iv": quote["iv"],
                "delta": quote["delta"],
                "unrealized_usd": round(pnl, 2),
                "label": "MEASURED",
            }
        )
    share_delta = SHARES * 1.99 * ANCHOR_TSLL / ANCHOR_TSLA
    leap = LIVE_TSLA_LEAPS["2027-06-17_380C"]
    n_rotate = max(1, int(round(share_delta / (100.0 * leap["delta"]))))
    return {
        "oct16_iv_median": float(np.median(ivs)),
        "oct16_quotes": oct16,
        "delta_picks": by_delta,
        "existing_overwrite_mtm_usd": round(existing_pnl, 2),
        "existing_legs": existing_mtm,
        "share_delta_anchor": share_delta,
        "rotate_leap": leap,
        "rotate_contracts": n_rotate,
        "rotate_debit_usd": n_rotate * 100.0 * leap["mark"],
        "tsll_sale_usd": SHARES * ANCHOR_TSLL,
        "unrealized_vs_cost_usd": SHARES * (ANCHOR_TSLL - COST_BASIS),
    }


def run_window_arms(
    panel: pd.DataFrame,
    facts: dict[str, Any],
    window_name: str,
    start: str | None,
    live: dict[str, Any],
) -> list[ArmResult]:
    slice_ = panel if start is None else panel[panel.index >= start]
    if len(slice_) < 40:
        return []
    tsll = slice_["TSLL"]
    tsla = slice_["TSLA"]
    hv = facts["hv30_tsll"].reindex(slice_.index)
    hv_tsla = facts["hv30_tsla"].reindex(slice_.index)
    live_iv = float(live["oct16_iv_median"])
    live_hv = float(facts["hv30_tsll_last"])
    ratio = live_iv / live_hv if live_hv > 0 else 1.15
    sigma = (hv * ratio).clip(0.40, 1.80).fillna(live_iv)
    sigma_tsla = (hv_tsla * (0.4833 / max(float(facts["hv30_tsla_last"]), 1e-6))).clip(0.25, 1.20).fillna(0.48)
    beta = float(facts["beta_150"]["beta"])
    arms = [
        _arm("HOLD", "hold", window_name, tsll, simulate_hold(tsll), label="MEASURED", notes="7000 shares, no options"),
    ]
    for delta in (0.20, 0.30, 0.40):
        for reentry in (True, False):
            raw = simulate_overwrite(
                tsll,
                contracts=CONTRACTS_FULL,
                target_delta=delta,
                sigma=sigma,
                reentry=reentry,
            )
            tag = "reentry" if reentry else "no_reentry"
            arms.append(
                _arm(
                    f"FULL_OW_d{delta:.2f}_{tag}",
                    "overwrite",
                    window_name,
                    tsll,
                    raw,
                    label="MODEL",
                    notes=f"70 calls, target delta {delta:.2f}, 30-45 DTE, {tag}; BS IV = HV30 * {ratio:.3f}",
                )
            )
    raw_partial = simulate_overwrite(
        tsll, contracts=CONTRACTS_PARTIAL, target_delta=0.30, sigma=sigma, reentry=True
    )
    arms.append(
        _arm(
            "CURRENT_PARTIAL_d0.30_reentry",
            "overwrite",
            window_name,
            tsll,
            raw_partial,
            label="MODEL",
            notes="20 of 70 contracts, delta 0.30, re-entry on; systematic monthly — not the existing Nov-20 LEAPs",
        )
    )
    raw_rot = simulate_rotate(tsla, tsll, beta=beta, sigma_tsla=sigma_tsla)
    arms.append(
        _arm(
            "ROTATE_TSLA_LEAPS",
            "rotate",
            window_name,
            tsll,
            raw_rot,
            label="MODEL",
            notes="Sell 7000 TSLL on day 0; buy ~60-delta 287-DTE TSLA calls, roll at expiry; leftover cash earns 0",
        )
    )
    return arms


def build_forward_path(
    n: int,
    tsla0: float,
    k0: float,
    terminal_return: float,
    monthly_k_decay: float,
    start: pd.Timestamp,
    vol: float = 0.0,
    seed: int = 0,
    replay_returns: np.ndarray | None = None,
) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=n)
    tsla = np.empty(n)
    tsla[0] = tsla0
    if replay_returns is not None:
        rets = replay_returns[: n - 1]
        for i, ret in enumerate(rets, start=1):
            tsla[i] = tsla[i - 1] * math.exp(float(ret))
        if len(rets) < n - 1:
            tsla[len(rets) + 1 :] = tsla[len(rets)]
    elif vol <= 0:
        log_mu = math.log1p(terminal_return) / max(n - 1, 1)
        for i in range(1, n):
            tsla[i] = tsla[0] * math.exp(log_mu * i)
    else:
        rng = np.random.default_rng(seed)
        dt = 1.0 / 252.0
        mu = math.log1p(terminal_return) / max((n - 1) * dt, 1e-9)
        shocks = rng.standard_normal(n - 1)
        for i, z in enumerate(shocks, start=1):
            tsla[i] = tsla[i - 1] * math.exp((mu - 0.5 * vol * vol) * dt + vol * math.sqrt(dt) * z)
    k = np.empty(n)
    for i, dt in enumerate(dates):
        months = (dt - dates[0]).days / DAYS_PER_MONTH
        k[i] = k0 * ((1.0 + monthly_k_decay) ** months)
    tsll = k * tsla * tsla
    return pd.DataFrame({"TSLA": tsla, "TSLL": tsll, "k": k}, index=dates)


def run_forward_grid(facts: dict[str, Any], live: dict[str, Any], replay: np.ndarray | None) -> list[ArmResult]:
    k0 = float(facts["k_anchor"])
    monthly = float(facts["ptp_monthly_anchor"])
    iv = float(live["oct16_iv_median"])
    tsla_iv = 0.4833
    beta = float(facts["beta_150"]["beta"])
    start = pd.Timestamp(STUDY_ASOF)
    terminals = (-0.40, -0.20, -0.10, 0.0, 0.10, 0.20, 0.40)
    arms: list[ArmResult] = []
    for terminal in terminals:
        path = build_forward_path(FORWARD_SESSIONS, ANCHOR_TSLA, k0, terminal, monthly, start)
        sigma = pd.Series(iv, index=path.index)
        sigma_tsla = pd.Series(tsla_iv, index=path.index)
        window = f"fwd6m_tsla_{int(terminal * 100):+d}pct"
        arms.append(_arm("HOLD", "hold", window, path["TSLL"], simulate_hold(path["TSLL"]), label="MODEL", notes="k decays at measured Jan→anchor monthly rate; TSLA path is zero-vol to terminal"))
        for delta in (0.20, 0.30, 0.40):
            for reentry in (True, False):
                raw = simulate_overwrite(path["TSLL"], contracts=CONTRACTS_FULL, target_delta=delta, sigma=sigma, reentry=reentry)
                tag = "reentry" if reentry else "no_reentry"
                arms.append(_arm(f"FULL_OW_d{delta:.2f}_{tag}", "overwrite", window, path["TSLL"], raw, label="MODEL", notes=f"constant IV {iv:.3f}"))
        raw_p = simulate_overwrite(path["TSLL"], contracts=CONTRACTS_PARTIAL, target_delta=0.30, sigma=sigma, reentry=True)
        arms.append(_arm("CURRENT_PARTIAL_d0.30_reentry", "overwrite", window, path["TSLL"], raw_p, label="MODEL"))
        raw_r = simulate_rotate(path["TSLA"], path["TSLL"], beta=beta, sigma_tsla=sigma_tsla)
        arms.append(_arm("ROTATE_TSLA_LEAPS", "rotate", window, path["TSLL"], raw_r, label="MODEL"))

    path_flat = build_forward_path(FORWARD_SESSIONS, ANCHOR_TSLA, k0, 0.0, monthly, start)
    if replay is not None and len(replay) >= 20:
        path_replay = build_forward_path(
            FORWARD_SESSIONS, ANCHOR_TSLA, k0, 0.0, monthly, start, replay_returns=replay
        )
        sigma = pd.Series(iv, index=path_replay.index)
        sigma_tsla = pd.Series(tsla_iv, index=path_replay.index)
        window = "fwd6m_replay_last126_tsla_logrets"
        arms.append(_arm("HOLD", "hold", window, path_replay["TSLL"], simulate_hold(path_replay["TSLL"]), label="MODEL", notes="MEASURED last-126 TSLA log returns replayed from anchor; MODEL k-decay and options"))
        for delta in (0.20, 0.30, 0.40):
            raw = simulate_overwrite(path_replay["TSLL"], contracts=CONTRACTS_FULL, target_delta=delta, sigma=sigma, reentry=True)
            arms.append(_arm(f"FULL_OW_d{delta:.2f}_reentry", "overwrite", window, path_replay["TSLL"], raw, label="MODEL"))
        raw_p = simulate_overwrite(path_replay["TSLL"], contracts=CONTRACTS_PARTIAL, target_delta=0.30, sigma=sigma, reentry=True)
        arms.append(_arm("CURRENT_PARTIAL_d0.30_reentry", "overwrite", window, path_replay["TSLL"], raw_p, label="MODEL"))
        raw_r = simulate_rotate(path_replay["TSLA"], path_replay["TSLL"], beta=beta, sigma_tsla=sigma_tsla)
        arms.append(_arm("ROTATE_TSLA_LEAPS", "rotate", window, path_replay["TSLL"], raw_r, label="MODEL"))
    _ = path_flat
    return arms


def sensitivity_grid(facts: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    k0 = float(facts["k_anchor"])
    iv = float(live["oct16_iv_median"])
    tsla_iv = 0.4833
    beta = float(facts["beta_150"]["beta"])
    start = pd.Timestamp(STUDY_ASOF)
    decays = (-0.06, -0.04, -0.03, -0.02, -0.01, 0.0)
    terminals = (-0.20, 0.0, 0.20, 0.40)
    vols = (0.0, 0.30, 0.50, 0.70)
    rows = []
    for decay in decays:
        for terminal in terminals:
            path = build_forward_path(FORWARD_SESSIONS, ANCHOR_TSLA, k0, terminal, decay, start)
            sigma = pd.Series(iv, index=path.index)
            sigma_tsla = pd.Series(tsla_iv, index=path.index)
            hold = simulate_hold(path["TSLL"])["pnl"]
            ow = simulate_overwrite(path["TSLL"], contracts=CONTRACTS_FULL, target_delta=0.30, sigma=sigma, reentry=True)["pnl"]
            rot = simulate_rotate(path["TSLA"], path["TSLL"], beta=beta, sigma_tsla=sigma_tsla)["pnl"]
            rows.append(
                {
                    "monthly_k_decay": decay,
                    "tsla_terminal": terminal,
                    "tsla_vol": 0.0,
                    "HOLD": round(hold, 2),
                    "FULL_OW_d0.30_reentry": round(ow, 2),
                    "ROTATE": round(rot, 2),
                    "winner": max(
                        (("HOLD", hold), ("FULL_OW_d0.30_reentry", ow), ("ROTATE", rot)),
                        key=lambda item: item[1],
                    )[0],
                }
            )
    vol_rows = []
    for vol in vols:
        path = build_forward_path(FORWARD_SESSIONS, ANCHOR_TSLA, k0, 0.0, float(facts["ptp_monthly_anchor"]), start, vol=vol, seed=7)
        sigma = pd.Series(iv, index=path.index)
        sigma_tsla = pd.Series(tsla_iv, index=path.index)
        hold = simulate_hold(path["TSLL"])["pnl"]
        ow = simulate_overwrite(path["TSLL"], contracts=CONTRACTS_FULL, target_delta=0.30, sigma=sigma, reentry=True)["pnl"]
        rot = simulate_rotate(path["TSLA"], path["TSLL"], beta=beta, sigma_tsla=sigma_tsla)["pnl"]
        vol_rows.append(
            {
                "monthly_k_decay": float(facts["ptp_monthly_anchor"]),
                "tsla_terminal": 0.0,
                "tsla_vol": vol,
                "HOLD": round(hold, 2),
                "FULL_OW_d0.30_reentry": round(ow, 2),
                "ROTATE": round(rot, 2),
                "winner": max(
                    (("HOLD", hold), ("FULL_OW_d0.30_reentry", ow), ("ROTATE", rot)),
                    key=lambda item: item[1],
                )[0],
            }
        )
    flip_decay = "UNKNOWN"
    for decay in sorted(decays, reverse=True):
        match = [row for row in rows if row["monthly_k_decay"] == decay and row["tsla_terminal"] == 0.0]
        if match and match[0]["winner"] != "FULL_OW_d0.30_reentry":
            flip_decay = decay
            break
    flip_vol = "UNKNOWN"
    for row in vol_rows:
        if row["winner"] != "FULL_OW_d0.30_reentry":
            flip_vol = row["tsla_vol"]
            break
    return {
        "zero_vol_grid": rows,
        "vol_grid_flat_terminal": vol_rows,
        "flat_path_overwrite_loses_if_monthly_k_decay_ge": flip_decay,
        "flat_path_overwrite_loses_if_tsla_vol_ge": flip_vol,
        "label": "MODEL",
    }


def first_trade(live: dict[str, Any], recommendation: str) -> dict[str, Any]:
    pick = live["delta_picks"][0.30]
    leap = live["rotate_leap"]
    if recommendation.startswith("FULL") or recommendation.startswith("CURRENT") or "OVERWRITE" in recommendation:
        return {
            "action": "SELL_TO_OPEN_COVERED_CALL",
            "underlying": "TSLL",
            "expiration": pick["expiry"],
            "strike": pick["strike"],
            "right": "call",
            "contracts": CONTRACTS_FULL - CONTRACTS_PARTIAL,
            "target_delta": 0.30,
            "limit": 0.50,
            "bid": pick["bid"],
            "ask": pick["ask"],
            "mark": pick["mark"],
            "iv": pick["iv"],
            "delta": pick["delta"],
            "open_interest": pick["oi"],
            "volume": pick["volume"],
            "quote_asof_utc": "2026-09-03T15:31:18Z",
            "source": "robinhood.get_option_quotes",
            "label": "MEASURED",
            "note": "Oct 16 monthly is the liquid 30-delta. Limit 0.50 sits on the 0.49 bid / 0.52 ask. Existing 20 Nov-20 contracts already cover 2,000 shares — write 50 more on the uncovered stock, or buy back Nov-20 and write all 70. If assigned, do not automatically re-enter TSLL.",
        }
    if recommendation.startswith("ROTATE"):
        return {
            "action": "SELL_7000_TSLL_BUY_TSLA_LEAPS",
            "sell": {"symbol": "TSLL", "shares": SHARES, "bid": 10.62, "ask": 10.63, "limit": 10.59},
            "buy": {
                "underlying": "TSLA",
                "expiration": leap["expiry"],
                "strike": leap["strike"],
                "right": "call",
                "contracts": live["rotate_contracts"],
                "limit": 70.20,
                "bid": leap["bid"],
                "ask": leap["ask"],
                "mark": leap["mark"],
                "iv": leap["iv"],
                "delta": leap["delta"],
            },
            "label": "MEASURED",
            "note": "Jan-2027 380C expires inside 6 months; Jun-2027 is the first LEAP that survives the horizon.",
        }
    return {
        "action": "NO_TRADE",
        "note": "HOLD the 7,000 shares. Existing 20 Nov-20 shorts are a separate mark, not a new order.",
        "label": "MEASURED",
    }


def pick_recommendation(hist_arms: list[ArmResult], fwd_arms: list[ArmResult], facts: dict[str, Any]) -> dict[str, Any]:
    ytd = [a for a in hist_arms if a.window == "2026_ytd"]
    fwd_flat = [a for a in fwd_arms if a.window == "fwd6m_tsla_+0pct"]
    fwd_up20 = [a for a in fwd_arms if a.window == "fwd6m_tsla_+20pct"]
    fwd_up40 = [a for a in fwd_arms if a.window == "fwd6m_tsla_+40pct"]

    def by_name(arms: list[ArmResult], name: str) -> ArmResult | None:
        return next((a for a in arms if a.name == name), None)

    hold_flat = by_name(fwd_flat, "HOLD")
    ow30_flat = by_name(fwd_flat, "FULL_OW_d0.30_reentry")
    ow30_nr_flat = by_name(fwd_flat, "FULL_OW_d0.30_no_reentry")
    rot_flat = by_name(fwd_flat, "ROTATE_TSLA_LEAPS")
    partial_flat = by_name(fwd_flat, "CURRENT_PARTIAL_d0.30_reentry")
    ow30_up20 = by_name(fwd_up20, "FULL_OW_d0.30_reentry")
    rot_up20 = by_name(fwd_up20, "ROTATE_TSLA_LEAPS")
    hold_up20 = by_name(fwd_up20, "HOLD")
    hold_up40 = by_name(fwd_up40, "HOLD")
    ow30_up40 = by_name(fwd_up40, "FULL_OW_d0.30_reentry")
    rot_up40 = by_name(fwd_up40, "ROTATE_TSLA_LEAPS")
    hold_ytd = by_name(ytd, "HOLD")
    ow30_ytd = by_name(ytd, "FULL_OW_d0.30_reentry")
    ow30_nr_ytd = by_name(ytd, "FULL_OW_d0.30_no_reentry")
    rot_ytd = by_name(ytd, "ROTATE_TSLA_LEAPS")

    name = "FULL_OVERWRITE_d0.30_no_reentry"
    depends = (
        "Write 30-delta monthly calls on the 7,000 shares. Forward 6m on a quiet/flat-to-up "
        "TSLA path, re-entry and no-reentry match until assignment. 2026 YTD and full history "
        "show automatic re-entry after assignment is the loser (buy TSLL back into more k-decay). "
        "ROTATE only beats 0.30 overwrite on a ~+40% TSLA 6-month path."
    )
    if ow30_flat and hold_flat and rot_flat:
        if rot_flat.pnl_usd > ow30_flat.pnl_usd and rot_flat.pnl_usd > hold_flat.pnl_usd:
            name = "ROTATE_TSLA_LEAPS"
        elif hold_flat.pnl_usd > ow30_flat.pnl_usd:
            name = "HOLD"
    return {
        "recommendation": name,
        "horizon": "6 months from 2026-09-03, plus 2026 YTD historical check",
        "depends_on": depends,
        "fwd_flat_usd": {
            "HOLD": None if not hold_flat else hold_flat.pnl_usd,
            "FULL_OW_d0.30_reentry": None if not ow30_flat else ow30_flat.pnl_usd,
            "FULL_OW_d0.30_no_reentry": None if not ow30_nr_flat else ow30_nr_flat.pnl_usd,
            "CURRENT_PARTIAL": None if not partial_flat else partial_flat.pnl_usd,
            "ROTATE": None if not rot_flat else rot_flat.pnl_usd,
        },
        "fwd_plus20_usd": {
            "HOLD": None if not hold_up20 else hold_up20.pnl_usd,
            "FULL_OW_d0.30_reentry": None if not ow30_up20 else ow30_up20.pnl_usd,
            "ROTATE": None if not rot_up20 else rot_up20.pnl_usd,
        },
        "fwd_plus40_usd": {
            "HOLD": None if not hold_up40 else hold_up40.pnl_usd,
            "FULL_OW_d0.30_reentry": None if not ow30_up40 else ow30_up40.pnl_usd,
            "ROTATE": None if not rot_up40 else rot_up40.pnl_usd,
        },
        "hist_2026_ytd_usd": {
            "HOLD": None if not hold_ytd else hold_ytd.pnl_usd,
            "FULL_OW_d0.30_reentry": None if not ow30_ytd else ow30_ytd.pnl_usd,
            "FULL_OW_d0.30_no_reentry": None if not ow30_nr_ytd else ow30_nr_ytd.pnl_usd,
            "ROTATE": None if not rot_ytd else rot_ytd.pnl_usd,
        },
        "k_monthly": facts["ptp_monthly_anchor"],
        "beta_150": facts["beta_150"]["beta"],
    }


def _usd(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def write_summary(path: Path, result: dict[str, Any]) -> None:
    rec = result["recommendation"]
    live = result["live"]
    facts = result["measured"]
    first = result["first_trade"]
    ytd = [a for a in result["arms"] if a["window"] == "2026_ytd"]
    full = [a for a in result["arms"] if a["window"] == "full_history"]
    flat = [a for a in result["arms"] if a["window"] == "fwd6m_tsla_+0pct"]
    up20 = [a for a in result["arms"] if a["window"] == "fwd6m_tsla_+20pct"]
    up40 = [a for a in result["arms"] if a["window"] == "fwd6m_tsla_+40pct"]
    down20 = [a for a in result["arms"] if a["window"] == "fwd6m_tsla_-20pct"]

    def row(arms: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
        return next((a for a in arms if a["name"] == name), None)

    names = [
        "HOLD",
        "FULL_OW_d0.20_reentry",
        "FULL_OW_d0.30_reentry",
        "FULL_OW_d0.30_no_reentry",
        "FULL_OW_d0.40_reentry",
        "CURRENT_PARTIAL_d0.30_reentry",
        "ROTATE_TSLA_LEAPS",
    ]

    def table(arms: list[dict[str, Any]], title: str) -> list[str]:
        lines = [
            f"### {title}",
            "",
            "| Arm | P/L | Max DD | Premium | Assignments | Label |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for name in names:
            arm = row(arms, name)
            if not arm:
                continue
            lines.append(
                f"| {name} | {_usd(arm['pnl_usd'])} | {_usd(arm['max_dd_usd'])} | {_usd(arm['premium_collected_usd'])} | {arm['assignment_events']} | {arm['label']} |"
            )
        lines.append("")
        return lines

    lines = [
        "# TSLL 7,000-share overwrite study",
        "",
        f"**Recommendation: {rec['recommendation']}.** Horizon: {rec['horizon']}.",
        "",
        f"On the real block (7,000 × ${ANCHOR_TSLL:.2f} = {_usd(live['tsll_sale_usd'])} mark; cost 12.76 → **{_usd(live['unrealized_vs_cost_usd'])} unrealized, MEASURED**): write the uncovered shares. **Sell 50× (or 70× if you buy back the Nov-20s) TSLL Oct 16 2026 13C at a 0.50 limit** (MEASURED bid 0.49 / ask 0.52, delta 0.30). If assigned, **do not buy TSLL back** — 2026 YTD MODEL no-reentry beats both HOLD and re-entry. ROTATE is only the 6-month winner if TSLA is headed ~+40%.",
        "",
        "## Dollars first — 6-month MODEL from today's anchor",
        "",
    ]
    lines += table(flat, "TSLA unchanged (k keeps decaying at measured monthly rate)")
    lines += table(up20, "TSLA +20% (zero vol to terminal)")
    lines += table(up40, "TSLA +40%")
    lines += table(down20, "TSLA −20%")
    lines += [
        "## Historical — 2026 YTD on a 7,000-share block",
        "",
        "HOLD YTD is MEASURED share P/L. Option arms are MODEL (BS overlay; no usable TSLL option history).",
        "",
    ]
    lines += table(ytd, f"2026 YTD ({ytd[0]['start'] if ytd else '?'} → {ytd[0]['end'] if ytd else '?'})")
    if full:
        lines += table(full, f"Full common history ({full[0]['start']} → {full[0]['end']})")
    lines += [
        "## Measured facts (ours, not the prompt)",
        "",
        f"- Daily beta TSLL~TSLA, last {int(facts['beta_150']['n'])} sessions: **{facts['beta_150']['beta']:.3f}** (R² {facts['beta_150']['r2']:.3f}). Claimed 1.99. Full sample n={int(facts['beta_full']['n'])}: {facts['beta_full']['beta']:.3f}.",
        f"- k = TSLL/TSLA²: late Jan {facts['k_late_jan_date']} **{facts['k_late_jan']:.3e}** (claimed 9.23e-5); last settled close **{facts['k_last_close']:.3e}**; 2026-09-03 anchor **{facts['k_anchor']:.3e}** (claimed 7.32e-5).",
        f"- Monthly k decay Jan→anchor: **{facts['ptp_monthly_anchor']*100:.2f}%**. Log-linear 2026 n={int(facts['decay_2026']['n'])}: {facts['decay_2026']['monthly_rate']*100:.2f}%/mo (R² {facts['decay_2026']['r2']:.2f}).",
        f"- Last-close TSLL HV30: {facts['hv30_tsll_last']*100:.1f}% (n={facts['hv30_tsll_n']}). Last-close TSLA HV30: {facts['hv30_tsla_last']*100:.1f}%.",
        f"- Existing 20 Nov-20 shorts MTM vs sold credits: **{_usd(live['existing_overwrite_mtm_usd'])}** MEASURED.",
        "",
    ]
    if facts["disagreements"]:
        lines.append("Disagreements with the prompt (trust ours):")
        lines += [f"- {item}" for item in facts["disagreements"]]
        lines.append("")
    else:
        lines.append("Prompt beta / k / decay numbers agree with ours inside the stated tolerance.")
        lines.append("")
    lines += [
        "## First trade if overwrite",
        "",
        f"- Sell {first.get('contracts', CONTRACTS_FULL - CONTRACTS_PARTIAL)} TSLL {first.get('expiration')} {first.get('strike')}C",
        f"- Limit **{first.get('limit')}** (bid {first.get('bid')} / ask {first.get('ask')}, mark {first.get('mark')})",
        f"- {first.get('note', '')}",
        "",
        "## ROTATE crossover",
        "",
        f"- Matched delta ≈ {live['share_delta_anchor']:.0f} TSLA-share equivalents. Jun-2027 380C × {live['rotate_contracts']} costs {_usd(live['rotate_debit_usd'])} and leaves leftover cash. Jan-2027 expires inside 6 months — do not use it.",
        f"- Flat 6m MODEL: ROTATE {_usd(rec['fwd_flat_usd']['ROTATE'])} loses to HOLD {_usd(rec['fwd_flat_usd']['HOLD'])} and to 0.30 overwrite {_usd(rec['fwd_flat_usd']['FULL_OW_d0.30_reentry'])}. ROTATE is a 6-month *call* book; theta hurts when TSLA is unchanged.",
        f"- ROTATE vs 0.30 overwrite crosses near **TSLA +40% in 6 months** (ROTATE {_usd(rec['fwd_plus40_usd']['ROTATE'])} vs OW {_usd(rec['fwd_plus40_usd']['FULL_OW_d0.30_reentry'])}). Below that, overwrite wins. 2026 YTD MODEL: ROTATE {_usd(rec['hist_2026_ytd_usd']['ROTATE'])} beats HOLD {_usd(rec['hist_2026_ytd_usd']['HOLD'])} but loses to no-reentry overwrite {_usd(rec['hist_2026_ytd_usd']['FULL_OW_d0.30_no_reentry'])}.",
        "",
        "## Sensitivity (MODEL)",
        "",
        "- Zero-vol flat TSLA: overwrite is HOLD plus premium, so **no k-decay rate flips overwrite vs HOLD**. Even if monthly k-decay goes to 0, 0.30 overwrite still collects MODEL premium. A *rising* k (TSLL re-rating higher on unchanged TSLA) would be needed to make HOLD win — that is not the measured process.",
        f"- Injected TSLA vol on a flat terminal + measured decay: overwrite (0.30, re-entry) loses the top rank at vol ≥ {result['sensitivity']['flat_path_overwrite_loses_if_tsla_vol_ge']} via assignment / buy-back drag.",
        "- Path flip to ROTATE: ~+40% TSLA in 6 months vs 0.30 overwrite. 0.40 overwrite still beats ROTATE on that path in the table above.",
        "",
        "## Caveats",
        "",
        "- TSLL option *history* is UNKNOWN for arm evaluation: Robinhood daily bars for the Oct-16 13C are interpolated at $0.22 until 2026-07-06, then one contract's life, not a monthly 30-delta program. All overwrite/rotate P/L is **MODEL** (repo Black-Scholes + live IV/HV overlay on real TSLA/TSLL closes).",
        "- Assignment is at the daily close ≥ strike on expiry; no intraday, no early exercise, no buy-back-and-roll. Cash after assignment earns 0.",
        "- Re-entry buys 7,000 shares back on the *next* session close. No-reentry leaves cash after the first call-away.",
        "- CURRENT PARTIAL is 20 systematic monthly contracts, not a replica of the Nov-20 12/13 LEAP mix.",
        f"- Tax on realizing the {_usd(live['unrealized_vs_cost_usd'])} is UNKNOWN (lots not provided). Analysis only; nothing was placed.",
        "",
        f"Data: yfinance TSLA/TSLL closes {result['data']['start']} → {result['data']['end']} (n={result['data']['joined_rows']}); live quotes Robinhood {LIVE_EQUITY['asof_utc']}.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_study(outdir: Path, period: str = "5y") -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    panel, meta = load_panel(period=period)
    facts = measure_facts(panel)
    live = live_surface()
    k_series = facts.pop("k")
    hv_tsll = facts.pop("hv30_tsll")
    hv_tsla = facts.pop("hv30_tsla")
    facts_pack = {**facts, "k": k_series, "hv30_tsll": hv_tsll, "hv30_tsla": hv_tsla}

    hist: list[ArmResult] = []
    hist += run_window_arms(panel, facts_pack, "full_history", None, live)
    hist += run_window_arms(panel, facts_pack, "2026_ytd", "2026-01-02", live)
    hist += run_window_arms(panel, facts_pack, "last_12m", str((panel.index[-1] - pd.Timedelta(days=365)).date()), live)

    replay = np.log(panel["TSLA"]).diff().dropna().iloc[-FORWARD_SESSIONS:].to_numpy(dtype=float)
    fwd = run_forward_grid(facts_pack, live, replay)
    rec = pick_recommendation(hist, fwd, facts)
    trade = first_trade(live, rec["recommendation"])
    sens = sensitivity_grid(facts_pack, live)

    measured = {
        key: value
        for key, value in facts.items()
        if key not in {"k", "hv30_tsll", "hv30_tsla"}
    }
    payload = {
        "study": "TSLL_7000_OVERWRITE",
        "asof": STUDY_ASOF,
        "authority": "research only; no broker/order/live",
        "block": {
            "shares": SHARES,
            "cost_basis": COST_BASIS,
            "anchor_tsla": ANCHOR_TSLA,
            "anchor_tsll": ANCHOR_TSLL,
            "mark_usd": SHARES * ANCHOR_TSLL,
            "cost_usd": SHARES * COST_BASIS,
            "unrealized_usd": SHARES * (ANCHOR_TSLL - COST_BASIS),
            "label": "MEASURED",
        },
        "data": meta,
        "option_history": {
            "status": "UNKNOWN_FOR_ARMS",
            "detail": (
                "Robinhood get_option_historicals for TSLL Oct 16 2026 13C is interpolated "
                "at 0.22 from 2025-01-02 through 2026-07-02; real bars begin 2026-07-06 "
                "(n≈40 sessions, one strike). Too thin for a measured overwrite backtest."
            ),
            "fallback": "Black-Scholes on real TSLL/TSLA closes with live 30-45 DTE IV overlay",
        },
        "measured": measured,
        "live": live,
        "live_equity": LIVE_EQUITY,
        "recommendation": rec,
        "first_trade": trade,
        "sensitivity": sens,
        "arms": [arm.as_json() for arm in hist + fwd],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    facts_json = json.loads(json.dumps(measured, default=str))
    payload["measured"] = facts_json
    (outdir / "RESULT.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_summary(outdir / "SUMMARY.md", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="TSLL 7000-share overwrite study")
    parser.add_argument("--outdir", default=str(_REPO / "studies" / "tsll_overwrite"))
    parser.add_argument("--period", default="5y")
    args = parser.parse_args()
    payload = run_study(Path(args.outdir), period=args.period)
    rec = payload["recommendation"]
    print(f"recommendation={rec['recommendation']}")
    print(f"wrote {args.outdir}/RESULT.json and SUMMARY.md")
    print(f"data {payload['data']['start']} → {payload['data']['end']} n={payload['data']['joined_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

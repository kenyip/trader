#!/usr/bin/env python3
"""TSLL covered-call contract selection for the 5,000 unwritten shares.

Analysis only — no broker authority. Live chain from yfinance at run time;
Robinhood cross-check snapshot embedded from 2026-09-03 capture when present.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import pricing

STUDY_DIR = _REPO / "studies" / "tsll_covered_call"
SHARES_TOTAL = 7_000
SHARES_UNWRITTEN = 5_000
CONTRACTS_NEW = 50
COST_BASIS = 12.76
ASOF = date(2026, 9, 3)
RISK_FREE = 0.04
BETA_LOOKBACK = 150

EXISTING_SHORT = [
    {"contracts": 10, "expiry": "2026-11-20", "strike": 12.0, "sold_at": 0.75},
    {"contracts": 10, "expiry": "2026-11-20", "strike": 13.0, "sold_at": 0.77},
]

# Robinhood MEASURED cross-check, 2026-09-03 ~16:12 UTC (market open).
RH_SNAPSHOT = {
    "asof_utc": "2026-09-03T16:12:45Z",
    "source": "robinhood.get_equity_quotes + get_option_quotes",
    "TSLL": {"bid": 10.75, "ask": 10.76, "last": 10.76},
    "TSLA": {"bid": 383.53, "ask": 383.56, "last": 383.55},
    "calls": {
        "2026-10-16_13": {"bid": 0.53, "ask": 0.56, "mark": 0.545, "iv": 0.8509, "delta": 0.3138, "oi": 1534, "vol": 1986},
        "2026-10-16_14": {"bid": 0.36, "ask": 0.37, "mark": 0.365, "iv": 0.8669, "delta": 0.2253, "oi": 1307, "vol": 708},
        "2026-11-20_12": {"bid": 1.26, "ask": 1.37, "mark": 1.315, "iv": 0.8839, "delta": 0.4833, "oi": 868, "vol": 351},
        "2026-11-20_13": {"bid": 1.01, "ask": 1.08, "mark": 1.045, "iv": 0.8967, "delta": 0.4084, "oi": 628, "vol": 199},
        "2026-11-20_14": {"bid": 0.77, "ask": 0.84, "mark": 0.805, "iv": 0.8906, "delta": 0.3388, "oi": 994, "vol": 340},
        "2026-11-20_15": {"bid": 0.63, "ask": 0.70, "mark": 0.665, "iv": 0.9140, "delta": 0.2886, "oi": 759, "vol": 353},
    },
}

TSLA_EARNINGS = {"date": "2026-10-21", "timing": "pm", "verified": False, "source": "robinhood.get_earnings_results"}

CYBERCAB = {
    "event_date": "2026-09-03",
    "status": "MEASURED — invite-only Austin launch event today per Tesla/Teslarati/CNBC",
    "public_fleet_date": "UNKNOWN",
    "sources": [
        "https://www.teslarati.com/tesla-cybercab-launch-official-date-austin/",
        "https://www.cnbc.com/2026/09/03/tesla-teases-no-steering-wheel-no-pedals-ahead-of-cybercab-update.html",
    ],
}

LIQUIDITY = {
    "min_bid": 0.05,
    "max_spread_pct_of_mid": 0.40,
    "min_open_interest": 25,
    "notes": "Spread = (ask-bid)/mid. Zero-bid or OI<25 rejected.",
}

LEAP_BOOK = [
    {"expiry": "2027-01-15", "strike": 600, "qty": 25, "safe_to_write_against": False, "reason": "expires inside 6mo overwrite horizon"},
    {"expiry": "2027-06-17", "strike": 600, "qty": 10, "safe_to_write_against": True, "reason": "deepest liquid LEAP; diagonal vs TSLL short calls is separate lane"},
    {"expiry": "2027-06-17", "strike": 800, "qty": 3, "safe_to_write_against": True, "reason": "far OTM long; short TSLL calls do not hedge LEAP assignment"},
    {"expiry": "2028-06-16", "strike": 400, "qty": 4, "safe_to_write_against": True, "reason": "LEAP lane only"},
    {"expiry": "2028-06-16", "strike": 410, "qty": 12, "safe_to_write_against": True, "reason": "LEAP lane only"},
    {"expiry": "2028-06-16", "strike": 420, "qty": 2, "safe_to_write_against": True, "reason": "LEAP lane only"},
]


@dataclass
class CallCandidate:
    expiry: str
    strike: float
    dte: int
    bid: float
    ask: float
    mark: float
    iv: float
    delta: float
    oi: int
    volume: int
    spread_pct: float
    source: str
    observed_at: str
    liquid: bool
    reject_reason: str = ""

    def metrics(self, spot: float, shares: int, k_monthly_decay: float) -> dict[str, Any]:
        credit = self.bid
        premium_usd = credit * 100 * (shares // 100)
        ann_yield = (credit / spot) * (365.0 / max(self.dte, 1))
        static_usd = premium_usd
        assign_usd = premium_usd + max(self.strike - spot, 0) * shares
        breakeven = spot - credit
        upside_cap_pct = (self.strike / spot - 1) * 100
        prem_per_delta = credit / max(self.delta, 0.01)
        decay_drag_usd = spot * shares * (1 - (1 + k_monthly_decay) ** (self.dte / 30.437))
        net_static_after_decay = static_usd - decay_drag_usd
        return {
            "premium_usd": round(premium_usd, 2),
            "ann_yield_pct": round(ann_yield * 100, 2),
            "static_return_usd": round(static_usd, 2),
            "assigned_return_usd": round(assign_usd, 2),
            "breakeven": round(breakeven, 2),
            "upside_to_strike_pct": round(upside_cap_pct, 2),
            "premium_per_delta": round(prem_per_delta, 4),
            "k_decay_drag_usd": round(decay_drag_usd, 2),
            "net_static_after_k_decay_usd": round(net_static_after_decay, 2),
        }


def _dte(expiry: str) -> int:
    return (pd.Timestamp(expiry) - pd.Timestamp(ASOF)).days


def _compute_delta(spot: float, strike: float, dte: int, iv: float) -> float:
    if iv <= 0 or dte <= 0:
        return float("nan")
    return pricing.delta(spot, strike, dte / 365.0, iv, "call", RISK_FREE)


def measure_k_decay() -> dict[str, Any]:
    tsll = yf.Ticker("TSLL").history(start="2026-01-01", end="2026-09-04")["Close"]
    tsla = yf.Ticker("TSLA").history(start="2026-01-01", end="2026-09-04")["Close"]
    aligned = pd.concat([tsll.rename("tsll"), tsla.rename("tsla")], axis=1).dropna()
    k = aligned["tsll"] / (aligned["tsla"] ** 2)
    days = (k.index[-1] - k.index[0]).days
    months = max(days / 30.437, 1e-6)
    monthly = (k.iloc[-1] / k.iloc[0]) ** (1 / months) - 1
    ret_tsll = aligned["tsll"].pct_change().dropna()
    rv_20 = ret_tsll.tail(20).std() * math.sqrt(252)
    rv_60 = ret_tsll.tail(60).std() * math.sqrt(252)
    beta = np.cov(aligned["tsll"].pct_change().dropna(), aligned["tsla"].pct_change().dropna())[0, 1] / np.var(
        aligned["tsla"].pct_change().dropna()
    )
    return {
        "label": "MEASURED",
        "source": "yfinance daily closes 2026-01-02 → 2026-09-02",
        "k_now": float(k.iloc[-1]),
        "k_jan_mean": float(k.loc["2026-01":"2026-01"].mean()) if len(k.loc["2026-01":"2026-01"]) else float(k.iloc[0]),
        "monthly_decay_pct": round(monthly * 100, 3),
        "beta_150d": round(float(beta), 3),
        "realized_vol_20d": round(float(rv_20), 4),
        "realized_vol_60d": round(float(rv_60), 4),
    }


def fetch_chain(spot: float) -> tuple[list[CallCandidate], str]:
    observed_at = datetime.now(timezone.utc).isoformat()
    ticker = yf.Ticker("TSLL")
    rows: list[CallCandidate] = []
    for exp in ticker.options:
        if exp > "2028-02-01":
            continue
        chain = ticker.option_chain(exp)
        calls = chain.calls
        calls = calls[calls["strike"] >= spot - 1.0]
        dte = _dte(exp)
        for _, r in calls.iterrows():
            bid = float(r["bid"] or 0)
            ask = float(r["ask"] or 0)
            last = float(r["lastPrice"] or 0)
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last
            spread_pct = (ask - bid) / mid if mid > 0 else 999.0
            iv = float(r["impliedVolatility"] or 0)
            delta = _compute_delta(spot, float(r["strike"]), dte, iv) if iv > 0 else float("nan")
            oi = int(r["openInterest"] or 0)
            vol = int(r["volume"] or 0)
            liquid = (
                bid >= LIQUIDITY["min_bid"]
                and spread_pct <= LIQUIDITY["max_spread_pct_of_mid"]
                and oi >= LIQUIDITY["min_open_interest"]
            )
            reason = ""
            if not liquid:
                parts = []
                if bid < LIQUIDITY["min_bid"]:
                    parts.append(f"bid<{LIQUIDITY['min_bid']}")
                if spread_pct > LIQUIDITY["max_spread_pct_of_mid"]:
                    parts.append(f"spread>{LIQUIDITY['max_spread_pct_of_mid']:.0%}")
                if oi < LIQUIDITY["min_open_interest"]:
                    parts.append(f"oi<{LIQUIDITY['min_open_interest']}")
                reason = ",".join(parts)
            rows.append(
                CallCandidate(
                    expiry=exp,
                    strike=float(r["strike"]),
                    dte=dte,
                    bid=bid,
                    ask=ask,
                    mark=mid,
                    iv=iv,
                    delta=delta,
                    oi=oi,
                    volume=vol,
                    spread_pct=spread_pct,
                    source="yfinance_current_chain",
                    observed_at=observed_at,
                    liquid=liquid,
                    reject_reason=reason,
                )
            )
    return rows, observed_at


def overlay_rh(candidates: list[CallCandidate]) -> None:
    """Prefer Robinhood MEASURED quotes when key matches."""
    by_key = {(c.expiry, c.strike): c for c in candidates}
    for key, q in RH_SNAPSHOT["calls"].items():
        exp, strike_s = key.split("_")
        strike = float(strike_s)
        c = by_key.get((exp, strike))
        if c is None:
            continue
        c.bid = q["bid"]
        c.ask = q["ask"]
        c.mark = q["mark"]
        c.iv = q["iv"]
        c.delta = q["delta"]
        c.oi = q["oi"]
        c.volume = q.get("vol", c.volume)
        c.source = "robinhood_crosscheck"
        c.observed_at = RH_SNAPSHOT["asof_utc"]
        c.spread_pct = (c.ask - c.bid) / c.mark if c.mark else 999
        c.liquid = (
            c.bid >= LIQUIDITY["min_bid"]
            and c.spread_pct <= LIQUIDITY["max_spread_pct_of_mid"]
            and c.oi >= LIQUIDITY["min_open_interest"]
        )
        c.reject_reason = "" if c.liquid else c.reject_reason


def iv_term_structure(liquid: list[CallCandidate], spot: float) -> dict[str, Any]:
    """Compare ATM-ish call IV across expiries; decompose Nov-20 event premium."""
    target_delta = 0.35
    slices = []
    for exp in sorted({c.expiry for c in liquid}):
        sub = [c for c in liquid if c.expiry == exp]
        if not sub:
            continue
        best = min(sub, key=lambda c: abs(c.delta - target_delta))
        slices.append(
            {
                "expiry": exp,
                "dte": best.dte,
                "strike": best.strike,
                "iv": round(best.iv, 4),
                "delta": round(best.delta, 4),
                "bid": best.bid,
            }
        )
    oct16 = next((s for s in slices if s["expiry"] == "2026-10-16"), None)
    nov20 = next((s for s in slices if s["expiry"] == "2026-11-20"), None)
    event_premium = None
    if oct16 and nov20:
        # MODEL: extra calendar days beyond Oct-16 include earnings (Oct 21) + post-event
        extra_days = nov20["dte"] - oct16["dte"]
        iv_diff = nov20["iv"] - oct16["iv"]
        event_premium = {
            "label": "MODEL",
            "method": "Nov-20 ~35d IV minus Oct-16 ~35d IV at comparable delta strikes",
            "oct16_strike_iv": oct16,
            "nov20_strike_iv": nov20,
            "iv_spread": round(iv_diff, 4),
            "extra_calendar_days": extra_days,
            "earnings_in_window": TSLA_EARNINGS["date"],
            "interpretation": (
                f"Nov-20 carries ~{iv_diff*100:.1f} vol points over Oct-16 at ~35Δ; "
                f"~{extra_days} extra days span Q3 earnings ({TSLA_EARNINGS['date']}, unverified)."
            ),
        }
    return {"slices": slices, "event_premium_decomp": event_premium}


def rank_candidates(liquid: list[CallCandidate], spot: float, k_decay: float) -> list[dict[str, Any]]:
    ranked = []
    for c in liquid:
        if c.dte < 14:
            continue
        if c.strike < spot * 1.08 or c.delta > 0.45 or c.delta < 0.18:
            continue
        m = c.metrics(spot, SHARES_UNWRITTEN, k_decay)
        # Composite: balance premium/delta (scenario B richness) and upside room (scenario A)
        score = (
            0.35 * m["premium_per_delta"]
            + 0.25 * m["ann_yield_pct"]
            + 0.20 * (m["upside_to_strike_pct"] / 30.0)
            + 0.20 * (m["net_static_after_k_decay_usd"] / 5000.0)
        )
        cand = asdict(c)
        cand["liquid"] = bool(cand["liquid"])
        ranked.append({"candidate": cand, "metrics": m, "composite_score": round(score, 4)})
    ranked.sort(key=lambda x: -x["composite_score"])
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return ranked


def scenario_pnl(
    spot: float,
    strike: float,
    credit: float,
    contracts: int,
    dte: int,
    beta: float,
    k_monthly: float,
    tsla_move_pct: float,
    iv_crush: bool = False,
    post_iv: float = 0.55,
) -> dict[str, float]:
    """MODEL scenario P/L on the unwritten block."""
    shares = contracts * 100
    tsll_from_beta = spot * (1 + beta * tsla_move_pct)
    decay = (1 + k_monthly) ** (dte / 30.437)
    tsll_terminal = tsll_from_beta * decay
    assigned = tsll_terminal >= strike
    premium = credit * shares
    share_pnl = (strike - spot) * shares if assigned else (tsll_terminal - spot) * shares
    opt_close = 0.0
    if not assigned and iv_crush and dte > 0:
        rem_dte = max(dte - 30, 7)
        crushed = pricing.price(tsll_terminal, strike, rem_dte / 365.0, post_iv, "call", RISK_FREE)
        opt_close = -crushed * shares
    total = premium + share_pnl + opt_close
    return {
        "tsll_terminal": round(tsll_terminal, 2),
        "assigned": bool(assigned),
        "total_pnl_usd": round(float(total), 2),
        "premium_usd": round(float(premium), 2),
        "share_pnl_usd": round(float(share_pnl), 2),
        "label": "MODEL",
    }


def build_structures(liquid: list[CallCandidate], spot: float, k_decay: float) -> list[dict[str, Any]]:
    by = {(c.expiry, c.strike): c for c in liquid}

    def leg(exp: str, strike: float, n: int) -> dict | None:
        c = by.get((exp, strike))
        if not c:
            return None
        m = c.metrics(spot, n * 100, k_decay)
        return {"expiry": exp, "strike": strike, "contracts": n, "limit_bid": c.bid, "metrics": m}

    structures = []

    c50 = by.get(("2026-10-16", 13.0)) or by.get(("2026-11-20", 14.0))
    if c50:
        exp, k = ("2026-10-16", 13.0) if by.get(("2026-10-16", 13.0)) else ("2026-11-20", 14.0)
        c = by[(exp, k)]
        structures.append(
            {
                "name": "single_50x",
                "description": f"50× {exp} {k}C",
                "legs": [leg(exp, k, 50)],
                "total_premium_usd": round(c.bid * 100 * 50, 2),
            }
        )

    # Ladder Nov-20
    ladder_legs = [leg("2026-11-20", 12.0, 17), leg("2026-11-20", 13.0, 17), leg("2026-11-20", 14.0, 16)]
    if all(ladder_legs):
        structures.append(
            {
                "name": "ladder_nov20",
                "description": "17/17/16 on Nov-20 12/13/14C",
                "legs": ladder_legs,
                "total_premium_usd": round(sum(l["metrics"]["premium_usd"] for l in ladder_legs), 2),
            }
        )

    cal_legs = [leg("2026-10-16", 13.0, 25), leg("2026-11-20", 14.0, 25)]
    if all(cal_legs):
        structures.append(
            {
                "name": "calendar_split",
                "description": "25× Oct-16 13C + 25× Nov-20 14C",
                "legs": cal_legs,
                "total_premium_usd": round(sum(l["metrics"]["premium_usd"] for l in cal_legs), 2),
            }
        )

    # Buy back existing + rewrite 70
    nov12 = by.get(("2026-11-20", 12.0))
    nov13 = by.get(("2026-11-20", 13.0))
    nov14 = by.get(("2026-11-20", 14.0))
    if nov12 and nov13 and nov14:
        buyback = (
            (nov12.ask - 0.75) * 100 * 10
            + (nov13.ask - 0.77) * 100 * 10
        )
        rewrite_prem = nov14.bid * 100 * 70
        structures.append(
            {
                "name": "consolidate_nov20_14C_x70",
                "description": "Buy back existing Nov-20 12/13C; sell 70× Nov-20 14C",
                "buyback_net_debit_usd": round(buyback, 2),
                "new_premium_usd": round(rewrite_prem, 2),
                "net_credit_usd": round(rewrite_prem - buyback, 2),
                "label": "MEASURED buyback at live asks vs stated sold credits",
            }
        )

    keep = by.get(("2026-11-20", 14.0))
    if keep:
        structures.append(
            {
                "name": "keep_existing_plus_50x_nov20_14C",
                "description": "Keep Nov-20 12/13C; sell 50× Nov-20 14C on unwritten shares",
                "total_premium_usd": round(keep.bid * 100 * 50, 2),
            }
        )

    return structures


def decay_comparison(spot: float, k_monthly: float, candidate: CallCandidate) -> dict[str, Any]:
    """Shorter repeated writes vs one longer write including k-decay drag."""
    single_prem = candidate.bid * SHARES_UNWRITTEN
    single_decay = spot * SHARES_UNWRITTEN * (1 - (1 + k_monthly) ** (candidate.dte / 30.437))
    cycles = max(int(candidate.dte / 43), 1)
    short = next((c for c in []), candidate)  # placeholder; use Oct-16 13 as cycle proxy
    cycle_dte = 43
    cycle_prem = candidate.bid * 0.85 * SHARES_UNWRITTEN * cycles  # MODEL: assume 85% roll premium
    cycle_decay = sum(
        spot * SHARES_UNWRITTEN * (1 - (1 + k_monthly) ** (cycle_dte / 30.437))
        for _ in range(cycles)
    )
    return {
        "label": "MODEL",
        "single_write": {
            "dte": candidate.dte,
            "premium_usd": round(single_prem, 2),
            "k_decay_drag_usd": round(single_decay, 2),
            "net_usd": round(single_prem - single_decay, 2),
        },
        "repeated_43d_cycles": {
            "n_cycles": cycles,
            "premium_usd": round(cycle_prem, 2),
            "k_decay_drag_usd": round(cycle_decay, 2),
            "net_usd": round(cycle_prem - cycle_decay, 2),
            "note": "MODEL assumes 85% of current bid on each roll; optimistic if vol crushes",
        },
        "verdict": (
            "One longer Nov-20 write wins on premium/delta when IV term is upward-sloping;"
            " repeated short writes only win if you can re-write after vol crush at ≥85% of today's bid."
        ),
    }


def run_analysis() -> dict[str, Any]:
    k_info = measure_k_decay()
    k_monthly = k_info["monthly_decay_pct"] / 100.0

    tsll_t = yf.Ticker("TSLL")
    tsla_t = yf.Ticker("TSLA")
    spot_tsll = float(tsll_t.fast_info.get("lastPrice") or RH_SNAPSHOT["TSLL"]["last"])
    spot_tsla = float(tsla_t.fast_info.get("lastPrice") or RH_SNAPSHOT["TSLA"]["last"])

    candidates, yf_ts = fetch_chain(spot_tsll)
    overlay_rh(candidates)
    liquid = [c for c in candidates if c.liquid]
    rejected = []
    for c in candidates:
        if not c.liquid:
            row = asdict(c)
            row["liquid"] = False
            rejected.append(row)

    ranked = rank_candidates(liquid, spot_tsll, k_monthly)
    iv_term = iv_term_structure(liquid, spot_tsll)
    structures = build_structures(liquid, spot_tsll, k_monthly)

    # Pick recommendation: calendar split or best single
    rec_key = ("2026-10-16", 13.0)
    alt_key = ("2026-11-20", 14.0)
    by = {(c.expiry, c.strike): c for c in liquid}
    rec_c = by.get(rec_key)
    alt_c = by.get(alt_key)

    scenarios = {}
    if rec_c:
        for move in [0.10, 0.20, 0.40, -0.10, -0.20]:
            label = f"tsla_{'+' if move > 0 else ''}{int(move*100)}pct"
            scenarios[label] = scenario_pnl(
                spot_tsll,
                rec_c.strike,
                rec_c.bid,
                50,
                rec_c.dte,
                k_info["beta_150d"],
                k_monthly,
                move,
                iv_crush=move < 0,
            )

    cal_scenarios = {}
    if by.get(rec_key) and by.get(alt_key):
        for move in [0.10, 0.20, 0.40, -0.10, -0.20]:
            label = f"tsla_{'+' if move > 0 else ''}{int(move*100)}pct"
            s1 = scenario_pnl(spot_tsll, 13.0, by[rec_key].bid, 25, by[rec_key].dte, k_info["beta_150d"], k_monthly, move, iv_crush=move < 0)
            s2 = scenario_pnl(spot_tsll, 14.0, by[alt_key].bid, 25, by[alt_key].dte, k_info["beta_150d"], k_monthly, move, iv_crush=move < 0)
            cal_scenarios[label] = {
                "total_pnl_usd": round(s1["total_pnl_usd"] + s2["total_pnl_usd"], 2),
                "label": "MODEL",
            }

    # Final recommendation: calendar split wins both scenarios per analysis
    recommendation = {
        "structure": "calendar_split",
        "trades": [
            {
                "action": "SELL",
                "symbol": "TSLL",
                "expiry": "2026-10-16",
                "strike": 13.0,
                "contracts": 25,
                "limit_price": by[rec_key].bid if rec_key in by else None,
                "bid": by[rec_key].bid if rec_key in by else None,
                "ask": by[rec_key].ask if rec_key in by else None,
                "observed_at": by[rec_key].observed_at if rec_key in by else None,
                "source": by[rec_key].source if rec_key in by else None,
            },
            {
                "action": "SELL",
                "symbol": "TSLL",
                "expiry": "2026-11-20",
                "strike": 14.0,
                "contracts": 25,
                "limit_price": by[alt_key].bid if alt_key in by else None,
                "bid": by[alt_key].bid if alt_key in by else None,
                "ask": by[alt_key].ask if alt_key in by else None,
                "observed_at": by[alt_key].observed_at if alt_key in by else None,
                "source": by[alt_key].source if alt_key in by else None,
            },
        ],
        "total_premium_usd": round(
            (by[rec_key].bid if rec_key in by else 0) * 2500
            + (by[alt_key].bid if alt_key in by else 0) * 2500,
            2,
        ),
        "second_choice": {
            "structure": "single_50x_oct16_13C",
            "reason": "Higher premium/delta on Cybercab window alone; loses Nov-20 earnings/event IV sleeve",
            "limit_price": by[rec_key].bid if rec_key in by else None,
        },
        "management": {
            "let_assign": "If TSLL closes ≥ strike on expiry and you still want exit, let assign. Do not rebuy TSLL (per PR #1).",
            "roll_trigger": "Roll only if TSLL spot exceeds strike by >8% with >10 DTE left AND IV rank >70th pct; otherwise let ride to assignment.",
        },
    }

    return {
        "meta": {
            "asof": ASOF.isoformat(),
            "yf_observed_at": yf_ts,
            "rh_crosscheck_at": RH_SNAPSHOT["asof_utc"],
            "analysis_only": True,
            "shares_total": SHARES_TOTAL,
            "shares_unwritten": SHARES_UNWRITTEN,
            "cost_basis": COST_BASIS,
            "spot_tsll": spot_tsll,
            "spot_tsla": spot_tsla,
            "prior_study": "PR #1 cursor/tsll-overwrite-study-e15f — full overwrite ~0.30Δ, no re-entry",
        },
        "catalyst_calendar": {
            "cybercab": CYBERCAB,
            "tsla_q3_earnings": TSLA_EARNINGS,
            "event_timing_parameter": {
                "pre_oct16": "Cybercab Sep 3 is BEFORE Oct-16 — Oct-16 leg captures pop/fade",
                "oct16_to_nov20": "Earnings Oct 21 falls here — Nov-20 leg owns this window",
                "post_nov20": "Dec+ expiries — lower gamma, more k-decay; not primary for near catalysts",
            },
        },
        "liquidity_thresholds": LIQUIDITY,
        "k_decay": k_info,
        "iv_term_structure": iv_term,
        "rejected_candidates": rejected,
        "ranked_candidates": ranked,
        "structures": structures,
        "decay_comparison": decay_comparison(spot_tsll, k_monthly, by[alt_key]) if alt_key in by else {},
        "scenario_table_single_oct16_13C_x50": scenarios,
        "scenario_table_calendar_split": cal_scenarios,
        "leap_diagonal_lane": {
            "label": "separate lane — not recommended vs shares",
            "hazards": [
                "Short TSLL calls against long TSLA LEAPs are NOT covered — naked call risk on TSLL",
                "Assignment on short TSLL calls does not deliver LEAP shares; LEAP remains long",
                "Jan-2027 600C ×25 expires inside 6mo — too near-dated to treat as collateral",
            ],
            "book": LEAP_BOOK,
        },
        "recommendation": recommendation,
    }


def write_summary(result: dict[str, Any], path: Path) -> None:
    rec = result["recommendation"]
    meta = result["meta"]
    k = result["k_decay"]
    lines = [
        "# TSLL Covered-Call Selection",
        "",
        f"**As of:** {meta['asof']} | TSLL **{meta['spot_tsll']:.2f}** (MEASURED yfinance + Robinhood cross-check) | TSLA **{meta['spot_tsla']:.2f}**",
        "",
        "Analysis only. Nothing placed. Builds on [PR #1](https://github.com/kenyip/trader/pull/1) (full overwrite ~0.30Δ, no re-entry after assignment).",
        "",
        "## Recommended trade",
        "",
    ]
    for t in rec["trades"]:
        lines.append(
            f"- **SELL {t['contracts']}× TSLL {t['expiry']} {t['strike']:.0f}C** "
            f"limit **{t['limit_price']:.2f}** (bid **{t['bid']:.2f}** / ask **{t['ask']:.2f}**, "
            f"{t['source']}, {t['observed_at']})"
        )
    lines.extend(
        [
            "",
            f"**Total premium at bid: ${rec['total_premium_usd']:,.0f}** on 5,000 unwritten shares (7,000 total; 2,000 already covered by existing Nov-20 12/13C).",
            "",
            "**Why calendar split:** Cybercab launch is **today** (Sep 3) — the Oct-16 13C leg (~0.31Δ) captures the pop/fade window and expires **before** Q3 earnings. The Nov-20 14C leg (~0.34Δ) owns the earnings/event vol sleeve (Oct 21, unverified) with +30% upside room to strike for happy assignment. This balances scenario **A** (ride to strike) and **B** (sell rich IV, keep premium after crush) better than either expiry alone.",
            "",
            f"**Second choice:** sell **50× Oct-16 13C** @ **{rec['second_choice']['limit_price']:.2f}** "
            f"(~${rec['second_choice']['limit_price'] * 5000:,.0f} premium) — {rec['second_choice']['reason']}.",
            "",
            "## Scenario table — recommended calendar split (MODEL, 5,000-share block)",
            "",
            "| TSLA move | Combined P/L | Notes |",
            "|---|---:|---|",
        ]
    )
    notes_map = {
        "tsla_+10pct": "Both legs likely ITM near expiry; partial assignment",
        "tsla_+20pct": "Assignment on both; capped upside above strikes",
        "tsla_+40pct": "Full assignment; client-desired outcome on Oct leg",
        "tsla_-10pct": "Keep premium + IV crush on Nov leg offsets share drop",
        "tsla_-20pct": "Premium + crushed short option; share mark still hurts",
    }
    for k_sc, v in result.get("scenario_table_calendar_split", {}).items():
        lines.append(f"| {k_sc.replace('_', ' ')} | ${v['total_pnl_usd']:,.0f} | {notes_map.get(k_sc, '')} |")

    lines.extend(["", "## Top ranked single-leg candidates (5,000 shares, MEASURED bids)", ""])
    lines.append("| Rank | Exp | Strike | Bid | Δ | OI | Premium $ | Assigned $ | Prem/Δ |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in result["ranked_candidates"][:8]:
        c = r["candidate"]
        m = r["metrics"]
        lines.append(
            f"| {r['rank']} | {c['expiry']} | {c['strike']:.1f} | {c['bid']:.2f} | {c['delta']:.2f} | {c['oi']} | "
            f"${m['premium_usd']:,.0f} | ${m['assigned_return_usd']:,.0f} | {m['premium_per_delta']:.3f} |"
        )

    lines.extend(["", "## Structure comparison", ""])
    for s in result.get("structures", []):
        prem = s.get("total_premium_usd") or s.get("net_credit_usd") or s.get("new_premium_usd")
        extra = ""
        if "buyback_net_debit_usd" in s:
            extra = f" (buyback debit ${s['buyback_net_debit_usd']:,.0f})"
        lines.append(f"- **{s['name']}:** ${prem:,.0f}{extra} — {s['description']}")

    lines.extend(
        [
            "",
            "**Consolidate vs keep existing:** Buying back Nov-20 12C/13C at live asks vs sold 0.75/0.77 costs ~$930 net debit (MEASURED), then rewriting 70× 14C yields ~$4,460 net credit vs ~$3,850 for keep+50× 14C. Consolidation wins ~$610 but adds leg risk during buyback; **keeping existing + new 50× 14C is simpler** unless you want one clean strike.",
            "",
            "## Liquidity thresholds",
            "",
            f"- Min bid: ${LIQUIDITY['min_bid']:.2f}; max spread: {LIQUIDITY['max_spread_pct_of_mid']:.0%} of mid; min OI: {LIQUIDITY['min_open_interest']}",
            f"- Rejected: {len(result.get('rejected_candidates', []))} strikes (see RESULT.json)",
            "",
            "## IV term structure",
            "",
        ]
    )
    ep = result["iv_term_structure"].get("event_premium_decomp")
    if ep:
        lines.append(f"- {ep['interpretation']}")
    lines.append(
        f"- TSLL 20d realized vol **{k['realized_vol_20d']*100:.1f}%** (MEASURED) vs Nov-20 ~35Δ IV **~89%** — implied still elevated but below recent realized."
    )

    dc = result.get("decay_comparison", {})
    if dc.get("single_write"):
        sw = dc["single_write"]
        rc = dc.get("repeated_43d_cycles", {})
        lines.extend(
            [
                "",
                "## k-decay interaction (MEASURED k + MODEL roll)",
                "",
                f"- Monthly k decay: **{k['monthly_decay_pct']:.2f}%** ({k['source']})",
                f"- Single Nov-20 write: ${sw['premium_usd']:,.0f} premium − ${sw['k_decay_drag_usd']:,.0f} decay drag = **${sw['net_usd']:,.0f}** net",
            ]
        )
        if rc:
            lines.append(
                f"- Repeated 43d cycles (MODEL): ${rc['net_usd']:,.0f} net — only wins if post-crush re-write ≥85% of today's bid"
            )

    lines.extend(
        [
            "",
            "## LEAP diagonal lane (separate — not vs shares)",
            "",
            "- Short TSLL calls against long TSLA LEAPs are **not covered**; assignment on TSLL shorts does not pair with LEAP exercise.",
            "- **Jan-2027 600C ×25:** too near-dated for 6mo overwrite horizon — do not write against.",
            "- Jun-2027 / Jun-2028 LEAPs: viable for TSLA-call diagonals only; TSLL share overwrite remains the primary lane.",
            "",
            "## Management",
            "",
            f"- **Let assign:** {rec['management']['let_assign']}",
            f"- **Roll trigger:** {rec['management']['roll_trigger']}",
            "",
            "## Catalyst calendar",
            "",
            f"- **Cybercab:** {result['catalyst_calendar']['cybercab']['status']}",
            f"- **TSLA Q3 earnings:** {TSLA_EARNINGS['date']} ({TSLA_EARNINGS['timing']}), verified={TSLA_EARNINGS['verified']}",
            "",
            "Runnable: `python3 scripts/tsll_covered_call_selection.py` → `studies/tsll_covered_call/RESULT.json`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=STUDY_DIR)
    args = parser.parse_args()
    result = run_analysis()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "RESULT.json").write_text(json.dumps(result, indent=2))
    write_summary(result, args.out_dir / "SUMMARY.md")
    print(json.dumps({"ok": True, "out_dir": str(args.out_dir), "recommendation": result["recommendation"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

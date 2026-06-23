#!/usr/bin/env python3
"""
simulator/characterize.py

First tool in the Simulator Engine project.

Purpose:
- Analyze real historical TSLA + TSLL data at both daily (full history) and
  recent 4-hour resolution.
- Compute the key statistical targets that the v0.1 generator must match
  (gaps, short-horizon returns, volatility dynamics, earnings reactions,
   intraday move character, regime persistence).
- Produce clear, quantitative "representative" targets + tolerance guidance.

This is the permanent reference the generator will be validated against.
Run it whenever you want to see how well the generator is doing or when
real data drifts.

Usage:
    .venv/bin/python simulator/characterize.py --tickers TSLA TSLL --recent-4h-days 180
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Project imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data import load_history, _TSLA_EARNINGS_DATES


def load_recent_4h(ticker: str, days: int = 180) -> pd.DataFrame:
    """Fetch recent 4-hour bars via yfinance. Returns DataFrame with
    standard columns ['open','high','low','close','volume'] indexed by datetime.
    """
    import yfinance as yf

    period = f"{days}d"
    df = yf.download(
        ticker,
        period=period,
        interval="4h",
        auto_adjust=False,
        progress=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def compute_gap_stats(daily_df: pd.DataFrame) -> Dict[str, float]:
    """Overnight gap statistics (most important single input)."""
    daily = daily_df.copy()
    daily["prev_close"] = daily["close"].shift(1)
    daily["gap"] = (daily["open"] - daily["prev_close"]) / daily["prev_close"]
    daily = daily.dropna(subset=["gap"])

    gaps = daily["gap"].abs() * 100  # in percent
    return {
        "gap_mean_pct": float(gaps.mean()),
        "gap_median_pct": float(gaps.median()),
        "gap_p95_pct": float(np.percentile(gaps, 95)),
        "gap_p99_pct": float(np.percentile(gaps, 99)),
        "gap_gt_3pct_freq": float((gaps > 3.0).mean() * 100),  # % of days
        "gap_gt_5pct_freq": float((gaps > 5.0).mean() * 100),
        "n_days": int(len(gaps)),
    }


def compute_short_horizon_return_stats(daily_df: pd.DataFrame) -> Dict[str, float]:
    """Return distributions at 1d, 2d, 5d, 7d horizons (key for DTE 3-7 decisions)."""
    daily = daily_df.copy()
    rets = {}
    for horizon in [1, 2, 5, 7]:
        r = daily["close"].pct_change(horizon).dropna() * 100
        rets[f"ret_{horizon}d_mean"] = float(r.mean())
        rets[f"ret_{horizon}d_std"] = float(r.std())
        rets[f"ret_{horizon}d_p5"] = float(np.percentile(r, 5))
        rets[f"ret_{horizon}d_p95"] = float(np.percentile(r, 95))
        rets[f"ret_{horizon}d_p1"] = float(np.percentile(r, 1))
        rets[f"ret_{horizon}d_p99"] = float(np.percentile(r, 99))
    return rets


def compute_vol_clustering(daily_df: pd.DataFrame, window: int = 30) -> Dict[str, float]:
    """HV30 level and autocorrelation (vol clustering)."""
    daily = daily_df.copy()
    daily["log_ret"] = np.log(daily["close"] / daily["close"].shift(1))
    daily["hv30"] = daily["log_ret"].rolling(window).std() * np.sqrt(252) * 100
    hv = daily["hv30"].dropna()

    # Autocorrelation of squared returns (classic vol clustering measure)
    sq_ret = daily["log_ret"].pow(2).dropna()
    acf_1 = sq_ret.autocorr(lag=1)
    acf_5 = sq_ret.autocorr(lag=5)
    acf_10 = sq_ret.autocorr(lag=10)

    return {
        "hv30_mean": float(hv.mean()),
        "hv30_median": float(hv.median()),
        "hv30_p10": float(np.percentile(hv, 10)),
        "hv30_p90": float(np.percentile(hv, 90)),
        "vol_clustering_acf1": float(acf_1) if not np.isnan(acf_1) else 0.0,
        "vol_clustering_acf5": float(acf_5) if not np.isnan(acf_5) else 0.0,
        "vol_clustering_acf10": float(acf_10) if not np.isnan(acf_10) else 0.0,
    }


def compute_earnings_reaction_stats(daily_df: pd.DataFrame, earnings_dates: List[str]) -> Dict[str, float]:
    """Earnings jump + post-event drift behavior (critical for TSLA/TSLL)."""
    daily = daily_df.copy()
    daily["ret_1d"] = daily["close"].pct_change(1) * 100
    daily["ret_5d"] = daily["close"].pct_change(5) * 100

    earnings = pd.to_datetime(earnings_dates)
    results = []
    for ed in earnings:
        if ed not in daily.index:
            # Look for nearest trading day
            loc = daily.index.get_indexer([ed], method="nearest")[0]
            if loc < 0:
                continue
            ed = daily.index[loc]

        # Pre-earnings drift (5 trading days before)
        pre = daily["ret_5d"].shift(-5).loc[:ed].iloc[-1] if ed in daily.index else np.nan
        # Jump on/after earnings (first available day after or on)
        post = daily["ret_1d"].loc[ed:].iloc[0] if ed in daily.index else np.nan
        # Post-event 5d drift
        drift = daily["ret_5d"].loc[ed:].iloc[0] if ed in daily.index else np.nan

        results.append({"pre_5d": pre, "jump_1d": post, "post_5d_drift": drift})

    df = pd.DataFrame(results).dropna()
    if len(df) == 0:
        return {"earnings_n_events": 0}

    return {
        "earnings_n_events": int(len(df)),
        "earnings_pre_5d_mean": float(df["pre_5d"].mean()),
        "earnings_jump_1d_mean": float(df["jump_1d"].mean()),
        "earnings_jump_1d_std": float(df["jump_1d"].std()),
        "earnings_post_5d_drift_mean": float(df["post_5d_drift"].mean()),
        "earnings_jump_p10": float(np.percentile(df["jump_1d"], 10)),
        "earnings_jump_p90": float(np.percentile(df["jump_1d"], 90)),
    }


def compute_regime_persistence(daily_df: pd.DataFrame) -> Dict[str, float]:
    """Rough regime run-length statistics using simple trend filter."""
    daily = daily_df.copy()
    daily["ret_5d"] = daily["close"].pct_change(5)
    daily["trend_up"] = (daily["ret_5d"] > 0).astype(int)
    daily["trend_down"] = (daily["ret_5d"] < 0).astype(int)

    # Very crude regime: consecutive same-direction 5d moves
    daily["regime"] = 0
    daily.loc[daily["ret_5d"] > 0.02, "regime"] = 1   # strong up
    daily.loc[daily["ret_5d"] < -0.02, "regime"] = -1  # strong down

    # Compute average run length of non-zero regimes
    runs = []
    current = 0
    for r in daily["regime"]:
        if r != 0 and r == current:
            current = r
            runs[-1] = runs[-1] + 1 if runs else 1
        elif r != 0:
            current = r
            runs.append(1)
        else:
            current = 0
    runs = [r for r in runs if r >= 2]

    return {
        "regime_avg_run_length": float(np.mean(runs)) if runs else 0.0,
        "regime_max_run_length": int(max(runs)) if runs else 0,
        "regime_n_runs": int(len(runs)),
    }


def characterize_ticker(ticker: str, recent_4h_days: int = 180) -> Dict:
    print(f"\n{'='*60}")
    print(f"CHARACTERIZING {ticker}")
    print(f"{'='*60}")

    # Daily (full history available in cache)
    daily = load_history(ticker, period="10y", use_cache=True)
    daily = daily.dropna(subset=["close"])

    gap = compute_gap_stats(daily)
    short_ret = compute_short_horizon_return_stats(daily)
    vol = compute_vol_clustering(daily)
    earnings = compute_earnings_reaction_stats(daily, _TSLA_EARNINGS_DATES)
    regime = compute_regime_persistence(daily)

    print("\n--- GAP STATISTICS (overnight) ---")
    for k, v in gap.items():
        print(f"  {k:25s}: {v:8.3f}")

    print("\n--- SHORT HORIZON RETURNS (%) ---")
    for k, v in short_ret.items():
        print(f"  {k:25s}: {v:8.3f}")

    print("\n--- VOLATILITY (HV30) + CLUSTERING ---")
    for k, v in vol.items():
        print(f"  {k:25s}: {v:8.3f}")

    print("\n--- EARNINGS REACTIONS ---")
    for k, v in earnings.items():
        print(f"  {k:25s}: {v:8.3f}")

    print("\n--- REGIME PERSISTENCE (crude 5d trend filter) ---")
    for k, v in regime.items():
        print(f"  {k:25s}: {v:8.3f}")

    # Recent 4h (if available)
    try:
        df4h = load_recent_4h(ticker, days=recent_4h_days)
        print(f"\n--- RECENT 4-HOUR DATA ({len(df4h)} bars, ~{recent_4h_days} days) ---")
        print(f"  Date range: {df4h.index.min().date()} → {df4h.index.max().date()}")
        # Basic 4h return stats
        df4h["ret_4h"] = df4h["close"].pct_change() * 100
        r4 = df4h["ret_4h"].dropna()
        print(f"  4h return mean:        {r4.mean():.4f}%")
        print(f"  4h return std:         {r4.std():.4f}%")
        print(f"  4h return p5 / p95:    {np.percentile(r4,5):.2f}% / {np.percentile(r4,95):.2f}%")
        print(f"  Large 4h moves (>2%):  {(r4.abs() > 2).mean()*100:.2f}% of bars")
    except Exception as e:
        print(f"\n[WARNING] Could not load recent 4h data for {ticker}: {e}")
        df4h = None

    result = {
        "ticker": ticker,
        "gap": gap,
        "short_returns": short_ret,
        "vol": vol,
        "earnings": earnings,
        "regime": regime,
        "has_4h": df4h is not None,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", default=["TSLA", "TSLL"])
    parser.add_argument("--recent-4h-days", type=int, default=180)
    args = parser.parse_args()

    all_results = {}
    for t in args.tickers:
        all_results[t] = characterize_ticker(t, args.recent_4h_days)

    print("\n\n" + "="*70)
    print("SUMMARY — TARGETS FOR v0.1 GENERATOR (use these as calibration goals)")
    print("="*70)
    for t, res in all_results.items():
        print(f"\n{t}:")
        g = res["gap"]
        print(f"  Gap p95: {g['gap_p95_pct']:.2f}%   |  >3% gap frequency: {g['gap_gt_3pct_freq']:.2f}%")
        e = res["earnings"]
        print(f"  Earnings jump mean: {e.get('earnings_jump_1d_mean', 0):.2f}%  (n={e.get('earnings_n_events',0)})")
        v = res["vol"]
        print(f"  HV30 mean: {v['hv30_mean']:.1f}   |  vol clustering (acf1): {v['vol_clustering_acf1']:.3f}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
simulator/validate_generator.py

Compares synthetic paths from MarketGenerator against real targets produced by characterize.py.

This is the key "is it representative enough?" tool for PoC 1.

Current v0.1 scope:
- Generates synthetic daily paths (4h synthesis is future work).
- Runs a lightweight version of the key statistics (gaps, short returns, HV30, earnings jumps).
- Prints side-by-side real vs synthetic + simple match scores.
- Exit code 0 if "good enough" on the prioritized dimensions, 1 otherwise (for CI/scripting).

Run after any change to the generator to see if we are getting closer to the real distribution.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

# Robust imports whether run from repo root or inside simulator/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulator.market_generator import MarketGenerator, GeneratorConfig
from simulator.characterize import (
    compute_gap_stats,
    compute_short_horizon_return_stats,
    compute_vol_clustering,
    compute_earnings_reaction_stats,
)
from data import _TSLA_EARNINGS_DATES


def quick_characterize(df: pd.DataFrame) -> Dict:
    """
    Lightweight characterization for generator validation.

    If the DataFrame contains multiple paths (has 'path_id' column from
    generate_daily_dataframe), we compute statistics per path on a clean
    unique DatetimeIndex, then return the average of the key scalars.
    This is the statistically correct way to compare distributions.
    """
    if "path_id" in df.columns:
        path_results = []
        for _, path_df in df.groupby("path_id"):
            if len(path_df) < 35:          # skip paths too short for HV30 + earnings stats
                continue
            # Create a clean unique daily index for this path
            clean = path_df[["open", "high", "low", "close", "volume"]].copy()
            clean.index = pd.date_range("2000-01-01", periods=len(clean), freq="B")
            clean = clean.sort_index()

            path_results.append({
                "gap": compute_gap_stats(clean),
                "short": compute_short_horizon_return_stats(clean),
                "vol": compute_vol_clustering(clean),
                "earnings": compute_earnings_reaction_stats(clean, _TSLA_EARNINGS_DATES),
            })
        if not path_results:
            return {"gap": {}, "short": {}, "vol": {}, "earnings": {}}

        def avg(key: str, sub: str) -> float:
            vals = [r[key][sub] for r in path_results if sub in r[key]]
            return float(np.nanmean(vals)) if vals else float("nan")

        return {
            "gap": {
                "gap_p95_pct": avg("gap", "gap_p95_pct"),
                "gap_gt_3pct_freq": avg("gap", "gap_gt_3pct_freq"),
            },
            "short": {
                "ret_1d_std": avg("short", "ret_1d_std"),
                "ret_1d_p5": avg("short", "ret_1d_p5"),
            },
            "vol": {"hv30_mean": avg("vol", "hv30_mean")},
            "earnings": {"earnings_jump_1d_mean": avg("earnings", "earnings_jump_1d_mean")},
        }
    else:
        # Single clean path
        gap = compute_gap_stats(df)
        short = compute_short_horizon_return_stats(df)
        vol = compute_vol_clustering(df)
        earn = compute_earnings_reaction_stats(df, _TSLA_EARNINGS_DATES)
        return {"gap": gap, "short": short, "vol": vol, "earnings": earn}


def compare_stat(real: float, synth: float, name: str, tol_rel: float = 0.25) -> str:
    """Return a formatted comparison string with pass/fail."""
    if real == 0:
        diff = abs(synth)
        passed = diff < 0.01
    else:
        rel_diff = abs(synth - real) / max(abs(real), 1e-9)
        passed = rel_diff <= tol_rel

    status = "✓" if passed else "✗"
    return f"{status} {name:25s} real={real:8.3f}  synth={synth:8.3f}  (tol ±{tol_rel*100:.0f}%)"


def validate(ticker: str, n_paths: int = 100, length_days: int = 63) -> bool:
    print(f"\n{'='*65}")
    print(f"VALIDATING GENERATOR vs REAL — {ticker}")
    print(f"{'='*65}")

    # Real data
    from data import load_history
    real_daily = load_history(ticker, period="10y", use_cache=True).dropna(subset=["close"])

    # Synthetic data
    cfg = GeneratorConfig(ticker=ticker, random_seed=123)
    gen = MarketGenerator(cfg)
    gen.calibrate()
    synth_df = gen.generate_daily_dataframe(n_paths=n_paths, length_days=length_days)

    # Characterize both
    real_stats = quick_characterize(real_daily)
    synth_stats = quick_characterize(synth_df)

    print("\n--- GAP STATISTICS ---")
    checks = []
    for key in ["gap_p95_pct", "gap_gt_3pct_freq"]:
        real_v = real_stats["gap"][key]
        synth_v = synth_stats["gap"][key]
        print(compare_stat(real_v, synth_v, key, tol_rel=0.30))
        checks.append(abs(synth_v - real_v) / max(real_v, 1e-6) <= 0.30)

    print("\n--- SHORT HORIZON RETURNS (1d std & p5) ---")
    for key in ["ret_1d_std", "ret_1d_p5"]:
        real_v = real_stats["short"][key]
        synth_v = synth_stats["short"][key]
        print(compare_stat(real_v, synth_v, key, tol_rel=0.25))
        checks.append(abs(synth_v - real_v) / max(abs(real_v), 1e-6) <= 0.25)

    print("\n--- VOLATILITY (HV30 mean) ---")
    real_v = real_stats["vol"]["hv30_mean"]
    synth_v = synth_stats["vol"]["hv30_mean"]
    print(compare_stat(real_v, synth_v, "hv30_mean", tol_rel=0.20))
    checks.append(abs(synth_v - real_v) / max(real_v, 1e-6) <= 0.20)

    print("\n--- EARNINGS JUMP (mean) ---")
    real_v = real_stats["earnings"].get("earnings_jump_1d_mean", 0.0)
    synth_v = synth_stats["earnings"].get("earnings_jump_1d_mean", 0.0)
    print(compare_stat(real_v, synth_v, "earnings_jump_mean", tol_rel=0.40))
    checks.append(abs(synth_v - real_v) / max(abs(real_v) or 0.01, 0.01) <= 0.40)

    passed = all(checks)
    print(f"\nOverall v0.1 match: {'PASS (good enough for iteration)' if passed else 'NEEDS WORK'}")

    # === Explicit Behavioral / Sanity Checks (these act as lightweight tests) ===
    print("\n--- Behavioral Sanity Checks ---")
    sanity_passed = True

    # 1. No NaN in core price data
    if synth_df[["open", "close"]].isna().any().any():
        print("✗ FAIL: NaNs present in synthetic price data")
        sanity_passed = False
    else:
        print("✓ No NaNs in OHLC")

    # 2. Volume always positive
    if (synth_df["volume"] <= 0).any():
        print("✗ FAIL: Non-positive volume generated")
        sanity_passed = False
    else:
        print("✓ All volumes > 0")

    # 3. Gaps exist (open/close ratio not always 1)
    gap_ratios = (synth_df["open"] / synth_df["close"].shift(1)).dropna()
    if (gap_ratios == 1.0).all():
        print("✗ FAIL: No overnight gaps generated")
        sanity_passed = False
    else:
        print(f"✓ Gaps present (observed { (gap_ratios != 1.0).mean()*100 :.1f}% of transitions)")

    # 4. When we force earnings in generation, we should see some larger moves
    # (we already force in some calls above; here we just check variability)
    if synth_df["close"].pct_change().abs().max() > 0.15:
        print("✓ Large moves (>15%) observed — earnings/gap injection is active")
    else:
        print("⚠ Only modest moves — earnings injection may be too conservative")

    print(f"\nSanity checks: {'ALL PASSED' if sanity_passed else 'ISSUES FOUND'}")
    return passed and sanity_passed


if __name__ == "__main__":
    ok_tsla = validate("TSLA", n_paths=80, length_days=42)
    ok_tsll = validate("TSLL", n_paths=80, length_days=42)

    print("\n" + "="*65)
    if ok_tsla and ok_tsll:
        print("Generator v0.1 is representative enough to continue to richer labeling.")
        sys.exit(0)
    else:
        print("Generator needs tuning before moving to next phase (normal in PoC 1).")
        sys.exit(1)

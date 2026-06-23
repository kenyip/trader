#!/usr/bin/env python3
"""
simulator/market_generator.py

v0.1 skeleton of the Market + Trade Simulator Engine.

Design goals for this phase:
- Produce representative (not perfect) 4h or daily paths.
- Prioritize matching the most important statistics from characterize.py:
    1. Overnight gap distribution (size + frequency, especially fat tails on TSLL)
    2. Short-horizon return distributions (1d–7d)
    3. Volatility level (HV30) and basic clustering
    4. Earnings reaction shapes (jump + post-event drift)
- Algorithmic / parametric approach derived from historical data.
- Easy to validate with validate_generator.py against real targets.
- Starts simple, will be iteratively improved.

Current implementation (v0.1 early):
- Regime-aware block bootstrap of real historical segments (safest way to stay representative).
- Simple earnings jump injector using distributions learned from characterize.py.
- Gap perturbation module.
- Can output daily bars (compatible with existing data pipeline) and can later synthesize plausible 4h structure.

This is deliberately minimal so we can get a working validate loop quickly.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal, Dict
import numpy as np
import pandas as pd

# Project imports (robust whether run from root or inside simulator/)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data import load_history, _TSLA_EARNINGS_DATES


Regime = Literal["huge_down", "normal_down", "flat", "normal_up", "huge_up", "chop", "earnings_window"]


@dataclass
class GeneratorConfig:
    """Configuration for the market generator (v0.1)."""
    ticker: str = "TSLA"
    resolution: str = "daily"          # "daily" or "4h" (4h synthesis is future work)
    random_seed: Optional[int] = None

    # How much to perturb gaps and earnings jumps (0.0 = use historical exactly)
    gap_perturbation_sigma: float = 0.3   # relative std on gap size
    earnings_jump_scale: float = 1.0      # multiplier on historical jump distribution

    # Minimum length of blocks we sample (in trading days)
    min_block_days: int = 5
    max_block_days: int = 25


class MarketGenerator:
    """
    Generates representative market paths for training / stress testing.

    v0.1 approach: regime-aware block bootstrap + calibrated event injection.
    This is "representative by construction" on many dimensions while still
    allowing us to create novel combinations and more samples than history.
    """

    def __init__(self, cfg: GeneratorConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.random_seed)

        # Load full daily history (cached)
        self.daily = load_history(cfg.ticker, period="10y", use_cache=True).copy()
        self.daily = self.daily.dropna(subset=["close", "open", "high", "low", "volume"])

        # Pre-compute simple regime labels on the real data (crude but sufficient for v0.1)
        self.daily["regime"] = self._compute_simple_regime(self.daily)

        # Earnings dates (shared)
        self.earnings_dates = pd.to_datetime(_TSLA_EARNINGS_DATES)

        # Placeholder for learned jump distributions (will be populated from real data or characterize output)
        self._earnings_jump_dist = None  # to be filled in calibrate()

    def _compute_simple_regime(self, df: pd.DataFrame) -> pd.Series:
        """Very crude regime tagger for block sampling. Good enough for v0.1."""
        ret_5d = df["close"].pct_change(5)
        regime = pd.Series("flat", index=df.index)
        regime[ret_5d > 0.04] = "normal_up"
        regime[ret_5d > 0.10] = "huge_up"
        regime[ret_5d < -0.04] = "normal_down"
        regime[ret_5d < -0.10] = "huge_down"
        return regime

    def calibrate(self, real_stats: Optional[Dict] = None):
        """
        Learn jump + post-event drift distributions from real history.
        This makes the generated earnings events much more realistic.
        """
        jumps = []
        post_5d_drifts = []

        for ed in self.earnings_dates:
            if ed in self.daily.index:
                loc = self.daily.index.get_indexer([ed], method="nearest")[0]
                if loc + 6 < len(self.daily):
                    jump = (self.daily["close"].iloc[loc + 1] / self.daily["close"].iloc[loc]) - 1
                    post = (self.daily["close"].iloc[loc + 6] / self.daily["close"].iloc[loc + 1]) - 1
                    jumps.append(jump)
                    post_5d_drifts.append(post)

        if jumps:
            self._earnings_jump_dist = {
                "mean": float(np.mean(jumps)),
                "std": float(np.std(jumps)),
                "p10": float(np.percentile(jumps, 10)),
                "p90": float(np.percentile(jumps, 90)),
            }
            self._earnings_post_drift_dist = {
                "mean": float(np.mean(post_5d_drifts)),
                "std": float(np.std(post_5d_drifts)),
            }
        else:
            self._earnings_jump_dist = {"mean": 0.0, "std": 0.04, "p10": -0.05, "p90": 0.05}
            self._earnings_post_drift_dist = {"mean": 0.0, "std": 0.03}

    def _sample_block(self, regime: Optional[str] = None, length_days: Optional[int] = None) -> pd.DataFrame:
        """Sample a contiguous historical block, optionally conditioned on regime."""
        df = self.daily
        if regime is not None:
            candidates = df[df["regime"] == regime]
            if len(candidates) < self.cfg.min_block_days:
                candidates = df  # fallback
        else:
            candidates = df

        if length_days is None:
            length_days = self.rng.integers(self.cfg.min_block_days, self.cfg.max_block_days + 1)

        max_start = len(candidates) - length_days
        if max_start <= 0:
            return candidates.copy()

        start_idx = self.rng.integers(0, max_start)
        block = candidates.iloc[start_idx : start_idx + length_days].copy()
        return block

    def generate_paths(
        self,
        n_paths: int = 50,
        length_days: int = 21,
        regime: Optional[str] = None,
        force_earnings: bool = False,
    ) -> list[pd.DataFrame]:
        """
        Generate n_paths of synthetic market data.

        Current v0.1 behavior:
        - Sample real historical blocks (regime-aware when possible).
        - Occasionally inject a calibrated earnings-style jump.
        - Apply light gap perturbation.
        - Return list of DataFrames (one per path) with OHLCV columns.

        This is deliberately simple so we can validate quickly.
        """
        paths = []
        for _ in range(n_paths):
            block = self._sample_block(regime=regime, length_days=length_days).copy()

            # Light gap perturbation (affects open of day 2+)
            if len(block) > 1 and self.cfg.gap_perturbation_sigma > 0:
                gaps = (block["open"].iloc[1:] / block["close"].iloc[:-1].values) - 1
                noise = self.rng.normal(0, self.cfg.gap_perturbation_sigma, size=len(gaps))
                new_gaps = gaps * (1 + noise)
                block.loc[block.index[1:], "open"] = block["close"].iloc[:-1].values * (1 + new_gaps)

            # Improved earnings-style event injection (v0.2)
            # Creates a realistic pattern: one-day jump + several days of post-event drift
            if force_earnings or (self.rng.random() < 0.18 and self._earnings_jump_dist is not None):
                jump_day = self.rng.integers(4, max(5, len(block) - 7))
                jump = self.rng.normal(
                    self._earnings_jump_dist["mean"],
                    self._earnings_jump_dist["std"],
                )
                # Apply the jump
                block.loc[block.index[jump_day:], "close"] *= (1 + jump)

                # Post-event drift (more realistic than pure noise)
                if self._earnings_post_drift_dist and jump_day + 5 < len(block):
                    drift = self.rng.normal(
                        self._earnings_post_drift_dist["mean"],
                        self._earnings_post_drift_dist["std"],
                    )
                    # Spread the drift over the next 4-5 days
                    for d in range(1, 6):
                        if jump_day + d < len(block):
                            factor = 1 + (drift * (d / 5.0) * 0.6)   # gradual realization
                            block.loc[block.index[jump_day + d], "close"] *= factor

                # Rebuild opens after the event for consistency
                for i in range(jump_day, len(block) - 1):
                    gap = self.rng.normal(0, 0.008)
                    block.loc[block.index[i + 1], "open"] = block["close"].iloc[i] * (1 + gap)

            # Basic volume noise (keep it positive)
            if "volume" in block.columns:
                vol_noise = self.rng.normal(1.0, 0.2, size=len(block))
                block["volume"] = (block["volume"] * np.clip(vol_noise, 0.3, 2.5)).astype(int)

            paths.append(block)

        return paths

    def generate_daily_dataframe(self, n_paths: int = 20, length_days: int = 21, **kwargs) -> pd.DataFrame:
        """
        Convenience: generate paths and concatenate into one long DataFrame
        with a 'path_id' column. Easy to feed into existing feature pipeline.
        """
        paths = self.generate_paths(n_paths=n_paths, length_days=length_days, **kwargs)
        dfs = []
        for i, p in enumerate(paths):
            p = p.copy()
            p["path_id"] = i
            dfs.append(p)
        return pd.concat(dfs)

    def generate_regime_batch(self, regime: str, n_paths: int = 50, length_days: int = 21) -> pd.DataFrame:
        """Generate many paths all from the same regime. Very useful for targeted scenario work."""
        return self.generate_daily_dataframe(n_paths=n_paths, length_days=length_days, regime=regime)

    def generate_earnings_scenarios(self, n_paths: int = 40, length_days: int = 25) -> pd.DataFrame:
        """Generate paths that deliberately contain an earnings-style event."""
        return self.generate_daily_dataframe(n_paths=n_paths, length_days=length_days, force_earnings=True)


# Quick smoke test when run directly
if __name__ == "__main__":
    print("MarketGenerator v0.1 smoke test")
    for ticker in ["TSLA", "TSLL"]:
        cfg = GeneratorConfig(ticker=ticker, random_seed=42)
        gen = MarketGenerator(cfg)
        gen.calibrate()
        paths = gen.generate_paths(n_paths=5, length_days=21, force_earnings=True)
        print(f"{ticker}: generated {len(paths)} paths, first path length = {len(paths[0])} days")
        print(paths[0][["open", "close", "volume"]].head(3))
        print()

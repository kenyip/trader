from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


WIDE_LEAPS_DTE_GRID = (270, 365, 450, 540, 630, 730, 900)
WIDE_SHORT_DTE_GRID = (7, 14, 21, 30, 45, 60, 75, 90, 120, 150, 180)

# Chain-aligned LEAPS / short tenors (refreshed from live expiries; override per preset).
CHAIN_LEAPS_DTE_GRID = (360, 452, 543, 578, 725, 907)
CHAIN_SHORT_DTE_GRID = (39, 60, 88, 116)


def strike_ladder(
    spot: float,
    lo_pct: float,
    hi_pct: float,
    *,
    step: int = 10,
) -> tuple[float, ...]:
    """$step-spaced strikes between spot×lo_pct and spot×hi_pct (inclusive)."""
    lo = int(round(spot * lo_pct / step) * step)
    hi = int(round(spot * hi_pct / step) * step)
    if lo > hi:
        return ()
    return tuple(float(x) for x in range(lo, hi + 1, step))


def default_strike_grids(
    spot: float,
    *,
    step: int = 10,
    leaps_lo_pct: float = 0.92,
    leaps_hi_pct: float = 1.05,
    short_lo_pct: float = 1.05,
    short_hi_pct: float = 1.38,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """LEAPS slightly ITM → ATM; shorts modest OTM → wide cap."""
    return (
        strike_ladder(spot, leaps_lo_pct, leaps_hi_pct, step=step),
        strike_ladder(spot, short_lo_pct, hi_pct=short_hi_pct, step=step),
    )


def resolve_strike_grids(cfg: "PmccConfig", spot: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if cfg.leaps_strike_grid is not None and cfg.short_strike_grid is not None:
        return cfg.leaps_strike_grid, cfg.short_strike_grid
    return default_strike_grids(
        spot,
        step=cfg.strike_step,
        leaps_lo_pct=cfg.leaps_strike_lo_pct,
        leaps_hi_pct=cfg.leaps_strike_hi_pct,
        short_lo_pct=cfg.short_strike_lo_pct,
        short_hi_pct=cfg.short_strike_hi_pct,
    )


@dataclass
class PmccConfig:
    ticker: str = "TSLA"

    grid_mode: str = "delta"  # "delta" (Δ targets) | "strike" ($10 strike ladder)

    leaps_dte_min: int = 270
    leaps_dte_max: int = 950
    leaps_dte_grid: tuple[int, ...] = (365, 450, 540, 630, 730)
    short_dte_grid: tuple[int, ...] = (14, 21, 30, 45, 60, 75, 90, 120)
    short_dte_max: int = 200

    leaps_delta_grid: tuple[float, ...] = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85)
    short_delta_grid: tuple[float, ...] = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)

    strike_step: int = 10
    leaps_strike_grid: tuple[float, ...] | None = None
    short_strike_grid: tuple[float, ...] | None = None
    leaps_strike_lo_pct: float = 0.92
    leaps_strike_hi_pct: float = 1.05
    leaps_delta_min: float | None = None
    leaps_delta_max: float | None = None
    short_strike_lo_pct: float = 1.05
    short_strike_hi_pct: float = 1.38

    min_short_strike_offset: float = 0.0
    max_bid_ask_spread_pct: float = 0.25
    min_short_bid: float = 0.10

    score_profile: str = "balanced"
    target_spot: float | None = None

    risk_free_rate: float = 0.04
    challenge_day_frac: float = 0.5
    roll_dte: int = 75

    chain_use_cache: bool = True
    chain_refresh: bool = False
    chain_max_age_minutes: int = 30

    path_sim_top_n: int = 0
    path_sim_blend: float = 0.0
    short_upside_min_pct: float | None = None
    short_upside_max_pct: float | None = None
    min_short_dte: int | None = None


SCORE_PROFILES: dict[str, dict[str, float]] = {
    "premium": {
        "coverage": 0.40,
        "breakeven": 0.35,
        "upside": 0.25,
    },
    "balanced": {
        "coverage": 0.22,
        "breakeven": 0.12,
        "upside": 0.12,
        "challenge": 0.12,
        "roll_eff": 0.18,
        "first_cycle": 0.08,
        "drop": 0.13,
        "path_net": 0.08,
        "rolls": 0.05,
    },
    "bullish": {
        "upside": 0.20,
        "challenge": 0.20,
        "roll_eff": 0.20,
        "first_cycle": 0.12,
        "coverage": 0.08,
        "drop": 0.05,
        "path_net": 0.10,
        "rolls": 0.05,
    },
    "managed": {},
}


MANAGEMENT_RULES: dict[str, list[str]] = {
    "income": [
        "Sell short 0.30–0.40Δ, 90–120 DTE — maximize coverage per cycle.",
        "On −10% drop mid-cycle: buy back short at 50%+ profit; hold LEAPS; re-sell when IV stable.",
        "On rip to short strike: roll up ~8% above challenge; accept roll tax if first_cycle_net stays positive.",
        "Take LEAPS profit only if short cycles have recovered ≥50% of net debit.",
    ],
    "balanced": [
        "LEAPS ~0.60–0.70Δ (~1yr); short 0.25–0.35Δ, 90–120 DTE — balance credit vs roll tax.",
        "Reject pairs with roll_tax_ratio > 0.8 unless first_cycle_net_after_roll > +$500.",
        "On drop: harvest short leg; keep LEAPS. On rip: roll to reopen ~8% above spot, not token strikes.",
        "Use --target-spot to sanity-check path; prefer ≤2 rolls before target.",
    ],
    "managed": [
        "Sim every LEAPS/short DTE cell on chain; rank the sim-best per strike pair.",
        "LEAPS max DTE (727-908d), 0.65-0.75Δ; short 60d 0.30Δ (~12-25% OTM).",
        "Conditional LEAPS roll at 365d remaining: roll unless deep ITM (>1.25x hold, >1.35x close short naked).",
        "Force close ITM short at 14 DTE — never let expire ITM (assignment forfeits LEAPS time value).",
        "Harvest short at 50%+ profit; roll up 10% when challenged at short strike.",
        "Never reset LEAPS to higher strike — original strike is anchor for premium selling.",
    ],
    "bullish": [
        "LEAPS ~0.65–0.75Δ; short 0.15–0.25Δ, 90–120 DTE — wide cap toward price target.",
        "Accept lower coverage; avoid shorts challenged before your target (use --target-spot 550).",
        "On rip: roll up aggressively (spot×1.08+); never let assignment exercise LEAPS.",
        "If path needs 3+ rolls before target, widen initial short strike.",
    ],
}


PRESETS: dict[str, dict[str, Any]] = {
    "income": {
        "score_profile": "premium",
        "leaps_dte_grid": (365, 450, 540),
        "short_dte_grid": (75, 90, 120),
        "leaps_delta_grid": (0.60, 0.65, 0.70),
        "short_delta_grid": (0.30, 0.35, 0.40),
        "target_spot": None,
    },
    "balanced": {
        "score_profile": "balanced",
        "grid_mode": "strike",
        "leaps_dte_grid": CHAIN_LEAPS_DTE_GRID,
        "short_dte_grid": CHAIN_SHORT_DTE_GRID,
        "leaps_delta_grid": (0.60, 0.65, 0.70, 0.75),
        "short_delta_grid": (0.25, 0.30, 0.35, 0.40),
        "target_spot": None,
    },
    "bullish": {
        "score_profile": "bullish",
        "leaps_dte_grid": (365, 450, 540, 630),
        "short_dte_grid": (75, 90, 120),
        "leaps_delta_grid": (0.65, 0.70, 0.75),
        "short_delta_grid": (0.15, 0.20, 0.25, 0.30),
        "target_spot": 550.0,
    },
    "managed": {
        "score_profile": "managed",
        "grid_mode": "strike",
        "leaps_dte_grid": CHAIN_LEAPS_DTE_GRID,
        "short_dte_grid": CHAIN_SHORT_DTE_GRID,
        "leaps_delta_grid": (0.60, 0.65, 0.70, 0.75),
        "short_delta_grid": (0.20, 0.25, 0.30, 0.35, 0.40),
        "leaps_delta_max": 0.76,
        "short_strike_lo_pct": 1.12,
        "short_upside_min_pct": 0.12,
        "min_short_dte": 39,
        "target_spot": None,
        "short_upside_max_pct": 0.30,
    },
}


def apply_preset(cfg: PmccConfig, preset: str) -> PmccConfig:
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose {list(PRESETS)}")
    return replace(cfg, **PRESETS[preset])
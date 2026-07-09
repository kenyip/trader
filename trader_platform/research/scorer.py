"""Per-symbol opportunity scores: vol / premium / alpha proxies (offline features).

Uses data.build (yfinance + feature pipeline). Scores are *proxies*, not guaranteed alpha.
Labels in SymbolScore make that explicit for downstream consumers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

# Features from data.py (repo root). Imported lazily inside score_symbol when needed.


@dataclass
class SymbolScore:
    symbol: str
    asof: str
    spot: float
    regime: str
    # Component scores in [0, 100] (higher = more interesting for short-premium / research)
    vol_score: float
    premium_score: float
    alpha_score: float
    composite: float
    # Raw feature snapshot (honest proxies)
    hv_20: float
    hv_60: float
    iv_rank: float
    ret_5d: float
    ret_14d: float
    ema_stack: float
    rsi_14: float
    atr_14: float
    high_iv: bool
    # Optional strategy family hint from regime (not a trade)
    strategy_family: str = "unknown"
    notes: list[str] = field(default_factory=list)
    error: Optional[str] = None
    # Capital-by-price sizing (filled by capital.attach_capital_to_score)
    share_lot_usd: float = 0.0  # 100 * spot
    short_premium_bp_proxy: float = 0.0  # CSP / covered rough BP
    long_debit_proxy: float = 0.0
    contracts_at_3k_short: int = 0
    contracts_at_5k_short: int = 0
    contracts_at_15k_short: int = 0
    contracts_at_3k_long: int = 0
    contracts_at_5k_long: int = 0
    contracts_at_15k_long: int = 0
    capital_fit: str = "unknown"  # fit_3k | fit_5k | fit_15k | oversized
    capital_fit_long: str = "unknown"
    # Honesty labels
    labels: dict[str, str] = field(
        default_factory=lambda: {
            "vol": "proxy: realized-vol regime (hv_20 vs hv_60 + level)",
            "premium": "proxy: iv_rank (hv-based) + move-vs-vol residual — not live chain IV",
            "alpha": "proxy: trend strength | mean-reversion residual — not guaranteed edge",
            "composite": "0.35*vol + 0.40*premium + 0.25*alpha (configurable weights)",
            "capital": "proxy: 100*spot CSP BP + ~2% spot long debit — not broker margin",
        }
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # nested capital object is optional runtime attr — drop if present via extra
        d.pop("capital", None)
        return d


# Weights: premium slightly preferred for options research desk
DEFAULT_WEIGHTS = {"vol": 0.35, "premium": 0.40, "alpha": 0.25}


def strategy_family_for_regime(regime: str, *, high_iv: bool, iv_rank: float) -> str:
    """Map regime → research strategy family (hint only; not live routing)."""
    r = (regime or "unknown").lower()
    if high_iv or iv_rank >= 60:
        if r == "bearish":
            return "short_put_cautious"  # elevated premium but trend against
        if r == "bullish":
            return "short_premium_rich"
        return "short_strangle_candidate"
    if r == "bullish":
        return "short_put_trend"
    if r == "bearish":
        return "short_call_or_stand_aside"
    if r == "neutral":
        return "iron_condor_or_strangle_research"
    return "stand_aside_research"


def _clip01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return float(max(0.0, min(100.0, x)))


def score_from_row(
    symbol: str,
    row: pd.Series,
    *,
    weights: Optional[dict[str, float]] = None,
) -> SymbolScore:
    """Score a single latest feature row (already built by data.add_features)."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    wsum = w["vol"] + w["premium"] + w["alpha"]
    if wsum <= 0:
        raise ValueError("weights must sum > 0")

    hv20 = float(row.get("hv_20") or 0.0)
    hv60 = float(row.get("hv_60") or hv20 or 1e-9)
    iv_rank = float(row.get("iv_rank") or 0.0)
    ret_5d = float(row.get("ret_5d") or 0.0)
    ret_14d = float(row.get("ret_14d") or 0.0)
    ema_stack = float(row.get("ema_stack") or 0.0)
    rsi = float(row.get("rsi_14") or 50.0)
    atr = float(row.get("atr_14") or 0.0)
    close = float(row.get("close") or 0.0)
    regime = str(row.get("regime") or "unknown")
    high_iv = bool(row.get("high_iv")) if "high_iv" in row.index else iv_rank > 50

    # --- vol opportunity: elevated short-term vol + expansion vs longer window ---
    # Level: map hv_20 (annualised) into 0..100; 15%→low, 80%+→high for single names
    vol_level = _clip01((hv20 - 0.10) / 0.70 * 100.0)
    expansion = hv20 / max(hv60, 1e-9)
    # expansion 0.7..1.5 → score
    vol_exp = _clip01((expansion - 0.7) / 0.8 * 100.0)
    vol_score = _clip01(0.55 * vol_level + 0.45 * vol_exp)

    # --- premium richness proxy ---
    # iv_rank already 0..100 percentile of hv_30. Plus "rich vs recent move":
    # if |ret_5d| is small relative to daily vol, options may be rich vs realized path.
    daily_vol = max(hv20 / np.sqrt(252.0), 1e-6)
    expected_5d = daily_vol * np.sqrt(5.0)
    move_ratio = abs(ret_5d) / expected_5d  # <1 quiet path vs vol; >1 already moved
    # Quiet path + high iv_rank = premium opportunity for sellers
    quiet_bonus = _clip01((1.2 - move_ratio) / 1.2 * 100.0)
    premium_score = _clip01(0.65 * iv_rank + 0.35 * quiet_bonus)

    # --- alpha / opportunity proxy (honest: not guaranteed edge) ---
    # Trend strength: |ema_stack| * 100
    trend = _clip01(abs(ema_stack) * 100.0)
    # Mean-reversion residual: distance from mid RSI / extreme
    # Prefer mild extremes (not 50, not fully stretched crash) for premium setups
    rsi_edge = abs(rsi - 50.0)  # 0..50
    mr = _clip01(rsi_edge / 50.0 * 100.0)
    # Momentum coherence: ret_14d sign aligns with ema_stack
    align = 1.0 if (ret_14d * ema_stack) > 0 else 0.35
    alpha_score = _clip01((0.50 * trend + 0.30 * mr) * align + 0.20 * min(100.0, abs(ret_14d) * 500.0))

    raw = w["vol"] * vol_score + w["premium"] * premium_score + w["alpha"] * alpha_score
    composite = _clip01(raw if abs(wsum - 1.0) < 1e-9 else raw / wsum)

    notes: list[str] = []
    if high_iv:
        notes.append("high_iv")
    if expansion >= 1.15:
        notes.append("vol_expansion")
    if move_ratio < 0.6 and iv_rank >= 50:
        notes.append("rich_vs_recent_move")
    if abs(ema_stack) >= 0.66:
        notes.append("strong_trend")

    asof = ""
    if hasattr(row, "name") and row.name is not None:
        asof = str(pd.Timestamp(row.name).date())

    fam = strategy_family_for_regime(regime, high_iv=high_iv, iv_rank=iv_rank)

    sc = SymbolScore(
        symbol=symbol.upper(),
        asof=asof,
        spot=close,
        regime=regime,
        vol_score=round(vol_score, 2),
        premium_score=round(premium_score, 2),
        alpha_score=round(alpha_score, 2),
        composite=round(composite, 2),
        hv_20=round(hv20, 4),
        hv_60=round(hv60, 4),
        iv_rank=round(iv_rank, 2),
        ret_5d=round(ret_5d, 4),
        ret_14d=round(ret_14d, 4),
        ema_stack=round(ema_stack, 4),
        rsi_14=round(rsi, 2),
        atr_14=round(atr, 4),
        high_iv=high_iv,
        strategy_family=fam,
        notes=notes,
    )
    from trader_platform.research.capital import attach_capital_to_score

    return attach_capital_to_score(sc)


def score_symbol(
    symbol: str,
    *,
    period: str = "2y",
    use_cache: bool = True,
    weights: Optional[dict[str, float]] = None,
    build_fn: Optional[Callable[..., pd.DataFrame]] = None,
) -> SymbolScore:
    """Load features for symbol and score latest bar."""
    try:
        if build_fn is None:
            from data import build as _build

            build_fn = _build
        df = build_fn(symbol.upper(), period=period, use_cache=use_cache)
        if df is None or len(df) == 0:
            return _error_score(symbol, "empty feature frame")
        return score_from_row(symbol, df.iloc[-1], weights=weights)
    except Exception as exc:  # noqa: BLE001 — research tick must continue
        return _error_score(symbol, str(exc))


def _error_score(symbol: str, err: str) -> SymbolScore:
    return SymbolScore(
        symbol=symbol.upper(),
        asof="",
        spot=0.0,
        regime="error",
        vol_score=0.0,
        premium_score=0.0,
        alpha_score=0.0,
        composite=0.0,
        hv_20=0.0,
        hv_60=0.0,
        iv_rank=0.0,
        ret_5d=0.0,
        ret_14d=0.0,
        ema_stack=0.0,
        rsi_14=0.0,
        atr_14=0.0,
        high_iv=False,
        strategy_family="error",
        notes=[],
        error=err,
    )

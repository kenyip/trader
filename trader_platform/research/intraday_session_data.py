"""No-lookahead 30-minute underlying bars for session-time proxy research.

This module supplies underlying-only yfinance data. Option marks remain synthetic
Black-Scholes proxies in downstream simulators; this data cannot establish L1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

NEW_YORK = "America/New_York"
OHLCV = ("open", "high", "low", "close", "volume")


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(column).strip().lower().replace(" ", "_") for column in out.columns]
    missing = [column for column in OHLCV if column not in out.columns]
    if missing:
        raise ValueError(f"intraday frame missing OHLCV columns: {missing}")
    return out.loc[:, list(OHLCV)].copy()


def _new_york_index(index: pd.Index) -> pd.DatetimeIndex:
    parsed = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce"))
    if parsed.isna().any():
        raise ValueError("intraday frame index contains invalid timestamps")
    if parsed.tz is None:
        return parsed.tz_localize(NEW_YORK)
    return parsed.tz_convert(NEW_YORK)


def _session_bucket(timestamp: pd.Timestamp) -> str:
    minute = timestamp.hour * 60 + timestamp.minute
    if minute < 11 * 60:
        return "open"
    if minute < 14 * 60:
        return "midday"
    return "late"


def _last_rank(values: np.ndarray) -> float:
    series = pd.Series(values, dtype=float)
    return float(series.rank(method="average", pct=True).iloc[-1] * 100.0)


def build_session_frame(raw: pd.DataFrame, *, min_daily_history: int = 20) -> pd.DataFrame:
    """Return RTH bars with entry features from the prior completed market date.

    Current-bar ``close`` remains available as the simulated entry/mark spot. All
    option-entry regime, IV proxy, and IV-rank fields are joined from the previous
    completed RTH session. Downstream should still use ``entry_signal_lag_bars=1``
    for any 30-minute signal columns such as ``intraday_return``.
    """
    if int(min_daily_history) < 1:
        raise ValueError("min_daily_history must be >= 1")
    frame = _normalize_columns(raw)
    frame.index = _new_york_index(frame.index)
    frame = frame.sort_index()
    for column in OHLCV:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    finite = np.isfinite(frame.loc[:, list(OHLCV)].to_numpy(dtype=float)).all(axis=1)
    frame = frame.loc[finite]
    minute = frame.index.hour * 60 + frame.index.minute
    rth = (minute >= 9 * 60 + 30) & (minute < 16 * 60) & (frame.index.dayofweek < 5)
    frame = frame.loc[rth].copy()
    if frame.empty:
        return frame.assign(
            market_date=pd.Series(dtype=object),
            session_bucket=pd.Series(dtype=str),
            feature_market_date=pd.Series(dtype=object),
            iv_proxy=pd.Series(dtype=float),
            iv_rank=pd.Series(dtype=float),
            regime=pd.Series(dtype=str),
        )

    frame["market_date"] = frame.index.date
    frame["session_bucket"] = [_session_bucket(timestamp) for timestamp in frame.index]
    frame["intraday_return"] = (
        frame.groupby("market_date", sort=False)["close"].pct_change().fillna(0.0) * 100.0
    )
    rolling_volume = frame["volume"].rolling(20, min_periods=1).mean().shift(1)
    frame["volume_surge"] = frame["volume"] / rolling_volume.replace(0.0, np.nan)

    daily = frame.groupby("market_date", sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    daily_return = daily["close"].pct_change().fillna(0.0)
    window = max(2, int(min_daily_history))
    min_periods = max(1, min(int(min_daily_history), window))
    daily["iv_proxy"] = (
        daily_return.rolling(window, min_periods=min_periods).std(ddof=0) * np.sqrt(252.0)
    ).clip(lower=0.05)
    daily["iv_rank"] = daily["iv_proxy"].rolling(
        20, min_periods=min(int(min_daily_history), 20)
    ).apply(_last_rank, raw=True)
    ema_fast = daily["close"].ewm(span=5, adjust=False).mean()
    ema_slow = daily["close"].ewm(span=20, adjust=False).mean()
    daily["regime"] = np.where(
        (daily["close"] > ema_slow) & (ema_fast > ema_slow),
        "bullish",
        np.where(
            (daily["close"] < ema_slow) & (ema_fast < ema_slow),
            "bearish",
            "neutral",
        ),
    )
    daily["feature_market_date"] = daily.index
    prior = daily.loc[:, ["feature_market_date", "iv_proxy", "iv_rank", "regime"]].shift(1)
    prior.index.name = "market_date"

    frame = frame.join(prior, on="market_date")
    frame = frame.dropna(subset=["feature_market_date", "iv_proxy", "iv_rank", "regime"])
    frame["data_provenance"] = "yfinance_30m_underlying_prior_session_features"
    return frame.sort_index()


def download_session_frame(
    symbol: str,
    *,
    period: str = "60d",
    interval: str = "30m",
    raw_out: Optional[Path | str] = None,
) -> pd.DataFrame:
    """Download current yfinance intraday history and build the L0 session frame."""
    raw = yf.download(
        symbol.upper(),
        period=period,
        interval=interval,
        auto_adjust=False,
        prepost=False,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise ValueError(f"no intraday history returned for {symbol.upper()}")
    normalized = _normalize_columns(raw)
    normalized.index = _new_york_index(normalized.index)
    if raw_out is not None:
        output = Path(raw_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(output)
    return build_session_frame(normalized)

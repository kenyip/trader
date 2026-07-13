"""No-lookahead 30-minute underlying bars for session-time proxy research.

This module supplies underlying-only yfinance data. Option marks remain synthetic
Black-Scholes proxies in downstream simulators; this data cannot establish L1.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

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


def _validated_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    out = _normalize_columns(frame)
    out.index = _new_york_index(out.index)
    out = out.sort_index()
    for column in OHLCV:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    finite = np.isfinite(out.loc[:, list(OHLCV)].to_numpy(dtype=float)).all(axis=1)
    if not bool(finite.all()):
        raise ValueError("OHLCV capture contains nonnumeric or nonfinite rows")
    out = out[~out.index.duplicated(keep="last")]
    if out.empty:
        raise ValueError("OHLCV capture has no finite rows")
    out.index.name = "timestamp"
    return out


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def append_ohlcv_archive(
    frame: pd.DataFrame,
    *,
    archive_path: Path | str,
    metadata_path: Path | str,
    symbol: str,
    interval: str,
    requested_period: str,
    captured_at: str,
    source: str = "yfinance",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Append one validated OHLCV capture and retain a provenance journal."""
    incoming = _validated_ohlcv(frame)
    archive = Path(archive_path)
    metadata_file = Path(metadata_path)
    sym = str(symbol).strip().upper()
    if not sym:
        raise ValueError("symbol is required")

    if archive.exists():
        existing = pd.read_csv(archive, index_col=0)
        existing = _validated_ohlcv(existing)
    else:
        existing = incoming.iloc[0:0].copy()

    if metadata_file.exists():
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if metadata.get("symbol") != sym or metadata.get("interval") != interval:
            raise ValueError("archive metadata symbol/interval mismatch")
        if metadata.get("source") != source:
            raise ValueError("archive metadata source mismatch")
    else:
        metadata = {
            "schema_version": 1,
            "symbol": sym,
            "interval": interval,
            "source": source,
            "captures": [],
        }

    overlap = existing.index.intersection(incoming.index)
    combined = pd.concat([existing, incoming]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    summary = {
        "captured_at": captured_at,
        "requested_period": requested_period,
        "downloaded_rows": int(len(incoming)),
        "new_rows": int(len(incoming.index.difference(existing.index))),
        "replaced_rows": int(len(overlap)),
        "archive_rows": int(len(combined)),
        "archive_market_dates": int(pd.Index(combined.index.date).nunique()),
        "archive_start": str(combined.index.min()),
        "archive_end": str(combined.index.max()),
    }
    metadata["captures"].append(summary)

    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = archive.with_name(f".{archive.name}.tmp")
    combined.to_csv(temporary_archive)
    temporary_archive.replace(archive)
    _atomic_write_text(metadata_file, json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return combined, summary


def _new_york_index(index: pd.Index) -> pd.DatetimeIndex:
    try:
        parsed = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce"))
    except ValueError:
        parsed = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce", utc=True))
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


def build_session_frame(
    raw: pd.DataFrame,
    *,
    min_daily_history: int = 20,
    prior_daily: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
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

    intraday_daily = frame.groupby("market_date", sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    daily = intraday_daily
    if prior_daily is not None:
        warmup = _validated_ohlcv(prior_daily)
        warmup["market_date"] = warmup.index.date
        warmup_daily = warmup.groupby("market_date", sort=True).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        daily = pd.concat([warmup_daily, intraday_daily]).sort_index()
        daily = daily[~daily.index.duplicated(keep="last")]
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
    frame["data_provenance"] = (
        "archived_30m_underlying_with_prior_daily_features"
        if prior_daily is not None
        else "yfinance_30m_underlying_prior_session_features"
    )
    return frame.sort_index()


def download_session_frame(
    symbol: str,
    *,
    period: str = "60d",
    interval: str = "30m",
    daily_period: str = "1y",
    raw_out: Optional[Path | str] = None,
    archive_dir: Optional[Path | str] = None,
    captured_at: Optional[str] = None,
    downloader: Optional[Callable[..., pd.DataFrame]] = None,
) -> pd.DataFrame:
    """Download and optionally append intraday/daily archives for the L0 session frame."""
    sym = symbol.upper()
    fetch = downloader or yf.download
    capture_time = captured_at or datetime.now(timezone.utc).isoformat()
    raw = fetch(
        sym,
        period=period,
        interval=interval,
        auto_adjust=False,
        prepost=False,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise ValueError(f"no intraday history returned for {sym}")
    daily_raw = fetch(
        sym,
        period=daily_period,
        interval="1d",
        auto_adjust=False,
        prepost=False,
        progress=False,
        threads=False,
    )
    if daily_raw is None or daily_raw.empty:
        raise ValueError(f"no daily warmup history returned for {sym}")
    normalized = _normalize_columns(raw)
    normalized.index = _new_york_index(normalized.index)
    daily_normalized = _normalize_columns(daily_raw)
    daily_normalized.index = _new_york_index(daily_normalized.index)
    provenance: dict[str, Any] = {
        "source": "yfinance",
        "captured_at": capture_time,
        "intraday": {
            "downloaded_rows": int(len(normalized)),
            "archive_rows": int(len(normalized)),
            "archive_market_dates": int(pd.Index(normalized.index.date).nunique()),
        },
        "daily": {
            "downloaded_rows": int(len(daily_normalized)),
            "archive_rows": int(len(daily_normalized)),
            "archive_market_dates": int(pd.Index(daily_normalized.index.date).nunique()),
        },
    }
    if archive_dir is not None:
        directory = Path(archive_dir)
        normalized, intraday_summary = append_ohlcv_archive(
            normalized,
            archive_path=directory / f"{sym}_{interval}.csv",
            metadata_path=directory / f"{sym}_{interval}.metadata.json",
            symbol=sym,
            interval=interval,
            requested_period=period,
            captured_at=capture_time,
        )
        daily_normalized, daily_summary = append_ohlcv_archive(
            daily_normalized,
            archive_path=directory / f"{sym}_1d.csv",
            metadata_path=directory / f"{sym}_1d.metadata.json",
            symbol=sym,
            interval="1d",
            requested_period=daily_period,
            captured_at=capture_time,
        )
        provenance["intraday"] = intraday_summary
        provenance["daily"] = daily_summary
    if raw_out is not None:
        output = Path(raw_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(output)
    result = build_session_frame(normalized, prior_daily=daily_normalized)
    result.attrs["archive_provenance"] = provenance
    return result

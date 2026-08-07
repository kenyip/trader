#!/usr/bin/env python3
"""
Data layer: load OHLCV via yfinance, build features used by the strategy classifier.

Outputs a pandas DataFrame indexed by date with one row per trading day. Every row
holds the state of the world *as of that close* — no future leakage. The backtest
loop is expected to make its decision using row t and apply outcomes on row t+1.

Feature groups:
- returns        ret_1d, ret_5d, ret_14d, ret_30d
- trend          ema_9, ema_21, ema_55, ema_200, ema_stack (-1..+1)
- momentum       rsi_14, macd, macd_signal, macd_hist
- range          atr_14, bb_pctb
- volume         vol_20d_avg, volume_surge (today / 20d avg)
- volatility     hv_20, hv_30, hv_60 (annualised), iv_proxy, iv_rank
- intraday       intraday_return ((close - open) / open)
- regime         regime ('bullish'|'bearish'|'neutral'), reversal, high_iv (bools)
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent / ".cache"
TRADING_DAYS_PER_YEAR = 252

# v1.12 — TSLA earnings dates (mirrored from scenarios.py to avoid circular import).
# When updating, keep both lists in sync. Used for days_to/since_earnings features.
_TSLA_EARNINGS_DATES = [
    '2021-01-27', '2021-04-26', '2021-07-26', '2021-10-20',
    '2022-01-26', '2022-04-20', '2022-07-20', '2022-10-19',
    '2023-01-25', '2023-04-19', '2023-07-19', '2023-10-18',
    '2024-01-24', '2024-04-23', '2024-07-23', '2024-10-23',
    '2025-01-29', '2025-04-22', '2025-07-23', '2025-10-22',
]


def _cache_last_date(index: pd.Index) -> pd.Timestamp | None:
    if index is None or len(index) == 0:
        return None
    return pd.Timestamp(pd.to_datetime(index).max()).normalize()


def _should_refresh_cache(last: pd.Timestamp | None) -> bool:
    """Refresh when cache ends before the current US equity session day.

    Weekends/holidays: last Friday stays valid until next session day advances.
    Intraday RTH: partial today bar from yfinance is preferred over multi-day stale.
    """
    if last is None or pd.isna(last):
        return True
    # Compare on calendar date in America/New_York (equity session anchor).
    try:
        today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
    except Exception:
        today = pd.Timestamp.now().normalize()
    return pd.Timestamp(last).normalize() < today


def load_history(ticker: str, period: str = "10y", use_cache: bool = True) -> pd.DataFrame:
    """Download daily OHLCV. Cached on disk; refreshes when last bar is before today (ET)."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker}_{period}.csv"
    if use_cache and cache_path.exists():
        cached = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        cached.index = pd.to_datetime(cached.index)
        if not _should_refresh_cache(_cache_last_date(cached.index)):
            return cached.sort_index()
    fresh = yf.download(ticker, period=period, auto_adjust=False, progress=False)
    if isinstance(fresh.columns, pd.MultiIndex):
        fresh.columns = fresh.columns.get_level_values(0)
    fresh = fresh[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    fresh.columns = ['open', 'high', 'low', 'close', 'volume']
    fresh.to_csv(cache_path)
    fresh.index = pd.to_datetime(fresh.index)
    return fresh.sort_index()


def load_vix(period: str = "10y", use_cache: bool = True) -> pd.Series:
    """v1.12 — fetch ^VIX close series for macro-vol context. Cached to disk.
    Returns an empty Series on failure so feature pipeline degrades gracefully.

    Corrupt on-disk caches (glued rows / wrong field counts) are discarded and
    re-fetched — a bad VIX CSV must not kill every evolve/B3/B4/research path.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"VIX_{period}.csv"
    if use_cache and cache_path.exists():
        try:
            s = pd.read_csv(cache_path, index_col=0, parse_dates=True).iloc[:, 0]
            s.name = "vix"
            if len(s) > 0 and not _should_refresh_cache(_cache_last_date(s.index)):
                return s
        except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, IndexError, OSError):
            # Glued-row / truncated caches (e.g. "10.202017-09-14,...") — drop and refetch.
            try:
                cache_path.unlink(missing_ok=True)
            except OSError:
                pass
    try:
        df = yf.download("^VIX", period=period, auto_adjust=False, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        s = df["Close"].copy()
        s.index = pd.to_datetime(s.index)
        s.name = "vix"
        s.to_csv(cache_path)
        return s
    except Exception:
        return pd.Series(dtype=float, name="vix")


def _third_friday(year: int, month: int) -> pd.Timestamp:
    """Monthly OPEX = 3rd Friday of each month."""
    first = pd.Timestamp(year=year, month=month, day=1)
    # Friday is weekday() == 4
    offset = (4 - first.weekday()) % 7
    first_friday = first + pd.Timedelta(days=offset)
    return first_friday + pd.Timedelta(days=14)


def _days_to_next_opex(date: pd.Timestamp) -> int:
    opex_this = _third_friday(date.year, date.month)
    if date <= opex_this:
        return (opex_this - date).days
    nm = date + pd.offsets.MonthBegin(1)
    return (_third_friday(nm.year, nm.month) - date).days


def _earnings_distance(date: pd.Timestamp, dates: list[pd.Timestamp]) -> tuple[int, int]:
    """Return (days_to_next_earnings, days_since_last_earnings).
    Each clamped to 0..120; sentinel 120 means 'no known event within window'."""
    CAP = 120
    days_to = CAP
    days_since = CAP
    for d in dates:
        delta = (d - date).days
        if delta >= 0 and delta < days_to:
            days_to = delta
        if delta < 0 and -delta < days_since:
            days_since = -delta
    return days_to, days_since


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _hv(close: pd.Series, n: int) -> pd.Series:
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(n).std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def _ema_stack_score(df: pd.DataFrame) -> pd.Series:
    """Return -1..+1 score for how aligned the EMA fan is."""
    bull = (df['ema_9'] > df['ema_21']).astype(int) \
         + (df['ema_21'] > df['ema_55']).astype(int) \
         + (df['ema_55'] > df['ema_200']).astype(int)
    bear = (df['ema_9'] < df['ema_21']).astype(int) \
         + (df['ema_21'] < df['ema_55']).astype(int) \
         + (df['ema_55'] < df['ema_200']).astype(int)
    score = (bull - bear) / 3.0
    return score.where(df['ema_200'].notna())


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out['ret_1d'] = out['close'].pct_change(1)
    out['ret_5d'] = out['close'].pct_change(5)
    out['ret_14d'] = out['close'].pct_change(14)
    out['ret_30d'] = out['close'].pct_change(30)

    for n in (9, 21, 55, 200):
        out[f'ema_{n}'] = out['close'].ewm(span=n, adjust=False).mean()
    out['ema_stack'] = _ema_stack_score(out)

    out['rsi_14'] = _rsi(out['close'], 14)

    ema12 = out['close'].ewm(span=12, adjust=False).mean()
    ema26 = out['close'].ewm(span=26, adjust=False).mean()
    out['macd'] = ema12 - ema26
    out['macd_signal'] = out['macd'].ewm(span=9, adjust=False).mean()
    out['macd_hist'] = out['macd'] - out['macd_signal']

    out['atr_14'] = _atr(out['high'], out['low'], out['close'], 14)

    bb_mid = out['close'].rolling(20).mean()
    bb_std = out['close'].rolling(20).std()
    out['bb_pctb'] = (out['close'] - (bb_mid - 2 * bb_std)) / (4 * bb_std)

    out['vol_20d_avg'] = out['volume'].rolling(20).mean()
    out['volume_surge'] = out['volume'] / out['vol_20d_avg']

    out['hv_20'] = _hv(out['close'], 20)
    out['hv_30'] = _hv(out['close'], 30)
    out['hv_60'] = _hv(out['close'], 60)

    # IV proxy: use realised vol as a stand-in for option-implied vol. This is
    # acceptable for backtest plumbing; live use should overwrite this column
    # with a real IV pulled from the chain.
    out['iv_proxy'] = out['hv_30']
    out['iv_rank'] = out['iv_proxy'].rolling(TRADING_DAYS_PER_YEAR).rank(pct=True) * 100
    # v1.12 — longer-window IV rank (3 years) captures structural-break context
    out['iv_rank_3y'] = out['iv_proxy'].rolling(TRADING_DAYS_PER_YEAR * 3).rank(pct=True) * 100

    out['intraday_return'] = (out['close'] - out['open']) / out['open'] * 100

    # v1.12 — calendar features
    out['day_of_week'] = out.index.dayofweek           # 0=Mon ... 4=Fri
    out['days_to_monthly_opex'] = [_days_to_next_opex(d) for d in out.index]

    # v1.12 — earnings features (TSLA earnings move TSLL too, so use the same dates)
    earnings = [pd.Timestamp(d) for d in _TSLA_EARNINGS_DATES]
    distances = [_earnings_distance(d, earnings) for d in out.index]
    out['days_to_earnings'] = [t[0] for t in distances]
    out['days_since_earnings'] = [t[1] for t in distances]

    # v1.12 — VIX (macro vol context). Joined as-of trading days; forward-fill
    # weekend/holiday gaps. Missing → NaN, rules should handle gracefully.
    vix = load_vix(period='10y')
    if not vix.empty:
        out['vix'] = vix.reindex(out.index, method='ffill')
        out['vix_rank'] = out['vix'].rolling(TRADING_DAYS_PER_YEAR).rank(pct=True) * 100
    else:
        out['vix'] = np.nan
        out['vix_rank'] = np.nan

    out = _classify_regime(out)
    return out


def _classify_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mirrors the logic in strategy_v5_optimized.classify_scenario plus the v6.3
    intraday reversal trigger and the v6 high-IV flag. Each row tagged from its
    own state — no peek-ahead.
    """
    price = df['close']
    bullish = (
        (price > df['ema_200'])
        & (df['ema_21'] > df['ema_55'])
        & (df['rsi_14'] < 70)
        & (df['macd'] > 0)
        & (df['volume_surge'] > 1.2)
    )
    bearish = (
        (price < df['ema_55'])
        & (df['macd'] < 0)
    )
    regime = np.where(bullish, 'bullish', np.where(bearish, 'bearish', 'neutral'))

    df['regime'] = regime
    df['reversal'] = (df['intraday_return'] < -3.0) & (df['volume_surge'] > 1.5)
    df['high_iv'] = df['iv_rank'] > 50
    return df


def build(ticker: str = 'TSLA', period: str = '10y', use_cache: bool = True) -> pd.DataFrame:
    """Convenience: load + features in one call."""
    raw = load_history(ticker, period=period, use_cache=use_cache)
    return add_features(raw).dropna(subset=['ema_200', 'iv_rank'])


if __name__ == "__main__":
    for ticker in ('TSLA', 'TSLL'):
        print(f"\n=== {ticker} ===")
        df = build(ticker, period='5y')
        print(f"rows: {len(df)}  range: {df.index.min().date()} → {df.index.max().date()}")
        latest = df.iloc[-1]
        cols = ['close', 'ret_14d', 'rsi_14', 'macd_hist', 'volume_surge',
                'hv_30', 'iv_rank', 'intraday_return', 'regime', 'reversal', 'high_iv']
        print(latest[cols].to_string())
        print(f"\nregime distribution over full sample:")
        print(df['regime'].value_counts(normalize=True).round(3).to_string())
        print(f"reversal days: {df['reversal'].sum()}  |  high_iv days: {df['high_iv'].sum()}")

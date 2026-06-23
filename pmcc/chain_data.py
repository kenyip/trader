from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

import pricing
from pmcc.market_hours import cache_policy_label, is_chain_cache_fresh, is_regular_trading_session

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


@dataclass
class ChainMeta:
    ticker: str
    fetched_at: datetime
    from_cache: bool
    spot: float
    n_rows: int
    n_expirations: int
    age_minutes: float
    market_open: bool = False
    cache_policy: str = ""


_LAST_META: ChainMeta | None = None


def chain_fetch_meta() -> ChainMeta | None:
    return _LAST_META


def _cache_paths(ticker: str) -> tuple[Path, Path]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = ticker.upper()
    return (
        CACHE_DIR / f"pmcc_{key}_chain.parquet",
        CACHE_DIR / f"pmcc_{key}_meta.json",
    )


def _load_cached_chain(
    ticker: str,
    max_age_minutes: int,
) -> tuple[float, pd.DataFrame, ChainMeta] | None:
    parquet_path, meta_path = _cache_paths(ticker)
    if not parquet_path.exists() or not meta_path.exists():
        return None
    try:
        with open(meta_path) as f:
            raw = json.load(f)
        fetched_at = datetime.fromisoformat(raw["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if not is_chain_cache_fresh(fetched_at, trading_ttl_minutes=max_age_minutes, now=now):
            return None
        df = pd.read_parquet(parquet_path)
        spot = float(raw["spot"])
        age = (now - fetched_at).total_seconds() / 60.0
        meta = ChainMeta(
            ticker=ticker.upper(),
            fetched_at=fetched_at,
            from_cache=True,
            spot=spot,
            n_rows=int(raw["n_rows"]),
            n_expirations=int(raw["n_expirations"]),
            age_minutes=age,
            market_open=is_regular_trading_session(now),
            cache_policy=cache_policy_label(now),
        )
        return spot, df, meta
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_cached_chain(ticker: str, spot: float, df: pd.DataFrame) -> ChainMeta:
    parquet_path, meta_path = _cache_paths(ticker)
    df.to_parquet(parquet_path, index=False)
    fetched_at = datetime.now(timezone.utc)
    n_exp = int(df["expiration"].nunique())
    meta = {
        "ticker": ticker.upper(),
        "fetched_at": fetched_at.isoformat(),
        "spot": spot,
        "n_rows": len(df),
        "n_expirations": n_exp,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    now = datetime.now(timezone.utc)
    return ChainMeta(
        ticker=ticker.upper(),
        fetched_at=fetched_at,
        from_cache=False,
        spot=spot,
        n_rows=len(df),
        n_expirations=n_exp,
        age_minutes=0.0,
        market_open=is_regular_trading_session(now),
        cache_policy=cache_policy_label(now),
    )


def _mid(bid: float, ask: float, last: float) -> float:
    if bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    if last > 0:
        return last
    return max(bid, ask, 0.0)


def _spread_pct(bid: float, ask: float, mid: float) -> float:
    if mid <= 0 or bid <= 0 or ask <= 0:
        return 1.0
    return (ask - bid) / mid


def fetch_spot(ticker: str) -> float:
    t = yf.Ticker(ticker)
    spot = t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
    if spot is None or spot <= 0:
        hist = t.history(period="5d")
        if hist.empty:
            raise RuntimeError(f"could not fetch spot for {ticker}")
        spot = float(hist["Close"].iloc[-1])
    return float(spot)


def _fetch_call_chain_live(
    ticker: str,
    *,
    r: float = 0.04,
    min_dte: int = 1,
) -> tuple[float, pd.DataFrame]:
    t = yf.Ticker(ticker)
    spot = fetch_spot(ticker)
    today = pd.Timestamp(date.today())
    rows: list[dict] = []

    for exp_str in t.options:
        exp = pd.Timestamp(exp_str)
        dte = (exp - today).days
        if dte < min_dte:
            continue
        try:
            calls = t.option_chain(exp_str).calls
        except Exception:
            continue
        if calls is None or calls.empty:
            continue

        for _, row in calls.iterrows():
            strike = float(row["strike"])
            bid = float(row.get("bid") or 0.0)
            ask = float(row.get("ask") or 0.0)
            last = float(row.get("lastPrice") or 0.0)
            iv = float(row.get("impliedVolatility") or 0.0)
            if iv <= 0 or strike <= 0:
                continue
            mid = _mid(bid, ask, last)
            T = dte / 365.0
            try:
                delta = pricing.delta(spot, strike, T, iv, "call", r=r)
                theta = pricing.theta(spot, strike, T, iv, "call", r=r) / 365.0
            except (ValueError, ZeroDivisionError):
                continue
            rows.append({
                "expiration": exp_str,
                "dte": dte,
                "strike": strike,
                "bid": bid,
                "ask": ask,
                "last": last,
                "mid": mid,
                "iv": iv,
                "delta": delta,
                "theta_per_day": theta,
                "volume": float(row.get("volume") or 0.0),
                "open_interest": float(row.get("openInterest") or 0.0),
                "spread_pct": _spread_pct(bid, ask, mid),
            })

    if not rows:
        raise RuntimeError(f"no call chain data for {ticker}")

    df = pd.DataFrame(rows)
    df["ticker"] = ticker
    df["spot"] = spot
    return spot, df.sort_values(["dte", "strike"]).reset_index(drop=True)


def fetch_call_chain(
    ticker: str,
    *,
    r: float = 0.04,
    min_dte: int = 1,
    use_cache: bool = True,
    refresh: bool = False,
    max_age_minutes: int = 30,
) -> tuple[float, pd.DataFrame]:
    """Return (spot, calls_df). Caches to .cache/pmcc_{TICKER}_chain.parquet."""
    global _LAST_META

    if use_cache and not refresh:
        cached = _load_cached_chain(ticker, max_age_minutes)
        if cached is not None:
            spot, df, meta = cached
            _LAST_META = meta
            return spot, df

    spot, df = _fetch_call_chain_live(ticker, r=r, min_dte=min_dte)
    if use_cache:
        _LAST_META = _save_cached_chain(ticker, spot, df)
    else:
        now = datetime.now(timezone.utc)
        _LAST_META = ChainMeta(
            ticker=ticker.upper(),
            fetched_at=now,
            from_cache=False,
            spot=spot,
            n_rows=len(df),
            n_expirations=int(df["expiration"].nunique()),
            age_minutes=0.0,
            market_open=is_regular_trading_session(now),
            cache_policy=cache_policy_label(now),
        )
    return spot, df


def format_chain_source(meta: ChainMeta | None) -> str:
    if meta is None:
        return "chain source: unknown"
    ts = meta.fetched_at.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    policy = meta.cache_policy or cache_policy_label()
    if meta.from_cache:
        return (
            f"chain: cached snapshot @ {ts} "
            f"({meta.age_minutes:.0f}m old, {meta.n_rows} calls / {meta.n_expirations} exp) — {policy}"
        )
    return (
        f"chain: live fetch @ {ts} "
        f"({meta.n_rows} calls / {meta.n_expirations} exp) → .cache/pmcc_{meta.ticker}_chain.parquet — {policy}"
    )


def pick_contract_at_strike(
    chain: pd.DataFrame,
    strike: float,
    target_dte: int,
    *,
    dte_min: int | None = None,
    dte_max: int | None = None,
) -> pd.Series | None:
    """Call at exact strike; expiration nearest target_dte."""
    sub = chain[chain["strike"] == float(strike)]
    if dte_min is not None:
        sub = sub[sub["dte"] >= dte_min]
    if dte_max is not None:
        sub = sub[sub["dte"] <= dte_max]
    if sub.empty:
        return None

    exp_dtes = sub.groupby("expiration")["dte"].first()
    best_exp = (exp_dtes - target_dte).abs().idxmin()
    exp_rows = sub[sub["expiration"] == best_exp]
    if exp_rows.empty:
        return None
    return exp_rows.iloc[0]


def pick_contract(
    chain: pd.DataFrame,
    target_dte: int,
    target_delta: float,
    *,
    dte_min: int | None = None,
    dte_max: int | None = None,
) -> pd.Series | None:
    """Best call on the chain for target DTE and delta."""
    sub = chain
    if dte_min is not None:
        sub = sub[sub["dte"] >= dte_min]
    if dte_max is not None:
        sub = sub[sub["dte"] <= dte_max]
    if sub.empty:
        return None

    exp_dtes = sub.groupby("expiration")["dte"].first()
    best_exp = (exp_dtes - target_dte).abs().idxmin()
    exp_rows = sub[sub["expiration"] == best_exp]
    if exp_rows.empty:
        return None

    idx = (exp_rows["delta"] - target_delta).abs().idxmin()
    return exp_rows.loc[idx]
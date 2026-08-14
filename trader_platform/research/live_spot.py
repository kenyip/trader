"""No-LLM last-price helper for the 1m paper tick.

Prefer a fresh RH quote-bus file. Fall back to yfinance fast_info / 1m bars.
Never calls a model. Never places.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
RH_QUOTES = _REPO / ".cache" / "platform" / "rh_quotes" / "LATEST.json"
_MEMO: dict[str, tuple[float, float, str]] = {}


def _age_seconds(generated_at: str) -> float | None:
    try:
        ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
    except Exception:
        return None


def load_rh_quotes(max_age_s: float = 90.0) -> dict[str, Any] | None:
    if not RH_QUOTES.exists():
        return None
    try:
        data = json.loads(RH_QUOTES.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not data.get("ok"):
        return None
    age = _age_seconds(str(data.get("generated_at") or ""))
    if age is None or age > max_age_s:
        return None
    return data


def last_spot(symbol: str) -> dict[str, Any]:
    """Return {symbol, last, source, asof} or last=None."""
    sym = str(symbol).upper().strip()
    now = time.time()
    cached = _MEMO.get(sym)
    if cached and now - cached[1] < 20:
        return {"symbol": sym, "last": cached[0], "source": cached[2], "asof": None}

    rh = load_rh_quotes()
    if rh:
        row = (rh.get("symbols") or {}).get(sym) or {}
        last = row.get("last")
        last_f = None
        if last is not None:
            try:
                last_f = float(last)
            except (TypeError, ValueError):
                last_f = None
        if last_f and last_f > 0:
            src = str(rh.get("source") or "quote_file")
            if src == "rh_mcp":
                label = "rh_mcp"
            elif src.startswith("yf"):
                label = src
            else:
                label = src
            _MEMO[sym] = (last_f, now, label)
            return {
                "symbol": sym,
                "last": last_f,
                "source": label,
                "asof": row.get("asof") or rh.get("generated_at"),
            }

    last_f = None
    source = "missing"
    try:
        import yfinance as yf

        info = getattr(yf.Ticker(sym), "fast_info", None)
        if info is not None:
            last_f = info.get("last_price") or info.get("lastPrice") or info.get("regularMarketPrice")
            last_f = float(last_f) if last_f is not None else None
            source = "yf_fast_info"
        if not last_f:
            hist = yf.Ticker(sym).history(period="1d", interval="1m")
            if hist is not None and len(hist) > 0:
                last_f = float(hist["Close"].iloc[-1])
                source = "yf_1m"
    except Exception:
        last_f = None
        source = "error"

    if last_f and last_f > 0:
        _MEMO[sym] = (last_f, now, source)
        return {"symbol": sym, "last": last_f, "source": source, "asof": None}
    return {"symbol": sym, "last": None, "source": source, "asof": None}

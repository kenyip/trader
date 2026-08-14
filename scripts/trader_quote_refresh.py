#!/usr/bin/env python3
"""Same-clock yfinance tape for the 1m no-LLM paper tick.

Writes:
  .cache/platform/rh_quotes/LATEST.json   (yf last; overwritten by trader RH when woken)
  .cache/platform/rh_quotes/WAKE.txt      (stable; trader monitor hashes this)

LLM/RH is NOT called here. Interesting prices flip WAKE.txt so the trader
monitor job fetches real RH quotes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

OUT = _REPO / ".cache" / "platform" / "rh_quotes" / "LATEST.json"
WAKE = _REPO / ".cache" / "platform" / "rh_quotes" / "WAKE.txt"
PREV = _REPO / ".cache" / "platform" / "rh_quotes" / "YF_PREV.json"
LEDGER = _REPO / ".cache" / "platform" / "paper_ledger.json"
WATCHER = _REPO / ".cache" / "platform" / "spine" / "watcher_LATEST.json"
INTEREST = _REPO / ".cache" / "platform" / "rh_quotes" / "INTEREST.json"
HUNT = ("INTC", "KO", "PLTR", "BAC", "IWM", "AAL", "CCL")
MOVE_FRAC = 0.004
APPROACH_FRAC = 0.015
RH_FRESH_S = 480.0


def _clamp(val: float, lo: float, hi: float, default: float) -> float:
    try:
        x = float(val)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, x))


def _load_interest() -> dict:
    if not INTEREST.exists():
        return {}
    try:
        data = json.loads(INTEREST.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _cfg() -> tuple[dict, dict[str, dict], list[str], float]:
    data = _load_interest()
    raw_defaults = data.get("defaults")
    defaults = raw_defaults if isinstance(raw_defaults, dict) else {}
    move = _clamp(defaults.get("move_frac", MOVE_FRAC), 0.001, 0.03, MOVE_FRAC)
    approach = _clamp(defaults.get("approach_frac", APPROACH_FRAC), 0.005, 0.08, APPROACH_FRAC)
    fresh = _clamp(defaults.get("rh_fresh_s", RH_FRESH_S), 120, 1800, RH_FRESH_S)
    raw_hunt = defaults.get("hunt")
    hunt = raw_hunt if isinstance(raw_hunt, list) else list(HUNT)
    hunt_s = [str(s).upper() for s in hunt if str(s).strip()][:12] or list(HUNT)
    raw_symbols = data.get("symbols")
    symbols = raw_symbols if isinstance(raw_symbols, dict) else {}
    per = {str(k).upper(): v for k, v in symbols.items() if isinstance(v, dict)}
    return {"move_frac": move, "approach_frac": approach, "rh_fresh_s": fresh}, per, hunt_s, fresh


def _universe() -> list[str]:
    seen: list[str] = []
    if LEDGER.exists():
        try:
            data = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        orders = data.get("orders") or {}
        items = orders.values() if isinstance(orders, dict) else orders
        for o in items:
            if not isinstance(o, dict):
                continue
            if str(o.get("status") or "").lower() not in {"working", "filled", "replaced"}:
                continue
            sym = str(o.get("symbol") or "").upper().strip()
            if sym and sym not in seen:
                seen.append(sym)
    defaults, per, hunt_s, _fresh = _cfg()
    for sym in hunt_s:
        if sym not in seen:
            seen.append(sym)
    return seen[:10]


def _working_orders() -> list[dict]:
    if not LEDGER.exists():
        return []
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return []
    orders = data.get("orders") or {}
    items = orders.values() if isinstance(orders, dict) else orders
    out = []
    for o in items:
        if not isinstance(o, dict):
            continue
        if str(o.get("status") or "").lower() not in {"working", "filled", "replaced"}:
            continue
        if "smoke" in str(o.get("tag") or "").lower():
            continue
        out.append(o)
    return out


def _yf_symbols(symbols: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        import yfinance as yf
    except Exception:
        return out
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for sym in symbols:
        last = None
        try:
            info = getattr(yf.Ticker(sym), "fast_info", None)
            if info is not None:
                last = info.get("last_price") or info.get("lastPrice") or info.get("regularMarketPrice")
            if last is None:
                hist = yf.Ticker(sym).history(period="1d", interval="1m")
                if hist is not None and len(hist) > 0:
                    last = float(hist["Close"].iloc[-1])
            last_f = float(last) if last is not None else None
        except Exception:
            last_f = None
        out[sym] = {"last": last_f, "bid": None, "ask": None, "asof": now}
    return out


def _rh_age_s() -> float | None:
    if not OUT.exists():
        return None
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return None
    if str(data.get("source") or "") != "rh_mcp" or not data.get("ok"):
        return None
    try:
        ts = datetime.fromisoformat(str(data.get("generated_at") or "").replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
    except Exception:
        return None


def _interest(rows: dict[str, dict], prev: dict[str, float]) -> list[str]:
    flags: list[str] = []
    defaults, per, _hunt, _fresh = _cfg()
    for o in _working_orders():
        sym = str(o.get("symbol") or "").upper()
        last = (rows.get(sym) or {}).get("last")
        if not last:
            continue
        cfg = per.get(sym) or {}
        move = _clamp(cfg.get("move_frac", defaults["move_frac"]), 0.001, 0.03, defaults["move_frac"])
        approach = _clamp(
            cfg.get("approach_frac", defaults["approach_frac"]), 0.005, 0.08, defaults["approach_frac"]
        )
        put_wake = cfg.get("put_wake_above")
        call_wake = cfg.get("call_wake_below")
        try:
            put_f = float(put_wake) if put_wake is not None else None
        except (TypeError, ValueError):
            put_f = None
        try:
            call_f = float(call_wake) if call_wake is not None else None
        except (TypeError, ValueError):
            call_f = None
        short = o.get("short_strike")
        try:
            short_f = float(short) if short is not None else None
        except (TypeError, ValueError):
            short_f = None
        if put_f is not None and last <= put_f:
            flags.append(f"{sym}:put_band")
        if call_f is not None and last >= call_f:
            flags.append(f"{sym}:call_band")
        if short_f and short_f > 0 and put_f is None and call_f is None:
            if last < short_f:
                flags.append(f"{sym}:short_breach")
            elif last <= short_f * (1.0 + approach):
                flags.append(f"{sym}:short_approach")
        prev_last = prev.get(sym)
        if prev_last and prev_last > 0 and abs(last - prev_last) / prev_last >= move:
            flags.append(f"{sym}:move")
    if WATCHER.exists():
        try:
            w = json.loads(WATCHER.read_text(encoding="utf-8"))
        except Exception:
            w = {}
        if str(w.get("status") or "") == "PAPER_PACKET_READY":
            sym = str(w.get("symbol") or "").upper()
            working_syms = {
                str(o.get("symbol") or "").upper()
                for o in _working_orders()
                if str(o.get("symbol") or "").strip()
            }
            # Already-open leftover must not hammer RH WAKE every minute.
            if sym and sym not in working_syms:
                flags.append(f"{sym}:packet_ready")
    return sorted(set(flags))


def _write_wake(flags: list[str]) -> str:
    defaults, _per, _hunt, fresh = _cfg()
    data = _load_interest()
    raw_defaults = data.get("defaults") if isinstance(data, dict) else {}
    defaults_map = raw_defaults if isinstance(raw_defaults, dict) else {}
    rh_wake = defaults_map.get("rh_wake", True)
    if isinstance(rh_wake, str):
        rh_wake = rh_wake.strip().lower() not in {"0", "false", "no", "off", "blocked"}
    rh_age = _rh_age_s()
    rh = "fresh" if rh_age is not None and rh_age < fresh else "stale"
    # RH OAuth parked → yf tape is authority. Do not flip WAKE every minute.
    if rh_wake is False:
        line = "quiet rh:blocked"
    elif flags and rh == "stale":
        line = "need " + " ".join(flags) + " rh:stale"
    else:
        line = "quiet"
    WAKE.parent.mkdir(parents=True, exist_ok=True)
    WAKE.write_text(line + "\n", encoding="utf-8")
    return line


def main() -> int:
    symbols = _universe()
    prev: dict[str, float] = {}
    if PREV.exists():
        try:
            raw = json.loads(PREV.read_text(encoding="utf-8"))
            prev = {str(k).upper(): float(v) for k, v in (raw or {}).items() if v}
        except Exception:
            prev = {}
    rows = _yf_symbols(symbols)
    ok = any((r or {}).get("last") for r in rows.values())
    source = "yf_1m" if ok else "missing"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    # Keep a prior RH file if it is still fresh; yf last is merged in.
    existing = None
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            existing = None
    rh_age = _rh_age_s()
    if existing and str(existing.get("source")) == "rh_mcp" and rh_age is not None and rh_age < 90:
        payload = existing
        payload["yf_overlay"] = rows
    else:
        payload = {
            "generated_at": now,
            "source": source,
            "trading_authority": False,
            "ok": ok,
            "symbols": rows,
            "options": existing.get("options") if isinstance(existing, dict) else [],
            "universe": symbols,
        }
        if not ok:
            payload["error"] = "no_last"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    wake = _write_wake(_interest(rows, prev))
    PREV.write_text(
        json.dumps(
            {s: (rows.get(s) or {}).get("last") for s in symbols if (rows.get(s) or {}).get("last")},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"bottom_line": "quotes", "source": payload.get("source"), "n": len(rows), "ok": ok, "wake": wake}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

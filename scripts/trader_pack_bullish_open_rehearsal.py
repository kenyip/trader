#!/usr/bin/env python3
"""Off-RTH bullish-bar consume rehearsal for the first-live PCS door.

Mocks a bullish KO daily (INTC leftover stays blocked). Never places.
Also tries pick_structure_entry on the cached Friday KO bar so Monday
knows whether 1-lot $1-wide legs can be built from existing data.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.living_registry import load_living_registry
from trader_platform.research.opportunity_watcher import watch_once
from trader_platform.research.pack_grade import is_pack_grade, quality_pass_index
from trader_platform.research.paper_handoff import intent_from_watch, run_paper_handoff
from trader_platform.research.pcs_sim import pick_structure_entry

try:
    from data import build as build_market_frame
except Exception:  # pragma: no cover
    build_market_frame = None  # type: ignore[assignment]

BU4 = "PCS_BULL_NEUTRAL_INCOME_45D_PT50_V1__dn_d12_pt40_dl14_iv15_c8_w1_pcs_bu_4"


def _fake_bar(symbol: str, period: str = "3mo"):
    sym = str(symbol).upper()
    if sym == "KO":
        row = pd.Series(
            {"close": 87.71, "iv_proxy": 0.4, "iv_rank": 90.08, "regime": "bullish"}
        )
    elif sym == "PLTR":
        row = pd.Series(
            {"close": 174.04, "iv_proxy": 0.4, "iv_rank": 98.41, "regime": "neutral"}
        )
    else:
        row = pd.Series(
            {"close": 102.5, "iv_proxy": 0.35, "iv_rank": 56.35, "regime": "neutral"}
        )
    return row, pd.Timestamp("2026-08-17")


def _pick_cached(symbol: str) -> dict:
    if build_market_frame is None:
        return {"ok": False, "reason": "data.build unavailable"}
    frame = None
    for period in ("1y", "2y", "5y"):
        try:
            candidate = build_market_frame(symbol, period=period, use_cache=True)
        except Exception as exc:
            return {"ok": False, "reason": f"build {period}: {exc}"}
        if candidate is not None and len(candidate) >= 5:
            frame = candidate
            break
    if frame is None:
        return {"ok": False, "reason": "no frame"}
    row = frame.iloc[-1]
    today = pd.Timestamp(str(frame.index[-1]))
    spot = float(row.get("close") or 0.0)
    cfg = {
        "structure": "put_credit_spread",
        "long_dte": 21,
        "long_target_delta": 0.20,
        "spread_width": 1.0,
        "min_credit_pct": 0.08,
        "profit_target": 0.40,
        "max_loss_budget_usd": 300.0,
        "iv_rank_min": 15.0,
        "bear_dte": 0,
    }
    trade = pick_structure_entry(row, spot, today, cfg, structure="put_credit_spread")
    if trade is None:
        return {
            "ok": False,
            "reason": "pick_structure_entry None",
            "spot": spot,
            "date": str(today)[:10],
            "regime": str(row.get("regime") or ""),
            "iv_rank": float(row.get("iv_rank") or 0.0),
        }
    return {
        "ok": True,
        "spot": spot,
        "date": str(today)[:10],
        "regime": str(row.get("regime") or ""),
        "iv_rank": float(row.get("iv_rank") or 0.0),
        "short_strike": float(trade.short_strike),
        "long_strike": float(trade.long_strike),
        "width": float(trade.width),
        "net_credit": float(trade.net_credit),
        "max_loss_usd": float(trade.max_loss_per_share) * 100.0,
        "dte": int(trade.dte_at_entry),
        "expiration": str(trade.expiration.date()),
    }


def main() -> int:
    reg = load_living_registry()
    idx = quality_pass_index()
    with patch(
        "trader_platform.research.opportunity_watcher._latest_bar",
        side_effect=_fake_bar,
    ):
        watch = watch_once(registry=reg)
    handoff = run_paper_handoff(watch=watch, dry_run=True, execute_paper=False)
    intent, intent_reason, intent_meta = intent_from_watch(watch, registry=reg)
    pick = _pick_cached("KO")
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "live_authority": False,
        "trading_authority": False,
        "honesty": (
            "Synthetic Monday bullish KO bar for watch only. "
            "pick_structure_entry uses cached Friday last bar. "
            "dry_run — no paper place, no ARM."
        ),
        "watch": {
            "status": watch.status,
            "reason": watch.reason,
            "seat_id": watch.seat_id,
            "candidate_id": watch.candidate_id,
            "symbol": watch.symbol,
            "regime": watch.regime,
            "selected_structure": watch.selected_structure,
            "is_pack_grade": is_pack_grade(
                candidate_id=str(watch.candidate_id or ""),
                seat_id=str(watch.seat_id or ""),
                symbol=str(watch.symbol or ""),
                index=idx,
            ),
            "door_match": watch.candidate_id == BU4 and watch.symbol == "KO",
        },
        "handoff": {
            "status": handoff.status,
            "reason": handoff.reason,
            "paper_action": getattr(handoff, "paper_action", ""),
        },
        "intent": {
            "ok": intent is not None,
            "reason": intent_reason,
            "max_loss_usd": None if intent is None else intent.max_loss_usd,
            "net_credit": None if intent is None else intent.net_credit,
            "structure": None if intent is None else intent.structure,
            "meta": {
                k: intent_meta.get(k)
                for k in ("expiration", "net_credit", "max_loss_usd", "seat_status")
            },
        },
        "cached_ko_pick": pick,
        "monday_rule": (
            "If live watch is PAPER_PACKET_READY on bu_4_KO, Monday agent may "
            "just trader-paper-handoff --execute-paper (paper ledger only). "
            "Cron must not --execute-paper. Never ARM."
        ),
    }
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        _REPO / "reports" / "trader-wakes" / "2026-08-16T1105-pack-bullish-open.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out),
                "watch": report["watch"],
                "handoff": report["handoff"],
                "intent_ok": report["intent"]["ok"],
                "intent_reason": report["intent"]["reason"],
                "cached_ko_pick": pick,
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Sunday/off-RTH pack consume rehearsal. Never places. Never invents DNA.

Pins living MULTI quality_pass bu_4 / bu_6 seats, last daily bars, watch_once,
and dry-run paper_handoff so Monday can OPEN only on a bullish + IV>=15 bar.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research.living_registry import load_living_registry
from trader_platform.research.opportunity_watcher import (
    hunt_symbols,
    watch_once,
    working_paper_symbols,
)
from trader_platform.research.pack_grade import (
    is_pack_grade,
    load_quality_pass_cells,
    quality_pass_index,
    seat_stem,
)
from trader_platform.research.paper_handoff import run_paper_handoff
from trader_platform.research.regime_router_sim import select_structure

try:
    from data import build as build_market_frame
except Exception:  # pragma: no cover
    build_market_frame = None  # type: ignore[assignment]

DOOR_STEMS = (
    "PCS_BULL_NEUTRAL_INCOME_45D_PT50_V1__dn_d12_pt40_dl14_iv15_c8_w1_pcs_bu_4",
    "PCS_BULL_NEUTRAL_INCOME_45D_PT50_V1__dn_d5_pt40_dl18_iv15_c6_w1_pcs_bu_6",
)
DOOR_NAMES = {
    DOOR_STEMS[0]: "bu_4",
    DOOR_STEMS[1]: "bu_6",
}


def _bars(symbol: str, n: int = 15) -> list[dict]:
    if build_market_frame is None:
        return []
    frame = None
    for period in ("1y", "2y", "5y"):
        try:
            candidate = build_market_frame(symbol, period=period, use_cache=True)
        except Exception:
            continue
        if candidate is not None and len(candidate) >= 5:
            frame = candidate
            break
    if frame is None or len(frame) < 1:
        return []
    tail = frame.tail(n)
    out: list[dict] = []
    for ts, row in tail.iterrows():
        out.append(
            {
                "date": str(ts)[:10],
                "close": round(float(row.get("close") or 0.0), 4),
                "regime": str(row.get("regime") or ""),
                "iv_rank": round(float(row.get("iv_rank") or 0.0), 2),
                "open_if_bull_iv15": (
                    str(row.get("regime") or "").lower() == "bullish"
                    and float(row.get("iv_rank") or 0.0) >= 15.0
                ),
            }
        )
    return out


def main() -> int:
    cells = load_quality_pass_cells()
    idx = quality_pass_index(cells)
    blocked = sorted(working_paper_symbols())
    hunt = hunt_symbols()
    door_cells = [
        {
            "door": DOOR_NAMES.get(c["candidate_id"], "other"),
            "candidate_id": c["candidate_id"],
            "f2_symbols": c["f2_symbols"],
            "family_id": c.get("family_id"),
        }
        for c in cells
        if c["candidate_id"] in DOOR_STEMS
    ]
    other_pack = [
        {"candidate_id": c["candidate_id"], "f2_symbols": c["f2_symbols"]}
        for c in cells
        if c["candidate_id"] not in DOOR_STEMS
    ]

    reg = load_living_registry()
    living = []
    for seat in reg.seats:
        stem = seat_stem(seat.seat_id, seat.candidate_id)
        if stem not in DOOR_STEMS:
            continue
        living.append(
            {
                "seat_id": seat.seat_id,
                "candidate_id": seat.candidate_id,
                "status": seat.status,
                "symbols": list(seat.symbols or []),
                "router_policy": getattr(seat, "router_policy", ""),
                "spec_path": seat.spec_path,
                "pack_grade_symbols": sorted(
                    sym
                    for sym in (list(seat.symbols or []) + hunt)
                    if is_pack_grade(
                        candidate_id=seat.candidate_id,
                        seat_id=seat.seat_id,
                        symbol=sym,
                        index=idx,
                    )
                ),
            }
        )

    last_bars = {sym: _bars(sym) for sym in ("KO", "PLTR", "INTC")}
    last_state = {}
    for sym, rows in last_bars.items():
        last = rows[-1] if rows else {}
        structure = None
        if last:
            import pandas as pd

            structure = select_structure(
                pd.Series(last),
                {"iron_condor": {"iv_rank_min": 15.0}},
                policy="pcs_bull_only",
            )
        last_state[sym] = {
            "last": last,
            "pcs_bull_only": structure,
            "blocked_working_paper": sym in blocked,
            "open_days_last_15": sum(1 for r in rows if r.get("open_if_bull_iv15")),
        }

    watch = watch_once(registry=reg)
    handoff = run_paper_handoff(watch=watch, dry_run=True)
    watch_pack = is_pack_grade(
        candidate_id=str(watch.candidate_id or ""),
        seat_id=str(watch.seat_id or ""),
        symbol=str(watch.symbol or ""),
        index=idx,
    )

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "live_authority": False,
        "trading_authority": False,
        "honesty": (
            "Off-RTH consume rehearsal. Last daily bar is Friday close. "
            "pcs_bull_only OPEN only on bullish + iv_rank>=15. "
            "Leftover INTC working paper is blocked. Do not remake INTC. "
            "Do not hunt SNAP/CSP as ARM. Never place_*."
        ),
        "multi_n_quality_pass": len(cells),
        "door_cells": door_cells,
        "other_pack_cells": other_pack,
        "blocked_working_paper": blocked,
        "hunt_symbols": hunt,
        "living_door_seats": living,
        "last_state": last_state,
        "last_bars": last_bars,
        "watch": {
            "status": watch.status,
            "reason": watch.reason,
            "seat_id": watch.seat_id,
            "candidate_id": watch.candidate_id,
            "symbol": watch.symbol,
            "regime": watch.regime,
            "selected_structure": watch.selected_structure,
            "is_pack_grade": watch_pack,
            "seats_considered_head": list(watch.seats_considered or [])[:12],
            "n_considered": len(watch.seats_considered or []),
        },
        "handoff": {
            "status": handoff.status,
            "reason": handoff.reason,
            "paper_action": getattr(handoff, "paper_action", ""),
            "watch_status": getattr(handoff, "watch_status", ""),
        },
        "monday_rule": {
            "primary": "OPEN 1-lot $1-wide bu_4 on KO if new daily bar is bullish and iv_rank>=15",
            "backup": "OPEN 1-lot $1-wide bu_6 on PLTR if new daily bar is bullish and iv_rank>=15",
            "stand_aside": "neutral/bear is a pass — do not force leftover F IC or SNAP CSP",
            "blocked": "INTC leftover working — do not remake; do not overlay pack PCS on INTC",
        },
    }
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        _REPO / "reports" / "trader-wakes" / "2026-08-16T0900-pack-monday-rehearsal.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    summary = {
        "out": str(out),
        "n_quality_pass": len(cells),
        "door_cells": door_cells,
        "living_door_n": len(living),
        "blocked": blocked,
        "last_state": last_state,
        "watch": report["watch"],
        "handoff": report["handoff"],
    }
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Patient opportunity watcher for Desk B.

Always safe to run with zero living strategies. Never places orders.
Statuses: NO_QUALIFIED_STRATEGY | NO_SETUP | PAPER_PACKET_READY | GATED_LIVE_PACKET
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import pandas as pd

from trader_platform.research.living_registry import (
    LivingRegistry,
    LivingSeat,
    load_living_registry,
)
from trader_platform.research.pack_grade import (
    DOOR_STEMS,
    is_pack_grade,
    quality_pass_index,
    seat_stem,
    watch_sort_key,
)
from trader_platform.research.opportunity import (
    Opportunity,
    StandAside,
    evaluate_from_row,
    thesis_from_strategy_spec,
)
from trader_platform.research.regime_router_sim import select_structure
from trader_platform.research.strategy_spec import (
    StrategySpec,
    load_strategy_spec,
    strategy_spec_from_mapping,
)

try:
    from data import build as build_market_frame
except Exception:  # pragma: no cover
    build_market_frame = None  # type: ignore[assignment]


WATCH_STATUSES = (
    "NO_QUALIFIED_STRATEGY",
    "NO_SETUP",
    "PAPER_PACKET_READY",
    "GATED_LIVE_PACKET",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class WatchResult:
    status: str
    generated_at: str
    desk: str = "B_agentic"
    trading_authority: bool = False
    live_authority: bool = False
    reason: str = ""
    living_watchable_count: int = 0
    seat_id: str = ""
    candidate_id: str = ""
    symbol: str = ""
    regime: str = ""
    selected_structure: str = ""
    packet: dict[str, Any] = field(default_factory=dict)
    seats_considered: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_BAR_MEMO: dict[tuple[str, int], tuple[pd.Series, pd.Timestamp]] = {}
# Pack-grade cells today are INTC/KO/PLTR; F/SNAP/AAL are research hunt, not leftover INTC.
DEFAULT_HUNT_SYMBOLS = ("KO", "PLTR", "F", "AAL", "SNAP", "CCL", "BAC", "IWM", "INTC")


def hunt_symbols() -> list[str]:
    raw = os.environ.get("TRADER_HUNT_SYMBOLS", "").strip()
    if raw:
        return [part.strip().upper() for part in raw.replace(",", " ").split() if part.strip()]
    return list(DEFAULT_HUNT_SYMBOLS)


def working_paper_symbols(ledger_path: str | Path | None = None) -> set[str]:
    """Symbols that already have a real working paper order (skip same-symbol spray)."""
    path = Path(ledger_path) if ledger_path else Path(__file__).resolve().parents[2] / ".cache" / "platform" / "paper_ledger.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    orders = data.get("orders") or {}
    items = orders.values() if isinstance(orders, dict) else orders
    out: set[str] = set()
    for o in items:
        if not isinstance(o, dict):
            continue
        if str(o.get("status") or "").lower() not in {"working", "filled", "replaced"}:
            continue
        if "smoke" in str(o.get("tag") or "").lower():
            continue
        sym = str(o.get("symbol") or "").upper().strip()
        if sym:
            out.add(sym)
    return out


def _latest_bar(symbol: str, period: str = "1y") -> tuple[pd.Series, pd.Timestamp]:
    key = (str(symbol).upper(), int(time.time() // 60))
    cached = _BAR_MEMO.get(key)
    if cached is not None:
        return cached
    if build_market_frame is None:
        raise RuntimeError("data.build unavailable")
    # Prefer requested period; fall back to longer history if cache is thin.
    for candidate in (period, "1y", "2y", "5y"):
        frame = build_market_frame(symbol, period=candidate, use_cache=True)
        if frame is not None and len(frame) >= 5:
            ts = pd.Timestamp(str(frame.index[-1]))
            row = frame.iloc[-1]
            _BAR_MEMO[key] = (row, ts)
            return row, ts
    raise ValueError(f"insufficient bars for {symbol}")


def _load_spec_for_seat(seat: LivingSeat) -> StrategySpec | None:
    if not seat.spec_path:
        return None
    path = Path(seat.spec_path)
    if not path.exists():
        return None
    return load_strategy_spec(path)


def _structure_for_seat(seat: LivingSeat, row: pd.Series, spec: StrategySpec | None) -> str | None:
    """Legacy structure-only path (no entry filters). Prefer `_decision_for_seat`."""
    if spec is not None and spec.evaluation_mode == "regime_router":
        configs = spec.router_configs()
        policy = str(seat.router_policy or spec.router_policy or "router")
        return select_structure(row, configs, policy=policy)
    if spec is not None and spec.evaluation_mode == "single_structure":
        structure = str(spec.structure or "")
        regime = str(row.get("regime") or "").lower()
        if structure == "put_credit_spread" and regime == "bearish":
            return None
        if structure == "call_credit_spread" and regime == "bullish":
            return None
        return structure or None
    # Fallback without spec: long-bias PCS only in non-bear.
    regime = str(row.get("regime") or "").lower()
    if regime in {"bullish", "neutral"}:
        return "put_credit_spread"
    return None


def _decision_for_seat(
    seat: LivingSeat,
    row: pd.Series,
    bar_time: pd.Timestamp,
    symbol: str,
    spec: StrategySpec | None,
) -> Opportunity | StandAside | None:
    """Shared opportunity rules (router + entry filters + signal bounds).

    When a StrategySpec is available, bridge it to a Thesis and run the
    opportunity emitter so watch matches prove-time entry filters.
    Returns None only when no spec exists (legacy fallback).
    """
    if spec is None:
        return None
    # Prefer seat router_policy when present (mutant may differ from seed file)
    policy = str(seat.router_policy or spec.router_policy or "router")
    if policy and policy != spec.router_policy:
        raw = spec.to_dict()
        raw["router_policy"] = policy
        spec = strategy_spec_from_mapping(raw)
    thesis = thesis_from_strategy_spec(spec, thesis_id=seat.candidate_id or seat.seat_id)
    return evaluate_from_row(
        thesis,
        row,
        symbol=symbol,
        asof=str(bar_time),
    )


def _paper_packet(
    *,
    seat: LivingSeat,
    symbol: str,
    regime: str,
    structure: str,
    row: pd.Series,
    bar_time: pd.Timestamp,
    spec: StrategySpec | None,
    decision_reason: str = "",
) -> dict[str, Any]:
    mgmt = dict(spec.management) if spec is not None else {}
    why = (
        f"Living seat {seat.seat_id} is watchable; regime={regime} maps to {structure}; "
        "entry filters / signal bounds passed on this bar."
    )
    if decision_reason:
        why = f"{why} ({decision_reason})"
    return {
        "packet_type": "paper_suggested_limit",
        "trading_authority": False,
        "live_authority": False,
        "seat_id": seat.seat_id,
        "candidate_id": seat.candidate_id,
        "family_id": seat.family_id,
        "funnel_stage": seat.funnel_stage,
        "confidence_stage": seat.status,
        "symbol": symbol,
        "regime": regime,
        "structure": structure,
        "forecast": seat.notes or (spec.forecast_type if spec else ""),
        "bar_time": str(bar_time),
        "spot": float(row.get("close") or 0.0),
        "iv_rank": float(row.get("iv_rank") or 0.0) if row.get("iv_rank") is not None else None,
        "management": {
            "long_dte": mgmt.get("long_dte"),
            "profit_target": mgmt.get("profit_target"),
            "dte_stop": mgmt.get("dte_stop"),
            "defined_loss_exit_frac": mgmt.get("defined_loss_exit_frac"),
            "delta_breach": mgmt.get("delta_breach"),
        },
        "risk": {
            "sleeve_usd": spec.sleeve_usd if spec else 3000.0,
            "max_loss_budget_usd": spec.max_loss_budget_usd if spec else 300.0,
            "max_lots": 1,
            "defined_risk": True,
        },
        "legs": [],  # filled later by scout/OPEN path; watcher only signals readiness
        "why_now": why,
        "invalidation": "regime flip, credit/max-loss filters fail, or risk governor deny",
        "next_action": "paper_only_open_or_update_limit_via_autonomy_loop — not live",
    }


def watch_once(
    *,
    registry: LivingRegistry | None = None,
    registry_path: str | Path | None = None,
    symbol_override: str | None = None,
    allow_live_packet: bool = False,
    market_period: str = "3mo",
) -> WatchResult:
    """Run one patient watch cycle.

    allow_live_packet is always ignored unless a future explicit arm flag is added;
    today it only ever returns GATED_LIVE_PACKET as a placeholder when allow_live_packet
    is True AND a paper packet would fire — still without authority.
    """
    reg = registry if registry is not None else load_living_registry(registry_path)
    watchable = reg.watchable_seats()
    generated = _now_iso()

    if not watchable:
        return WatchResult(
            status="NO_QUALIFIED_STRATEGY",
            generated_at=generated,
            reason=(
                "No f2_holdout/paper_eligible seats in living registry. "
                "Evolve/evaluate until a sealed holdout survivor exists; stand-aside is success."
            ),
            living_watchable_count=0,
            seats_considered=[s.seat_id for s in reg.seats],
        )

    # Prefer MULTI quality_pass cells. When living pack seats exist, fail closed
    # on leftover near-miss / router DNA (do not tunnel leftover INTC).
    pack_index = quality_pass_index()
    pack_only = (
        [s for s in watchable if watch_sort_key(s, pack_index)[0] == 0]
        if pack_index
        else []
    )
    door_only = [
        s
        for s in pack_only
        if seat_stem(s.seat_id, s.candidate_id) in DOOR_STEMS
    ]
    if door_only:
        pack_only = door_only
    others = [s for s in watchable if s not in pack_only]
    if pack_only:
        ordered = sorted(pack_only, key=lambda s: watch_sort_key(s, pack_index))
    else:
        ordered = sorted(others, key=lambda s: watch_sort_key(s, pack_index))
    considered: list[str] = []
    last_no_setup: WatchResult | None = None
    hunt = hunt_symbols()
    blocked = {str(s).upper() for s in working_paper_symbols() if str(s).strip()}

    for seat in ordered:
        considered.append(seat.seat_id)
        symbols = [symbol_override.upper()] if symbol_override else list(seat.symbols)
        if not symbols:
            symbols = ["SPY"]
        # Grow names on pack / paper_eligible seats — same structure, more underlyings.
        # When MULTI quality_pass cells exist, only grow to *that DNA's* pack
        # symbols. Otherwise a blocked native (already-open INTC) leaves leftover
        # hunt names (IWM/BAC/F) and last_no_setup tunnels leftover overlay.
        if symbol_override is None and (
            (pack_index and watch_sort_key(seat, pack_index)[0] == 0)
            or str(seat.status or "") == "paper_eligible"
        ):
            for extra in hunt:
                if extra in symbols:
                    continue
                if pack_index and not is_pack_grade(
                    candidate_id=seat.candidate_id,
                    seat_id=seat.seat_id,
                    symbol=extra,
                    index=pack_index,
                ):
                    continue
                symbols.append(extra)
        if symbol_override is None:
            symbols = [sym for sym in symbols if sym not in blocked]
            if not symbols:
                continue
        spec = _load_spec_for_seat(seat)
        for symbol in symbols:
            try:
                row, bar_time = _latest_bar(symbol, period=market_period)
            except Exception as exc:  # noqa: BLE001
                last_no_setup = WatchResult(
                    status="NO_SETUP",
                    generated_at=generated,
                    reason=f"market data unavailable for {symbol}: {exc}",
                    living_watchable_count=len(watchable),
                    seat_id=seat.seat_id,
                    candidate_id=seat.candidate_id,
                    symbol=symbol,
                    seats_considered=list(considered),
                )
                continue
            regime = str(row.get("regime") or "unknown")
            decision = _decision_for_seat(seat, row, bar_time, symbol, spec)
            if decision is None:
                structure = _structure_for_seat(seat, row, spec)
                decision_reason = "legacy_structure_only"
            elif isinstance(decision, StandAside):
                structure = None
                decision_reason = decision.reason
            else:
                structure = decision.structure
                decision_reason = decision.reason
                regime = decision.regime or regime

            if structure is None:
                last_no_setup = WatchResult(
                    status="NO_SETUP",
                    generated_at=generated,
                    reason=(
                        f"Living seat {seat.seat_id} on {symbol}: regime={regime} "
                        f"→ stand aside ({decision_reason or 'no structure selected'})."
                    ),
                    living_watchable_count=len(watchable),
                    seat_id=seat.seat_id,
                    candidate_id=seat.candidate_id,
                    symbol=symbol,
                    regime=regime,
                    selected_structure="",
                    seats_considered=list(considered),
                )
                continue

            packet = _paper_packet(
                seat=seat,
                symbol=symbol,
                regime=regime,
                structure=structure,
                row=row,
                bar_time=bar_time,
                spec=spec,
                decision_reason=decision_reason,
            )
            if allow_live_packet:
                # Still not authority — Ken-facing draft only.
                return WatchResult(
                    status="GATED_LIVE_PACKET",
                    generated_at=generated,
                    reason="Paper setup present; live remains gated pending Ken arm + funding + options level.",
                    living_watchable_count=len(watchable),
                    seat_id=seat.seat_id,
                    candidate_id=seat.candidate_id,
                    symbol=symbol,
                    regime=regime,
                    selected_structure=structure,
                    packet={**packet, "packet_type": "gated_live_draft", "live_authority": False},
                    seats_considered=list(considered),
                )
            return WatchResult(
                status="PAPER_PACKET_READY",
                generated_at=generated,
                reason="Watchable living seat and regime/structure filters aligned on latest bar.",
                living_watchable_count=len(watchable),
                seat_id=seat.seat_id,
                candidate_id=seat.candidate_id,
                symbol=symbol,
                regime=regime,
                selected_structure=structure,
                packet=packet,
                seats_considered=list(considered),
            )

    if last_no_setup is not None:
        last_no_setup.seats_considered = considered
        return last_no_setup
    return WatchResult(
        status="NO_SETUP",
        generated_at=generated,
        reason="Watchable seats exist but no symbol/regime produced a setup.",
        living_watchable_count=len(watchable),
        seats_considered=considered,
    )


def write_watch_result(result: WatchResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path

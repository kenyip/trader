"""Patient opportunity watcher for Desk B.

Always safe to run with zero living strategies. Never places orders.
Statuses: NO_QUALIFIED_STRATEGY | NO_SETUP | PAPER_PACKET_READY | GATED_LIVE_PACKET
"""

from __future__ import annotations

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
from trader_platform.research.regime_router_sim import select_structure
from trader_platform.research.strategy_spec import (
    StrategySpec,
    load_strategy_spec,
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


def _latest_bar(symbol: str, period: str = "1y") -> tuple[pd.Series, pd.Timestamp]:
    if build_market_frame is None:
        raise RuntimeError("data.build unavailable")
    # Prefer requested period; fall back to longer history if cache is thin.
    for candidate in (period, "1y", "2y", "5y"):
        frame = build_market_frame(symbol, period=candidate, use_cache=True)
        if frame is not None and len(frame) >= 5:
            ts = pd.Timestamp(str(frame.index[-1]))
            return frame.iloc[-1], ts
    raise ValueError(f"insufficient bars for {symbol}")


def _load_spec_for_seat(seat: LivingSeat) -> StrategySpec | None:
    if not seat.spec_path:
        return None
    path = Path(seat.spec_path)
    if not path.exists():
        return None
    return load_strategy_spec(path)


def _structure_for_seat(seat: LivingSeat, row: pd.Series, spec: StrategySpec | None) -> str | None:
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


def _paper_packet(
    *,
    seat: LivingSeat,
    symbol: str,
    regime: str,
    structure: str,
    row: pd.Series,
    bar_time: pd.Timestamp,
    spec: StrategySpec | None,
) -> dict[str, Any]:
    mgmt = dict(spec.management) if spec is not None else {}
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
        "why_now": (
            f"Living seat {seat.seat_id} is watchable; regime={regime} maps to {structure}; "
            "stand-aside not required on this bar."
        ),
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

    # Prefer paper_eligible, then f2_holdout; stable order by seat_id.
    ordered = sorted(
        watchable,
        key=lambda s: (0 if s.status == "paper_eligible" else 1, s.seat_id),
    )
    considered: list[str] = []
    last_no_setup: WatchResult | None = None

    for seat in ordered:
        considered.append(seat.seat_id)
        symbols = [symbol_override.upper()] if symbol_override else list(seat.symbols)
        if not symbols:
            symbols = ["SPY"]
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
            structure = _structure_for_seat(seat, row, spec)
            if structure is None:
                last_no_setup = WatchResult(
                    status="NO_SETUP",
                    generated_at=generated,
                    reason=(
                        f"Living seat {seat.seat_id} on {symbol}: regime={regime} "
                        "→ stand aside (no structure selected)."
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

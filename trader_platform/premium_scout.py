"""Research loop foundation: regime → strategy → symbol → premium scout (paper-first).

Replaces M0–M1 stub proposals with real short-premium signals from live.make_recommendation
(same pick_entry path as backtest). Default consumer is autonomy_loop paper/shadow modes.

Pipeline stages
--------------
1. REGIME   — features from data.build (regime, iv_rank, high_iv, reversal)
2. STRATEGY — eligible hypotheses from registry (premium sleeve; status testing|paper|shadow|live)
3. SYMBOL   — instruments on each hypothesis, ranked by scout fitness
4. PREMIUM  — live.make_recommendation → OrderIntent or stand-aside
5. PAPER    — caller (autonomy_loop) risk-checks and paper-executes; this module never places live

Stand-aside is success (logged, not a failed scout).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

from trader_platform.hypothesis_registry import Hypothesis, HypothesisRegistry
from trader_platform.risk_governor import OrderIntent

_REPO = Path(__file__).resolve().parents[1]
_SCOUT_AUDIT = _REPO / ".cache" / "platform" / "premium_scout.jsonl"

# Statuses eligible to emit paper/shadow intents (live still gated by autonomy_loop).
ELIGIBLE_STATUSES = frozenset({"testing", "paper", "shadow", "live"})
# Sleeves that produce premium-sale intents via pick_entry.
PREMIUM_SLEEVES = frozenset({"premium"})

RecProvider = Callable[[str], dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def audit_scout(event: str, payload: dict[str, Any]) -> None:
    _SCOUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    line = {"ts": _now(), "event": event, **payload}
    with _SCOUT_AUDIT.open("a") as f:
        f.write(json.dumps(line, default=str) + "\n")


@dataclass
class RegimeSnapshot:
    symbol: str
    regime: str
    iv_rank: float
    high_iv: bool
    reversal: bool
    spot: float
    date: str
    source: str = "live.make_recommendation"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoutCandidate:
    """One stage-4 outcome for (strategy, symbol)."""

    hypothesis_id: str
    hypothesis_name: str
    sleeve: str
    symbol: str
    regime: RegimeSnapshot
    action: str  # STAND_ASIDE | SELL_PUT | SELL_CALL | SKIP
    reason: str
    intent: Optional[OrderIntent] = None
    strike: Optional[float] = None
    expiration: Optional[str] = None
    dte: Optional[int] = None
    estimated_credit: Optional[float] = None
    stage_trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_name": self.hypothesis_name,
            "sleeve": self.sleeve,
            "symbol": self.symbol,
            "regime": self.regime.to_dict() if self.regime else None,
            "action": self.action,
            "reason": self.reason,
            "strike": self.strike,
            "expiration": str(self.expiration) if self.expiration is not None else None,
            "dte": self.dte,
            "estimated_credit": self.estimated_credit,
            "stage_trace": list(self.stage_trace),
        }
        if self.intent is not None:
            d["intent"] = {
                "symbol": self.intent.symbol,
                "side": self.intent.side,
                "qty": self.intent.qty,
                "order_type": self.intent.order_type,
                "limit_price": self.intent.limit_price,
                "strategy_id": self.intent.strategy_id,
                "tag": self.intent.tag,
                "notional": self.intent.estimated_notional(),
            }
        return d


def default_rec_provider(ticker: str) -> dict[str, Any]:
    """Live short-premium recommendation (same path as just test / live.py)."""
    from live import make_recommendation

    return make_recommendation(ticker)


def _regime_from_rec(symbol: str, rec: dict[str, Any]) -> RegimeSnapshot:
    feats = rec.get("features") or {}
    date = rec.get("date")
    return RegimeSnapshot(
        symbol=symbol.upper(),
        regime=str(feats.get("regime") or "unknown"),
        iv_rank=float(feats.get("iv_rank") or 0.0),
        high_iv=bool(feats.get("high_iv")),
        reversal=bool(feats.get("reversal")),
        spot=float(rec.get("spot") or 0.0),
        date=str(date) if date is not None else "",
    )


def select_strategies(
    registry: HypothesisRegistry,
    *,
    statuses: Iterable[str] = ELIGIBLE_STATUSES,
    sleeves: Iterable[str] = PREMIUM_SLEEVES,
) -> list[Hypothesis]:
    """Stage 2 — strategy selection from hypothesis registry."""
    status_set = set(statuses)
    sleeve_set = set(sleeves)
    registry.ensure_seeded()
    out: list[Hypothesis] = []
    for h in registry.list():
        if h.status not in status_set:
            continue
        if h.sleeve not in sleeve_set:
            continue
        if not h.instruments:
            continue
        # Prefer entry refs that map to pick_entry / short-premium; skip pure PMCC for v1 scout.
        ref = (h.entry_logic_ref or "").lower()
        if "pmcc" in ref and "pick_entry" not in ref:
            continue
        out.append(h)
    return out


def select_symbols(hyp: Hypothesis, *, only: Optional[Sequence[str]] = None) -> list[str]:
    """Stage 3 — symbols for a strategy."""
    symbols = [s.upper() for s in (hyp.instruments or [])]
    if only:
        allow = {s.upper() for s in only}
        symbols = [s for s in symbols if s in allow]
    return symbols


def rec_to_intent(
    rec: dict[str, Any],
    *,
    hypothesis_id: str,
    qty: float = 1.0,
    event: str = "premium_scout",
) -> tuple[str, str, Optional[OrderIntent], dict[str, Any]]:
    """Map a live recommendation dict → (action, reason, intent|None, meta)."""
    action = str(rec.get("action") or "STAND_ASIDE")
    symbol = str(rec.get("ticker") or "").upper()
    meta: dict[str, Any] = {
        "strike": rec.get("strike"),
        "expiration": rec.get("expiration"),
        "dte": rec.get("dte"),
        "estimated_credit": rec.get("estimated_credit"),
        "regime_at_entry": rec.get("regime_at_entry")
        or (rec.get("features") or {}).get("regime"),
    }

    if action == "STAND_ASIDE":
        return action, str(rec.get("reason") or "stand_aside"), None, meta

    if not action.startswith("SELL_"):
        return "SKIP", f"unsupported action {action}", None, meta

    credit = rec.get("estimated_credit")
    if credit is None or float(credit) <= 0:
        return "SKIP", "missing or non-positive estimated_credit", None, meta

    # Limit at model credit (paper-first). Real fill would improve/worsen vs live chain.
    limit_price = round(float(credit), 2)
    option_side = "put" if action == "SELL_PUT" else "call"
    tag = (
        f"scout:{event}|{option_side}|K={meta.get('strike')}|dte={meta.get('dte')}"
        f"|exp={meta.get('expiration')}"
    )
    intent = OrderIntent(
        symbol=symbol,
        side="sell",
        qty=qty,
        order_type="limit",
        limit_price=limit_price,
        strategy_id=hypothesis_id,
        multiplier=100.0,
        tag=tag,
    )
    reason = (
        f"{action} {symbol} K={meta.get('strike')} "
        f"dte={meta.get('dte')} credit≈${limit_price:.2f} "
        f"regime={meta.get('regime_at_entry')}"
    )
    return action, reason, intent, meta


def scout_symbol(
    hyp: Hypothesis,
    symbol: str,
    *,
    rec_provider: RecProvider = default_rec_provider,
    qty: float = 1.0,
    event: str = "premium_scout",
) -> ScoutCandidate:
    """Stages 1+4 for one (hypothesis, symbol)."""
    trace = [
        f"strategy:{hyp.id}:{hyp.sleeve}:{hyp.status}",
        f"symbol:{symbol.upper()}",
    ]
    try:
        rec = rec_provider(symbol.upper())
    except Exception as exc:  # noqa: BLE001 — scout must not crash the tick
        audit_scout(
            "scout_error",
            {"hypothesis_id": hyp.id, "symbol": symbol, "error": str(exc)},
        )
        empty_regime = RegimeSnapshot(
            symbol=symbol.upper(),
            regime="error",
            iv_rank=0.0,
            high_iv=False,
            reversal=False,
            spot=0.0,
            date="",
            source="error",
        )
        return ScoutCandidate(
            hypothesis_id=hyp.id,
            hypothesis_name=hyp.name,
            sleeve=hyp.sleeve,
            symbol=symbol.upper(),
            regime=empty_regime,
            action="SKIP",
            reason=f"rec_provider error: {exc}",
            stage_trace=trace + [f"error:{exc}"],
        )

    regime = _regime_from_rec(symbol, rec)
    trace.append(f"regime:{regime.regime}:ivr={regime.iv_rank:.1f}")
    action, reason, intent, meta = rec_to_intent(
        rec, hypothesis_id=hyp.id, qty=qty, event=event
    )
    trace.append(f"premium:{action}")
    return ScoutCandidate(
        hypothesis_id=hyp.id,
        hypothesis_name=hyp.name,
        sleeve=hyp.sleeve,
        symbol=symbol.upper(),
        regime=regime,
        action=action,
        reason=reason,
        intent=intent,
        strike=meta.get("strike"),
        expiration=str(meta["expiration"]) if meta.get("expiration") is not None else None,
        dte=int(meta["dte"]) if meta.get("dte") is not None else None,
        estimated_credit=float(meta["estimated_credit"])
        if meta.get("estimated_credit") is not None
        else None,
        stage_trace=trace,
    )


@dataclass
class ScoutReport:
    event: str
    candidates: list[ScoutCandidate]
    intents: list[OrderIntent]
    stand_asides: list[ScoutCandidate]
    skipped: list[ScoutCandidate]
    audit_path: str = str(_SCOUT_AUDIT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "n_candidates": len(self.candidates),
            "n_intents": len(self.intents),
            "n_stand_asides": len(self.stand_asides),
            "n_skipped": len(self.skipped),
            "candidates": [c.to_dict() for c in self.candidates],
            "audit_path": self.audit_path,
        }


def run_premium_scout(
    *,
    registry: Optional[HypothesisRegistry] = None,
    symbols: Optional[Sequence[str]] = None,
    rec_provider: RecProvider = default_rec_provider,
    qty: float = 1.0,
    event: str = "premium_scout",
    max_intents: int = 3,
    audit: bool = True,
) -> ScoutReport:
    """Full pipeline: regime → strategy → symbol → premium → intent list.

    max_intents caps paper proposals per tick (risk + ops hygiene).
    """
    reg = registry or HypothesisRegistry()
    strategies = select_strategies(reg)
    candidates: list[ScoutCandidate] = []

    for hyp in strategies:
        for sym in select_symbols(hyp, only=symbols):
            cand = scout_symbol(
                hyp, sym, rec_provider=rec_provider, qty=qty, event=event
            )
            candidates.append(cand)

    intents: list[OrderIntent] = []
    stand_asides: list[ScoutCandidate] = []
    skipped: list[ScoutCandidate] = []
    for c in candidates:
        if c.intent is not None and c.action.startswith("SELL_"):
            if len(intents) < max_intents:
                intents.append(c.intent)
            else:
                c.action = "SKIP"
                c.reason = f"max_intents={max_intents} reached; {c.reason}"
                c.intent = None
                skipped.append(c)
                continue
        elif c.action == "STAND_ASIDE":
            stand_asides.append(c)
        else:
            skipped.append(c)

    report = ScoutReport(
        event=event,
        candidates=candidates,
        intents=intents,
        stand_asides=stand_asides,
        skipped=skipped,
    )
    if audit:
        audit_scout(
            "scout_complete",
            {
                "event": event,
                "n_candidates": len(candidates),
                "n_intents": len(intents),
                "n_stand_asides": len(stand_asides),
                "n_skipped": len(skipped),
                "strategies": [h.id for h in strategies],
                "actions": [c.action for c in candidates],
            },
        )
    return report


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Premium scout: regime→strategy→symbol→premium (paper-first intents)"
    )
    p.add_argument("--event", default="manual_scout")
    p.add_argument("--symbols", nargs="*", default=None, help="Limit to these underlyings")
    p.add_argument("--qty", type=float, default=1.0)
    p.add_argument("--max-intents", type=int, default=3)
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--stub",
        action="store_true",
        help="Use offline stub recs (no network / no live.py) for CI smoke",
    )
    args = p.parse_args(argv)

    if args.stub:
        def _stub(ticker: str) -> dict[str, Any]:
            # Deterministic offline rec for smoke: TSLA sell put, TSLL stand aside.
            t = ticker.upper()
            if t == "TSLA":
                return {
                    "ticker": "TSLA",
                    "date": "2026-07-09",
                    "spot": 250.0,
                    "action": "SELL_PUT",
                    "strike": 230.0,
                    "expiration": "2026-07-25",
                    "dte": 16,
                    "estimated_credit": 1.85,
                    "features": {
                        "regime": "bullish",
                        "iv_rank": 55.0,
                        "high_iv": False,
                        "reversal": False,
                    },
                    "regime_at_entry": "bullish",
                }
            return {
                "ticker": t,
                "date": "2026-07-09",
                "spot": 20.0,
                "action": "STAND_ASIDE",
                "reason": "stub: iv_rank below floor",
                "features": {
                    "regime": "neutral",
                    "iv_rank": 10.0,
                    "high_iv": False,
                    "reversal": False,
                },
            }

        report = run_premium_scout(
            symbols=args.symbols,
            rec_provider=_stub,
            qty=args.qty,
            event=args.event,
            max_intents=args.max_intents,
        )
    else:
        report = run_premium_scout(
            symbols=args.symbols,
            qty=args.qty,
            event=args.event,
            max_intents=args.max_intents,
        )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(
            f"scout event={report.event} candidates={len(report.candidates)} "
            f"intents={len(report.intents)} stand_asides={len(report.stand_asides)} "
            f"skipped={len(report.skipped)}"
        )
        for c in report.candidates:
            print(
                f"  [{c.action}] {c.symbol} hyp={c.hypothesis_id} "
                f"regime={c.regime.regime} — {c.reason}"
            )
            if c.stage_trace:
                print(f"    trace: {' → '.join(c.stage_trace)}")
        print(f"audit: {report.audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

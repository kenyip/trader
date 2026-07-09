"""Focused smoke for M0–M1 platform foundation. Run: just platform-smoke"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure repo root on path when run as script
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.execution.broker_adapter import (
    LiveOrdersBlocked,
    NotConnected,
    PaperBroker,
    PaperRhBridge,
    RhMcpReadAdapter,
    RobinhoodMcpBroker,
    build_review_option_order,
    get_broker,
)
from trader_platform.rh_snapshot import (
    AccountView,
    RhSnapshot,
    recommend_risk_limits,
    save_snapshot,
    try_load_snapshot,
)
from trader_platform.hypothesis_registry import HypothesisRegistry
from trader_platform.promotion_gates import evaluate_promotion
from trader_platform.risk_governor import OrderIntent, PortfolioSnapshot, RiskGovernor, load_limits
from trader_platform.autonomy_loop import run_tick


def main() -> int:
    errors: list[str] = []

    # Registry
    with tempfile.TemporaryDirectory() as td:
        reg_path = Path(td) / "hypotheses.yaml"
        reg = HypothesisRegistry(reg_path)
        reg.ensure_seeded()
        hyps = reg.list()
        assert len(hyps) == 4, hyps
        h = reg.get("hyp_short_premium_tsla")
        assert h.status == "testing"
        bare = reg.add(
            name="no-evidence",
            thesis="should not go live",
            sleeve="tactical",
            instruments=["TSLA"],
            status="shadow",
            hypothesis_id="hyp_no_evidence_test",
        )
        try:
            reg.transition(
                bare.id,
                "live",
                force=True,
                allow_live_without_evidence=False,
            )
            errors.append("expected live without evidence to fail")
        except ValueError:
            pass

        report = evaluate_promotion(h, "live")
        assert not report.allowed, "live must not auto-pass with incomplete gates"
        assert report.blockers

    # Risk governor
    gov = RiskGovernor()
    ok = gov.check(
        OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.5)
    )
    assert ok.allowed, ok.reasons

    deny = gov.check(
        OrderIntent(symbol="TSLA", side="sell", qty=99, order_type="limit", limit_price=50.0)
    )
    assert not deny.allowed

    deny_mkt = gov.check(
        OrderIntent(symbol="TSLA", side="buy", qty=1, order_type="market")
    )
    assert not deny_mkt.allowed

    deny_live = gov.check(
        OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.0),
        mode="agentic_live",
    )
    assert not deny_live.allowed  # agentic.enabled false

    # Kill switch
    with tempfile.TemporaryDirectory() as td:
        kill = Path(td) / "agentic_kill.switch"
        kill.write_text("stop\n")
        limits = load_limits()
        limits = dict(limits)
        limits["kill_switch_file"] = str(kill)
        gov2 = RiskGovernor(limits=limits, repo_root=Path(td))
        d = gov2.check(
            OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.0)
        )
        assert not d.allowed and any("kill switch" in r for r in d.reasons)

    # Paper broker lifecycle
    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "ledger.json"
        br = PaperBroker(ledger)
        place = br.place_limit(
            OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.25)
        )
        assert place.ok and place.order
        oid = place.order.order_id
        rep = br.replace_limit(oid, limit_price=1.10)
        assert rep.ok and rep.order and rep.order.limit_price == 1.10
        assert len(br.list_open_orders()) == 1
        can = br.cancel(oid)
        assert can.ok and can.order and can.order.status == "canceled"
        assert br.list_open_orders() == []

    # RH stub: place blocked without agentic_live+enabled+connected
    rh = RobinhoodMcpBroker(connected=False, mode="paper")
    try:
        rh.place_limit(
            OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.0)
        )
        errors.append("RH stub should raise NotConnected")
    except NotConnected:
        pass

    # Even with connected+agentic_live, agentic_enabled false → NotConnected
    rh2 = RobinhoodMcpBroker(connected=True, mode="agentic_live", agentic_enabled=False)
    try:
        rh2.place_limit(
            OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.0)
        )
        errors.append("RH stub should raise NotConnected when agentic_enabled false")
    except NotConnected:
        pass

    # review_* payload builders (no MCP invoke)
    intent = OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.25)
    payload = build_review_option_order(intent)
    assert payload.tool == "review_option_order" and payload.as_dict()["places"] is False
    reader = RhMcpReadAdapter()
    reviewed = reader.review_option_order(intent)
    assert reviewed.get("invoked") is False and reviewed.get("places") is False

    # Autonomy paper tick (stub proposals: offline, no live.py)
    summary = run_tick(mode="paper", event="smoke_test", stub_proposals=True)
    assert summary.get("ok") is True
    assert summary.get("mode") == "paper"
    assert summary.get("stub_proposals") is True

    # shadow attaches rh_review payloads without place
    shadow = run_tick(mode="shadow", event="smoke_test", stub_proposals=True)
    assert shadow.get("ok") is True
    if shadow.get("results"):
        assert "rh_review" in shadow["results"][0]
        assert shadow["results"][0]["rh_review"].get("places") is False

    # dry-review builds payloads, no paper mutate
    dry = run_tick(mode="paper", event="smoke_test", dry_review=True, stub_proposals=True)
    assert dry.get("ok") is True
    if dry.get("results"):
        assert dry["results"][0].get("action") == "dry_review"
        assert dry["results"][0]["rh_review"].get("places") is False

    # M2 premium scout offline (injectable rec provider)
    from trader_platform.premium_scout import run_premium_scout

    def _stub_rec(ticker: str) -> dict:
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
            "reason": "stub stand_aside",
            "features": {
                "regime": "neutral",
                "iv_rank": 10.0,
                "high_iv": False,
                "reversal": False,
            },
        }

    scout = run_premium_scout(
        rec_provider=_stub_rec, event="smoke_scout", max_intents=2, audit=False
    )
    assert any(c.action == "SELL_PUT" for c in scout.candidates)
    assert any(c.action == "STAND_ASIDE" for c in scout.candidates)
    assert len(scout.intents) >= 1
    assert scout.intents[0].limit_price == 1.85
    assert "scout:" in (scout.intents[0].tag or "")


    # Stage2: PaperRhBridge + snapshot readiness
    with tempfile.TemporaryDirectory() as td:
        snap_path = Path(td) / "snap.json"
        snap = RhSnapshot(
            fetched_at="2026-07-09T00:00:00+00:00",
            data_quality="after_hours",
            accounts=[
                AccountView(
                    account_number_masked="••••8507",
                    nickname="Agentic",
                    account_type="cash",
                    agentic_allowed=True,
                    option_level="",
                    total_value=0.0,
                )
            ],
        )
        save_snapshot(snap, snap_path)
        bridge = PaperRhBridge(ledger_path=Path(td) / "ledger.json", snapshot_path=snap_path)
        assert bridge.name == "paper_rh_bridge"
        assert bridge.has_readonly_snapshot()
        ready = bridge.get_rh_snapshot().readiness()
        assert not ready.ok
        assert any("capital" in b or "$0" in b or "options" in b for b in ready.blockers)
        place = bridge.place_limit(
            OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.0)
        )
        assert place.ok
        # live place still blocked
        rh_live = RobinhoodMcpBroker(
            connected=True, mode="agentic_live", agentic_enabled=True, snapshot_path=snap_path
        )
        try:
            rh_live.place_limit(
                OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.0)
            )
            errors.append("expected LiveOrdersBlocked on live place")
        except (LiveOrdersBlocked, NotImplementedError):
            pass
        rec0 = recommend_risk_limits(0)
        assert rec0["status"] == "unfunded"
        rec5 = recommend_risk_limits(5000)
        assert rec5["status"] == "funded"
        # get_broker paper uses bridge by default
        br = get_broker("paper", snapshot_path=snap_path)
        assert br.name == "paper_rh_bridge"

    # default snapshot (if present) loads
    _ = try_load_snapshot()

    # agentic_live blocked (not connected and/or agentic.enabled false)
    blocked = run_tick(mode="agentic_live", event="smoke_test", rh_connected=False)
    assert blocked.get("ok") is False

    if errors:
        print("FAIL:", errors)
        return 1
    print("platform smoke OK")
    print(f"  registry seeds: 4")
    print(f"  paper tick results: {len(summary.get('results') or [])}")
    print(f"  shadow rh_review: {bool((shadow.get('results') or [{}])[0].get('rh_review'))}")
    print(f"  dry_review action: {(dry.get('results') or [{}])[0].get('action')}")
    print(f"  premium_scout intents: {len(scout.intents)} stand_asides={len(scout.stand_asides)}")
    print(f"  agentic_live blocked: {blocked.get('error')}")
    print(f"  stage2 bridge + readiness checks OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

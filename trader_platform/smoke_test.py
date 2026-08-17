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
        OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=0.80)
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
        # live place still blocked without mcp_call
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


    # Multi-leg PCS: risk uses max_loss; paper ledger stores legs + tag
    pcs_intent = OrderIntent(
        symbol="TSLL",
        side="sell",
        qty=1,
        order_type="limit",
        limit_price=0.25,
        strategy_id="hyp_dna_tsll_put_credit_spread_b195f5fe",
        multiplier=100.0,
        tag="scout:smoke|pcs|w=1.0|Ks=18.0|Kl=17.0|dte=21|ml=75.0",
        structure="put_credit_spread",
        legs=[
            {"action": "sell", "right": "put", "strike": 18.0, "qty": 1, "position_effect": "open"},
            {"action": "buy", "right": "put", "strike": 17.0, "qty": 1, "position_effect": "open"},
        ],
        max_loss_usd=75.0,
        width=1.0,
        net_credit=0.25,
        short_strike=18.0,
        long_strike=17.0,
        expiration="2026-07-30",
        dte=21,
    )
    assert abs(pcs_intent.risk_amount() - 75.0) < 1e-6
    assert abs(pcs_intent.estimated_notional() - 25.0) < 1e-6  # 0.25 * 100
    d_pcs = RiskGovernor().check(pcs_intent, portfolio=PortfolioSnapshot(open_risk=0.0))
    assert d_pcs.allowed, d_pcs.reasons
    assert any("defined_risk" in r for r in d_pcs.reasons)
    # open_risk + max_loss > 750 denies
    d_pcs2 = RiskGovernor().check(
        pcs_intent, portfolio=PortfolioSnapshot(open_risk=700.0)
    )
    assert not d_pcs2.allowed and any("open_risk" in r for r in d_pcs2.reasons)

    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "pcs_ledger.json"
        br = PaperBroker(ledger)
        place = br.place_limit(pcs_intent)
        assert place.ok and place.order
        assert place.order.structure == "put_credit_spread"
        assert place.order.max_loss_usd == 75.0
        assert place.order.legs and len(place.order.legs) == 2
        assert "pcs" in (place.order.tag or "")
        port = br.portfolio_snapshot()
        assert abs(port.open_risk - 75.0) < 1e-6
        assert port.open_order_count == 1

    # Offline PCS rec → OPEN_PCS intent via rec_to_intent
    from trader_platform.premium_scout import rec_to_intent

    pcs_rec = {
        "ticker": "TSLL",
        "action": "OPEN_PCS",
        "estimated_credit": 0.28,
        "max_loss_usd": 72.0,
        "width": 1.0,
        "short_strike": 18.5,
        "long_strike": 17.5,
        "expiration": "2026-07-30",
        "dte": 21,
        "legs": [
            {"action": "sell", "right": "put", "strike": 18.5, "qty": 1},
            {"action": "buy", "right": "put", "strike": 17.5, "qty": 1},
        ],
        "structure": "put_credit_spread",
        "features": {"regime": "bullish", "iv_rank": 80.0},
    }
    act, reason, intent, meta = rec_to_intent(
        pcs_rec, hypothesis_id="hyp_dna_tsll_put_credit_spread_b195f5fe", event="smoke_pcs"
    )
    assert act == "OPEN_PCS" and intent is not None
    assert intent.max_loss_usd == 72.0
    assert intent.structure == "put_credit_spread"
    assert intent.legs and len(intent.legs) == 2
    assert intent.risk_amount() == 72.0

    # Evolve ship bar (offline) — thin perfect / inf PF must not rank or SHIP
    from trader_platform.evolve_tick import assert_ship_bar

    assert_ship_bar()

    # Calendar scaffold: real event loop on synthetic daily bars, defined debit risk.
    import numpy as np
    import pandas as pd

    from trader_platform.research.calendar_sim import run_calendar_backtest

    calendar_df = pd.DataFrame(
        {
            "close": np.linspace(20.0, 21.5, 45),
            "iv_proxy": np.full(45, 0.65),
            "iv_rank": np.full(45, 70.0),
            "regime": ["neutral"] * 45,
        },
        index=pd.bdate_range("2026-01-02", periods=45),
    )
    calendar = run_calendar_backtest(
        "TEST",
        period="smoke",
        df=calendar_df,
        config={
            "short_dte": 7,
            "long_dte": 21,
            "long_target_delta": 0.30,
            "profit_target": 0.30,
            "defined_loss_exit_frac": 0.65,
            "max_loss_budget_usd": 300.0,
            "front_iv_multiplier": 1.05,
            "back_iv_multiplier": 0.95,
            "put_skew_per_moneyness": 0.25,
        },
    )
    assert calendar.ok and calendar.n_trades > 0, calendar.reason
    assert calendar.capital["structure"] == "calendar_spread"
    assert 0 < calendar.capital["max_loss_usd"] <= 300.0
    assert calendar.trades[0].front_iv_at_entry > calendar.trades[0].back_iv_at_entry

    from trader_platform.research.diagonal_sim import run_diagonal_backtest

    diagonal_df = calendar_df.copy()
    diagonal_df["regime"] = "neutral"
    diagonal = run_diagonal_backtest(
        "TEST",
        period="smoke",
        df=diagonal_df,
        config={
            "diagonal_short_dte": 7,
            "diagonal_long_dte": 45,
            "diagonal_short_delta": 0.25,
            "diagonal_long_delta": 0.70,
            "profit_target": 0.30,
            "defined_loss_exit_frac": 0.65,
            "dte_stop": 0,
            "max_loss_budget_usd": 300.0,
            "front_iv_multiplier": 1.05,
            "back_iv_multiplier": 0.95,
        },
    )
    assert diagonal.ok and diagonal.n_trades > 0, diagonal.reason
    assert diagonal.capital["structure"] == "diagonal_spread"
    assert 0 < diagonal.capital["max_loss_usd"] <= 300.0
    assert diagonal.trades[0].long_strike < diagonal.trades[0].short_strike

    from trader_platform.research.butterfly_sim import run_butterfly_backtest

    butterfly = run_butterfly_backtest(
        "TEST",
        period="smoke",
        df=calendar_df,
        config={
            "long_dte": 14,
            "long_target_delta": 0.35,
            "spread_width": 1.0,
            "profit_target": 0.40,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
        },
    )
    assert butterfly.ok and butterfly.n_trades > 0, butterfly.reason
    assert butterfly.capital["structure"] == "butterfly_spread"
    assert 0 < butterfly.capital["max_loss_usd"] <= 300.0
    first_bfly = butterfly.trades[0]
    assert first_bfly.lower_strike < first_bfly.middle_strike < first_bfly.upper_strike

    from trader_platform.research.iron_butterfly_sim import run_iron_butterfly_backtest

    iron_butterfly = run_iron_butterfly_backtest(
        "TEST",
        period="smoke",
        df=calendar_df,
        config={
            "long_dte": 21,
            "spread_width": 2.0,
            "min_credit_pct": 0.25,
            "iv_rank_min": 20.0,
            "profit_target": 0.40,
            "defined_loss_exit_frac": 0.70,
            "dte_stop": 3,
            "max_loss_budget_usd": 300.0,
        },
    )
    assert iron_butterfly.ok and iron_butterfly.n_trades > 0, iron_butterfly.reason
    assert iron_butterfly.capital["structure"] == "iron_butterfly"
    assert 0 < iron_butterfly.capital["max_loss_usd"] <= 300.0
    first_iron_bfly = iron_butterfly.trades[0]
    assert first_iron_bfly.lower_strike < first_iron_bfly.middle_strike < first_iron_bfly.upper_strike
    assert first_iron_bfly.entry_credit > 0

    from trader_platform.research.debit_vertical_sim import run_debit_vertical_backtest

    debit_vertical = run_debit_vertical_backtest(
        "TEST",
        structure="bull_call_debit_spread",
        period="smoke",
        df=calendar_df.assign(regime="bullish"),
        config={
            "long_dte": 21,
            "debit_long_delta": 0.55,
            "spread_width": 2.0,
            "max_loss_budget_usd": 300.0,
        },
    )
    assert debit_vertical.ok and debit_vertical.n_trades > 0, debit_vertical.reason
    assert debit_vertical.capital["structure"] == "bull_call_debit_spread"
    assert 0 < debit_vertical.capital["max_loss_usd"] <= 300.0
    assert debit_vertical.trades[0].long_strike < debit_vertical.trades[0].short_strike

    # --- P0 capital-fit + smoke-stub filters ---
    from trader_platform.learn_tick import _paper_stats_for_hyp
    from trader_platform.paper_filters import is_smoke_stub_order, is_smoke_stub_tag

    assert is_smoke_stub_tag("m0_stub:smoke_test")
    assert is_smoke_stub_order({"tag": "m0_stub:smoke_test", "strategy_id": "hyp_x"})
    assert not is_smoke_stub_tag("scout:rth|call|K=12.5")

    smoke_ledger = {
        "orders": {
            "a": {
                "order_id": "a",
                "strategy_id": "hyp_short_premium_tsla",
                "status": "working",
                "tag": "m0_stub:smoke_test",
            },
            "b": {
                "order_id": "b",
                "strategy_id": "hyp_short_premium_tsla",
                "status": "working",
                "tag": "m0_stub:smoke_test",
            },
            "c": {
                "order_id": "c",
                "strategy_id": "hyp_short_premium_tsla",
                "status": "working",
                "tag": "scout:real|put|K=200",
            },
        }
    }
    stats = _paper_stats_for_hyp(smoke_ledger, "hyp_short_premium_tsla")
    assert stats["orders"] == 1 and stats["working"] == 1, stats

    # Naked TSLL short call: notional-allowed size must still capital_reject
    naked_tsll = OrderIntent(
        symbol="TSLL",
        side="sell",
        qty=1,
        order_type="limit",
        limit_price=0.49,
        strategy_id="hyp_dna_tsll_short",
        structure="naked_short_call",
        option_right="call",
        max_loss_usd=None,
        tag="scout:test|call|K=12.5",
    )
    cap_deny = gov.check(naked_tsll, mode="paper")
    assert not cap_deny.allowed, cap_deny.reasons
    assert any("capital_reject" in r for r in cap_deny.reasons), cap_deny.reasons

    # Defined-risk TSLL with max_loss_usd clears capital-fit (subject to open_risk caps)
    pcs_tsll = OrderIntent(
        symbol="TSLL",
        side="sell",
        qty=1,
        order_type="limit",
        limit_price=0.25,
        strategy_id="hyp_dna_tsll_pcs",
        structure="put_credit_spread",
        defined_risk=True,
        option_right="put",
        max_loss_usd=76.0,
        tag="scout:test|pcs|width=1",
    )
    cap_ok = gov.check(pcs_tsll, mode="paper")
    assert cap_ok.allowed, cap_ok.reasons
    assert pcs_tsll.risk_amount() == 76.0
    # open_risk accounting prefers max_loss over tiny premium notional
    tight = PortfolioSnapshot(open_risk=700.0)
    over = gov.check(pcs_tsll, portfolio=tight, mode="paper")
    assert not over.allowed
    assert any("open_risk" in r for r in over.reasons), over.reasons

    if errors:
        print("FAIL:", errors)
        return 1
    print("platform smoke OK")
    print(f"  registry seeds: 4")
    print(f"  paper tick results: {len(summary.get('results') or [])}")
    print(f"  shadow rh_review: {bool((shadow.get('results') or [{}])[0].get('rh_review'))}")
    print(f"  dry_review action: {(dry.get('results') or [{}])[0].get('action')}")
    print(f"  premium_scout intents: {len(scout.intents)} stand_asides={len(scout.stand_asides)}")
    print(f"  PCS multi-leg risk/ledger/intent path OK (max_loss open_risk)")
    print(f"  agentic_live blocked: {blocked.get('error')}")
    print(f"  stage2 bridge + readiness checks OK")
    print("  evolve ship bar asserts OK")
    print("  calendar sim synthetic smoke OK (defined debit risk)")
    print("  diagonal sim synthetic smoke OK (defined debit risk)")
    print("  capital-fit: naked TSLL short denied; PCS max_loss_usd open_risk OK")
    print("  learn_tick: smoke stubs excluded from paper_orders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

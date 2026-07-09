"""Focused smoke for M0–M1 platform foundation. Run: just platform-smoke"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure repo root on path when run as script
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from platform.execution.broker_adapter import NotConnected, PaperBroker, RobinhoodMcpBroker
from platform.hypothesis_registry import HypothesisRegistry
from platform.promotion_gates import evaluate_promotion
from platform.risk_governor import OrderIntent, PortfolioSnapshot, RiskGovernor, load_limits
from platform.autonomy_loop import run_tick


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

    # RH stub
    rh = RobinhoodMcpBroker(connected=False, mode="paper")
    try:
        rh.place_limit(
            OrderIntent(symbol="TSLA", side="sell", qty=1, order_type="limit", limit_price=1.0)
        )
        errors.append("RH stub should raise NotConnected")
    except NotConnected:
        pass

    # Autonomy paper tick
    summary = run_tick(mode="paper", event="smoke_test")
    assert summary.get("ok") is True
    assert summary.get("mode") == "paper"

    # agentic_live blocked
    blocked = run_tick(mode="agentic_live", event="smoke_test", rh_connected=False)
    assert blocked.get("ok") is False

    if errors:
        print("FAIL:", errors)
        return 1
    print("platform smoke OK")
    print(f"  registry seeds: 4")
    print(f"  paper tick results: {len(summary.get('results') or [])}")
    print(f"  agentic_live blocked: {blocked.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

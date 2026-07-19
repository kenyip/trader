"""RiskGovernor deny matrix — engine safety contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trader_platform.risk_governor import OrderIntent, PortfolioSnapshot, RiskGovernor


def _pcs_intent(**overrides) -> OrderIntent:
    base = dict(
        symbol="BAC",
        side="sell",
        qty=1,
        order_type="limit",
        limit_price=0.45,
        max_loss_usd=180.0,
        structure="put_credit_spread",
        defined_risk=True,
        strategy_id="test_pcs",
    )
    base.update(overrides)
    return OrderIntent(**base)


class RiskGovernorMatrixTest(unittest.TestCase):
    def setUp(self):
        # Minimal limits without reading production kill switch path noise
        self.limits = {
            "kill_switch_file": "agentic_kill.switch",
            "order": {
                "allowed_sides": ["buy", "sell"],
                "allowed_order_types": ["limit"],
                "allow_market": False,
                "max_contracts_per_order": 2,
                "max_notional_per_order": 500,
            },
            "portfolio": {
                "max_open_risk": 750,
                "max_open_orders": 3,
                "max_daily_loss": 300,
            },
            "agentic": {"enabled": False},
            "capital_fit": {
                "enabled": True,
                "levered_underlyings": ["TSLL"],
                "reject_undefined_risk_on_levered": True,
            },
        }

    def _gov(self, tmp: str) -> RiskGovernor:
        return RiskGovernor(limits=self.limits, repo_root=Path(tmp))

    def test_allows_defined_risk_paper_pcs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._gov(tmp).check(_pcs_intent(), mode="paper")
            self.assertTrue(d.allowed, d.reasons)

    def test_denies_live_when_agentic_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._gov(tmp).check(_pcs_intent(), mode="agentic_live")
            self.assertFalse(d.allowed)
            self.assertTrue(any("agentic.enabled" in r for r in d.reasons))

    def test_denies_kill_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            kill = Path(tmp) / "agentic_kill.switch"
            kill.write_text("stop\n")
            d = self._gov(tmp).check(_pcs_intent(), mode="paper")
            self.assertFalse(d.allowed)
            self.assertTrue(any("kill switch" in r for r in d.reasons))

    def test_denies_undefined_risk_levered(self):
        with tempfile.TemporaryDirectory() as tmp:
            intent = _pcs_intent(
                symbol="TSLL",
                max_loss_usd=None,
                defined_risk=False,
                structure="naked_short_put",
            )
            d = self._gov(tmp).check(intent, mode="paper")
            self.assertFalse(d.allowed)
            self.assertTrue(any("capital_reject" in r for r in d.reasons))

    def test_denies_oversize_max_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._gov(tmp).check(_pcs_intent(max_loss_usd=900.0), mode="paper")
            self.assertFalse(d.allowed)

    def test_denies_open_risk_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = PortfolioSnapshot(open_risk=700.0)
            d = self._gov(tmp).check(_pcs_intent(max_loss_usd=180.0), portfolio=port, mode="paper")
            self.assertFalse(d.allowed)
            self.assertTrue(any("open_risk" in r for r in d.reasons))


if __name__ == "__main__":
    unittest.main()

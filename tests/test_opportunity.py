"""Engine contracts for thesis → opportunity emitter (not strategy doctrine).

Tests use *synthetic* fixture theses. Catalog theses under configs/theses/ are
data for prove/bootstrap and must not be frozen as eternal edge by assertions.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from trader_platform.research.opportunity import (
    Opportunity,
    StandAside,
    evaluate_from_row,
    evaluate_opportunity,
    load_thesis,
    plan_structures,
    strategy_spec_from_thesis,
    thesis_from_mapping,
    thesis_from_strategy_spec,
)
from trader_platform.research.opportunity_watcher import watch_once
from trader_platform.research.living_registry import LivingRegistry, LivingSeat, save_living_registry
from trader_platform.research.signals import SignalSnapshot, load_signal_catalog
from trader_platform.research.strategy_spec import load_strategy_spec


def _fixture_thesis(**overrides):
    base = {
        "thesis_id": "test_only_bull_pcs",
        "router_policy": "pcs_non_bear",
        "signal_bounds": {},
        "entry": {},
        "management": {
            "long_dte": 21,
            "profit_target": 0.5,
            "max_loss_budget_usd": 300.0,
        },
    }
    base.update(overrides)
    return thesis_from_mapping(base)


def _snap(regime="bullish", iv_rank=40.0, ema_stack=0.5, **extra):
    values = {
        "regime": regime,
        "iv_rank": iv_rank,
        "ema_stack": ema_stack,
        "close": 100.0,
        **extra,
    }
    return SignalSnapshot(symbol="TEST", asof="2024-06-01", values=values)


class OpportunityEmitterContractTest(unittest.TestCase):
    def test_config_drives_stand_aside_on_regime_allow(self):
        thesis = _fixture_thesis(regime_allow=("bullish",))
        decision = evaluate_opportunity(thesis, _snap(regime="bearish"))
        self.assertIsInstance(decision, StandAside)
        self.assertIn("regime_not_allowed", decision.reason)

    def test_config_drives_opportunity_when_rules_pass(self):
        thesis = _fixture_thesis(regime_allow=("bullish", "neutral"))
        decision = evaluate_opportunity(thesis, _snap(regime="bullish"))
        self.assertIsInstance(decision, Opportunity)
        self.assertEqual(decision.structure, "put_credit_spread")

    def test_signal_bounds_from_config(self):
        thesis = _fixture_thesis(signal_bounds={"iv_rank": {"min": 30.0}})
        low = evaluate_opportunity(thesis, _snap(regime="bullish", iv_rank=10.0))
        self.assertIsInstance(low, StandAside)
        high = evaluate_opportunity(thesis, _snap(regime="bullish", iv_rank=55.0))
        self.assertIsInstance(high, Opportunity)

    def test_stand_aside_yields_zero_structures(self):
        thesis = _fixture_thesis(regime_allow=("bullish",))
        decision = evaluate_opportunity(thesis, _snap(regime="bearish"))
        self.assertEqual(plan_structures(decision, thesis), [])

    def test_opportunity_yields_structure_plan(self):
        thesis = _fixture_thesis()
        decision = evaluate_opportunity(thesis, _snap(regime="neutral"))
        plans = plan_structures(decision, thesis)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].structure, "put_credit_spread")
        self.assertEqual(plans[0].max_loss_usd, 300.0)

    def test_invalid_max_structures_rejected(self):
        with self.assertRaises(ValueError):
            thesis_from_mapping({"thesis_id": "x", "max_structures": 9})

    def test_unknown_signal_in_bounds_raises(self):
        thesis = _fixture_thesis(signal_bounds={"not_in_catalog": {"min": 1.0}})
        with self.assertRaises(KeyError):
            evaluate_opportunity(thesis, _snap())

    def test_emitter_does_not_import_broker(self):
        import trader_platform.research.opportunity as opp_mod

        src = Path(opp_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("RiskGovernor", src)
        self.assertNotIn("PaperBroker", src)
        self.assertNotIn("broker_adapter", src)

    def test_strategy_spec_bridge_preserves_iv_bound(self):
        seed = load_strategy_spec(
            Path("configs/strategy_specs/pcs_iv_rich_noncollapse_21d_v1.json")
        )
        thesis = thesis_from_strategy_spec(seed)
        # Mechanical field bridge — not an edge claim
        self.assertIn("iv_rank", thesis.signal_bounds)
        self.assertEqual(thesis.signal_bounds["iv_rank"]["min"], 30.0)
        low = evaluate_opportunity(thesis, _snap(regime="bullish", iv_rank=5.0))
        self.assertIsInstance(low, StandAside)

    def test_load_repo_thesis_files(self):
        path = Path("configs/theses/bull_neutral_pcs_45d.yaml")
        self.assertTrue(path.exists())
        thesis = load_thesis(path)
        self.assertEqual(thesis.thesis_id, "bull_neutral_pcs_45d")
        # Can serialize to StrategySpec for prove path
        spec = strategy_spec_from_thesis(thesis, symbols=["BAC"])
        self.assertEqual(spec.symbols, ("BAC",))
        self.assertEqual(spec.router_policy, "pcs_non_bear")

    def test_shared_path_watcher_uses_emitter_stand_aside(self):
        """Watch maps StandAside → NO_SETUP (not a fake paper packet)."""
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "reg.json"
            # Minimal valid seed file for seat
            seed_path = Path("configs/strategy_specs/pcs_iv_rich_noncollapse_21d_v1.json")
            seat = LivingSeat(
                seat_id="test_iv_seat",
                candidate_id="TEST_IV",
                family_id="TEST_FAM",
                status="paper_eligible",
                funnel_stage="F3_ROBUST_PAPER_PLAN",
                symbols=["BAC"],
                router_policy="pcs_non_bear",
                spec_path=str(seed_path.resolve()),
            )
            reg = LivingRegistry(seats=[seat])
            save_living_registry(reg, reg_path)

            # Bar that fails iv_rank_min=30 from seed management
            row = pd.Series(
                {
                    "close": 40.0,
                    "regime": "bullish",
                    "iv_rank": 5.0,
                    "ema_stack": 0.5,
                    "rsi_14": 50.0,
                    "hv_20": 0.2,
                    "hv_60": 0.25,
                    "volume_surge": 1.0,
                    "ret_1d": 0.0,
                    "ret_5d": 0.0,
                    "ret_14d": 0.0,
                    "intraday_return": 0.0,
                }
            )
            bar_time = pd.Timestamp("2024-06-03")

            with patch(
                "trader_platform.research.opportunity_watcher._latest_bar",
                return_value=(row, bar_time),
            ):
                result = watch_once(registry_path=reg_path)
            self.assertEqual(result.status, "NO_SETUP")
            self.assertIn("stand aside", result.reason.lower())


if __name__ == "__main__":
    unittest.main()

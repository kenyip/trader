"""Spine contract: seed → thesis bridge → opportunity → (mocked) prove → watch.

Uses synthetic market rows and mocked evaluate/ingest — engine wiring only.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from trader_platform.research.identity import coarse_dna_from_spec
from trader_platform.research.living_registry import (
    LivingRegistry,
    LivingSeat,
    save_living_registry,
)
from trader_platform.research.opportunity import (
    evaluate_from_row,
    plan_structures,
    thesis_from_strategy_spec,
)
from trader_platform.research.opportunity_watcher import watch_once
from trader_platform.research.strategy_spec import load_strategy_spec


class SpineContractTest(unittest.TestCase):
    def test_seed_to_thesis_to_decision_to_structure(self):
        seed = load_strategy_spec(
            Path("configs/strategy_specs/pcs_iv_rich_noncollapse_21d_v1.json")
        )
        thesis = thesis_from_strategy_spec(seed)
        row = pd.Series(
            {
                "close": 50.0,
                "regime": "bullish",
                "iv_rank": 55.0,
                "ema_stack": 0.5,
                "rsi_14": 50.0,
                "hv_20": 0.25,
                "hv_60": 0.3,
                "volume_surge": 1.1,
                "ret_1d": 0.0,
                "ret_5d": 0.0,
                "ret_14d": 0.0,
                "intraday_return": 0.0,
            }
        )
        decision = evaluate_from_row(thesis, row, symbol="BAC", asof="2024-06-01")
        self.assertTrue(decision.is_opportunity)
        plans = plan_structures(decision, thesis)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].structure, "put_credit_spread")
        dna = coarse_dna_from_spec(seed)
        self.assertIn("pcs_non_bear", dna)

    def test_watch_with_seat_and_spec_shared_path(self):
        seed_path = Path("configs/strategy_specs/pcs_bull_neutral_income_45d_v1.json")
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "reg.json"
            seat = LivingSeat(
                seat_id="spine:BAC",
                candidate_id="SPINE_TEST",
                family_id="SPINE_FAM",
                status="paper_eligible",
                symbols=["BAC"],
                router_policy="pcs_non_bear",
                spec_path=str(seed_path.resolve()),
                funnel_stage="F3_ROBUST_PAPER_PLAN",
            )
            save_living_registry(LivingRegistry(seats=[seat]), reg_path)
            bull = pd.Series(
                {
                    "close": 40.0,
                    "regime": "bullish",
                    "iv_rank": 40.0,
                    "ema_stack": 0.3,
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
            with patch(
                "trader_platform.research.opportunity_watcher._latest_bar",
                return_value=(bull, pd.Timestamp("2024-06-02")),
            ):
                ready = watch_once(registry_path=reg_path)
            self.assertEqual(ready.status, "PAPER_PACKET_READY")
            self.assertEqual(ready.selected_structure, "put_credit_spread")
            self.assertFalse(ready.trading_authority)

            bear = bull.copy()
            bear["regime"] = "bearish"
            with patch(
                "trader_platform.research.opportunity_watcher._latest_bar",
                return_value=(bear, pd.Timestamp("2024-06-03")),
            ):
                aside = watch_once(registry_path=reg_path)
            self.assertEqual(aside.status, "NO_SETUP")


if __name__ == "__main__":
    unittest.main()

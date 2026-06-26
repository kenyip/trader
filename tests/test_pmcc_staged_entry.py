from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from pmcc.staged_entry import build_tsla_staged_entry_plan


class StagedEntryPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.chain = pd.DataFrame([
            {"expiration": "2026-08-21", "dte": 57, "strike": 450.0, "bid": 6.80, "ask": 6.95, "mid": 6.875, "iv": 0.475, "delta": 0.20},
            {"expiration": "2026-08-21", "dte": 57, "strike": 460.0, "bid": 5.65, "ask": 5.75, "mid": 5.70, "iv": 0.478, "delta": 0.17},
            {"expiration": "2026-08-21", "dte": 57, "strike": 470.0, "bid": 4.70, "ask": 4.80, "mid": 4.75, "iv": 0.483, "delta": 0.15},
            {"expiration": "2026-08-21", "dte": 57, "strike": 500.0, "bid": 2.86, "ask": 2.94, "mid": 2.90, "iv": 0.501, "delta": 0.09},
            {"expiration": "2026-08-21", "dte": 57, "strike": 520.0, "bid": 2.14, "ask": 2.20, "mid": 2.17, "iv": 0.516, "delta": 0.07},
        ])
        self.records = [
            {"ticker": "TSLA", "leaps_strike": 410, "leaps_expiration": "2028-06-16", "leaps_debit": 13000, "contracts": 2, "open_short": False},
            {"ticker": "TSLA", "leaps_strike": 400, "leaps_expiration": "2028-06-16", "leaps_debit": 11225, "contracts": 4, "open_short": False},
            {"ticker": "TSLA", "leaps_strike": 410, "leaps_expiration": "2028-06-16", "leaps_debit": 10800, "contracts": 1, "open_short": False},
            {"ticker": "NVDA", "leaps_strike": 210, "leaps_expiration": "2028-06-16", "leaps_debit": 5250, "contracts": 1, "open_short": False},
        ]

    def test_summarizes_current_tsla_leaps_and_coverage_goal(self) -> None:
        plan = build_tsla_staged_entry_plan(self.records, self.chain, spot=375.12, today=date(2026, 6, 25))

        self.assertEqual(plan["position"]["leaps_contracts"], 7)
        self.assertEqual(plan["position"]["open_short_contracts"], 0)
        self.assertEqual(plan["position"]["target_short_contracts"], 5)
        self.assertAlmostEqual(plan["position"]["total_leaps_debit"], 81700.0)
        self.assertAlmostEqual(plan["position"]["coverage_target_pct"], 71.4, places=1)

    def test_package_quotes_include_daily_targets_that_decay_with_dte(self) -> None:
        plan = build_tsla_staged_entry_plan(self.records, self.chain, spot=375.12, today=date(2026, 6, 25))
        initial = plan["packages"]["initial"]

        self.assertEqual(initial["label"], "Initial 3-short stack")
        self.assertEqual(initial["legs"], "2x $450 + 1x $500")
        self.assertAlmostEqual(initial["bid_credit"], 1646.0)
        self.assertAlmostEqual(initial["bid_per_day"], 28.877, places=3)
        self.assertAlmostEqual(initial["target_credit_good"], 1995.0)
        self.assertAlmostEqual(initial["target_credit_strong"], 2565.0)
        self.assertEqual(initial["order_limit_text"], "2x $450 + 1x $500 @ $19.95 package credit good-till-green-day")

    def test_action_switches_to_higher_strikes_when_spot_is_near_400(self) -> None:
        plan = build_tsla_staged_entry_plan(self.records, self.chain, spot=396.0, today=date(2026, 6, 25))

        self.assertIn("shift higher", plan["next_step"]["action"].lower())
        self.assertEqual(plan["next_step"]["preferred_package"], "higher")
        self.assertEqual(plan["packages"]["higher"]["legs"], "2x $470 + 1x $520")

    def test_management_rows_show_trigger_strike_target_short_and_estimated_premium(self) -> None:
        plan = build_tsla_staged_entry_plan(self.records, self.chain, spot=375.12, today=date(2026, 6, 25))
        rip_row = next(row for row in plan["management"] if row["trigger"] == "$490")

        self.assertEqual(rip_row["target_short"], "$545-$550")
        self.assertIn("roll 2x $450", rip_row["action"].lower())
        self.assertIn("est_roll_credit_per_short", rip_row)
        self.assertIn("est_net_debit_per_short", rip_row)


if __name__ == "__main__":
    unittest.main()

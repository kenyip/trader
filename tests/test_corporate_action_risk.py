import unittest
from typing import cast

import numpy as np
import pandas as pd

from trader_platform.research.corporate_action_risk import (
    DividendEvent,
    assess_short_call_assignment_risk,
)
from trader_platform.research.debit_vertical_sim import run_debit_vertical_backtest
from trader_platform.research.diagonal_sim import run_diagonal_backtest
from trader_platform.strategy_dna import STRUCTURE_CATALOG


class CorporateActionRiskTest(unittest.TestCase):
    def _bars(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": np.linspace(50.0, 80.0, 60),
                "iv_proxy": np.full(60, 0.30),
                "iv_rank": np.full(60, 35.0),
                "regime": ["bullish"] * 60,
            },
            index=pd.bdate_range("2026-01-02", periods=60),
        )

    def test_future_announcement_cannot_leak_into_earlier_bar(self):
        event = DividendEvent(
            symbol="TEST",
            ex_date=pd.Timestamp("2026-01-20"),
            amount_per_share=5.0,
            known_at=pd.Timestamp("2026-01-12"),
        )

        before_announcement = assess_short_call_assignment_risk(
            symbol="TEST",
            as_of=pd.Timestamp("2026-01-09"),
            expiration=pd.Timestamp("2026-01-30"),
            spot=60.0,
            short_strike=50.0,
            short_call_mark=10.25,
            events=[event],
        )
        after_announcement = assess_short_call_assignment_risk(
            symbol="TEST",
            as_of=pd.Timestamp("2026-01-13"),
            expiration=pd.Timestamp("2026-01-30"),
            spot=60.0,
            short_strike=50.0,
            short_call_mark=10.25,
            events=[event],
        )

        self.assertFalse(before_announcement.at_risk)
        self.assertEqual(before_announcement.reason, "no_known_dividend_before_expiry")
        self.assertTrue(after_announcement.at_risk)
        self.assertEqual(after_announcement.reason, "early_assignment_risk")

    def test_required_provider_missing_or_uncovered_fails_closed(self):
        bars = self._bars()
        missing = run_diagonal_backtest(
            "TEST",
            period="smoke",
            df=bars,
            require_dividend_events=True,
        )
        uncovered = run_debit_vertical_backtest(
            "TEST",
            structure="bull_call_debit_spread",
            period="smoke",
            df=bars,
            dividend_event_provider=lambda symbol, as_of, through: None,
            require_dividend_events=True,
        )

        self.assertFalse(missing.ok)
        self.assertTrue(missing.skipped)
        self.assertIn("provider missing", missing.reason)
        self.assertFalse(uncovered.ok)
        self.assertTrue(uncovered.skipped)
        self.assertIn("coverage missing", uncovered.reason)

    def test_malformed_dividend_data_fails_closed(self):
        malformed = DividendEvent(
            symbol="TEST",
            ex_date=cast(pd.Timestamp, pd.Timestamp("2026-01-30")),
            amount_per_share=float("nan"),
            known_at=cast(pd.Timestamp, pd.Timestamp("2026-01-01")),
        )
        result = run_debit_vertical_backtest(
            "TEST",
            structure="bull_call_debit_spread",
            period="smoke",
            df=self._bars(),
            dividend_event_provider=lambda symbol, as_of, through: [malformed],
            require_dividend_events=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.skipped)
        self.assertIn("invalid dividend event data", result.reason)

    def test_nonfinite_assignment_threshold_fails_closed(self):
        event = DividendEvent(
            symbol="TEST",
            ex_date=cast(pd.Timestamp, pd.Timestamp("2026-01-30")),
            amount_per_share=1.0,
            known_at=cast(pd.Timestamp, pd.Timestamp("2026-01-01")),
        )
        result = run_diagonal_backtest(
            "TEST",
            period="smoke",
            df=self._bars(),
            config={
                "assignment_dividend_to_extrinsic_ratio": float("nan"),
                "diagonal_short_dte": 30,
                "diagonal_long_dte": 60,
                "max_loss_budget_usd": 500.0,
            },
            dividend_event_provider=lambda symbol, as_of, through: [event],
            require_dividend_events=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.skipped)
        self.assertIn("invalid dividend event data", result.reason)

    def test_known_dividend_closes_at_risk_short_calls_in_both_sims(self):
        bars = self._bars()
        event = DividendEvent(
            symbol="TEST",
            ex_date=pd.Timestamp("2026-01-30"),
            amount_per_share=100.0,
            known_at=pd.Timestamp("2026-01-01"),
        )
        provider = lambda symbol, as_of, through: [event]
        common = {
            "profit_target": 100.0,
            "defined_loss_exit_frac": 100.0,
            "dte_stop": 0,
            "max_loss_budget_usd": 500.0,
        }

        diagonal = run_diagonal_backtest(
            "TEST",
            period="smoke",
            df=bars,
            config={**common, "diagonal_short_dte": 30, "diagonal_long_dte": 60},
            dividend_event_provider=provider,
            require_dividend_events=True,
        )
        vertical = run_debit_vertical_backtest(
            "TEST",
            structure="bull_call_debit_spread",
            period="smoke",
            df=bars,
            config={**common, "long_dte": 30, "spread_width": 2.0},
            dividend_event_provider=provider,
            require_dividend_events=True,
        )

        self.assertTrue(diagonal.ok, diagonal.reason)
        self.assertTrue(vertical.ok, vertical.reason)
        self.assertGreater(diagonal.metrics["early_assignment_risk_exits"], 0)
        self.assertGreater(vertical.metrics["early_assignment_risk_exits"], 0)
        self.assertIn("early_assignment_risk", diagonal.metrics["exit_reasons"])
        self.assertIn("early_assignment_risk", vertical.metrics["exit_reasons"])

    def test_below_extrinsic_dividend_does_not_force_sim_exit(self):
        event = DividendEvent(
            symbol="TEST",
            ex_date=cast(pd.Timestamp, pd.Timestamp("2026-01-30")),
            amount_per_share=1e-6,
            known_at=cast(pd.Timestamp, pd.Timestamp("2026-01-01")),
        )
        provider = lambda symbol, as_of, through: [event]
        common = {
            "profit_target": 100.0,
            "defined_loss_exit_frac": 100.0,
            "dte_stop": 0,
            "max_loss_budget_usd": 500.0,
        }

        diagonal = run_diagonal_backtest(
            "TEST",
            period="smoke",
            df=self._bars(),
            config={**common, "diagonal_short_dte": 30, "diagonal_long_dte": 60},
            dividend_event_provider=provider,
            require_dividend_events=True,
        )
        vertical = run_debit_vertical_backtest(
            "TEST",
            structure="bull_call_debit_spread",
            period="smoke",
            df=self._bars(),
            config={**common, "long_dte": 30, "spread_width": 2.0},
            dividend_event_provider=provider,
            require_dividend_events=True,
        )

        self.assertTrue(diagonal.ok, diagonal.reason)
        self.assertTrue(vertical.ok, vertical.reason)
        self.assertEqual(diagonal.metrics["early_assignment_risk_exits"], 0)
        self.assertEqual(vertical.metrics["early_assignment_risk_exits"], 0)

    def test_assignment_exit_precedes_profit_target_in_both_sims(self):
        bars = self._bars()
        bars.loc[bars.index[1]:, "close"] = 100.0
        event = DividendEvent(
            symbol="TEST",
            ex_date=cast(pd.Timestamp, pd.Timestamp("2026-01-30")),
            amount_per_share=100.0,
            known_at=cast(pd.Timestamp, pd.Timestamp("2026-01-01")),
        )
        provider = lambda symbol, as_of, through: [event]
        common = {
            "profit_target": -1.0,
            "defined_loss_exit_frac": 100.0,
            "dte_stop": 0,
            "max_loss_budget_usd": 500.0,
        }

        diagonal = run_diagonal_backtest(
            "TEST",
            period="smoke",
            df=bars,
            config={**common, "diagonal_short_dte": 30, "diagonal_long_dte": 60},
            dividend_event_provider=provider,
            require_dividend_events=True,
        )
        vertical = run_debit_vertical_backtest(
            "TEST",
            structure="bull_call_debit_spread",
            period="smoke",
            df=bars,
            config={**common, "long_dte": 30, "spread_width": 2.0},
            dividend_event_provider=provider,
            require_dividend_events=True,
        )

        self.assertEqual(diagonal.trades[0].exit_reason, "early_assignment_risk")
        self.assertEqual(vertical.trades[0].exit_reason, "early_assignment_risk")

    def test_catalog_exposes_provider_dependent_assignment_guard(self):
        for structure in ("diagonal_spread", "bull_call_debit_spread"):
            exit_plan = STRUCTURE_CATALOG[structure]["exit_plan"]
            self.assertEqual(exit_plan["ladder"][0], "early_assignment_risk")
            self.assertIn("honest_known_at_required", exit_plan["limitations"])

    def test_bear_put_vertical_does_not_require_dividend_events(self):
        result = run_debit_vertical_backtest(
            "TEST",
            structure="bear_put_debit_spread",
            period="smoke",
            df=self._bars().assign(regime="bearish", close=np.linspace(80.0, 50.0, 60)),
            require_dividend_events=True,
        )

        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.metrics["corporate_action_mode"], "not_applicable_put")
        self.assertEqual(result.metrics["early_assignment_risk_exits"], 0)


if __name__ == "__main__":
    unittest.main()

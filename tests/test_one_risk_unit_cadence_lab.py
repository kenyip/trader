import unittest

import pandas as pd

from scripts.one_risk_unit_cadence_lab import (
    CANDIDATE_ID,
    CLUSTERS,
    COST_AXES,
    FAMILY_CLASS,
    FAMILY_ID,
    PortfolioEvent,
    admit_one_risk_unit,
    evaluate_axis,
    strategy_decision,
)
from trader_platform.research.pcs_sim import PcsTrade
from trader_platform.strategy_dna import STRUCTURE_CATALOG


class OneRiskUnitCadenceLabTest(unittest.TestCase):
    def _integrity(self) -> dict[str, object]:
        return {
            "all_symbol_lag_boundaries_ok": True,
            "holdout_backtest_invocations": 0,
            "holdout_trade_rows_written": 0,
            "holdout_outcomes_read": False,
            "train_backtest_invocations": 16,
            "population_complete": True,
            "priority_outcome_free": True,
            "signal_dna_identical_within_axis": True,
        }

    def _event(
        self,
        symbol: str,
        entry: str,
        exit_: str,
        pnl_usd: float,
        *,
        max_loss_usd: float = 100.0,
    ) -> PortfolioEvent:
        credit = 0.50
        exit_debit = credit - pnl_usd / 100.0
        trade = PcsTrade(
            entry_date=pd.Timestamp(entry),
            expiration=pd.Timestamp(exit_) + pd.Timedelta(days=7),
            short_strike=50.0,
            long_strike=49.0,
            width=1.0,
            net_credit=credit,
            dte_at_entry=14,
            iv_at_entry=0.40,
            regime_at_entry="neutral",
            short_delta_entry=-0.20,
            max_loss_per_share=max_loss_usd / 100.0,
            exit_date=pd.Timestamp(exit_),
            exit_debit=exit_debit,
            exit_reason="test",
            closed=True,
        )
        return PortfolioEvent(symbol, CLUSTERS[symbol], trade)

    def _frames(self, dates: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
        frame = pd.DataFrame(
            {
                "close": [50.0] * len(dates),
                "iv_proxy": [0.40] * len(dates),
            },
            index=dates,
        )
        return {symbol: frame.copy() for symbol in CLUSTERS}

    def test_fixed_priority_breaks_same_day_tie_without_pnl(self):
        high_profit_late_priority = self._event("AMD", "2026-01-02", "2026-01-08", 1000.0)
        loss_first_priority = self._event("AAPL", "2026-01-02", "2026-01-05", -10.0)

        accepted, rejected = admit_one_risk_unit([high_profit_late_priority, loss_first_priority])

        self.assertEqual([event.symbol for event in accepted], ["AAPL"])
        self.assertEqual([event.symbol for event in rejected], ["AMD"])

    def test_exit_date_is_consumed_and_next_day_can_enter(self):
        first = self._event("AAPL", "2026-01-02", "2026-01-05", 5.0)
        same_exit_date = self._event("BAC", "2026-01-05", "2026-01-06", 5.0)
        next_day = self._event("F", "2026-01-06", "2026-01-07", 5.0)

        accepted, rejected = admit_one_risk_unit([next_day, same_exit_date, first])

        self.assertEqual([event.symbol for event in accepted], ["AAPL", "F"])
        self.assertEqual([event.symbol for event in rejected], ["BAC"])

    def test_changing_outcomes_cannot_change_admission(self):
        original = [
            self._event("AAPL", "2026-01-02", "2026-01-05", 10.0),
            self._event("AMD", "2026-01-02", "2026-01-08", -100.0),
            self._event("BAC", "2026-01-06", "2026-01-09", 5.0),
        ]
        reversed_outcomes = [
            self._event("AAPL", "2026-01-02", "2026-01-05", -100.0),
            self._event("AMD", "2026-01-02", "2026-01-08", 1000.0),
            self._event("BAC", "2026-01-06", "2026-01-09", -50.0),
        ]

        first_keys = [(event.entry_date, event.symbol) for event in admit_one_risk_unit(original)[0]]
        second_keys = [(event.entry_date, event.symbol) for event in admit_one_risk_unit(reversed_outcomes)[0]]

        self.assertEqual(first_keys, second_keys)

    def test_negative_stream_fails_even_when_one_unit_integrity_holds(self):
        dates = pd.bdate_range("2026-01-02", "2026-03-31")
        events = []
        starts = [0, 10, 20, 30]
        for offset in starts:
            events.append(
                self._event(
                    "AAPL",
                    str(dates[offset].date()),
                    str(dates[offset + 4].date()),
                    -20.0,
                )
            )

        result = evaluate_axis(events, self._frames(dates), dates, COST_AXES["fixed_001"])

        self.assertLessEqual(result["capped"]["max_concurrent_open_units"], 1)
        self.assertEqual(result["capped"]["cluster_overlap_violations"], 0)
        self.assertFalse(result["gates"]["after_cost_positive"])
        self.assertFalse(result["pass"])

    def test_marked_ledger_reconciles_terminal_realized_pnl(self):
        dates = pd.bdate_range("2026-01-02", "2026-01-15")
        events = [
            self._event("AAPL", str(dates[0].date()), str(dates[3].date()), 10.0),
            self._event("BAC", str(dates[4].date()), str(dates[7].date()), -5.0),
        ]

        result = evaluate_axis(events, self._frames(dates), dates, COST_AXES["fixed_001"])

        self.assertAlmostEqual(result["capped"]["total_pnl_usd"], 5.0, places=9)
        self.assertAlmostEqual(result["capped"]["terminal_equity_usd"], 5.0, places=9)
        self.assertAlmostEqual(result["capped"]["ledger_delta_usd"], 0.0, places=9)
        self.assertTrue(result["gates"]["ledger_exact"])

    def test_decision_requires_both_frozen_cost_axes(self):
        passing = {axis: {"pass": True} for axis in COST_AXES}

        decision, integrity_pass = strategy_decision(passing, self._integrity(), None)
        missing_axis_decision, missing_axis_integrity = strategy_decision(
            {"pct_5": {"pass": True}}, self._integrity(), None
        )

        self.assertEqual(decision, "STRATEGY_ADVANCED")
        self.assertTrue(integrity_pass)
        self.assertEqual(missing_axis_decision, "FAMILY_CLOSED")
        self.assertTrue(missing_axis_integrity)

    def test_decision_requires_unread_holdout_payload(self):
        passing = {axis: {"pass": True} for axis in COST_AXES}
        inspected_integrity = self._integrity()
        inspected_integrity["holdout_backtest_invocations"] = 1

        metrics_decision, metrics_integrity = strategy_decision(
            passing, self._integrity(), {"total_pnl_usd": 1.0}
        )
        invocation_decision, invocation_integrity = strategy_decision(
            passing, inspected_integrity, None
        )

        self.assertEqual(metrics_decision, "FAMILY_CLOSED")
        self.assertFalse(metrics_integrity)
        self.assertEqual(invocation_decision, "FAMILY_CLOSED")
        self.assertFalse(invocation_integrity)

    def test_payload_identity_uses_canonical_family_and_14_dte_seed(self):
        seed = STRUCTURE_CATALOG["put_credit_spread"]["config_seed"]

        self.assertEqual(FAMILY_ID, "ONE_RISK_UNIT_CADENCE_POLICY_F0")
        self.assertEqual(CANDIDATE_ID, "ONE_RISK_UNIT_CADENCE_PCS_V1")
        self.assertEqual(FAMILY_CLASS, "PORTFOLIO_CADENCE_CONCENTRATION_CONTROL")
        self.assertEqual(seed["long_dte"], 14)


if __name__ == "__main__":
    unittest.main()

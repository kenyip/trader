import subprocess
import sys
import unittest

import numpy as np
import pandas as pd

from scripts.breakout_continuation_train_lab import (
    build_matched_blueprints,
    evaluate_train_partition,
    run_lab_from_panel,
)


DEFAULT_TEST_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN"]


class BreakoutContinuationTrainLabTest(unittest.TestCase):
    @staticmethod
    def _panel(periods: int = 420) -> pd.DataFrame:
        index = pd.bdate_range("2019-01-02", periods=periods)
        base = 100.0 * np.exp(np.arange(periods) * 0.0006)
        panel = pd.DataFrame({"AAPL": base.copy(), "MSFT": base * 1.1}, index=index)
        for symbol, offset in (("AAPL", 0), ("MSFT", 8)):
            for position in (145 + offset, 225 + offset, 305 + offset, 385 + offset):
                if position < periods:
                    panel.loc[index[position], symbol] = panel.loc[index[position - 1], symbol] * 1.05
        return panel

    def test_blueprints_use_prior_high_and_outcome_shock_cannot_change_selection(self):
        panel = self._panel()
        blueprints = build_matched_blueprints(
            panel,
            breakout_lookback_sessions=20,
            trend_lookback_sessions=60,
            forward_sessions=10,
            max_match_distance_sessions=126,
        )

        self.assertGreaterEqual(len(blueprints), 4)
        first = blueprints[0]
        self.assertLess(first["treated_signal_date"], first["treated_entry_date"])
        self.assertLess(first["treated_entry_date"], first["treated_exit_date"])
        self.assertGreater(first["treated_breakout_ratio"], 1.0)
        self.assertGreaterEqual(first["control_breakout_ratio"], 0.95)
        self.assertLessEqual(first["control_breakout_ratio"], 1.0)
        self.assertLess(first["control_exit_date"], first["treated_signal_date"])

        shocked = panel.copy()
        shocked.loc[first["treated_exit_date"], first["symbol"]] *= 1.50
        rebuilt = build_matched_blueprints(
            shocked,
            breakout_lookback_sessions=20,
            trend_lookback_sessions=60,
            forward_sessions=10,
            max_match_distance_sessions=126,
        )
        rebuilt_first = rebuilt[0]
        for key in (
            "symbol",
            "control_signal_date",
            "control_entry_date",
            "control_exit_date",
            "treated_signal_date",
            "treated_entry_date",
            "treated_exit_date",
        ):
            self.assertEqual(first[key], rebuilt_first[key])

    def test_train_gate_requires_positive_after_cost_continuation_and_bounded_excess(self):
        index = pd.bdate_range("2020-01-02", periods=360)
        panel = pd.DataFrame({"AAPL": 100.0}, index=index)
        blueprints = []
        for pair_index in range(12):
            base = 5 + pair_index * 28
            control_entry, control_exit = index[base + 1], index[base + 11]
            treated_entry, treated_exit = index[base + 15], index[base + 25]
            panel.loc[control_exit, "AAPL"] = 101.0
            panel.loc[treated_exit, "AAPL"] = 105.0
            blueprints.append(
                {
                    "symbol": "AAPL",
                    "control_signal_date": index[base],
                    "control_entry_date": control_entry,
                    "control_exit_date": control_exit,
                    "control_breakout_ratio": 0.98,
                    "control_trend_distance": 0.05,
                    "control_ret_20": 0.10,
                    "control_hv_20": 0.30,
                    "treated_signal_date": index[base + 14],
                    "treated_entry_date": treated_entry,
                    "treated_exit_date": treated_exit,
                    "treated_breakout_ratio": 1.03,
                    "treated_trend_distance": 0.05,
                    "treated_ret_20": 0.10,
                    "treated_hv_20": 0.30,
                    "calendar_distance_sessions": 14,
                    "return_20d_match_distance": 0.0,
                    "hv_20d_match_distance": 0.0,
                }
            )

        result = evaluate_train_partition(
            panel,
            blueprints,
            min_pairs=10,
            round_trip_cost_bps=20.0,
            bootstrap_samples=500,
        )

        self.assertTrue(result["gate_pass"])
        self.assertGreater(result["treated_mean_return_after_cost"], 0.0)
        self.assertGreater(result["paired_excess_mean"], 0.0)
        self.assertGreater(result["paired_excess_bootstrap_lb90"], 0.0)
        self.assertEqual(result["integrity_violations"], [])

    def test_positive_point_excess_with_nonpositive_bootstrap_bound_fails(self):
        index = pd.bdate_range("2020-01-02", periods=360)
        panel = pd.DataFrame({"AAPL": 100.0}, index=index)
        blueprints = []
        for pair_index, excess in enumerate([0.10, -0.09] * 6):
            base = 5 + pair_index * 28
            control_entry, control_exit = index[base + 1], index[base + 11]
            treated_entry, treated_exit = index[base + 15], index[base + 25]
            panel.loc[control_exit, "AAPL"] = 101.0
            panel.loc[treated_exit, "AAPL"] = 100.0 * (1.01 + excess)
            blueprints.append(
                {
                    "symbol": "AAPL",
                    "control_signal_date": index[base],
                    "control_entry_date": control_entry,
                    "control_exit_date": control_exit,
                    "control_breakout_ratio": 0.98,
                    "control_trend_distance": 0.05,
                    "control_ret_20": 0.10,
                    "control_hv_20": 0.30,
                    "treated_signal_date": index[base + 14],
                    "treated_entry_date": treated_entry,
                    "treated_exit_date": treated_exit,
                    "treated_breakout_ratio": 1.03,
                    "treated_trend_distance": 0.05,
                    "treated_ret_20": 0.10,
                    "treated_hv_20": 0.30,
                    "calendar_distance_sessions": 14,
                    "return_20d_match_distance": 0.0,
                    "hv_20d_match_distance": 0.0,
                }
            )

        result = evaluate_train_partition(
            panel,
            blueprints,
            min_pairs=10,
            bootstrap_samples=2_000,
        )

        self.assertGreater(result["treated_mean_return_after_cost"], 0.0)
        self.assertGreater(result["paired_excess_mean"], 0.0)
        self.assertLessEqual(result["paired_excess_bootstrap_lb90"], 0.0)
        self.assertFalse(result["gate_checks"]["paired_excess_bootstrap_lb90_positive"])
        self.assertFalse(result["gate_pass"])

    def test_payload_reserves_holdout_and_carries_complete_bounded_stack(self):
        panel = self._panel(periods=520)

        payload = run_lab_from_panel(
            panel,
            symbols=list(panel.columns),
            provenance={"fixture": True},
            train_fraction=0.60,
            breakout_lookback_sessions=20,
            trend_lookback_sessions=60,
            min_train_pairs=2,
            bootstrap_samples=500,
        )

        self.assertIn(payload["strategy_outcome"], {"STRATEGY_ADVANCED", "FAMILY_CLOSED"})
        self.assertFalse(payload["f2_or_l1_claim"])
        self.assertFalse(payload["untouched_holdout"]["outcome_metrics_read"])
        self.assertFalse(payload["untouched_holdout"]["simulation_run"])
        self.assertNotIn("pairs", payload["untouched_holdout"])
        self.assertEqual(payload["option_stage"]["pricing_calls"], 0)
        self.assertEqual(payload["structure"], "conditional_bull_call_debit_spread_not_yet_priced")
        self.assertEqual(payload["capital_fit_usd"], 100.0)
        self.assertEqual(payload["one_lot_max_loss_usd"], 100.0)
        self.assertEqual(payload["max_lots"], 1)
        self.assertEqual(payload["forecast_type"], "direction_up")
        self.assertIn("intended", payload["greek_exposures"])
        self.assertIn("dangerous_unintended", payload["greek_exposures"])
        self.assertTrue(payload["stand_aside_rule"])
        self.assertIn("fixed ten-session underlying return", payload["exit_rule"])
        self.assertIn("no managed exit was simulated", payload["exit_rule"])
        self.assertIn("approximate directional pre-screen", payload["horizon_alignment"])
        self.assertIn("does not stress paired excess", payload["claim_scope"])
        self.assertEqual(
            len(payload["untouched_holdout"]["required_non_gating_diagnostics_if_opened"]),
            3,
        )
        self.assertIn(
            "must not become a post-hoc second gate",
            payload["untouched_holdout"]["diagnostic_role"],
        )
        encoded = __import__("json").dumps(payload, allow_nan=False)
        self.assertNotIn("holdout_return", encoded)

    def test_minimum_symbol_breadth_fails_even_when_return_gates_pass(self):
        index = pd.bdate_range("2020-01-02", periods=360)
        panel = pd.DataFrame({"AAPL": 100.0}, index=index)
        blueprints = []
        for pair_index in range(12):
            base = 5 + pair_index * 28
            control_entry, control_exit = index[base + 1], index[base + 11]
            treated_entry, treated_exit = index[base + 15], index[base + 25]
            panel.loc[control_exit, "AAPL"] = 101.0
            panel.loc[treated_exit, "AAPL"] = 105.0
            blueprints.append(
                {
                    "symbol": "AAPL",
                    "control_signal_date": index[base],
                    "control_entry_date": control_entry,
                    "control_exit_date": control_exit,
                    "control_breakout_ratio": 0.98,
                    "control_trend_distance": 0.05,
                    "control_ret_20": 0.10,
                    "control_hv_20": 0.30,
                    "treated_signal_date": index[base + 14],
                    "treated_entry_date": treated_entry,
                    "treated_exit_date": treated_exit,
                    "treated_breakout_ratio": 1.03,
                    "treated_trend_distance": 0.05,
                    "treated_ret_20": 0.10,
                    "treated_hv_20": 0.30,
                    "calendar_distance_sessions": 14,
                    "return_20d_match_distance": 0.0,
                    "hv_20d_match_distance": 0.0,
                }
            )

        result = evaluate_train_partition(
            panel,
            blueprints,
            min_pairs=10,
            min_symbols=2,
            round_trip_cost_bps=20.0,
            bootstrap_samples=500,
        )

        self.assertTrue(result["gate_checks"]["minimum_train_pairs"])
        self.assertFalse(result["gate_checks"]["minimum_symbol_breadth"])
        self.assertTrue(result["gate_checks"]["positive_treated_mean_after_cost"])
        self.assertTrue(result["gate_checks"]["positive_paired_excess_mean"])
        self.assertTrue(result["gate_checks"]["paired_excess_bootstrap_lb90_positive"])
        self.assertFalse(result["gate_pass"])

    def test_cli_exposes_frozen_parameters_and_output_path(self):
        completed = subprocess.run(
            [sys.executable, "scripts/breakout_continuation_train_lab.py", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--symbols", completed.stdout)
        self.assertIn("--start", completed.stdout)
        self.assertIn("--end", completed.stdout)
        self.assertIn("--out", completed.stdout)

    def test_zero_support_serializes_null_metrics_and_closes_family(self):
        index = pd.bdate_range("2020-01-02", periods=260)
        panel = pd.DataFrame(
            {symbol: np.full(len(index), 100.0 + offset) for offset, symbol in enumerate(DEFAULT_TEST_SYMBOLS)},
            index=index,
        )

        payload = run_lab_from_panel(
            panel,
            symbols=DEFAULT_TEST_SYMBOLS,
            provenance={"fixture": True},
            trend_lookback_sessions=60,
            min_train_pairs=2,
            min_train_symbols=2,
            bootstrap_samples=100,
        )

        self.assertEqual(payload["strategy_outcome"], "FAMILY_CLOSED")
        self.assertEqual(payload["train"]["n_pairs"], 0)
        self.assertIsNone(payload["train"]["paired_excess_mean"])
        self.assertIsNone(payload["train"]["paired_excess_bootstrap_lb90"])
        self.assertFalse(payload["train"]["gate_pass"])
        __import__("json").dumps(payload, allow_nan=False)

    def test_nonfinite_panel_fails_closed(self):
        panel = self._panel()
        panel.iloc[200, 0] = np.nan

        with self.assertRaisesRegex(ValueError, "finite"):
            build_matched_blueprints(panel)


if __name__ == "__main__":
    unittest.main()

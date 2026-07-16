import json
import subprocess
import sys
import unittest

import numpy as np
import pandas as pd

from scripts.post_shock_range_compression_train_lab import (
    build_matched_blueprints,
    evaluate_train_partition,
    run_lab_from_panel,
)


class PostShockRangeCompressionTrainLabTest(unittest.TestCase):
    @staticmethod
    def _selection_panel(periods: int = 520) -> pd.DataFrame:
        index = pd.bdate_range("2018-01-02", periods=periods)
        rng = np.random.default_rng(20260715)
        panel = {}
        for symbol_index, symbol in enumerate(("AAPL", "AMD")):
            returns = rng.normal(0.0002, 0.008, periods)
            for position in (170 + symbol_index * 7, 300 + symbol_index * 7, 430 + symbol_index * 7):
                returns[position] = 0.04 if position % 2 == 0 else -0.04
                returns[position + 1 : position + 6] = 0.0002
            panel[symbol] = 100.0 * np.exp(np.cumsum(returns))
        return pd.DataFrame(panel, index=index)

    def test_blueprints_are_prior_only_and_outcome_changes_do_not_select_pairs(self):
        panel = self._selection_panel()
        blueprints = build_matched_blueprints(
            panel,
            shock_return_min=0.03,
            hv_ratio_min=0.10,
            control_abs_return_max=0.01,
            max_match_distance_sessions=252,
            max_return_20d_distance=0.50,
            max_hv_ratio_distance=5.0,
            max_sma20_distance_gap=0.50,
        )
        self.assertGreaterEqual(len(blueprints), 3)
        first = blueprints[0]
        self.assertLess(first["control_exit_date"], first["treated_signal_date"])
        self.assertLess(first["treated_signal_date"], first["treated_entry_date"])
        self.assertLess(first["treated_entry_date"], first["treated_exit_date"])

        shocked = panel.copy()
        shocked.loc[first["treated_exit_date"], first["symbol"]] *= 1.50
        rebuilt = build_matched_blueprints(
            shocked,
            shock_return_min=0.03,
            hv_ratio_min=0.10,
            control_abs_return_max=0.01,
            max_match_distance_sessions=252,
            max_return_20d_distance=0.50,
            max_hv_ratio_distance=5.0,
            max_sma20_distance_gap=0.50,
        )
        for key in (
            "symbol",
            "control_signal_date",
            "control_entry_date",
            "control_exit_date",
            "treated_signal_date",
            "treated_entry_date",
            "treated_exit_date",
        ):
            self.assertEqual(first[key], rebuilt[0][key])

    @staticmethod
    def _manual_partition(compressions: list[float], *, symbols=("AAPL", "AMD")):
        periods = 520
        index = pd.bdate_range("2020-01-02", periods=periods)
        panel = pd.DataFrame({symbol: 100.0 for symbol in symbols}, index=index)
        blueprints = []
        for pair_index, compression in enumerate(compressions):
            base = 5 + pair_index * 20
            symbol = symbols[pair_index % len(symbols)]
            control_signal = index[base]
            control_entry = index[base + 1]
            control_exit = index[base + 6]
            treated_signal = index[base + 9]
            treated_entry = index[base + 10]
            treated_exit = index[base + 15]
            control_range = 0.08
            treated_range = control_range - compression
            panel.loc[control_entry:control_exit, symbol] = [100.0, 108.0, 101.0, 107.0, 102.0, 106.0]
            treated_high = 100.0 * (1.0 + max(treated_range, 0.001))
            panel.loc[treated_entry:treated_exit, symbol] = [
                100.0,
                treated_high,
                100.5,
                100.4,
                100.3,
                100.2,
            ]
            blueprints.append(
                {
                    "symbol": symbol,
                    "control_signal_date": control_signal,
                    "control_entry_date": control_entry,
                    "control_exit_date": control_exit,
                    "control_abs_ret_1d": 0.001,
                    "control_ret_20": 0.02,
                    "control_hv_ratio": 1.30,
                    "control_sma20_distance": 0.01,
                    "treated_signal_date": treated_signal,
                    "treated_entry_date": treated_entry,
                    "treated_exit_date": treated_exit,
                    "treated_abs_ret_1d": 0.03,
                    "treated_ret_20": 0.02,
                    "treated_hv_ratio": 1.30,
                    "treated_sma20_distance": 0.01,
                    "calendar_distance_sessions": 9,
                    "return_20d_match_distance": 0.0,
                    "hv_ratio_match_distance": 0.0,
                    "sma20_distance_match_gap": 0.0,
                }
            )
        return panel, blueprints

    def test_train_gate_passes_only_for_dense_range_compression_and_pin_edge(self):
        panel, blueprints = self._manual_partition([0.06] * 12)
        result = evaluate_train_partition(
            panel,
            blueprints,
            min_pairs=10,
            min_symbols=2,
            bootstrap_samples=500,
        )
        self.assertTrue(result["gate_pass"], result["gate_checks"])
        self.assertLess(result["treated_mean_path_range"], result["control_mean_path_range"])
        self.assertGreaterEqual(result["pin_rate_edge"], 0.05)
        self.assertGreater(result["paired_range_compression_mean"], 0.0)
        self.assertGreater(result["paired_range_compression_bootstrap_lb90"], 0.0)
        self.assertEqual(result["integrity_violations"], [])

    def test_positive_point_compression_with_nonpositive_bound_fails(self):
        panel, blueprints = self._manual_partition([0.07, -0.06] * 6)
        result = evaluate_train_partition(
            panel,
            blueprints,
            min_pairs=10,
            min_symbols=2,
            bootstrap_samples=2_000,
        )
        self.assertGreater(result["paired_range_compression_mean"], 0.0)
        self.assertLessEqual(result["paired_range_compression_bootstrap_lb90"], 0.0)
        self.assertFalse(result["gate_checks"]["paired_range_compression_bootstrap_lb90_positive"])
        self.assertFalse(result["gate_pass"])

    def test_symbol_breadth_is_nonvacuous_gate(self):
        panel, blueprints = self._manual_partition([0.06] * 12, symbols=("AAPL",))
        result = evaluate_train_partition(
            panel,
            blueprints,
            min_pairs=10,
            min_symbols=2,
            bootstrap_samples=500,
        )
        self.assertTrue(result["gate_checks"]["minimum_train_pairs"])
        self.assertFalse(result["gate_checks"]["minimum_symbol_breadth"])
        self.assertFalse(result["gate_pass"])

    def test_payload_reserves_holdout_and_carries_complete_stack(self):
        panel = self._selection_panel(periods=620)
        payload = run_lab_from_panel(
            panel,
            symbols=list(panel.columns),
            provenance={"fixture": True},
            train_fraction=0.60,
            shock_return_min=0.03,
            hv_ratio_min=0.10,
            control_abs_return_max=0.01,
            max_match_distance_sessions=252,
            max_return_20d_distance=0.50,
            max_hv_ratio_distance=5.0,
            max_sma20_distance_gap=0.50,
            min_train_pairs=1,
            min_train_symbols=1,
            bootstrap_samples=500,
        )
        self.assertIn(payload["strategy_outcome"], {"STRATEGY_ADVANCED", "FAMILY_CLOSED"})
        self.assertFalse(payload["funnel_claim_f2"])
        self.assertFalse(payload["l1_claim"])
        self.assertFalse(payload["untouched_holdout"]["outcome_metrics_read"])
        self.assertNotIn("pairs", payload["untouched_holdout"])
        self.assertEqual(payload["option_stage"]["pricing_calls"], 0)
        self.assertEqual(payload["structure"], "conditional_iron_butterfly_not_yet_priced")
        self.assertEqual(payload["capital_fit_usd"], 200.0)
        self.assertEqual(payload["one_lot_max_loss_usd"], 200.0)
        self.assertEqual(payload["max_lots"], 1)
        self.assertEqual(payload["forecast_type"], "range_bound")
        self.assertTrue(payload["stand_aside_rule"])
        self.assertIn("positive theta", payload["greek_exposures"]["intended"])
        self.assertIn("underlying-only", payload["claim_scope"])
        self.assertIn("does not establish theta/vega", payload["horizon_alignment"])
        json.dumps(payload, allow_nan=False)

    def test_flat_panel_closes_with_strict_json_nulls(self):
        index = pd.bdate_range("2020-01-02", periods=400)
        symbols = ["AAPL", "AMD", "META", "GOOGL"]
        panel = pd.DataFrame({symbol: 100.0 for symbol in symbols}, index=index)
        payload = run_lab_from_panel(
            panel,
            symbols=symbols,
            provenance={"fixture": True},
            min_train_pairs=2,
            min_train_symbols=2,
            bootstrap_samples=100,
        )
        self.assertEqual(payload["strategy_outcome"], "FAMILY_CLOSED")
        self.assertEqual(payload["train"]["n_pairs"], 0)
        self.assertIsNone(payload["train"]["paired_range_compression_mean"])
        self.assertIsNone(payload["train"]["paired_range_compression_bootstrap_lb90"])
        json.dumps(payload, allow_nan=False)

    def test_nonfinite_panel_fails_closed(self):
        panel = self._selection_panel()
        panel.iloc[200, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            build_matched_blueprints(panel)

    def test_cli_help_exposes_frozen_inputs(self):
        completed = subprocess.run(
            [sys.executable, "scripts/post_shock_range_compression_train_lab.py", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--symbols", completed.stdout)
        self.assertIn("--start", completed.stdout)
        self.assertIn("--end", completed.stdout)
        self.assertIn("--out", completed.stdout)


if __name__ == "__main__":
    unittest.main()

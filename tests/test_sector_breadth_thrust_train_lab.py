import unittest

import numpy as np
import pandas as pd

from scripts.sector_breadth_thrust_train_lab import (
    DEFAULT_SYMBOLS,
    build_breadth_thrust_blueprints,
    evaluate_train_partition,
    run_lab_from_panel,
)


class SectorBreadthThrustTrainLabTest(unittest.TestCase):
    @staticmethod
    def _panel(periods: int = 420) -> pd.DataFrame:
        index = pd.bdate_range("2018-01-02", periods=periods)
        symbols = ["SPY", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
        rng = np.random.default_rng(20260715)
        data = {}
        for offset, symbol in enumerate(symbols):
            returns = rng.normal(0.0004 + offset * 0.00001, 0.006, periods)
            data[symbol] = 100.0 * np.exp(np.cumsum(returns))
        return pd.DataFrame(data, index=index)

    def test_blueprints_use_completed_signal_and_next_session_entry(self):
        panel = self._panel()
        rows = build_breadth_thrust_blueprints(
            panel,
            breadth_min=0.0,
            breadth_change_min=-1.0,
            control_breadth_change_max=1.0,
            max_match_distance_sessions=252,
            max_return_60d_distance=2.0,
            max_hv_ratio_distance=10.0,
            max_breadth_distance=1.0,
        )
        self.assertGreater(len(rows), 1)
        first = rows[0]
        self.assertLess(first["control_exit_date"], first["treated_signal_date"])
        self.assertLess(first["treated_signal_date"], first["treated_entry_date"])
        self.assertLess(first["treated_entry_date"], first["treated_exit_date"])
        self.assertEqual(first["treated_feature_max_date"], first["treated_signal_date"])
        self.assertEqual(first["control_feature_max_date"], first["control_signal_date"])

    @staticmethod
    def _manual_partition(paired_excess: list[float]) -> tuple[pd.DataFrame, list[dict]]:
        panel = SectorBreadthThrustTrainLabTest._panel(periods=620)
        rows = []
        for index, excess in enumerate(paired_excess):
            base = 120 + index * 24
            control_signal = panel.index[base]
            control_entry = panel.index[base + 1]
            control_exit = panel.index[base + 11]
            treated_signal = panel.index[base + 12]
            treated_entry = panel.index[base + 13]
            treated_exit = panel.index[base + 23]
            panel.loc[control_exit, "SPY"] = panel.loc[control_entry, "SPY"] * 1.002
            panel.loc[treated_exit, "SPY"] = panel.loc[treated_entry, "SPY"] * (1.002 + excess)
            rows.append(
                {
                    "control_signal_date": control_signal,
                    "control_feature_max_date": control_signal,
                    "control_entry_date": control_entry,
                    "control_exit_date": control_exit,
                    "control_breadth": 9 / 11,
                    "control_breadth_change": 0.0,
                    "control_spy_ret_60": 0.10,
                    "control_spy_hv_ratio": 1.0,
                    "treated_signal_date": treated_signal,
                    "treated_feature_max_date": treated_signal,
                    "treated_entry_date": treated_entry,
                    "treated_exit_date": treated_exit,
                    "treated_breadth": 1.0,
                    "treated_breadth_change": 3 / 11,
                    "treated_spy_ret_60": 0.10,
                    "treated_spy_hv_ratio": 1.0,
                    "calendar_distance_sessions": 12,
                    "return_60d_match_distance": 0.0,
                    "hv_ratio_match_distance": 0.0,
                    "breadth_match_distance": 2 / 11,
                }
            )
        return panel, rows

    def test_train_gate_requires_absolute_relative_uncertainty_and_tail_quality(self):
        panel, rows = self._manual_partition([0.012] * 20)
        result = evaluate_train_partition(
            panel,
            rows,
            min_pairs=20,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertTrue(result["gate_pass"], result["gate_checks"])
        self.assertGreater(result["treated_mean_return_after_cost"], 0.005)
        self.assertGreaterEqual(result["treated_positive_frequency_after_cost"], 0.55)
        self.assertGreaterEqual(result["paired_excess_mean"], 0.0025)
        self.assertGreater(result["paired_excess_bootstrap_lb90"], 0.0)
        self.assertGreaterEqual(result["treated_worst_decile_return_after_cost"], -0.03)
        self.assertEqual(result["integrity_violations"], [])

    def test_run_lab_keeps_holdout_outcomes_sealed_and_closes_when_specificity_fails(self):
        panel, rows = self._manual_partition([0.0] * 20)
        payload = run_lab_from_panel(
            panel,
            provenance={symbol: {"sha256": symbol} for symbol in DEFAULT_SYMBOLS},
            frozen_blueprints=rows,
            train_fraction=0.60,
            min_pairs=8,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertFalse(payload["holdout"]["outcome_metrics_read"])
        self.assertFalse(payload["holdout"]["simulation_run"])
        self.assertNotIn("pairs", payload["holdout"])
        self.assertEqual(payload["strategy_outcome"], "FAMILY_CLOSED")
        self.assertIn("paired_excess", payload["dominant_failure_mechanism"])
        self.assertFalse(payload["f2_or_l1_claim"])
        self.assertFalse(payload["f2_claim"])
        self.assertFalse(payload["l1_or_capital_seat_claim"])
        self.assertIs(payload["strategy_advancement"], False)
        self.assertIn("closed at F0", payload["strategy_advancement_summary"])
        self.assertEqual(payload["layered_edge_stack"]["max_loss_usd"], 200.0)
        self.assertEqual(payload["train"]["worst_decile_n"], 2)
        self.assertEqual(
            sum(payload["train"]["signal_year_counts"].values()),
            payload["train"]["n_pairs"],
        )
        match_quality = payload["train"]["match_quality"]
        self.assertEqual(match_quality["calendar_distance_sessions"]["count"], 12)
        self.assertEqual(match_quality["calendar_distance_sessions"]["median"], 12.0)
        self.assertEqual(match_quality["breadth_match_distance"]["max"], 2 / 11)
        self.assertIn("coarse", payload["methodology_boundaries"]["matching"])
        self.assertIn("may not be repaired post hoc", payload["methodology_boundaries"]["history_floor"])
        self.assertIn("thin", payload["methodology_boundaries"]["tail"])
        self.assertIn("does not validate", payload["methodology_boundaries"]["horizon_option_alignment"])
        self.assertIn("same_panel_retunes", payload["quarantine"]["scope"])

    def test_holdout_price_perturbation_cannot_change_train_or_holdout_identity(self):
        panel, rows = self._manual_partition([0.012] * 20)
        baseline = run_lab_from_panel(
            panel,
            provenance={},
            frozen_blueprints=rows,
            min_pairs=8,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        mutated = panel.copy()
        holdout_start = pd.Timestamp(baseline["holdout"]["first_treated_signal_date"])
        mutated.loc[mutated.index > holdout_start, "SPY"] *= 7.0
        replay = run_lab_from_panel(
            mutated,
            provenance={},
            frozen_blueprints=rows,
            min_pairs=8,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertEqual(baseline["train"], replay["train"])
        self.assertEqual(baseline["holdout"], replay["holdout"])

    def test_chronology_violation_fails_closed(self):
        panel, rows = self._manual_partition([0.012] * 20)
        rows[0]["treated_feature_max_date"] = rows[0]["treated_entry_date"]
        result = evaluate_train_partition(
            panel,
            rows,
            min_pairs=20,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertFalse(result["gate_pass"])
        self.assertIn("chronology:0", result["integrity_violations"])
        self.assertFalse(result["gate_checks"]["zero_integrity_violations"])


if __name__ == "__main__":
    unittest.main()

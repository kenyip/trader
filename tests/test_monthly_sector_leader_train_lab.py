import unittest

import numpy as np
import pandas as pd

from scripts.monthly_sector_leader_train_lab import (
    SECTOR_SYMBOLS,
    build_monthly_leader_blueprints,
    evaluate_train_partition,
    run_lab_from_panel,
)


class MonthlySectorLeaderTrainLabTest(unittest.TestCase):
    @staticmethod
    def _panel(periods: int = 900) -> pd.DataFrame:
        index = pd.bdate_range("2018-01-02", periods=periods)
        rng = np.random.default_rng(20260716)
        data = {}
        for offset, symbol in enumerate(SECTOR_SYMBOLS):
            returns = rng.normal(0.00025 + offset * 0.00002, 0.006, periods)
            data[symbol] = 100.0 * np.exp(np.cumsum(returns))
        return pd.DataFrame(data, index=index)

    def test_blueprints_use_month_end_completed_features_and_next_session_entry(self):
        panel = self._panel()
        rows = build_monthly_leader_blueprints(
            panel,
            min_leader_return_63=-1.0,
            min_leader_median_spread=-1.0,
            require_above_sma=False,
        )
        self.assertGreater(len(rows), 10)
        for row in rows:
            signal = pd.Timestamp(row["signal_date"])
            entry = pd.Timestamp(row["entry_date"])
            exit_date = pd.Timestamp(row["exit_date"])
            signal_position = panel.index.get_loc(signal)
            entry_position = panel.index.get_loc(entry)
            exit_position = panel.index.get_loc(exit_date)
            self.assertEqual(row["feature_max_date"], row["signal_date"])
            self.assertEqual(entry_position, signal_position + 1)
            self.assertEqual(exit_position, entry_position + 20)
            self.assertNotEqual(signal.month, panel.index[signal_position + 1].month)
            self.assertIn(row["leader"], SECTOR_SYMBOLS)
            self.assertEqual(
                sorted(row["peers"]),
                sorted(set(SECTOR_SYMBOLS) - {row["leader"]}),
            )

    def test_first_identity_cannot_be_changed_by_future_price_perturbation(self):
        panel = self._panel()
        baseline = build_monthly_leader_blueprints(
            panel,
            min_leader_return_63=-1.0,
            min_leader_median_spread=-1.0,
            require_above_sma=False,
        )
        self.assertGreater(len(baseline), 10)
        first_signal = pd.Timestamp(baseline[0]["signal_date"])
        mutated = panel.copy()
        future = mutated.index > first_signal
        factors = np.linspace(0.25, 4.0, int(future.sum()))
        mutated.loc[future, :] = mutated.loc[future, :].multiply(factors, axis=0)
        replay = build_monthly_leader_blueprints(
            mutated,
            min_leader_return_63=-1.0,
            min_leader_median_spread=-1.0,
            require_above_sma=False,
        )
        identity_fields = ["signal_date", "feature_max_date", "entry_date", "exit_date", "leader", "peers"]
        self.assertEqual(
            {field: baseline[0][field] for field in identity_fields},
            {field: replay[0][field] for field in identity_fields},
        )

    @staticmethod
    def _manual_partition(excesses: list[float]) -> tuple[pd.DataFrame, list[dict]]:
        panel = MonthlySectorLeaderTrainLabTest._panel(periods=1900)
        rows = []
        month_end_positions = [
            position
            for position in range(200, len(panel) - 22)
            if panel.index[position].month != panel.index[position + 1].month
        ]
        selected_positions = month_end_positions[::2][: len(excesses)]
        if len(selected_positions) != len(excesses):
            raise AssertionError("synthetic panel lacks enough separated month ends")
        for index, (excess, signal_position) in enumerate(zip(excesses, selected_positions)):
            signal = panel.index[signal_position]
            entry = panel.index[signal_position + 1]
            exit_date = panel.index[signal_position + 21]
            leader = SECTOR_SYMBOLS[index % len(SECTOR_SYMBOLS)]
            peers = [symbol for symbol in SECTOR_SYMBOLS if symbol != leader]
            for peer in peers:
                panel.loc[exit_date, peer] = panel.loc[entry, peer] * 1.006
            panel.loc[exit_date, leader] = panel.loc[entry, leader] * (1.006 + excess)
            rows.append(
                {
                    "signal_date": signal,
                    "feature_max_date": signal,
                    "entry_date": entry,
                    "exit_date": exit_date,
                    "leader": leader,
                    "peers": peers,
                    "leader_return_63": 0.12,
                    "median_return_63": 0.05,
                    "leader_median_spread": 0.07,
                    "leader_signal_close": 112.0,
                    "leader_sma_126": 100.0,
                }
            )
        return panel, rows

    def test_train_gate_requires_absolute_relative_uncertainty_and_tail_quality(self):
        panel, rows = self._manual_partition([0.012] * 24)
        result = evaluate_train_partition(
            panel,
            rows,
            min_signals=20,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertTrue(result["gate_pass"], result["gate_checks"])
        self.assertGreater(result["leader_mean_return_after_cost"], 0.005)
        self.assertGreaterEqual(result["leader_positive_frequency_after_cost"], 0.55)
        self.assertGreaterEqual(result["paired_excess_mean"], 0.003)
        self.assertGreater(result["paired_excess_bootstrap_lb90"], 0.0)
        self.assertGreaterEqual(result["leader_worst_decile_return_after_cost"], -0.08)
        self.assertEqual(result["integrity_violations"], [])

    def test_run_lab_keeps_holdout_outcomes_sealed_and_closes_failed_specificity(self):
        panel, rows = self._manual_partition([0.0] * 24)
        payload = run_lab_from_panel(
            panel,
            provenance={symbol: {"sha256": symbol} for symbol in SECTOR_SYMBOLS},
            frozen_blueprints=rows,
            train_fraction=0.60,
            min_signals=12,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertEqual(payload["strategy_outcome"], "FAMILY_CLOSED")
        self.assertFalse(payload["strategy_advancement"])
        self.assertFalse(payload["holdout"]["outcome_metrics_read"])
        self.assertFalse(payload["holdout"]["simulation_run"])
        self.assertNotIn("rows", payload["holdout"])
        self.assertIn("paired_excess", payload["dominant_failure_mechanism"])
        self.assertFalse(payload["f2_or_l1_claim"])
        self.assertEqual(payload["layered_edge_stack"]["max_loss_usd"], 200.0)
        self.assertIn("same_panel_retunes", payload["quarantine"]["scope"])

    def test_holdout_price_perturbation_cannot_change_train_or_holdout_identity(self):
        panel, rows = self._manual_partition([0.012] * 24)
        baseline = run_lab_from_panel(
            panel,
            provenance={},
            frozen_blueprints=rows,
            train_fraction=0.60,
            min_signals=12,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        mutated = panel.copy()
        holdout_start = pd.Timestamp(baseline["holdout"]["first_signal_date"])
        mutated.loc[mutated.index > holdout_start, :] *= 7.0
        replay = run_lab_from_panel(
            mutated,
            provenance={},
            frozen_blueprints=rows,
            train_fraction=0.60,
            min_signals=12,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertEqual(baseline["train"], replay["train"])
        self.assertEqual(baseline["holdout"], replay["holdout"])

    def test_chronology_violation_fails_closed(self):
        panel, rows = self._manual_partition([0.012] * 24)
        rows[0]["feature_max_date"] = rows[0]["entry_date"]
        result = evaluate_train_partition(
            panel,
            rows,
            min_signals=20,
            min_signal_years=1,
            bootstrap_samples=500,
        )
        self.assertFalse(result["gate_pass"])
        self.assertIn("chronology:0", result["integrity_violations"])
        self.assertFalse(result["gate_checks"]["zero_integrity_violations"])

    def test_panel_population_fails_closed(self):
        panel = self._panel().drop(columns=[SECTOR_SYMBOLS[-1]])
        with self.assertRaisesRegex(ValueError, "exactly match"):
            build_monthly_leader_blueprints(panel)


if __name__ == "__main__":
    unittest.main()

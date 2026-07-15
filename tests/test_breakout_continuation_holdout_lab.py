import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.breakout_continuation_holdout_lab import (
    build_concentration_diagnostics,
    evaluate_holdout_partition,
    load_frozen_panel,
    run_holdout_from_panel,
    verify_frozen_population,
)
from scripts.breakout_continuation_train_lab import run_lab_from_panel


class BreakoutContinuationHoldoutLabTest(unittest.TestCase):
    @staticmethod
    def _trend_panel(periods: int = 520) -> pd.DataFrame:
        index = pd.bdate_range("2019-01-02", periods=periods)
        base = 100.0 * np.exp(np.arange(periods) * 0.0006)
        panel = pd.DataFrame({"AAPL": base.copy(), "MSFT": base * 1.1}, index=index)
        for symbol, offset in (("AAPL", 0), ("MSFT", 8)):
            for position in (145 + offset, 225 + offset, 305 + offset, 385 + offset, 465 + offset):
                if position < periods:
                    panel.loc[index[position], symbol] = panel.loc[index[position - 1], symbol] * 1.05
        return panel

    def test_holdout_gate_uses_holdout_labels_and_passes_positive_fixture(self):
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

        result = evaluate_holdout_partition(
            panel,
            blueprints,
            min_pairs=10,
            min_symbols=1,
            round_trip_cost_bps=20.0,
            bootstrap_samples=500,
        )

        self.assertTrue(result["gate_pass"])
        self.assertIn("minimum_holdout_pairs", result["gate_checks"])
        self.assertNotIn("minimum_train_pairs", result["gate_checks"])
        self.assertGreater(result["paired_excess_bootstrap_lb90"], 0.0)
        self.assertEqual(result["integrity_violations"], [])

    def test_frozen_population_verifier_accepts_exact_train_prefix_and_partition(self):
        index = pd.bdate_range("2022-01-03", periods=40)
        reconstructed = []
        for position, symbol in ((2, "AAPL"), (12, "MSFT"), (22, "AAPL")):
            reconstructed.append(
                {
                    "symbol": symbol,
                    "control_signal_date": index[position],
                    "control_entry_date": index[position + 1],
                    "control_exit_date": index[position + 3],
                    "treated_signal_date": index[position + 5],
                    "treated_entry_date": index[position + 6],
                    "treated_exit_date": index[position + 8],
                    "calendar_distance_sessions": 5,
                    "return_20d_match_distance": 0.01,
                    "hv_20d_match_distance": 0.02,
                }
            )
        frozen = {
            "selection_diagnostics": {
                "matched_blueprints": 3,
                "train_blueprints": 1,
                "holdout_blueprints": 2,
            },
            "train": {
                "pairs": [
                    {
                        key: (
                            str(value.date())
                            if isinstance(value, pd.Timestamp)
                            else value
                        )
                        for key, value in reconstructed[0].items()
                    }
                ]
            },
            "untouched_holdout": {
                "n_blueprints": 2,
                "outcome_metrics_read": False,
                "simulation_run": False,
            },
        }

        result = verify_frozen_population(frozen, reconstructed, train_fraction=0.60)

        self.assertTrue(result["exact_population_reproduced"])
        self.assertEqual(result["train_blueprints"], 1)
        self.assertEqual(result["holdout_blueprints"], 2)

    def test_frozen_population_verifier_rejects_changed_train_identity(self):
        index = pd.bdate_range("2022-01-03", periods=20)
        reconstructed = [
            {
                "symbol": "AAPL",
                "control_signal_date": index[1],
                "control_entry_date": index[2],
                "control_exit_date": index[4],
                "treated_signal_date": index[6],
                "treated_entry_date": index[7],
                "treated_exit_date": index[9],
                "calendar_distance_sessions": 5,
                "return_20d_match_distance": 0.01,
                "hv_20d_match_distance": 0.02,
            },
            {
                "symbol": "MSFT",
                "control_signal_date": index[10],
                "control_entry_date": index[11],
                "control_exit_date": index[13],
                "treated_signal_date": index[15],
                "treated_entry_date": index[16],
                "treated_exit_date": index[18],
                "calendar_distance_sessions": 5,
                "return_20d_match_distance": 0.01,
                "hv_20d_match_distance": 0.02,
            },
        ]
        frozen_train = {
            key: (str(value.date()) if isinstance(value, pd.Timestamp) else value)
            for key, value in reconstructed[0].items()
        }
        frozen_train["treated_exit_date"] = str(index[10].date())
        frozen = {
            "selection_diagnostics": {
                "matched_blueprints": 2,
                "train_blueprints": 1,
                "holdout_blueprints": 1,
            },
            "train": {"pairs": [frozen_train]},
            "untouched_holdout": {
                "n_blueprints": 1,
                "outcome_metrics_read": False,
                "simulation_run": False,
            },
        }

        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            verify_frozen_population(frozen, reconstructed, train_fraction=0.60)

    def test_concentration_diagnostics_cover_symbols_leave_one_out_and_tertiles(self):
        pairs = []
        symbols = ["AAPL", "MSFT", "TSLA"]
        dates = pd.bdate_range("2023-01-03", periods=12)
        for index, date in enumerate(dates):
            symbol = symbols[index % len(symbols)]
            control = 0.005 * ((index % 2) - 0.5)
            excess = 0.01 + 0.001 * (index % 3)
            pairs.append(
                {
                    "symbol": symbol,
                    "treated_signal_date": str(date.date()),
                    "treated_return_after_cost": control + excess,
                    "control_return_after_cost": control,
                    "paired_excess_return": excess,
                }
            )

        diagnostics = build_concentration_diagnostics(pairs, bootstrap_samples=500)

        self.assertEqual(sorted(diagnostics["per_symbol"]), sorted(symbols))
        self.assertEqual(sorted(diagnostics["leave_one_symbol_out"]), sorted(symbols))
        self.assertEqual(len(diagnostics["chronological_tertiles"]), 3)
        self.assertEqual(sum(row["n_pairs"] for row in diagnostics["chronological_tertiles"]), 12)
        self.assertEqual(diagnostics["role"], "mandatory_non_gating_context")

    def test_end_to_end_one_shot_holdout_emits_closed_decision_and_no_option_authority(self):
        panel = self._trend_panel()
        frozen = run_lab_from_panel(
            panel,
            symbols=list(panel.columns),
            provenance={"fixture": True},
            train_fraction=0.60,
            breakout_lookback_sessions=20,
            trend_lookback_sessions=60,
            min_train_pairs=1,
            min_train_symbols=1,
            bootstrap_samples=500,
        )
        frozen["strategy_outcome"] = "STRATEGY_ADVANCED"
        frozen["funnel_stage_after"] = "F1_TRAIN"

        payload = run_holdout_from_panel(frozen, panel, bootstrap_samples=500)

        self.assertIn(payload["strategy_outcome"], {"STRATEGY_ADVANCED", "FAMILY_CLOSED"})
        self.assertTrue(payload["holdout"]["outcome_metrics_read"])
        self.assertTrue(payload["holdout"]["simulation_run"])
        self.assertIn("concentration_diagnostics", payload["holdout"])
        self.assertEqual(payload["option_stage"]["pricing_calls"], 0)
        self.assertFalse(payload["authority"]["l1_or_capital_seat"])
        self.assertFalse(payload["authority"]["paper_or_higher"])
        self.assertEqual(
            payload["funnel_claim_f2"],
            payload["funnel_stage_after"] == "F2_UNTOUCHED_HOLDOUT",
        )
        self.assertFalse(payload["l1_claim"])
        self.assertNotIn("f2_or_l1_claim", payload)
        self.assertTrue(payload["population_verification"]["exact_population_reproduced"])
        self.assertIn("minimum_holdout_pairs", payload["holdout"]["gate_checks"])
        freeze = payload["next_option_freeze_constraints"]
        self.assertEqual(freeze["freeze_partition"], "original_development_blueprints_only")
        self.assertEqual(
            freeze["freeze_blueprints"],
            payload["population_verification"]["train_blueprints"],
        )
        self.assertEqual(freeze["opened_holdout_role"], "inspected_secondary_stress_only")
        self.assertEqual(freeze["hard_time_stop_sessions"], frozen["config"]["forward_sessions"])
        self.assertEqual(freeze["primary_metric"], "absolute_after_cost_option_pnl_and_path_risk")
        self.assertFalse(freeze["paired_underlying_excess_can_rescue_failure"])
        self.assertFalse(freeze["hold_to_expiry_is_primary_exit"])
        self.assertTrue(freeze["missing_listing_fails_closed"])
        __import__("json").dumps(payload, allow_nan=False)

    def test_cli_exposes_frozen_artifact_and_output_path(self):
        completed = subprocess.run(
            [sys.executable, "scripts/breakout_continuation_holdout_lab.py", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--frozen", completed.stdout)
        self.assertIn("--out", completed.stdout)
        self.assertIn("one-shot", completed.stdout.lower())

    def test_frozen_panel_loader_fails_closed_on_source_hash_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = {}
            for symbol, multiplier in (("AAPL", 1.0), ("MSFT", 1.1)):
                path = root / f"{symbol}.csv"
                path.write_text(
                    "Date,close\n2024-01-02," + str(100.0 * multiplier) +
                    "\n2024-01-03," + str(101.0 * multiplier) + "\n",
                    encoding="utf-8",
                )
                sources[symbol] = {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "rows": 2,
                    "start": "2024-01-02",
                    "end": "2024-01-03",
                }
            frozen = {
                "config": {"symbols": ["AAPL", "MSFT"]},
                "data_provenance": {
                    "sources": sources,
                    "common_panel": {
                        "rows": 2,
                        "start": "2024-01-02",
                        "end": "2024-01-03",
                    },
                },
            }
            panel, verification = load_frozen_panel(frozen, repo_root=root)
            self.assertEqual(panel.shape, (2, 2))
            self.assertTrue(verification["all_source_hashes_match"])

            (root / "MSFT.csv").write_text(
                "Date,close\n2024-01-02,99\n2024-01-03,100\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                load_frozen_panel(frozen, repo_root=root)


if __name__ == "__main__":
    unittest.main()

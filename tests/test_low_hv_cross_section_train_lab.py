import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.low_hv_cross_section_train_lab import (
    assemble_close_panel,
    build_monthly_blueprints,
    evaluate_train_partition,
    load_adjusted_history,
    run_lab_from_panel,
    split_blueprints,
)


class LowHvCrossSectionTrainLabTest(unittest.TestCase):
    @staticmethod
    def _panel(periods: int = 180) -> pd.DataFrame:
        index = pd.bdate_range("2023-01-02", periods=periods)
        pattern = np.resize(np.array([1.0, -1.0, 0.5, -0.5]), periods)
        scales = {
            "A": 0.001,
            "B": 0.002,
            "C": 0.003,
            "D": 0.006,
            "E": 0.010,
            "F": 0.014,
        }
        return pd.DataFrame(
            {
                symbol: 100.0 * np.exp(np.cumsum(pattern * scale))
                for symbol, scale in scales.items()
            },
            index=index,
        )

    def test_monthly_blueprints_use_prior_completed_hv_and_disjoint_controls(self):
        panel = self._panel()

        blueprints = build_monthly_blueprints(
            panel,
            hv_lookback=20,
            forward_sessions=5,
            quantile_count=2,
        )

        self.assertGreaterEqual(len(blueprints), 4)
        first = blueprints[0]
        self.assertLess(first["rank_date"], first["entry_date"])
        self.assertLess(first["entry_date"], first["exit_date"])
        self.assertEqual(first["low_hv_symbols"], ["A", "B"])
        self.assertEqual(first["high_hv_symbols"], ["E", "F"])
        self.assertTrue(set(first["low_hv_symbols"]).isdisjoint(first["high_hv_symbols"]))

        shocked = panel.copy()
        shocked.loc[first["entry_date"], "A"] *= 1.50
        rebuilt = build_monthly_blueprints(
            shocked,
            hv_lookback=20,
            forward_sessions=5,
            quantile_count=2,
        )
        rebuilt_first = rebuilt[0]
        self.assertEqual(first["rank_date"], rebuilt_first["rank_date"])
        self.assertEqual(first["low_hv_symbols"], rebuilt_first["low_hv_symbols"])
        self.assertEqual(first["high_hv_symbols"], rebuilt_first["high_hv_symbols"])

    def test_train_gate_requires_positive_low_hv_return_and_bootstrapped_control_edge(self):
        index = pd.bdate_range("2023-01-02", periods=140)
        panel = pd.DataFrame(
            {
                "A": 100.0 * np.exp(np.arange(len(index)) * 0.0015),
                "B": 100.0 * np.exp(np.arange(len(index)) * 0.0010),
                "E": 100.0 * np.exp(np.arange(len(index)) * -0.0005),
                "F": 100.0 * np.exp(np.arange(len(index)) * -0.0010),
            },
            index=index,
        )
        blueprints = []
        for start in range(10, 110, 12):
            blueprints.append(
                {
                    "rank_date": index[start - 1],
                    "feature_max_date": index[start - 1],
                    "entry_date": index[start],
                    "exit_date": index[start + 5],
                    "low_hv_symbols": ["A", "B"],
                    "high_hv_symbols": ["E", "F"],
                    "low_hv_values": {"A": 0.10, "B": 0.12},
                    "high_hv_values": {"E": 0.30, "F": 0.40},
                }
            )

        train, holdout = split_blueprints(blueprints, train_fraction=0.60)
        result = evaluate_train_partition(
            panel,
            train,
            min_episodes=5,
            bootstrap_samples=500,
        )

        self.assertTrue(result["gate_pass"])
        self.assertGreater(result["low_hv_mean_return"], 0.0)
        self.assertGreater(result["paired_excess_mean"], 0.0)
        self.assertGreater(result["paired_excess_bootstrap_lb90"], 0.0)
        self.assertEqual(result["n_episodes"], len(train))
        self.assertGreater(len(holdout), 0)
        self.assertFalse(any("return" in key for key in holdout[0]))
        json.dumps(result, allow_nan=False)

    def test_payload_advances_train_only_without_reading_holdout_outcomes(self):
        periods = 520
        index = pd.bdate_range("2022-01-03", periods=periods)
        pattern = np.resize(np.array([1.0, -1.0, 0.5, -0.5]), periods)
        panel = pd.DataFrame(
            {
                "A": 100.0 * np.exp(np.cumsum(0.0010 + pattern * 0.0010)),
                "B": 100.0 * np.exp(np.cumsum(0.0008 + pattern * 0.0020)),
                "C": 100.0 * np.exp(np.cumsum(0.0001 + pattern * 0.0040)),
                "D": 100.0 * np.exp(np.cumsum(0.0000 + pattern * 0.0060)),
                "E": 100.0 * np.exp(np.cumsum(-0.0005 + pattern * 0.0100)),
                "F": 100.0 * np.exp(np.cumsum(-0.0008 + pattern * 0.0140)),
            },
            index=index,
        )

        payload = run_lab_from_panel(
            panel,
            symbols=list(panel.columns),
            provenance={symbol: {"fixture": True} for symbol in panel.columns},
            train_fraction=0.60,
            hv_lookback=20,
            forward_sessions=5,
            quantile_count=2,
            min_train_episodes=5,
            bootstrap_samples=500,
        )

        self.assertEqual(payload["strategy_outcome"], "STRATEGY_ADVANCED")
        self.assertEqual(payload["funnel_stage_after"], "F1_TRAIN")
        self.assertFalse(payload["f2_or_l1_claim"])
        self.assertFalse(payload["option_stage"]["pricing_run"])
        self.assertEqual(payload["max_lots"], 1)
        self.assertEqual(payload["one_lot_max_loss_usd"], 100.0)
        self.assertGreater(payload["untouched_holdout"]["n_blueprints"], 0)
        self.assertNotIn("episodes", payload["untouched_holdout"])
        encoded = json.dumps(payload, allow_nan=False)
        self.assertNotIn("holdout_return", encoded)

    def test_payload_closes_when_absolute_low_hv_drift_is_positive_but_excess_is_not(self):
        periods = 520
        index = pd.bdate_range("2022-01-03", periods=periods)
        pattern = np.resize(np.array([1.0, -1.0, 0.5, -0.5]), periods)
        panel = pd.DataFrame(
            {
                "A": 100.0 * np.exp(np.cumsum(0.0004 + pattern * 0.0010)),
                "B": 100.0 * np.exp(np.cumsum(0.0005 + pattern * 0.0020)),
                "C": 100.0 * np.exp(np.cumsum(0.0008 + pattern * 0.0040)),
                "D": 100.0 * np.exp(np.cumsum(0.0010 + pattern * 0.0060)),
                "E": 100.0 * np.exp(np.cumsum(0.0015 + pattern * 0.0100)),
                "F": 100.0 * np.exp(np.cumsum(0.0018 + pattern * 0.0140)),
            },
            index=index,
        )

        payload = run_lab_from_panel(
            panel,
            symbols=list(panel.columns),
            provenance={symbol: {"fixture": True} for symbol in panel.columns},
            train_fraction=0.60,
            hv_lookback=20,
            forward_sessions=4,
            quantile_count=2,
            min_train_episodes=5,
            bootstrap_samples=500,
        )

        self.assertGreater(payload["train"]["low_hv_mean_return"], 0.0)
        self.assertLess(payload["train"]["paired_excess_mean"], 0.0)
        self.assertTrue(payload["train"]["gate_checks"]["positive_low_hv_mean_return"])
        self.assertFalse(payload["train"]["gate_checks"]["positive_paired_excess_mean"])
        self.assertFalse(payload["train"]["gate_pass"])
        self.assertEqual(payload["strategy_outcome"], "FAMILY_CLOSED")
        self.assertEqual(payload["closed_family"], "MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT")
        self.assertIn("positive absolute train drift", payload["dominant_failure_mechanism"])

    def test_adjusted_history_cache_is_validated_and_reused(self):
        index = pd.bdate_range("2024-01-02", periods=80)
        downloaded = pd.DataFrame(
            {
                "Open": np.linspace(99.0, 109.0, len(index)),
                "High": np.linspace(101.0, 111.0, len(index)),
                "Low": np.linspace(98.0, 108.0, len(index)),
                "Close": np.linspace(100.0, 110.0, len(index)),
                "Volume": np.full(len(index), 1_000_000),
            },
            index=index,
        )
        downloaded.loc[index[7], "Close"] = np.nextafter(103.14159265358979, np.inf)
        calls = []

        def downloader(*args, **kwargs):
            calls.append((args, kwargs))
            return downloaded

        with tempfile.TemporaryDirectory() as directory:
            first, first_meta = load_adjusted_history(
                "AAPL",
                cache_dir=Path(directory),
                start="2024-01-01",
                end="2024-12-31",
                downloader=downloader,
            )
            second, second_meta = load_adjusted_history(
                "AAPL",
                cache_dir=Path(directory),
                start="2024-01-01",
                end="2024-12-31",
                downloader=lambda *args, **kwargs: self.fail("cache should avoid download"),
            )

        self.assertEqual(len(calls), 1)
        pd.testing.assert_series_equal(first, second, check_exact=True)
        self.assertEqual(first_meta["sha256"], second_meta["sha256"])
        self.assertEqual(first_meta["adjustment_semantics"], "yfinance auto_adjust=True")
        self.assertEqual(first_meta["rows"], 80)

    def test_adjusted_history_discards_only_trailing_unsettled_nan_rows(self):
        index = pd.bdate_range("2024-01-02", periods=80)
        trailing_nan = pd.DataFrame(
            {"Close": np.r_[np.linspace(100.0, 110.0, 79), np.nan]},
            index=index,
        )
        internal_nan = trailing_nan.copy()
        internal_nan.iloc[-1, 0] = 110.0
        internal_nan.iloc[20, 0] = np.nan

        with tempfile.TemporaryDirectory() as directory:
            series, meta = load_adjusted_history(
                "AAPL",
                cache_dir=Path(directory),
                start="2024-01-01",
                end="2024-12-31",
                downloader=lambda *args, **kwargs: trailing_nan,
            )
            self.assertEqual(len(series), 79)
            self.assertEqual(meta["discarded_trailing_unsettled_rows"], 1)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "finite"):
                load_adjusted_history(
                    "MSFT",
                    cache_dir=Path(directory),
                    start="2024-01-01",
                    end="2024-12-31",
                    downloader=lambda *args, **kwargs: internal_nan,
                )

    def test_close_panel_uses_complete_common_dates_and_preserves_symbol_order(self):
        index = pd.bdate_range("2024-01-02", periods=10)
        histories = {
            "B": pd.Series(np.arange(10) + 100.0, index=index, name="B"),
            "A": pd.Series(np.arange(9) + 200.0, index=index[1:], name="A"),
            "D": pd.Series(np.arange(10) + 300.0, index=index, name="D"),
            "C": pd.Series(np.arange(10) + 400.0, index=index, name="C"),
        }

        panel = assemble_close_panel(histories, symbols=["A", "B", "C", "D"], min_common_rows=9)

        self.assertEqual(list(panel.columns), ["A", "B", "C", "D"])
        self.assertEqual(len(panel), 9)
        self.assertEqual(panel.index[0], index[1])

        with self.assertRaisesRegex(ValueError, "common rows"):
            assemble_close_panel(histories, symbols=["A", "B", "C", "D"], min_common_rows=10)


if __name__ == "__main__":
    unittest.main()

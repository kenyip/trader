import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import scripts.spy_vrp_pcs_study as vrp


class SpyVrpPcsStudyTest(unittest.TestCase):
    def test_feature_warmup_and_forward_outcome_boundaries_are_exact(self):
        index = pd.bdate_range("2020-01-02", periods=260)
        returns = np.resize(np.array([0.004, -0.003, 0.006, -0.002]), len(index))
        close = 100.0 * np.exp(np.cumsum(returns))
        spy = self._spy(index, close)
        vix = pd.Series(20.0, index=index, name="vix")

        frame = vrp.build_feature_frame(spy, vix)

        self.assertTrue(pd.isna(frame.iloc[19]["rv20"]))
        self.assertTrue(np.isfinite(frame.iloc[20]["rv20"]))
        self.assertTrue(pd.isna(frame.iloc[198]["sma200"]))
        self.assertTrue(np.isfinite(frame.iloc[199]["sma200"]))
        self.assertTrue(np.isfinite(frame.iloc[-22]["subsequent_rv21"]))
        self.assertTrue(pd.isna(frame.iloc[-21]["subsequent_rv21"]))

        anchor = 210
        future_shock = spy.copy()
        future_shock.iloc[anchor + 21, future_shock.columns.get_loc("close")] *= 1.20
        shocked = vrp.build_feature_frame(future_shock, vix)
        self.assertAlmostEqual(frame.iloc[anchor]["rv20"], shocked.iloc[anchor]["rv20"])
        self.assertNotAlmostEqual(
            frame.iloc[anchor]["subsequent_rv21"],
            shocked.iloc[anchor]["subsequent_rv21"],
        )

    def test_episode_suppression_requires_more_than_21_sessions(self):
        index = pd.bdate_range("2020-01-02", periods=80)
        frame = self._mechanism_frame(index)
        for position in (5, 26, 27, 48, 49):
            frame.iloc[position, frame.columns.get_loc("signal")] = True
            frame.iloc[position, frame.columns.get_loc("vrp_ratio")] = 1.50
            frame.iloc[position, frame.columns.get_loc("mechanism_outcome")] = 5.0
        fold = {
            "name": "test",
            "assessment_start": str(index[0].date()),
            "assessment_end": str(index[-1].date()),
        }

        selected = vrp.select_treated_episodes(frame, fold)

        self.assertEqual(selected["signal_position"].tolist(), [5, 27, 49])
        self.assertTrue(
            all(
                following - previous > vrp.OUTCOME_SESSIONS
                for previous, following in zip(
                    selected["signal_position"], selected["signal_position"].iloc[1:]
                )
            )
        )

    def test_treated_outcome_must_fit_inside_assessment_window(self):
        index = pd.bdate_range("2020-01-02", periods=100)
        frame = self._mechanism_frame(index)
        position = 60
        frame.iloc[position, frame.columns.get_loc("signal")] = True
        frame.iloc[position, frame.columns.get_loc("vrp_ratio")] = 1.50
        frame.iloc[position, frame.columns.get_loc("mechanism_outcome")] = 5.0
        fold = {
            "name": "test",
            "assessment_start": "2020-01-02",
            "assessment_end": "2020-04-09",
        }

        selected = vrp.select_treated_episodes(frame, fold)

        self.assertTrue(selected.empty)

    def test_control_outcome_must_fit_inside_assessment_window(self):
        index = pd.bdate_range("2020-01-02", periods=100)
        frame = self._mechanism_frame(index)
        frame["positive_trend"] = False
        frame.iloc[10, frame.columns.get_loc("positive_trend")] = True
        frame.iloc[65, frame.columns.get_loc("positive_trend")] = True
        frame.iloc[10, frame.columns.get_loc("signal")] = True
        frame.iloc[10, frame.columns.get_loc("vrp_ratio")] = 1.50
        fold = {
            "name": "test",
            "assessment_start": "2020-01-02",
            "assessment_end": "2020-04-09",
        }
        treated = vrp.select_treated_episodes(frame, fold)

        controls = vrp.match_controls(frame, treated, fold)

        self.assertTrue(controls.empty)

    def test_control_matching_is_outcome_independent_without_replacement_or_window_overlap(self):
        index = pd.date_range("2020-01-01", periods=220, freq="D")
        frame = self._mechanism_frame(index)
        treated_positions = (10, 50, 90, 130, 170)
        for position in treated_positions:
            frame.iloc[position, frame.columns.get_loc("signal")] = True
            frame.iloc[position, frame.columns.get_loc("vrp_ratio")] = 1.50
            frame.iloc[position, frame.columns.get_loc("mechanism_outcome")] = 5.0
        fold = {
            "name": "test",
            "assessment_start": str(index[0].date()),
            "assessment_end": str(index[-1].date()),
        }
        treated = vrp.select_treated_episodes(frame, fold)

        first = vrp.match_controls(frame, treated, fold)
        changed = frame.copy()
        changed.loc[changed["vrp_ratio"] < vrp.RATIO_THRESHOLD, "mechanism_outcome"] = -500.0
        second = vrp.match_controls(changed, treated, fold)

        self.assertEqual(first["control_date"].tolist(), second["control_date"].tolist())
        self.assertEqual(first["control_date"].nunique(), len(first))
        windows = list(zip(first["control_outcome_start"], first["control_outcome_end"]))
        for index_a, left in enumerate(windows):
            for right in windows[index_a + 1 :]:
                self.assertTrue(left[1] < right[0] or right[1] < left[0])
        self.assertTrue((first["vix_difference"] <= 5.0).all())
        self.assertTrue((first["trend_distance_difference"] <= 0.10).all())
        treated_windows = list(zip(treated["outcome_start"], treated["outcome_end"]))
        for control_window in windows:
            for treated_window in treated_windows:
                self.assertTrue(
                    control_window[1] < treated_window[0]
                    or treated_window[1] < control_window[0]
                )

    def test_integrity_rejects_control_window_overlapping_any_treated_window(self):
        index = pd.date_range("2020-01-01", periods=220, freq="D")
        frame = self._mechanism_frame(index)
        for position in (10, 50, 90, 130, 170):
            frame.iloc[position, frame.columns.get_loc("signal")] = True
            frame.iloc[position, frame.columns.get_loc("vrp_ratio")] = 1.50
        fold = {
            "name": "test",
            "assessment_start": "2020-01-01",
            "assessment_end": "2020-08-07",
        }
        treated = vrp.select_treated_episodes(frame, fold)
        controls = vrp.match_controls(frame, treated, fold)
        tampered = controls.copy()
        tampered.loc[tampered.index[0], "control_outcome_start"] = treated.iloc[0]["outcome_start"]
        tampered.loc[tampered.index[0], "control_outcome_end"] = treated.iloc[0]["outcome_end"]

        with patch.object(vrp, "FOLDS", [fold]):
            violations, counters = vrp._mechanism_integrity(
                frame, {"test": treated}, {"test": tampered}
            )

        self.assertEqual(counters["control_treated_overlap_violations"], 1)
        self.assertIn("control_treated_overlap_violations=1", violations)

    def test_integrity_rejects_outcome_crossing_assessment_boundary(self):
        index = pd.date_range("2020-01-01", periods=220, freq="D")
        frame = self._mechanism_frame(index)
        frame.iloc[10, frame.columns.get_loc("signal")] = True
        frame.iloc[10, frame.columns.get_loc("vrp_ratio")] = 1.50
        fold = {
            "name": "test",
            "assessment_start": "2020-01-01",
            "assessment_end": "2020-08-07",
        }
        treated = vrp.select_treated_episodes(frame, fold)
        controls = vrp.match_controls(frame, treated, fold)
        tampered = treated.copy()
        tampered.loc[tampered.index[0], "outcome_end"] = pd.Timestamp("2020-08-08")

        with patch.object(vrp, "FOLDS", [fold]):
            violations, counters = vrp._mechanism_integrity(
                frame, {"test": tampered}, {"test": controls}
            )

        self.assertEqual(counters["assessment_boundary_violations"], 1)
        self.assertIn("assessment_boundary_violations=1", violations)

    def test_mechanism_gate_passes_positive_fixture_and_fails_matched_negative_control(self):
        features, folds = self._three_fold_features()
        with patch.object(vrp, "FOLDS", folds):
            passed, _ = vrp.evaluate_mechanism(features, bootstrap_samples=200)
        self.assertTrue(passed["gate_pass"])
        self.assertEqual(passed["pooled"]["n_treated"], 57)
        self.assertEqual(passed["pooled"]["n_matched_pairs"], 57)
        self.assertEqual(passed["integrity"]["violations"], [])

        failed_features = features.copy()
        failed_features.loc[failed_features["vrp_ratio"] < vrp.RATIO_THRESHOLD, "mechanism_outcome"] = 6.0
        with patch.object(vrp, "FOLDS", folds):
            failed, _ = vrp.evaluate_mechanism(failed_features, bootstrap_samples=200)
        self.assertFalse(failed["gate_pass"])
        self.assertLess(failed["pooled"]["matched_difference_mean_vol_points"], 0.0)
        self.assertFalse(failed["pooled"]["gate_checks"]["matched_difference_bootstrap_lb95_positive"])

    def test_circular_block_bootstrap_is_deterministic_and_one_sided(self):
        values = np.array([1.0, 2.0, 3.0, 4.0])
        first = vrp.circular_block_bootstrap_lower_bound(values, samples=500, seed=20260714)
        second = vrp.circular_block_bootstrap_lower_bound(values, samples=500, seed=20260714)
        negative = vrp.circular_block_bootstrap_lower_bound(-values, samples=500, seed=20260714)
        self.assertEqual(first, second)
        self.assertGreater(first, 0.0)
        self.assertLess(negative, 0.0)

    def test_fixed_cost_axis_is_exact_four_dollars_round_trip(self):
        short_mid_entry, long_mid_entry = 0.40, 0.20
        short_mid_exit, long_mid_exit = 0.20, 0.10
        short_sale, long_buy, credit = vrp._adverse_entry(
            short_mid_entry, long_mid_entry, "fixed_0p01_per_leg"
        )
        short_buy, long_sale, debit = vrp._adverse_exit(
            short_mid_exit, long_mid_exit, "fixed_0p01_per_leg"
        )
        midpoint_pnl = (short_mid_entry - long_mid_entry - short_mid_exit + long_mid_exit) * 100.0
        stressed_pnl = (short_sale - long_buy - short_buy + long_sale) * 100.0
        self.assertAlmostEqual(midpoint_pnl - stressed_pnl, 4.0, places=9)
        self.assertAlmostEqual(credit, 0.18, places=9)
        self.assertAlmostEqual(debit, 0.12, places=9)

    def test_integer_strike_selection_is_one_dollar_wide_and_delta_nearest(self):
        short_strike, long_strike, actual_delta = vrp._select_integer_put_strikes(
            500.0, 23, 0.20
        )
        self.assertEqual(short_strike, float(int(short_strike)))
        self.assertEqual(short_strike - long_strike, 1.0)
        self.assertLess(abs(actual_delta - 0.20), 0.02)

    def test_path_gate_requires_every_assessment_and_hard_one_trade_loss_boundary(self):
        trades = self._passing_trades()
        metrics = vrp._axis_metrics("fixed_0p01_per_leg", trades)
        self.assertTrue(metrics["gate_pass"])
        self.assertIsNone(metrics["profit_factor"])
        self.assertEqual(metrics["max_lots"], 1)

        loss_breach = [dict(trade) for trade in trades]
        loss_breach[0]["realized_loss_usd"] = 100.01
        failed = vrp._axis_metrics("fixed_0p01_per_leg", loss_breach)
        self.assertFalse(failed["gate_pass"])
        self.assertFalse(failed["gate_checks"]["maximum_structural_or_realized_loss_lte_100"])

        chronology_breach = [dict(trade) for trade in trades]
        chronology_breach[0]["signal_date"] = chronology_breach[0]["entry_date"]
        failed_chronology = vrp._axis_metrics("fixed_0p01_per_leg", chronology_breach)
        self.assertFalse(failed_chronology["gate_checks"]["zero_integrity_violations"])

    def test_strict_json_output_has_development_not_f2_labels(self):
        features, folds = self._three_fold_features()
        features.loc[features["vrp_ratio"] < vrp.RATIO_THRESHOLD, "mechanism_outcome"] = 6.0
        spy = self._spy(features.index, np.linspace(100.0, 150.0, len(features)))
        vix = pd.Series(20.0, index=features.index, name="vix")
        # This test exercises the serializer boundary without relying on the real cache.
        with patch.object(vrp, "FOLDS", folds), patch.object(
            vrp, "build_feature_frame", return_value=features
        ):
            payload = vrp.run_study(
                spy,
                vix,
                provenance={"synthetic_fixture": True},
                bootstrap_samples=200,
            )
        encoded = json.dumps(payload, allow_nan=False)
        self.assertIn('"all_rows_are_inspected_development_data": true', encoded)
        self.assertFalse(payload["f2_or_l1_claim"])
        self.assertNotIn("untouched", encoded.lower())
        self.assertEqual(payload["candidate_id"], vrp.CANDIDATE_ID)
        self.assertEqual(payload["mechanism_family"], vrp.MECHANISM_FAMILY)
        self.assertEqual(payload["closed_family"], vrp.MECHANISM_FAMILY)
        self.assertIn("raw treated VIX-minus-forward-RV premium passed", payload["dominant_failure_mechanism"])
        self.assertIn("failed stable incremental edge versus matched controls", payload["dominant_failure_mechanism"])

    @staticmethod
    def _spy(index: pd.DatetimeIndex, close: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000_000,
            },
            index=index,
        )

    @staticmethod
    def _mechanism_frame(index: pd.DatetimeIndex) -> pd.DataFrame:
        frame = pd.DataFrame(index=index)
        frame["positive_trend"] = True
        frame["vrp_ratio"] = 1.0
        frame["mechanism_outcome"] = 2.0
        frame["vix"] = 20.0
        frame["trend_distance"] = 0.05
        frame["rv20"] = 15.0
        frame["sma200"] = 100.0
        frame["subsequent_rv21"] = 18.0
        frame["signal"] = False
        return frame

    @classmethod
    def _three_fold_features(cls):
        # Each fold has enough room for 19 treated 21-session windows and 19
        # disjoint matched-control windows. A 45-session signal cadence leaves
        # a 23-session gap between treated outcome windows, so the fixture can
        # exercise the production no-overlap matcher without weakening its
        # minimum 8-pairs-per-assessment / 24-pairs-pooled gates.
        index = pd.date_range("2020-01-01", periods=3000, freq="D")
        frame = cls._mechanism_frame(index)
        folds = []
        for fold_number in range(3):
            start = fold_number * 1000
            end = start + 999
            fold = {
                "name": f"fold_{fold_number}",
                "origin_start": str(index[start].date()),
                "origin_end": str(index[start].date()),
                "assessment_start": str(index[start].date()),
                "assessment_end": str(index[end].date()),
            }
            folds.append(fold)
            for position in range(start + 50, start + 901, 45):
                frame.iloc[position, frame.columns.get_loc("signal")] = True
                frame.iloc[position, frame.columns.get_loc("vrp_ratio")] = 1.50
                frame.iloc[position, frame.columns.get_loc("mechanism_outcome")] = 5.0
                frame.iloc[position, frame.columns.get_loc("subsequent_rv21")] = 15.0
        return frame, tuple(folds)

    @staticmethod
    def _passing_trades():
        trades = []
        sequence = 0
        for fold in vrp.FOLDS:
            for _ in range(15):
                entry = pd.Timestamp("2020-01-02") + pd.Timedelta(days=sequence * 3)
                trades.append(
                    {
                        "fold": fold["name"],
                        "signal_date": str((entry - pd.Timedelta(days=1)).date()),
                        "entry_date": str(entry.date()),
                        "exit_date": str((entry + pd.Timedelta(days=1)).date()),
                        "counts_for_density": True,
                        "pnl_usd": 2.0,
                        "structural_max_loss_usd": 95.0,
                        "realized_loss_usd": 0.0,
                        "ledger_error_usd": 0.0,
                        "max_loss_reconciliation_error_usd": 0.0,
                        "entry_cost_adverse": True,
                        "exit_cost_adverse": True,
                    }
                )
                sequence += 1
        return trades


if __name__ == "__main__":
    unittest.main()

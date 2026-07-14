import json
import unittest

import numpy as np
import pandas as pd

from scripts.spy_turn_of_month_event_study import (
    _option_feature_frame,
    _serialize_event_rows,
    build_monthly_event_rows,
    conditionally_run_option_stage,
    evaluate_underlying_partitions,
    tom_pcs_config,
)


class SpyTurnOfMonthEventStudyTest(unittest.TestCase):
    def test_event_rows_are_calendar_labeled_disjoint_and_use_post_close_excursion(self):
        index = pd.bdate_range("2024-01-02", "2024-03-29")
        base = np.arange(len(index), dtype=float) + 100.0
        frame = pd.DataFrame(
            {
                "open": base,
                "high": base + 1.0,
                "low": base - 1.0,
                "close": base + 0.5,
                "volume": 1_000_000,
            },
            index=index,
        )

        rows = build_monthly_event_rows(frame)

        self.assertEqual(len(rows), 3)
        january = rows.iloc[0]
        january_sessions = frame.loc["2024-01"].index
        self.assertEqual(january["event_entry_date"], january_sessions[0])
        self.assertEqual(january["event_exit_date"], january_sessions[5])
        self.assertEqual(january["placebo_entry_date"], january_sessions[9])
        complement_date = january["complement_entry_date"]
        self.assertIn(complement_date, set(january_sessions[11:17]))
        self.assertEqual(complement_date.weekday(), january_sessions[0].weekday())
        self.assertEqual(
            len({january["event_entry_date"], january["placebo_entry_date"], complement_date}),
            3,
        )
        expected_event_return = (
            frame.loc[january_sessions[5], "close"] / frame.loc[january_sessions[0], "close"] - 1.0
        )
        expected_mae = (
            frame.loc[january_sessions[1:6], "low"].min()
            / frame.loc[january_sessions[0], "close"]
            - 1.0
        )
        self.assertAlmostEqual(january["event_return_5s"], expected_event_return)
        self.assertAlmostEqual(january["event_mae_5s"], expected_mae)

    def test_complete_month_is_retained_when_exact_weekday_control_is_calendar_impossible(self):
        index = pd.bdate_range("2018-10-01", "2018-12-31").difference(
            pd.DatetimeIndex([pd.Timestamp("2018-11-22")])
        )
        base = np.arange(len(index), dtype=float) + 100.0
        frame = pd.DataFrame(
            {
                "open": base,
                "high": base + 1.0,
                "low": base - 1.0,
                "close": base + 0.5,
                "volume": 1_000_000,
            },
            index=index,
        )

        rows = build_monthly_event_rows(frame)
        november = rows.loc[rows["month"] == "2018-11"].iloc[0]

        self.assertFalse(november["complement_available"])
        self.assertTrue(pd.isna(november["complement_entry_date"]))
        self.assertTrue(np.isfinite(november["event_return_5s"]))
        self.assertTrue(np.isfinite(november["placebo_return_5s"]))

    def test_underlying_gate_requires_train_and_untouched_holdout_against_both_controls(self):
        rows = self._synthetic_event_rows(100)

        result = evaluate_underlying_partitions(rows, train_fraction=0.60, bootstrap_samples=400)

        self.assertTrue(result["underlying_gate_pass"])
        self.assertEqual(result["train"]["n_events"], 60)
        self.assertEqual(result["untouched_holdout"]["n_events"], 40)
        for partition in ("train", "untouched_holdout"):
            metrics = result[partition]
            self.assertGreater(metrics["event_mean_return"], 0.0)
            self.assertGreater(metrics["event_median_return"], 0.0)
            self.assertGreater(metrics["paired_excess_placebo_bootstrap_lb90"], 0.0)
            self.assertGreater(metrics["paired_excess_complement_bootstrap_lb90"], 0.0)
            self.assertTrue(metrics["gate_pass"])

        failing = rows.copy()
        failing.loc[60:, "event_return_5s"] = -0.01
        failed = evaluate_underlying_partitions(
            failing, train_fraction=0.60, bootstrap_samples=400
        )
        self.assertTrue(failed["train"]["gate_pass"])
        self.assertFalse(failed["untouched_holdout"]["gate_pass"])
        self.assertFalse(failed["underlying_gate_pass"])

    def test_option_stage_is_fail_closed_and_fixed_dna_is_capital_bounded(self):
        calls = []

        skipped = conditionally_run_option_stage(
            {"underlying_gate_pass": False}, lambda: calls.append("called")
        )
        self.assertEqual(calls, [])
        self.assertEqual(skipped["status"], "NOT_RUN_UNDERLYING_GATE_FAILED")

        executed = conditionally_run_option_stage(
            {"underlying_gate_pass": True}, lambda: {"candidate_pass": False}
        )
        self.assertEqual(executed, {"candidate_pass": False})
        config = tom_pcs_config()
        self.assertEqual(config["structure"], "put_credit_spread")
        self.assertEqual(config["long_dte"], 21)
        self.assertEqual(config["long_target_delta"], 0.20)
        self.assertEqual(config["spread_width"], 1.0)
        self.assertEqual(config["profit_target"], 0.50)
        self.assertEqual(config["loss_exit_multiple_of_credit"], 2.0)
        self.assertEqual(config["max_hold_sessions"], 5)
        self.assertLessEqual(config["max_loss_budget_usd"], 125.0)

    def test_option_volatility_uses_only_prior_completed_bars(self):
        index = pd.bdate_range("2024-01-02", periods=40)
        returns = np.resize(np.array([0.004, -0.003, 0.006, -0.002]), len(index))
        close = 100.0 * np.exp(np.cumsum(returns))
        frame = pd.DataFrame(
            {
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000,
            },
            index=index,
        )

        baseline = _option_feature_frame(frame)
        shocked = frame.copy()
        shocked.loc[index[31], "close"] *= 1.25
        changed = _option_feature_frame(shocked)

        self.assertTrue(pd.isna(baseline.loc[index[30], "iv_proxy"]))
        self.assertTrue(np.isfinite(baseline.loc[index[31], "iv_proxy"]))
        self.assertAlmostEqual(
            baseline.loc[index[31], "iv_proxy"], changed.loc[index[31], "iv_proxy"]
        )
        self.assertNotAlmostEqual(
            baseline.loc[index[32], "iv_proxy"], changed.loc[index[32], "iv_proxy"]
        )

    def test_unavailable_complement_serializes_as_strict_json_null(self):
        index = pd.bdate_range("2018-10-01", "2018-12-31").difference(
            pd.DatetimeIndex([pd.Timestamp("2018-11-22")])
        )
        base = np.arange(len(index), dtype=float) + 100.0
        frame = pd.DataFrame(
            {
                "open": base,
                "high": base + 1.0,
                "low": base - 1.0,
                "close": base + 0.5,
                "volume": 1_000_000,
            },
            index=index,
        )

        november = next(
            row
            for row in _serialize_event_rows(build_monthly_event_rows(frame))
            if row["month"] == "2018-11"
        )

        self.assertIsNone(november["complement_entry_date"])
        self.assertIsNone(november["complement_return_5s"])
        json.dumps(november, allow_nan=False)

    @staticmethod
    def _synthetic_event_rows(n: int) -> pd.DataFrame:
        months = pd.period_range("2016-01", periods=n, freq="M")
        return pd.DataFrame(
            {
                "month": months.astype(str),
                "event_entry_date": months.to_timestamp(),
                "event_return_5s": np.full(n, 0.02),
                "event_mae_5s": np.full(n, -0.005),
                "event_drawdown_2pct": np.zeros(n, dtype=bool),
                "placebo_entry_date": months.to_timestamp() + pd.Timedelta(days=10),
                "placebo_return_5s": np.full(n, 0.005),
                "placebo_mae_5s": np.full(n, -0.01),
                "placebo_drawdown_2pct": np.zeros(n, dtype=bool),
                "complement_entry_date": months.to_timestamp() + pd.Timedelta(days=15),
                "complement_return_5s": np.zeros(n),
                "complement_mae_5s": np.full(n, -0.015),
                "complement_drawdown_2pct": np.zeros(n, dtype=bool),
            }
        )


if __name__ == "__main__":
    unittest.main()

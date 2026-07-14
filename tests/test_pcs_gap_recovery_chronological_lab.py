import unittest

import numpy as np
import pandas as pd

from scripts.pcs_gap_recovery_chronological_lab import (
    COST_AXES,
    _candidate_pass,
    _capital_fields,
    failed_recovery_control,
    gap_recovery_config,
    prepare_gap_features,
    unconditional_control,
)
from trader_platform.research.pcs_sim import entry_filters_pass


class PcsGapRecoveryChronologicalLabTest(unittest.TestCase):
    def test_gap_features_use_previous_close_and_fully_warmed_lagged_ema(self):
        closes = pd.Series(np.linspace(100.0, 106.1, 62))
        opens = closes.copy()
        opens.iloc[1] = 98.0
        frame = pd.DataFrame(
            {"open": opens.to_numpy(), "close": closes.to_numpy()},
            index=pd.bdate_range("2025-01-02", periods=62),
        )

        prepared = prepare_gap_features(frame)
        expected_ema = (
            frame["close"].ewm(span=60, adjust=False, min_periods=60).mean().shift(1)
        )

        self.assertTrue(np.isnan(prepared["gap_return"].iloc[0]))
        self.assertAlmostEqual(prepared["gap_return"].iloc[1], 98.0 / 100.0 - 1.0)
        self.assertAlmostEqual(
            prepared["intraday_return"].iloc[1], closes.iloc[1] / 98.0 - 1.0
        )
        pd.testing.assert_series_equal(
            prepared["lagged_ema_60"], expected_ema, check_names=False
        )
        self.assertTrue(prepared["lagged_ema_60"].iloc[:60].isna().all())
        self.assertTrue(prepared["close_vs_lagged_ema60"].iloc[:60].isna().all())
        self.assertAlmostEqual(
            prepared["close_vs_lagged_ema60"].iloc[60],
            closes.iloc[60] / expected_ema.iloc[60] - 1.0,
        )

    def test_signal_and_failed_recovery_control_are_lagged_and_disjoint(self):
        signal = gap_recovery_config()
        failed = failed_recovery_control(signal)
        recovered = pd.Series(
            {
                "gap_return": -0.01,
                "intraday_return": 0.0,
                "close_vs_lagged_ema60": 0.01,
            }
        )
        failed_row = pd.Series(
            {
                "gap_return": -0.02,
                "intraday_return": -0.001,
                "close_vs_lagged_ema60": 0.01,
            }
        )

        self.assertEqual(signal["entry_signal_lag_bars"], 1)
        self.assertEqual(failed["entry_signal_lag_bars"], 1)
        self.assertTrue(entry_filters_pass(recovered, signal))
        self.assertFalse(entry_filters_pass(recovered, failed))
        self.assertFalse(entry_filters_pass(failed_row, signal))
        self.assertTrue(entry_filters_pass(failed_row, failed))

    def test_signal_requires_strictly_above_lagged_ema_and_fails_closed(self):
        signal = gap_recovery_config()
        valid = {
            "gap_return": -0.02,
            "intraday_return": 0.01,
            "close_vs_lagged_ema60": 0.001,
        }
        self.assertTrue(entry_filters_pass(pd.Series(valid), signal))
        self.assertFalse(
            entry_filters_pass(
                pd.Series({**valid, "close_vs_lagged_ema60": 0.0}), signal
            )
        )
        for key, bad in (
            ("gap_return", None),
            ("intraday_return", np.nan),
            ("close_vs_lagged_ema60", "invalid"),
        ):
            with self.subTest(key=key, bad=bad):
                self.assertFalse(entry_filters_pass(pd.Series({**valid, key: bad}), signal))

    def test_unconditional_control_removes_only_signal_filters(self):
        control = unconditional_control(gap_recovery_config())

        self.assertEqual(control["entry_signal_lag_bars"], 1)
        self.assertFalse(
            any(
                key.startswith("entry_") and key != "entry_signal_lag_bars"
                for key in control
            )
        )
        self.assertTrue(entry_filters_pass(pd.Series(dtype=float), control))

    def test_capital_fit_uses_larger_observed_one_lot_loss_not_representative_proxy(self):
        representative = {
            "capital_fit_usd": 90.0,
            "gate_max_loss_usd": 120.0,
            "max_loss_usd": 120.0,
        }
        smaller = {
            "capital_fit_usd": 85.0,
            "gate_max_loss_usd": 100.0,
            "max_loss_usd": 100.0,
        }
        train = {axis: representative for axis in COST_AXES}
        holdout = {axis: smaller for axis in COST_AXES}

        capital = _capital_fields(train, holdout)

        self.assertEqual(capital["capital_fit_usd"], 120.0)
        self.assertEqual(capital["one_lot_max_loss_usd"], 120.0)
        self.assertEqual(capital["max_lots"], 1)

    def test_candidate_gate_requires_train_and_holdout_on_every_cost_axis(self):
        passing = self._run_row()
        failing = {**passing, "gate_pnl": -0.01, "pnl": -0.01, "verdict": "NULL"}
        train = {axis: passing for axis in COST_AXES}
        holdout = {axis: passing for axis in COST_AXES}
        windows = {
            axis: {"dense_negative_n": 0, "window_max_dd": 10.0, "integrity": True}
            for axis in COST_AXES
        }
        self.assertTrue(_candidate_pass(train, holdout, windows))

        failed_train = dict(train)
        failed_train["fixed_0p01"] = failing
        self.assertFalse(_candidate_pass(failed_train, holdout, windows))

    @staticmethod
    def _run_row():
        return {
            "ok": True,
            "n_trades": 8,
            "gate_pnl": 1.0,
            "pnl": 1.0,
            "verdict": "SHIP",
            "gate_max_loss_usd": 50.0,
            "max_loss_usd": 50.0,
            "gate_dd": 10.0,
            "dd": 10.0,
            "integrity": True,
        }


if __name__ == "__main__":
    unittest.main()

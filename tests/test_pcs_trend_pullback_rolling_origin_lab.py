import unittest

import numpy as np
import pandas as pd

from scripts.pcs_trend_pullback_rolling_origin_lab import (
    COST_AXES,
    _fold_pass,
    bearish_mirror_control,
    trend_pullback_config,
    unconditional_control,
)
from trader_platform.research.pcs_sim import entry_filters_pass


class PcsTrendPullbackRollingOriginLabTest(unittest.TestCase):
    def test_trend_pullback_and_bearish_mirror_are_lagged_and_disjoint(self):
        trend = trend_pullback_config()
        mirror = bearish_mirror_control(trend)

        bullish_row = pd.Series({"ret_5d": -0.001, "ret_14d": 0.03, "ema_stack": 1.0})
        bearish_row = pd.Series({"ret_5d": 0.001, "ret_14d": -0.03, "ema_stack": -1.0})
        self.assertEqual(trend["entry_signal_lag_bars"], 1)
        self.assertTrue(entry_filters_pass(bullish_row, trend))
        self.assertFalse(entry_filters_pass(bearish_row, trend))
        self.assertTrue(entry_filters_pass(bearish_row, mirror))
        self.assertFalse(entry_filters_pass(bullish_row, mirror))
        self.assertNotIn("entry_ret_5d_max", mirror)
        self.assertNotIn("entry_ret_14d_min", mirror)
        self.assertNotIn("entry_ema_stack_min", mirror)

    def test_new_multi_horizon_filters_fail_closed_on_bad_inputs(self):
        config = trend_pullback_config()
        valid = {"ret_5d": -0.01, "ret_14d": 0.05, "ema_stack": 1.0}

        self.assertTrue(entry_filters_pass(pd.Series(valid), config))
        for key, bad in (
            ("ret_5d", None),
            ("ret_14d", np.nan),
            ("ema_stack", "invalid"),
        ):
            row = {**valid, key: bad}
            self.assertFalse(entry_filters_pass(pd.Series(row), config))

    def test_fold_gate_rejects_passing_holdout_when_train_axis_failed(self):
        passing = self._run_row()
        failing = {**passing, "gate_pnl": -0.01, "pnl": -0.01, "verdict": "NULL"}
        train = {axis: passing for axis in COST_AXES}
        train["slip_5pct"] = failing
        holdout = {axis: passing for axis in COST_AXES}
        windows = {
            axis: {"dense_negative_n": 0, "window_max_dd": 10.0, "integrity": True}
            for axis in COST_AXES
        }

        self.assertFalse(_fold_pass(train, holdout, windows))

    def test_unconditional_control_removes_entry_filters_but_keeps_lag(self):
        config = trend_pullback_config()
        control = unconditional_control(config)

        self.assertEqual(control["entry_signal_lag_bars"], 1)
        self.assertFalse(any(key.startswith("entry_") and key != "entry_signal_lag_bars" for key in control))
        self.assertTrue(entry_filters_pass(pd.Series(dtype=float), control))

    @staticmethod
    def _run_row():
        return {
            "ok": True,
            "n_trades": 10,
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

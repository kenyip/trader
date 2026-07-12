import unittest

import pandas as pd

from scripts.ccs_vol_expansion_rolling_origin_lab import (
    COST_AXES,
    _fold_pass,
    compression_control,
    expansion_ccs_config,
    unconditional_control,
)
from trader_platform.research.pcs_sim import entry_filters_pass, run_pcs_backtest


class CcsVolExpansionRollingOriginLabTest(unittest.TestCase):
    def test_expansion_and_compression_controls_are_lagged_and_disjoint(self):
        expansion = expansion_ccs_config()
        compression = compression_control(expansion)

        self.assertEqual(expansion["structure"], "call_credit_spread")
        self.assertEqual(expansion["entry_signal_lag_bars"], 1)
        self.assertEqual(compression["entry_signal_lag_bars"], 1)
        expansion_row = pd.Series({"hv_20": 0.24, "hv_60": 0.20, "ret_1d": -0.01})
        compression_row = pd.Series({"hv_20": 0.16, "hv_60": 0.20, "ret_1d": -0.01})
        positive_row = pd.Series({"hv_20": 0.24, "hv_60": 0.20, "ret_1d": 0.01})

        self.assertTrue(entry_filters_pass(expansion_row, expansion))
        self.assertFalse(entry_filters_pass(compression_row, expansion))
        self.assertFalse(entry_filters_pass(positive_row, expansion))
        self.assertTrue(entry_filters_pass(compression_row, compression))
        self.assertFalse(entry_filters_pass(expansion_row, compression))
        self.assertNotIn("entry_hv_ratio_max", expansion)
        self.assertNotIn("entry_hv_ratio_min", compression)

    def test_unconditional_control_removes_signals_but_retains_structure_and_lag(self):
        config = expansion_ccs_config()
        control = unconditional_control(config)

        self.assertEqual(control["structure"], "call_credit_spread")
        self.assertEqual(control["entry_signal_lag_bars"], 1)
        self.assertNotIn("entry_hv_ratio_min", control)
        self.assertNotIn("entry_ret_1d_max", control)
        self.assertTrue(entry_filters_pass(pd.Series(dtype=float), control))

    def test_structure_dispatch_stays_call_credit_spread(self):
        frame = pd.DataFrame(
            {
                "close": [100.0] * 20,
                "iv_proxy": [0.30] * 20,
                "iv_rank": [50.0] * 20,
                "regime": ["bearish"] * 20,
                "hv_20": [0.24] * 20,
                "hv_60": [0.20] * 20,
                "ret_1d": [-0.01] * 20,
            },
            index=pd.date_range("2026-01-01", periods=20, freq="B"),
        )

        result = run_pcs_backtest("TEST", df=frame, config=expansion_ccs_config())

        self.assertTrue(result.ok)
        self.assertEqual(result.metrics["structure"], "call_credit_spread")
        self.assertEqual(result.capital["structure"], "call_credit_spread")
        self.assertTrue(all(trade.right == "call" for trade in result.trades))

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

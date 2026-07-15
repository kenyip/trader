import unittest
from types import SimpleNamespace

from scripts.pcs_early_exit_train_lab import (
    COST_AXES,
    _capital_fields,
    _operating_summary,
    discovery_pass,
    early_exit_config,
    late_exit_control_config,
    management_diagnostics,
    train_rank_key,
)


class PcsEarlyExitTrainLabTest(unittest.TestCase):
    @staticmethod
    def _axis(*, pnl: float = 10.0, n_trades: int = 10, max_loss: float = 90.0, integrity: bool = True):
        return {
            "ok": True,
            "n_trades": n_trades,
            "gate_pnl": pnl,
            "gate_max_loss_usd": max_loss,
            "integrity": integrity,
        }

    def test_candidate_and_control_only_change_predeclared_dte_stop(self):
        candidate = early_exit_config()
        control = late_exit_control_config(candidate)

        self.assertEqual(candidate["entry_weekdays"], [0])
        self.assertEqual(candidate["long_dte"], 45)
        self.assertEqual(candidate["dte_stop"], 21)
        self.assertEqual(control["dte_stop"], 5)
        self.assertEqual(
            {key: value for key, value in candidate.items() if key != "dte_stop"},
            {key: value for key, value in control.items() if key != "dte_stop"},
        )

    def test_discovery_gate_requires_dual_cost_positive_integrity_capital_and_control_outperformance(self):
        candidate = {axis: self._axis(pnl=20.0) for axis in COST_AXES}
        control = {axis: self._axis(pnl=19.0) for axis in COST_AXES}

        self.assertTrue(discovery_pass(candidate, control))

        for mutation in (
            {"slip_5pct": {**candidate["slip_5pct"], "n_trades": 7}},
            {"fixed_0p01": {**candidate["fixed_0p01"], "gate_pnl": 0.0}},
            {"slip_5pct": {**candidate["slip_5pct"], "integrity": False}},
            {"fixed_0p01": {**candidate["fixed_0p01"], "gate_max_loss_usd": 300.0001}},
        ):
            changed = {axis: dict(candidate[axis]) for axis in COST_AXES}
            changed.update(mutation)
            self.assertFalse(discovery_pass(changed, control))

        tied_control = {axis: self._axis(pnl=20.0) for axis in COST_AXES}
        self.assertFalse(discovery_pass(candidate, tied_control))

        for mutation in (
            {"slip_5pct": {**control["slip_5pct"], "ok": False}},
            {"fixed_0p01": {**control["fixed_0p01"], "n_trades": 7}},
            {"fixed_0p01": {**control["fixed_0p01"], "integrity": False}},
        ):
            invalid_control = {axis: dict(control[axis]) for axis in COST_AXES}
            invalid_control.update(mutation)
            self.assertFalse(discovery_pass(candidate, invalid_control))

    def test_train_rank_prefers_stronger_worst_cost_axis_then_lower_max_loss(self):
        stronger = {
            "train": {
                "slip_5pct": self._axis(pnl=25.0, max_loss=100.0),
                "fixed_0p01": self._axis(pnl=20.0, max_loss=100.0),
            }
        }
        weaker = {
            "train": {
                "slip_5pct": self._axis(pnl=30.0, max_loss=80.0),
                "fixed_0p01": self._axis(pnl=19.0, max_loss=80.0),
            }
        }
        equal_edge_lower_loss = {
            "train": {
                "slip_5pct": self._axis(pnl=25.0, max_loss=90.0),
                "fixed_0p01": self._axis(pnl=20.0, max_loss=90.0),
            }
        }

        self.assertGreater(train_rank_key(stronger), train_rank_key(weaker))
        self.assertGreater(train_rank_key(equal_edge_lower_loss), train_rank_key(stronger))

    def test_management_diagnostics_prove_calendar_stop_was_exercised(self):
        result = SimpleNamespace(
            metrics={
                "avg_days_held": 12.5,
                "exit_reasons": {"dte_stop": 7, "profit_target": 3},
            }
        )

        self.assertEqual(
            management_diagnostics(result),
            {
                "avg_days_held": 12.5,
                "exit_reasons": {"dte_stop": 7, "profit_target": 3},
                "calendar_stop_exits": 7,
                "calendar_stop_exercised": True,
            },
        )

    def test_capital_fields_state_one_lot_loss_and_operating_limit(self):
        axes = {
            "slip_5pct": {
                "gate_max_loss_usd": 95.0,
                "capital_fit_usd": 92.0,
                "max_lots": 3,
            },
            "fixed_0p01": {
                "gate_max_loss_usd": 90.0,
                "capital_fit_usd": 98.0,
                "max_lots": 3,
            },
        }

        self.assertEqual(
            _capital_fields(axes),
            {
                "capital_fit_usd": 98.0,
                "max_loss_usd": 95.0,
                "one_lot_max_loss_usd": 95.0,
                "operating_max_lots": 1,
                "max_lots": 1,
            },
        )

        self.assertEqual(
            _operating_summary({"max_lots": 3, "pnl": 12.5}),
            {
                "max_lots": 1,
                "pnl": 12.5,
                "theoretical_max_lots": 3,
                "operating_max_lots": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()

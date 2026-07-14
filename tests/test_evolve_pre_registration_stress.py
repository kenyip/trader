import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from scripts.evolve_pre_registration_stress import (
    evaluate_proxy_gates,
    load_ship_candidates,
)
from scripts.pcs_cost_stress import _metrics_row
from scripts.pcs_regime_stress import _row_from_pcs


def _passing_inputs():
    regime = {
        "full_history": {
            "ok": True,
            "verdict": "SHIP",
            "n_trades": 20,
            "pnl": 25.0,
            "max_loss_usd": 100.0,
        },
        "summary": {
            "regime_hold": True,
            "max_dd_across_windows": 70.0,
            "n_negative_n_ge_3": 3,
        },
    }
    cost = {
        "by_slip": [
            {
                "slippage_pct": 0.05,
                "ok": True,
                "verdict": "SHIP",
                "n_trades": 18,
                "pnl": 5.0,
                "max_loss_usd": 105.0,
            }
        ]
    }
    fixed = {
        "by_half_spread": [
            {
                "half_spread_per_leg": 0.01,
                "ok": True,
                "verdict": "SHIP",
                "n_trades": 17,
                "pnl": 3.0,
                "max_loss_usd": 110.0,
            }
        ]
    }
    return regime, cost, fixed


class EvolvePreRegistrationStressTest(unittest.TestCase):
    @staticmethod
    def _dna(**overrides):
        dna = {
            "structure": "put_credit_spread",
            "symbols": ["AAA"],
            "entry_plan": {},
            "exit_plan": {},
            "config": {},
            "dna_id": "dna_unique",
        }
        dna.update(overrides)
        return dna

    def test_loads_only_unique_ship_dna_from_dry_run(self):
        dna = self._dna()
        payload = {
            "applied": False,
            "dry_run": True,
            "results": [
                {"verdict": "SHIP", "dna": dna, "n_trades": 20},
                {"verdict": "SHIP", "dna": dna, "n_trades": 20},
                {"verdict": "NULL", "dna": {**dna, "dna_id": "dna_null"}},
            ],
        }

        candidates = load_ship_candidates(payload)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["id"], "transient_dna_unique")
        self.assertEqual(candidates[0]["status"], "research_transient")

    def test_rejects_multi_symbol_ship_to_preserve_structure_purity(self):
        payload = {
            "applied": False,
            "dry_run": True,
            "results": [
                {
                    "verdict": "SHIP",
                    "dna": self._dna(symbols=["AAA", "BBB"]),
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "exactly one symbol"):
            load_ship_candidates(payload)

    def test_rejects_unsupported_ship_structure(self):
        payload = {
            "applied": False,
            "dry_run": True,
            "results": [
                {
                    "verdict": "SHIP",
                    "dna": self._dna(structure="cash_secured_put"),
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "unsupported SHIP structure"):
            load_ship_candidates(payload)

    def test_rejects_applied_report_to_preserve_pre_registration_boundary(self):
        with self.assertRaisesRegex(ValueError, "dry-run"):
            load_ship_candidates({"applied": True, "dry_run": False, "results": []})

    def test_rejects_missing_or_false_dry_run_provenance(self):
        for payload in (
            {"applied": False, "results": []},
            {"applied": False, "dry_run": False, "results": []},
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "dry-run"):
                    load_ship_candidates(payload)

    def test_complete_proxy_pass_still_cannot_register_without_holdout(self):
        regime, cost, fixed = _passing_inputs()

        result = evaluate_proxy_gates(regime, cost, fixed)

        self.assertTrue(result["complete_proxy_gates"])
        self.assertFalse(result["registration_eligible"])
        self.assertIn("untouched_holdout", result["registration_blocker"])
        self.assertEqual(result["capital"]["capital_fit_usd"], 110.0)
        self.assertEqual(result["capital"]["one_lot_max_loss_usd"], 110.0)
        self.assertEqual(result["capital"]["max_lots"], 1)
        self.assertEqual(result["capital"]["sleeve_usd"], 3000.0)
        self.assertTrue(result["capital"]["fits_sleeve"])
        self.assertTrue(result["capital"]["fits_open_risk_budget"])
        self.assertTrue(result["capital"]["fits_max_loss_budget"])

    def test_fixed_cost_loss_fails_complete_gate(self):
        regime, cost, fixed = _passing_inputs()
        row = fixed["by_half_spread"][0]
        row["verdict"] = "REJECT"
        row["pnl"] = -0.01

        result = evaluate_proxy_gates(regime, cost, fixed)

        self.assertFalse(result["gates"]["fixed_0_01_positive_non_vacuous_ship"])
        self.assertFalse(result["complete_proxy_gates"])

    def test_thin_cost_axis_and_oversized_loss_fail_closed(self):
        regime, cost, fixed = _passing_inputs()
        cost["by_slip"][0]["n_trades"] = 14
        fixed["by_half_spread"][0]["max_loss_usd"] = 300.01

        result = evaluate_proxy_gates(regime, cost, fixed)

        self.assertFalse(result["gates"]["slip_5pct_positive_non_vacuous_ship"])
        self.assertFalse(result["gates"]["max_loss_lte_300"])
        self.assertFalse(result["complete_proxy_gates"])

    def test_cost_metric_rows_preserve_unrounded_gate_values(self):
        sim = SimpleNamespace(
            ok=True,
            skipped=False,
            reason=None,
            n_trades=15,
            metrics={
                "n_trades": 15,
                "total_pnl_per_contract": 0.004,
                "win_rate_pct": 60.0,
                "max_dd_per_contract": 75.0001,
                "profit_factor": 1.2,
            },
            capital={"max_loss_usd": 300.0001, "capital_fit": "fit_3k"},
        )

        row = _metrics_row(sim, 0.05)

        self.assertEqual(row["pnl"], 0.0)
        self.assertEqual(row["dd"], 75.0)
        self.assertEqual(row["max_loss_usd"], 300.0001)
        self.assertEqual(row["gate_pnl"], 0.004)
        self.assertEqual(row["gate_dd"], 75.0001)
        self.assertEqual(row["gate_max_loss_usd"], 300.0001)

    def test_regime_rows_preserve_unrounded_gate_values(self):
        sim = SimpleNamespace(
            ok=True,
            skipped=False,
            reason=None,
            n_trades=15,
            metrics={
                "n_trades": 15,
                "total_pnl_per_contract": 0.004,
                "win_rate_pct": 60.0,
                "max_dd_per_contract": 75.0001,
                "profit_factor": 1.2,
            },
            capital={"max_loss_usd": 300.0001, "capital_fit": "fit_3k"},
        )
        frame = pd.DataFrame(
            {"close": range(15)},
            index=pd.date_range("2025-01-01", periods=15, freq="D"),
        )
        with patch("scripts.pcs_regime_stress.run_pcs_backtest", return_value=sim):
            row = _row_from_pcs(
                "fixture",
                frame,
                "AAA",
                {"structure": "put_credit_spread"},
                structure="put_credit_spread",
            )

        self.assertEqual(row["pnl"], 0.0)
        self.assertEqual(row["dd"], 75.0)
        self.assertEqual(row["gate_pnl"], 0.004)
        self.assertEqual(row["gate_dd"], 75.0001)
        self.assertEqual(row["gate_max_loss_usd"], 300.0001)

    def test_hard_gates_prefer_unrounded_metrics_over_display_values(self):
        regime, cost, fixed = _passing_inputs()
        regime["full_history"]["gate_pnl"] = -0.0001
        regime["summary"]["gate_max_dd_across_windows"] = 75.0001
        fixed["by_half_spread"][0]["gate_max_loss_usd"] = 300.0001

        result = evaluate_proxy_gates(regime, cost, fixed)

        self.assertFalse(result["gates"]["baseline_positive_non_vacuous_ship"])
        self.assertFalse(result["gates"]["window_max_dd_lte_75"])
        self.assertFalse(result["gates"]["max_loss_lte_300"])
        self.assertFalse(result["complete_proxy_gates"])


if __name__ == "__main__":
    unittest.main()

import unittest

import pandas as pd

from scripts.evolve_chronological_pre_registration import (
    build_fixed_population,
    chronological_complete_gate,
    run_lab,
    sample_universe_rows,
    split_frame,
    train_selection_ship,
)
from trader_platform.strategy_dna import dna_from_structure


class EvolveChronologicalPreRegistrationTest(unittest.TestCase):
    @staticmethod
    def _gate_result(*, passed: bool) -> dict:
        return {
            "complete_proxy_gates": passed,
            "registration_eligible": False,
            "capital": {
                "capital_fit_usd": 100.0,
                "one_lot_max_loss_usd": 100.0,
                "max_lots": 1,
            },
        }

    def test_split_is_strictly_chronological_and_disjoint(self):
        frame = pd.DataFrame(
            {"close": range(100)},
            index=pd.date_range("2025-01-01", periods=100, freq="D"),
        )

        train, holdout, metadata = split_frame(frame, 0.60, min_bars=15)

        self.assertEqual(len(train), 60)
        self.assertEqual(len(holdout), 40)
        self.assertLess(train.index[-1], holdout.index[0])
        self.assertTrue(metadata["chronology_ok"])
        self.assertEqual(metadata["train_end"], "2025-03-01")
        self.assertEqual(metadata["holdout_start"], "2025-03-02")

    def test_split_fails_closed_on_invalid_fraction_or_index(self):
        valid = pd.DataFrame(
            {"close": range(40)},
            index=pd.date_range("2025-01-01", periods=40, freq="D"),
        )
        duplicated = pd.concat([valid.iloc[:20], valid.iloc[19:]])
        descending = valid.sort_index(ascending=False)

        for frame, fraction, message in (
            (valid, 0.49, "train_fraction"),
            (valid, 0.81, "train_fraction"),
            (duplicated, 0.60, "unique"),
            (descending, 0.60, "monotonic"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    split_frame(frame, fraction, min_bars=15)

    def test_train_selection_ship_requires_unrounded_positive_dense_ship(self):
        passing = {
            "ok": True,
            "verdict": "SHIP",
            "n_trades": 15,
            "gate_pnl": 0.004,
        }
        self.assertTrue(train_selection_ship(passing))

        for update in (
            {"ok": False},
            {"verdict": "NULL"},
            {"n_trades": 14},
            {"gate_pnl": 0.0},
            {"gate_pnl": -0.001},
        ):
            with self.subTest(update=update):
                self.assertFalse(train_selection_ship({**passing, **update}))

    def test_complete_gate_requires_train_and_holdout_and_never_registers(self):
        passing = self._gate_result(passed=True)
        failing = self._gate_result(passed=False)

        complete = chronological_complete_gate(passing, passing, chronology_ok=True)
        failed_train = chronological_complete_gate(failing, passing, chronology_ok=True)
        failed_chronology = chronological_complete_gate(passing, passing, chronology_ok=False)

        self.assertTrue(complete["complete_chronological_proxy_gates"])
        self.assertFalse(complete["registration_eligible"])
        self.assertIn("first_pass", complete["registration_blocker"])
        self.assertFalse(failed_train["complete_chronological_proxy_gates"])
        self.assertFalse(failed_chronology["complete_chronological_proxy_gates"])

    def test_fixed_population_is_reproducible_capped_and_structure_pure(self):
        rows = [
            {"symbol": "AAA", "strategy_family": "short_put_cautious"},
            {"symbol": "BBB", "strategy_family": "short_strangle_candidate"},
        ]
        structures = ["put_credit_spread", "call_credit_spread", "iron_condor"]

        first = build_fixed_population(
            rows,
            structures=structures,
            mutants_per_seed=2,
            seed=1754,
            max_population=7,
        )
        second = build_fixed_population(
            rows,
            structures=structures,
            mutants_per_seed=2,
            seed=1754,
            max_population=7,
        )

        self.assertEqual([dna.ensure_id() for dna in first], [dna.ensure_id() for dna in second])
        self.assertEqual(len(first), 7)
        self.assertLessEqual({dna.structure for dna in first}, set(structures))
        self.assertEqual({len(dna.symbols) for dna in first}, {1})

    def test_capped_population_reports_silent_eligible_structures(self):
        frame = pd.DataFrame(
            {"close": range(100)},
            index=pd.date_range("2025-01-01", periods=100, freq="D"),
        )
        dna = dna_from_structure("call_credit_spread", ["AAA"])

        def baseline_runner(candidate, supplied_frame, label):
            return {
                "ok": True,
                "verdict": "NULL",
                "n_trades": 0,
                "gate_pnl": 0.0,
                "dna_id": candidate.ensure_id(),
                "symbol": "AAA",
                "structure": candidate.structure,
            }

        payload = run_lab(
            symbol_rows=[{"symbol": "AAA", "strategy_family": ""}],
            frames={"AAA": frame},
            structures=["call_credit_spread", "put_credit_spread"],
            mutants_per_seed=0,
            seed=1754,
            max_population=1,
            train_fraction=0.60,
            period="fixture",
            population=[dna],
            baseline_runner=baseline_runner,
        )

        self.assertEqual(
            payload["structures_eligible"],
            ["call_credit_spread", "put_credit_spread"],
        )
        self.assertEqual(payload["structures_evaluated"], ["call_credit_spread"])
        self.assertEqual(payload["structures_not_evaluated"], ["put_credit_spread"])
        self.assertEqual(
            payload["evaluated_structure_counts"],
            {"call_credit_spread": 1, "put_credit_spread": 0},
        )
        self.assertFalse(payload["validity"]["all_eligible_structures_evaluated"])
        self.assertTrue(payload["validity"]["ranking_complete"])

    def test_universe_sampling_is_fixed_seed_and_outcome_rank_free(self):
        symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]

        first = sample_universe_rows(symbols, top_symbols=3, seed=1754)
        second = sample_universe_rows(list(reversed(symbols)), top_symbols=3, seed=1754)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertTrue(all(row["selection"] == "fixed_seed_uniform_universe" for row in first))
        self.assertTrue(all("score" not in row for row in first))

    def test_run_lab_never_uses_holdout_for_train_selection(self):
        frame = pd.DataFrame(
            {"close": range(100)},
            index=pd.date_range("2025-01-01", periods=100, freq="D"),
        )
        dna = dna_from_structure("put_credit_spread", ["AAA"])
        calls = []

        def baseline_runner(candidate, supplied_frame, label):
            calls.append(("baseline", label, supplied_frame.index[0], supplied_frame.index[-1]))
            return {
                "ok": True,
                "verdict": "SHIP",
                "n_trades": 20,
                "gate_pnl": 1.0,
                "dna_id": candidate.ensure_id(),
                "symbol": "AAA",
                "structure": candidate.structure,
            }

        def stress_runner(hyp, supplied_frame, label):
            calls.append(("stress", label, supplied_frame.index[0], supplied_frame.index[-1]))
            return {
                "complete_proxy_gates": True,
                "registration_eligible": False,
                "capital": {
                    "capital_fit_usd": 100.0,
                    "one_lot_max_loss_usd": 100.0,
                    "max_lots": 1,
                },
            }

        payload = run_lab(
            symbol_rows=[{"symbol": "AAA", "strategy_family": ""}],
            frames={"AAA": frame},
            structures=["put_credit_spread"],
            mutants_per_seed=0,
            seed=1754,
            max_population=1,
            train_fraction=0.60,
            period="fixture",
            population=[dna],
            baseline_runner=baseline_runner,
            stress_runner=stress_runner,
        )

        train_end = frame.index[59]
        holdout_start = frame.index[60]
        self.assertEqual(calls[0], ("baseline", "train_selection", frame.index[0], train_end))
        self.assertEqual(calls[1], ("stress", "train_stress", frame.index[0], train_end))
        self.assertEqual(calls[2], ("stress", "untouched_holdout", holdout_start, frame.index[-1]))
        self.assertEqual(payload["selected_train_ship_n"], 1)
        self.assertEqual(payload["complete_chronological_proxy_gate_n"], 1)
        self.assertEqual(payload["registration_eligible_ids"], [])
        self.assertTrue(payload["validity"]["ranking_complete"])

    def test_run_lab_rejects_passing_holdout_when_train_gate_failed(self):
        frame = pd.DataFrame(
            {"close": range(100)},
            index=pd.date_range("2025-01-01", periods=100, freq="D"),
        )
        dna = dna_from_structure("call_credit_spread", ["AAA"])

        def baseline_runner(candidate, supplied_frame, label):
            return {
                "ok": True,
                "verdict": "SHIP",
                "n_trades": 20,
                "gate_pnl": 1.0,
                "dna_id": candidate.ensure_id(),
                "symbol": "AAA",
                "structure": candidate.structure,
            }

        def stress_runner(hyp, supplied_frame, label):
            return {
                "complete_proxy_gates": label == "untouched_holdout",
                "registration_eligible": False,
                "capital": {
                    "capital_fit_usd": 100.0,
                    "one_lot_max_loss_usd": 100.0,
                    "max_lots": 1,
                },
            }

        payload = run_lab(
            symbol_rows=[{"symbol": "AAA", "strategy_family": ""}],
            frames={"AAA": frame},
            structures=["call_credit_spread"],
            mutants_per_seed=0,
            seed=1754,
            max_population=1,
            train_fraction=0.60,
            period="fixture",
            population=[dna],
            baseline_runner=baseline_runner,
            stress_runner=stress_runner,
        )

        self.assertEqual(payload["complete_chronological_proxy_gate_n"], 0)
        self.assertFalse(payload["selected_results"][0]["complete_chronological_proxy_gates"])
        self.assertEqual(
            payload["decision"],
            "REJECT_ALL_TRAIN_SELECTED_DNA_ON_CONJUNCTIVE_HOLDOUT_GATES",
        )


if __name__ == "__main__":
    unittest.main()

"""DNA and lock math for the agentic credit-door hunter."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.agentic_credit_door_hunt import (
    MAX_LOCK_USD,
    MRK_MEASURED,
    crown_decision,
    discard_reason,
    evaluate_structure,
    lock_usd,
    run_hunt,
    sendable_roc,
)


def _pcs(**kwargs) -> dict:
    row = {
        "symbol": "KO",
        "structure": "put_credit_spread",
        "expiry": "2026-10-16",
        "as_of": "2026-09-03",
        "short_strike": 85.0,
        "long_strike": 80.0,
        "short_bid": 0.60,
        "short_ask": 0.70,
        "long_bid": 0.02,
        "long_ask": 0.10,
        "short_delta": -0.22,
        "ivr": 45.0,
        "earnings": "2026-10-20",
        "new_strike_or_expiry": False,
    }
    row.update(kwargs)
    return row


class LockMath(unittest.TestCase):
    def test_pcs_lock_is_width_minus_credit_times_100(self) -> None:
        self.assertAlmostEqual(lock_usd(5.0, 0.58), 442.0)

    def test_ccs_lock_same_formula(self) -> None:
        self.assertAlmostEqual(lock_usd(5.0, 0.80), 420.0)

    def test_sendable_roc_uses_lock_not_credit(self) -> None:
        self.assertAlmostEqual(sendable_roc(27.08, 425.0), 27.08 / 425.0)


class DnaGates(unittest.TestCase):
    def test_pass_defined_credit(self) -> None:
        ev = evaluate_structure(_pcs(), cash_usd=854.90, lock_cap_usd=MAX_LOCK_USD)
        self.assertTrue(ev["dna_pass"], ev["fails"])
        self.assertLessEqual(ev["lock_usd"], MAX_LOCK_USD)
        self.assertGreaterEqual(ev["credit_pct_of_width"], 0.10)

    def test_skinny_credit_fails(self) -> None:
        ev = evaluate_structure(
            _pcs(short_bid=0.12, short_ask=0.18, long_bid=0.02, long_ask=0.10),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertIn("width_skinny", ev["fails"])
        self.assertFalse(ev["dna_pass"])

    def test_inverted_nbbo_fails(self) -> None:
        ev = evaluate_structure(
            _pcs(short_bid=0.80, short_ask=0.70),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertIn("nbbo_inverted", ev["fails"])

    def test_earnings_inside_hold_fails(self) -> None:
        ev = evaluate_structure(
            _pcs(earnings="2026-10-10"),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertIn("earnings_inside_hold", ev["fails"])

    def test_discard_list_fails(self) -> None:
        ev = evaluate_structure(
            _pcs(symbol="MPC"),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertIn("discard_prior_hunt", ev["fails"])
        self.assertEqual(discard_reason("MPC", "put_credit_spread", new_strike_or_expiry=True), "discard_prior_hunt")

    def test_mrk_allowed_only_on_new_strike(self) -> None:
        self.assertEqual(
            discard_reason("MRK", "put_credit_spread", new_strike_or_expiry=False),
            "discard_unless_new_strike_expiry",
        )
        self.assertIsNone(discard_reason("MRK", "put_credit_spread", new_strike_or_expiry=True))

    def test_long_leg_first_must_fit_cash(self) -> None:
        ev = evaluate_structure(
            _pcs(short_bid=10.0, short_ask=11.0, long_bid=8.0, long_ask=9.0, short_delta=-0.22),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertIn("long_leg_cash_fail", ev["fails"])

    def test_lock_over_cash_cap_fails_sendable(self) -> None:
        ev = evaluate_structure(
            _pcs(
                symbol="CVS",
                short_strike=92.5,
                long_strike=80.0,
                short_bid=1.60,
                short_ask=1.80,
                long_bid=0.25,
                long_ask=0.40,
                short_delta=-0.26,
            ),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertGreater(ev["lock_usd"], MAX_LOCK_USD)
        self.assertIn("lock_over_cash", ev["fails"])

    def test_naked_rejected(self) -> None:
        ev = evaluate_structure(
            _pcs(naked=True),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertIn("naked_short", ev["fails"])

    def test_delta_too_hot_fails(self) -> None:
        ev = evaluate_structure(
            _pcs(short_delta=-0.40),
            cash_usd=854.90,
            lock_cap_usd=MAX_LOCK_USD,
        )
        self.assertIn("delta_hot", ev["fails"])


class CrownRules(unittest.TestCase):
    def _pass_row(self, **kwargs) -> dict:
        ev = evaluate_structure(_pcs(), cash_usd=854.90, lock_cap_usd=MAX_LOCK_USD)
        ev["fillable_under_855"] = True
        ev.update(kwargs)
        return ev

    def test_null_when_no_dna_pass(self) -> None:
        ev = evaluate_structure(_pcs(earnings="2026-10-10"), cash_usd=854.90, lock_cap_usd=MAX_LOCK_USD)
        ev["fillable_under_855"] = False
        ev["model_avg_pnl_usd"] = 40.0
        ev["model_n"] = 12
        crown = crown_decision([ev], mrk_model_roc=None, mrk_model_lock=425.0)
        self.assertIsNone(crown)

    def test_null_when_roc_does_not_beat_mrk(self) -> None:
        ev = self._pass_row(model_avg_pnl_usd=5.0, model_n=20)
        crown = crown_decision([ev], mrk_model_roc=None, mrk_model_lock=425.0)
        self.assertIsNone(crown)

    def test_crown_when_fillable_under_cap_and_beats_mrk_roc(self) -> None:
        ev = self._pass_row(model_avg_pnl_usd=80.0, model_n=20)
        crown = crown_decision([ev], mrk_model_roc=None, mrk_model_lock=425.0)
        self.assertIsNotNone(crown)
        self.assertEqual(crown["symbol"], "KO")
        self.assertGreater(crown["sendable_roc"], 27.08 / 425.0)

    def test_run_hunt_writes_artifacts_without_network(self) -> None:
        snapshot = {
            "as_of": "2026-09-03",
            "cash_usd": 854.90,
            "buying_power_usd": 784.86,
            "account_value_usd": 984.90,
            "lock_cap_usd": 855.0,
            "book": {"ticker": "OKE"},
            "working_orders": [],
            "candidates": [_pcs()],
        }
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = run_hunt(snapshot, backtest=False, out_dir=out)
            self.assertTrue((out / "RESULT.json").is_file())
            self.assertTrue((out / "SUMMARY.md").is_file())
            self.assertTrue((out / "CROWN.json").is_file())
            self.assertIsNone(result["crown"])
            self.assertTrue(result["candidates"][0]["dna_pass"])
            self.assertEqual(MRK_MEASURED["n"], 15)


if __name__ == "__main__":
    unittest.main()

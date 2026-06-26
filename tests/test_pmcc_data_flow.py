"""Verification harness for plan step 2 — exercises real pmcc data paths."""

from __future__ import annotations

import unittest

from pmcc.chain_data import fetch_call_chain
from pmcc.income import income_metrics, reentry_candidates
from pmcc.positions import check_leaps_only_position, check_pmcc_position, load_pmcc_positions
from pmcc.scenarios import PmccPair
from pmcc.staged_entry import build_tsla_staged_entry_plan


class PmccDataFlowVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spot, cls.chain = fetch_call_chain("TSLA", refresh=False)
        cls.recs = load_pmcc_positions()

    def test_live_records_and_staged_plan(self) -> None:
        print("RECORDS:", len(self.recs))
        staged = build_tsla_staged_entry_plan(self.recs, self.chain, spot=self.spot)
        print("STAGED NEXT:", staged.get("next_step"))
        print("STAGED EVENTS:", staged.get("events"))
        self.assertIn("next_step", staged)
        self.assertIn("events", staged)

    def test_open_short_carry_or_leaps_only_clock(self) -> None:
        """LEAPS-only records have carry=None but closed_short_clock; open shorts have carry."""
        saw_carry = False
        saw_clock = False
        for r in self.recs[:3]:
            s = check_pmcc_position(r, self.spot)
            print("PRIMARY:", s.get("primary_action"))
            print("CHECKS:", len(s.get("checks", [])))
            self.assertGreater(len(s.get("checks", [])), 0)
            if s.get("carry"):
                saw_carry = True
                carry = s["carry"]
                print("CARRY KEYS:", sorted(carry.keys()))
                for key in ("wait_good_days_after_harvest", "net_current_profit_daily"):
                    self.assertIn(key, carry)
            if s.get("closed_short_clock"):
                saw_clock = True
                good = s["closed_short_clock"]["targets"]["good"]
                print("CLOCK WAIT:", good.get("portfolio_wait_days"))
                self.assertIn("portfolio_budget_until", good)
            cands = reentry_candidates(self.spot, s["pair"], chain=self.chain)
            print("REENTRY COUNT:", len(cands))
            self.assertGreater(len(cands), 0)
            self.assertIn("daily", cands[0])
            self.assertIn("risk", cands[0])
            self.assertIn("income", cands[0])
        self.assertTrue(saw_carry or saw_clock, "expected carry or closed_short_clock from live records")

    def test_income_metrics_synthetic_carry(self) -> None:
        pair = PmccPair(
            spot_entry=self.spot,
            leaps_strike=410.0,
            leaps_exp="2028-06-16",
            leaps_dte=700,
            leaps_iv=0.55,
            leaps_debit=13000.0,
            short_strike=500.0,
            short_exp="2026-08-21",
            short_dte=57,
            short_iv=0.50,
            short_credit=700.0,
            leaps_delta_target=0.65,
            short_delta_target=0.30,
        )
        carry = income_metrics(
            {"entry_date": "2026-06-01", "short_open_dte": 60},
            pair,
            self.spot,
            short_mark=350.0,
            leaps_mark=13000.0,
        )
        print("SYNTHETIC CARRY wait_good:", carry["wait_good_days_after_harvest"])
        self.assertIn("wait_good_days_after_harvest", carry)
        self.assertIn("net_full_credit_daily", carry)


if __name__ == "__main__":
    unittest.main()
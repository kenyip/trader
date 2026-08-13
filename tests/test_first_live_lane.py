"""First-live single-leg capital-fit ranker."""

from __future__ import annotations

import unittest

from trader_platform.first_live_lane import (
    classify_place_shape,
    rank_first_live_seats,
)


class FirstLiveLaneTest(unittest.TestCase):
    def test_classify_place_shape(self):
        self.assertEqual(classify_place_shape("cash_secured_put"), "single_leg")
        self.assertEqual(classify_place_shape("put_credit_spread"), "multi_leg")
        self.assertEqual(classify_place_shape("short_put_credit"), "single_leg")

    def test_csp_sleeve_fit_not_collateral_as_300_bar(self):
        """CSP collateral is the capital gate; $300 bar is for explicit path stops / longs.

        2026-08-08 coach: treating short BP as max_loss emptied the board (SNAP CSP
        ml≈500>300 forever) while doctrine prefers SNAP/TSLL CSP first-arm DNA.
        """
        sims = [
            {
                "dna_id": "dna_nflx",
                "structure": "cash_secured_put",
                "symbol": "NFLX",
                "verdict": "SHIP",
                "score": 1000.0,
                "n_trades": 90,
                "metrics": {},
                "config": {},
                "hyp_id": "hyp_nflx",
            },
            {
                "dna_id": "dna_tsll",
                "structure": "cash_secured_put",
                "symbol": "TSLL",
                "verdict": "SHIP",
                "score": 200.0,
                "n_trades": 40,
                "metrics": {},
                "config": {},
                "hyp_id": "hyp_tsll",
            },
            {
                "dna_id": "dna_snap",
                "structure": "cash_secured_put",
                "symbol": "SNAP",
                "verdict": "SHIP",
                "score": 80.0,
                "n_trades": 100,
                "metrics": {},
                "config": {},
                "hyp_id": "hyp_snap",
            },
            {
                "dna_id": "dna_f_long",
                "structure": "long_call",
                "symbol": "F",
                "verdict": "SHIP",
                "score": 150.0,
                "n_trades": 30,
                "metrics": {"max_loss_usd": 250.0},
                "config": {},
                "hyp_id": "hyp_f_long",
            },
        ]
        capital = {
            "NFLX": {
                "spot": 70.0,
                "short_premium_bp_proxy": 6650.0,
                "capital_fit": "fit_15k",
                "capital_fit_long": "fit_3k",
            },
            "TSLL": {
                "spot": 8.0,
                "short_premium_bp_proxy": 760.0,
                "capital_fit": "fit_3k",
                "capital_fit_long": "fit_3k",
            },
            "SNAP": {
                "spot": 5.0,
                "short_premium_bp_proxy": 500.0,
                "capital_fit": "fit_3k",
                "capital_fit_long": "fit_3k",
            },
            "F": {
                "spot": 12.0,
                "short_premium_bp_proxy": 1140.0,
                "capital_fit": "fit_3k",
                "capital_fit_long": "fit_3k",
            },
        }
        report = rank_first_live_seats(
            sim_rows=sims,
            capital_by_symbol=capital,
            min_trades=15,
            top_n=5,
            registry_dna_ids={"dna_nflx", "dna_tsll", "dna_snap", "dna_f_long"},
        )
        # SNAP + TSLL CSP fit_3k collateral + F long debit under $300 bar
        self.assertGreaterEqual(report["n_eligible"], 3)
        elig_syms = {s["symbol"] for s in report["shortlist"] if s.get("eligible")}
        self.assertIn("SNAP", elig_syms)
        self.assertIn("TSLL", elig_syms)
        self.assertIn("F", elig_syms)
        self.assertFalse(report["live_authority"])
        snap = next(s for s in report["shortlist"] if s["symbol"] == "SNAP")
        self.assertTrue(snap.get("fits_test_cash_500"))
        tsll = next(s for s in report["shortlist"] if s["symbol"] == "TSLL")
        self.assertFalse(tsll.get("fits_test_cash_500"))
        near = report["near_miss_oversized"]
        self.assertTrue(any(r["symbol"] == "NFLX" for r in near))
        nflx = next(r for r in near if r["symbol"] == "NFLX")
        self.assertTrue(
            any(x.startswith("csp_bp=") or x.startswith("capital_fit=") for x in nflx["reject_reasons"])
        )

    def test_csp_explicit_path_stop_still_honors_300_bar(self):
        sims = [
            {
                "dna_id": "dna_tsll_stop",
                "structure": "cash_secured_put",
                "symbol": "TSLL",
                "verdict": "SHIP",
                "score": 50.0,
                "n_trades": 40,
                "metrics": {"max_loss_usd": 450.0},
                "config": {},
                "hyp_id": "hyp_tsll_stop",
            }
        ]
        capital = {
            "TSLL": {
                "spot": 8.0,
                "short_premium_bp_proxy": 760.0,
                "capital_fit": "fit_3k",
                "capital_fit_long": "fit_3k",
            }
        }
        report = rank_first_live_seats(
            sim_rows=sims,
            capital_by_symbol=capital,
            min_trades=15,
            registry_dna_ids={"dna_tsll_stop"},
        )
        self.assertEqual(report["n_eligible"], 0)
        self.assertIn("max_loss=450>300", report["near_miss_oversized"][0]["reject_reasons"])

    def test_rejects_thin_sim(self):
        sims = [
            {
                "dna_id": "dna_x",
                "structure": "short_put_credit",
                "symbol": "F",
                "verdict": "SHIP",
                "score": 50.0,
                "n_trades": 3,
                "metrics": {},
                "config": {},
            }
        ]
        capital = {
            "F": {
                "spot": 12.0,
                "short_premium_bp_proxy": 1140.0,
                "capital_fit": "fit_3k",
                "capital_fit_long": "fit_3k",
            }
        }
        report = rank_first_live_seats(
            sim_rows=sims,
            capital_by_symbol=capital,
            min_trades=15,
            registry_dna_ids={"dna_x"},
        )
        self.assertEqual(report["n_eligible"], 0)
        self.assertIsNone(report["leader"])

    def test_rejects_short_seat_without_spot_or_loss_proxy(self):
        report = rank_first_live_seats(
            sim_rows=[
                {
                    "dna_id": "dna_wheel",
                    "structure": "wheel_assignment",
                    "symbol": "AAL",
                    "verdict": "SHIP",
                    "score": 20.0,
                    "n_trades": 29,
                    "metrics": {},
                    "config": {},
                }
            ],
            capital_by_symbol={},
            min_trades=15,
            registry_dna_ids={"dna_wheel"},
        )
        self.assertEqual(report["n_eligible"], 0)
        self.assertIsNone(report["leader"])
        self.assertIn("no_spot_bp", report["near_miss_oversized"][0]["reject_reasons"])

    def test_rejects_ghost_dna_not_in_registry(self):
        """Sim-only DNA (never promoted to hypotheses.yaml) must not lead the board."""
        sims = [
            {
                "dna_id": "dna_ghostabc123",
                "structure": "cash_secured_put",
                "symbol": "SNAP",
                "verdict": "SHIP",
                "score": 999.0,
                "n_trades": 100,
                "metrics": {},
                "config": {},
            }
        ]
        capital = {
            "SNAP": {
                "spot": 5.0,
                "short_premium_bp_proxy": 500.0,
                "capital_fit": "fit_3k",
                "capital_fit_long": "fit_3k",
            }
        }
        report = rank_first_live_seats(
            sim_rows=sims,
            capital_by_symbol=capital,
            min_trades=15,
            registry_dna_ids={"dna_real123456"},
        )
        self.assertEqual(report["n_eligible"], 0)
        self.assertIsNone(report["leader"])
        self.assertEqual(report["n_ghost_dna"], 1)
        self.assertIn(
            "ghost_dna_no_registry_hyp",
            report["near_miss_oversized"][0]["reject_reasons"],
        )


if __name__ == "__main__":
    unittest.main()

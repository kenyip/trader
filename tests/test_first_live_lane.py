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

    def test_rank_requires_strict_loss_fit_not_only_sleeve_fit(self):
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
        )
        self.assertEqual(report["n_eligible"], 1)
        self.assertEqual(report["leader"]["symbol"], "F")
        self.assertTrue(report["leader"]["eligible"])
        self.assertFalse(report["live_authority"])
        near = report["near_miss_oversized"]
        self.assertTrue(any(r["symbol"] == "NFLX" for r in near))
        tsll = next(r for r in near if r["symbol"] == "TSLL")
        self.assertIn("max_loss=760>300", tsll["reject_reasons"])

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
        )
        self.assertEqual(report["n_eligible"], 0)
        self.assertIsNone(report["leader"])
        self.assertIn("no_spot_bp", report["near_miss_oversized"][0]["reject_reasons"])


if __name__ == "__main__":
    unittest.main()

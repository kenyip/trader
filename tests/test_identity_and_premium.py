"""Engine contracts for premium/day score + coarse DNA diversify."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import date

import pandas as pd

from trader_platform.research.evaluate_proxy import premium_per_day_stats
from trader_platform.research.identity import coarse_dna_key, diversify_rows


@dataclass
class _T:
    net_credit: float
    exit_debit: float
    entry_date: date
    exit_date: date


class PremiumPerDayTest(unittest.TestCase):
    def test_premium_per_day_math(self):
        trades = [
            _T(1.0, 0.4, date(2024, 1, 1), date(2024, 1, 11)),  # 0.6/10 = 0.06
            _T(0.8, 0.3, date(2024, 2, 1), date(2024, 2, 3)),  # 0.5/2 = 0.25
        ]
        stats = premium_per_day_stats(trades)
        self.assertIsNotNone(stats["premium_per_day_mean"])
        self.assertAlmostEqual(float(stats["premium_per_day_mean"]), (0.06 + 0.25) / 2, places=5)
        self.assertIsNotNone(stats["premium_per_day_median"])

    def test_empty_trades(self):
        stats = premium_per_day_stats([])
        self.assertIsNone(stats["premium_per_day_mean"])


class CoarseDnaTest(unittest.TestCase):
    def test_same_coarse_dna_collapses_clones(self):
        a = coarse_dna_key(
            family_id="LONG_BIAS_PCS__g_d14_pt50_x",
            router_policy="pcs_non_bear",
            management={"long_dte": 21, "profit_target": 0.5, "iv_rank_min": 0.0, "long_target_delta": 0.18},
            evaluation_mode="regime_router",
        )
        b = coarse_dna_key(
            family_id="LONG_BIAS_PCS__dn_d14_pt50_y",
            router_policy="pcs_non_bear",
            management={"long_dte": 21, "profit_target": 0.5, "iv_rank_min": 0.0, "long_target_delta": 0.18},
            evaluation_mode="regime_router",
        )
        self.assertEqual(a, b)

    def test_different_dte_band_differs(self):
        a = coarse_dna_key(
            family_id="LONG_BIAS_PCS",
            router_policy="pcs_non_bear",
            management={"long_dte": 14, "profit_target": 0.5},
        )
        b = coarse_dna_key(
            family_id="LONG_BIAS_PCS",
            router_policy="pcs_non_bear",
            management={"long_dte": 45, "profit_target": 0.5},
        )
        self.assertNotEqual(a, b)

    def test_diversify_by_symbol_and_dna(self):
        rows = [
            {"seat_id": "1", "symbols": ["INTC"], "coarse_dna_key": "A", "rank": 1},
            {"seat_id": "2", "symbols": ["INTC"], "coarse_dna_key": "A", "rank": 2},
            {"seat_id": "3", "symbols": ["BAC"], "coarse_dna_key": "A", "rank": 3},
            {"seat_id": "4", "symbols": ["KO"], "coarse_dna_key": "B", "rank": 4},
            {"seat_id": "5", "symbols": ["IWM"], "coarse_dna_key": "C", "rank": 5},
        ]
        chosen = diversify_rows(rows, top_n=3, by_symbol=True, by_dna=True)
        ids = [c["seat_id"] for c in chosen]
        self.assertEqual(ids[0], "1")
        # seat 2 same symbol+dna skipped; seat 3 same dna as 1 skipped when by_dna
        self.assertIn("4", ids)
        self.assertEqual(len(chosen), 3)


if __name__ == "__main__":
    unittest.main()

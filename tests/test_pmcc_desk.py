from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from pmcc.desk import (
    assemble_pmcc_desk,
    candidate_is_preferred,
    candidate_table_styler,
    compute_patience_expires,
    desk_gating_lines,
    position_record_key,
    position_remove_match,
)
from pmcc.income import reentry_candidates
from pmcc.positions import load_pmcc_positions


class AssemblePmccDeskIntegrationTest(unittest.TestCase):
    def test_assemble_pmcc_desk_live_yaml(self) -> None:
        records = load_pmcc_positions()
        if not records:
            self.skipTest("no pmcc_positions.yaml")

        bundle = assemble_pmcc_desk(records, preset="managed", refresh=False)
        self.assertEqual(len(bundle.statuses), len(records))

        keys = {position_record_key(r) for r in records}
        self.assertEqual(len(keys), len(records))

        nvda_rows = [
            r for r in bundle.position_rows
            if "NVDA" in r.get("diagonal", "") and r.get("leg") == "LEAPS"
        ]
        if nvda_rows:
            upside = float(nvda_rows[0]["upside_pct"].rstrip("%"))
            self.assertGreater(upside, 0.0)

        for s in bundle.statuses:
            ticker = str(s["record"].get("ticker", "TSLA")).upper()
            spot = bundle.spots_by_ticker[ticker]
            self.assertAlmostEqual(s["spot_now"], spot, places=1)

        candidates = bundle.next_short.get("candidates") or []
        self.assertGreater(len(candidates), 0)
        self.assertIn("_prefer", candidates[0])

        tsla_status = next(
            s for s in bundle.statuses
            if str(s["record"].get("ticker", "TSLA")).upper() == "TSLA"
        )
        full_cands = reentry_candidates(
            tsla_status["spot_now"],
            tsla_status["pair"],
            chain=bundle.tsla_chain,
        )
        self.assertTrue(any(candidate_is_preferred(c) for c in full_cands))

        prefer_rows = [c for c in candidates if c.get("_prefer")]
        styler_input = pd.DataFrame(prefer_rows) if prefer_rows else pd.DataFrame([{
            "strike": "$500",
            "income": "good",
            "risk": "balanced",
            "prefer": "✓",
            "_prefer": True,
        }])
        styled = candidate_table_styler(styler_input)
        self.assertIn("background-color", styled.to_html())

        lines = desk_gating_lines(bundle)
        self.assertIn("VERIFY OK", lines)
        self.assertTrue(any(line.startswith("RECORDS:") for line in lines))
        self.assertTrue(any(line.startswith("REENTRY COUNT:") for line in lines))
        self.assertTrue(any("STYLED HTML background-color: present" in line for line in lines))
        self.assertTrue(any("background-color:" in line for line in lines))
        self.assertEqual(bundle.situation["patience_expires"]["date"], "2026-07-01")
        self.assertTrue(any(line.startswith("PATIENCE EXPIRES: 2026-07-01") for line in lines))
        self.assertTrue(any(line.startswith("PATIENCE SOURCE: delivery window") for line in lines))

    def test_position_record_key_distinguishes_same_strike_lots(self) -> None:
        a = {
            "ticker": "TSLA",
            "leaps_strike": 410,
            "leaps_expiration": "2028-06-16",
            "leaps_debit": 13000,
            "contracts": 2,
            "open_short": False,
        }
        b = {
            "ticker": "TSLA",
            "leaps_strike": 410,
            "leaps_expiration": "2028-06-16",
            "leaps_debit": 10800,
            "contracts": 1,
            "open_short": False,
        }
        self.assertNotEqual(position_record_key(a), position_record_key(b))
        self.assertFalse(position_remove_match(a, b))


class ComputePatienceExpiresTest(unittest.TestCase):
    _clock_status = {
        "no_open_short": True,
        "closed_short_clock": {
            "targets": {"good": {"portfolio_budget_until": "2026-07-03"}},
        },
    }

    def test_delivery_window_wins(self) -> None:
        result = compute_patience_expires(
            staged_events={
                "delivery_window": "2026-07-01 to 2026-07-03 (estimate)",
                "earnings_date": "2026-07-22",
            },
            statuses=[self._clock_status],
            today=date(2026, 6, 26),
        )
        self.assertEqual(result["date"], "2026-07-01")
        self.assertEqual(result["explanation"], "delivery window")

    def test_premium_clock_wins(self) -> None:
        result = compute_patience_expires(
            staged_events={
                "delivery_window": "2026-07-05 to 2026-07-07",
                "earnings_date": "2026-07-22",
            },
            statuses=[self._clock_status],
            today=date(2026, 6, 26),
        )
        self.assertEqual(result["date"], "2026-07-03")
        self.assertEqual(result["explanation"], "premium clock portfolio budget")

    def test_earnings_minus_five_wins(self) -> None:
        result = compute_patience_expires(
            staged_events={
                "delivery_window": "2026-07-20 to 2026-07-22",
                "earnings_date": "2026-07-22",
            },
            statuses=[],
            today=date(2026, 6, 26),
        )
        self.assertEqual(result["date"], "2026-07-17")
        self.assertEqual(result["explanation"], "earnings − 5 calendar days")


if __name__ == "__main__":
    unittest.main()
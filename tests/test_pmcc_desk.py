from __future__ import annotations

import math
import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from pmcc.desk import (
    assemble_pmcc_desk,
    candidate_table_styler,
    compute_patience_expires,
    desk_gating_lines,
    position_record_key,
    position_remove_match,
    select_next_short,
)
from pmcc.income import reentry_candidates
from pmcc.positions import (
    close_short_on_record,
    load_pmcc_positions,
    make_leaps_record,
    open_short_on_record,
)
from pmcc.scenarios import PmccPair


class AssemblePmccDeskIntegrationTest(unittest.TestCase):
    def test_harvest_preview_falls_back_to_model_credit_when_bid_is_none(self) -> None:
        pair = PmccPair(
            spot_entry=400.0,
            leaps_strike=300.0,
            leaps_exp="2028-06-16",
            leaps_dte=700,
            leaps_iv=0.50,
            leaps_debit=120.0,
            short_strike=450.0,
            short_exp="2026-09-18",
            short_dte=66,
            short_iv=0.45,
            short_credit=4.0,
            leaps_delta_target=0.70,
            short_delta_target=0.20,
        )
        candidate = {
            "strike": 460.0,
            "dte": 66,
            "credit": 4.0,
            "bid_credit": None,
            "daily": 0.06,
            "delta": 0.10,
            "upside_pct": 15.0,
            "risk": "balanced",
            "income": "good",
            "expiration": "2026-09-18",
        }
        status = {
            "no_open_short": False,
            "primary_action": "HOLD",
            "pair": pair,
            "carry": {"current_short_profit": 500.0, "harvest_profit": 400.0, "harvest_mark": 100.0},
        }

        with patch("pmcc.desk.reentry_candidates", return_value=[candidate]):
            result = select_next_short(
                spot=400.0,
                chain=None,
                records=[],
                statuses=[status],
                staged=None,
                today=date(2026, 7, 14),
            )

        self.assertEqual(result["source"], "harvest")
        self.assertIn("preview reload $460 ~$4 ($0.1/d)", result["hero"])

        reentry_status = dict(status)
        reentry_status["no_open_short"] = True
        reentry_status["primary_action"] = "OPEN_SHORT"
        with patch("pmcc.desk.reentry_candidates", return_value=[candidate]):
            reentry_result = select_next_short(
                spot=400.0,
                chain=None,
                records=[],
                statuses=[reentry_status],
                staged=None,
                today=date(2026, 7, 14),
            )

        self.assertEqual(reentry_result["source"], "reentry")
        self.assertIn("target ≥ $4", reentry_result["hero"])

        zero_bid_candidate = dict(candidate, bid_credit=0.0)
        with patch("pmcc.desk.reentry_candidates", return_value=[zero_bid_candidate]):
            zero_bid_result = select_next_short(
                spot=400.0,
                chain=None,
                records=[],
                statuses=[reentry_status],
                staged=None,
                today=date(2026, 7, 14),
            )
        self.assertEqual(zero_bid_result["source"], "reentry")
        self.assertIn("target ≥ $0", zero_bid_result["hero"])
        self.assertNotIn("target ≥ $4", zero_bid_result["hero"])

    def test_assemble_pmcc_desk_live_yaml(self) -> None:
        records = load_pmcc_positions()
        if not records:
            self.skipTest("no pmcc_positions.yaml")

        bundle = assemble_pmcc_desk(records, preset="managed", refresh=False)
        self.assertEqual(len(bundle.statuses), len(records))

        keys = {position_record_key(r) for r in records}
        self.assertEqual(len(keys), len(records))

        nvda_rows = [r for r in bundle.position_rows if r.get("position", "").startswith("NVDA")]
        if nvda_rows:
            upside = float(nvda_rows[0]["upside"].rstrip("%"))
            # Live positions can legitimately be capped/ITM, so upside may be
            # negative. The integration invariant is a finite rendered metric.
            self.assertTrue(math.isfinite(upside))

        for s in bundle.statuses:
            ticker = str(s["record"].get("ticker", "TSLA")).upper()
            spot = bundle.spots_by_ticker[ticker]
            self.assertAlmostEqual(s["spot_now"], spot, places=1)

        candidates = bundle.next_short.get("candidates") or []
        self.assertGreater(len(candidates), 0)
        self.assertIn("_prefer", candidates[0])
        if bundle.next_short.get("source") == "staged":
            pkg = bundle.next_short.get("staged_package") or {}
            pkg_strikes = {int(s) for s in pkg.get("leg_strikes") or []}
            picked = [c for c in candidates if c.get("pick")]
            for row in picked:
                strike = int(str(row["strike"]).lstrip("$"))
                self.assertIn(strike, pkg_strikes)
            top = candidates[0]
            if pkg_strikes and int(str(top["strike"]).lstrip("$")) not in pkg_strikes:
                self.assertFalse(top.get("pick"))

        tsla_status = next(
            s for s in bundle.statuses
            if str(s["record"].get("ticker", "TSLA")).upper() == "TSLA"
        )
        full_cands = reentry_candidates(
            tsla_status["spot_now"],
            tsla_status["pair"],
            chain=bundle.tsla_chain,
        )
        self.assertGreater(len(full_cands), 0)
        # Live IV/spot can legitimately leave every candidate below the
        # carry-income threshold. The integration invariant is a nonempty,
        # finite candidate surface, not a forced preferred trade.
        for candidate in full_cands:
            self.assertTrue(math.isfinite(float(candidate["strike"])))
            self.assertTrue(math.isfinite(float(candidate["daily"])))
            self.assertTrue(math.isfinite(float(candidate["upside_pct"])))

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
        patience = bundle.situation["patience_expires"]
        date.fromisoformat(patience["date"])
        self.assertTrue(any(line.startswith(f"PATIENCE EXPIRES: {patience['date']}") for line in lines))
        self.assertTrue(any(line.startswith(f"PATIENCE SOURCE: {patience['explanation']}") for line in lines))

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


class PmccTradeLogTest(unittest.TestCase):
    def test_open_and_close_short_appends_transaction(self) -> None:
        lot = make_leaps_record(
            ticker="TSLA",
            leaps_strike=400,
            leaps_expiration="2028-06-16",
            leaps_debit=11000,
            contracts=2,
        )
        with_short = open_short_on_record(
            lot,
            strike=500,
            expiration="2026-08-21",
            credit=725,
            contracts=1,
            opened="2026-06-22",
        )
        closed = close_short_on_record(
            with_short,
            close_debit=400,
            closed="2026-06-23",
            notes="harvest",
        )
        self.assertFalse(closed.get("short_strike"))
        self.assertEqual(len(closed["closed_shorts"]), 1)
        self.assertEqual(closed["closed_shorts"][0]["realized_pnl"], 325)


if __name__ == "__main__":
    unittest.main()

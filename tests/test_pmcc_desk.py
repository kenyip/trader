from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from pmcc.desk import (
    build_position_rows,
    build_situation,
    compute_patience_expires,
    next_earnings_date,
    position_record_key,
    position_remove_match,
    select_next_short,
)
from pmcc.income import income_metrics, reentry_candidates
from pmcc.positions import check_leaps_only_position
from pmcc.scenarios import PmccPair
from pmcc.staged_entry import build_tsla_staged_entry_plan


class PmccDeskTest(unittest.TestCase):
    def setUp(self) -> None:
        self.chain = pd.DataFrame([
            {"expiration": "2026-08-21", "dte": 57, "strike": 450.0, "bid": 6.80, "ask": 6.95, "mid": 6.875, "iv": 0.475, "delta": 0.20},
            {"expiration": "2026-08-21", "dte": 57, "strike": 470.0, "bid": 4.70, "ask": 4.80, "mid": 4.75, "iv": 0.483, "delta": 0.15},
            {"expiration": "2026-08-21", "dte": 57, "strike": 500.0, "bid": 2.86, "ask": 2.94, "mid": 2.90, "iv": 0.501, "delta": 0.09},
            {"expiration": "2026-08-21", "dte": 57, "strike": 520.0, "bid": 2.14, "ask": 2.20, "mid": 2.17, "iv": 0.516, "delta": 0.07},
            {"expiration": "2026-08-21", "dte": 57, "strike": 540.0, "bid": 1.55, "ask": 1.60, "mid": 1.57, "iv": 0.52, "delta": 0.05},
        ])
        self.records = [
            {"ticker": "TSLA", "leaps_strike": 410, "leaps_expiration": "2028-06-16", "leaps_debit": 13000, "contracts": 2, "open_short": False},
        ]
        self.pair = PmccPair(
            spot_entry=375.0,
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

    def test_next_earnings_prefers_staged_date(self) -> None:
        d = next_earnings_date(today=date(2026, 6, 25), staged_earnings="2026-07-22")
        self.assertEqual(d, date(2026, 7, 22))

    def test_compute_patience_expires_returns_earliest_deadline(self) -> None:
        staged = build_tsla_staged_entry_plan(self.records, self.chain, spot=375.0, today=date(2026, 6, 25))
        result = compute_patience_expires(staged_events=staged["events"], statuses=[], today=date(2026, 6, 25))
        self.assertIn("date", result)
        self.assertIn("label", result)
        self.assertTrue(result["date"] <= "2026-07-17")

    def test_reentry_candidates_chain_bid_fields(self) -> None:
        rows = reentry_candidates(
            375.0, self.pair, chain=self.chain, expiration="2026-08-21",
        )
        self.assertGreater(len(rows), 0)
        chain_rows = [r for r in rows if r.get("source") == "chain"]
        self.assertGreater(len(chain_rows), 0)
        row = chain_rows[0]
        self.assertIn("daily", row)
        self.assertIn("risk", row)
        self.assertIn("income", row)
        self.assertIsNotNone(row.get("bid_credit"))

    def test_build_situation_from_empty_statuses(self) -> None:
        staged = build_tsla_staged_entry_plan(self.records, self.chain, spot=375.0, today=date(2026, 6, 25))
        sit = build_situation(spot=375.0, chain_age_minutes=12.0, statuses=[], staged=staged)
        self.assertEqual(sit["spot"], 375.0)
        self.assertIn("catalyst", sit)
        self.assertIn("patience_expires", sit)

    def test_select_next_short_staged_when_building_stack(self) -> None:
        staged = build_tsla_staged_entry_plan(self.records, self.chain, spot=375.0, today=date(2026, 6, 25))
        out = select_next_short(
            spot=375.0,
            chain=self.chain,
            records=self.records,
            statuses=[],
            staged=staged,
        )
        self.assertEqual(out["source"], "staged")
        self.assertIn("hero", out)
        self.assertGreater(len(out.get("candidates", [])), 0)

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
        self.assertTrue(position_remove_match(a, dict(a)))

    def test_staged_entry_sparse_chain_uses_model_fallback(self) -> None:
        sparse = self.chain[self.chain["strike"] >= 500.0]
        plan = build_tsla_staged_entry_plan(self.records, sparse, spot=375.0, today=date(2026, 6, 25))
        self.assertIn("packages", plan)
        self.assertGreater(plan["packages"]["initial"]["bid_credit"], 0)

    def test_income_metrics_carry_has_wait_and_net_daily_fields(self) -> None:
        record = {
            "entry_date": "2026-06-01",
            "short_open_date": "2026-06-01",
            "short_open_dte": 60,
            "income_floor_daily": 10.0,
            "income_good_daily": 15.0,
            "income_strong_daily": 20.0,
        }
        carry = income_metrics(record, self.pair, 375.0, short_mark=350.0, leaps_mark=13000.0)
        for key in (
            "wait_floor_days_after_harvest",
            "wait_good_days_after_harvest",
            "net_current_profit_daily",
            "net_full_credit_daily",
        ):
            self.assertIn(key, carry)

    def test_leaps_only_status_has_closed_short_clock(self) -> None:
        record = {
            "ticker": "TSLA",
            "leaps_strike": 410,
            "leaps_expiration": "2028-06-16",
            "leaps_debit": 13000,
            "contracts": 2,
            "open_short": False,
            "entry_date": "2026-06-20",
            "closed_shorts": [{
                "credit": 325,
                "close_debit": 50,
                "contracts": 1,
                "opened": "2026-06-20",
                "closed": "2026-06-23",
            }],
        }
        status = check_leaps_only_position(record, 375.0, preset="managed")
        clock = status.get("closed_short_clock")
        self.assertIsNotNone(clock)
        good = clock["targets"]["good"]
        self.assertIn("portfolio_wait_days", good)
        self.assertIn("portfolio_budget_until", good)

    def test_build_position_rows_leaps_only(self) -> None:
        status = {
            "pair": self.pair,
            "record": self.records[0],
            "contracts": 2,
            "no_open_short": True,
            "leaps_mark": {"price": 130.0, "delta": 0.65},
            "leaps_leg_pnl": 500.0,
            "net_pnl": 500.0,
            "net_pnl_total": 1000.0,
            "realized_short_total": 200.0,
            "primary_action": "LEAPS ONLY",
            "primary_level": "info",
            "checks": [{"level": "info", "rule": "LEAPS ONLY", "detail": "no short"}],
        }
        rows = build_position_rows([status], 375.0)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["leg"], "LEAPS")
        self.assertEqual(rows[1]["leg"], "Closed shorts")


if __name__ == "__main__":
    unittest.main()
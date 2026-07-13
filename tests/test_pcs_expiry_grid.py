import unittest
from typing import cast
from unittest.mock import patch

import pandas as pd

from trader_platform.research.pcs_sim import (
    ContractGrid,
    PcsTrade,
    entry_filters_pass,
    listed_weekly_expiration,
    max_close_debit,
    pick_iron_condor_entry,
    pick_vertical_entry,
    run_pcs_backtest,
)


class PcsExpiryGridTest(unittest.TestCase):
    def test_current_row_entry_filters_include_boundaries_and_fail_closed(self):
        config = {
            "entry_intraday_return_max": -2.0,
            "entry_volume_surge_min": 1.2,
            "entry_rsi_min": 30.0,
        }

        self.assertTrue(
            entry_filters_pass(
                pd.Series({"intraday_return": -2.0, "volume_surge": 1.2, "rsi_14": 30.0}),
                config,
            )
        )
        self.assertFalse(
            entry_filters_pass(
                pd.Series({"intraday_return": -1.99, "volume_surge": 1.2, "rsi_14": 30.0}),
                config,
            )
        )
        self.assertFalse(entry_filters_pass(pd.Series({"intraday_return": -3.0}), config))

    def test_backtest_lagged_signal_never_enters_on_the_signal_bar(self):
        dates = pd.bdate_range("2026-05-01", periods=30)
        intraday = [-3.0 if index % 4 == 0 else 0.0 for index in range(len(dates))]
        history = pd.DataFrame(
            {
                "close": [50.0] * len(dates),
                "iv_proxy": [0.45] * len(dates),
                "iv_rank": [60.0] * len(dates),
                "regime": ["neutral"] * len(dates),
                "intraday_return": intraday,
                "volume_surge": [1.5] * len(dates),
            },
            index=dates,
        )

        result = run_pcs_backtest(
            "TEST",
            df=history,
            config={
                "long_dte": 7,
                "long_target_delta": 0.20,
                "spread_width": 1.0,
                "min_credit_pct": 0.0,
                "profit_target": 0.0,
                "entry_intraday_return_max": -2.0,
                "entry_volume_surge_min": 1.2,
                "entry_signal_lag_bars": 1,
            },
        )

        self.assertGreater(result.n_trades, 0)
        signal_dates = set(history.index[history["intraday_return"] <= -2.0])
        expected_entry_dates = {
            cast(pd.Timestamp, history.index[index + 1])
            for index, date in enumerate(history.index[:-1])
            if date in signal_dates
        }
        self.assertTrue(all(trade.entry_date in expected_entry_dates for trade in result.trades))
        self.assertTrue(all(trade.entry_date not in signal_dates for trade in result.trades))

    def test_backtest_lag_applies_to_all_entry_features_not_only_filters(self):
        dates = pd.bdate_range("2026-05-01", periods=2)
        history = pd.DataFrame(
            {
                "close": [50.0, 50.0],
                "iv_proxy": [0.45, 0.45],
                "iv_rank": [60.0, 60.0],
                "regime": ["bearish", "bullish"],
            },
            index=dates,
        )

        result = run_pcs_backtest(
            "TEST",
            df=history,
            min_bars=1,
            config={
                "long_dte": 7,
                "long_target_delta": 0.20,
                "spread_width": 1.0,
                "min_credit_pct": 0.0,
                "entry_signal_lag_bars": 1,
                "bear_dte": 0,
            },
        )

        self.assertEqual(result.n_trades, 0)

    def test_backtest_entry_session_bucket_filters_intraday_entries(self):
        timestamps = pd.to_datetime(
            ["2026-05-01 09:30", "2026-05-01 10:00", "2026-05-01 14:00"]
        )
        history = pd.DataFrame(
            {
                "close": [50.0, 50.0, 50.0],
                "iv_proxy": [0.45, 0.45, 0.45],
                "iv_rank": [60.0, 60.0, 60.0],
                "regime": ["neutral", "neutral", "neutral"],
                "session_bucket": ["open", "open", "late"],
            },
            index=timestamps,
        )

        result = run_pcs_backtest(
            "TEST",
            df=history,
            min_bars=1,
            config={
                "long_dte": 7,
                "long_target_delta": 0.20,
                "spread_width": 1.0,
                "min_credit_pct": 0.0,
                "profit_target": 0.0,
                "entry_session_buckets": ["late"],
            },
        )

        self.assertGreater(result.n_trades, 0)
        self.assertTrue(all(trade.entry_date.hour >= 14 for trade in result.trades))

    def test_backtest_does_not_reenter_the_same_session_bucket_on_one_date(self):
        timestamps = pd.to_datetime(
            ["2026-05-01 14:00", "2026-05-01 14:30", "2026-05-01 15:00"]
        )
        history = pd.DataFrame(
            {
                "close": [50.0, 50.0, 50.0],
                "iv_proxy": [0.45, 0.45, 0.45],
                "iv_rank": [60.0, 60.0, 60.0],
                "regime": ["neutral", "neutral", "neutral"],
                "session_bucket": ["late", "late", "late"],
            },
            index=timestamps,
        )

        result = run_pcs_backtest(
            "TEST",
            df=history,
            min_bars=1,
            config={
                "long_dte": 7,
                "long_target_delta": 0.20,
                "spread_width": 1.0,
                "min_credit_pct": 0.0,
                "profit_target": 0.0,
                "entry_session_buckets": ["late"],
            },
        )

        self.assertEqual(result.n_trades, 1)

    def test_backtest_exit_consumes_session_bucket_before_later_reentry(self):
        timestamps = pd.to_datetime(
            ["2026-05-01 14:00", "2026-05-04 14:00", "2026-05-04 14:30"]
        )
        history = pd.DataFrame(
            {
                "close": [50.0, 50.0, 50.0],
                "iv_proxy": [0.45, 0.45, 0.45],
                "iv_rank": [60.0, 60.0, 60.0],
                "regime": ["neutral", "neutral", "neutral"],
                "session_bucket": ["late", "late", "late"],
            },
            index=timestamps,
        )

        result = run_pcs_backtest(
            "TEST",
            df=history,
            min_bars=1,
            config={
                "long_dte": 7,
                "long_target_delta": 0.20,
                "spread_width": 1.0,
                "min_credit_pct": 0.0,
                "profit_target": 0.0,
                "entry_session_buckets": ["late"],
            },
        )

        self.assertEqual(result.n_trades, 1)

    def test_target_dte_rolls_forward_to_listed_friday(self):
        entry = cast(pd.Timestamp, pd.Timestamp("2026-07-06"))

        expiration = listed_weekly_expiration(entry, 14)

        self.assertEqual(expiration, pd.Timestamp("2026-07-24"))
        self.assertEqual(expiration.weekday(), 4)

    def test_friday_target_is_not_rolled_an_extra_week(self):
        entry = cast(pd.Timestamp, pd.Timestamp("2026-07-03"))

        expiration = listed_weekly_expiration(entry, 14)

        self.assertEqual(expiration, pd.Timestamp("2026-07-17"))

    def test_vertical_prices_and_records_actual_listed_dte(self):
        entry = cast(pd.Timestamp, pd.Timestamp("2026-07-06"))
        row = pd.Series(
            {"iv_proxy": 0.45, "iv_rank": 60.0, "regime": "neutral"}
        )

        trade = pick_vertical_entry(
            row,
            50.0,
            entry,
            {
                "long_dte": 14,
                "long_target_delta": 0.20,
                "spread_width": 2.0,
                "min_credit_pct": 0.01,
                "max_loss_budget_usd": 300.0,
            },
        )

        self.assertIsNotNone(trade)
        assert trade is not None
        self.assertEqual(trade.expiration, pd.Timestamp("2026-07-24"))
        self.assertEqual(trade.dte_at_entry, 18)

    def test_timezone_aware_intraday_marks_use_calendar_dte(self):
        entry = cast(
            pd.Timestamp,
            pd.Timestamp("2026-07-06 09:30", tz="America/New_York"),
        )
        row = pd.Series(
            {"iv_proxy": 0.45, "iv_rank": 60.0, "regime": "neutral"}
        )
        trade = pick_vertical_entry(
            row,
            50.0,
            entry,
            {
                "long_dte": 7,
                "long_target_delta": 0.20,
                "spread_width": 1.0,
                "min_credit_pct": 0.0,
            },
        )

        self.assertIsNotNone(trade)
        assert trade is not None
        mark = trade.mark_net_debit(
            50.0,
            0.45,
            cast(
                pd.Timestamp,
                pd.Timestamp("2026-07-07 14:00", tz="America/New_York"),
            ),
            0.04,
        )

        self.assertEqual(trade.expiration, pd.Timestamp("2026-07-17"))
        self.assertEqual(mark["dte_remaining"], 10)

    def test_injected_grid_selects_actual_expiration_and_strikes(self):
        entry = cast(pd.Timestamp, pd.Timestamp("2026-07-06"))
        row = pd.Series({"iv_proxy": 0.45, "iv_rank": 60.0, "regime": "neutral"})
        grid: ContractGrid = {
            "2026-07-22": {"put": [43.0, 45.0, 47.0, 49.0]},
            "2026-07-29": {"put": [44.0, 46.0, 48.0]},
        }

        trade = pick_vertical_entry(
            row,
            50.0,
            entry,
            {
                "long_dte": 14,
                "long_target_delta": 0.20,
                "spread_width": 2.0,
                "min_credit_pct": 0.01,
                "max_loss_budget_usd": 300.0,
            },
            contract_grid=grid,
            require_contract_grid=True,
        )

        self.assertIsNotNone(trade)
        assert trade is not None
        self.assertEqual(trade.expiration, pd.Timestamp("2026-07-22"))
        self.assertIn(trade.short_strike, grid["2026-07-22"]["put"])
        self.assertIn(trade.long_strike, grid["2026-07-22"]["put"])
        self.assertEqual(trade.dte_at_entry, 16)

    def test_required_grid_fails_closed_when_absent(self):
        entry = cast(pd.Timestamp, pd.Timestamp("2026-07-06"))
        row = pd.Series({"iv_proxy": 0.45, "iv_rank": 60.0, "regime": "neutral"})

        trade = pick_vertical_entry(
            row,
            50.0,
            entry,
            {
                "long_dte": 14,
                "long_target_delta": 0.20,
                "spread_width": 2.0,
                "min_credit_pct": 0.01,
                "max_loss_budget_usd": 300.0,
            },
            require_contract_grid=True,
        )

        self.assertIsNone(trade)

    def test_required_grid_rejects_missing_right_or_wing(self):
        entry = cast(pd.Timestamp, pd.Timestamp("2026-07-06"))
        row = pd.Series({"iv_proxy": 0.45, "iv_rank": 60.0, "regime": "neutral"})

        trade = pick_vertical_entry(
            row,
            50.0,
            entry,
            {
                "long_dte": 14,
                "long_target_delta": 0.20,
                "spread_width": 2.0,
                "min_credit_pct": 0.01,
                "max_loss_budget_usd": 300.0,
            },
            contract_grid={"2026-07-24": {"call": [50.0, 52.0]}},
            require_contract_grid=True,
        )

        self.assertIsNone(trade)

    def test_backtest_required_grid_provider_fails_closed_without_coverage(self):
        dates = pd.bdate_range("2026-06-01", periods=20)
        history = pd.DataFrame(
            {
                "close": [50.0] * len(dates),
                "iv_proxy": [0.45] * len(dates),
                "iv_rank": [60.0] * len(dates),
                "regime": ["neutral"] * len(dates),
            },
            index=dates,
        )

        result = run_pcs_backtest(
            "TEST",
            df=history,
            config={"min_credit_pct": 0.01},
            contract_grid_provider=lambda _symbol, _date: None,
            require_contract_grid=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.n_trades, 0)
        self.assertEqual(result.metrics["contract_grid_mode"], "required_observed")


    def test_asymmetric_condor_uses_side_specific_delta_width_and_regime_gate(self):
        entry = cast(pd.Timestamp, pd.Timestamp("2026-07-06"))
        base = pd.Series({"iv_proxy": 0.45, "iv_rank": 60.0, "regime": "bullish"})
        config = {
            "long_dte": 14,
            "put_target_delta": 0.25,
            "call_target_delta": 0.10,
            "put_spread_width": 1.0,
            "call_spread_width": 2.0,
            "put_min_credit_pct": 0.0,
            "call_min_credit_pct": 0.0,
            "min_credit_pct": 0.01,
            "max_loss_budget_usd": 300.0,
            "ic_allowed_regimes": ["bullish", "neutral"],
        }

        trade = pick_iron_condor_entry(base, 50.0, entry, config)

        self.assertIsNotNone(trade)
        assert trade is not None
        self.assertGreater(abs(trade.short_delta_entry), 0.20)
        self.assertEqual(abs(trade.short_strike - trade.long_strike), 1.0)
        self.assertEqual(trade.call_width, 2.0)
        bearish = base.copy()
        bearish["regime"] = "bearish"
        self.assertIsNone(pick_iron_condor_entry(bearish, 50.0, entry, config))

    def test_iron_condor_close_cap_is_widest_wing_not_sum_of_wings(self):
        trade = PcsTrade(
            entry_date=cast(pd.Timestamp, pd.Timestamp("2026-07-06")),
            expiration=cast(pd.Timestamp, pd.Timestamp("2026-07-24")),
            short_strike=48.0,
            long_strike=47.0,
            width=2.0,
            net_credit=0.40,
            dte_at_entry=18,
            iv_at_entry=0.45,
            regime_at_entry="neutral",
            short_delta_entry=-0.20,
            max_loss_per_share=1.60,
            right="iron_condor",
            call_short_strike=52.0,
            call_long_strike=54.0,
            call_width=2.0,
        )

        self.assertEqual(max_close_debit(trade), 2.0)
        self.assertEqual((max_close_debit(trade) - trade.net_credit) * 100.0, 160.0)

        dates = pd.bdate_range("2026-07-06", periods=2)
        history = pd.DataFrame(
            {
                "close": [50.0, 50.0],
                "iv_proxy": [0.45, 0.45],
                "iv_rank": [60.0, 60.0],
                "regime": ["neutral", "neutral"],
            },
            index=dates,
        )
        with (
            patch("trader_platform.research.pcs_sim.pick_structure_entry", return_value=trade),
            patch.object(
                PcsTrade,
                "mark_net_debit",
                return_value={"net_debit": 4.0, "short_delta": 0.0, "dte_remaining": 10},
            ),
        ):
            result = run_pcs_backtest(
                "TEST",
                df=history,
                min_bars=1,
                structure="iron_condor",
                config={"dte_stop": 10},
            )

        self.assertEqual(result.n_trades, 1)
        self.assertEqual(result.trades[0].exit_debit, 2.0)
        self.assertAlmostEqual(result.metrics["total_pnl_per_contract"], -160.0)
        self.assertAlmostEqual(
            -result.metrics["worst_group_pnl_per_contract"],
            result.trades[0].max_loss_per_share * 100.0,
        )


if __name__ == "__main__":
    unittest.main()

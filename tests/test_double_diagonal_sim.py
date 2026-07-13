import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import pandas as pd

import pricing
from trader_platform.evolve_tick import build_population, sim_dna
from trader_platform.research.double_diagonal_sim import (
    pick_double_diagonal_entry,
    run_double_diagonal_backtest,
)
from trader_platform.strategy_dna import dna_from_structure


class DoubleDiagonalSimTest(unittest.TestCase):
    def _bars(self, regime: str = "neutral", periods: int = 100) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": np.linspace(50.0, 51.5, periods),
                "iv_proxy": np.full(periods, 0.45),
                "iv_rank": np.full(periods, 65.0),
                "regime": [regime] * periods,
            },
            index=pd.bdate_range("2025-01-02", periods=periods),
        )

    def test_catalog_entry_is_four_leg_defined_debit_with_protective_back_strikes(self):
        dna = dna_from_structure("double_diagonal_spread", ["TEST"])
        row = self._bars().iloc[0]
        today = cast(pd.Timestamp, self._bars().index[0])

        trade = pick_double_diagonal_entry(row, 50.0, today, dna.sim_config())

        self.assertTrue(dna.uses_double_diagonal_sim())
        self.assertIsNotNone(trade)
        assert trade is not None
        self.assertGreaterEqual(trade.long_put_strike, trade.short_put_strike)
        self.assertLess(trade.short_put_strike, 50.0)
        self.assertLessEqual(trade.long_call_strike, trade.short_call_strike)
        self.assertGreater(trade.short_call_strike, 50.0)
        self.assertLess(trade.long_put_strike, trade.long_call_strike)
        self.assertGreater(trade.entry_debit, 0.0)
        self.assertAlmostEqual(trade.defined_max_loss_usd, trade.entry_debit * 100.0)
        self.assertLessEqual(trade.defined_max_loss_usd, 300.0)

    def test_entry_filters_and_budget_fail_closed(self):
        dna = dna_from_structure("double_diagonal_spread", ["TEST"])
        cfg = dna.sim_config()
        today = cast(pd.Timestamp, self._bars().index[0])
        self.assertIsNone(
            pick_double_diagonal_entry(
                self._bars("bullish").iloc[0], 50.0, today, cfg
            )
        )
        low_iv_rank = self._bars().iloc[0].copy()
        low_iv_rank["iv_rank"] = 5.0
        self.assertIsNone(pick_double_diagonal_entry(low_iv_rank, 50.0, today, cfg))
        invalid_iv = self._bars().iloc[0].copy()
        invalid_iv["iv_proxy"] = np.nan
        self.assertIsNone(pick_double_diagonal_entry(invalid_iv, 50.0, today, cfg))
        self.assertIsNone(
            pick_double_diagonal_entry(
                self._bars().iloc[0],
                50.0,
                today,
                {**cfg, "max_loss_budget_usd": 1.0},
            )
        )
        # The mid entry narrowly fits $300, but both adverse four-leg cost axes
        # cross the capital budget and must remain ineligible.
        self.assertIsNone(
            pick_double_diagonal_entry(
                self._bars().iloc[0],
                50.0,
                today,
                {**cfg, "half_spread_per_leg": 0.01},
            )
        )
        self.assertIsNone(
            pick_double_diagonal_entry(
                self._bars().iloc[0],
                50.0,
                today,
                {**cfg, "slippage_pct": 0.05},
            )
        )

    def test_population_and_evolve_dispatch_are_structure_pure(self):
        population = build_population(
            [{"symbol": "TEST", "strategy_family": "wheel"}],
            structures=["double_diagonal_spread"],
            mutants_per_seed=4,
            seed=7,
        )
        self.assertGreater(len(population), 1)
        self.assertEqual({dna.structure for dna in population}, {"double_diagonal_spread"})
        dna = population[0]
        with TemporaryDirectory() as tmp, patch("data.build", return_value=self._bars()):
            verdict = sim_dna(dna, period="smoke", dump_dir=Path(tmp))
        self.assertTrue(verdict.ok, verdict.reason)
        self.assertGreater(verdict.n_trades, 0)
        self.assertEqual(
            verdict.dna.last_sim["sim_engine"],
            "double_diagonal_sim:double_diagonal_spread",
        )

    def test_fixed_half_spread_counts_four_legs_on_entry_and_exit(self):
        bars = self._bars()
        row = bars.iloc[0]
        today = cast(pd.Timestamp, bars.index[0])
        base = {
            **dna_from_structure("double_diagonal_spread", ["TEST"]).sim_config(),
            "max_loss_budget_usd": 500.0,  # isolate arithmetic, not capital eligibility
        }
        mid = pick_double_diagonal_entry(row, 50.0, today, base)
        costly = pick_double_diagonal_entry(
            row,
            50.0,
            today,
            {**base, "half_spread_per_leg": 0.01},
        )

        self.assertIsNotNone(mid)
        self.assertIsNotNone(costly)
        assert mid is not None and costly is not None
        self.assertAlmostEqual(costly.entry_debit - mid.entry_debit, 0.04, places=8)
        mark_day = today + pd.Timedelta(days=5)
        mid_exit = mid.mark_credit(50.5, 0.45, mark_day)
        costly_exit = costly.mark_credit(
            50.5, 0.45, mark_day, half_spread_per_leg=0.01
        )
        self.assertAlmostEqual(mid_exit - costly_exit, 0.04, places=8)
        self.assertAlmostEqual(
            (mid_exit - mid.entry_debit) - (costly_exit - costly.entry_debit),
            0.08,
            places=8,
        )

    def test_percentage_slip_is_applied_adversely_to_all_four_legs(self):
        bars = self._bars()
        row = bars.iloc[0]
        today = cast(pd.Timestamp, bars.index[0])
        base = {
            **dna_from_structure("double_diagonal_spread", ["TEST"]).sim_config(),
            "max_loss_budget_usd": 500.0,  # isolate arithmetic, not capital eligibility
        }
        mid = pick_double_diagonal_entry(row, 50.0, today, base)
        slipped = pick_double_diagonal_entry(
            row, 50.0, today, {**base, "slippage_pct": 0.05}
        )

        self.assertIsNotNone(mid)
        self.assertIsNotNone(slipped)
        assert mid is not None and slipped is not None
        front_sigma = 0.45 * mid.front_iv_multiplier
        back_sigma = 0.45 * mid.back_iv_multiplier
        gross_entry_marks = sum(
            (
                pricing.price(50.0, mid.short_put_strike, 14 / 365.0, front_sigma, "put"),
                pricing.price(50.0, mid.short_call_strike, 14 / 365.0, front_sigma, "call"),
                pricing.price(50.0, mid.long_put_strike, 60 / 365.0, back_sigma, "put"),
                pricing.price(50.0, mid.long_call_strike, 60 / 365.0, back_sigma, "call"),
            )
        )
        self.assertAlmostEqual(
            slipped.entry_debit - mid.entry_debit,
            0.05 * gross_entry_marks,
            places=8,
        )
        mark_day = today + pd.Timedelta(days=5)
        mid_exit = mid.mark_credit(50.5, 0.45, mark_day)
        slipped_exit = mid.mark_credit(
            50.5, 0.45, mark_day, slippage_pct=0.05
        )
        front_days = (mid.front_expiration - mark_day).days
        back_days = (mid.back_expiration - mark_day).days
        gross_exit_marks = sum(
            (
                pricing.price(
                    50.5, mid.short_put_strike, front_days / 365.0, front_sigma, "put"
                ),
                pricing.price(
                    50.5, mid.short_call_strike, front_days / 365.0, front_sigma, "call"
                ),
                pricing.price(
                    50.5, mid.long_put_strike, back_days / 365.0, back_sigma, "put"
                ),
                pricing.price(
                    50.5, mid.long_call_strike, back_days / 365.0, back_sigma, "call"
                ),
            )
        )
        self.assertAlmostEqual(
            mid_exit - slipped_exit,
            0.05 * gross_exit_marks,
            places=8,
        )

    def test_front_expiry_uses_protective_intrinsic_floor_without_clipping_exit_cost(self):
        bars = self._bars()
        today = cast(pd.Timestamp, bars.index[0])
        cfg = {
            **dna_from_structure("double_diagonal_spread", ["TEST"]).sim_config(),
            "max_loss_budget_usd": 500.0,
        }
        trade = pick_double_diagonal_entry(bars.iloc[0], 50.0, today, cfg)

        self.assertIsNotNone(trade)
        assert trade is not None
        # At front expiry the same-strike back legs can protect at intrinsic.
        # The active long put and two short legs incur $0.01 adverse marks;
        # the worthless long call is abandoned rather than sold below zero.
        exit_value = trade.mark_credit(
            21.0,
            0.30,
            trade.front_expiration,
            half_spread_per_leg=0.01,
        )
        self.assertAlmostEqual(exit_value, -0.03, places=8)

    def test_capital_includes_realized_loss_beyond_structural_debit(self):
        today = pd.Timestamp("2025-01-02")
        bars = pd.DataFrame(
            {
                "close": [50.0, 21.0],
                "iv_proxy": [0.45, 0.30],
                "iv_rank": [65.0, 65.0],
                "regime": ["neutral", "neutral"],
            },
            index=[today, today + pd.Timedelta(days=14)],
        )
        cfg = {
            **dna_from_structure("double_diagonal_spread", ["TEST"]).sim_config(),
            "max_loss_budget_usd": 500.0,
            "half_spread_per_leg": 0.01,
        }

        result = run_double_diagonal_backtest(
            "TEST", period="boundary", df=bars, config=cfg, min_bars=2
        )

        self.assertEqual(result.n_trades, 1)
        self.assertGreater(
            result.capital["observed_path_worst_loss_usd"],
            result.capital["structural_max_loss_usd"],
        )
        self.assertEqual(
            result.capital["max_loss_usd"],
            result.capital["observed_path_worst_loss_usd"],
        )

    def test_backtest_defers_reentry_and_reports_honest_one_lot_capital(self):
        dna = dna_from_structure("double_diagonal_spread", ["TEST"])
        result = run_double_diagonal_backtest(
            "TEST",
            period="smoke",
            df=self._bars(periods=100),
            config={**dna.sim_config(), "dte_stop": 100},
        )

        self.assertTrue(result.ok, result.reason)
        self.assertGreater(len(result.trades), 2)
        for previous, following in zip(result.trades, result.trades[1:]):
            self.assertNotEqual(previous.exit_date, following.entry_date)
        recomputed = sum(
            ((trade.exit_credit or 0.0) - trade.entry_debit) * 100.0
            for trade in result.trades
        )
        self.assertAlmostEqual(
            recomputed,
            result.metrics["total_pnl_per_contract"],
            places=9,
        )
        self.assertIn("worst_realized_loss_usd", result.metrics)
        self.assertEqual(result.capital["structure"], "double_diagonal_spread")
        self.assertGreaterEqual(
            result.capital["max_loss_usd"],
            result.metrics["worst_realized_loss_usd"],
        )
        self.assertLessEqual(result.capital["capital_fit_usd"], 300.0)
        self.assertLessEqual(result.capital["max_loss_usd"], 300.0)
        self.assertEqual(result.capital["max_lots"], 1)
        self.assertGreater(result.capital["theoretical_max_lots"], 1)
        self.assertEqual(
            result.capital["max_lots_policy"],
            "one_lot_conservative_operating_posture",
        )


if __name__ == "__main__":
    unittest.main()

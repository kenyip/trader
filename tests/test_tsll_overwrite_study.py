import unittest

import numpy as np
import pandas as pd

from scripts.tsll_overwrite_study import (
    SHARES,
    build_forward_path,
    decay_constant,
    listed_target_expiration,
    log_linear_monthly_decay,
    max_drawdown,
    ols_beta,
    point_to_point_monthly,
    simulate_hold,
    simulate_overwrite,
    simulate_rotate,
)


class TsllOverwriteStudyTest(unittest.TestCase):
    def test_decay_constant_is_tsll_over_tsla_squared(self):
        self.assertAlmostEqual(decay_constant(10.59, 380.45), 10.59 / (380.45 ** 2))

    def test_ols_beta_recovers_two_times_plus_noise(self):
        rng = np.random.default_rng(0)
        x = pd.Series(rng.normal(0, 0.02, 200))
        y = 2.0 * x + rng.normal(0, 0.001, 200)
        fit = ols_beta(y, x)
        self.assertAlmostEqual(fit["beta"], 2.0, places=1)
        self.assertEqual(fit["n"], 200)
        self.assertGreater(fit["r2"], 0.95)

    def test_log_linear_monthly_decay_recovers_known_rate(self):
        index = pd.bdate_range("2026-01-02", periods=160)
        monthly = -0.034
        k0 = 9.23e-5
        values = [
            k0 * ((1.0 + monthly) ** ((dt - index[0]).days / 30.437))
            for dt in index
        ]
        fit = log_linear_monthly_decay(pd.Series(values, index=index))
        self.assertAlmostEqual(fit["monthly_rate"], monthly, places=3)
        self.assertEqual(int(fit["n"]), 160)

    def test_point_to_point_monthly_matches_compound(self):
        rate = point_to_point_monthly(9.23e-5, 7.32e-5, pd.Timestamp("2026-01-30"), pd.Timestamp("2026-09-03"))
        months = (pd.Timestamp("2026-09-03") - pd.Timestamp("2026-01-30")).days / 30.437
        self.assertAlmostEqual((1.0 + rate) ** months, 7.32e-5 / 9.23e-5, places=12)

    def test_hold_pnl_is_shares_times_price_change(self):
        index = pd.bdate_range("2026-01-02", periods=10)
        tsll = pd.Series(np.linspace(12.0, 10.0, 10), index=index)
        raw = simulate_hold(tsll, shares=7000)
        self.assertAlmostEqual(raw["pnl"], 7000 * (10.0 - 12.0))
        self.assertEqual(raw["assignments"], 0)
        self.assertEqual(raw["premium"], 0.0)

    def test_overwrite_assignment_sells_shares_at_strike_without_reentry(self):
        index = pd.bdate_range("2026-01-02", periods=50)
        tsll = pd.Series(10.0, index=index)
        tsll.iloc[8:] = 20.0
        sigma = pd.Series(0.80, index=index)
        raw = simulate_overwrite(
            tsll, shares0=7000, contracts=70, target_delta=0.40, sigma=sigma, reentry=False
        )
        self.assertGreaterEqual(raw["assignments"], 1)
        self.assertLess(raw["shares_end"], 7000)
        self.assertGreater(raw["cash_end"], 0.0)
        self.assertGreater(raw["premium"], 0.0)

    def test_overwrite_reentry_buys_the_block_back(self):
        index = pd.bdate_range("2026-01-02", periods=80)
        tsll = pd.Series(10.0, index=index)
        tsll.iloc[8:] = 18.0
        tsll.iloc[-15:] = 11.0
        sigma = pd.Series(0.80, index=index)
        raw = simulate_overwrite(
            tsll, shares0=7000, contracts=70, target_delta=0.40, sigma=sigma, reentry=True
        )
        self.assertGreaterEqual(raw["assignments"], 1)
        self.assertEqual(raw["shares_end"], 7000)

    def test_partial_overwrite_cannot_call_away_the_full_block(self):
        index = pd.bdate_range("2026-01-02", periods=50)
        tsll = pd.Series(10.0, index=index)
        tsll.iloc[8:] = 25.0
        sigma = pd.Series(0.80, index=index)
        raw = simulate_overwrite(
            tsll, shares0=7000, contracts=20, target_delta=0.40, sigma=sigma, reentry=False
        )
        self.assertGreaterEqual(raw["assignments"], 1)
        self.assertGreaterEqual(raw["shares_end"], 5000)

    def test_rotate_sells_shares_on_bar_zero(self):
        index = pd.bdate_range("2026-01-02", periods=40)
        tsla = pd.Series(380.0, index=index)
        tsll = pd.Series(10.59, index=index)
        sigma = pd.Series(0.48, index=index)
        raw = simulate_rotate(tsla, tsll, beta=1.99, sigma_tsla=sigma)
        self.assertEqual(raw["shares_end"], 0.0)
        self.assertLess(raw["premium"], 0.0)
        self.assertAlmostEqual(raw["start_wealth"], 7000 * 10.59)

    def test_forward_path_obeys_k_times_tsla_squared(self):
        start = pd.Timestamp("2026-09-03")
        path = build_forward_path(20, 380.45, 7.32e-5, 0.10, -0.034, start)
        rebuilt = path["k"] * path["TSLA"] * path["TSLA"]
        np.testing.assert_allclose(path["TSLL"].to_numpy(), rebuilt.to_numpy(), rtol=1e-12)
        self.assertAlmostEqual(path["TSLA"].iloc[-1] / path["TSLA"].iloc[0], 1.10, places=8)

    def test_k_on_row_t_does_not_use_future_prices(self):
        index = pd.bdate_range("2026-01-02", periods=5)
        tsla = pd.Series([300.0, 310.0, 320.0, 330.0, 340.0], index=index)
        tsll = pd.Series([8.0, 8.2, 8.4, 8.6, 8.8], index=index)
        k = decay_constant(tsll, tsla)
        shocked = tsll.copy()
        shocked.iloc[-1] = 20.0
        k_shocked = decay_constant(shocked, tsla)
        self.assertAlmostEqual(k.iloc[0], k_shocked.iloc[0])
        self.assertNotAlmostEqual(k.iloc[-1], k_shocked.iloc[-1])

    def test_listed_expiration_is_friday_inside_30_45_dte_band(self):
        entry = pd.Timestamp("2026-09-03")
        expiry = listed_target_expiration(entry, 38)
        self.assertEqual(expiry.weekday(), 4)
        dte = (expiry - entry).days
        self.assertGreaterEqual(dte, 30)
        self.assertLessEqual(dte, 45)

    def test_max_drawdown_is_peak_to_trough_dollars(self):
        self.assertAlmostEqual(max_drawdown(np.array([100.0, 120.0, 90.0, 95.0])), 30.0)

    def test_hold_scales_linearly_with_share_count(self):
        index = pd.bdate_range("2026-01-02", periods=8)
        tsll = pd.Series([12.0, 11.5, 11.0, 10.5, 10.0, 10.2, 10.1, 9.8], index=index)
        one = simulate_hold(tsll, shares=1000)
        seven = simulate_hold(tsll, shares=7000)
        self.assertAlmostEqual(seven["pnl"], 7.0 * one["pnl"])
        self.assertAlmostEqual(seven["max_dd"], 7.0 * one["max_dd"])


if __name__ == "__main__":
    unittest.main()

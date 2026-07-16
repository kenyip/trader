import json
import unittest

import numpy as np
import pandas as pd

from scripts.downside_semivariance_etf_barrier_train_lab import (
    _dominant_failure_mechanism,
    build_rank_blueprints,
    evaluate_train_partition,
    run_lab_from_panel,
)


class DownsideSemivarianceEtfBarrierTrainLabTest(unittest.TestCase):
    @staticmethod
    def _ranking_panel(periods: int = 700) -> pd.DataFrame:
        index = pd.bdate_range("2018-01-02", periods=periods)
        symbols = ("SPY", "QQQ", "IWM", "XLF", "XLE", "XLK", "XLI", "XLV")
        data = {}
        for symbol_index, symbol in enumerate(symbols):
            returns = np.full(periods, 0.0008 + symbol_index * 0.00001)
            returns[::17] -= 0.002 + symbol_index * 0.001
            returns[8::17] += 0.001 * symbol_index
            data[symbol] = 100.0 * np.exp(np.cumsum(returns))
        return pd.DataFrame(data, index=index)

    def test_blueprints_rank_completed_downside_semivariance_and_are_global_nonoverlap(self):
        panel = self._ranking_panel()
        blueprints = build_rank_blueprints(
            panel,
            symbols=list(panel.columns),
            semivariance_lookback_sessions=20,
            trend_lookback_sessions=40,
            momentum_lookback_sessions=20,
            forward_sessions=5,
        )

        self.assertGreater(len(blueprints), 20)
        for previous, following in zip(blueprints, blueprints[1:]):
            self.assertLess(previous["rank_date"], previous["entry_date"])
            self.assertLess(previous["entry_date"], previous["exit_date"])
            self.assertLess(previous["exit_date"], following["entry_date"])
            self.assertNotEqual(
                previous["low_semivariance_symbol"], previous["high_semivariance_symbol"]
            )

        first = blueprints[0]
        changed = panel.copy()
        changed.loc[first["entry_date"] : first["exit_date"], first["low_semivariance_symbol"]] *= 0.50
        rebuilt = build_rank_blueprints(
            changed,
            symbols=list(panel.columns),
            semivariance_lookback_sessions=20,
            trend_lookback_sessions=40,
            momentum_lookback_sessions=20,
            forward_sessions=5,
        )
        for key in (
            "rank_date",
            "entry_date",
            "exit_date",
            "low_semivariance_symbol",
            "high_semivariance_symbol",
            "low_hv_symbol",
            "high_hv_symbol",
        ):
            self.assertEqual(first[key], rebuilt[0][key])

    @staticmethod
    def _manual_partition(episodes: int = 24):
        index = pd.bdate_range("2020-01-02", periods=episodes * 14 + 5)
        symbols = ("SPY", "QQQ", "IWM", "XLF", "XLE", "XLK", "XLI", "XLV")
        panel = pd.DataFrame(100.0, index=index, columns=symbols)
        blueprints = []
        candidates = symbols[:6]
        for episode_index in range(episodes):
            base = 1 + episode_index * 14
            signal, entry, exit_ = index[base], index[base + 1], index[base + 11]
            low = candidates[episode_index % len(candidates)]
            high = candidates[(episode_index + 1) % len(candidates)]
            hv_low = candidates[(episode_index + 2) % len(candidates)]
            hv_high = candidates[(episode_index + 3) % len(candidates)]
            panel.loc[entry:exit_, low] = 100.0
            panel.loc[index[base + 5], low] = 98.0
            panel.loc[exit_, low] = 102.0
            panel.loc[entry:exit_, high] = 100.0
            panel.loc[index[base + 5], high] = 90.0
            panel.loc[exit_, high] = 97.0
            panel.loc[entry:exit_, hv_low] = 100.0
            panel.loc[index[base + 5], hv_low] = 96.0
            panel.loc[entry:exit_, hv_high] = 100.0
            panel.loc[index[base + 5], hv_high] = 96.0
            blueprints.append(
                {
                    "rank_date": signal,
                    "feature_max_date": signal,
                    "entry_date": entry,
                    "exit_date": exit_,
                    "low_semivariance_symbol": low,
                    "high_semivariance_symbol": high,
                    "low_semivariance_value": 0.01,
                    "high_semivariance_value": 0.04,
                    "low_hv_symbol": hv_low,
                    "high_hv_symbol": hv_high,
                    "low_hv_value": 0.10,
                    "high_hv_value": 0.30,
                    "spy_trend_distance": 0.10,
                    "spy_momentum_return": 0.08,
                }
            )
        return panel, blueprints

    def test_train_gate_passes_for_absolute_specific_date_blocked_tail_edge(self):
        panel, blueprints = self._manual_partition()
        result = evaluate_train_partition(
            panel,
            blueprints,
            min_rank_dates=20,
            min_symbols=6,
            bootstrap_samples=500,
        )

        self.assertTrue(result["gate_pass"], result["gate_checks"])
        self.assertEqual(result["low_semivariance_breach_rate"], 0.0)
        self.assertEqual(result["high_semivariance_breach_rate"], 1.0)
        self.assertGreater(result["semivariance_breach_rate_edge"], 0.05)
        self.assertGreater(result["date_block_bootstrap_edge_lb90"], 0.0)
        self.assertGreater(
            result["low_semivariance_worst_decile_mean_min_return"],
            result["high_semivariance_worst_decile_mean_min_return"],
        )
        self.assertGreater(
            result["semivariance_breach_rate_edge"], result["plain_hv_breach_rate_edge"]
        )
        self.assertEqual(result["integrity_violations"], [])

    def test_payload_seals_holdout_and_carries_complete_one_lot_stack(self):
        panel = self._ranking_panel(periods=900)
        payload = run_lab_from_panel(
            panel,
            symbols=list(panel.columns),
            provenance={"fixture": True},
            train_fraction=0.60,
            semivariance_lookback_sessions=20,
            trend_lookback_sessions=40,
            momentum_lookback_sessions=20,
            forward_sessions=5,
            min_rank_dates=10,
            min_symbols=2,
            bootstrap_samples=500,
        )

        self.assertIn(payload["strategy_outcome"], {"STRATEGY_ADVANCED", "FAMILY_CLOSED"})
        self.assertFalse(payload["funnel_claim_f2"])
        self.assertFalse(payload["l1_claim"])
        self.assertFalse(payload["untouched_holdout"]["outcome_metrics_read"])
        self.assertNotIn("rank_dates", payload["untouched_holdout"])
        self.assertTrue(payload["untouched_holdout"]["identity_sha256"])
        self.assertLess(
            payload["data_window"]["train_last_rank_date"],
            payload["untouched_holdout"]["first_rank_date"],
        )
        self.assertEqual(payload["option_stage"]["pricing_calls"], 0)
        self.assertEqual(payload["structure"], "conditional_put_credit_spread_not_yet_priced")
        self.assertEqual(payload["option_entry_filter"]["dte_range"], [18, 24])
        self.assertEqual(payload["option_entry_filter"]["short_put_delta_range"], [0.18, 0.25])
        self.assertEqual(payload["capital_fit_usd"], 200.0)
        self.assertEqual(payload["one_lot_max_loss_usd"], 200.0)
        self.assertEqual(payload["max_lots"], 1)
        self.assertEqual(payload["forecast_type"], "non_collapse")
        self.assertIn("positive theta", payload["greek_exposures"]["intended"])
        self.assertTrue(payload["stand_aside_rule"])
        self.assertIn("date-block", payload["methodology_boundaries"]["bootstrap_dependence"])
        self.assertFalse(payload["methodology_boundaries"]["barrier_is_intraday_or_option_mark"])
        self.assertTrue(payload["population_validity"]["population_pure"])
        self.assertFalse(payload["population_validity"]["point_in_time_composition"])
        json.dumps(payload, allow_nan=False)

    def test_positive_terminal_mean_cannot_rescue_failed_absolute_tail_gate(self):
        panel, blueprints = self._manual_partition()
        for blueprint in blueprints:
            low = blueprint["low_semivariance_symbol"]
            path_dates = panel.loc[blueprint["entry_date"] : blueprint["exit_date"]].index
            panel.loc[path_dates, low] = 100.0
            panel.loc[path_dates[len(path_dates) // 2], low] = 90.0
            panel.loc[path_dates[-1], low] = 112.0
        result = evaluate_train_partition(
            panel,
            blueprints,
            min_rank_dates=20,
            min_symbols=6,
            bootstrap_samples=500,
        )
        self.assertGreater(result["low_semivariance_mean_terminal_return_after_cost"], 0.0)
        self.assertFalse(result["gate_checks"]["low_breach_rate_at_most_limit"])
        self.assertFalse(result["gate_pass"])

    def test_plain_hv_equivalence_fails_mechanism_specificity(self):
        panel, blueprints = self._manual_partition()
        for blueprint in blueprints:
            blueprint["low_hv_symbol"] = blueprint["low_semivariance_symbol"]
            blueprint["high_hv_symbol"] = blueprint["high_semivariance_symbol"]
        result = evaluate_train_partition(
            panel,
            blueprints,
            min_rank_dates=20,
            min_symbols=6,
            bootstrap_samples=500,
        )
        self.assertGreater(result["semivariance_breach_rate_edge"], 0.05)
        self.assertEqual(
            result["semivariance_breach_rate_edge"], result["plain_hv_breach_rate_edge"]
        )
        self.assertFalse(result["gate_checks"]["semivariance_edge_exceeds_plain_hv"])
        self.assertFalse(result["gate_pass"])

        dominant_failure = _dominant_failure_mechanism(
            [name for name, passed in result["gate_checks"].items() if not passed]
        )
        self.assertEqual(
            dominant_failure,
            "mechanism non-specificity only: the downside-semivariance breach edge did not exceed "
            "the same-date plain-HV breach edge; every other frozen train gate passed",
        )
        self.assertNotIn("absolute", dominant_failure)

    def test_overlapping_rank_dates_fail_closed(self):
        panel, blueprints = self._manual_partition()
        blueprints[1]["entry_date"] = blueprints[0]["exit_date"]
        result = evaluate_train_partition(
            panel,
            blueprints,
            min_rank_dates=20,
            min_symbols=6,
            bootstrap_samples=500,
        )
        self.assertTrue(any(value.startswith("overlap:1") for value in result["integrity_violations"]))
        self.assertFalse(result["gate_checks"]["zero_integrity_violations"])
        self.assertFalse(result["gate_pass"])

    def test_fixed_population_rejects_missing_etf(self):
        panel = self._ranking_panel().drop(columns=["XLV"])
        with self.assertRaisesRegex(ValueError, "frozen ordered ETF panel"):
            build_rank_blueprints(
                panel,
                symbols=list(panel.columns),
                semivariance_lookback_sessions=20,
                trend_lookback_sessions=40,
                momentum_lookback_sessions=20,
                forward_sessions=5,
            )


if __name__ == "__main__":
    unittest.main()

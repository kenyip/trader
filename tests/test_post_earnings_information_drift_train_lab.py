import json
import subprocess
import sys
import unittest

import numpy as np
import pandas as pd

from scripts.post_earnings_information_drift_train_lab import (
    build_event_matched_blueprints,
    evaluate_train_partition,
    first_completed_session_after_announcement,
    run_lab_from_panel,
)


class PostEarningsInformationDriftTrainLabTest(unittest.TestCase):
    def test_announcement_timing_maps_to_first_completed_session(self):
        sessions = pd.bdate_range("2024-01-02", periods=10)
        self.assertEqual(
            first_completed_session_after_announcement(
                pd.Timestamp("2024-01-03 07:00:00", tz="America/New_York"), sessions
            ),
            pd.Timestamp("2024-01-03"),
        )
        self.assertEqual(
            first_completed_session_after_announcement(
                pd.Timestamp("2024-01-05 16:00:00", tz="America/New_York"), sessions
            ),
            pd.Timestamp("2024-01-08"),
        )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            first_completed_session_after_announcement(
                pd.Timestamp("2024-01-03 12:00:00", tz="America/New_York"), sessions
            )
        with self.assertRaisesRegex(ValueError, "timezone"):
            first_completed_session_after_announcement(pd.Timestamp("2024-01-03 07:00:00"), sessions)

    def test_ambiguous_event_is_stand_aside_not_global_failure(self):
        panel, events = self._selection_panel()
        baseline = build_event_matched_blueprints(
            panel,
            events,
            reaction_abs_min=0.03,
            max_abs_reaction_gap=0.04,
            max_ret20_gap=0.50,
            max_hv20_gap=0.50,
            max_match_distance_sessions=504,
        )
        ambiguous = pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "announcement_at": pd.Timestamp(
                        "2018-06-01 12:00:00", tz="America/New_York"
                    ),
                }
            ]
        )
        rebuilt = build_event_matched_blueprints(
            panel,
            pd.concat([events, ambiguous], ignore_index=True),
            reaction_abs_min=0.03,
            max_abs_reaction_gap=0.04,
            max_ret20_gap=0.50,
            max_hv20_gap=0.50,
            max_match_distance_sessions=504,
        )
        self.assertEqual(baseline, rebuilt)

    @staticmethod
    def _selection_panel(periods: int = 900):
        index = pd.bdate_range("2018-01-02", periods=periods)
        symbols = ("AAPL", "AMD", "META", "NVDA", "TSLA", "GOOGL")
        rng = np.random.default_rng(20260715)
        panel = {}
        events = []
        for symbol_index, symbol in enumerate(symbols):
            returns = rng.normal(0.0002, 0.009, periods)
            for event_number, position in enumerate((180, 310, 440, 570, 700, 830)):
                signal_position = position + symbol_index
                sign = 1.0 if (event_number + symbol_index) % 2 == 0 else -1.0
                returns[signal_position] = sign * 0.04
                returns[signal_position + 1 : signal_position + 6] = sign * 0.004
                announcement_date = index[signal_position - 1]
                events.append(
                    {
                        "symbol": symbol,
                        "announcement_at": pd.Timestamp(announcement_date).tz_localize(
                            "America/New_York"
                        )
                        + pd.Timedelta(hours=16),
                    }
                )
            panel[symbol] = 100.0 * np.exp(np.cumsum(returns))
        return pd.DataFrame(panel, index=index), pd.DataFrame(events)

    def test_blueprints_are_prior_only_non_event_controls_and_outcome_invariant(self):
        panel, events = self._selection_panel()
        blueprints = build_event_matched_blueprints(
            panel,
            events,
            reaction_abs_min=0.03,
            max_abs_reaction_gap=0.04,
            max_ret20_gap=0.50,
            max_hv20_gap=0.50,
            max_match_distance_sessions=504,
        )
        self.assertGreaterEqual(len(blueprints), 12)
        first = blueprints[0]
        self.assertLess(first["control_exit_date"], first["event_signal_date"])
        self.assertLess(first["event_signal_date"], first["event_exit_date"])
        self.assertNotIn(first["control_signal_date"], set(first["excluded_event_signal_dates"]))

        shocked = panel.copy()
        shocked.loc[first["event_exit_date"], first["symbol"]] *= 1.50
        rebuilt = build_event_matched_blueprints(
            shocked,
            events,
            reaction_abs_min=0.03,
            max_abs_reaction_gap=0.04,
            max_ret20_gap=0.50,
            max_hv20_gap=0.50,
            max_match_distance_sessions=504,
        )
        for key in (
            "symbol",
            "announcement_at",
            "event_signal_date",
            "event_exit_date",
            "control_signal_date",
            "control_exit_date",
        ):
            self.assertEqual(first[key], rebuilt[0][key])

    @staticmethod
    def _manual_partition(excesses, *, symbols=("AAPL", "AMD", "META", "NVDA", "TSLA", "GOOGL")):
        index = pd.bdate_range("2010-01-04", periods=1600)
        panel = pd.DataFrame({symbol: 100.0 for symbol in symbols}, index=index)
        rows = []
        for pair_index, excess in enumerate(excesses):
            symbol = symbols[pair_index % len(symbols)]
            base = 10 + pair_index * 14
            control_signal = index[base]
            control_exit = index[base + 5]
            event_signal = index[base + 7]
            event_exit = index[base + 12]
            sign = 1.0 if pair_index % 2 == 0 else -1.0
            control_signed = -0.005
            event_signed = control_signed + excess
            panel.loc[control_signal, symbol] = 100.0
            panel.loc[control_exit, symbol] = 100.0 * (1.0 + sign * control_signed)
            panel.loc[event_signal, symbol] = 100.0
            panel.loc[event_exit, symbol] = 100.0 * (1.0 + sign * event_signed)
            rows.append(
                {
                    "symbol": symbol,
                    "announcement_at": "2010-01-01T21:00:00+00:00",
                    "event_signal_date": event_signal,
                    "event_exit_date": event_exit,
                    "event_reaction": sign * 0.04,
                    "event_ret20": 0.01,
                    "event_hv20": 0.20,
                    "control_signal_date": control_signal,
                    "control_exit_date": control_exit,
                    "control_reaction": sign * 0.035,
                    "control_ret20": 0.01,
                    "control_hv20": 0.20,
                    "calendar_distance_sessions": 7,
                    "abs_reaction_match_gap": 0.005,
                    "ret20_match_gap": 0.0,
                    "hv20_match_gap": 0.0,
                    "excluded_event_signal_dates": [event_signal],
                }
            )
        return panel, rows

    def test_train_gate_passes_only_for_dense_positive_paired_drift(self):
        panel, rows = self._manual_partition([0.03] * 48)
        result = evaluate_train_partition(
            panel,
            rows,
            min_pairs=40,
            min_symbols=6,
            bootstrap_samples=500,
        )
        self.assertTrue(result["gate_pass"], result["gate_checks"])
        self.assertGreater(result["paired_signed_excess_mean"], 0.0)
        self.assertGreater(result["paired_signed_excess_bootstrap_lb90"], 0.0)
        self.assertGreaterEqual(result["continuation_hit_rate_edge"], 0.05)
        self.assertEqual(result["integrity_violations"], [])

    def test_positive_point_mean_with_nonpositive_bound_fails(self):
        panel, rows = self._manual_partition([0.04, -0.035] * 24)
        result = evaluate_train_partition(
            panel,
            rows,
            min_pairs=40,
            min_symbols=6,
            bootstrap_samples=2000,
        )
        self.assertGreater(result["paired_signed_excess_mean"], 0.0)
        self.assertLessEqual(result["paired_signed_excess_bootstrap_lb90"], 0.0)
        self.assertFalse(result["gate_pass"])

    def test_match_geometry_and_extreme_pair_diagnostics_are_serialized(self):
        panel, rows = self._manual_partition([0.12, -0.11] + [0.03] * 46)
        result = evaluate_train_partition(
            panel,
            rows,
            min_pairs=40,
            min_symbols=6,
            bootstrap_samples=500,
        )
        first = result["pairs"][0]
        for key in (
            "calendar_distance_sessions",
            "abs_reaction_match_gap",
            "ret20_match_gap",
            "hv20_match_gap",
        ):
            self.assertIn(key, first)
        diagnostics = result["match_diagnostics"]
        self.assertTrue(diagnostics["diagnostic_only_not_a_predeclared_gate"])
        self.assertEqual(diagnostics["calendar_distance_sessions_max"], 7)
        self.assertEqual(diagnostics["calendar_distance_sessions_median"], 7.0)
        self.assertEqual(diagnostics["paired_signed_excess_extreme_abs_count"], 2)
        self.assertEqual(diagnostics["paired_signed_excess_extreme_abs_threshold"], 0.10)

    def test_zero_control_support_fails_before_bootstrap_with_strict_nulls(self):
        panel, events = self._selection_panel()
        payload = run_lab_from_panel(
            panel,
            events,
            symbols=list(panel.columns),
            provenance={"fixture": True},
            reaction_abs_min=0.99,
            bootstrap_samples=500,
        )
        self.assertEqual(payload["strategy_outcome"], "FAMILY_CLOSED")
        self.assertEqual(payload["train"]["n_pairs"], 0)
        self.assertIsNone(payload["train"]["paired_signed_excess_mean"])
        self.assertIsNone(payload["train"]["paired_signed_excess_bootstrap_lb90"])
        self.assertEqual(
            payload["train"]["match_diagnostics"][
                "paired_signed_excess_extreme_abs_count"
            ],
            0,
        )
        self.assertFalse(payload["train"]["gate_pass"])
        json.dumps(payload, allow_nan=False)

    def test_payload_reserves_outcome_unread_holdout_and_carries_stack(self):
        panel, events = self._selection_panel()
        payload = run_lab_from_panel(
            panel,
            events,
            symbols=list(panel.columns),
            provenance={"fixture": True},
            reaction_abs_min=0.03,
            max_abs_reaction_gap=0.04,
            max_ret20_gap=0.50,
            max_hv20_gap=0.50,
            max_match_distance_sessions=504,
            min_train_pairs=1,
            min_train_symbols=1,
            bootstrap_samples=500,
        )
        self.assertIn(payload["strategy_outcome"], {"STRATEGY_ADVANCED", "FAMILY_CLOSED"})
        self.assertFalse(payload["funnel_claim_f2"])
        self.assertFalse(payload["l1_claim"])
        self.assertFalse(payload["untouched_holdout"]["outcome_metrics_read"])
        self.assertNotIn("pairs", payload["untouched_holdout"])
        self.assertEqual(payload["option_stage"]["pricing_calls"], 0)
        self.assertEqual(payload["capital_fit_usd"], 200.0)
        self.assertEqual(payload["one_lot_max_loss_usd"], 200.0)
        self.assertEqual(payload["max_lots"], 1)
        self.assertEqual(payload["forecast_type"], "signed_direction_continuation")
        self.assertIn("call debit", payload["option_structure"])
        self.assertIn("put debit", payload["option_structure"])
        self.assertTrue(payload["stand_aside_rule"])
        self.assertIn("underlying-only", payload["claim_scope"])
        self.assertIn("retrospectively downloaded", payload["claim_scope"])
        self.assertTrue(
            payload["population_validity"][
                "earnings_timestamp_source_is_current_retrospective_download"
            ]
        )
        json.dumps(payload, allow_nan=False)

    def test_nonfinite_panel_fails_closed(self):
        panel, events = self._selection_panel()
        panel.iloc[200, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            build_event_matched_blueprints(panel, events)

    def test_cli_help_exposes_frozen_inputs(self):
        completed = subprocess.run(
            [sys.executable, "scripts/post_earnings_information_drift_train_lab.py", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for option in ("--symbols", "--start", "--end", "--out"):
            self.assertIn(option, completed.stdout)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from typing import cast

import pandas as pd

from scripts.yield_curve_regional_bank_train_lab import (
    build_feature_panel,
    evaluate_train,
    freeze_events,
    frozen_geometry,
    holdout_identity_payload,
    load_treasury_year,
    parse_treasury_csv,
    partition_events,
    planning_risk_boundaries,
)


class YieldCurveRegionalBankTrainLabTest(unittest.TestCase):
    @staticmethod
    def _outcome_panel(event_returns: list[float]) -> tuple[pd.DataFrame, list[dict]]:
        index = pd.bdate_range("2010-01-04", periods=500)
        panel = pd.DataFrame({"kre": 100.0, "xlf": 100.0}, index=index)
        events = []
        for episode, event_return in enumerate(event_returns):
            signal_pos = 120 + episode * 20
            entry_pos = signal_pos + 1
            exit_pos = entry_pos + 10
            panel.iloc[entry_pos, panel.columns.get_loc("kre")] = 100.0
            panel.iloc[exit_pos, panel.columns.get_loc("kre")] = 100.0 * (1.0 + event_return)
            panel.iloc[entry_pos, panel.columns.get_loc("xlf")] = 100.0
            panel.iloc[exit_pos, panel.columns.get_loc("xlf")] = 100.0
            events.append(
                {
                    "signal_pos": signal_pos,
                    "signal_date": index[signal_pos],
                    "feature_max_date": index[signal_pos],
                    "entry_pos": entry_pos,
                    "entry_date": index[entry_pos],
                    "exit_pos": exit_pos,
                    "exit_date": index[exit_pos],
                    "spread_change20": 0.25,
                    "dgs2_change20": -0.15,
                }
            )
        return panel, events

    def test_treasury_parser_uses_direct_two_and_ten_year_fields_in_date_order(self):
        payload = (
            'Date,"2 Yr","10 Yr"\n'
            '01/03/2020,1.52,1.80\n'
            '01/02/2020,1.55,1.88\n'
        ).encode()
        frame = parse_treasury_csv(payload)
        self.assertEqual(list(frame.index), list(pd.to_datetime(["2020-01-02", "2020-01-03"])))
        self.assertEqual(frame.loc[pd.Timestamp("2020-01-02"), "dgs2"], 1.55)
        self.assertEqual(frame.loc[pd.Timestamp("2020-01-03"), "dgs10"], 1.80)
        self.assertEqual(frame.loc[pd.Timestamp("2020-01-03"), "spread_2s10s"], 0.28)

    def test_treasury_parser_drops_missing_direct_curve_date_without_forward_fill(self):
        payload = (
            'Date,"2 Yr","10 Yr"\n'
            '01/02/2020,1.55,1.88\n'
            '01/03/2020,,\n'
            '01/06/2020,1.58,1.90\n'
        ).encode()
        frame = parse_treasury_csv(payload)
        self.assertEqual(list(frame.index), list(pd.to_datetime(["2020-01-02", "2020-01-06"])))
        self.assertNotIn(pd.Timestamp("2020-01-03"), frame.index)

    def test_treasury_parser_rejects_duplicate_date_even_when_one_row_is_missing(self):
        payload = (
            'Date,"2 Yr","10 Yr"\n'
            '01/02/2020,1.55,1.88\n'
            '01/02/2020,,\n'
        ).encode()
        with self.assertRaisesRegex(ValueError, "duplicate dates"):
            parse_treasury_csv(payload)

    def test_treasury_loader_parses_the_persisted_bytes_not_response_memory(self):
        response_payload = b'Date,"2 Yr","10 Yr"\n01/02/2020,1.55,1.88\n'
        persisted_payload = b'Date,"2 Yr","10 Yr"\n01/02/2020,2.00,3.00\n'

        def requester(_url: str) -> bytes:
            return response_payload

        def transforming_persist(path: Path, _payload: bytes) -> None:
            path.write_bytes(persisted_payload)

        with tempfile.TemporaryDirectory() as temporary:
            frame, provenance = load_treasury_year(
                2020,
                cache_dir=Path(temporary),
                requester=requester,
                persister=transforming_persist,
            )
        self.assertEqual(frame.iloc[0]["dgs2"], 2.0)
        self.assertEqual(frame.iloc[0]["dgs10"], 3.0)
        self.assertEqual(provenance["rows"], 1)

    def test_signal_uses_completed_curve_and_trends_then_enters_next_close(self):
        index = pd.bdate_range("2018-01-02", periods=180)
        curve = pd.DataFrame(
            {"dgs2": 2.0, "dgs10": 3.0},
            index=index,
        )
        curve.loc[index[120]:, "dgs2"] = 1.70
        curve["spread_2s10s"] = curve["dgs10"] - curve["dgs2"]
        closes = {
            "KRE": pd.Series(range(100, 280), index=index, dtype=float),
            "XLF": pd.Series(range(80, 260), index=index, dtype=float),
            "SPY": pd.Series(range(200, 380), index=index, dtype=float),
        }
        panel = build_feature_panel(curve, closes)
        events = freeze_events(panel, forward_sessions=10)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["signal_date"], index[120])
        self.assertEqual(event["feature_max_date"], index[120])
        self.assertEqual(event["entry_date"], index[121])
        self.assertEqual(event["exit_date"], index[131])

        changed = closes.copy()
        changed["KRE"] = closes["KRE"].copy()
        changed["KRE"].loc[index[121]:] *= 4.0
        replay = freeze_events(build_feature_panel(curve, changed), forward_sessions=10)
        identity_fields = ["signal_date", "feature_max_date", "entry_date"]
        self.assertEqual(
            {field: event[field] for field in identity_fields},
            {field: replay[0][field] for field in identity_fields},
        )

    def test_aligned_positive_train_panel_passes_complete_discovery_gate(self):
        panel, events = self._outcome_panel([0.02] * 8)
        result = evaluate_train(
            panel,
            events,
            min_episodes=8,
            min_years=1,
            bootstrap_samples=500,
        )
        self.assertTrue(result["gate_pass"], result["gate_checks"])
        self.assertGreater(result["kre_mean_return_after_10bps"], 0.0)
        self.assertGreater(result["kre_minus_xlf_mean"], 0.0)
        self.assertGreater(result["kre_minus_xlf_block_bootstrap_lb90"], 0.0)
        self.assertEqual(result["train_signal_year_counts"], {"2010": 7, "2011": 1})
        self.assertEqual(result["train_calendar_concentration_max_fraction"], 7 / 8)

    def test_underlying_cost_is_labeled_as_ten_bps_round_trip_not_per_leg(self):
        geometry = frozen_geometry()
        self.assertEqual(geometry["underlying_round_trip_cost_bps"], 10.0)
        self.assertNotIn("underlying_cost_bps_each_leg", geometry)
        panel, events = self._outcome_panel([0.02] * 5)
        result = evaluate_train(
            panel,
            events,
            min_episodes=5,
            min_years=1,
            bootstrap_samples=500,
        )
        self.assertAlmostEqual(cast(float, result["kre_mean_return_after_10bps"]), 0.019)

    def test_five_episode_uncertainty_gate_is_nonvacuous(self):
        panel, events = self._outcome_panel([0.02] * 4)
        result = evaluate_train(
            panel,
            events,
            min_episodes=4,
            min_years=1,
            bootstrap_samples=500,
        )
        self.assertGreater(result["kre_minus_xlf_mean"], 0.0)
        self.assertFalse(
            result["gate_checks"]["kre_minus_xlf_five_episode_block_lb90_positive"]
        )
        self.assertFalse(result["gate_pass"])

    def test_favorable_center_with_unstable_episode_fails_uncertainty(self):
        panel, events = self._outcome_panel([0.02, 0.02, 0.02, 0.02, 0.02, -0.05])
        result = evaluate_train(
            panel,
            events,
            min_episodes=6,
            min_years=1,
            bootstrap_samples=2_000,
        )
        self.assertGreater(result["kre_mean_return_after_10bps"], 0.0)
        self.assertFalse(
            result["gate_checks"]["kre_minus_xlf_five_episode_block_lb90_positive"]
        )
        self.assertFalse(result["gate_pass"])

    def test_event_tail_gate_cannot_be_rescued_by_relative_outperformance(self):
        panel, events = self._outcome_panel([0.02, 0.02, 0.02, 0.02, 0.02, -0.08])
        last = events[-1]
        panel.iloc[last["entry_pos"], panel.columns.get_loc("xlf")] = 100.0
        panel.iloc[last["exit_pos"], panel.columns.get_loc("xlf")] = 80.0
        result = evaluate_train(
            panel,
            events,
            min_episodes=6,
            min_years=1,
            bootstrap_samples=2_000,
        )
        self.assertGreater(result["kre_minus_xlf_mean"], 0.0)
        self.assertLess(result["kre_event_return_worst_decile_mean_after_10bps"], -0.07)
        self.assertFalse(
            result["gate_checks"]["kre_event_return_worst_decile_at_least_negative_7pct"]
        )
        self.assertFalse(result["gate_pass"])

    def test_option_structure_is_only_a_capital_planning_boundary(self):
        boundary = planning_risk_boundaries()
        self.assertEqual(boundary["structure"], "KRE $2-wide bull call debit spread")
        self.assertEqual(boundary["capital_fit_usd"], 200.0)
        self.assertEqual(boundary["max_loss_usd"], 200.0)
        self.assertEqual(boundary["max_lots"], 1)
        self.assertFalse(boundary["option_path_measured"])
        self.assertEqual(boundary["option_pricing_calls"], 0)
        self.assertIn("frictionless planning", boundary["max_loss_semantics"])

    def test_partition_seals_identity_only_holdout(self):
        events = [
            {
                "signal_pos": 100 + i * 12,
                "signal_date": pd.Timestamp("2010-01-04") + pd.offsets.BDay(100 + i * 12),
                "feature_max_date": pd.Timestamp("2010-01-04") + pd.offsets.BDay(100 + i * 12),
                "entry_pos": 101 + i * 12,
                "entry_date": pd.Timestamp("2010-01-04") + pd.offsets.BDay(101 + i * 12),
                "exit_pos": 111 + i * 12,
                "exit_date": pd.Timestamp("2010-01-04") + pd.offsets.BDay(111 + i * 12),
                "spread_change20": 0.25,
                "dgs2_change20": -0.15,
            }
            for i in range(10)
        ]
        train, holdout = partition_events(events, train_fraction=0.60)
        self.assertEqual((len(train), len(holdout)), (6, 4))
        payload = holdout_identity_payload(holdout)
        self.assertFalse(payload["outcome_metrics_read"])
        self.assertFalse(payload["simulation_run"])
        self.assertEqual(payload["option_pricing_calls"], 0)
        self.assertNotIn("return", " ".join(payload.keys()).lower())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.trader_strategy_engine_route_batch import (
    _candidate_events,
    _managed_forward_return,
    _panel_rows,
    _route_specs,
    build_batch,
)


class StrategyEngineRouteBatchTests(unittest.TestCase):
    def test_builds_manifest_panel_and_quarantine_from_cached_ohlcv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            cache = repo / ".cache"
            cache.mkdir()
            run = repo / "reports" / "trader-wakes" / "moa" / "2026-test"
            run.mkdir(parents=True)
            run.joinpath("compounding.json").write_text(
                json.dumps({"closed_families": ["CLOSED_FAMILY_V1"]}) + "\n",
                encoding="utf-8",
            )
            dates = pd.bdate_range("2021-01-01", periods=420)
            for i, symbol in enumerate(
                [
                    "SPY",
                    "QQQ",
                    "IWM",
                    "TSLA",
                    "NVDA",
                    "AMD",
                    "PLTR",
                    "SMCI",
                    "AAPL",
                    "MSFT",
                    "META",
                    "GOOGL",
                    "AMZN",
                ]
            ):
                close = [100 + i + idx * 0.2 + ((idx % 17) - 8) * 0.05 for idx in range(len(dates))]
                pd.DataFrame(
                    {
                        "Date": dates,
                        "open": close,
                        "high": [value * 1.01 for value in close],
                        "low": [value * 0.99 for value in close],
                        "close": close,
                        "volume": 1_000_000,
                    }
                ).to_csv(cache / f"{symbol}_5y.csv", index=False)

            result = build_batch(
                repo,
                repo / ".cache" / "strategy-engine" / "routes.json",
                repo / ".cache" / "strategy-engine" / "panel.csv",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["route_count"], 9)
            manifest = json.loads((repo / ".cache" / "strategy-engine" / "routes.json").read_text())
            self.assertIn({"family": "CLOSED_FAMILY_V1", "fingerprint": ""}, manifest["quarantine"])
            gap_reversal = next(
                route
                for route in manifest["routes"]
                if route["id"] == "cached_high_beta_downside_gap_reversal_call_debit_5d_v1"
            )
            self.assertEqual(gap_reversal["family"], "CACHED_HIGH_BETA_DOWNSIDE_GAP_REVERSAL")
            self.assertEqual(gap_reversal["search_budget"]["max_variants"], 1)
            self.assertEqual(gap_reversal["trigger"]["source_semantics"], "cached_daily_ohlcv_close_known_at_signal_close")
            managed = [route for route in manifest["routes"] if route["risk_management"]["type"] == "path_aware"]
            self.assertEqual(len(managed), 3)
            self.assertEqual(
                {route["id"] for route in managed},
                {
                    "cached_high_beta_momentum_call_debit_stop6_10d_v1",
                    "cached_high_beta_momentum_call_debit_time5_v1",
                    "cached_high_beta_momentum_call_debit_stop6_time5_v1",
                },
            )
            self.assertTrue(all(route["search_budget"]["max_variants"] == 1 for route in managed))
            bearish = next(
                route
                for route in manifest["routes"]
                if route["id"] == "cached_broad_index_volatility_breakdown_put_debit_5d_v1"
            )
            self.assertEqual(bearish["direction"], "short")
            self.assertEqual(bearish["planned_structure"]["expression"], "debit_put_spread")
            self.assertEqual(bearish["risk_management"]["type"], "terminal_close")
            self.assertEqual(bearish["search_budget"]["max_variants"], 1)
            self.assertGreater(result["panel_rows"], 0)
            panel_text = (repo / ".cache" / "strategy-engine" / "panel.csv").read_text()
            self.assertIn("event_return", panel_text)
            self.assertIn("control_return", panel_text)

    def test_path_management_uses_next_session_ohlc_and_fixed_time_exit(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=12)
        frame = pd.DataFrame(
            {
                "open": [100.0] * 12,
                "high": [101.0] * 12,
                "low": [99.0, 93.0, *([99.0] * 10)],
                "close": [100.0, 98.0, 102.0, 104.0, 106.0, 110.0, 108.0, 105.0, 100.0, 90.0, 80.0, 79.0],
            },
            index=dates,
        )
        specs = {spec.route_id: spec for spec in _route_specs()}
        stop = specs["cached_high_beta_momentum_call_debit_stop6_10d_v1"]
        time_exit = specs["cached_high_beta_momentum_call_debit_time5_v1"]

        stop_return = _managed_forward_return(frame, dates[0], stop)
        time_exit_return = _managed_forward_return(frame, dates[0], time_exit)
        assert stop_return is not None
        assert time_exit_return is not None
        self.assertAlmostEqual(float(stop_return), -0.06)
        self.assertAlmostEqual(float(time_exit_return), 0.10)

        gap_frame = frame.copy()
        gap_frame.loc[dates[1], "open"] = 92.0
        gap_frame.loc[dates[1], "low"] = 91.0
        gap_return = _managed_forward_return(gap_frame, dates[0], stop)
        assert gap_return is not None
        self.assertAlmostEqual(float(gap_return), -0.08)

        no_same_bar_reentry = frame.copy()
        no_same_bar_reentry["low"] = 99.0
        no_same_bar_reentry.loc[dates[0], "low"] = 50.0
        no_same_bar_reentry.loc[dates[10], "close"] = 110.0
        no_same_bar_return = _managed_forward_return(no_same_bar_reentry, dates[0], stop)
        assert no_same_bar_return is not None
        self.assertAlmostEqual(float(no_same_bar_return), 0.10)

    def test_short_terminal_route_keeps_raw_return_for_engine_signing(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=8)
        frame = pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.0, 98.0, 96.0, 94.0, 92.0, 90.0, 89.0, 88.0],
            },
            index=dates,
        )
        specs = {spec.route_id: spec for spec in _route_specs()}
        bearish = specs["cached_broad_index_volatility_breakdown_put_debit_5d_v1"]

        terminal_return = _managed_forward_return(frame, dates[0], bearish)

        assert terminal_return is not None
        self.assertAlmostEqual(float(terminal_return), -0.10)

    def test_downside_gap_reversal_trigger_uses_current_day_ohlc_only(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=130)
        frame = pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.0] * len(dates),
            },
            index=dates,
        )
        signal = dates[100]
        frame.loc[signal, ["open", "high", "low", "close"]] = [94.0, 99.0, 92.0, 98.5]
        specs = {spec.route_id: spec for spec in _route_specs()}
        spec = specs["cached_high_beta_downside_gap_reversal_call_debit_5d_v1"]

        events = _candidate_events(spec, {"TSLA": frame})

        self.assertEqual([(event["date"], event["symbol"]) for event in events], [(signal, "TSLA")])

    def test_chronological_split_never_bisects_same_date_events(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=20)
        frame = pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.0 + idx for idx in range(len(dates))],
            },
            index=dates,
        )
        specs = {spec.route_id: spec for spec in _route_specs()}
        spec = specs["cached_high_beta_downside_gap_reversal_call_debit_5d_v1"]
        events = [
            {"date": dates[idx], "symbol": "TSLA", "event_return": 0.01}
            for idx in range(6)
        ]
        boundary_date = dates[6]
        events.extend(
            [
                {"date": boundary_date, "symbol": "TSLA", "event_return": 0.01},
                {"date": boundary_date, "symbol": "NVDA", "event_return": 0.01},
                {"date": dates[7], "symbol": "TSLA", "event_return": 0.01},
                {"date": dates[8], "symbol": "TSLA", "event_return": 0.01},
            ]
        )

        rows = _panel_rows(spec, events, {"TSLA": frame, "NVDA": frame, "SPY": frame})
        boundary_splits = {
            row["split"]
            for row in rows
            if row["is_event"] == 1 and row["date"] == boundary_date.date().isoformat()
        }

        self.assertEqual(boundary_splits, {"train"})

    def test_chronological_split_uses_only_events_with_same_date_controls(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=20)
        frame = pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.0 + idx for idx in range(len(dates))],
            },
            index=dates,
        )
        specs = {spec.route_id: spec for spec in _route_specs()}
        spec = specs["cached_high_beta_downside_gap_reversal_call_debit_5d_v1"]
        events = [
            {"date": dates[idx], "symbol": "TSLA", "event_return": 0.01}
            for idx in range(10)
        ]

        rows = _panel_rows(spec, events, {"TSLA": frame, "SPY": frame.loc[dates[5] :]})
        event_rows = [row for row in rows if row["is_event"] == 1]

        self.assertEqual(len(event_rows), 5)
        self.assertEqual(sum(row["split"] == "train" for row in event_rows), 3)
        self.assertEqual(sum(row["split"] == "holdout" for row in event_rows), 2)


if __name__ == "__main__":
    unittest.main()

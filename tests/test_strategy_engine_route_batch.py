from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.trader_strategy_engine_route_batch import (
    _managed_forward_return,
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
            self.assertEqual(result["route_count"], 7)
            manifest = json.loads((repo / ".cache" / "strategy-engine" / "routes.json").read_text())
            self.assertIn({"family": "CLOSED_FAMILY_V1", "fingerprint": ""}, manifest["quarantine"])
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


if __name__ == "__main__":
    unittest.main()

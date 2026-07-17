from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.trader_strategy_engine_route_batch import build_batch


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
            self.assertEqual(result["route_count"], 4)
            manifest = json.loads((repo / ".cache" / "strategy-engine" / "routes.json").read_text())
            self.assertIn({"family": "CLOSED_FAMILY_V1", "fingerprint": ""}, manifest["quarantine"])
            self.assertGreater(result["panel_rows"], 0)
            panel_text = (repo / ".cache" / "strategy-engine" / "panel.csv").read_text()
            self.assertIn("event_return", panel_text)
            self.assertIn("control_return", panel_text)


if __name__ == "__main__":
    unittest.main()

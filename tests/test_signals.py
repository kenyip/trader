"""Engine contracts for signal catalog + snapshots (not strategy doctrine)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

from trader_platform.research.signals import (
    DEFAULT_CATALOG_PATH,
    load_signal_catalog,
    snapshot_from_row,
)


class SignalCatalogTest(unittest.TestCase):
    def test_default_catalog_loads(self):
        cat = load_signal_catalog(reload=True)
        self.assertGreaterEqual(cat.version, 1)
        self.assertIn("regime", cat.names())
        self.assertIn("iv_rank", cat.names())
        self.assertTrue(cat.get("regime").lag_safe)
        self.assertIsNotNone(cat.get("iv_rank").known_lie)
        self.assertTrue(DEFAULT_CATALOG_PATH.exists())

    def test_entry_relevant_subset_of_catalog(self):
        cat = load_signal_catalog(reload=True)
        for name in cat.entry_relevant:
            self.assertIn(name, cat.names())

    def test_unknown_signal_raises(self):
        cat = load_signal_catalog(reload=True)
        with self.assertRaises(KeyError):
            cat.get("not_a_real_signal")

    def test_invalid_entry_relevant_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "signals": {
                            "close": {
                                "column": "close",
                                "group": "price",
                                "units": "px",
                                "lag_safe": True,
                                "description": "x",
                                "source": "ohlcv",
                            }
                        },
                        "entry_relevant": ["missing_signal"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_signal_catalog(path, reload=True)

    def test_snapshot_from_row_projects_named_values(self):
        cat = load_signal_catalog(reload=True)
        row = pd.Series(
            {
                "close": 100.0,
                "regime": "bullish",
                "iv_rank": 55.0,
                "ema_stack": 0.5,
            }
        )
        snap = snapshot_from_row(
            row,
            symbol="bac",
            asof="2024-01-02",
            catalog=cat,
            signal_names=["close", "regime", "iv_rank"],
        )
        self.assertEqual(snap.symbol, "BAC")
        self.assertEqual(snap.asof, "2024-01-02")
        self.assertEqual(snap.values["regime"], "bullish")
        self.assertEqual(snap.values["iv_rank"], 55.0)
        self.assertEqual(snap.values["close"], 100.0)
        self.assertEqual(snap.missing, ())

    def test_snapshot_lists_missing_columns(self):
        cat = load_signal_catalog(reload=True)
        row = pd.Series({"close": 10.0})
        snap = snapshot_from_row(
            row,
            symbol="KO",
            asof="2024-01-02",
            catalog=cat,
            signal_names=["close", "regime"],
        )
        self.assertIn("close", snap.values)
        self.assertIn("regime", snap.missing)
        with self.assertRaises(KeyError):
            snap.require("regime")

    def test_snapshot_rejects_unknown_signal_name(self):
        cat = load_signal_catalog(reload=True)
        with self.assertRaises(KeyError):
            snapshot_from_row(
                {"close": 1.0},
                symbol="X",
                asof="t",
                catalog=cat,
                signal_names=["totally_fake"],
            )


if __name__ == "__main__":
    unittest.main()

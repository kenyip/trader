from __future__ import annotations

import unittest
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import yaml

from scripts.pcs_time_bias_grid import _hyp_ids, _weekday_slices
import scripts.pcs_time_variant_stress as time_stress
from scripts.pcs_time_variant_stress import _load_variant
from trader_platform.research import pcs_sim


class PcsTimeBiasGridTest(unittest.TestCase):
    def test_time_variant_can_override_spread_width(self) -> None:
        args = Namespace(
            hyp="hyp_dna_bac_put_credit_spread_5f52fa0e",
            long_dte=7,
            profit_target=0.35,
            dte_stop=5,
            entry_weekday="fri",
            spread_width=0.5,
        )

        fixture = {
            "hypotheses": [
                {
                    "id": args.hyp,
                    "dna": {
                        "structure": "put_credit_spread",
                        "symbols": ["BAC"],
                        "config": {"spread_width": 1.0},
                    },
                }
            ]
        }
        with TemporaryDirectory() as tmp:
            fixture_path = Path(tmp) / "hypotheses.yaml"
            fixture_path.write_text(yaml.safe_dump(fixture), encoding="utf-8")
            with patch.object(time_stress, "HYPS_PATH", fixture_path):
                variant = _load_variant(args)

        self.assertEqual(variant["dna"]["config"]["spread_width"], 0.5)
        self.assertTrue(variant["id"].endswith("_w0.5"))

    def test_hyp_ids_support_single_and_multi_hyp_grids(self) -> None:
        self.assertEqual(_hyp_ids(None, None), ["hyp_dna_tsll_put_credit_spread_b195f5fe"])
        self.assertEqual(_hyp_ids("one", None), ["one"])
        self.assertEqual(_hyp_ids(None, "one, two"), ["one", "two"])
        with self.assertRaises(SystemExit):
            _hyp_ids("one", "two")

    def test_weekday_slices_parse_all_trading_days(self) -> None:
        self.assertEqual(
            _weekday_slices("all,mon,wed,fri"),
            [("all", None), ("mon", [0]), ("wed", [2]), ("fri", [4])],
        )

    def test_run_pcs_backtest_only_opens_on_configured_weekday(self) -> None:
        dates = pd.date_range("2026-06-01", periods=15, freq="B")
        df = pd.DataFrame({"close": 20.0, "iv_proxy": 0.5}, index=dates)
        opened: list[int] = []

        def fake_entry(row, spot, today, cfg, *, structure):
            opened.append(int(pd.Timestamp(today).weekday()))
            return None

        with patch.object(pcs_sim, "pick_structure_entry", side_effect=fake_entry):
            result = pcs_sim.run_pcs_backtest(
                "TEST",
                config={"entry_weekdays": [2]},
                df=df,
                min_bars=1,
            )

        self.assertTrue(result.ok)
        self.assertEqual(opened, [2, 2, 2])


if __name__ == "__main__":
    unittest.main()

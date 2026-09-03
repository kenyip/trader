"""Tests for TSLL covered-call selection study."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


class TestTsllCoveredCallSelection(unittest.TestCase):
    def test_result_schema(self):
        result_path = _REPO / "studies" / "tsll_covered_call" / "RESULT.json"
        if not result_path.exists():
            import subprocess
            subprocess.run(
                ["python3", str(_REPO / "scripts" / "tsll_covered_call_selection.py")],
                check=True,
                cwd=_REPO,
            )
        payload = json.loads(result_path.read_text())
        self.assertIn("recommendation", payload)
        self.assertIn("ranked_candidates", payload)
        self.assertTrue(payload["ranked_candidates"])
        rec = payload["recommendation"]
        self.assertIn("trades", rec)
        self.assertGreater(rec["total_premium_usd"], 0)
        for t in rec["trades"]:
            self.assertGreaterEqual(t["bid"], 0.05)
            self.assertGreater(t["contracts"], 0)

    def test_liquidity_thresholds_documented(self):
        from scripts.tsll_covered_call_selection import LIQUIDITY

        self.assertGreaterEqual(LIQUIDITY["min_bid"], 0.05)
        self.assertGreaterEqual(LIQUIDITY["min_open_interest"], 1)

    def test_measure_k_decay(self):
        from scripts.tsll_covered_call_selection import measure_k_decay

        info = measure_k_decay()
        self.assertEqual(info["label"], "MEASURED")
        self.assertLess(info["monthly_decay_pct"], 0)
        self.assertGreater(info["k_now"], 0)


if __name__ == "__main__":
    unittest.main()

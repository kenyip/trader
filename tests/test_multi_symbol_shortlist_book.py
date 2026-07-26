"""Multi-symbol re-prove expands book with quality shortlist symbols."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trader_platform.research.bootstrap import (
    run_multi_symbol_pack,
    symbols_from_quality_shortlist,
)


class MultiSymbolShortlistBookTest(unittest.TestCase):
    def test_symbols_from_quality_shortlist(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "QUALITY_SHORTLIST.json"
            p.write_text(
                json.dumps(
                    {
                        "shortlist": [
                            {"symbol": "AAL", "structure": "put_credit_spread"},
                            {"symbol": "BAC", "structure": "put_credit_spread"},
                            {"symbol": "AAL", "structure": "put_credit_spread"},
                            {"symbol": "F", "structure": "put_credit_spread"},
                        ]
                    }
                )
            )
            syms = symbols_from_quality_shortlist(p, top_n=10)
            self.assertEqual(syms, ["AAL", "BAC", "F"])

    def test_from_quality_shortlist_prepends_book(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qs = root / "QUALITY_SHORTLIST.json"
            qs.write_text(
                json.dumps(
                    {
                        "shortlist": [
                            {"symbol": "AAL"},
                            {"symbol": "BAC"},
                        ]
                    }
                )
            )
            seed = Path("configs/strategy_specs/pcs_bull_neutral_income_45d_v1.json")
            shortlist = [
                {
                    "candidate_id": "TEST_DNA",
                    "spec_path": str(seed.resolve()),
                    "symbols": ["KO"],
                }
            ]

            seen_symbols: list[list[str]] = []

            def fake_eval(spec, **kwargs):
                seen_symbols.append(list(spec.symbols))
                return {
                    "decision": "FAMILY_CLOSED",
                    "n_train_pass": 0,
                    "n_holdout_pass": 0,
                    "holdout_rows": [],
                }

            report_path = root / "MULTI.json"
            report = run_multi_symbol_pack(
                shortlist=shortlist,
                symbols=["IWM"],
                report_path=report_path,
                evaluate_fn=fake_eval,
                from_quality_shortlist=True,
                quality_shortlist_path=qs,
            )
            self.assertEqual(report["quality_shortlist_symbols"], ["AAL", "BAC"])
            self.assertIn("AAL", report["book_symbols"])
            self.assertIn("BAC", report["book_symbols"])
            self.assertIn("IWM", report["book_symbols"])
            # multi_symbol_reprove evaluates one symbol at a time; first calls include AAL/BAC
            flat = {s for batch in seen_symbols for s in batch}
            self.assertIn("AAL", flat)
            self.assertIn("BAC", flat)
            self.assertIn("KO", flat)
            self.assertFalse(report["live_authority"])


if __name__ == "__main__":
    unittest.main()

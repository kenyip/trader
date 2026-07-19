"""Bootstrap tooling contracts — selection plumbing, not fixed winners."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trader_platform.research.bootstrap import (
    collect_bootstrap_candidates,
    load_bootstrap_config,
    re_prove_candidates,
    select_shortlist,
    write_bootstrap_report,
)


class BootstrapToolingTest(unittest.TestCase):
    def test_config_loads(self):
        cfg = load_bootstrap_config()
        self.assertIn("selection", cfg)
        self.assertIn("candidates", cfg)

    def test_select_shortlist_diversity(self):
        cands = [
            {
                "seat_id": "a",
                "symbols": ["INTC"],
                "coarse_dna_key": "dna1",
                "candidate_id": "a",
            },
            {
                "seat_id": "b",
                "symbols": ["INTC"],
                "coarse_dna_key": "dna1",
                "candidate_id": "b",
            },
            {
                "seat_id": "c",
                "symbols": ["BAC"],
                "coarse_dna_key": "dna2",
                "candidate_id": "c",
            },
            {
                "seat_id": "d",
                "symbols": ["KO"],
                "coarse_dna_key": "dna3",
                "candidate_id": "d",
            },
        ]
        short = select_shortlist(cands, top_n=3)
        self.assertEqual(len(short), 3)
        self.assertEqual(short[0]["symbols"], ["INTC"])

    def test_re_prove_with_injected_evaluate(self):
        def fake_eval(spec, **kwargs):
            return {
                "decision": "STRATEGY_ADVANCED_F2",
                "n_train_pass": 1,
                "n_holdout_pass": 1,
                "option_mark_provenance": "black_scholes_proxy",
            }

        seed = Path("configs/strategy_specs/pcs_bull_neutral_income_45d_v1.json")
        cands = [
            {
                "candidate_id": "X",
                "symbols": ["BAC"],
                "spec_path": str(seed.resolve()),
                "coarse_dna_key": "dnaX",
            }
        ]
        report = re_prove_candidates(cands, evaluate_fn=fake_eval)
        self.assertEqual(report["n_passed_f2"], 1)
        self.assertTrue(report["shortlist"])
        self.assertFalse(report["live_authority"])
        self.assertIn("L0", report["honesty"])

    def test_re_prove_records_fail_without_loosening(self):
        def fail_eval(spec, **kwargs):
            return {
                "decision": "FAMILY_CLOSED",
                "n_train_pass": 0,
                "n_holdout_pass": 0,
            }

        seed = Path("configs/strategy_specs/pcs_bull_neutral_income_45d_v1.json")
        report = re_prove_candidates(
            [{"symbols": ["BAC"], "spec_path": str(seed.resolve())}],
            evaluate_fn=fail_eval,
        )
        self.assertEqual(report["n_passed_f2"], 0)
        self.assertEqual(report["shortlist"], [])

    def test_write_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "boot.json"
            p = write_bootstrap_report({"ok": True, "n": 1}, path)
            self.assertTrue(p.exists())

    def test_collect_includes_thesis_files(self):
        cands = collect_bootstrap_candidates(include_theses=True, include_f2=False)
        ids = {c.thesis_id for c in cands}
        self.assertIn("bull_neutral_pcs_45d", ids)
        self.assertIn("iv_rich_noncollapse_pcs_21d", ids)


if __name__ == "__main__":
    unittest.main()

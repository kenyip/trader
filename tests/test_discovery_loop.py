import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trader_platform.research.discovery_loop import (
    all_grid_mutants,
    generation_mutants,
    list_seed_specs,
    run_discovery_loop,
    run_generation,
)
from trader_platform.research.evolve_strategy_spec import apply_mutant
from trader_platform.research.living_registry import LivingRegistry, save_living_registry
from trader_platform.research.strategy_spec import load_strategy_spec


class DiscoveryLoopTest(unittest.TestCase):
    def test_generation_mutants_rotate(self):
        a = generation_mutants(0, 2)
        b = generation_mutants(1, 2)
        self.assertEqual(len(a), 2)
        self.assertEqual(len(b), 2)
        # dense grid slices differ by generation offset
        self.assertNotEqual(
            (a[0].suffix, a[1].suffix),
            (b[0].suffix, b[1].suffix),
        )

    def test_list_seed_specs_finds_repo_configs(self):
        seeds = list_seed_specs()
        self.assertTrue(any(p.name.endswith(".json") for p in seeds))

    def test_run_generation_skips_known_and_records_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "reg.json"
            out = Path(tmp) / "out"
            save_living_registry(LivingRegistry(), reg)
            seed = list_seed_specs()[0]
            fake_report = {
                "candidate_id": "X",
                "family_id": "F",
                "decision": "FAMILY_CLOSED",
                "n_train_pass": 0,
                "n_holdout_pass": 0,
                "symbols": ["BAC"],
                "evaluation_mode": "regime_router",
                "living_candidates": [],
            }

            def _fake_job(payload):
                mid = payload["mutant"]["candidate_id"]
                fid = payload["mutant"]["family_id"]
                return {
                    **fake_report,
                    "candidate_id": mid,
                    "family_id": fid,
                    "suffix": payload.get("suffix", ""),
                    "spec_path": str(out / f"{mid}.json"),
                    "report_path": str(out / f"{mid}_eval.json"),
                    "report": {**fake_report, "candidate_id": mid, "family_id": fid},
                }

            with patch(
                "trader_platform.research.discovery_loop._evaluate_one_job",
                side_effect=_fake_job,
            ), patch(
                "trader_platform.research.discovery_loop.ingest_evaluate_report",
                return_value=LivingRegistry(),
            ):
                summary = run_generation(
                    seed_path=seed,
                    gen_index=0,
                    max_mutants=2,
                    screen_symbol_list=["BAC"],
                    prove_symbol_list=["BAC"],
                    out_dir=out,
                    registry_path=reg,
                    run_holdout=False,
                    known=set(),
                    workers=1,
                )
            self.assertEqual(summary["n_evaluated"], 2)
            self.assertTrue(summary["progressed"])

    def test_loop_stops_on_no_progress_when_all_skipped(self):
        """Stall when the full Wave A bag is already known (no novel evals)."""
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "reg.json"
            out = Path(tmp) / "out"
            save_living_registry(LivingRegistry(), reg)
            seed = list_seed_specs()[0]
            seed_spec = load_strategy_spec(seed)
            known: set[str] = set()
            for plan in all_grid_mutants():
                m = apply_mutant(seed_spec, plan)
                known.add(m.candidate_id)
                known.add(m.family_id)

            with patch(
                "trader_platform.research.discovery_loop.known_ids", return_value=known
            ), patch(
                "trader_platform.research.discovery_loop.list_seed_specs",
                return_value=[seed],
            ):
                report = run_discovery_loop(
                    seeds=[seed],
                    max_generations=5,
                    max_mutants_per_gen=2,
                    max_no_progress_generations=2,
                    symbols=["BAC"],
                    run_holdout=False,
                    registry_path=reg,
                    out_dir=out,
                    state_path=Path(tmp) / "state.json",
                    workers=1,
                )
            self.assertEqual(report["stop_reason"], "no_progress_stall")
            self.assertEqual(report["total_evaluated"], 0)


if __name__ == "__main__":
    unittest.main()

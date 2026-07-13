from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.trader_build_compounding import (
    CompoundingError,
    assess_research_routes,
    build_context,
    snapshot,
    validate,
)


class TraderBuildCompoundingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=self.repo, check=True)
        (self.repo / "seed.txt").write_text("seed\n")
        (self.repo / "scripts").mkdir()
        (self.repo / "tests").mkdir()
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 1\n")
        (self.repo / "tests" / "test_existing.py").write_text("# existing\n")
        self._git("add", "-A")
        self._git("commit", "-m", "seed")
        self.base = self._git("rev-parse", "HEAD")
        self.remote = self.repo.parent / f"{self.repo.name}-remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        self._git("remote", "add", "origin", str(self.remote))
        self._git("push", "-u", "origin", "main")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, text=True, capture_output=True
        ).stdout.strip()

    def _handoff(self, stamp: str, **updates):
        run = self.repo / "reports" / "trader-wakes" / "moa" / stamp
        run.mkdir(parents=True, exist_ok=True)
        learning = run / "learning-promotion.md"
        learning.write_text(
            "## VERIFICATION\ngreen\n\n## DURABLE\ndelta\n\n"
            "## LESSON\nlearned\n\n## NEXT\none seed\n"
        )
        artifact = self.repo / "reports" / "delta.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("material delta\n")
        row = {
            "schema_version": 1,
            "stamp": stamp,
            "loop_signature": "direction/pullback/rolling-origin",
            "outcome": "FALSIFIED",
            "useful_deltas": [
                {
                    "kind": "evidence",
                    "summary": "closed a family",
                    "novelty_key": f"closed-{stamp}",
                    "artifacts": ["reports/delta.md"],
                }
            ],
            "critic_findings": [],
            "closed_families": ["mild-pullback-pcs"],
            "data_dependencies": ["new market date"],
            "next": "one seed",
        }
        row.update(updates)
        (run / "compounding.json").write_text(json.dumps(row) + "\n")
        return run, learning

    def test_context_carries_closed_families_and_redirects_repeated_loop(self):
        for stamp in ("2026-01-01T0000", "2026-01-01T0100"):
            run, _ = self._handoff(stamp)
            self._git("add", str(run.relative_to(self.repo)))
            self._git("commit", "-m", stamp)
            self._git("push", "origin", "main")
        out = self.repo / "reports" / "current" / "orientation.json"
        result = build_context(self.repo, "2026-01-01T0200", out)
        self.assertEqual(result["closed_families"], ["mild-pullback-pcs"])
        self.assertTrue(result["redirect_required"])
        self.assertIn("last two", result["redirect_reasons"][0])

    def test_forward_archive_dependency_cannot_globally_force_diminishing_returns(self):
        stamp = "2026-01-01T0159"
        run, _ = self._handoff(
            stamp,
            outcome="DIMINISHING_RETURNS",
            useful_deltas=[],
            next="DIMINISHING_RETURNS",
            data_dependencies=["forward option archive needs two more dates"],
        )
        self._git("add", str(run.relative_to(self.repo)))
        self._git("commit", "-m", stamp)
        self._git("push", "origin", "main")
        cache = self.repo / ".cache"
        cache.mkdir()
        (cache / "AAPL_5y.csv").write_text("date,close\n2025-01-01,100\n")
        sim = self.repo / "trader_platform" / "research" / "pcs_sim.py"
        sim.parent.mkdir(parents=True)
        sim.write_text("# historical underlying / proxy option simulator\n")

        out = self.repo / "reports" / "current" / "orientation.json"
        result = build_context(self.repo, "2026-01-01T0200", out)

        routes = result["research_routes"]
        self.assertFalse(routes["archive_density_alone_can_justify_diminishing_returns"])
        self.assertTrue(routes["routes"]["historical_underlying_proxy_discovery"]["executable"])
        self.assertFalse(routes["routes"]["observed_historical_option_replay"]["executable"])
        self.assertTrue(result["redirect_required"])
        self.assertTrue(result["archive_dependent_stop_invalidated"])
        self.assertTrue(any("independent research route" in reason for reason in result["redirect_reasons"]))

    def test_non_archive_information_exhaustion_stop_is_not_invalidated(self):
        stamp = "2026-01-01T0159b"
        run, _ = self._handoff(
            stamp,
            outcome="DIMINISHING_RETURNS",
            useful_deltas=[],
            next="DIMINISHING_RETURNS",
            data_dependencies=["all materially novel open routes assessed"],
        )
        self._git("add", str(run.relative_to(self.repo)))
        self._git("commit", "-m", stamp)
        self._git("push", "origin", "main")
        cache = self.repo / ".cache"
        cache.mkdir()
        (cache / "AAPL_5y.csv").write_text("date,close\n2025-01-01,100\n")
        sim = self.repo / "trader_platform" / "research" / "pcs_sim.py"
        sim.parent.mkdir(parents=True)
        sim.write_text("# simulator\n")

        result = build_context(
            self.repo, "2026-01-01T0200b", self.repo / "reports" / "current" / "orientation.json"
        )

        self.assertFalse(result["archive_dependent_stop_invalidated"])
        self.assertFalse(any("archive-dependent" in reason for reason in result["redirect_reasons"]))

    def test_three_date_archive_is_plumbing_not_historical_edge_route(self):
        cache = self.repo / ".cache"
        cache.mkdir()
        (cache / "AAPL_5y.csv").write_text("date,close\n2025-01-01,100\n")
        sim = self.repo / "trader_platform" / "research" / "pcs_sim.py"
        sim.parent.mkdir(parents=True)
        sim.write_text("# simulator\n")
        archive = cache / "platform" / "option_quotes" / "AAPL_archive.csv"
        archive.parent.mkdir(parents=True)
        archive.write_text(
            "observed_at\n"
            "2026-01-02T20:00:00+00:00\n"
            "2026-01-05T20:00:00+00:00\n"
            "2026-01-06T20:00:00+00:00\n"
        )

        result = assess_research_routes(self.repo)
        observed = result["routes"]["observed_historical_option_replay"]

        self.assertTrue(observed["plumbing_gate_met"])
        self.assertFalse(observed["executable"])
        self.assertTrue(result["routes"]["historical_underlying_proxy_discovery"]["executable"])
        self.assertFalse(result["archive_density_alone_can_justify_diminishing_returns"])

    def test_no_executable_research_route_is_globally_blocked(self):
        result = assess_research_routes(self.repo)
        self.assertTrue(result["global_build_blocked"])
        self.assertFalse(result["archive_density_alone_can_justify_diminishing_returns"])

    def test_non_diminishing_handoff_requires_measurable_delta(self):
        stamp = "2026-01-01T0200"
        self._handoff(stamp, useful_deltas=[])
        with self.assertRaisesRegex(CompoundingError, "measurable useful delta"):
            validate(self.repo, stamp, self.base, None)

    def test_capability_delta_requires_machinery_and_test(self):
        stamp = "2026-01-01T0201"
        self._handoff(
            stamp,
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "script only",
                    "novelty_key": "script-only",
                    "artifacts": [
                        "scripts/existing.py",
                        "tests/test_existing.py",
                        "reports/delta.md",
                    ],
                }
            ],
        )
        with self.assertRaisesRegex(CompoundingError, "changed machinery"):
            validate(self.repo, stamp, self.base, None)

    def test_capability_requires_changed_tests_after_changed_machinery(self):
        stamp = "2026-01-01T0201a"
        self._handoff(
            stamp,
            outcome="CAPABILITY",
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "one-sided change",
                    "novelty_key": "one-sided-capability",
                    "artifacts": ["scripts/existing.py", "tests/test_existing.py"],
                }
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        with self.assertRaisesRegex(CompoundingError, "changed tests"):
            validate(self.repo, stamp, self.base, None)

    def test_capability_requires_test_artifact_and_accepts_dual_change(self):
        stamp = "2026-01-01T0201aa"
        self._handoff(
            stamp,
            outcome="CAPABILITY",
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "missing test path",
                    "novelty_key": "missing-test-path",
                    "artifacts": ["scripts/existing.py"],
                }
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        with self.assertRaisesRegex(CompoundingError, "test artifact"):
            validate(self.repo, stamp, self.base, None)
        row = json.loads((self.repo / "reports" / "trader-wakes" / "moa" / stamp / "compounding.json").read_text())
        row["useful_deltas"][0]["artifacts"].append("tests/test_existing.py")
        (self.repo / "reports" / "trader-wakes" / "moa" / stamp / "compounding.json").write_text(json.dumps(row) + "\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed\n")
        self.assertTrue(validate(self.repo, stamp, self.base, None)["role_ready"])

    def test_repaired_critic_finding_requires_existing_changed_machinery_and_tests(self):
        stamp = "2026-01-01T0201b"
        self._handoff(
            stamp,
            critic_findings=[
                {
                    "finding": "broken gate",
                    "status": "repaired",
                    "rationale": "claimed repair",
                    "repair_artifacts": ["scripts/missing.py"],
                    "test_artifacts": ["tests/test_existing.py"],
                }
            ],
        )
        with self.assertRaisesRegex(CompoundingError, "missing repair/test artifact"):
            validate(self.repo, stamp, self.base, None)

    def test_repaired_critic_finding_requires_both_changed_sides_and_prefixes(self):
        finding = {
            "finding": "broken gate",
            "status": "repaired",
            "rationale": "repair",
            "repair_artifacts": ["scripts/existing.py"],
            "test_artifacts": ["tests/test_existing.py"],
        }
        stamp = "2026-01-01T0201ba"
        self._handoff(stamp, critic_findings=[finding])
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        with self.assertRaisesRegex(CompoundingError, "tests were not changed"):
            validate(self.repo, stamp, self.base, None)

        (self.repo / "scripts" / "existing.py").write_text("VALUE = 1\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed\n")
        with self.assertRaisesRegex(CompoundingError, "machinery was not changed"):
            validate(self.repo, stamp, self.base, None)

        row_path = self.repo / "reports" / "trader-wakes" / "moa" / stamp / "compounding.json"
        row = json.loads(row_path.read_text())
        row["critic_findings"][0]["repair_artifacts"] = ["reports/delta.md"]
        row_path.write_text(json.dumps(row) + "\n")
        with self.assertRaisesRegex(CompoundingError, "not machinery"):
            validate(self.repo, stamp, self.base, None)

    def test_repaired_critic_finding_accepts_changed_machinery_and_tests(self):
        stamp = "2026-01-01T0201bb"
        self._handoff(
            stamp,
            critic_findings=[
                {
                    "finding": "broken gate",
                    "status": "repaired",
                    "rationale": "repair",
                    "repair_artifacts": ["scripts/existing.py"],
                    "test_artifacts": ["tests/test_existing.py"],
                }
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed\n")
        self.assertTrue(validate(self.repo, stamp, self.base, None)["role_ready"])

    def test_unintegrated_prior_record_does_not_pollute_orientation(self):
        self._handoff("2026-01-01T0100")
        out = self.repo / "reports" / "current" / "orientation.json"
        result = build_context(self.repo, "2026-01-01T0200", out)
        self.assertEqual(result["prior_record_count"], 0)
        self.assertEqual(result["closed_families"], [])

    def test_committed_unpushed_side_branch_prior_does_not_pollute_orientation(self):
        self._git("switch", "-c", "local-side")
        self._handoff("2026-01-01T0100b")
        self._git("add", "-A")
        self._git("commit", "-m", "local only prior")
        out = self.repo / "reports" / "current" / "orientation.json"
        result = build_context(self.repo, "2026-01-01T0200b", out)
        self.assertEqual(result["prior_record_count"], 0)
        self.assertEqual(result["closed_families"], [])

    def test_novelty_replay_against_integrated_prior_is_rejected(self):
        prior, _ = self._handoff("2026-01-01T0101")
        self._git("add", "-A")
        self._git("commit", "-m", "prior")
        self._git("push", "origin", "main")
        self.base = self._git("rev-parse", "HEAD")
        stamp = "2026-01-01T0201c"
        self._handoff(
            stamp,
            useful_deltas=[
                {
                    "kind": "evidence",
                    "summary": "replayed",
                    "novelty_key": "closed-2026-01-01T0101",
                    "artifacts": ["reports/delta.md"],
                }
            ],
        )
        (self.repo / "reports" / "delta.md").write_text("changed but not novel\n")
        with self.assertRaisesRegex(CompoundingError, "no new novelty"):
            validate(self.repo, stamp, self.base, None)

    def test_prompt_echo_cannot_satisfy_role_ready(self):
        stamp = "2026-01-01T0202"
        run, _ = self._handoff(stamp)
        baseline = self.repo / ".cache" / "baseline.json"
        snapshot(self.repo, stamp, baseline)
        (run / "finalizer-session.log").write_text("MOA_FINALIZE_READY\n")
        with self.assertRaisesRegex(CompoundingError, "did not materially write role artifact"):
            validate(self.repo, stamp, self.base, baseline)

    def test_changed_structured_handoff_validates_without_session_marker(self):
        stamp = "2026-01-01T0203"
        run, learning = self._handoff(stamp)
        baseline = self.repo / ".cache" / "baseline.json"
        snapshot(self.repo, stamp, baseline)
        learning.write_text(learning.read_text() + "finalizer evidence\n")
        row = json.loads((run / "compounding.json").read_text())
        row["finalized"] = True
        (run / "compounding.json").write_text(json.dumps(row) + "\n")
        result = validate(self.repo, stamp, self.base, baseline)
        self.assertTrue(result["role_ready"])
        self.assertIn("session text ignored", result["role_ready_basis"])


if __name__ == "__main__":
    unittest.main()

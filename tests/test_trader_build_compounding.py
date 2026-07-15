from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.trader_build_compounding import (
    SCHEMA_VERSION,
    CompoundingError,
    assess_research_routes,
    build_context,
    snapshot,
    strategy_advanced,
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
            "schema_version": SCHEMA_VERSION,
            "stamp": stamp,
            "loop_signature": "direction/pullback/rolling-origin",
            "economic_mechanism": "theta harvest after mild pullback",
            "candidate_or_family_scope": "mild-pullback-pcs",
            "funnel_stage_before": "F1_TRAIN",
            "funnel_stage_after": "F1_TRAIN",
            "falsifier": "train gate fails or holdout max_dd exceeds 75",
            "outcome": "FAMILY_CLOSED",
            "strategy_advancement": {
                "advanced": False,
                "summary": "family closed without stage movement",
            },
            "search_information": {
                "summary": "closed a family with falsification residue",
                "delta_kinds": ["falsification"],
            },
            "useful_deltas": [
                {
                    "kind": "falsification",
                    "summary": "closed a family",
                    "novelty_key": f"closed-{stamp}",
                    "artifacts": ["reports/delta.md"],
                }
            ],
            "critic_findings": [],
            "closed_families": ["mild-pullback-pcs"],
            "data_dependencies": ["new market date"],
            "next": "one seed",
            "retest_decision": None,
            "evidence_wake_condition": "",
        }
        row.update(updates)
        # Keep search_information.delta_kinds aligned when callers override useful_deltas only.
        if "useful_deltas" in updates and "search_information" not in updates:
            kinds = sorted(
                {
                    str(delta.get("kind"))
                    for delta in row.get("useful_deltas", [])
                    if isinstance(delta, dict) and delta.get("kind")
                }
            )
            search = dict(row.get("search_information") or {})
            search["delta_kinds"] = kinds
            if not search.get("summary"):
                search["summary"] = "search information"
            row["search_information"] = search
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
        self.assertTrue(result["strategy_pivot_required"])
        self.assertEqual(result["consecutive_no_strategy_advance"], 2)
        self.assertTrue(any("last two" in reason for reason in result["redirect_reasons"]))

    def test_forward_archive_dependency_cannot_globally_force_diminishing_returns(self):
        stamp = "2026-01-01T0159"
        run, _ = self._handoff(
            stamp,
            outcome="EVIDENCE_WAIT",
            useful_deltas=[],
            search_information={"summary": "waiting on archive density", "delta_kinds": []},
            strategy_advancement={"advanced": False, "summary": "no advance; waiting on data"},
            closed_families=[],
            data_dependencies=["forward option archive needs two more dates"],
            evidence_wake_condition="wake when a third distinct NY market date is archived",
            next="wait for third archive date",
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
            outcome="EVIDENCE_WAIT",
            useful_deltas=[],
            search_information={"summary": "all open routes assessed", "delta_kinds": []},
            strategy_advancement={"advanced": False, "summary": "no advance"},
            closed_families=[],
            data_dependencies=["all materially novel open routes assessed"],
            evidence_wake_condition="reassess only after a new evidence class appears",
            next="DIMINISHING_RETURNS",
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

    def test_family_closed_handoff_requires_falsification_delta(self):
        stamp = "2026-01-01T0200"
        self._handoff(stamp, useful_deltas=[])
        with self.assertRaisesRegex(CompoundingError, "measurable useful delta"):
            validate(self.repo, stamp, self.base, None)

    def test_legacy_schema_handoff_is_rejected_for_new_validation(self):
        stamp = "2026-01-01T0199"
        self._handoff(
            stamp,
            schema_version=1,
            outcome="CAPABILITY",
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "legacy capability",
                    "novelty_key": "legacy-capability",
                    "artifacts": ["scripts/existing.py", "tests/test_existing.py"],
                }
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed\n")
        with self.assertRaisesRegex(CompoundingError, "schema_version=2"):
            validate(self.repo, stamp, self.base, None)

    def test_capability_only_completion_fails_closed(self):
        stamp = "2026-01-01T0201"
        self._handoff(
            stamp,
            outcome="FAMILY_CLOSED",
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "tool only",
                    "novelty_key": "tool-only",
                    "artifacts": ["scripts/existing.py", "tests/test_existing.py"],
                }
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed\n")
        with self.assertRaisesRegex(CompoundingError, "capability-only handoff"):
            validate(self.repo, stamp, self.base, None)

    def test_capability_delta_requires_machinery_and_test(self):
        stamp = "2026-01-01T0201b"
        self._handoff(
            stamp,
            outcome="BLOCKER_REMOVED_AND_RETESTED",
            retest_decision="FAMILY_CLOSED",
            strategy_advancement={"advanced": False, "summary": "repaired then closed"},
            search_information={
                "summary": "repair + falsify",
                "delta_kinds": ["capability", "falsification"],
            },
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
                },
                {
                    "kind": "falsification",
                    "summary": "retest closed family",
                    "novelty_key": "retest-closed",
                    "artifacts": ["reports/delta.md"],
                },
            ],
        )
        with self.assertRaisesRegex(CompoundingError, "changed machinery"):
            validate(self.repo, stamp, self.base, None)

    def test_capability_requires_changed_tests_after_changed_machinery(self):
        stamp = "2026-01-01T0201a"
        self._handoff(
            stamp,
            outcome="BLOCKER_REMOVED_AND_RETESTED",
            retest_decision="FAMILY_CLOSED",
            strategy_advancement={"advanced": False, "summary": "repaired then closed"},
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "one-sided change",
                    "novelty_key": "one-sided-capability",
                    "artifacts": ["scripts/existing.py", "tests/test_existing.py"],
                },
                {
                    "kind": "falsification",
                    "summary": "retest closed family",
                    "novelty_key": "retest-closed-a",
                    "artifacts": ["reports/delta.md"],
                },
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        with self.assertRaisesRegex(CompoundingError, "changed tests"):
            validate(self.repo, stamp, self.base, None)

    def test_blocker_removed_and_retested_accepts_repair_plus_retest_close(self):
        stamp = "2026-01-01T0201aa"
        self._handoff(
            stamp,
            outcome="BLOCKER_REMOVED_AND_RETESTED",
            retest_decision="FAMILY_CLOSED",
            strategy_advancement={"advanced": False, "summary": "blocker removed; family closed on retest"},
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "fixed gate",
                    "novelty_key": "fixed-gate",
                    "artifacts": ["scripts/existing.py", "tests/test_existing.py"],
                },
                {
                    "kind": "falsification",
                    "summary": "retest closed family",
                    "novelty_key": "retest-closed-b",
                    "artifacts": ["reports/delta.md"],
                },
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed\n")
        result = validate(self.repo, stamp, self.base, None)
        self.assertTrue(result["role_ready"])
        self.assertEqual(result["outcome"], "BLOCKER_REMOVED_AND_RETESTED")
        self.assertFalse(result["strategy_advanced"])

    def test_blocker_without_retest_experiment_fails(self):
        stamp = "2026-01-01T0201ab"
        self._handoff(
            stamp,
            outcome="BLOCKER_REMOVED_AND_RETESTED",
            retest_decision="FAMILY_CLOSED",
            strategy_advancement={"advanced": False, "summary": "claimed retest"},
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "fixed gate only",
                    "novelty_key": "fixed-gate-only",
                    "artifacts": ["scripts/existing.py", "tests/test_existing.py"],
                }
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 2\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed\n")
        with self.assertRaisesRegex(CompoundingError, "dependent experiment"):
            validate(self.repo, stamp, self.base, None)

    def test_strategy_advanced_requires_stage_movement(self):
        stamp = "2026-01-01T0201ac"
        self._handoff(
            stamp,
            outcome="STRATEGY_ADVANCED",
            funnel_stage_before="F1_TRAIN",
            funnel_stage_after="F1_TRAIN",
            strategy_advancement={"advanced": True, "summary": "claimed advance"},
            closed_families=[],
            useful_deltas=[
                {
                    "kind": "candidate",
                    "summary": "candidate moved",
                    "novelty_key": "candidate-moved",
                    "artifacts": ["reports/delta.md"],
                }
            ],
        )
        with self.assertRaisesRegex(CompoundingError, "funnel stage movement"):
            validate(self.repo, stamp, self.base, None)

    def test_strategy_advanced_accepts_stage_move(self):
        stamp = "2026-01-01T0201ad"
        self._handoff(
            stamp,
            outcome="STRATEGY_ADVANCED",
            funnel_stage_before="F1_TRAIN",
            funnel_stage_after="F2_UNTOUCHED_HOLDOUT",
            strategy_advancement={
                "advanced": True,
                "summary": "named candidate survived untouched holdout",
            },
            closed_families=[],
            useful_deltas=[
                {
                    "kind": "candidate",
                    "summary": "candidate moved",
                    "novelty_key": "candidate-moved-ok",
                    "artifacts": ["reports/delta.md"],
                }
            ],
        )
        result = validate(self.repo, stamp, self.base, None)
        self.assertTrue(result["strategy_advanced"])
        self.assertEqual(result["funnel_stage_after"], "F2_UNTOUCHED_HOLDOUT")

    def test_evidence_wait_requires_wake_condition_and_rejects_capability_laundering(self):
        stamp = "2026-01-01T0201ae"
        self._handoff(
            stamp,
            outcome="EVIDENCE_WAIT",
            useful_deltas=[],
            search_information={"summary": "waiting", "delta_kinds": []},
            strategy_advancement={"advanced": False, "summary": "waiting"},
            closed_families=[],
            data_dependencies=["need future RTH session"],
            evidence_wake_condition="",
            next="wait for RTH",
        )
        with self.assertRaisesRegex(CompoundingError, "evidence_wake_condition"):
            validate(self.repo, stamp, self.base, None)

        self._handoff(
            stamp,
            outcome="EVIDENCE_WAIT",
            strategy_advancement={"advanced": False, "summary": "waiting"},
            closed_families=[],
            data_dependencies=["need future RTH session"],
            evidence_wake_condition="next RTH open",
            next="wait for RTH",
            useful_deltas=[
                {
                    "kind": "capability",
                    "summary": "tool only",
                    "novelty_key": "wait-tool-only",
                    "artifacts": ["scripts/existing.py", "tests/test_existing.py"],
                }
            ],
        )
        (self.repo / "scripts" / "existing.py").write_text("VALUE = 3\n")
        (self.repo / "tests" / "test_existing.py").write_text("# changed again\n")
        with self.assertRaisesRegex(CompoundingError, "capability-only"):
            validate(self.repo, stamp, self.base, None)

    def test_repaired_critic_finding_requires_existing_changed_machinery_and_tests(self):
        stamp = "2026-01-01T0201c"
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
                    "kind": "falsification",
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

    def test_legacy_capability_does_not_count_as_strategy_advanced(self):
        legacy = {"schema_version": 1, "outcome": "CAPABILITY"}
        candidate = {"schema_version": 1, "outcome": "CANDIDATE"}
        self.assertFalse(strategy_advanced(legacy))
        self.assertTrue(strategy_advanced(candidate))
        self.assertTrue(
            strategy_advanced(
                {
                    "schema_version": 2,
                    "outcome": "BLOCKER_REMOVED_AND_RETESTED",
                    "retest_decision": "STRATEGY_ADVANCED",
                }
            )
        )

    def test_three_no_advance_wakes_force_burst_stop(self):
        for stamp in ("2026-01-01T0000", "2026-01-01T0100", "2026-01-01T0200"):
            run, _ = self._handoff(stamp, loop_signature=f"sig-{stamp}")
            self._git("add", str(run.relative_to(self.repo)))
            self._git("commit", "-m", stamp)
            self._git("push", "origin", "main")
        result = build_context(
            self.repo, "2026-01-01T0300", self.repo / "reports" / "current" / "orientation.json"
        )
        self.assertEqual(result["consecutive_no_strategy_advance"], 3)
        self.assertTrue(result["strategy_burst_stop_required"])
        self.assertTrue(any("stop the burst" in reason for reason in result["redirect_reasons"]))

    def test_active_search_epoch_resets_burst_stop_and_supersedes_prior_dr(self):
        for stamp in ("2026-01-01T0000", "2026-01-01T0100", "2026-01-01T0200"):
            run, _ = self._handoff(
                stamp,
                loop_signature=f"sig-{stamp}",
                outcome="FAMILY_CLOSED" if stamp != "2026-01-01T0200" else "EVIDENCE_WAIT",
                next="DIMINISHING_RETURNS" if stamp == "2026-01-01T0200" else "continue",
            )
            if stamp == "2026-01-01T0200":
                row = json.loads((run / "compounding.json").read_text())
                row["outcome"] = "DIMINISHING_RETURNS"
                # schema v2 doesn't allow DIMINISHING_RETURNS for new handoffs, but
                # orientation still reads historical schema-1 style stops; force v1.
                row["schema_version"] = 1
                row.pop("strategy_advancement", None)
                row.pop("economic_mechanism", None)
                (run / "compounding.json").write_text(json.dumps(row) + "\n")
            self._git("add", str(run.relative_to(self.repo)))
            self._git("commit", "-m", stamp)
            self._git("push", "origin", "main")
        epoch_path = self.repo / "configs" / "search_epoch.json"
        epoch_path.parent.mkdir(parents=True, exist_ok=True)
        epoch_path.write_text(
            json.dumps(
                {
                    "epoch_id": "test-epoch",
                    "status": "active",
                    "started_stamp": "2026-01-01T0300",
                    "reassessment_complete": True,
                    "discovery_bar": {"purpose": "signal", "cannot_earn_L1_or_capital_seat": True},
                    "capital_seat_bar": {"max_loss_usd_one_lot": 300, "window_max_dd_usd": 75},
                }
            )
            + "\n"
        )
        result = build_context(
            self.repo, "2026-01-01T0400", self.repo / "reports" / "current" / "orientation.json"
        )
        self.assertEqual(result["epoch_record_count"], 0)
        self.assertEqual(result["consecutive_no_strategy_advance"], 0)
        self.assertFalse(result["strategy_burst_stop_required"])
        self.assertFalse(result["strategy_pivot_required"])
        self.assertEqual(result["search_epoch"]["epoch_id"], "test-epoch")
        self.assertTrue(result["search_epoch"]["reassessment_complete"])
        self.assertTrue(any("superseded by completed search-design" in r for r in result["redirect_reasons"]))
        self.assertFalse(any("last completed wake declared DIMINISHING_RETURNS" in r for r in result["redirect_reasons"]))
        self.assertIn("discovery_bar", result)
        self.assertIn("capital_seat_bar", result)


if __name__ == "__main__":
    unittest.main()

"""Focused tests for strategy-first BUILD progress scoreboard."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import trader_build_progress as progress
from scripts.trader_build_compounding import SCHEMA_VERSION


class TraderBuildProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=self.repo, check=True)
        (self.repo / "seed.txt").write_text("seed\n")
        self._git("add", "-A")
        self._git("commit", "-m", "seed")
        self.remote = self.repo.parent / f"{self.repo.name}-remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        self._git("remote", "add", "origin", str(self.remote))
        self._git("push", "-u", "origin", "main")

        self._orig_repo = progress.REPO
        self._orig_moa = progress.MOA
        progress.REPO = self.repo
        progress.MOA = self.repo / "reports" / "trader-wakes" / "moa"
        progress.MOA.mkdir(parents=True)

    def tearDown(self) -> None:
        progress.REPO = self._orig_repo
        progress.MOA = self._orig_moa
        self.tmp.cleanup()

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, text=True, capture_output=True
        ).stdout.strip()

    def _write_complete_stamp(
        self,
        stamp: str,
        *,
        compounding: dict | None,
        contract_version: int = 3,
        integrate: bool = True,
    ) -> Path:
        run = progress.MOA / stamp
        run.mkdir(parents=True, exist_ok=True)
        (run / "executor-exit.txt").write_text("0\n")
        (run / "challenger-exit.txt").write_text("0\n")
        (run / "executor-closeout.md").write_text("# exec\nscore: 4 / 5\n")
        (run / "challenger-critique.md").write_text("# critique\nPASS\n")
        (run / "merged-next-seed.md").write_text("NEXT seed\n")
        (run / "learning-promotion.md").write_text(
            "## VERIFICATION\nok\n\n## DURABLE\nok\n\n## LESSON\nok\n\n## NEXT\none\n"
        )
        (run / "meta.json").write_text(
            json.dumps(
                {
                    "completion_contract_version": contract_version,
                    "executor": {"model": "gpt-test"},
                    "challenger": {"model": "grok-test"},
                }
            )
        )
        if compounding is not None:
            row = dict(compounding)
            row.setdefault("stamp", stamp)
            (run / "compounding.json").write_text(json.dumps(row) + "\n")
        if integrate:
            self._git("add", "-A")
            self._git("commit", "-m", stamp)
            self._git("push", "origin", "main")
        return run

    def test_classify_verdicts_for_schema_v2_outcomes(self) -> None:
        self.assertEqual(
            progress.classify_strategy_verdict(
                complete=True,
                compounding={
                    "schema_version": 2,
                    "outcome": "STRATEGY_ADVANCED",
                    "strategy_advancement": {"advanced": True},
                },
            ),
            progress.VERDICT_BETTER,
        )
        self.assertEqual(
            progress.classify_strategy_verdict(
                complete=True,
                compounding={
                    "schema_version": 2,
                    "outcome": "FAMILY_CLOSED",
                    "strategy_advancement": {"advanced": False},
                },
            ),
            progress.VERDICT_INFORMATIVE,
        )
        self.assertEqual(
            progress.classify_strategy_verdict(
                complete=True,
                compounding={
                    "schema_version": 2,
                    "outcome": "EVIDENCE_WAIT",
                    "strategy_advancement": {"advanced": False},
                },
            ),
            progress.VERDICT_INFORMATIVE,
        )
        self.assertEqual(
            progress.classify_strategy_verdict(
                complete=True,
                compounding={
                    "schema_version": 2,
                    "outcome": "BLOCKER_REMOVED_AND_RETESTED",
                    "retest_decision": "FAMILY_CLOSED",
                    "strategy_advancement": {"advanced": False},
                },
            ),
            progress.VERDICT_INFORMATIVE,
        )
        self.assertEqual(
            progress.classify_strategy_verdict(
                complete=True,
                compounding={
                    "schema_version": 2,
                    "outcome": "BLOCKER_REMOVED_AND_RETESTED",
                    "retest_decision": "STRATEGY_ADVANCED",
                    "strategy_advancement": {"advanced": True},
                },
            ),
            progress.VERDICT_BETTER,
        )
        self.assertEqual(
            progress.classify_strategy_verdict(complete=False, compounding={}),
            progress.VERDICT_THRASH,
        )
        self.assertEqual(
            progress.classify_strategy_verdict(complete=True, compounding={}),
            progress.VERDICT_THRASH,
        )

    def test_legacy_capability_is_informative_not_better(self) -> None:
        self.assertEqual(
            progress.classify_strategy_verdict(
                complete=True,
                compounding={"schema_version": 1, "outcome": "CAPABILITY"},
            ),
            progress.VERDICT_INFORMATIVE,
        )
        self.assertEqual(
            progress.classify_strategy_verdict(
                complete=True,
                compounding={"schema_version": 1, "outcome": "CANDIDATE"},
            ),
            progress.VERDICT_BETTER,
        )

    def test_forbidden_repetition_is_thrash(self) -> None:
        verdict = progress.classify_strategy_verdict(
            complete=True,
            compounding={
                "schema_version": 2,
                "outcome": "FAMILY_CLOSED",
                "loop_signature": "same/loop",
                "strategy_advancement": {"advanced": False},
            },
            prior_loop_signature="same/loop",
            novelty_keys=["already-seen"],
            prior_novelty_keys={"already-seen"},
        )
        self.assertEqual(verdict, progress.VERDICT_THRASH)

    def test_score_stamp_high_process_score_cannot_claim_strategy_advance(self) -> None:
        stamp = "2026-07-14T0100"
        self._write_complete_stamp(
            stamp,
            compounding={
                "schema_version": 1,
                "outcome": "CAPABILITY",
                "loop_signature": "tooling/capability",
                "useful_deltas": [
                    {
                        "kind": "capability",
                        "summary": "tool",
                        "novelty_key": "cap-1",
                        "artifacts": ["seed.txt"],
                    }
                ],
                "closed_families": [],
            },
        )
        row = progress.score_stamp(progress.MOA / stamp)
        self.assertTrue(row["complete"])
        self.assertFalse(row["strategy_advanced"])
        self.assertEqual(row["strategy_verdict"], progress.VERDICT_INFORMATIVE)
        self.assertEqual(row["research_process_score_0_5"], 4)
        self.assertEqual(row["progress_score_0_5"], 4)  # legacy alias
        self.assertIn("strategy_no_advance", row["progress_types"])

    def test_scoreboard_leads_with_zero_advance_not_high_value(self) -> None:
        for i, stamp in enumerate(("2026-07-14T0200", "2026-07-14T0300")):
            self._write_complete_stamp(
                stamp,
                compounding={
                    "schema_version": 1,
                    "outcome": "CAPABILITY",
                    "loop_signature": f"tooling/capability-{i}",
                    "useful_deltas": [
                        {
                            "kind": "capability",
                            "summary": "tool",
                            "novelty_key": f"cap-{i}",
                            "artifacts": ["seed.txt"],
                        }
                    ],
                    "closed_families": [],
                },
            )
        rows = [
            progress.score_stamp(progress.MOA / "2026-07-14T0200"),
            progress.score_stamp(progress.MOA / "2026-07-14T0300"),
        ]
        text = progress.render_scoreboard(rows, all_records=[])
        self.assertIn("Strategy-convergence scorecard", text)
        self.assertIn("Strategy advances (BETTER): **0**", text)
        self.assertIn("INFORMATIVE_BUT_NOT_CLOSER", text)
        self.assertIn("Secondary context (research-process / capability", text)
        self.assertNotIn("High-value runs", text)
        self.assertIn("zero strategy advance", text)
        # Must not lead with avg progress framing as primary closeness.
        self.assertLess(text.index("Strategy-convergence"), text.index("Secondary context"))

    def test_living_candidates_and_streak(self) -> None:
        records = [
            {
                "schema_version": 2,
                "stamp": "a",
                "outcome": "STRATEGY_ADVANCED",
                "candidate_or_family_scope": "pcs-leader",
                "funnel_stage_after": "F1_TRAIN",
                "strategy_advancement": {"advanced": True},
                "closed_families": [],
            },
            {
                "schema_version": 2,
                "stamp": "b",
                "outcome": "FAMILY_CLOSED",
                "candidate_or_family_scope": "dead-family",
                "funnel_stage_after": "F1_TRAIN",
                "strategy_advancement": {"advanced": False},
                "closed_families": ["dead-family"],
            },
            {
                "schema_version": 2,
                "stamp": "c",
                "outcome": "STRATEGY_ADVANCED",
                "candidate_or_family_scope": "pcs-leader",
                "funnel_stage_after": "F2_UNTOUCHED_HOLDOUT",
                "strategy_advancement": {"advanced": True},
                "closed_families": [],
            },
            {
                "schema_version": 1,
                "stamp": "d",
                "outcome": "CAPABILITY",
                "closed_families": [],
            },
        ]
        living = progress.living_strategy_state(records)
        self.assertEqual(living["living_candidate_count"], 1)
        self.assertEqual(living["living_candidates"], ["pcs-leader"])
        self.assertEqual(living["furthest_living_funnel_stage"], "F2_UNTOUCHED_HOLDOUT")
        self.assertEqual(progress.consecutive_no_strategy_advance(records), 1)
        # After closing the living candidate, living empties and streak grows from end.
        records.append(
            {
                "schema_version": 2,
                "stamp": "e",
                "outcome": "FAMILY_CLOSED",
                "strategy_advancement": {"advanced": False},
                "closed_families": ["pcs-leader"],
            }
        )
        living2 = progress.living_strategy_state(records)
        self.assertEqual(living2["living_candidate_count"], 0)
        self.assertIsNone(living2["furthest_living_funnel_stage"])
        self.assertEqual(progress.consecutive_no_strategy_advance(records), 2)
        self.assertEqual(progress.pivot_stop_state(2)["pivot_stop_state"], "strategy_pivot_required")
        self.assertEqual(progress.pivot_stop_state(3)["pivot_stop_state"], "strategy_burst_stop_required")

    def test_better_advance_from_schema_v2_row(self) -> None:
        stamp = "2026-07-14T0400"
        self._write_complete_stamp(
            stamp,
            compounding={
                "schema_version": SCHEMA_VERSION,
                "outcome": "STRATEGY_ADVANCED",
                "loop_signature": "direction/pullback",
                "economic_mechanism": "theta after pullback",
                "candidate_or_family_scope": "mild-pullback-pcs",
                "funnel_stage_before": "F1_TRAIN",
                "funnel_stage_after": "F2_UNTOUCHED_HOLDOUT",
                "strategy_advancement": {
                    "advanced": True,
                    "summary": "train→holdout",
                },
                "useful_deltas": [
                    {
                        "kind": "candidate",
                        "summary": "advanced",
                        "novelty_key": "adv-1",
                        "artifacts": ["seed.txt"],
                    }
                ],
                "closed_families": [],
            },
        )
        row = progress.score_stamp(progress.MOA / stamp)
        self.assertTrue(row["strategy_advanced"])
        self.assertEqual(row["strategy_verdict"], progress.VERDICT_BETTER)
        self.assertEqual(row["funnel_stage_after"], "F2_UNTOUCHED_HOLDOUT")
        self.assertEqual(row["research_process_score_0_5"], 5)


if __name__ == "__main__":
    unittest.main()

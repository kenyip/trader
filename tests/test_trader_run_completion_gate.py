from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import trader_build_progress
from scripts.trader_run_completion_gate import (
    GateError,
    postflight,
    preflight,
    prepare,
    require_manual_report,
)

GATE = Path(__file__).resolve().parents[1] / "scripts" / "trader_run_completion_gate.py"


class TraderRunCompletionGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.remote = root / "remote.git"
        self.repo.mkdir()
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Test Trader")
        self._git("config", "user.email", "trader@example.test")
        (self.repo / "README.md").write_text("seed\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-m", "seed")
        subprocess.run(
            ["git", "init", "--bare", str(self.remote)], check=True, capture_output=True
        )
        self._git("remote", "add", "origin", str(self.remote))
        self._git("push", "-u", "origin", "main")
        self.base = self._git("rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=self.repo, text=True, capture_output=True, check=True
        )
        return proc.stdout.strip()

    def _write_required_artifacts(self, stamp: str) -> None:
        run_dir = self.repo / "reports" / "trader-wakes" / "moa" / stamp
        run_dir.mkdir(parents=True)
        for name in (
            "meta.json",
            "orientation.json",
            "executor-closeout.md",
            "challenger-critique.md",
            "merged-next-seed.md",
        ):
            (run_dir / name).write_text(
                "{}\n" if name.endswith(".json") else f"{name}\n", encoding="utf-8"
            )
        (run_dir / "learning-promotion.md").write_text(
            "## VERIFICATION\nall green\n\n"
            "## DURABLE\ndocs\n\n"
            "## LESSON\nlearned\n\n"
            "## NEXT\none seed\n",
            encoding="utf-8",
        )
        wakes = self.repo / "reports" / "trader-wakes"
        for name in (f"{stamp}-moa-exec.md", f"{stamp}-moa-merge.md", "LATEST.md", "INDEX.md"):
            (wakes / name).write_text(f"{name}\n", encoding="utf-8")
        (run_dir / "compounding.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "stamp": stamp,
                    "loop_signature": "test-loop",
                    "economic_mechanism": "test economic mechanism",
                    "candidate_or_family_scope": "test-family",
                    "funnel_stage_before": "F1_TRAIN",
                    "funnel_stage_after": "F1_TRAIN",
                    "falsifier": "holdout fails absolute gate",
                    "outcome": "FAMILY_CLOSED",
                    "strategy_advancement": {
                        "advanced": False,
                        "summary": "family closed in fixture",
                    },
                    "search_information": {
                        "summary": "fixture falsification residue",
                        "delta_kinds": ["falsification"],
                    },
                    "useful_deltas": [
                        {
                            "kind": "falsification",
                            "summary": "test evidence",
                            "novelty_key": f"test-{stamp}",
                            "artifacts": [f"reports/trader-wakes/{stamp}-moa-exec.md"],
                        }
                    ],
                    "critic_findings": [],
                    "closed_families": ["test-family"],
                    "data_dependencies": [],
                    "next": "one seed",
                    "retest_decision": None,
                    "evidence_wake_condition": "",
                }
            ) + "\n",
            encoding="utf-8",
        )

    def test_preflight_requires_clean_main_synced_to_origin(self) -> None:
        result = preflight(self.repo)
        self.assertTrue(result["ok"])
        self.assertFalse(result["completion"])
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(GateError, "not clean"):
            preflight(self.repo)

    def test_prepare_accepts_complete_staged_run(self) -> None:
        stamp = "2026-07-12T1200"
        branch = f"trader/run-{stamp}"
        self._git("switch", "-c", branch)
        self._write_required_artifacts(stamp)
        self._git("add", "-A")
        result = prepare(self.repo, stamp, self.base, branch)
        self.assertTrue(result["ok"])
        self.assertNotEqual(result["staged_files"], 0)

    def test_prepare_rejects_sensitive_staged_path(self) -> None:
        stamp = "2026-07-12T1201"
        branch = f"trader/run-{stamp}"
        self._git("switch", "-c", branch)
        self._write_required_artifacts(stamp)
        (self.repo / "positions.yaml").write_text("private: true\n", encoding="utf-8")
        self._git("add", "-A")
        with self.assertRaisesRegex(GateError, "sensitive/runtime"):
            prepare(self.repo, stamp, self.base, branch)

    def test_postflight_requires_advanced_clean_pushed_main(self) -> None:
        stamp = "2026-07-12T1202"
        self._write_required_artifacts(stamp)
        self._git("add", "-A")
        self._git("commit", "-m", "complete run")
        self._git("push", "origin", "main")
        run_head = self._git("rev-parse", "HEAD")
        result = postflight(self.repo, stamp, self.base, run_head)
        self.assertTrue(result["integrated"])
        self.assertTrue(result["clean"])
        self.assertEqual(result["head"], result["origin_main"])
        with self.assertRaisesRegex(GateError, "not an ancestor"):
            postflight(self.repo, stamp, self.base, "0" * 40)

    def test_manual_postflight_requires_tracked_report_and_proves_completion(self) -> None:
        report = self.repo / "reports" / "trader-wakes" / "manual.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "## VERIFICATION\ngreen\n\n"
            "## DURABLE\ngate\n\n"
            "## LESSON\nfail closed\n\n"
            "## NEXT\none seed\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(GateError, "not tracked"):
            require_manual_report(self.repo, str(report.relative_to(self.repo)))

        self._git("add", "-A")
        self._git("commit", "-m", "manual infrastructure wake")
        self._git("push", "origin", "main")
        run_head = self._git("rev-parse", "HEAD")
        result = postflight(
            self.repo,
            None,
            self.base,
            run_head,
            report=str(report.relative_to(self.repo)),
        )
        self.assertTrue(result["completion"])
        self.assertEqual(result["mode"], "postflight")
        self.assertEqual(result["completion_kind"], "manual")
        self.assertEqual(result["report"], "reports/trader-wakes/manual.md")

    def test_manual_postflight_rejects_report_unchanged_since_base(self) -> None:
        report = self.repo / "reports" / "trader-wakes" / "old.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "## VERIFICATION\ngreen\n\n"
            "## DURABLE\ngate\n\n"
            "## LESSON\nold\n\n"
            "## NEXT\none seed\n",
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-m", "old report")
        self._git("push", "origin", "main")
        base = self._git("rev-parse", "HEAD")
        (self.repo / "unrelated.txt").write_text("change\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "unrelated run")
        self._git("push", "origin", "main")
        run_head = self._git("rev-parse", "HEAD")
        with self.assertRaisesRegex(GateError, "not added or changed"):
            postflight(
                self.repo,
                None,
                base,
                run_head,
                report=str(report.relative_to(self.repo)),
            )

    def test_only_postflight_can_write_completion_receipt(self) -> None:
        receipt = self.repo / ".cache" / "platform" / "completion" / "manual.json"
        proc = subprocess.run(
            [
                str(GATE),
                "preflight",
                "--repo",
                str(self.repo),
                "--receipt",
                str(receipt.relative_to(self.repo)),
            ],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("only postflight", proc.stdout)
        self.assertFalse(receipt.exists())

    def test_manual_postflight_writes_atomic_completion_receipt(self) -> None:
        report = self.repo / "reports" / "trader-wakes" / "manual.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "## VERIFICATION\ngreen\n\n"
            "## DURABLE\ngate\n\n"
            "## LESSON\nfail closed\n\n"
            "## NEXT\none seed\n",
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-m", "manual infrastructure wake")
        self._git("push", "origin", "main")
        run_head = self._git("rev-parse", "HEAD")
        receipt_rel = ".cache/platform/completion/manual.json"
        proc = subprocess.run(
            [
                str(GATE),
                "postflight",
                "--repo",
                str(self.repo),
                "--report",
                "reports/trader-wakes/manual.md",
                "--base-head",
                self.base,
                "--run-head",
                run_head,
                "--receipt",
                receipt_rel,
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        receipt = json.loads((self.repo / receipt_rel).read_text())
        self.assertEqual(receipt, json.loads(proc.stdout))
        self.assertEqual(receipt["mode"], "postflight")
        self.assertTrue(receipt["completion"])
        self.assertTrue(receipt["clean"])
        self.assertTrue(receipt["integrated"])
        self.assertTrue(receipt["pushed"])

    def test_prepare_rejects_private_key_marker(self) -> None:
        stamp = "2026-07-12T1204"
        branch = f"trader/run-{stamp}"
        self._git("switch", "-c", branch)
        self._write_required_artifacts(stamp)
        (self.repo / "unsafe.txt").write_text(
            "-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n", encoding="utf-8"
        )
        self._git("add", "-A")
        with self.assertRaisesRegex(GateError, "raw secret"):
            prepare(self.repo, stamp, self.base, branch)

    def test_prepare_requires_exactly_one_next_heading(self) -> None:
        stamp = "2026-07-12T1205"
        branch = f"trader/run-{stamp}"
        self._git("switch", "-c", branch)
        self._write_required_artifacts(stamp)
        learning = self.repo / "reports" / "trader-wakes" / "moa" / stamp / "learning-promotion.md"
        learning.write_text(learning.read_text() + "\n## NEXT\nsecond seed\n")
        self._git("add", "-A")
        with self.assertRaisesRegex(GateError, "exactly one"):
            prepare(self.repo, stamp, self.base, branch)

    def test_v2_monitor_completion_requires_learning_integrated_to_origin_main(self) -> None:
        stamp = "2026-07-12T1203"
        run_dir = self.repo / "reports" / "trader-wakes" / "moa" / stamp
        self._write_required_artifacts(stamp)
        (run_dir / "meta.json").write_text(
            json.dumps({"completion_contract_version": 2}), encoding="utf-8"
        )
        (run_dir / "executor-exit.txt").write_text("0\n", encoding="utf-8")
        (run_dir / "challenger-exit.txt").write_text("0\n", encoding="utf-8")

        original_repo = trader_build_progress.REPO
        trader_build_progress.REPO = self.repo
        try:
            self.assertFalse(trader_build_progress.score_stamp(run_dir)["complete"])
            self._git("add", "-A")
            self._git("commit", "-m", "complete v2 run")
            self._git("push", "origin", "main")
            self.assertTrue(trader_build_progress.score_stamp(run_dir)["complete"])
            self.assertTrue(
                trader_build_progress.score_stamp(run_dir.relative_to(self.repo))["complete"]
            )
        finally:
            trader_build_progress.REPO = original_repo


if __name__ == "__main__":
    unittest.main()

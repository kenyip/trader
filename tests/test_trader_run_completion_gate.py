from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import trader_build_progress
from scripts.trader_run_completion_gate import GateError, postflight, preflight, prepare


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
            "executor-closeout.md",
            "challenger-critique.md",
            "merged-next-seed.md",
        ):
            (run_dir / name).write_text(f"{name}\n", encoding="utf-8")
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

    def test_preflight_requires_clean_main_synced_to_origin(self) -> None:
        result = preflight(self.repo)
        self.assertTrue(result["ok"])
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
        result = postflight(self.repo, stamp, self.base)
        self.assertTrue(result["integrated"])
        self.assertTrue(result["clean"])
        self.assertEqual(result["head"], result["origin_main"])

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

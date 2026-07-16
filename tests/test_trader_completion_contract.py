from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class TraderCompletionContractSurfaceTest(unittest.TestCase):
    def test_repo_contract_and_goal_require_shipped_clean_learning(self) -> None:
        agents = (REPO / "AGENTS.md").read_text()
        goal = (REPO / "configs" / "build_lab_free_goal.txt").read_text()
        platform_goal = (REPO / "docs" / "TRADER_PLATFORM_GOAL.md").read_text()
        direct_plan = (REPO / "docs" / "TRADER_DIRECT_TO_PAPER_WATCH_PLAN.md").read_text()
        for token in ("RUN COMPLETE", "full-suite", "integrated into `main`", "Learning is promoted"):
            self.assertIn(token, agents)
        for token in ("deterministic completion gate", "durable learning", "RUN COMPLETE"):
            self.assertIn(token, goal)
        for token in (
            "TRADER_DIRECT_TO_PAPER_WATCH_PLAN.md",
            "cheap batch candidate screening",
            "reusable option payoff validators",
            "patient opportunity watcher",
            "Strategy Discovery Engine handoff",
            "NO_QUALIFIED_STRATEGY",
        ):
            self.assertIn(token, goal)
        for token in (
            "cheap batch screen → selected candidate deep validation → reusable payoff map → patient watcher → paper packet",
            "NO_QUALIFIED_STRATEGY",
            "NO_SETUP",
            "PAPER_PACKET_READY",
            "live limit orders remain behind paper evidence",
        ):
            self.assertIn(token, platform_goal + direct_plan)

    def test_all_moa_entrypoints_share_fail_closed_build_orchestrator(self) -> None:
        build = (REPO / "scripts" / "trader_build_lab_moa.sh").read_text()
        stress = (REPO / "scripts" / "trader_wake_moa.sh").read_text()
        self.assertNotIn("run_chall || true", build)
        self.assertNotIn("run_chall || true", stress)
        self.assertIn("run_finalize", build)
        self.assertIn("integrate_run", build)
        self.assertIn("validate-handoff", build)
        self.assertNotIn('grep -q "MOA_FINALIZE_READY"', build)
        self.assertIn("exec \"$BUILD_WRAPPER\"", stress)
        self.assertIn("args=()", stress)
        self.assertNotIn("args=(--slot", stress)
        self.assertIn("--finalizer-only", stress)
        self.assertIn("--resume", stress)
        self.assertIn("SMART-RECOVERY", build)
        self.assertIn("append_executor_recovery_guidance", build)
        self.assertIn("has_executor_closeout", build)
        self.assertIn('MAX_EXEC="${MOA_MAX_TURNS_EXEC:-90}"', build)
        self.assertIn("trader_strategy_engine_gate.py", build)
        self.assertIn("STRATEGY_ENGINE_CONTEXT_FILE", build)
        self.assertIn("strategy-engine-handoff.md", build)
        self.assertIn("TRADER_STRATEGY_ENGINE_GATE_BYPASS", build)

    def test_bootstrap_does_not_overwrite_evolved_profile_contract(self) -> None:
        bootstrap = (REPO / "scripts" / "bootstrap_trader_profile.sh").read_text()
        protected = (
            '${PROFILE_DIR}/SOUL.md',
            '${PROFILE_DIR}/skills/trading/trader-self-evolution/SKILL.md',
            '${PROFILE_DIR}/workspace/AGENTS.md',
            '${PROFILE_DIR}/memories/MEMORY.md',
            '${PROFILE_DIR}/memories/USER.md',
            '${PROFILE_DIR}/skills/trading/trading-partner/SKILL.md',
        )
        for path in protected:
            self.assertIn(f'if [[ ! -f "{path}" ]]', bootstrap)

    def test_bootstrap_preserves_existing_profile_surfaces_in_fake_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile = home / ".hermes" / "profiles" / "trader"
            protected = (
                profile / "SOUL.md",
                profile / "skills" / "trading" / "trader-self-evolution" / "SKILL.md",
                profile / "skills" / "trading" / "trading-partner" / "SKILL.md",
                profile / "workspace" / "AGENTS.md",
                profile / "memories" / "MEMORY.md",
                profile / "memories" / "USER.md",
            )
            for path in protected:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"EVOLVED:{path.name}\n", encoding="utf-8")
            (profile / "config.yaml").write_text(
                "platform_toolsets:\n  cli: []\n", encoding="utf-8"
            )
            fake_bin = home / "bin"
            fake_bin.mkdir()
            hermes = fake_bin / "hermes"
            hermes.write_text(
                "#!/bin/sh\n"
                "case \"$*\" in\n"
                "  \"profile list\") echo trader ;;\n"
                "  *\"skills list\"*) echo pmcc-strategy ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            hermes.chmod(0o755)
            before = {path: path.read_bytes() for path in protected}
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = f"{fake_bin}:{REPO / '.venv' / 'bin'}:{env['PATH']}"
            subprocess.run(
                ["bash", str(REPO / "scripts" / "bootstrap_trader_profile.sh")],
                cwd=REPO,
                env=env,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertEqual(before, {path: path.read_bytes() for path in protected})
            canonical = profile / "scripts" / "trader-build-lab-canonical.sh"
            self.assertIn(
                f'exec bash "{REPO}/scripts/trader_build_lab_moa.sh"',
                canonical.read_text(),
            )
            for wrapper in profile.joinpath("scripts").glob("trader*build*lab*.sh"):
                if wrapper == canonical:
                    continue
                body = wrapper.read_text()
                self.assertIn(f'exec "{canonical}"', body)
                self.assertNotIn("--goal", body)
                self.assertNotIn("--slot", body)

    def test_stress_adapter_forwards_recovery_to_build_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copy2(REPO / "scripts" / "trader_wake_moa.sh", scripts / "trader_wake_moa.sh")
            wrapper = scripts / "trader_build_lab_moa.sh"
            wrapper.write_text(
                "#!/bin/sh\nprintf '%s\n' \"$@\"\n", encoding="utf-8"
            )
            wrapper.chmod(0o755)
            proc = subprocess.run(
                [
                    "bash", str(scripts / "trader_wake_moa.sh"),
                    "--hyps", "id1,id2", "--stamp", "test-stamp", "--resume",
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertNotIn("manual-stress", proc.stdout)
            self.assertIn("id1,id2", proc.stdout)
            self.assertIn("test-stamp", proc.stdout)
            self.assertIn("--resume", proc.stdout)

    def test_zero_input_build_front_door_loads_exact_canonical_goal(self) -> None:
        env = os.environ.copy()
        env["TRADER_BUILD_CONTEXT_ONLY"] = "1"
        proc = subprocess.run(
            ["just", "trader-build-lab"],
            cwd=REPO,
            env=env,
            check=True,
            text=True,
            capture_output=True,
        )
        expected = (REPO / "configs" / "build_lab_free_goal.txt").read_text().strip()
        assembled = proc.stdout.split("--- CANONICAL GOAL ---\n", 1)[1].split(
            "\n--- END GOAL ---", 1
        )[0]
        self.assertEqual(expected, assembled)
        self.assertIn("goal_source=canonical", proc.stdout)
        self.assertIn("context_source=auto", proc.stdout)
        self.assertIn("strategy_engine_gate=skipped_context_only", proc.stdout)
        self.assertNotIn("BUILD LAB (", assembled)
        wrapper = (REPO / "scripts" / "trader_build_lab_moa.sh").read_text()
        for surface in (
            "docs/TRADER_PLATFORM_GOAL.md",
            "docs/TRADER_LOOPS.md",
            "docs/AGENTIC_AUTONOMY_POLICY.md",
            "docs/GO_LIVE_READINESS.md",
            "reports/trader-wakes/LATEST.md",
            "reports/readiness/LATEST.md",
            "hypothesis registry, learn/evolve audits",
            "market/session state",
        ):
            self.assertIn(surface, wrapper)


    def test_zero_input_interrupted_branch_auto_resumes_without_strategy_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "configs").mkdir()
            shutil.copy2(
                REPO / "scripts" / "trader_build_lab_moa.sh",
                root / "scripts" / "trader_build_lab_moa.sh",
            )
            shutil.copy2(
                REPO / "configs" / "build_lab_free_goal.txt",
                root / "configs" / "build_lab_free_goal.txt",
            )
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "switch", "-c", "trader/run-2026-01-02T0304"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            env = os.environ.copy()
            env["TRADER_BUILD_CONTEXT_ONLY"] = "1"
            proc = subprocess.run(
                ["bash", str(root / "scripts" / "trader_build_lab_moa.sh")],
                cwd=root,
                env=env,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("mode=resume", proc.stdout)
            self.assertIn("stamp=2026-01-02T0304", proc.stdout)
            self.assertIn("AUTO-RECOVERY", proc.stderr)

    def test_committed_interrupted_run_recovers_without_regenerating_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            remote = Path(tmp) / "remote.git"
            (root / "scripts").mkdir(parents=True)
            (root / "configs").mkdir()
            (root / ".venv" / "bin").mkdir(parents=True)
            shutil.copy2(REPO / "scripts" / "trader_build_lab_moa.sh", root / "scripts" / "trader_build_lab_moa.sh")
            shutil.copy2(REPO / "configs" / "build_lab_free_goal.txt", root / "configs" / "build_lab_free_goal.txt")
            for name in ("trader_run_completion_gate.py", "trader_build_compounding.py"):
                fake = root / "scripts" / name
                fake.write_text("#!/usr/bin/env python3\nprint('{\"ok\": true}')\n")
                fake.chmod(0o755)
            (root / ".gitignore").write_text(".cache/\n")
            fake_python = root / ".venv" / "bin" / "python"
            fake_python.write_text("#!/bin/sh\nexit 0\n")
            fake_python.chmod(0o755)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
            base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=root, check=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=root, check=True, capture_output=True)
            stamp = "2026-01-02T0405"
            branch = f"trader/run-{stamp}"
            subprocess.run(["git", "switch", "-c", branch], cwd=root, check=True, capture_output=True)
            run = root / "reports" / "trader-wakes" / "moa" / stamp
            run.mkdir(parents=True)
            (run / "meta.json").write_text(json.dumps({"base_head": base, "run_branch": branch, "goal": "goal", "goal_source": "canonical", "context": "weekend", "context_source": "auto"}) + "\n")
            (run / "compounding.json").write_text("{}\n")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "completed run commit"], cwd=root, check=True, capture_output=True)
            proc = subprocess.run(
                ["bash", str(root / "scripts" / "trader_build_lab_moa.sh")],
                cwd=root,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
            self.assertIn("committed run detected", proc.stderr)
            self.assertIn("RUN COMPLETE", proc.stdout)
            self.assertEqual(
                subprocess.run(["git", "branch", "--show-current"], cwd=root, check=True, text=True, capture_output=True).stdout.strip(),
                "main",
            )
            self.assertEqual(
                subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, text=True, capture_output=True).stdout,
                "",
            )

    def test_goal_and_slot_overrides_remain_debuggable(self) -> None:
        env = os.environ.copy()
        env["TRADER_BUILD_CONTEXT_ONLY"] = "1"
        proc = subprocess.run(
            [
                "bash", str(REPO / "scripts" / "trader_build_lab_moa.sh"),
                "--goal", "diagnostic override", "--slot", "replay",
            ],
            cwd=REPO,
            env=env,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertIn("goal_source=override", proc.stdout)
        self.assertIn("context=replay", proc.stdout)
        self.assertIn("context_source=override", proc.stdout)
        self.assertIn("--- CANONICAL GOAL ---\ndiagnostic override\n", proc.stdout)

    def test_integrate_only_recovery_mode_is_parseable(self) -> None:
        env = os.environ.copy()
        env["TRADER_BUILD_CONTEXT_ONLY"] = "1"
        proc = subprocess.run(
            [
                "bash", str(REPO / "scripts" / "trader_build_lab_moa.sh"),
                "--integrate-only", "--stamp", "2026-01-02T0405",
            ],
            cwd=REPO,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("mode=integrate-only", proc.stdout)
        self.assertIn("stamp=2026-01-02T0405", proc.stdout)

    def test_bootstrap_cron_compatibility_names_converge_without_judgment(self) -> None:
        bootstrap = (REPO / "scripts" / "bootstrap_trader_profile.sh").read_text()
        names = (
            "trader-build-lab-premarket.sh",
            "trader-build-lab-postclose.sh",
            "trader-build-lab-daily.sh",
            "trader-build-lab-evening.sh",
            "trader-build-lab-weekend.sh",
            "trader-build-lab-weekly.sh",
            "trader-build-lab-midday.sh",
            "trader-build-lab-overnight.sh",
            "trader-build-lab-free-explore.sh",
            "trader_build_lab_cron.sh",
        )
        for name in names:
            self.assertIn(name, bootstrap)
        managed = bootstrap.split("# Canonical zero-input BUILD wake.", 1)[1].split(
            'hermes -p "${PROFILE}" config set terminal.cwd', 1
        )[0]
        self.assertIn('exec bash "${REPO_DIR}/scripts/trader_build_lab_moa.sh"', managed)
        self.assertIn('exec "${PROFILE_BUILD_CANONICAL}"', managed)
        self.assertNotIn("--goal", managed)
        self.assertNotIn("--slot", managed)

    def test_claude_points_to_current_suite_and_contract(self) -> None:
        claude = (REPO / "CLAUDE.md").read_text()
        self.assertIn("Read `AGENTS.md` first", claude)
        self.assertIn("python -m unittest discover -s tests", claude)
        self.assertNotIn("There is **no unit-test suite**", claude)


if __name__ == "__main__":
    unittest.main()

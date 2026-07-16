from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.trader_strategy_engine_gate import run_gate, StrategyEngineGateError


REPO = Path(__file__).resolve().parents[1]


def _report(**overrides):
    survivor = {
        "route_id": "r_edge",
        "family": "sector_event_drift",
        "status": "F1_TRAIN_SURVIVOR",
        "rank": 1,
        "evidence_class": "proxy_underlying_f0",
        "metrics": {
            "n_train_events": 24,
            "paired_excess_mean": 0.012,
            "lower_bound": 0.003,
            "hit_rate": 0.71,
            "worst_decile_tail": -0.011,
            "cost_per_event": 0.001,
        },
        "holdout": {
            "event_count": 4,
            "control_count": 4,
            "identity_hash": "abc123",
            "dates": ["2025-01-01"],
            "symbols": ["SPY"],
        },
        "promotion_blocked": ["l1", "shadow", "broker", "funding", "arm", "live"],
    }
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "engine_git_sha": "a" * 40,
        "trader_git_sha": "b" * 40,
        "manifest_sha256": "c" * 64,
        "panel_sha256": "d" * 64,
        "route_count": 1,
        "status": "NEXT_SURVIVOR",
        "engine_version": "0.1.0",
        "authority": {
            "paper": False,
            "shadow": False,
            "broker": False,
            "funding": False,
            "arm": False,
            "live": False,
            "l1": False,
        },
        "survivors": [survivor],
    }
    report.update(overrides)
    return report


class StrategyEngineHandoffGateTest(unittest.TestCase):
    def _repo_with_config(self, report: dict | None = None):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "configs").mkdir()
        (root / ".cache" / "strategy-engine").mkdir(parents=True)
        routes = root / "routes.json"
        panel = root / "panel.csv"
        routes.write_text(json.dumps({"routes": [{"id": "r_edge"}]}), encoding="utf-8")
        panel.write_text("date,split,route_id,is_event,is_control,event_return,control_return,symbol\n", encoding="utf-8")
        (root / ".gitignore").write_text(".cache/\n", encoding="utf-8")
        cfg = {
            "schema_version": 1,
            "required_for_new_build": True,
            "engine_repo": str(root),
            "report_path": ".cache/strategy-engine/latest.json",
            "allowed_statuses": ["NEXT_SURVIVOR"],
            "block_statuses": ["NO_QUALIFIED_STRATEGY"],
            "report_schema_version": 1,
            "require_provenance": True,
            "max_report_age_seconds": 21600,
        }
        (root / "configs" / "strategy_engine_handoff.json").write_text(json.dumps(cfg), encoding="utf-8")
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
        if report is not None:
            report["engine_git_sha"] = head
            report["trader_git_sha"] = head
            report["manifest_sha256"] = hashlib.sha256(routes.read_bytes()).hexdigest()
            report["panel_sha256"] = hashlib.sha256(panel.read_bytes()).hexdigest()
            report["provenance"] = {"routes_path": str(routes), "panel_path": str(panel)}
            (root / ".cache" / "strategy-engine" / "latest.json").write_text(json.dumps(report), encoding="utf-8")
        return td, root

    def test_next_survivor_writes_context_and_receipt(self):
        td, root = self._repo_with_config(_report())
        with td:
            out_md = root / ".cache" / "handoff.md"
            out_json = root / ".cache" / "handoff.json"
            receipt = run_gate(root, "2026-01-02T0304", None, out_md, out_json)
            self.assertEqual(receipt["gate"], "STRATEGY_ENGINE_NEXT_SURVIVOR")
            self.assertEqual(receipt["selected"]["route_id"], "r_edge")
            self.assertTrue(out_md.exists())
            self.assertTrue(out_json.exists())
            context = out_md.read_text(encoding="utf-8")
            self.assertIn("Strategy Engine Handoff", context)
            self.assertIn("does not grant L1, paper, shadow, broker, funding, arm, or live authority", context)
            self.assertNotIn("event_return", context)

    def test_missing_report_fails_closed(self):
        td, root = self._repo_with_config(None)
        with td:
            with self.assertRaises(StrategyEngineGateError):
                run_gate(root, "stamp", None, None, None)


    def test_missing_provenance_fails_closed(self):
        r = _report()
        del r["generated_at"]
        td, root = self._repo_with_config(r)
        with td:
            with self.assertRaises(StrategyEngineGateError) as ctx:
                run_gate(root, "stamp", None, None, None)
            self.assertIn("generated_at", str(ctx.exception))

    def test_stale_report_fails_closed_before_no_strategy_noop(self):
        r = _report(status="NO_QUALIFIED_STRATEGY", survivors=[])
        r["generated_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
        td, root = self._repo_with_config(r)
        with td:
            with self.assertRaises(StrategyEngineGateError) as ctx:
                run_gate(root, "stamp", None, None, None)
            self.assertIn("stale", str(ctx.exception))

    def test_no_qualified_strategy_blocks_launch(self):
        td, root = self._repo_with_config({**_report(), "status": "NO_QUALIFIED_STRATEGY", "survivors": []})
        with td:
            with self.assertRaises(StrategyEngineGateError) as ctx:
                run_gate(root, "stamp", None, None, None)
            self.assertIn("NO_QUALIFIED_STRATEGY", str(ctx.exception))

    def test_no_qualified_strategy_blocks_launch_after_authority_check(self):
        report = {**_report(), "status": "NO_QUALIFIED_STRATEGY", "survivors": []}
        report["authority"]["paper"] = True
        td, root = self._repo_with_config(report)
        with td:
            with self.assertRaises(StrategyEngineGateError) as ctx:
                run_gate(root, "stamp", None, None, None)
            self.assertIn("authority", str(ctx.exception))

    def test_authority_positive_fails_closed(self):
        r = _report()
        r["authority"]["paper"] = True
        td, root = self._repo_with_config(r)
        with td:
            with self.assertRaises(StrategyEngineGateError) as ctx:
                run_gate(root, "stamp", None, None, None)
            self.assertIn("authority", str(ctx.exception))

    def test_holdout_outcome_leak_fails_closed(self):
        r = _report()
        r["survivors"][0]["holdout"]["event_return"] = 0.99
        td, root = self._repo_with_config(r)
        with td:
            with self.assertRaises(StrategyEngineGateError) as ctx:
                run_gate(root, "stamp", None, None, None)
            self.assertIn("holdout", str(ctx.exception))

    def test_build_wrapper_blocks_missing_report_before_branch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts").mkdir()
            (root / "configs").mkdir()
            shutil.copy2(REPO / "scripts" / "trader_build_lab_moa.sh", root / "scripts" / "trader_build_lab_moa.sh")
            shutil.copy2(REPO / "scripts" / "trader_strategy_engine_gate.py", root / "scripts" / "trader_strategy_engine_gate.py")
            shutil.copy2(REPO / "configs" / "build_lab_free_goal.txt", root / "configs" / "build_lab_free_goal.txt")
            shutil.copy2(REPO / "configs" / "strategy_engine_handoff.json", root / "configs" / "strategy_engine_handoff.json")
            (root / ".gitignore").write_text(".cache/\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
            proc = subprocess.run(
                ["bash", str(root / "scripts" / "trader_build_lab_moa.sh")],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("STRATEGY_ENGINE_GATE_FAILED", proc.stderr)
            branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
            self.assertEqual(branch, "main")
            self.assertEqual(subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, text=True, capture_output=True).stdout, "")


    def test_build_wrapper_no_qualified_strategy_exits_noop_before_branch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts").mkdir()
            (root / "configs").mkdir()
            (root / ".cache" / "strategy-engine").mkdir(parents=True)
            shutil.copy2(REPO / "scripts" / "trader_build_lab_moa.sh", root / "scripts" / "trader_build_lab_moa.sh")
            shutil.copy2(REPO / "scripts" / "trader_strategy_engine_gate.py", root / "scripts" / "trader_strategy_engine_gate.py")
            shutil.copy2(REPO / "configs" / "build_lab_free_goal.txt", root / "configs" / "build_lab_free_goal.txt")
            routes = root / "routes.json"
            panel = root / "panel.csv"
            routes.write_text(json.dumps({"routes": [{"id": "r_edge"}]}), encoding="utf-8")
            panel.write_text("date,split,route_id,is_event,is_control,event_return,control_return,symbol\n", encoding="utf-8")
            (root / ".gitignore").write_text(".cache/\n", encoding="utf-8")
            (root / "configs" / "strategy_engine_handoff.json").write_text(json.dumps({
                "schema_version": 1,
                "required_for_new_build": True,
                "engine_repo": ".",
                "report_path": ".cache/strategy-engine/latest.json",
                "allowed_statuses": ["NEXT_SURVIVOR"],
                "block_statuses": ["NO_QUALIFIED_STRATEGY"],
            }), encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
            (root / ".cache" / "strategy-engine" / "latest.json").write_text(json.dumps({
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "engine_git_sha": head,
                "trader_git_sha": head,
                "manifest_sha256": hashlib.sha256(routes.read_bytes()).hexdigest(),
                "panel_sha256": hashlib.sha256(panel.read_bytes()).hexdigest(),
                "route_count": 1,
                "provenance": {"routes_path": str(routes), "panel_path": str(panel)},
                "status": "NO_QUALIFIED_STRATEGY",
                "engine_version": "0.1.0",
                "authority": {
                    "paper": False,
                    "shadow": False,
                    "broker": False,
                    "funding": False,
                    "arm": False,
                    "live": False,
                    "l1": False,
                },
                "survivors": [],
            }), encoding="utf-8")
            proc = subprocess.run(
                ["bash", str(root / "scripts" / "trader_build_lab_moa.sh")],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("NO_STRATEGY_STATUS", proc.stderr)
            branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
            self.assertEqual(branch, "main")
            self.assertEqual(subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, text=True, capture_output=True).stdout, "")
            receipts = list((root / ".cache" / "platform" / "strategy-engine-handoff").glob("*.json"))
            self.assertEqual(len(receipts), 1)
            receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(receipt["gate"], "NO_STRATEGY_STATUS")
            self.assertFalse(receipt["launch_allowed"])



if __name__ == "__main__":
    unittest.main()

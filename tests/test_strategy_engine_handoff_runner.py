from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.trader_strategy_engine_handoff import run_handoff


def _git_init_commit(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=path, check=True, capture_output=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StrategyEngineHandoffRunnerTest(unittest.TestCase):
    def _fixture(self, *, status: str = "NEXT_SURVIVOR"):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        trader = root / "trader"
        engine = root / "engine"
        trader.mkdir()
        engine.mkdir()

        pkg = engine / "src" / "strategy_engine"
        pkg.mkdir(parents=True)
        (engine / ".gitignore").write_text("__pycache__/\n*.pyc\nsrc/**/__pycache__/\n", encoding="utf-8")
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        survivors = "[]" if status == "NO_QUALIFIED_STRATEGY" else """[{
            "route_id": "r_edge",
            "family": "sector_event_drift",
            "status": "F1_TRAIN_SURVIVOR",
            "rank": 1,
            "evidence_class": "proxy_underlying_f0",
            "metrics": {"n_train_events": 24, "paired_excess_mean": 0.02, "lower_bound": 0.01, "hit_rate": 0.7},
            "holdout": {"route_id": "r_edge", "event_count": 4, "control_count": 4, "identity_hash": "abc123", "dates": ["2025-01-01"], "symbols": ["SPY"]},
            "promotion_blocked": ["l1", "paper", "shadow", "broker", "funding", "arm", "live"]
        }]"""
        (pkg / "cli.py").write_text(
            f"""
import argparse, json
p=argparse.ArgumentParser()
p.add_argument('--routes', required=True)
p.add_argument('--panel', required=True)
p.add_argument('--out', required=True)
args=p.parse_args()
report={{
  'status': {status!r},
  'engine_version': 'fake-test',
  'authority': {{'paper': False, 'shadow': False, 'broker': False, 'funding': False, 'arm': False, 'live': False, 'l1': False}},
  'survivors': {survivors},
}}
open(args.out, 'w', encoding='utf-8').write(json.dumps(report))
""",
            encoding="utf-8",
        )
        _git_init_commit(engine)

        (trader / "configs").mkdir()
        (trader / "configs" / "strategy_engine_handoff.json").write_text(
            json.dumps({
                "schema_version": 1,
                "required_for_new_build": True,
                "engine_repo": str(engine),
                "report_path": ".cache/strategy-engine/latest.json",
                "allowed_statuses": ["NEXT_SURVIVOR"],
                "block_statuses": ["NO_QUALIFIED_STRATEGY"],
                "report_schema_version": 1,
                "require_provenance": True,
                "max_report_age_seconds": 21600,
            }),
            encoding="utf-8",
        )
        routes = trader / "routes.json"
        panel = trader / "panel.csv"
        routes.write_text(json.dumps({"routes": [{"id": "r_edge"}]}), encoding="utf-8")
        panel.write_text("date,split,route_id,is_event,is_control,event_return,control_return,symbol\n", encoding="utf-8")
        _git_init_commit(trader)
        return td, trader, routes, panel

    def test_runner_writes_provenance_and_validates_next_survivor(self):
        td, trader, routes, panel = self._fixture()
        with td:
            receipt = run_handoff(trader, str(routes), str(panel), None, "test-stamp")
            self.assertEqual(receipt["status"], "NEXT_SURVIVOR")
            self.assertEqual(receipt["gate_status"], "validated_next_survivor")
            report_path = trader / ".cache" / "strategy-engine" / "latest.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["manifest_sha256"], _sha256(routes))
            self.assertEqual(report["panel_sha256"], _sha256(panel))
            self.assertEqual(report["route_count"], 1)
            self.assertTrue(report["engine_git_sha"])
            self.assertTrue(report["trader_git_sha"])
            self.assertTrue(all(v is False for v in report["authority"].values()))

    def test_runner_treats_no_qualified_as_valid_current_handoff(self):
        td, trader, routes, panel = self._fixture(status="NO_QUALIFIED_STRATEGY")
        with td:
            receipt = run_handoff(trader, str(routes), str(panel), None, "test-stamp")
            self.assertEqual(receipt["status"], "NO_QUALIFIED_STRATEGY")
            self.assertEqual(receipt["gate_status"], "validated_no_qualified_strategy")
            report = json.loads((trader / ".cache" / "strategy-engine" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["route_count"], 1)
            self.assertEqual(report["survivors"], [])


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class TraderIncomeCoverageTest(unittest.TestCase):
    def test_session_time_gap_reports_built_rejected_cycle_not_missing_capability(self):
        completed = subprocess.run(
            [
                str(REPO / ".venv" / "bin" / "python"),
                str(REPO / "scripts" / "trader_income_coverage.py"),
                "--json",
                "--no-write",
                "--stamp",
                "test",
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        time_gap = next(
            gap for gap in payload["gaps"] if gap.startswith("time-bucket scoreboard")
        )

        self.assertIn("completed-30-minute", time_gap)
        self.assertIn("0/24 complete train+holdout passes", time_gap)
        self.assertIn("append-safe", time_gap)
        self.assertIn("60 usable", time_gap)
        self.assertIn("1/24 train", time_gap)
        self.assertNotIn("session-time slices missing", time_gap)
        self.assertNotIn("21 dates", time_gap)
        self.assertTrue(payload["quality_leader_hint"].startswith("none; former reference"))


if __name__ == "__main__":
    unittest.main()
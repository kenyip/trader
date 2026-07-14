import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class TraderIncomeCoverageTest(unittest.TestCase):
    def test_session_time_gap_reports_built_rejected_cycle_not_missing_capability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "quotes.csv"
            archive.write_text(
                "observed_at,symbol,expiration,option_type,strike,bid,ask,source,is_observed\n"
                "2026-07-11T15:00:00-04:00,TSLL,2026-07-17,put,10,0.10,0.12,test,true\n"
                "2026-07-13T15:00:00-04:00,TSLL,2026-07-24,put,10,0.11,0.13,test,true\n"
                "2026-07-14T09:31:00-04:00,TSLL,2027-01-15,put,10,0.12,0.14,test,true\n"
                "2026-07-14T09:31:00-04:00,TSLL,2028-01-21,put,10,0.13,0.15,test,true\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    str(REPO / ".venv" / "bin" / "python"),
                    str(REPO / "scripts" / "trader_income_coverage.py"),
                    "--json",
                    "--no-write",
                    "--stamp",
                    "test",
                    "--option-archive",
                    str(archive),
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

        cost_gap = next(
            gap for gap in payload["gaps"] if gap.startswith("cost realism")
        )
        self.assertEqual(payload["option_archive_density"]["n_market_dates"], 3)
        self.assertEqual(
            payload["option_archive_density"]["expirations_by_market_date"]["2026-07-14"],
            ["2027-01-15", "2028-01-21"],
        )
        self.assertIn("current TSLL archive covers 3/3 dates", cost_gap)
        self.assertIn("newest-date expiration breadth is 2 (thin)", cost_gap)
        self.assertIn("three-date floor is plumbing only", cost_gap)
        self.assertNotIn("covers 2/3 dates", cost_gap)


if __name__ == "__main__":
    unittest.main()

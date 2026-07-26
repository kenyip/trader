"""Shadow rehearsal window accounting (no live authority)."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import scripts.trader_shadow_rehearsal as sr


class ShadowRehearsalTest(unittest.TestCase):
    def test_session_days_counts_two_weekdays(self):
        history = [
            {"ts": "2026-07-22T15:00:00+00:00", "n_shadow_log": 1},
            {"ts": "2026-07-23T15:00:00+00:00", "n_shadow_log": 1},
        ]
        days = sr._session_days_from_history(history)
        self.assertIn("2026-07-22", days)
        self.assertIn("2026-07-23", days)
        self.assertGreaterEqual(len(days), 2)

    def test_stub_only_stays_partial(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow_dir = root / "shadow"
            latest = shadow_dir / "LATEST.json"
            history = shadow_dir / "history.jsonl"
            report = root / "SHADOW_REHEARSAL_LATEST.json"
            shadow_dir.mkdir(parents=True)
            history.write_text("")

            fake_tick = {
                "ok": True,
                "n_proposals": 1,
                "results": [
                    {
                        "action": "shadow_log_only",
                        "rh_review": {"places": False},
                    }
                ],
                "broker": "paper",
            }

            with (
                mock.patch.object(sr, "_SHADOW_DIR", shadow_dir),
                mock.patch.object(sr, "_LATEST", latest),
                mock.patch.object(sr, "_HISTORY", history),
                mock.patch.object(sr, "_REPORT", report),
                mock.patch.object(sr, "run_shadow_tick", return_value=fake_tick),
            ):
                out = sr.run_rehearsal(ticks=1, stub=True, min_session_days_for_pass=2)

            self.assertTrue(latest.is_file())
            data = json.loads(latest.read_text())
            self.assertEqual(data["mode"], "shadow_rehearsal")
            self.assertFalse(data["live_authority"])
            self.assertFalse(data["authority_creep"])
            self.assertEqual(data["status"], "PARTIAL")
            self.assertIn("stub", data["detail"].lower())
            self.assertEqual(out["n_history_ticks"], 1)

    def test_non_stub_multi_session_can_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow_dir = root / "shadow"
            latest = shadow_dir / "LATEST.json"
            history = shadow_dir / "history.jsonl"
            report = root / "SHADOW.json"
            shadow_dir.mkdir(parents=True)
            with history.open("w") as f:
                f.write(
                    json.dumps(
                        {
                            "ts": "2026-07-22T15:00:00+00:00",
                            "n_shadow_log": 1,
                            "n_proposals": 1,
                            "stub": False,
                            "authority_creep": False,
                        }
                    )
                    + "\n"
                )

            fake_tick = {
                "ok": True,
                "n_proposals": 1,
                "results": [{"action": "shadow_log_only", "rh_review": {"places": False}}],
            }
            with (
                mock.patch.object(sr, "_SHADOW_DIR", shadow_dir),
                mock.patch.object(sr, "_LATEST", latest),
                mock.patch.object(sr, "_HISTORY", history),
                mock.patch.object(sr, "_REPORT", report),
                mock.patch.object(sr, "run_shadow_tick", return_value=fake_tick),
                mock.patch.object(sr, "_now", return_value="2026-07-23T16:00:00+00:00"),
            ):
                out = sr.run_rehearsal(ticks=1, stub=False, min_session_days_for_pass=2)

            self.assertEqual(out["status"], "PASS")
            self.assertTrue(out["window_complete"])

    def test_authority_creep_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow_dir = root / "shadow"
            latest = shadow_dir / "LATEST.json"
            history = shadow_dir / "history.jsonl"
            report = root / "SHADOW.json"
            shadow_dir.mkdir(parents=True)
            history.write_text("")

            fake_tick = {
                "ok": True,
                "n_proposals": 1,
                "results": [
                    {
                        "action": "live_place",
                        "broker": {"order_id": "x"},
                        "rh_review": {"places": True},
                    }
                ],
            }
            with (
                mock.patch.object(sr, "_SHADOW_DIR", shadow_dir),
                mock.patch.object(sr, "_LATEST", latest),
                mock.patch.object(sr, "_HISTORY", history),
                mock.patch.object(sr, "_REPORT", report),
                mock.patch.object(sr, "run_shadow_tick", return_value=fake_tick),
            ):
                out = sr.run_rehearsal(ticks=1, stub=True)

            self.assertTrue(out["authority_creep"])
            self.assertEqual(out["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()

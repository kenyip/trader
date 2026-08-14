import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trader_platform.research import live_spot
from trader_platform.research.opportunity_watcher import working_paper_symbols


class LiveSpotSourceHonestyTest(unittest.TestCase):
    def tearDown(self) -> None:
        live_spot._MEMO.clear()

    def test_yf_file_is_not_labeled_rh_mcp(self):
        live_spot._MEMO.clear()
        with patch.object(
            live_spot,
            "load_rh_quotes",
            return_value={
                "ok": True,
                "source": "yf_1m",
                "generated_at": "2026-08-14T16:25:11+00:00",
                "symbols": {"INTC": {"last": 103.4, "asof": "2026-08-14T16:25:10+00:00"}},
            },
        ):
            out = live_spot.last_spot("INTC")
        self.assertEqual(out["last"], 103.4)
        self.assertEqual(out["source"], "yf_1m")

    def test_rh_mcp_file_keeps_rh_label(self):
        live_spot._MEMO.clear()
        with patch.object(
            live_spot,
            "load_rh_quotes",
            return_value={
                "ok": True,
                "source": "rh_mcp",
                "generated_at": "2026-08-14T16:25:11+00:00",
                "symbols": {"KO": {"last": 87.7}},
            },
        ):
            out = live_spot.last_spot("KO")
        self.assertEqual(out["source"], "rh_mcp")


class WorkingPaperSymbolsTest(unittest.TestCase):
    def test_reads_working_and_skips_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(
                json.dumps(
                    {
                        "orders": {
                            "a": {"symbol": "INTC", "status": "working", "tag": "spine:x"},
                            "b": {"symbol": "BAC", "status": "closed", "tag": ""},
                            "c": {"symbol": "F", "status": "working", "tag": "m0_stub:smoke_test"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(working_paper_symbols(path), {"INTC"})


class QuoteRefreshWakeTest(unittest.TestCase):
    def test_skips_packet_ready_when_symbol_already_working(self):
        from scripts import trader_quote_refresh as qr

        rows = {"INTC": {"last": 103.4}}
        watcher = {"status": "PAPER_PACKET_READY", "symbol": "INTC"}
        working = [{"symbol": "INTC", "status": "working", "tag": "spine:x"}]
        with patch.object(qr, "_working_orders", return_value=working), patch.object(
            qr, "WATCHER", Path("/tmp/does-not-matter")
        ), patch.object(Path, "exists", return_value=True), patch(
            "scripts.trader_quote_refresh.json.loads", return_value=watcher
        ):
            flags = qr._interest(rows, {})
        self.assertNotIn("INTC:packet_ready", flags)

    def test_rh_blocked_wake_stays_quiet(self):
        from scripts import trader_quote_refresh as qr

        with patch.object(
            qr,
            "_load_interest",
            return_value={"defaults": {"rh_wake": False, "rh_fresh_s": 480}},
        ), patch.object(qr, "_rh_age_s", return_value=None):
            line = qr._write_wake(["INTC:packet_ready"])
        self.assertTrue(line.startswith("quiet"))
        self.assertIn("rh:blocked", line)


if __name__ == "__main__":
    unittest.main()

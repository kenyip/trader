"""Tests for discovery F2 → multi-symbol reprove handoff."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.research import bootstrap as boot
from trader_platform.research import discovery_f2_handoff as h


def _prove_eval(
    *,
    cid: str,
    decision: str = "STRATEGY_ADVANCED_F2",
    stage: str = "F2_UNTOUCHED_HOLDOUT",
    symbols: list[tuple[str, bool, int]] | None = None,
    generated_at: str = "2026-08-06T12:00:00+00:00",
) -> dict:
    rows = []
    for sym, dual, n in symbols or [("AMZN", True, 14), ("INTC", True, 19)]:
        rows.append(
            {
                "symbol": sym,
                "holdout_dual_cost_pass": dual,
                "holdout": {
                    "fixed_0p01": {"n_trades": n, "pnl": 10.0, "ok": True},
                    "slip_5pct": {"n_trades": n, "pnl": 8.0, "ok": True},
                },
            }
        )
    return {
        "candidate_id": cid,
        "family_id": f"FAM__{cid}",
        "decision": decision,
        "funnel_stage_after": stage,
        "generated_at": generated_at,
        "n_holdout_pass": sum(1 for _, d, _ in (symbols or []) if d) or 2,
        "holdout_rows": rows,
        "live_authority": False,
    }


class DiscoveryF2HandoffTests(unittest.TestCase):
    def test_axis_markers(self) -> None:
        cid = "PCS_X__dn_d5_pt30_dl18_iv35_c8_w1_pcs_bu_7"
        self.assertEqual(h.axis_markers(cid), ["dn_d5"])
        self.assertIn("g_d7", h.axis_markers("FOO__g_d7_pt40_x"))

    def test_scan_admits_f2_and_resolves_spec(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "discovery"
            gen = root / "gen_0001_20260806T000000Z"
            gen.mkdir(parents=True)
            cid = "PCS_IV__dn_d5_pt30_dl18_iv35_c8_w1_pcs_bu_7"
            spec = gen / f"{cid}__prove.json"
            spec.write_text(json.dumps({"candidate_id": cid, "symbols": ["AMZN", "INTC"]}), encoding="utf-8")
            ev_path = gen / f"{cid}__prove_eval.json"
            ev_path.write_text(json.dumps(_prove_eval(cid=cid)), encoding="utf-8")
            # non-F2 should be ignored
            bad = gen / "PCS_IV__dn_d5_bad__prove_eval.json"
            bad.write_text(
                json.dumps(_prove_eval(cid="PCS_IV__dn_d5_bad", decision="F0_CLOSED", stage="F0_MECHANISM")),
                encoding="utf-8",
            )
            (gen / "PCS_IV__dn_d5_bad__prove.json").write_text("{}", encoding="utf-8")

            rows = h.scan_discovery_f2_candidates(root, min_generated_at="2026-08-05")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["candidate_id"], cid)
            self.assertTrue(rows[0]["pack_grade_shaped"])
            self.assertTrue(rows[0]["new_axis"])
            self.assertEqual(rows[0]["symbols_proved"], ["AMZN", "INTC"])
            self.assertEqual(Path(rows[0]["spec_path"]), spec.resolve())
            self.assertFalse(rows[0]["capital_path_ok"])

            payload = h.write_discovery_f2_candidates(rows, Path(td) / "out.json", discovery_root=root)
            self.assertEqual(payload["n_pack_grade_shaped"], 1)
            self.assertTrue(Path(payload["report_path"]).is_file())

            items = h.load_discovery_f2_items(Path(td) / "out.json")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["source"], "discovery_f2")

    def test_thin_symbol_not_thick(self) -> None:
        ev = _prove_eval(
            cid="X__dn_d5_thin",
            symbols=[("AMZN", True, 5), ("INTC", True, 19)],
        )
        thick = h.thick_dual_cost_symbols(ev, min_trades_worst_axis=12)
        self.assertEqual(thick, ["INTC"])
        self.assertFalse(len(thick) >= 2)

    def test_load_dna_items_includes_discovery_f2(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cid = "PCS_IV__dn_d5_pt30_dl18_iv35_c8_w1_pcs_bu_2"
            spec = td_path / f"{cid}__prove.json"
            spec.write_text(json.dumps({"candidate_id": cid}), encoding="utf-8")
            surface = td_path / "DISCOVERY_F2_CANDIDATES.json"
            h.write_discovery_f2_candidates(
                [
                    {
                        "candidate_id": cid,
                        "spec_path": str(spec),
                        "symbols_proved": ["AMZN", "INTC"],
                        "pack_grade_shaped": True,
                        "new_axis": True,
                        "axis_markers": ["dn_d5"],
                        "capital_path_ok": False,
                    }
                ],
                surface,
            )
            # Patch default path via explicit load then bootstrap helper
            items = boot.load_dna_items_for_multi_symbol(
                shortlist=[],
                include_seed_specs=False,
                include_discovery_f2=True,
                discovery_f2_path=surface,
            )
            ids = [i.get("candidate_id") for i in items]
            self.assertIn(cid, ids)
            row = next(i for i in items if i.get("candidate_id") == cid)
            self.assertEqual(row.get("source"), "discovery_f2")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from trader_platform.research.living_registry import (
    LivingRegistry,
    LivingSeat,
    load_living_registry,
    save_living_registry,
)
from trader_platform.research.opportunity_watcher import WatchResult, watch_once
from trader_platform.research.pack_grade import (
    is_pack_grade,
    load_quality_pass_cells,
    quality_pass_index,
    watch_sort_key,
)
from trader_platform.research.paper_handoff import run_paper_handoff
from trader_platform.research.promote_paper import promote_pack_grade_to_paper

BU4 = "PCS_BULL_NEUTRAL_INCOME_45D_PT50_V1__dn_d12_pt40_dl14_iv15_c8_w1_pcs_bu_4"
BU6 = "PCS_BULL_NEUTRAL_INCOME_45D_PT50_V1__dn_d5_pt40_dl18_iv15_c6_w1_pcs_bu_6"
NEAR = "PCS_IV_RICH_NONCOLLAPSE_21D_PT50_V1__dn_d14_pt60_dl14_iv30_c10_w1_pcs_bu_4"
ROUTER = "PCS_BULL_NEUTRAL_INCOME_45D_PT50_V1__dn_d14_pt30_dl14_iv40_c10_w1_router_2"


def _write_multi(path: Path, cells: list[dict]) -> Path:
    payload = {
        "generated_at": "2026-08-13T07:14:01+00:00",
        "n_quality_pass": sum(1 for c in cells if c.get("quality_pass")),
        "results": cells,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _seat(seat_id: str, candidate_id: str, symbol: str, status: str = "f2_holdout") -> LivingSeat:
    return LivingSeat(
        seat_id=seat_id,
        candidate_id=candidate_id,
        family_id="F",
        status=status,
        symbols=[symbol],
        router_policy="pcs_non_bear",
    )


class PackGradeMatchKeyTest(unittest.TestCase):
    def test_allow_exact_stem_and_symbol(self):
        cells = [{"candidate_id": BU4, "f2_symbols": ["INTC", "KO"], "quality_pass": True}]
        idx = quality_pass_index(cells)
        self.assertTrue(is_pack_grade(candidate_id=BU4, symbol="INTC", index=idx))
        self.assertTrue(is_pack_grade(candidate_id=BU4, symbol="KO", index=idx))
        self.assertTrue(
            is_pack_grade(seat_id=f"{BU4}_INTC", symbol="INTC", index=idx)
        )

    def test_deny_near_miss_and_router(self):
        cells = [{"candidate_id": BU4, "f2_symbols": ["INTC", "KO"], "quality_pass": True}]
        idx = quality_pass_index(cells)
        self.assertFalse(is_pack_grade(candidate_id=NEAR, symbol="IWM", index=idx))
        self.assertFalse(is_pack_grade(candidate_id=ROUTER, symbol="INTC", index=idx))
        self.assertFalse(is_pack_grade(candidate_id=BU4, symbol="IWM", index=idx))

    def test_missing_multi_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            self.assertEqual(load_quality_pass_cells(missing), [])


class WatcherPackGradePreferenceTest(unittest.TestCase):
    def test_pack_grade_selected_before_legacy_paper_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "reg.json"
            multi = _write_multi(
                Path(tmp) / "multi.json",
                [{"candidate_id": BU4, "f2_symbols": ["INTC", "KO"], "quality_pass": True}],
            )
            reg = LivingRegistry()
            reg.upsert(_seat(f"{NEAR}_IWM", NEAR, "IWM", "paper_eligible"))
            reg.upsert(_seat(f"{ROUTER}_INTC", ROUTER, "INTC", "f2_holdout"))
            reg.upsert(_seat(f"{BU4}_INTC", BU4, "INTC", "f2_holdout"))
            save_living_registry(reg, reg_path)
            row = pd.Series(
                {"close": 40.0, "iv_proxy": 0.4, "iv_rank": 20.0, "regime": "bullish"}
            )
            with patch(
                "trader_platform.research.opportunity_watcher._latest_bar",
                return_value=(row, pd.Timestamp("2026-08-13")),
            ), patch(
                "trader_platform.research.pack_grade.load_quality_pass_cells",
                return_value=load_quality_pass_cells(multi),
            ), patch(
                "trader_platform.research.opportunity_watcher.working_paper_symbols",
                return_value=set(),
            ):
                result = watch_once(registry_path=reg_path)
            self.assertEqual(result.status, "PAPER_PACKET_READY")
            self.assertEqual(result.candidate_id, BU4)
            self.assertEqual(result.symbol, "INTC")
            self.assertTrue(result.seats_considered[0].endswith("_INTC"))
            self.assertIn(BU4, result.seats_considered[0])

    def test_pack_grade_no_setup_does_not_fall_through_to_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "reg.json"
            multi = _write_multi(
                Path(tmp) / "multi.json",
                [{"candidate_id": BU4, "f2_symbols": ["INTC", "KO"], "quality_pass": True}],
            )
            reg = LivingRegistry()
            reg.upsert(_seat(f"{ROUTER}_INTC", ROUTER, "INTC", "paper_eligible"))
            pack_seat = _seat(f"{BU4}_INTC", BU4, "INTC", "paper_eligible")
            pack_seat.router_policy = "pcs_bull_only"
            reg.upsert(pack_seat)
            save_living_registry(reg, reg_path)
            row = pd.Series(
                {"close": 40.0, "iv_proxy": 0.4, "iv_rank": 20.0, "regime": "bearish"}
            )
            with patch(
                "trader_platform.research.opportunity_watcher._latest_bar",
                return_value=(row, pd.Timestamp("2026-08-13")),
            ), patch(
                "trader_platform.research.pack_grade.load_quality_pass_cells",
                return_value=load_quality_pass_cells(multi),
            ), patch(
                "trader_platform.research.opportunity_watcher.working_paper_symbols",
                return_value=set(),
            ):
                result = watch_once(registry_path=reg_path)
            self.assertEqual(result.status, "NO_SETUP")
            self.assertNotEqual(result.candidate_id, ROUTER)
            self.assertTrue(all(ROUTER not in sid for sid in result.seats_considered))

    def test_sort_key_near_miss_not_tier_zero(self):
        idx = quality_pass_index(
            [{"candidate_id": BU4, "f2_symbols": ["INTC", "KO"]}]
        )
        near = _seat(f"{NEAR}_IWM", NEAR, "IWM", "paper_eligible")
        pack = _seat(f"{BU4}_KO", BU4, "KO", "f2_holdout")
        self.assertEqual(watch_sort_key(pack, idx)[0], 0)
        self.assertEqual(watch_sort_key(near, idx)[0], 1)


class HandoffPackGradeGateTest(unittest.TestCase):
    def test_non_pack_ready_watch_fail_closed_when_multi_exists(self):
        cells = [{"candidate_id": BU4, "f2_symbols": ["INTC", "KO"], "quality_pass": True}]
        watch = WatchResult(
            status="PAPER_PACKET_READY",
            generated_at="2026-08-13T00:00:00+00:00",
            seat_id=f"{ROUTER}_INTC",
            candidate_id=ROUTER,
            symbol="INTC",
            selected_structure="call_credit_spread",
            packet={},
        )
        with patch(
            "trader_platform.research.paper_handoff.load_quality_pass_cells",
            return_value=cells,
        ):
            result = run_paper_handoff(watch=watch)
        self.assertEqual(result.status, "CANDIDATE_NOT_PACK_GRADE")
        self.assertEqual(result.paper_action, "candidate_not_pack_grade")

    def test_missing_multi_does_not_invent_gate(self):
        watch = WatchResult(
            status="NO_QUALIFIED_STRATEGY",
            generated_at="2026-08-13T00:00:00+00:00",
            reason="none",
        )
        with patch(
            "trader_platform.research.paper_handoff.load_quality_pass_cells",
            return_value=[],
        ):
            result = run_paper_handoff(watch=watch)
        self.assertEqual(result.status, "NO_QUALIFIED_STRATEGY")


class PromotePackGradeTest(unittest.TestCase):
    def test_promotes_exact_cells_and_demotes_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "reg.json"
            multi = _write_multi(
                Path(tmp) / "multi.json",
                [
                    {"candidate_id": BU4, "f2_symbols": ["INTC", "KO"], "quality_pass": True},
                    {"candidate_id": BU6, "f2_symbols": ["INTC", "PLTR"], "quality_pass": True},
                ],
            )
            reg = LivingRegistry()
            reg.upsert(_seat(f"{BU4}_INTC", BU4, "INTC"))
            reg.upsert(_seat(f"{BU4}_KO", BU4, "KO"))
            reg.upsert(_seat(f"{BU6}_PLTR", BU6, "PLTR"))
            reg.upsert(_seat(f"{NEAR}_IWM", NEAR, "IWM", "paper_eligible"))
            save_living_registry(reg, reg_path)
            out = promote_pack_grade_to_paper(registry_path=reg_path, multi_path=multi)
            self.assertEqual(out["n_promoted"], 3)
            self.assertEqual(out["n_demoted"], 1)
            reloaded = load_living_registry(reg_path)
            statuses = {s.seat_id: s.status for s in reloaded.seats}
            self.assertEqual(statuses[f"{BU4}_INTC"], "paper_eligible")
            self.assertEqual(statuses[f"{NEAR}_IWM"], "f2_holdout")


if __name__ == "__main__":
    unittest.main()

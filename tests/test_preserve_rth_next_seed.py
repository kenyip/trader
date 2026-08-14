"""Campaign must not erase RTH NEXT_SEED marks."""

from __future__ import annotations

import json
from pathlib import Path

from trader_platform.execution.preserve_rth_next_seed import (
    apply_preserve,
    merge_preserved_seed,
    seed_is_thin,
)


def _campaign_seed() -> dict:
    return {
        "source": "trader_paper_campaign",
        "stamp": "20260814T220043",
        "ken_required": False,
        "next_action": "manage_open_paper_campaign",
        "detail": {
            "hint": "RTH: mark/manage paper; learn_tick; stand-aside if no new capital-fit OPEN_*",
            "open_orders": [
                {
                    "order_id": "paper_b5b969c4a65f",
                    "symbol": "INTC",
                    "structure": "iron_condor",
                    "status": "working",
                    "max_loss_usd": 188.72,
                }
            ],
        },
    }


def _rich_seed() -> dict:
    return {
        "source": "rth_eval_20260814T1242",
        "stamp": "20260814T1242",
        "ken_required": False,
        "next_action": "manage_open_paper_campaign",
        "detail": {
            "hint": "HOLD INTC IC until dual RH adjacent-ask >= PT",
            "f_ic": {"miss": "put_wing_none_after_further_rip", "spot": 14.38},
            "pack": {"KO": "pcs_bull_only:neutral", "PLTR": "pcs_bull_only:neutral"},
            "open_orders": [
                {
                    "order_id": "paper_b5b969c4a65f",
                    "symbol": "INTC",
                    "decision": "HOLD",
                    "spot": 102.87,
                    "mtm_usd": 24.78,
                    "mtm_adverse_usd": 8.28,
                    "pt_usd": 18.38,
                    "dual_pt_ready": False,
                }
            ],
        },
    }


def test_campaign_seed_is_thin_and_rich_is_not() -> None:
    assert seed_is_thin(_campaign_seed())
    assert not seed_is_thin(_rich_seed())


def test_merge_restores_marks_and_hunt_on_current_working_id() -> None:
    merged = merge_preserved_seed(_campaign_seed(), rich=_rich_seed())
    order = merged["detail"]["open_orders"][0]
    assert order["mtm_usd"] == 24.78
    assert order["decision"] == "HOLD"
    assert order["dual_pt_ready"] is False
    assert merged["detail"]["f_ic"]["miss"] == "put_wing_none_after_further_rip"
    assert merged["source"] == "rth_eval_20260814T1242"
    assert merged["ken_required"] is False
    assert not seed_is_thin(merged)


def test_marks_file_overrides_stale_sidecar_mtm() -> None:
    marks = {
        "marks": [
            {
                "order_id": "paper_b5b969c4a65f",
                "mtm_usd": 26.78,
                "mtm_adverse_usd": 5.78,
                "decision": "HOLD",
                "spot": 102.54,
                "pt_usd": 18.38,
                "dual_pt_ready": False,
            }
        ]
    }
    merged = merge_preserved_seed(_campaign_seed(), rich=_rich_seed(), marks=marks)
    order = merged["detail"]["open_orders"][0]
    assert order["mtm_usd"] == 26.78
    assert order["spot"] == 102.54
    assert merged["detail"]["pack"]["KO"] == "pcs_bull_only:neutral"


def test_apply_preserve_restores_thin_file(tmp_path: Path) -> None:
    seed_path = tmp_path / "NEXT_SEED.json"
    marks_path = tmp_path / "marks.json"
    sidecar_path = tmp_path / "rich.json"
    seed_path.write_text(json.dumps(_campaign_seed()), encoding="utf-8")
    sidecar_path.write_text(json.dumps(_rich_seed()), encoding="utf-8")
    marks_path.write_text(
        json.dumps(
            {
                "marks": [
                    {
                        "order_id": "paper_b5b969c4a65f",
                        "mtm_usd": 26.78,
                        "decision": "HOLD",
                        "spot": 102.54,
                        "dual_pt_ready": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = apply_preserve(seed_path=seed_path, marks_path=marks_path, sidecar_path=sidecar_path)
    assert result["action"] == "restored"
    living = json.loads(seed_path.read_text(encoding="utf-8"))
    assert living["detail"]["open_orders"][0]["mtm_usd"] == 26.78
    assert living["detail"]["f_ic"]["spot"] == 14.38
    assert not seed_is_thin(living)


def test_apply_preserve_refreshes_sidecar_when_already_rich(tmp_path: Path) -> None:
    seed_path = tmp_path / "NEXT_SEED.json"
    sidecar_path = tmp_path / "rich.json"
    seed_path.write_text(json.dumps(_rich_seed()), encoding="utf-8")
    result = apply_preserve(
        seed_path=seed_path,
        marks_path=tmp_path / "missing.json",
        sidecar_path=sidecar_path,
    )
    assert result["action"] == "sidecar_refresh"
    assert sidecar_path.is_file()
    assert json.loads(seed_path.read_text(encoding="utf-8"))["source"] == "rth_eval_20260814T1242"


def test_quality_cycle_hooks_preserve_after_campaign() -> None:
    text = Path("scripts/trader_quality_cycle.py").read_text(encoding="utf-8")
    assert "trader_preserve_rth_next_seed.py" in text
    assert "next_seed_preserve" in text
    assert text.index("next_seed_preserve") > text.index("paper_campaign")

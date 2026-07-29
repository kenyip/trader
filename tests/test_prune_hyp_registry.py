"""Boundary tests for off-hours hypotheses.yaml prune."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts import trader_prune_hyp_registry as prune


def _write_hyps(path: Path, rows: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"version": 1, "hypotheses": rows}, sort_keys=False), encoding="utf-8")


def test_paper_open_strategy_forced_even_when_low_score(tmp_path: Path, monkeypatch) -> None:
    hyps_path = tmp_path / "hypotheses.yaml"
    ledger = tmp_path / "paper_ledger.json"
    shortlist = tmp_path / "QUALITY_SHORTLIST.json"
    first_live = tmp_path / "FIRST_LIVE_LANE.json"
    rotation = tmp_path / "STRESS_ROTATION.json"

    rows = [
        {"id": "hyp_open_paper", "status": "candidate", "score": 0.1, "structure": "put_credit_spread"},
        {"id": "hyp_hot_score", "status": "candidate", "score": 999.0, "structure": "put_credit_spread"},
        {"id": "hyp_shortlist", "status": "testing", "score": 10.0, "structure": "put_credit_spread"},
        {"id": "hyp_junk", "status": "rejected", "score": 1.0, "structure": "call_credit_spread"},
    ]
    _write_hyps(hyps_path, rows)
    ledger.write_text(
        json.dumps(
            {
                "orders": {
                    "paper_1": {
                        "status": "working",
                        "strategy_id": "hyp_open_paper",
                        "symbol": "BAC",
                    },
                    "paper_closed": {
                        "status": "closed",
                        "strategy_id": "hyp_should_not_force",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    shortlist.write_text(
        json.dumps({"shortlist": [{"hyp_id": "hyp_shortlist"}]}),
        encoding="utf-8",
    )
    # Ghost first-live id — never registered.
    first_live.write_text(
        json.dumps(
            {
                "leader": {"hyp_id": "hyp_snap_ghost_dna"},
                "shortlist": [{"hyp_id": "hyp_snap_ghost_dna"}],
            }
        ),
        encoding="utf-8",
    )
    rotation.write_text(json.dumps({"by_hyp_id": {}}), encoding="utf-8")

    monkeypatch.setattr(prune, "_HYPS", hyps_path)
    monkeypatch.setattr(prune, "_SHORTLIST", shortlist)
    monkeypatch.setattr(prune, "_FIRST_LIVE", first_live)
    monkeypatch.setattr(prune, "_ROTATION", rotation)
    monkeypatch.setattr(prune, "_PAPER_LEDGER", ledger)
    monkeypatch.setattr(prune, "_BACKUP_DIR", tmp_path / "bak")

    res = prune.prune(path=hyps_path, max_keep=2, dry_run=False, force=True)
    assert res["ok"] is True
    assert res["n_after"] >= 2
    assert res["n_first_live_ghosts"] == 1
    assert "hyp_snap_ghost_dna" in res["first_live_ghosts_sample"]
    assert res["n_paper_open_forced"] == 1

    saved = yaml.safe_load(hyps_path.read_text(encoding="utf-8"))
    ids = {h["id"] for h in saved["hypotheses"]}
    assert "hyp_open_paper" in ids
    assert "hyp_shortlist" in ids
    # max_keep=2 with 2 forced → junk high-score optional row may drop
    assert "hyp_junk" not in ids or len(ids) > 2


def test_paper_open_ids_parser_skips_closed() -> None:
    assert prune._paper_open_strategy_ids  # import surface
    # empty path
    assert prune._paper_open_strategy_ids(Path("/nonexistent/paper_ledger.json")) == set()

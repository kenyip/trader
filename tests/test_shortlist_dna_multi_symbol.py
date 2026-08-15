"""Shortlist DNA multi-symbol selector unit tests (no heavy pcs sim)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.trader_shortlist_dna_multi_symbol import (
    peer_symbols,
    select_leader_hyps,
    select_pinned_hyps,
)


def test_select_leader_hyps_prefers_capital_path_ok_and_dedupes(tmp_path: Path):
    rot = tmp_path / "STRESS.json"
    by = {
        "hyp_aal_a": {
            "symbol": "AAL",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "dense_neg_ge3": 1,
            "max_dd": 34.0,
            "b4_slip5_verdict": "SHIP",
            "b4_slip5_pnl": 50.0,
            "full_pnl": 180.0,
        },
        "hyp_aal_b": {
            "symbol": "AAL",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "dense_neg_ge3": 1,
            "max_dd": 40.0,
            "b4_slip5_verdict": "SHIP",
            "b4_slip5_pnl": 40.0,
            "full_pnl": 100.0,
        },
        "hyp_bac": {
            "symbol": "BAC",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "dense_neg_ge3": 0,
            "max_dd": 42.0,
            "b4_slip5_verdict": "SHIP",
            "b4_slip5_pnl": 200.0,
            "full_pnl": 600.0,
        },
        "hyp_fail": {
            "symbol": "NFLX",
            "structure": "call_credit_spread",
            "capital_path_ok": False,
            "dense_neg_ge3": 5,
            "max_dd": 400.0,
            "b4_slip5_verdict": "NULL",
            "b4_slip5_pnl": -10.0,
            "full_pnl": 900.0,
        },
    }
    rot.write_text(json.dumps({"by_hyp_id": by}), encoding="utf-8")
    sl = tmp_path / "SHORTLIST.json"
    sl.write_text(
        json.dumps(
            {
                "shortlist": [
                    {"hyp_id": "hyp_aal_a", "symbol": "AAL"},
                    {"hyp_id": "hyp_bac", "symbol": "BAC"},
                ]
            }
        ),
        encoding="utf-8",
    )
    leaders = select_leader_hyps(top_n=3, rotation_path=rot, shortlist_path=sl)
    ids = [r["hyp_id"] for r in leaders]
    assert "hyp_fail" not in ids
    # one AAL family only
    assert sum(1 for i in ids if i.startswith("hyp_aal")) == 1
    assert "hyp_bac" in ids


def test_peer_symbols_excludes_origin(tmp_path: Path):
    sl = tmp_path / "SHORTLIST.json"
    sl.write_text(
        json.dumps({"shortlist": [{"symbol": "AAL"}, {"symbol": "BAC"}, {"symbol": "F"}]}),
        encoding="utf-8",
    )
    peers = peer_symbols("AAL", shortlist_path=sl, extra=["KO"], max_peers=10)
    assert "AAL" not in peers
    assert peers[0] == "BAC"
    assert "F" in peers
    assert "KO" in peers


def test_peer_symbols_exclusive_skips_shortlist_leftovers(tmp_path: Path):
    sl = tmp_path / "SHORTLIST.json"
    sl.write_text(
        json.dumps({"shortlist": [{"symbol": "F"}, {"symbol": "AAL"}, {"symbol": "BAC"}]}),
        encoding="utf-8",
    )
    peers = peer_symbols(
        "F",
        shortlist_path=sl,
        extra=["SOFI", "PFE", "NIO", "JPM", "QQQ"],
        max_peers=6,
        exclusive=True,
    )
    assert peers == ["SOFI", "PFE", "NIO", "JPM", "QQQ"]
    assert "AAL" not in peers
    assert "BAC" not in peers


def test_select_pinned_hyps_keeps_order_and_skips_blank(tmp_path: Path):
    rot = tmp_path / "STRESS.json"
    rot.write_text(
        json.dumps(
            {
                "by_hyp_id": {
                    "hyp_dna_bac_put_credit_spread_631f9804": {
                        "symbol": "BAC",
                        "structure": "put_credit_spread",
                        "capital_path_ok": True,
                    },
                    "hyp_dna_f_iron_condor_5d8c1fff": {
                        "symbol": "F",
                        "structure": "iron_condor",
                        "capital_path_ok": True,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    sl = tmp_path / "SHORTLIST.json"
    sl.write_text(
        json.dumps(
            {
                "shortlist": [
                    {"hyp_id": "hyp_dna_f_iron_condor_39f86341", "symbol": "F"},
                    {"hyp_id": "hyp_dna_bac_put_credit_spread_631f9804", "symbol": "BAC"},
                ]
            }
        ),
        encoding="utf-8",
    )
    pinned = select_pinned_hyps(
        [
            "hyp_dna_bac_put_credit_spread_631f9804",
            "",
            "hyp_dna_f_iron_condor_5d8c1fff",
            "hyp_dna_bac_put_credit_spread_631f9804",
        ],
        rotation_path=rot,
        shortlist_path=sl,
    )
    assert [r["hyp_id"] for r in pinned] == [
        "hyp_dna_bac_put_credit_spread_631f9804",
        "hyp_dna_f_iron_condor_5d8c1fff",
    ]
    via_select = select_leader_hyps(
        top_n=1,
        rotation_path=rot,
        shortlist_path=sl,
        hyp_ids=["hyp_dna_f_iron_condor_5d8c1fff"],
    )
    assert [r["hyp_id"] for r in via_select] == ["hyp_dna_f_iron_condor_5d8c1fff"]
    assert via_select[0]["structure"] == "iron_condor"

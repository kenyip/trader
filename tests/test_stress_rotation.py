"""Stress-rotation selector: leaders + fresh unstressed multi-leg; ledger excludes re-stress."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import scripts.trader_select_stress_hyps as sel


def test_rotation_ledger_excludes_fresh_pick(tmp_path: Path, monkeypatch):
    repo = tmp_path
    shortlist = {
        "shortlist": [
            {
                "hyp_id": "hyp_dna_bac_put_credit_spread_leader",
                "structure": "put_credit_spread",
                "symbol": "BAC",
                "stress_priority": True,
                "full_pnl": 500,
            },
            {
                "hyp_id": "hyp_dna_pltr_put_credit_spread_leader",
                "structure": "put_credit_spread",
                "symbol": "PLTR",
                "stress_priority": True,
                "full_pnl": 400,
            },
        ]
    }
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(json.dumps(shortlist), encoding="utf-8")
    # already stressed fresh id
    (bootstrap / "STRESS_ROTATION.json").write_text(
        json.dumps(
            {
                "by_hyp_id": {
                    "hyp_dna_mu_put_credit_spread_done": {
                        "hyp_id": "hyp_dna_mu_put_credit_spread_done",
                        "reject_reason": "B4 fail",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    # no hyp yaml → registry path empty; evolve logs supply fresh
    log_dir = repo / ".cache" / "platform" / "quality_residual"
    log_dir.mkdir(parents=True)
    (log_dir / "evolve_dr_test.log").write_text(
        "SHIP                 500.00     40  call_credit_spread/NFLX  positive_sim\n"
        "SHIP                 100.00     20  put_credit_spread/MU  positive_sim\n"
        "created: hyp_dna_nflx_call_credit_spread_fresh1, hyp_dna_mu_put_credit_spread_done\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sel, "_REPO", repo)
    monkeypatch.setattr(sel, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")
    monkeypatch.setattr(sel, "_HYPS", repo / "missing_hyps.yaml")
    monkeypatch.setattr(sel, "_EVOLVE_LOG_DIR", log_dir)
    monkeypatch.setattr(sel, "_ROTATION", bootstrap / "STRESS_ROTATION.json")

    res = sel.select_stress_hyps(limit=4, n_leaders=2, include_logs=True)
    ids = res["hyp_ids"]
    assert ids[0] == "hyp_dna_bac_put_credit_spread_leader"
    assert ids[1] == "hyp_dna_pltr_put_credit_spread_leader"
    assert "hyp_dna_nflx_call_credit_spread_fresh1" in ids
    assert "hyp_dna_mu_put_credit_spread_done" not in ids


def test_ingest_marks_rejects_and_ranks_leader(tmp_path: Path, monkeypatch):
    import scripts.trader_ingest_stress_rotation as ing

    repo = tmp_path
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    regime = {
        "results": [
            {
                "hyp_id": "hyp_a_bac",
                "symbol": "BAC",
                "structure": "put_credit_spread",
                "full_history": {"pnl": 500, "n_trades": 40, "verdict": "SHIP", "max_loss_usd": 160},
                "summary": {
                    "regime_hold": True,
                    "n_negative_n_ge_3": 1,
                    "max_dd_across_windows": 68.2,
                    "worst_window_pnl": -20,
                },
            },
            {
                "hyp_id": "hyp_b_mu",
                "symbol": "MU",
                "structure": "put_credit_spread",
                "full_history": {"pnl": 800, "n_trades": 100, "verdict": "SHIP", "max_loss_usd": 200},
                "summary": {
                    "regime_hold": True,
                    "n_negative_n_ge_3": 5,
                    "max_dd_across_windows": 270,
                    "worst_window_pnl": -180,
                },
            },
            {
                "hyp_id": "hyp_c_smci_softnull",
                "symbol": "SMCI",
                "structure": "call_credit_spread",
                "full_history": {"pnl": 218, "n_trades": 30, "verdict": "SHIP", "max_loss_usd": 170},
                "summary": {
                    "regime_hold": True,
                    "n_negative_n_ge_3": 1,
                    "max_dd_across_windows": 51,
                    "worst_window_pnl": -10,
                },
            },
            {
                "hyp_id": "hyp_d_smci_negfull",
                "symbol": "SMCI",
                "structure": "call_credit_spread",
                "full_history": {"pnl": -10.79, "n_trades": 20, "verdict": "NULL", "max_loss_usd": 80},
                "summary": {
                    "regime_hold": True,
                    "n_negative_n_ge_3": 1,
                    "max_dd_across_windows": 65,
                    "worst_window_pnl": -20,
                },
            },
            {
                "hyp_id": "hyp_e_nflx_null_pos",
                "symbol": "NFLX",
                "structure": "call_credit_spread",
                "full_history": {"pnl": 860, "n_trades": 40, "verdict": "SHIP", "max_loss_usd": 180},
                "summary": {
                    "regime_hold": True,
                    "n_negative_n_ge_3": 1,
                    # Tighter DD than BAC SHIP — still must NOT lead (verdict before DD)
                    "max_dd_across_windows": 58.98,
                    "worst_window_pnl": -15,
                },
            },
            {
                "hyp_id": "hyp_f_bac_softloss",
                "symbol": "BAC",
                "structure": "put_credit_spread",
                "full_history": {"pnl": 340, "n_trades": 25, "verdict": "SHIP", "max_loss_usd": 160},
                "summary": {
                    "regime_hold": True,
                    "n_negative_n_ge_3": 1,
                    "max_dd_across_windows": 71,
                    "worst_window_pnl": -30,
                },
            },
        ]
    }
    cost = {
        "summaries": [
            {
                "hyp": "hyp_a_bac",
                "cost_hold": True,
                "slip_5_verdict": "SHIP",
                "slip_5_pnl": 200,
                "note": "survives_5pct_slip",
            },
            {
                "hyp": "hyp_b_mu",
                "cost_hold": False,
                "slip_5_verdict": "REJECT",
                "slip_5_pnl": -600,
                "note": "fragile_at_5pct_slip",
            },
            {
                "hyp": "hyp_c_smci_softnull",
                "cost_hold": True,
                "slip_5_verdict": "NULL",
                "slip_5_pnl": 0.0,
                "note": "survives_5pct_slip",
            },
            {
                "hyp": "hyp_d_smci_negfull",
                "cost_hold": True,
                "slip_5_verdict": "NULL",
                "slip_5_pnl": 0.0,
                "note": "survives_5pct_slip",
            },
            {
                "hyp": "hyp_e_nflx_null_pos",
                "cost_hold": True,
                "slip_5_verdict": "NULL",
                "slip_5_pnl": 80.47,
                "note": "survives_5pct_slip",
            },
            {
                "hyp": "hyp_f_bac_softloss",
                "cost_hold": True,
                "slip_5_verdict": "NEEDS_MORE_DATA",
                "slip_5_pnl": -31.92,
                "note": "soft_loss_at_5pct_defined_risk",
            },
        ]
    }
    rp = tmp_path / "regime.json"
    cp = tmp_path / "cost.json"
    rp.write_text(json.dumps(regime), encoding="utf-8")
    cp.write_text(json.dumps(cost), encoding="utf-8")

    monkeypatch.setattr(ing, "_REPO", repo)
    monkeypatch.setattr(ing, "_LEDGER", bootstrap / "STRESS_ROTATION.json")
    monkeypatch.setattr(ing, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(json.dumps({"shortlist": []}), encoding="utf-8")

    res = ing.ingest_pair(rp, cp, source="test")
    assert res["n_ledger"] == 6
    ledger = json.loads((bootstrap / "STRESS_ROTATION.json").read_text(encoding="utf-8"))
    assert ledger["by_hyp_id"]["hyp_a_bac"]["capital_path_ok"] is True
    assert ledger["by_hyp_id"]["hyp_b_mu"]["capital_path_ok"] is False
    assert ledger["by_hyp_id"]["hyp_c_smci_softnull"]["capital_path_ok"] is False
    assert "NULL/~0" in (ledger["by_hyp_id"]["hyp_c_smci_softnull"].get("reject_reason") or "")
    assert ledger["by_hyp_id"]["hyp_d_smci_negfull"]["capital_path_ok"] is False
    assert ledger["by_hyp_id"]["hyp_e_nflx_null_pos"]["capital_path_ok"] is True
    assert ledger["by_hyp_id"]["hyp_f_bac_softloss"]["capital_path_ok"] is False
    assert "soft_loss" in (ledger["by_hyp_id"]["hyp_f_bac_softloss"].get("reject_reason") or "")

    sl = ing.refresh_shortlist_from_ledger()
    data = json.loads((bootstrap / "QUALITY_SHORTLIST.json").read_text(encoding="utf-8"))
    ids = [r["hyp_id"] for r in data["shortlist"]]
    assert "hyp_a_bac" in ids
    assert "hyp_e_nflx_null_pos" in ids
    assert "hyp_b_mu" not in ids
    assert "hyp_c_smci_softnull" not in ids
    assert "hyp_d_smci_negfull" not in ids
    assert "hyp_f_bac_softloss" not in ids
    assert any(r.get("hyp_id") == "hyp_b_mu" for r in data["rejected_tonight"])
    assert any(r.get("hyp_id") == "hyp_c_smci_softnull" for r in data["rejected_tonight"])
    assert any(r.get("hyp_id") == "hyp_f_bac_softloss" for r in data["rejected_tonight"])
    # SHIP@5% BAC ranks above NULL@positive NFLX even when NFLX has tighter DD
    assert data["shortlist"][0]["hyp_id"] == "hyp_a_bac"
    assert data["shortlist"][0]["stress_priority"] is True
    assert data["shortlist"][0]["hyp_id"] != "hyp_e_nflx_null_pos" or data["shortlist"][0]["hyp_id"] == "hyp_a_bac"
    # NFLX may remain on shortlist but not ahead of SHIP when dens equal
    nflx_i = ids.index("hyp_e_nflx_null_pos")
    bac_i = ids.index("hyp_a_bac")
    assert bac_i < nflx_i


def test_rescore_flips_soft_null_zero(tmp_path: Path, monkeypatch):
    import scripts.trader_ingest_stress_rotation as ing

    repo = tmp_path
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    ledger = {
        "by_hyp_id": {
            "hyp_soft": {
                "hyp_id": "hyp_soft",
                "symbol": "SMCI",
                "structure": "call_credit_spread",
                "b3_hold": True,
                "b4_cost_hold": True,
                "b4_slip5_verdict": "NULL",
                "b4_slip5_pnl": 0.0,
                "dense_neg_ge3": 1,
                "max_dd": 50,
                "full_pnl": 200,
                "capital_path_ok": True,
                "reject_reason": None,
            },
            "hyp_softloss": {
                "hyp_id": "hyp_softloss",
                "symbol": "BAC",
                "structure": "put_credit_spread",
                "b3_hold": True,
                "b4_cost_hold": True,
                "b4_slip5_verdict": "NEEDS_MORE_DATA",
                "b4_slip5_pnl": -31.92,
                "dense_neg_ge3": 1,
                "max_dd": 71,
                "full_pnl": 340,
                "capital_path_ok": True,
                "reject_reason": None,
            },
            "hyp_needs_pos": {
                "hyp_id": "hyp_needs_pos",
                "symbol": "PLTR",
                "structure": "put_credit_spread",
                "b3_hold": True,
                "b4_cost_hold": True,
                "b4_slip5_verdict": "NEEDS_MORE_DATA",
                "b4_slip5_pnl": 6.33,
                "dense_neg_ge3": 1,
                "max_dd": 198,
                "full_pnl": 963,
                "capital_path_ok": True,
                "reject_reason": None,
            },
            "hyp_ship": {
                "hyp_id": "hyp_ship",
                "symbol": "BAC",
                "structure": "put_credit_spread",
                "b3_hold": True,
                "b4_cost_hold": True,
                "b4_slip5_verdict": "SHIP",
                "b4_slip5_pnl": 100,
                "dense_neg_ge3": 1,
                "max_dd": 70,
                "full_pnl": 400,
                "capital_path_ok": True,
                "reject_reason": None,
            },
        }
    }
    (bootstrap / "STRESS_ROTATION.json").write_text(json.dumps(ledger), encoding="utf-8")
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(json.dumps({"shortlist": []}), encoding="utf-8")
    monkeypatch.setattr(ing, "_REPO", repo)
    monkeypatch.setattr(ing, "_LEDGER", bootstrap / "STRESS_ROTATION.json")
    monkeypatch.setattr(ing, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")

    res = ing.rescore_ledger(source="test")
    assert res["n_flipped_off"] == 3
    data = json.loads((bootstrap / "STRESS_ROTATION.json").read_text(encoding="utf-8"))
    assert data["by_hyp_id"]["hyp_soft"]["capital_path_ok"] is False
    assert data["by_hyp_id"]["hyp_softloss"]["capital_path_ok"] is False
    assert data["by_hyp_id"]["hyp_needs_pos"]["capital_path_ok"] is False
    assert data["by_hyp_id"]["hyp_ship"]["capital_path_ok"] is True
    ing.refresh_shortlist_from_ledger()
    sl = json.loads((bootstrap / "QUALITY_SHORTLIST.json").read_text(encoding="utf-8"))
    ids = [r["hyp_id"] for r in sl["shortlist"]]
    assert ids == ["hyp_ship"]


def test_capital_path_requires_ship_at_5pct():
    import scripts.trader_ingest_stress_rotation as ing

    ok, reason = ing.capital_path_decision(
        b3=True,
        b4=True,
        slip5_v="NEEDS_MORE_DATA",
        slip5_pnl=6.33,
        dense_neg=1,
        max_dd=198,
        full_pnl=900,
    )
    assert ok is False
    assert "NEEDS_MORE_DATA" in (reason or "")

    ok2, reason2 = ing.capital_path_decision(
        b3=True,
        b4=True,
        slip5_v="SHIP",
        slip5_pnl=300.72,
        dense_neg=0,
        max_dd=35,
        full_pnl=390,
    )
    assert ok2 is True
    assert reason2 is None


def test_select_skips_negative_score_shipish(tmp_path: Path, monkeypatch):
    """Vanity SHIP tag + negative composite must not burn B3/B4 slots."""
    repo = tmp_path
    shortlist = {
        "shortlist": [
            {
                "hyp_id": "hyp_dna_bac_put_credit_spread_leader",
                "structure": "put_credit_spread",
                "symbol": "BAC",
                "stress_priority": True,
                "full_pnl": 500,
            }
        ]
    }
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(json.dumps(shortlist), encoding="utf-8")
    (bootstrap / "STRESS_ROTATION.json").write_text(json.dumps({"by_hyp_id": {}}), encoding="utf-8")

    hyps_yaml = repo / "hyps.yaml"
    # Minimal registry-compatible rows via monkeypatch of HypothesisRegistry path is heavy;
    # use evolve log path: only positive scores are emitted; registry returns empty.
    log_dir = repo / ".cache" / "platform" / "quality_residual"
    log_dir.mkdir(parents=True)
    (log_dir / "evolve_dr_test.log").write_text(
        "SHIP                -146.58     27  put_credit_spread/TSLL  positive_sim\n"
        "SHIP                  37.33     26  put_credit_spread/BAC  positive_sim\n"
        "created: hyp_dna_tsll_put_credit_spread_neg, hyp_dna_bac_put_credit_spread_pos\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sel, "_REPO", repo)
    monkeypatch.setattr(sel, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")
    monkeypatch.setattr(sel, "_HYPS", hyps_yaml)
    monkeypatch.setattr(sel, "_EVOLVE_LOG_DIR", log_dir)
    monkeypatch.setattr(sel, "_ROTATION", bootstrap / "STRESS_ROTATION.json")

    res = sel.select_stress_hyps(limit=4, n_leaders=1, include_logs=True)
    ids = res["hyp_ids"]
    assert ids[0] == "hyp_dna_bac_put_credit_spread_leader"
    assert "hyp_dna_bac_put_credit_spread_pos" in ids
    assert "hyp_dna_tsll_put_credit_spread_neg" not in ids


def test_rank_key_prefers_dense_zero_over_dense_one(tmp_path: Path, monkeypatch):
    """dense_neg=0 must not be treated as missing (0 or 99 bug)."""
    import scripts.trader_ingest_stress_rotation as ing

    repo = tmp_path
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    ledger = {
        "by_hyp_id": {
            "hyp_dense0": {
                "hyp_id": "hyp_dense0",
                "symbol": "AAL",
                "structure": "put_credit_spread",
                "capital_path_ok": True,
                "reject_reason": None,
                "b3_hold": True,
                "b4_cost_hold": True,
                "dense_neg_ge3": 0,
                "max_dd": 35.0,
                "b4_slip5_verdict": "SHIP",
                "b4_slip5_pnl": 300.0,
                "full_pnl": 400.0,
                "max_loss_usd": 180.0,
                "source": "test",
                "stressed_at": "2026-07-23T12:00:00+00:00",
            },
            "hyp_dense1": {
                "hyp_id": "hyp_dense1",
                "symbol": "AAL",
                "structure": "call_credit_spread",
                "capital_path_ok": True,
                "reject_reason": None,
                "b3_hold": True,
                "b4_cost_hold": True,
                "dense_neg_ge3": 1,
                "max_dd": 48.0,
                "b4_slip5_verdict": "SHIP",
                "b4_slip5_pnl": 290.0,
                "full_pnl": 370.0,
                "max_loss_usd": 185.0,
                "source": "test",
                "stressed_at": "2026-07-23T12:00:00+00:00",
            },
        }
    }
    (bootstrap / "STRESS_ROTATION.json").write_text(json.dumps(ledger), encoding="utf-8")
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(
        json.dumps({"shortlist": [], "rejected_tonight": []}), encoding="utf-8"
    )
    monkeypatch.setattr(ing, "_LEDGER", bootstrap / "STRESS_ROTATION.json")
    monkeypatch.setattr(ing, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")
    res = ing.refresh_shortlist_from_ledger()
    assert res["top_ids"][0] == "hyp_dense0"
    assert res["top_ids"][1] == "hyp_dense1"


def test_select_skips_fresh_capital_path_leaders(tmp_path: Path, monkeypatch):
    """Leaders already capital_path_ok within TTL free stress slots for fresh DNA."""
    from datetime import datetime, timezone

    repo = tmp_path
    shortlist = {
        "shortlist": [
            {
                "hyp_id": "hyp_dna_bac_put_credit_spread_leader",
                "structure": "put_credit_spread",
                "symbol": "BAC",
                "stress_priority": True,
                "full_pnl": 500,
            }
        ]
    }
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(json.dumps(shortlist), encoding="utf-8")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    (bootstrap / "STRESS_ROTATION.json").write_text(
        json.dumps(
            {
                "by_hyp_id": {
                    "hyp_dna_bac_put_credit_spread_leader": {
                        "hyp_id": "hyp_dna_bac_put_credit_spread_leader",
                        "capital_path_ok": True,
                        "stressed_at": now,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    log_dir = repo / ".cache" / "platform" / "quality_residual"
    log_dir.mkdir(parents=True)
    (log_dir / "evolve_dr_test.log").write_text(
        "SHIP                 500.00     40  call_credit_spread/NFLX  positive_sim\n"
        "created: hyp_dna_nflx_call_credit_spread_fresh1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sel, "_REPO", repo)
    monkeypatch.setattr(sel, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")
    monkeypatch.setattr(sel, "_HYPS", repo / "missing_hyps.yaml")
    monkeypatch.setattr(sel, "_EVOLVE_LOG_DIR", log_dir)
    monkeypatch.setattr(sel, "_ROTATION", bootstrap / "STRESS_ROTATION.json")

    res = sel.select_stress_hyps(
        limit=4, n_leaders=1, include_logs=True, leader_ttl_hours=6.0, min_fresh_trades=0
    )
    assert "hyp_dna_bac_put_credit_spread_leader" not in res["hyp_ids"]
    assert "hyp_dna_bac_put_credit_spread_leader" in res["skipped_fresh_leaders"]
    assert "hyp_dna_nflx_call_credit_spread_fresh1" in res["hyp_ids"]


def test_metric_twin_key_and_dedupe(tmp_path, monkeypatch):
    """Identical evolve score/n twins collapse to one stress slot."""
    repo = tmp_path
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(
        json.dumps({"shortlist": []}), encoding="utf-8"
    )
    (bootstrap / "STRESS_ROTATION.json").write_text(
        json.dumps({"by_hyp_id": {}}), encoding="utf-8"
    )
    log_dir = repo / ".cache" / "platform" / "quality_residual"
    log_dir.mkdir(parents=True)
    # Two SHIP lines same score/n/symbol + two created ids (twins)
    (log_dir / "evolve_dr_twins.log").write_text(
        "SHIP                 475.65     46  call_credit_spread/NFLX  positive_sim\n"
        "SHIP                 475.65     46  call_credit_spread/NFLX  positive_sim\n"
        "SHIP                 200.00     20  put_credit_spread/AAL  positive_sim\n"
        "created: hyp_dna_nflx_call_credit_spread_twin_a,"
        "hyp_dna_nflx_call_credit_spread_twin_b,"
        "hyp_dna_aal_put_credit_spread_other\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sel, "_REPO", repo)
    monkeypatch.setattr(sel, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")
    monkeypatch.setattr(sel, "_HYPS", repo / "missing_hyps.yaml")
    monkeypatch.setattr(sel, "_EVOLVE_LOG_DIR", log_dir)
    monkeypatch.setattr(sel, "_ROTATION", bootstrap / "STRESS_ROTATION.json")

    k1 = sel._metric_twin_key(
        {"symbol": "NFLX", "structure": "call_credit_spread", "score": 475.65, "n_trades": 46}
    )
    k2 = sel._metric_twin_key(
        {"symbol": "NFLX", "structure": "call_credit_spread", "score": 475.649, "n_trades": 46}
    )
    assert k1 == k2

    res = sel.select_stress_hyps(
        limit=4,
        n_leaders=0,
        include_logs=True,
        leader_ttl_hours=0,
        min_fresh_trades=0,
        family_fail_window_hours=0,  # disable cool for this unit
    )
    nflx = [h for h in res["hyp_ids"] if "nflx_call_credit_spread" in h]
    assert len(nflx) == 1, res
    assert len(res.get("skipped_metric_twins") or []) >= 1
    assert "hyp_dna_aal_put_credit_spread_other" in res["hyp_ids"]


def test_family_recent_fail_cooled(tmp_path, monkeypatch):
    """Symbol×structure with recent fails and zero capital_ok is cooled."""
    repo = tmp_path
    bootstrap = repo / "reports" / "bootstrap"
    bootstrap.mkdir(parents=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    (bootstrap / "QUALITY_SHORTLIST.json").write_text(
        json.dumps({"shortlist": []}), encoding="utf-8"
    )
    (bootstrap / "STRESS_ROTATION.json").write_text(
        json.dumps(
            {
                "by_hyp_id": {
                    "hyp_dna_nflx_call_credit_spread_old1": {
                        "hyp_id": "hyp_dna_nflx_call_credit_spread_old1",
                        "symbol": "NFLX",
                        "structure": "call_credit_spread",
                        "capital_path_ok": False,
                        "stressed_at": now,
                    },
                    "hyp_dna_nflx_call_credit_spread_old2": {
                        "hyp_id": "hyp_dna_nflx_call_credit_spread_old2",
                        "symbol": "NFLX",
                        "structure": "call_credit_spread",
                        "capital_path_ok": False,
                        "stressed_at": now,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    log_dir = repo / ".cache" / "platform" / "quality_residual"
    log_dir.mkdir(parents=True)
    (log_dir / "evolve_dr_cool.log").write_text(
        "SHIP                 475.65     46  call_credit_spread/NFLX  positive_sim\n"
        "SHIP                 300.00     30  put_credit_spread/AAL  positive_sim\n"
        "created: hyp_dna_nflx_call_credit_spread_freshx,hyp_dna_aal_put_credit_spread_freshy\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sel, "_REPO", repo)
    monkeypatch.setattr(sel, "_SHORTLIST", bootstrap / "QUALITY_SHORTLIST.json")
    monkeypatch.setattr(sel, "_HYPS", repo / "missing_hyps.yaml")
    monkeypatch.setattr(sel, "_EVOLVE_LOG_DIR", log_dir)
    monkeypatch.setattr(sel, "_ROTATION", bootstrap / "STRESS_ROTATION.json")

    assert sel._family_recent_fail_cooled("NFLX", "call_credit_spread", window_hours=6.0, min_fails=2)
    assert not sel._family_recent_fail_cooled("AAL", "put_credit_spread", window_hours=6.0, min_fails=2)

    res = sel.select_stress_hyps(
        limit=4,
        n_leaders=0,
        include_logs=True,
        leader_ttl_hours=0,
        min_fresh_trades=0,
        family_fail_window_hours=6.0,
        family_fail_min=2,
    )
    assert "hyp_dna_nflx_call_credit_spread_freshx" not in res["hyp_ids"]
    assert "hyp_dna_aal_put_credit_spread_freshy" in res["hyp_ids"]
    assert "hyp_dna_nflx_call_credit_spread_freshx" in res.get("skipped_family_cooled", [])
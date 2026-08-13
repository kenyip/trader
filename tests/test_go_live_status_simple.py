"""Tests for simplified go-live status (3-layer + session spanning)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.trader_go_live_status import (
    _load_first_live_lane,
    format_text,
    market_session_days_spanned,
)


def test_market_session_days_spanned_overnight_counts_two_weekdays():
    start = datetime(2026, 7, 22, 5, 41, tzinfo=timezone.utc)  # Wed
    end = datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc)  # Thu
    days = market_session_days_spanned(start, end)
    assert "2026-07-22" in days
    assert "2026-07-23" in days
    assert len(days) == 2


def test_market_session_days_skips_weekend():
    start = datetime(2026, 7, 24, 15, 0, tzinfo=timezone.utc)  # Fri
    end = datetime(2026, 7, 27, 15, 0, tzinfo=timezone.utc)  # Mon
    days = market_session_days_spanned(start, end)
    assert "2026-07-24" in days
    assert "2026-07-27" in days
    assert "2026-07-25" not in days  # Sat
    assert "2026-07-26" not in days  # Sun
    assert len(days) == 2


def test_first_live_loader_rejects_legacy_sleeve_only_seat(monkeypatch):
    legacy = {
        "max_loss_budget_usd": 300.0,
        "n_eligible": 901,
        "leader": {
            "eligible": True,
            "symbol": "AAL",
            "max_loss_usd_proxy": 1494.82,
            "csp_bp_proxy": 1494.82,
        },
        "shortlist": [
            {
                "eligible": True,
                "symbol": "AAL",
                "max_loss_usd_proxy": 1494.82,
            }
        ],
    }
    monkeypatch.setattr("scripts.trader_go_live_status._load_json", lambda _path: legacy)
    loaded = _load_first_live_lane()
    assert loaded["leader"] is None
    assert loaded["shortlist"] == []
    assert loaded["n_eligible"] == 0
    assert loaded["raw_n_eligible"] == 901


def test_first_live_loader_accepts_fit_3k_csp_above_300_bar(monkeypatch):
    """Status must not empty the board by treating CSP collateral BP as $300 max-loss."""
    report = {
        "max_loss_budget_usd": 300.0,
        "n_eligible": 2,
        "leader": {
            "eligible": True,
            "symbol": "SNAP",
            "structure": "cash_secured_put",
            "capital_fit": "fit_3k",
            "capital_ok": True,
            "max_loss_usd_proxy": 503.03,
            "csp_bp_proxy": 503.03,
            "path_max_loss_usd": None,
            "verdict": "SHIP",
            "hyp_id": "hyp_snap",
        },
        "shortlist": [
            {
                "eligible": True,
                "symbol": "SNAP",
                "structure": "cash_secured_put",
                "capital_fit": "fit_3k",
                "capital_ok": True,
                "max_loss_usd_proxy": 503.03,
                "csp_bp_proxy": 503.03,
                "path_max_loss_usd": None,
                "verdict": "SHIP",
                "hyp_id": "hyp_snap",
            },
            {
                "eligible": True,
                "symbol": "TSLL",
                "structure": "cash_secured_put",
                "capital_fit": "fit_3k",
                "capital_ok": True,
                "max_loss_usd_proxy": 766.51,
                "csp_bp_proxy": 766.51,
                "path_max_loss_usd": None,
                "verdict": "SHIP",
                "hyp_id": "hyp_tsll",
            },
            {
                # Explicit path stop still fails the $300 bar even with fit_3k.
                "eligible": True,
                "symbol": "F",
                "structure": "cash_secured_put",
                "capital_fit": "fit_3k",
                "capital_ok": True,
                "max_loss_usd_proxy": 500.0,
                "csp_bp_proxy": 500.0,
                "path_max_loss_usd": 450.0,
                "verdict": "SHIP",
                "hyp_id": "hyp_f_stop",
            },
        ],
    }
    monkeypatch.setattr("scripts.trader_go_live_status._load_json", lambda _path: report)
    loaded = _load_first_live_lane()
    assert loaded["leader"] is not None
    assert loaded["leader"]["symbol"] == "SNAP"
    assert loaded["n_eligible"] == 2
    assert {r["symbol"] for r in loaded["shortlist"]} == {"SNAP", "TSLL"}
    assert loaded["raw_n_eligible"] == 2


def test_format_text_uses_three_layers_not_alphabet_soup():
    # Minimal Funnel-like object via collect would need repo; unit the formatter contract
    from scripts.trader_go_live_status import Funnel

    f = Funnel(
        generated_at="2026-07-23T00:00:00+00:00",
        phase="PAPER",
        sleeve_plan_usd=3000,
        sleeve_cash_usd=500.0,
        option_level="option_level_2",
        agentic_enabled=False,
        overall_pct=66.0,
        overall_label="IN_PROGRESS",
        activity_pct=90.0,
        activity_label="SEARCHING",
        next_action="manage_open_paper_campaign",
        ken_required=False,
        layers={
            "edge": {
                "status": "PARTIAL",
                "summary": "stressed survivors — not pack-grade yet",
                "paper_research_leader": "hyp_x",
                "first_live_candidate": "TSLL cash_secured_put",
            },
            "robot": {
                "status": "PARTIAL",
                "summary": "paper=partial; shadow=todo",
                "paper_sessions": 2,
                "paper_sessions_target": 3,
                "shadow": "PARTIAL",
                "live_disarmed": True,
            },
            "arm": {
                "status": "BLOCKED",
                "summary": "Ken only",
            },
        },
        paper={
            "real_orders": 2,
            "working": 2,
            "open_risk_usd": 359.0,
            "oldest_open_hold_hours": 25.0,
            "open": [
                {
                    "symbol": "BAC",
                    "structure": "put_credit_spread",
                    "max_loss_usd": 162.0,
                    "hold_hours": 25.0,
                }
            ],
        },
        continuum={
            "quality_worker_running": True,
            "quality_cycles_completed": 100,
            "quality_worker_hb_age_h": 0.1,
        },
        shortlist_top=[],
        blockers=["No pack-grade edge yet"],
        path_to_live=["1. EDGE"],
        simple_next="Keep paper open/managed.",
        glossary={
            "EDGE": "sims",
            "ROBOT": "paper+shadow",
            "ARM": "Ken",
            "paper": "fake money",
            "shadow": "log only",
        },
        why_overall_stuck="remaining: edge",
    )
    text = format_text(f)
    assert "1) EDGE" in text
    assert "2) ROBOT" in text
    assert "3) ARM" in text
    assert "HOW THIS WORKS" in text
    # Primary view should not dump A1/B6 checklist
    assert "A · PLATFORM" not in text
    assert "B6 multi-session" not in text
    assert "ready-bar" not in text
    assert "layered readiness: EDGE=PARTIAL · ROBOT=PARTIAL · ARM=BLOCKED" in text
    assert "Keep paper open/managed" in text


def test_same_day_single_session():
    start = datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=3)
    days = market_session_days_spanned(start, end)
    assert len(days) == 1


def test_edge_search_health_detects_registry_bloat_skip():
    from scripts.trader_go_live_status import edge_search_health

    missing = Path("/tmp/trader-no-ken-freeze-test.json")
    bloated = edge_search_health(
        {
            "stamp": "20260731T040026",
            "evolve_note": "skipped both evolves: hypotheses.yaml 6002931b > limit 6000000b",
            "registry_bytes": 6_002_931,
            "registry_max_bytes": 6_000_000,
            "phases": {
                "evolve_csp": {
                    "skipped": True,
                    "reason": "registry_bloat_skip_evolve",
                    "registry_bytes": 6_002_931,
                },
                "evolve_defined_risk": {
                    "skipped": True,
                    "reason": "registry_bloat_skip_evolve",
                },
            },
        },
        freeze_path=missing,
    )
    assert bloated["registry_bloated_skip"] is True
    assert bloated["state"] == "BLOATED_SKIP"
    assert bloated["ken_edge_frozen"] is False
    assert bloated["evolve_ran"] == 0

    ok = edge_search_health(
        {
            "stamp": "20260731T040441",
            "registry_bytes": 1_848_575,
            "registry_max_bytes": 6_000_000,
            "phases": {
                "evolve_csp": {
                    "cmd": ["python", "-m", "trader_platform.evolve_tick"],
                    "rc": 0,
                    "seconds": 28.7,
                },
                "evolve_defined_risk": {
                    "skipped": True,
                    "reason": "evolve_lanes_one_alternate",
                },
            },
        },
        freeze_path=missing,
    )
    assert ok["registry_bloated_skip"] is False
    assert ok["state"] == "OK"
    assert ok["ken_edge_frozen"] is False
    assert ok["evolve_ran"] >= 1


def test_edge_search_health_ken_freeze_outranks_bloat_and_ok_partial():
    from scripts.trader_go_live_status import edge_search_health

    missing = Path("/tmp/trader-no-ken-freeze-test.json")
    frozen = edge_search_health(
        {
            "stamp": "20260813T155740",
            "evolve_note": (
                "skipped both evolves: Ken EDGE freeze (ken_first_close_freeze_edge_search); "
                "worker watch/paper only — do not prune-to-unfreeze"
            ),
            "registry_bytes": 6_000_873,
            "registry_max_bytes": 6_000_000,
            "phases": {
                "evolve_csp": {
                    "skipped": True,
                    "reason": "ken_first_close_freeze_edge_search",
                    "registry_bytes": 6_000_873,
                },
                "evolve_defined_risk": {
                    "skipped": True,
                    "reason": "ken_first_close_freeze_edge_search",
                },
            },
        },
        freeze_path=missing,
    )
    assert frozen["state"] == "KEN_FROZEN"
    assert frozen["ken_edge_frozen"] is True
    assert frozen["ken_freeze_reason"] == "ken_first_close_freeze_edge_search"
    assert frozen["registry_bloated_skip"] is False
    assert frozen["registry_over_limit"] is True
    assert frozen["evolve_ran"] == 0


def test_edge_search_health_reads_operator_freeze_file(tmp_path):
    from scripts.trader_go_live_status import edge_search_health

    latch = tmp_path / "edge-search-freeze.json"
    latch.write_text(
        '{"skip_evolve": true, "reason": "ken_first_close_freeze_edge_search"}',
        encoding="utf-8",
    )
    # Alternate-lane cycle would otherwise look OK_PARTIAL / SEARCHING.
    out = edge_search_health(
        {
            "stamp": "20260813T0900",
            "registry_bytes": 1_848_575,
            "registry_max_bytes": 6_000_000,
            "phases": {
                "evolve_csp": {
                    "skipped": True,
                    "reason": "evolve_lanes_one_alternate",
                },
                "evolve_defined_risk": {
                    "skipped": True,
                    "reason": "evolve_lanes_one_alternate",
                },
            },
        },
        freeze_path=latch,
    )
    assert out["state"] == "KEN_FROZEN"
    assert out["ken_edge_frozen"] is True
    assert out["registry_bloated_skip"] is False


def test_format_text_surfaces_edge_search_bloat():
    from scripts.trader_go_live_status import Funnel, format_text

    f = Funnel(
        generated_at="2026-07-31T04:00:00+00:00",
        phase="SHADOW",
        sleeve_plan_usd=3000,
        sleeve_cash_usd=500.0,
        option_level="option_level_2",
        agentic_enabled=False,
        overall_pct=85.0,
        overall_label="NEAR_PACKET",
        activity_pct=35.0,
        activity_label="EDGE_FROZEN_BLOAT",
        next_action="manage_open_paper_campaign",
        ken_required=False,
        layers={
            "edge": {
                "status": "PASS",
                "summary": "pack-grade",
                "paper_research_leader": "hyp_x",
                "first_live_candidate": "AAL short_put_credit",
            },
            "robot": {
                "status": "PASS",
                "summary": "paper=ok; shadow=ok",
                "paper_sessions": 8,
                "paper_sessions_target": 3,
                "shadow": "PASS",
                "live_disarmed": True,
            },
            "arm": {"status": "BLOCKED", "summary": "Ken only"},
        },
        paper={"real_orders": 2, "working": 2, "open_risk_usd": 264.0, "open": []},
        continuum={
            "quality_worker_running": True,
            "quality_cycles_completed": 5900,
            "quality_worker_hb_age_h": 0.0,
            "registry_bloated_skip": True,
            "registry_bytes": 6_002_931,
            "edge_search": {
                "state": "BLOATED_SKIP",
                "registry_bloated_skip": True,
                "registry_bytes": 6_002_931,
            },
        },
        shortlist_top=[],
        blockers=["Real money blocked until Ken LIVE_PACKET arm"],
        path_to_live=["1. EDGE"],
        simple_next="Manage open paper.",
        glossary={
            "EDGE": "sims",
            "ROBOT": "paper+shadow",
            "ARM": "Ken",
            "paper": "fake money",
            "shadow": "log only",
        },
        why_overall_stuck="remaining: arm",
    )
    text = format_text(f)
    assert "edge_search=BLOATED_SKIP" in text
    assert "EDGE frozen" in text
    assert "trader_prune_hyp_registry" in text


def test_format_text_surfaces_ken_freeze_not_prune():
    from scripts.trader_go_live_status import Funnel, format_text

    f = Funnel(
        generated_at="2026-08-13T16:00:00+00:00",
        phase="SHADOW",
        sleeve_plan_usd=3000,
        sleeve_cash_usd=500.0,
        option_level="option_level_2",
        agentic_enabled=False,
        overall_pct=85.0,
        overall_label="NEAR_PACKET",
        activity_pct=35.0,
        activity_label="EDGE_FROZEN_KEN",
        next_action="manage_open_paper_campaign",
        ken_required=False,
        layers={
            "edge": {
                "status": "PASS",
                "summary": "pack-grade",
                "paper_research_leader": "hyp_x",
                "first_live_candidate": "SNAP cash_secured_put",
            },
            "robot": {
                "status": "PASS",
                "summary": "paper=ok; shadow=ok",
                "paper_sessions": 17,
                "paper_sessions_target": 3,
                "shadow": "PASS",
                "live_disarmed": True,
            },
            "arm": {"status": "BLOCKED", "summary": "Ken only"},
        },
        paper={"real_orders": 1, "working": 1, "open_risk_usd": 79.32, "open": []},
        continuum={
            "quality_worker_running": True,
            "quality_cycles_completed": 22284,
            "quality_worker_hb_age_h": 0.02,
            "registry_bloated_skip": False,
            "registry_bytes": 6_000_873,
            "edge_search": {
                "state": "KEN_FROZEN",
                "ken_edge_frozen": True,
                "ken_freeze_reason": "ken_first_close_freeze_edge_search",
                "registry_bloated_skip": False,
                "registry_bytes": 6_000_873,
            },
        },
        shortlist_top=[],
        blockers=["Real money blocked until Ken LIVE_PACKET arm"],
        path_to_live=["1. EDGE"],
        simple_next="Manage open paper.",
        glossary={
            "EDGE": "sims",
            "ROBOT": "paper+shadow",
            "ARM": "Ken",
            "paper": "fake money",
            "shadow": "log only",
        },
        why_overall_stuck="remaining: arm",
    )
    text = format_text(f)
    assert "edge_search=KEN_FROZEN" in text
    assert "do not prune-to-unfreeze" in text
    assert "trader_prune_hyp_registry" not in text
    assert "search EDGE_FROZEN_KEN" in text
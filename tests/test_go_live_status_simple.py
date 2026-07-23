"""Tests for simplified go-live status (3-layer + session spanning)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.trader_go_live_status import (
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
    assert "Keep paper open/managed" in text


def test_same_day_single_session():
    start = datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=3)
    days = market_session_days_spanned(start, end)
    assert len(days) == 1

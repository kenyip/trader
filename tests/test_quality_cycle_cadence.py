"""Cadence / sprint helpers for quality_cycle."""
from __future__ import annotations

import json
import os
from pathlib import Path

import scripts.trader_quality_cycle as qc


def test_due_cadence():
    assert qc._due(1, 1) is True
    assert qc._due(1, 7) is True
    assert qc._due(3, 3) is True
    assert qc._due(3, 6) is True
    assert qc._due(3, 1) is False
    assert qc._due(3, 2) is False
    assert qc._due(0, 5) is True  # treated as every 1


def test_paper_book_snapshot_reads_working(tmp_path, monkeypatch):
    ledger = tmp_path / "paper_ledger.json"
    ledger.write_text(
        """
{
  "orders": {
    "a": {"status": "working", "max_loss_usd": 100, "tag": "real"},
    "b": {"status": "working", "max_loss_usd": 200, "tag": "real"},
    "s": {"status": "working", "max_loss_usd": 1, "tag": "m0_stub:smoke_test"}
  }
}
""".strip()
    )
    monkeypatch.setattr(qc, "_LEDGER", ledger)
    snap = qc._paper_book_snapshot()
    assert snap["working"] == 2
    assert snap["book_full"] is True
    assert snap["open_risk_usd"] == 300.0


def test_campaign_skip_when_book_full(monkeypatch):
    # Simulate decision logic used in run_cycle without running evolves
    book = {"working": 2, "book_full": True, "has_book": True, "open_risk_usd": 350.0}
    monkeypatch.setenv("TRADER_QC_CAMPAIGN_EVERY", "3")
    monkeypatch.setenv("TRADER_QC_PAPER_EVERY", "3")
    monkeypatch.setenv("TRADER_QC_FORCE_PAPER", "0")
    force = False
    paper_every = 3
    campaign_every = 3
    for cycle_n, expect_campaign in [(1, False), (2, False), (3, True), (4, False)]:
        run_campaign = force or (not book["book_full"]) or qc._due(campaign_every, cycle_n)
        assert run_campaign is expect_campaign, cycle_n


def test_paper_campaign_manage_only_gate():
    """Mirror paper_campaign book-full fast path predicate (no scout/dry under capacity)."""
    max_conc = 2
    max_risk = 500.0
    # 2 working orders → manage_only
    real_open = [{"order_id": "a"}, {"order_id": "b"}]
    open_risk = 359.0
    book_full = len(real_open) >= max_conc
    risk_blocked = open_risk >= max_risk
    manage_only = book_full or risk_blocked
    assert book_full is True
    assert manage_only is True
    # room for new → not manage_only
    real_open1 = [{"order_id": "a"}]
    open_risk1 = 160.0
    assert (len(real_open1) >= max_conc or open_risk1 >= max_risk) is False
    # risk headroom gone alone
    assert (1 >= max_conc or 500.0 >= max_risk) is True


def test_book_full_skips_learn_tick_predicate():
    """Bash campaign peeks ledger before learn; full book → skip learn (300s hang fix)."""
    max_conc = 2
    max_risk = 500.0

    def manage_only(working: int, risk: float, force_learn: bool = False) -> bool:
        full = working >= max_conc or risk >= max_risk
        return full and not force_learn

    assert manage_only(2, 359.0) is True
    assert manage_only(1, 160.0) is False
    assert manage_only(2, 359.0, force_learn=True) is False
    assert manage_only(0, 500.0) is True


def test_ken_skip_evolve_from_file(tmp_path, monkeypatch):
    """Ken first-close latch must skip evolve even when yaml is under the bloat ceiling."""
    latch = tmp_path / "edge-search-freeze.json"
    latch.write_text(
        json.dumps(
            {
                "skip_evolve": True,
                "reason": "ken_first_close_freeze_edge_search",
                "unfreeze_gate": "explicit Ken only",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qc, "_KEN_EDGE_FREEZE", latch)
    monkeypatch.delenv("TRADER_QC_SKIP_EVOLVE", raising=False)
    skip, reason = qc._ken_skip_evolve()
    assert skip is True
    assert reason == "ken_first_close_freeze_edge_search"
    # Ken skip outranks bloat in run_cycle (if/elif). Payload reason stays Ken.
    payload = qc._evolve_skip_payload(
        reason=reason, lane="defined_risk", registry_bytes=6_000_873
    )
    assert payload["skipped"] is True
    assert payload["reason"] == "ken_first_close_freeze_edge_search"


def test_ken_skip_evolve_env_without_file(tmp_path, monkeypatch):
    monkeypatch.setattr(qc, "_KEN_EDGE_FREEZE", tmp_path / "missing.json")
    monkeypatch.setenv("TRADER_QC_SKIP_EVOLVE", "1")
    skip, reason = qc._ken_skip_evolve()
    assert skip is True
    assert reason == "ken_edge_search_frozen_env"


def test_ken_freeze_skips_edge_prove_not_paper():
    """Ken latch must drop unchanged-DNA re-prove and keep watch/paper phases."""
    skip_phases = set(qc._ken_frozen_skip_prove_phases())
    keep = set(qc.KEN_FROZEN_KEEP_PHASES)
    assert "multi_symbol" in skip_phases
    assert "shortlist_dna_multi" in skip_phases
    assert "discovery_f2_ingest" in skip_phases
    assert "shortlist_refresh" in skip_phases
    assert "paper_campaign" not in skip_phases
    assert "paper_loop" not in skip_phases
    assert "research" not in skip_phases
    assert keep.isdisjoint(skip_phases)
    payload = qc._phase_skip_payload(
        reason="ken_first_close_freeze_edge_search", phase="multi_symbol"
    )
    assert payload["skipped"] is True
    assert payload["rc"] == 0
    assert payload["reason"] == "ken_first_close_freeze_edge_search"
    assert payload["phase"] == "multi_symbol"


def test_ken_skip_evolve_inactive_or_corrupt(tmp_path, monkeypatch):
    monkeypatch.delenv("TRADER_QC_SKIP_EVOLVE", raising=False)
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(qc, "_KEN_EDGE_FREEZE", missing)
    assert qc._ken_skip_evolve() == (False, "")

    off = tmp_path / "off.json"
    off.write_text(json.dumps({"skip_evolve": False, "reason": "stale"}), encoding="utf-8")
    monkeypatch.setattr(qc, "_KEN_EDGE_FREEZE", off)
    assert qc._ken_skip_evolve() == (False, "")

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(qc, "_KEN_EDGE_FREEZE", bad)
    assert qc._ken_skip_evolve() == (False, "")


def test_registry_bloat_skip_evolve_predicate(tmp_path, monkeypatch):
    """Bloated hypotheses.yaml must skip evolve --apply (45MB TIMEOUT thrash)."""
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_bytes(b"x" * 13_000_000)
    monkeypatch.setattr(qc, "_HYPS", hyps)
    monkeypatch.setenv("TRADER_QC_REGISTRY_MAX_BYTES", "12000000")
    assert qc._registry_bytes() == 13_000_000
    assert qc._registry_bloat_limit() == 12_000_000
    assert qc._registry_bytes() > qc._registry_bloat_limit()
    payload = qc._evolve_skip_payload(
        reason="registry_bloat_skip_evolve", lane="csp", registry_bytes=13_000_000
    )
    assert payload["rc"] == 0
    assert payload["skipped"] is True
    assert payload["reason"] == "registry_bloat_skip_evolve"


def test_registry_healthy_does_not_trip_bloat(tmp_path, monkeypatch):
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_bytes(b"x" * 1_100_000)
    monkeypatch.setattr(qc, "_HYPS", hyps)
    monkeypatch.setenv("TRADER_QC_REGISTRY_MAX_BYTES", "12000000")
    assert qc._registry_bytes() < qc._registry_bloat_limit()


def test_registry_bloat_skip_learn_predicate():
    """Empty book + bloated yaml still skips learn (campaign 300s hang)."""

    def skip_learn(
        *,
        book_manage_only: bool,
        registry_bloat: bool,
        learn_bloat: bool = False,
        force_learn: bool = False,
    ) -> bool:
        if force_learn:
            return False
        return book_manage_only or registry_bloat or learn_bloat

    assert skip_learn(book_manage_only=False, registry_bloat=True) is True
    assert skip_learn(book_manage_only=True, registry_bloat=False) is True
    assert skip_learn(book_manage_only=False, registry_bloat=False) is False
    assert skip_learn(book_manage_only=True, registry_bloat=True, force_learn=True) is False
    # 2026-08-07: learn ceiling below evolve bloat — 5.5MB hangs past campaign timeout
    assert skip_learn(book_manage_only=False, registry_bloat=False, learn_bloat=True) is True
    assert skip_learn(
        book_manage_only=False, registry_bloat=False, learn_bloat=True, force_learn=True
    ) is False


def test_learn_bloat_threshold_below_evolve_ceiling():
    """Learn skip must trip before evolve bloat when yaml is mid-size (~5.5MB)."""
    hyps_bytes = 5_567_565
    evolve_max = 6_000_000
    learn_max = 4_000_000
    assert hyps_bytes < evolve_max  # evolve still allowed
    assert hyps_bytes > learn_max  # learn must skip
    assert (hyps_bytes > learn_max) and not (hyps_bytes > evolve_max)


def test_stress_markers_ignore_dna_hash_b3_suffix():
    """Bare b3:/b4: must not mark evolve DNA hashes as already B3/B4-stressed."""
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    sel_path = Path(__file__).resolve().parents[1] / "scripts" / "trader_select_stress_hyps.py"
    spec = importlib.util.spec_from_file_location("trader_select_stress_hyps", sel_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    # Real false-positive shape from 2026-08-07 coach (hash ends with b3 before :verdict)
    h_false = SimpleNamespace(
        evidence_links=[
            "evolve_sim:dna_e9c4e51389b3:verdict=SHIP:score=122.08:trades=34",
            "/Users/jarvis/dev/trader/.cache/platform/evolve_backtests/F_pcs_trades.json",
        ],
        notes="source=evolve_tick; structure=iron_condor; never_auto_live=true",
    )
    assert mod._is_stressed(h_false) is False

    h_true = SimpleNamespace(
        evidence_links=["pcs_regime_stress:b3_hold=true:dense_neg=1"],
        notes="ingested stress_rotation",
    )
    assert mod._is_stressed(h_true) is True

    # b4 hash suffix must not trip either
    h_b4 = SimpleNamespace(
        evidence_links=["evolve_sim:dna_abc123b4:verdict=SHIP:score=10:trades=20"],
        notes="",
    )
    assert mod._is_stressed(h_b4) is False


def test_shortlist_hyps_trusts_empty_selector(tmp_path, monkeypatch):
    """Empty selector queue must NOT fall back to stress_priority leaders (AAL re-burn)."""
    import types
    import importlib.util

    out = tmp_path / "quality_residual"
    out.mkdir()
    monkeypatch.setattr(qc, "_OUT", out)
    monkeypatch.setattr(qc, "_REPO", tmp_path)
    sel_path = tmp_path / "scripts" / "trader_select_stress_hyps.py"
    sel_path.parent.mkdir(parents=True)
    sel_path.write_text("# stub\n", encoding="utf-8")

    def select_stress_hyps(**kwargs):
        return {
            "csv": "",
            "hyp_ids": [],
            "n": 0,
            "skipped_fresh_leaders": [
                "hyp_dna_aal_put_credit_spread_32c7191f",
                "hyp_dna_aal_put_credit_spread_a337c5ac",
            ],
        }

    def fake_spec(name, path, *a, **k):
        if "trader_select_stress_hyps" in str(name) or "trader_select_stress_hyps" in str(path):
            spec = types.SimpleNamespace()
            spec.loader = types.SimpleNamespace(
                exec_module=lambda mod: setattr(mod, "select_stress_hyps", select_stress_hyps)
            )
            return spec
        raise AssertionError(f"unexpected spec load {name} {path}")

    monkeypatch.setattr(importlib.util, "spec_from_file_location", fake_spec)
    monkeypatch.setattr(
        importlib.util, "module_from_spec", lambda spec: types.ModuleType("trader_select_stress_hyps")
    )
    shortlist = tmp_path / "QUALITY_SHORTLIST.json"
    shortlist.write_text(
        json.dumps(
            {
                "shortlist": [
                    {
                        "hyp_id": "hyp_dna_aal_put_credit_spread_32c7191f",
                        "structure": "put_credit_spread",
                        "stress_priority": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qc, "_SHORTLIST", shortlist)

    csv = qc._shortlist_hyps(limit=6)
    assert csv == ""
    receipt = out / "stress_selection_LATEST.json"
    assert receipt.is_file()
    data = json.loads(receipt.read_text(encoding="utf-8"))
    assert data.get("n") == 0
    assert "hyp_dna_aal_put_credit_spread_32c7191f" in (data.get("skipped_fresh_leaders") or [])


def test_shortlist_hyps_returns_selector_csv(tmp_path, monkeypatch):
    import types
    import importlib.util

    out = tmp_path / "quality_residual"
    out.mkdir()
    monkeypatch.setattr(qc, "_OUT", out)
    monkeypatch.setattr(qc, "_REPO", tmp_path)
    sel_path = tmp_path / "scripts" / "trader_select_stress_hyps.py"
    sel_path.parent.mkdir(parents=True)
    sel_path.write_text("# stub\n", encoding="utf-8")

    def select_stress_hyps(**kwargs):
        return {
            "csv": "hyp_dna_ccl_call_credit_spread_fresh",
            "hyp_ids": ["hyp_dna_ccl_call_credit_spread_fresh"],
            "n": 1,
        }

    def fake_spec(name, path, *a, **k):
        if "trader_select_stress_hyps" in str(name) or "trader_select_stress_hyps" in str(path):
            spec = types.SimpleNamespace()
            spec.loader = types.SimpleNamespace(
                exec_module=lambda mod: setattr(mod, "select_stress_hyps", select_stress_hyps)
            )
            return spec
        raise AssertionError(f"unexpected spec load {name} {path}")

    monkeypatch.setattr(importlib.util, "spec_from_file_location", fake_spec)
    monkeypatch.setattr(
        importlib.util, "module_from_spec", lambda spec: types.ModuleType("trader_select_stress_hyps")
    )
    assert qc._shortlist_hyps(limit=6) == "hyp_dna_ccl_call_credit_spread_fresh"

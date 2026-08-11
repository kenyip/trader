"""Toxic symbol×structure families must not occupy evolve --apply create slots."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from trader_platform.evolve_tick import SimVerdict, apply_results
from trader_platform.hypothesis_registry import HypothesisRegistry
from trader_platform.strategy_dna import dna_from_structure


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _verdict(sym: str, structure: str, score: float, verdict: str = "SHIP") -> SimVerdict:
    dna = dna_from_structure(structure, [sym])
    return SimVerdict(
        dna=dna,
        ok=True,
        skipped=False,
        reason="positive_sim",
        n_trades=40,
        metrics={"pnl": 100.0, "max_dd": 50.0},
        score=score,
        verdict=verdict,
        evidence_path="",
    )


def test_apply_skips_toxic_family_creates(tmp_path: Path):
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
    reg = HypothesisRegistry(hyps)
    now = _now()
    # Synthetic rotation: NFLX CCS is toxic (many recent fails, 0 ok); BAC PCS clean.
    rotation = {
        "by_hyp_id": {
            f"hyp_dna_nflx_call_credit_spread_{i:02d}": {
                "hyp_id": f"hyp_dna_nflx_call_credit_spread_{i:02d}",
                "symbol": "NFLX",
                "structure": "call_credit_spread",
                "capital_path_ok": False,
                "stressed_at": now,
            }
            for i in range(10)
        }
    }
    results = [
        _verdict("NFLX", "call_credit_spread", 300.0),
        _verdict("NFLX", "call_credit_spread", 280.0),
        _verdict("BAC", "put_credit_spread", 12.0),
    ]
    created, updated = apply_results(
        results,
        registry=reg,
        max_create=5,
        ship_only=False,
        rotation=rotation,
        skip_toxic_families=True,
    )
    assert updated == []
    assert len(created) == 1
    assert "bac" in created[0]
    assert not any("nflx" in c for c in created)


def test_apply_toxic_skip_does_not_consume_max_create_budget(tmp_path: Path):
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
    reg = HypothesisRegistry(hyps)
    now = _now()
    rotation = {
        "by_hyp_id": {
            f"hyp_dna_pltr_call_credit_spread_{i:02d}": {
                "symbol": "PLTR",
                "structure": "call_credit_spread",
                "capital_path_ok": False,
                "stressed_at": now,
            }
            for i in range(12)
        }
    }
    # Three toxic tops then two good — max_create=2 must still get both good.
    results = [
        _verdict("PLTR", "call_credit_spread", 400.0),
        _verdict("PLTR", "call_credit_spread", 390.0),
        _verdict("PLTR", "call_credit_spread", 380.0),
        _verdict("BAC", "put_credit_spread", 20.0),
        _verdict("AAL", "put_credit_spread", 18.0),
    ]
    created, _ = apply_results(
        results,
        registry=reg,
        max_create=2,
        rotation=rotation,
        skip_toxic_families=True,
    )
    assert len(created) == 2
    joined = " ".join(created)
    assert "bac" in joined and "aal" in joined
    assert "pltr" not in joined


def test_apply_skips_hot_fail_streak_family_creates(tmp_path: Path):
    """Recent capital_path fail streak blocks creates even with historic oks."""
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
    reg = HypothesisRegistry(hyps)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    by = {}
    # Historic ok keeps lifetime rate healthy
    by["hyp_dna_aal_call_credit_spread_old_ok"] = {
        "symbol": "AAL",
        "structure": "call_credit_spread",
        "capital_path_ok": True,
        "stressed_at": (now.replace(year=2026, month=7, day=20)).isoformat(),
    }
    # Newest 7 fails (24h) → hot streak toxic
    for i in range(7):
        by[f"hyp_dna_aal_call_credit_spread_hot{i}"] = {
            "symbol": "AAL",
            "structure": "call_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now.isoformat(),
        }
    results = [
        _verdict("AAL", "call_credit_spread", 50.0),
        _verdict("F", "put_credit_spread", 12.0),
    ]
    created, _ = apply_results(
        results,
        registry=reg,
        max_create=3,
        ship_only=True,
        rotation={"by_hyp_id": by},
        skip_toxic_families=True,
    )
    assert len(created) == 1
    assert "f_" in created[0] or "put_credit_spread" in created[0]
    assert not any("aal" in c and "call_credit" in c for c in created)


def test_apply_skips_saturated_family_creates_prefers_unsaturated(tmp_path: Path):
    """Many capital_path_ok survivors block new clones; unsaturated family wins budget."""
    hyps = tmp_path / "hypotheses.yaml"
    # Pre-seed living AAL PCS dens (≥ min_living) so ledger saturation still holds.
    # Ghost-prune reopen only when living count is below the floor (2026-08-10 coach).
    living_rows = []
    for i in range(5):
        living_rows.append(
            {
                "id": f"hyp_dna_aal_put_credit_spread_live{i:02d}",
                "name": f"seed aal pcs {i}",
                "thesis": "seed",
                "sleeve": "premium",
                "instruments": ["AAL"],
                "entry_logic_ref": "x",
                "exit_logic_ref": "y",
                "status": "candidate",
                "evidence_links": ["seed"],
                "null_results": [],
                "notes": "structure=put_credit_spread",
                "dna": {
                    "structure": "put_credit_spread",
                    "symbols": ["AAL"],
                    "dna_id": f"dna_live_aal_pcs_{i:02d}",
                    "config": {"spread_width": 1.0 + 0.1 * i},
                },
            }
        )
    import yaml

    hyps.write_text(
        yaml.safe_dump({"version": 1, "hypotheses": living_rows}, sort_keys=False),
        encoding="utf-8",
    )
    reg = HypothesisRegistry(hyps)
    now = _now()
    by = {
        f"hyp_dna_aal_put_credit_spread_ok{i:02d}": {
            "hyp_id": f"hyp_dna_aal_put_credit_spread_ok{i:02d}",
            "symbol": "AAL",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
        for i in range(30)  # >= default min_capital_path_ok=25
    }
    # High-score saturated AAL PCS clones should lose to lower-score F CCS.
    results = [
        _verdict("AAL", "put_credit_spread", 400.0),
        _verdict("AAL", "put_credit_spread", 390.0),
        _verdict("F", "call_credit_spread", 40.0),
    ]
    created, updated = apply_results(
        results,
        registry=reg,
        max_create=2,
        ship_only=True,
        rotation={"by_hyp_id": by},
        skip_toxic_families=True,
    )
    assert updated == []
    assert len(created) == 1
    assert "f_" in created[0]
    assert "call_credit" in created[0]
    assert not any("aal" in c for c in created)


def test_apply_saturated_skip_does_not_consume_max_create_budget(tmp_path: Path):
    import yaml

    living_rows = []
    for i in range(5):
        living_rows.append(
            {
                "id": f"hyp_dna_bac_put_credit_spread_live{i:02d}",
                "name": f"seed bac pcs {i}",
                "thesis": "seed",
                "sleeve": "premium",
                "instruments": ["BAC"],
                "entry_logic_ref": "x",
                "exit_logic_ref": "y",
                "status": "candidate",
                "evidence_links": ["seed"],
                "null_results": [],
                "notes": "structure=put_credit_spread",
                "dna": {
                    "structure": "put_credit_spread",
                    "symbols": ["BAC"],
                    "dna_id": f"dna_live_bac_pcs_{i:02d}",
                    "config": {"spread_width": 1.0 + 0.1 * i},
                },
            }
        )
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text(
        yaml.safe_dump({"version": 1, "hypotheses": living_rows}, sort_keys=False),
        encoding="utf-8",
    )
    reg = HypothesisRegistry(hyps)
    now = _now()
    by = {
        f"hyp_dna_bac_put_credit_spread_ok{i:02d}": {
            "symbol": "BAC",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
        for i in range(25)
    }
    results = [
        _verdict("BAC", "put_credit_spread", 500.0),
        _verdict("BAC", "put_credit_spread", 490.0),
        _verdict("SNAP", "put_credit_spread", 15.0),
        _verdict("F", "call_credit_spread", 12.0),
    ]
    created, _ = apply_results(
        results,
        registry=reg,
        max_create=2,
        ship_only=True,
        rotation={"by_hyp_id": by},
        skip_toxic_families=True,
    )
    assert len(created) == 2
    joined = " ".join(created)
    assert "snap" in joined and ("f_" in joined or "call_credit" in joined)
    assert "bac" not in joined


def test_apply_existing_updates_do_not_consume_max_create_budget(tmp_path: Path):
    """Re-sim updates of known DNA must not starve unsaturated creates (coach 2026-08-10)."""
    from trader_platform.evolve_tick import hyp_id_for_dna

    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
    reg = HypothesisRegistry(hyps)
    # Pre-register two high-score DNA rows (already in registry = update path).
    v_arm = _verdict("ARM", "call_credit_spread", 495.0)
    v_aal = _verdict("AAL", "iron_condor", 109.0)
    for v in (v_arm, v_aal):
        dna = v.dna
        reg.add(
            hypothesis_id=hyp_id_for_dna(dna),
            name=f"seed {dna.structure}",
            thesis="seed",
            sleeve="premium",
            instruments=list(dna.symbols),
            entry_logic_ref="x",
            exit_logic_ref="y",
            status="candidate",
            evidence_links=["seed"],
            notes=f"structure={dna.structure}",
            dna=dna.to_dict(),
        )
    # Top SHIPs are updates; unsaturated KO/SOFI must still create under max_create=2.
    results = [
        v_arm,
        v_aal,
        _verdict("KO", "iron_condor", 33.0),
        _verdict("SOFI", "call_credit_spread", 28.0),
        _verdict("XOM", "call_credit_spread", 22.0),
    ]
    created, updated = apply_results(
        results,
        registry=reg,
        max_create=2,
        ship_only=True,
        rotation={"by_hyp_id": {}},
        skip_toxic_families=True,
    )
    assert hyp_id_for_dna(v_arm.dna) in updated
    assert hyp_id_for_dna(v_aal.dna) in updated
    assert len(created) == 2
    joined = " ".join(created)
    assert "ko" in joined or "sofi" in joined
    assert "arm" not in joined
    # Third new family must not exceed max_create
    assert "xom" not in joined


def test_family_create_saturated_threshold():
    from trader_platform.stress_family_policy import family_create_saturated

    now = _now()
    by = {
        f"h{i}": {
            "symbol": "X",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
        for i in range(24)
    }
    rot = {"by_hyp_id": by}
    assert not family_create_saturated("X", "put_credit_spread", rotation=rot, min_capital_path_ok=25)
    by["h24"] = {
        "symbol": "X",
        "structure": "put_credit_spread",
        "capital_path_ok": True,
        "stressed_at": now,
    }
    assert family_create_saturated("X", "put_credit_spread", rotation=rot, min_capital_path_ok=25)


def test_family_create_saturated_ghost_prune_reopen():
    """Ledger ≥25 oks must not saturate when living registry DNA is gone (prune)."""
    from trader_platform.stress_family_policy import (
        family_create_saturated,
        living_multi_leg_family_counts,
        unsaturated_discovery_families,
    )

    now = _now()
    by = {
        f"snap{i}": {
            "symbol": "SNAP",
            "structure": "call_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
        for i in range(25)
    }
    rot = {"by_hyp_id": by}
    # Legacy ledger-only: still saturated.
    assert family_create_saturated(
        "SNAP", "call_credit_spread", rotation=rot, min_capital_path_ok=25
    )
    # Ghost-prune: 0 living rows → reopen creates.
    assert not family_create_saturated(
        "SNAP",
        "call_credit_spread",
        rotation=rot,
        min_capital_path_ok=25,
        living_count=0,
    )
    assert not family_create_saturated(
        "SNAP",
        "call_credit_spread",
        rotation=rot,
        min_capital_path_ok=25,
        living_count=2,
        min_living=3,
    )
    # Living dens clones still block.
    assert family_create_saturated(
        "SNAP",
        "call_credit_spread",
        rotation=rot,
        min_capital_path_ok=25,
        living_count=5,
        min_living=3,
    )
    live = living_multi_leg_family_counts(
        [
            {
                "id": "hyp_dna_aal_put_credit_spread_x",
                "dna": {"structure": "put_credit_spread", "symbols": ["AAL"]},
            }
        ]
    )
    assert live.get(("AAL", "put_credit_spread")) == 1
    fams = unsaturated_discovery_families(
        limit=6,
        rotation=rot,
        universe=["SNAP", "ZZZ"],
        structures=("call_credit_spread", "put_credit_spread"),
        living_family_counts={("SNAP", "call_credit_spread"): 0},
    )
    assert any(
        f.get("symbol") == "SNAP" and f.get("structure") == "call_credit_spread" for f in fams
    ), fams
    # Living count above floor keeps SNAP ghost-sat closed.
    fams_closed = unsaturated_discovery_families(
        limit=6,
        rotation=rot,
        universe=["SNAP"],
        structures=("call_credit_spread",),
        living_family_counts={("SNAP", "call_credit_spread"): 10},
    )
    assert not any(f.get("symbol") == "SNAP" for f in fams_closed), fams_closed


def test_unsaturated_discovery_symbols_skips_toxic_and_saturated():
    from trader_platform.stress_family_policy import unsaturated_discovery_symbols

    now = _now()
    by = {}
    # AAL PCS saturated (25 oks)
    for i in range(25):
        by[f"aal{i}"] = {
            "symbol": "AAL",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
    # AAL CCS also saturated so AAL has no open ML struct
    for i in range(25):
        by[f"aal_c{i}"] = {
            "symbol": "AAL",
            "structure": "call_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
    # NFLX CCS toxic: many fails, 0 ok
    for i in range(25):
        by[f"nflx{i}"] = {
            "symbol": "NFLX",
            "structure": "call_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now,
        }
    # SNAP PCS unsaturated (3 oks)
    for i in range(3):
        by[f"snap{i}"] = {
            "symbol": "SNAP",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
    rot = {"by_hyp_id": by}
    out = unsaturated_discovery_symbols(
        limit=6,
        rotation=rot,
        universe=["AAL", "NFLX", "SNAP", "ZZZ"],
        structures=("put_credit_spread", "call_credit_spread"),
    )
    assert "SNAP" in out
    assert "AAL" not in out
    # SNAP has proven oks → tier0; cold ZZZ/NFLX PCS → tier1
    assert out[0] == "SNAP"


def test_unsaturated_discovery_skips_recent_fail_thrash_cold_names():
    """Cold mega-caps with only recent fails must not crowd unsat inject (2026-07-30T1500)."""
    from trader_platform.stress_family_policy import unsaturated_discovery_symbols

    now = _now()
    by = {}
    # AMD PCS: 6 recent fails, 0 ok — thrash
    for i in range(6):
        by[f"amd{i}"] = {
            "symbol": "AMD",
            "structure": "put_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now,
        }
    # KO PCS: cold, never stressed — allowed
    # SNAP PCS: 2 recent oks — proven unsaturated tier0
    for i in range(2):
        by[f"snap{i}"] = {
            "symbol": "SNAP",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
    rot = {"by_hyp_id": by}
    out = unsaturated_discovery_symbols(
        limit=6,
        rotation=rot,
        universe=["AMD", "KO", "SNAP"],
        structures=("put_credit_spread", "call_credit_spread"),
        recent_fail_thrash_min=6,
    )
    assert "AMD" not in out
    assert "SNAP" in out
    assert out[0] == "SNAP"
    assert "KO" in out


def test_unsaturated_cold_prefers_liquid_over_alphabetical_mega():
    """When tier-0 empty, cold inject must not alphabetical-AMD/AVGO starve F/KO/IWM (2026-08-03)."""
    from trader_platform.stress_family_policy import (
        unsaturated_discovery_families,
        unsaturated_discovery_symbols,
    )

    # Empty rotation: every name is cold tier-1 open.
    rot = {"by_hyp_id": {}}
    universe = ["AMD", "AVGO", "GOOGL", "F", "KO", "IWM", "META"]
    syms = unsaturated_discovery_symbols(
        limit=4,
        rotation=rot,
        universe=universe,
        structures=("put_credit_spread", "call_credit_spread", "iron_condor"),
    )
    assert syms[0] in {"F", "KO", "IWM"}
    assert "AMD" not in syms[:3]
    assert "AVGO" not in syms[:3]
    fams = unsaturated_discovery_families(
        limit=6,
        rotation=rot,
        universe=universe,
        structures=("put_credit_spread", "call_credit_spread", "iron_condor"),
    )
    fam_syms = [f["symbol"] for f in fams]
    assert fam_syms
    assert fam_syms[0] in {"F", "KO", "IWM"}
    assert "AMD" not in fam_syms[:4]
    assert "AVGO" not in fam_syms[:4]
    # Preferred cold can fill beyond old cold_cap=2 when tier0 empty.
    assert len(fams) >= 4


def test_effective_discovery_universe_unions_preferred_cold():
    """Default unsat path must see preferred KO/INTC even if research list omits them (2026-08-07)."""
    from trader_platform.stress_family_policy import (
        _PREFERRED_COLD_DISCOVERY,
        _effective_discovery_universe,
        unsaturated_discovery_families,
        unsaturated_discovery_symbols,
    )

    # Research-like list missing KO/INTC (pre-fix universe.yaml pathology).
    base = ["MU", "TSLA", "AAPL", "AMD", "SPY"]
    eff = _effective_discovery_universe(base)
    assert "KO" in eff and "INTC" in eff
    assert eff.index("MU") < eff.index("KO")  # base order preserved, preferred appended
    for s in _PREFERRED_COLD_DISCOVERY:
        assert s in eff

    # Live rotation: KO PCS is the only tier-0 open preferred; mega cold must not lead.
    now = _now()
    by = {
        "ko_ok": {
            "symbol": "KO",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        },
        "ko_fail": {
            "symbol": "KO",
            "structure": "put_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now,
        },
    }
    rot = {"by_hyp_id": by}
    # Explicit universe without KO — still need default-path union for production.
    # Simulate default path by passing universe=None with monkeypatched loader via rotation-only:
    # Use _effective_discovery_universe + families on merged list.
    merged = _effective_discovery_universe(base)
    fams = unsaturated_discovery_families(
        limit=6,
        rotation=rot,
        universe=merged,
        structures=("put_credit_spread", "call_credit_spread", "iron_condor"),
    )
    assert fams
    assert fams[0]["symbol"] == "KO"
    assert fams[0]["structure"] == "put_credit_spread"
    assert fams[0]["tier"] == 0
    syms = unsaturated_discovery_symbols(
        limit=4,
        rotation=rot,
        universe=merged,
        structures=("put_credit_spread", "call_credit_spread", "iron_condor"),
    )
    assert syms[0] == "KO"


def test_unsaturated_families_keep_open_sibling_when_other_structure_toxic():
    """INTC PCS toxic thrash must not hide open INTC IC from family inject (2026-08-08)."""
    from trader_platform.stress_family_policy import unsaturated_discovery_families

    now = _now()
    by = {}
    # INTC PCS: recent fail thrash (toxic via hot streak / fail mass)
    for i in range(8):
        by[f"intc_pcs{i}"] = {
            "symbol": "INTC",
            "structure": "put_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now,
        }
    # INTC IC: only 3 fails — still open, not family-thrashed
    for i in range(3):
        by[f"intc_ic{i}"] = {
            "symbol": "INTC",
            "structure": "iron_condor",
            "capital_path_ok": False,
            "stressed_at": now,
        }
    # MU cold open — mega demote should not beat preferred INTC IC
    rot = {"by_hyp_id": by}
    fams = unsaturated_discovery_families(
        limit=6,
        rotation=rot,
        universe=["MU", "TSLA", "INTC", "AMD"],
        structures=("put_credit_spread", "call_credit_spread", "iron_condor"),
        recent_fail_thrash_min=6,
    )
    assert fams
    pairs = {(f["symbol"], f["structure"]) for f in fams}
    assert ("INTC", "iron_condor") in pairs
    assert ("INTC", "put_credit_spread") not in pairs  # toxic / thrash


def test_run_evolve_tick_force_symbols_skips_research(monkeypatch):
    import trader_platform.evolve_tick as ev

    calls = {}

    def fake_top(**kwargs):
        calls["top"] = True
        return [{"symbol": "NFLX", "strategy_family": "x", "composite": 99}]

    def fake_build(rows, **kwargs):
        calls["syms"] = [r["symbol"] for r in rows]
        return []

    monkeypatch.setattr(ev, "top_research_symbols", fake_top)
    monkeypatch.setattr(ev, "build_population", fake_build)
    monkeypatch.setattr(ev, "sim_dna", lambda *a, **k: None)
    rep = ev.run_evolve_tick(
        apply=False,
        force_symbols=["SNAP", "CCL"],
        unsat_extra=0,
        max_population=4,
    )
    assert "top" not in calls
    assert calls["syms"] == ["SNAP", "CCL"]
    assert rep.symbols == ["SNAP", "CCL"]


def test_run_evolve_tick_injects_unsaturated(monkeypatch):
    import trader_platform.evolve_tick as ev

    monkeypatch.setattr(
        ev,
        "top_research_symbols",
        lambda **k: [{"symbol": "AAL", "strategy_family": "x", "composite": 1}],
    )
    monkeypatch.setattr(
        "trader_platform.stress_family_policy.unsaturated_discovery_families",
        lambda **k: [
            {"symbol": "SNAP", "structure": "put_credit_spread", "tier": 0, "lifetime_ok": 3},
            {"symbol": "CCL", "structure": "put_credit_spread", "tier": 0, "lifetime_ok": 2},
            {"symbol": "F", "structure": "call_credit_spread", "tier": 0, "lifetime_ok": 5},
        ],
    )
    captured = {}

    def fake_build(rows, **kwargs):
        captured["rows"] = list(rows)
        captured["syms"] = [r["symbol"] for r in rows]
        return []

    monkeypatch.setattr(ev, "build_population", fake_build)
    rep = ev.run_evolve_tick(apply=False, top_symbols=1, unsat_extra=2, max_population=4)
    assert "AAL" in captured["syms"]
    assert "SNAP" in captured["syms"] and "CCL" in captured["syms"]
    assert "SNAP" in rep.symbols
    # Family inject carries force_structure (not toxic twin of open family).
    forced = {
        (r.get("symbol"), r.get("force_structure") or r.get("structure"))
        for r in captured["rows"]
        if str(r.get("source") or "").startswith("unsaturated_discovery")
    }
    assert ("SNAP", "put_credit_spread") in forced
    assert ("F", "call_credit_spread") in forced


def test_unsaturated_discovery_families_open_structure_only():
    """F PCS toxic + F CCS open → families list CCS only (2026-07-31 coach)."""
    from trader_platform.stress_family_policy import unsaturated_discovery_families

    now = _now()
    by = {}
    for i in range(25):
        by[f"fpcs{i}"] = {
            "symbol": "F",
            "structure": "put_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now,
        }
    for i in range(5):
        by[f"fccs{i}"] = {
            "symbol": "F",
            "structure": "call_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
    for i in range(3):
        by[f"snap{i}"] = {
            "symbol": "SNAP",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        }
    rot = {"by_hyp_id": by}
    out = unsaturated_discovery_families(
        limit=8,
        rotation=rot,
        universe=["F", "SNAP", "NFLX"],
        structures=("put_credit_spread", "call_credit_spread"),
    )
    pairs = {(r["symbol"], r["structure"]) for r in out}
    assert ("F", "call_credit_spread") in pairs
    assert ("F", "put_credit_spread") not in pairs
    assert ("SNAP", "put_credit_spread") in pairs


def test_seed_population_includes_loose_entry_for_credit_spreads():
    """Catalog 0.18×$2 defaults zero-trade on F; loose base must also be seeded."""
    import random

    from trader_platform.strategy_dna import seed_population

    pop = seed_population(
        ["F"],
        structures=["call_credit_spread"],
        mutants_per_seed=0,
        rng=random.Random(0),
    )
    assert len(pop) == 2
    widths = sorted(float(d.config.get("spread_width") or 0) for d in pop)
    credits = sorted(float(d.config.get("min_credit_pct") or 0) for d in pop)
    assert min(widths) <= 1.0 + 1e-9
    assert min(credits) <= 0.10 + 1e-9
    assert any(bool(d.config.get("call_in_bull_ok", False)) for d in pop)
    assert any("loose_entry_seed" in (d.notes or "") for d in pop)


def test_seed_population_includes_loose_entry_for_iron_condor():
    """IC catalog 0.14×$2 also zero-trades SNAP; need loose IC base (2026-07-31T2100)."""
    import random

    from trader_platform.strategy_dna import seed_population

    pop = seed_population(
        ["SNAP"],
        structures=["iron_condor"],
        mutants_per_seed=0,
        rng=random.Random(0),
    )
    assert len(pop) == 2
    assert any("loose_entry_seed" in (d.notes or "") for d in pop)
    assert min(float(d.config.get("spread_width") or 99) for d in pop) <= 1.0 + 1e-9
    assert min(float(d.config.get("min_credit_pct") or 99) for d in pop) <= 0.08 + 1e-9


def test_unsaturated_discovery_families_caps_cold_tier():
    """Cold mega-caps must not crowd inject after proven tier-0 (2026-07-31/08-03)."""
    from trader_platform.stress_family_policy import unsaturated_discovery_families

    now = _now()
    by = {
        "f0": {
            "symbol": "F",
            "structure": "call_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        },
        "c0": {
            "symbol": "CCL",
            "structure": "put_credit_spread",
            "capital_path_ok": True,
            "stressed_at": now,
        },
    }
    # Many cold mega names with zero oks — without demote they fill the whole limit.
    for sym in ("AVGO", "DIA", "GOOGL", "JPM", "META", "NVDA"):
        by[f"{sym}_c"] = {
            "symbol": sym,
            "structure": "call_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now,
        }
        by[f"{sym}_p"] = {
            "symbol": sym,
            "structure": "put_credit_spread",
            "capital_path_ok": False,
            "stressed_at": now,
        }
    out = unsaturated_discovery_families(
        limit=8,
        rotation={"by_hyp_id": by},
        universe=["F", "CCL", "AVGO", "DIA", "GOOGL", "JPM", "META", "NVDA"],
        structures=("put_credit_spread", "call_credit_spread"),
        # no recent thrash filter noise
        recent_fail_thrash_min=99,
    )
    pairs = [(r["symbol"], r["structure"], r["tier"]) for r in out]
    assert any(p[0] == "F" and p[2] == 0 for p in pairs)
    assert any(p[0] == "CCL" and p[2] == 0 for p in pairs)
    mega = {"AVGO", "DIA", "GOOGL", "JPM", "META", "NVDA"}
    n_mega_cold = sum(1 for p in pairs if p[2] >= 1 and p[0] in mega)
    # Non-preferred cold still capped; preferred cold (F/CCL open twins) may add.
    assert n_mega_cold <= max(2, 8 // 3)
    assert len(out) <= 8
    # Tier-0 leaders stay ahead of mega cold.
    assert pairs[0][2] == 0


def test_build_population_registry_family_seeds(monkeypatch, tmp_path):
    """Unsat force_structure rows should pull living registry DNA when present."""
    import trader_platform.evolve_tick as ev
    from trader_platform.hypothesis_registry import HypothesisRegistry
    from trader_platform.strategy_dna import dna_from_structure

    reg_path = tmp_path / "hyps.yaml"
    reg = HypothesisRegistry(reg_path)
    reg.ensure_seeded()
    base = dna_from_structure(
        "call_credit_spread",
        ["F"],
        config_overrides={"spread_width": 0.5, "min_credit_pct": 0.18, "call_in_bull_ok": True},
    )
    reg.add(
        name="F CCS test",
        thesis="test",
        sleeve="tactical",
        instruments=["F"],
        status="candidate",
        hypothesis_id="hyp_dna_f_call_credit_spread_testseed",
        dna=base.to_dict(),
    )
    monkeypatch.setattr(ev, "HypothesisRegistry", lambda *a, **k: HypothesisRegistry(reg_path))
    pop = ev.build_population(
        [
            {
                "symbol": "F",
                "force_structure": "call_credit_spread",
                "structure": "call_credit_spread",
                "source": "unsaturated_discovery_family",
            }
        ],
        structures=["call_credit_spread"],
        mutants_per_seed=0,
        seed=1,
        registry_seed_limit=2,
    )
    assert any("registry_family_seed" in (d.notes or "") for d in pop)
    assert any(abs(float(d.config.get("spread_width") or 0) - 0.5) < 1e-9 for d in pop)


def test_quality_cycle_dr_structures_include_iron_condor():
    """DR lane must allow IC so unsat SNAP/F/CCL IC inject is not filtered out."""
    from pathlib import Path

    src = Path("scripts/trader_quality_cycle.py").read_text(encoding="utf-8")
    # Find the _evolve_dr command list literal region
    assert "def _evolve_dr()" in src
    start = src.index("def _evolve_dr()")
    chunk = src[start : start + 900]
    assert '"iron_condor"' in chunk or "'iron_condor'" in chunk
    assert '"put_credit_spread"' in chunk
    assert '"call_credit_spread"' in chunk


def test_unsaturated_with_ic_surfaces_current_open_families():
    """Live-ledger ordering may rotate; IC must remain eligible when requested."""
    from trader_platform.stress_family_policy import unsaturated_discovery_families

    out = unsaturated_discovery_families(
        limit=8,
        structures=("put_credit_spread", "call_credit_spread", "iron_condor"),
        use_registry_living_counts=True,
    )
    pairs = [(r.get("symbol"), r.get("structure")) for r in out]
    structs = {p[1] for p in pairs}
    # Ghost-prune reopen + preferred cold should surface IC and/or PFE-class families.
    # Exact open symbol rotates with the live ledger — assert policy, not a dated order.
    assert "iron_condor" in structs or any(p[0] == "PFE" for p in pairs)
    assert pairs, "expected at least one open multi-leg family"

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
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
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
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
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
        "trader_platform.stress_family_policy.unsaturated_discovery_symbols",
        lambda **k: ["SNAP", "CCL"],
    )
    captured = {}

    def fake_build(rows, **kwargs):
        captured["syms"] = [r["symbol"] for r in rows]
        return []

    monkeypatch.setattr(ev, "build_population", fake_build)
    rep = ev.run_evolve_tick(apply=False, top_symbols=1, unsat_extra=2, max_population=4)
    assert "AAL" in captured["syms"]
    assert "SNAP" in captured["syms"] and "CCL" in captured["syms"]
    assert "SNAP" in rep.symbols

"""Vanity SHIP (score<=0) must not occupy evolve --apply registry create slots."""
from __future__ import annotations

from pathlib import Path

from trader_platform.evolve_tick import SimVerdict, apply_results
from trader_platform.hypothesis_registry import HypothesisRegistry
from trader_platform.strategy_dna import dna_from_structure


def _verdict(sym: str, score: float, verdict: str = "SHIP") -> SimVerdict:
    dna = dna_from_structure("put_credit_spread", [sym])
    return SimVerdict(
        dna=dna,
        ok=True,
        skipped=False,
        reason="positive_sim",
        n_trades=40,
        metrics={"pnl": 100.0 if score > 0 else 50.0, "max_dd": 200.0},
        score=score,
        verdict=verdict,
        evidence_path="",
    )


def test_apply_skips_negative_score_ship(tmp_path: Path):
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text(
        "version: 1\nhypotheses: []\n",
        encoding="utf-8",
    )
    reg = HypothesisRegistry(hyps)
    # max_create would fill with vanity SHIPs first if rank only used verdict.
    results = [
        _verdict("PLTR", -49.0),
        _verdict("SMCI", -74.0),
        _verdict("XOM", -127.0),
        _verdict("BAC", 7.8),
        _verdict("AAL", -200.0),
    ]
    created, updated = apply_results(
        results,
        registry=reg,
        max_create=5,
        ship_only=False,
        rotation={},  # isolate vanity gates from live STRESS_ROTATION saturation
    )
    assert updated == []
    assert len(created) == 1
    assert any("bac" in c for c in created)
    assert not any(x in " ".join(created) for x in ("pltr", "smci", "xom", "aal"))


def test_apply_ship_only_also_skips_vanity(tmp_path: Path):
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
    reg = HypothesisRegistry(hyps)
    created, _ = apply_results(
        [_verdict("PLTR", -10.0), _verdict("BAC", 12.0)],
        registry=reg,
        max_create=5,
        ship_only=True,
        rotation={},
    )
    assert len(created) == 1
    assert "bac" in created[0]


def test_apply_skips_thin_needs_and_neg_score_creates(tmp_path: Path):
    """Thin NEEDS (n<6) and score<=0 must not mint rows the stress selector cannot queue."""
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
    reg = HypothesisRegistry(hyps)

    def _v(sym: str, score: float, n: int, verdict: str) -> SimVerdict:
        dna = dna_from_structure("put_credit_spread", [sym])
        return SimVerdict(
            dna=dna,
            ok=True,
            skipped=False,
            reason="positive_sim",
            n_trades=n,
            metrics={"pnl": 10.0, "max_dd": 20.0},
            score=score,
            verdict=verdict,
            evidence_path="",
        )

    results = [
        _v("XOM", -1.68, 3, "NEEDS_MORE_DATA"),  # thin + neg
        _v("AAL", 3.38, 5, "NEEDS_MORE_DATA"),  # thin positive NEEDS
        _v("SOFI", 20.0, 14, "NEEDS_MORE_DATA"),  # dense NEEDS ok when not ship_only
        _v("BAC", 12.0, 40, "SHIP"),  # good SHIP
    ]
    created, _ = apply_results(
        results, registry=reg, max_create=5, ship_only=False, rotation={}
    )
    joined = " ".join(created)
    assert "bac" in joined
    assert "sofi" in joined
    assert "xom" not in joined
    assert "aal" not in joined
    # ship_only drops dense NEEDS too
    hyps.write_text("version: 1\nhypotheses: []\n", encoding="utf-8")
    reg2 = HypothesisRegistry(hyps)
    created2, _ = apply_results(
        results, registry=reg2, max_create=5, ship_only=True, rotation={}
    )
    assert len(created2) == 1
    assert "bac" in created2[0]

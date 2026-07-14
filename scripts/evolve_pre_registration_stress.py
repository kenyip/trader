#!/usr/bin/env python3
"""Stress dry-run evolve SHIPs before any hypothesis-registry write.

This is a research-only reject gate. Candidates are selected on an evolve sample that
can overlap the stress history, so even a complete proxy-gate pass remains ineligible
for registration until a chronological train/untouched-holdout confirmation exists.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data import build  # noqa: E402
from scripts.defined_risk_fixed_cost_stress import _run as run_fixed_cost  # noqa: E402
from scripts.pcs_cost_stress import _metrics_row, stress_hyp  # noqa: E402
from scripts.pcs_regime_stress import stress_one  # noqa: E402
from trader_platform.evolve_tick import MIN_TRADES_SHIP  # noqa: E402
from trader_platform.strategy_dna import StrategyDNA  # noqa: E402

SUPPORTED_STRUCTURES = {
    "put_credit_spread",
    "call_credit_spread",
    "iron_condor",
    "butterfly_spread",
    "iron_butterfly",
    "broken_wing_iron_butterfly",
    "calendar_spread",
    "diagonal_spread",
    "bull_call_debit_spread",
    "bear_put_debit_spread",
    "put_ratio_backspread",
}
DEFAULT_SLIPS = [0.0, 0.02, 0.05, 0.10]
FIXED_HALF_SPREAD = 0.01
SLEEVE_USD = 3000.0
OPEN_RISK_BUDGET_USD = 750.0
MAX_LOSS_USD = 300.0
MAX_WINDOW_DD_USD = 75.0
MAX_DENSE_NEGATIVE_WINDOWS = 5
OPERATING_MAX_LOTS = 1


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def load_ship_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return structure-pure dry-run SHIPs as transient hypothesis-shaped rows."""
    if payload.get("applied") is not False or payload.get("dry_run") is not True:
        raise ValueError("evolve report must prove dry-run=true/applied=false")
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in payload.get("results") or []:
        if not isinstance(result, dict) or result.get("verdict") != "SHIP":
            continue
        raw_dna = result.get("dna")
        if not isinstance(raw_dna, dict):
            raise ValueError("SHIP result missing DNA")
        dna = StrategyDNA.from_dict(raw_dna)
        if dna is None:
            raise ValueError("SHIP result has invalid DNA")
        dna_id = dna.ensure_id()
        if dna_id in seen:
            continue
        seen.add(dna_id)
        if dna.structure not in SUPPORTED_STRUCTURES:
            raise ValueError(f"unsupported SHIP structure: {dna.structure}")
        if len(dna.symbols or []) != 1:
            raise ValueError(f"candidate {dna_id} must have exactly one symbol")
        candidates.append(
            {
                "id": f"transient_{dna_id}",
                "status": "research_transient",
                "dna": dna.to_dict(),
                "source_result": {
                    "verdict": result.get("verdict"),
                    "n_trades": result.get("n_trades"),
                    "score": result.get("score"),
                    "reason": result.get("reason"),
                },
            }
        )
    return candidates


def _row_at(rows: list[dict[str, Any]], key: str, value: float) -> dict[str, Any] | None:
    for row in rows:
        parsed = _finite(row.get(key))
        if parsed is not None and abs(parsed - value) < 1e-12:
            return row
    return None


def evaluate_proxy_gates(
    regime: dict[str, Any],
    cost: dict[str, Any],
    fixed: dict[str, Any],
) -> dict[str, Any]:
    """Apply explicit absolute proxy gates without granting registration eligibility."""
    regime_summary = regime.get("summary") or {}
    full = regime.get("full_history") or {}
    slip_5 = _row_at(cost.get("by_slip") or [], "slippage_pct", 0.05) or {}
    fixed_1c = _row_at(fixed.get("by_half_spread") or [], "half_spread_per_leg", 0.01) or {}

    max_loss_values = [
        _finite(full.get("gate_max_loss_usd", full.get("max_loss_usd"))),
        _finite(slip_5.get("gate_max_loss_usd", slip_5.get("max_loss_usd"))),
        _finite(fixed_1c.get("gate_max_loss_usd", fixed_1c.get("max_loss_usd"))),
    ]
    observed_max_losses = [value for value in max_loss_values if value is not None]
    max_loss_usd = max(observed_max_losses) if observed_max_losses else None
    max_window_dd = _finite(
        regime_summary.get(
            "gate_max_dd_across_windows",
            regime_summary.get("max_dd_across_windows"),
        )
    )
    dense_negative = int(regime_summary.get("n_negative_n_ge_3") or 0)

    gates = {
        "baseline_positive_non_vacuous_ship": bool(
            full.get("ok")
            and full.get("verdict") == "SHIP"
            and int(full.get("n_trades") or 0) >= MIN_TRADES_SHIP
            and (_finite(full.get("gate_pnl", full.get("pnl"))) or 0.0) > 0.0
        ),
        "regime_soft_hold": bool(regime_summary.get("regime_hold")),
        "slip_5pct_positive_non_vacuous_ship": bool(
            slip_5.get("ok")
            and slip_5.get("verdict") == "SHIP"
            and int(slip_5.get("n_trades") or 0) >= MIN_TRADES_SHIP
            and (_finite(slip_5.get("gate_pnl", slip_5.get("pnl"))) or 0.0) > 0.0
        ),
        "fixed_0_01_positive_non_vacuous_ship": bool(
            fixed_1c.get("ok")
            and fixed_1c.get("verdict") == "SHIP"
            and int(fixed_1c.get("n_trades") or 0) >= MIN_TRADES_SHIP
            and (_finite(fixed_1c.get("gate_pnl", fixed_1c.get("pnl"))) or 0.0) > 0.0
        ),
        "max_loss_lte_300": max_loss_usd is not None and max_loss_usd <= MAX_LOSS_USD,
        "window_max_dd_lte_75": max_window_dd is not None and max_window_dd <= MAX_WINDOW_DD_USD,
        "dense_negative_windows_lte_5": dense_negative <= MAX_DENSE_NEGATIVE_WINDOWS,
    }
    complete_proxy_gates = all(gates.values())
    return {
        "gates": gates,
        "complete_proxy_gates": complete_proxy_gates,
        "registration_eligible": False,
        "registration_blocker": (
            "chronological_train_and_untouched_holdout_not_proven; evolve selection and "
            "stress history may overlap"
        ),
        "capital": {
            "capital_fit_usd": max_loss_usd,
            "one_lot_max_loss_usd": max_loss_usd,
            "max_lots": OPERATING_MAX_LOTS,
            "sleeve_usd": SLEEVE_USD,
            "open_risk_budget_usd": OPEN_RISK_BUDGET_USD,
            "fits_sleeve": max_loss_usd is not None and max_loss_usd <= SLEEVE_USD,
            "fits_open_risk_budget": (
                max_loss_usd is not None and max_loss_usd <= OPEN_RISK_BUDGET_USD
            ),
            "fits_max_loss_budget": max_loss_usd is not None and max_loss_usd <= MAX_LOSS_USD,
        },
        "quality": {
            "window_max_dd_usd": max_window_dd,
            "dense_negative_windows_n_ge_3": dense_negative,
            "slip_5pct_n": int(slip_5.get("n_trades") or 0),
            "slip_5pct_pnl": _finite(slip_5.get("pnl")),
            "fixed_0_01_n": int(fixed_1c.get("n_trades") or 0),
            "fixed_0_01_pnl": _finite(fixed_1c.get("pnl")),
        },
    }


def stress_candidate(hyp: dict[str, Any], frame: Any, period: str) -> dict[str, Any]:
    dna = StrategyDNA.from_dict(hyp["dna"])
    if dna is None:
        raise ValueError(f"invalid DNA for {hyp.get('id')}")
    regime = stress_one(hyp, frame)
    cost = stress_hyp(hyp, frame, DEFAULT_SLIPS, period)
    base = dict(dna.pcs_config() if hasattr(dna, "pcs_config") else (dna.config or {}))
    base["structure"] = dna.structure
    fixed_rows = []
    for half_spread in (0.0, FIXED_HALF_SPREAD):
        config = deepcopy(base)
        config["slippage_pct"] = 0.0
        config["half_spread_per_leg"] = half_spread
        sim = run_fixed_cost(dna, frame, config, period)
        row = _metrics_row(sim, 0.0)
        row.pop("slippage_pct", None)
        row["half_spread_per_leg"] = half_spread
        fixed_rows.append(row)
    fixed = {"by_half_spread": fixed_rows}
    gate = evaluate_proxy_gates(regime, cost, fixed)
    return {
        "transient_id": hyp["id"],
        "dna_id": dna.ensure_id(),
        "symbol": dna.symbols[0].upper(),
        "structure": dna.structure,
        "source_result": hyp.get("source_result") or {},
        "regime": regime,
        "cost": cost,
        "fixed_cost": fixed,
        **gate,
    }


def build_payload(
    evolve_payload: dict[str, Any],
    *,
    evolve_report: str,
    period: str,
    frames: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidates = load_ship_candidates(evolve_payload)
    frame_cache = frames if frames is not None else {}
    results = []
    for hyp in candidates:
        dna = StrategyDNA.from_dict(hyp["dna"])
        assert dna is not None
        symbol = dna.symbols[0].upper()
        if symbol not in frame_cache:
            print(f"loading {symbol} {period}…", file=sys.stderr)
            frame_cache[symbol] = build(symbol, period=period, use_cache=True)
        results.append(stress_candidate(hyp, frame_cache[symbol], period))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_PROXY",
        "paper_only": True,
        "source_evolve_report": evolve_report,
        "source_evolve_ts": evolve_payload.get("ts"),
        "source_symbols": evolve_payload.get("symbols") or [],
        "source_population_n": int(evolve_payload.get("n_population") or 0),
        "ship_candidates_n": len(candidates),
        "period": period,
        "option_mark_provenance": "black_scholes_proxy",
        "cost_axes": {
            "percentage_slippage": DEFAULT_SLIPS,
            "fixed_half_spread_per_leg_usd": [0.0, FIXED_HALF_SPREAD],
            "observed_quotes": False,
        },
        "selection_validity": {
            "chronological_train_holdout": False,
            "stress_may_overlap_evolve_selection": True,
            "claim_limit": "screening/falsification only; a pass cannot register or earn L1",
        },
        "absolute_gates": {
            "minimum_trades_each_cost_axis": MIN_TRADES_SHIP,
            "positive_ship_each_cost_axis": True,
            "max_loss_usd": MAX_LOSS_USD,
            "window_max_dd_usd": MAX_WINDOW_DD_USD,
            "dense_negative_windows_n_ge_3": MAX_DENSE_NEGATIVE_WINDOWS,
            "regime_soft_hold": True,
        },
        "results": results,
        "complete_proxy_gate_ids": [r["dna_id"] for r in results if r["complete_proxy_gates"]],
        "registration_eligible_ids": [],
        "decision": (
            "NO_REGISTRATION_OVERLAPPING_SELECTION_STRESS"
            if any(r["complete_proxy_gates"] for r in results)
            else "REJECT_ALL_DRY_RUN_SHIPS_BEFORE_REGISTRATION"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evolve-report", required=True)
    parser.add_argument("--period", default="5y")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    report_path = Path(args.evolve_report)
    evolve_payload = json.loads(report_path.read_text())
    payload = build_payload(
        evolve_payload,
        evolve_report=str(report_path),
        period=args.period,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(
        json.dumps(
            {
                "out": str(out),
                "ship_candidates_n": payload["ship_candidates_n"],
                "complete_proxy_gate_ids": payload["complete_proxy_gate_ids"],
                "registration_eligible_ids": payload["registration_eligible_ids"],
                "decision": payload["decision"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

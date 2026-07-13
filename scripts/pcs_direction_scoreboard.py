#!/usr/bin/env python3
"""Compare stressed strategy DNA on shared regime windows and 5% cost stress."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trader_platform.research.evidence_policy import PROXY_OPTION_MARKS, assess_l1_evidence


DIRECTION_BY_STRUCTURE = {
    "put_credit_spread": "bullish",
    "call_credit_spread": "bearish",
    "iron_condor": "neutral",
    "calendar_spread": "time_neutral_to_bullish",
    "diagonal_spread": "bullish_time",
}


def _window_rows(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = list(result.get("yearly_and_chunks") or []) + list(result.get("canonical") or [])
    return {
        str(row["label"]): row
        for row in rows
        if row.get("ok") and (str(row.get("label", "")).startswith("year_") or str(row.get("label", "")).startswith("canon_"))
    }


def _slip_five(result: dict[str, Any]) -> dict[str, Any]:
    return next(
        (
            row
            for row in result.get("by_slip") or []
            if abs(float(row.get("slippage_pct") or 0.0) - 0.05) < 1e-9
        ),
        {},
    )


def build_scoreboard(regime: dict[str, Any], cost: dict[str, Any]) -> dict[str, Any]:
    regime_results = list(regime.get("results") or [])
    cost_by_hyp = {row["hyp_id"]: row for row in cost.get("results") or []}
    window_maps = [_window_rows(row) for row in regime_results]
    common_labels = sorted(set.intersection(*(set(rows) for rows in window_maps))) if window_maps else []

    rows = []
    for result, windows in zip(regime_results, window_maps, strict=True):
        cost_result = cost_by_hyp.get(result["hyp_id"], {})
        slip = _slip_five(cost_result)
        common = [windows[label] for label in common_labels]
        dense_negative = [
            row for row in common if int(row.get("n_trades") or 0) >= 3 and float(row.get("pnl") or 0.0) < 0
        ]
        full = result.get("full_history") or {}
        slip_n = int(slip.get("n_trades") or 0)
        slip_pnl = float(slip.get("pnl") or 0.0)
        rows.append(
            {
                "hyp_id": result["hyp_id"],
                "symbol": result.get("symbol"),
                "structure": result.get("structure"),
                "direction_bias": DIRECTION_BY_STRUCTURE.get(result.get("structure"), "other"),
                "max_loss_usd": full.get("max_loss_usd"),
                "full_history_max_dd": full.get("dd"),
                "common_windows_n": len(common),
                "common_dense_negative_n": len(dense_negative),
                "common_worst_pnl": min((float(row.get("pnl") or 0.0) for row in common), default=0.0),
                "common_window_max_dd": max((float(row.get("dd") or 0.0) for row in common), default=0.0),
                "regime_hold": bool((result.get("summary") or {}).get("regime_hold")),
                "slip_5_n": slip_n,
                "slip_5_pnl": slip_pnl,
                "slip_5_verdict": slip.get("verdict"),
                "cost_hold": bool((cost_result.get("summary") or {}).get("cost_hold")),
                "after_cost_positive_nonvacuous": slip_n > 0 and slip_pnl > 0,
            }
        )

    def quality_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            not row["after_cost_positive_nonvacuous"],
            not (row["regime_hold"] and row["cost_hold"]),
            float(row["max_loss_usd"] or 1e9),
            float(row["common_window_max_dd"] or 1e9),
            row["common_dense_negative_n"],
        )

    rows.sort(key=quality_key)
    # This scoreboard consumes daily-bar BS stress outputs by construction.
    # Input metadata cannot relabel those rows as observed option evidence.
    evidence_decision = assess_l1_evidence(option_mark_provenance=PROXY_OPTION_MARKS)
    metric_eligible = [
        row["hyp_id"]
        for row in rows
        if row["after_cost_positive_nonvacuous"] and row["regime_hold"] and row["cost_hold"]
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "common_window_labels": common_labels,
        "leader_hyp_id": rows[0]["hyp_id"] if rows else None,
        "l1_hyp_ids": [],
        "metric_eligible_hyp_ids": metric_eligible,
        "l1_evidence": evidence_decision.to_dict(),
        "rows": rows,
        "note": "Research scoreboard only. Metric eligibility requires positive non-vacuous 5% slip plus B3+B4; L1 additionally requires sufficient joined observed historical option evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regime", required=True)
    parser.add_argument("--cost", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    regime = json.loads(Path(args.regime).read_text())
    cost = json.loads(Path(args.cost).read_text())
    payload = build_scoreboard(regime, cost)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"out": str(out), "leader": payload["leader_hyp_id"], "l1_hyp_ids": payload["l1_hyp_ids"], "rows": payload["rows"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

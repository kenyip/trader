#!/usr/bin/env python3
"""Income strategy coverage scoreboard for BUILD lab.

Read-only inventory of STRUCTURE_CATALOG vs hyp registry + sim evidence paths.
Writes reports/readiness/income-coverage-LATEST.md (and optional dated copy).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from trader_platform.strategy_dna import STRUCTURE_CATALOG  # noqa: E402


def _load_hyps() -> list[dict]:
    path = REPO / "trader_platform" / "data" / "hypotheses.yaml"
    if not path.exists():
        return []
    try:
        import yaml  # type: ignore
    except ImportError:
        return []
    data = yaml.safe_load(path.read_text()) or {}
    if isinstance(data, dict) and "hypotheses" in data:
        hyps = data["hypotheses"]
        if isinstance(hyps, dict):
            return list(hyps.values())
        if isinstance(hyps, list):
            return hyps
    if isinstance(data, list):
        return data
    return []


def _structure_of(h: dict) -> str:
    dna = h.get("dna") or h.get("strategy_dna") or {}
    if isinstance(dna, dict) and dna.get("structure"):
        return str(dna["structure"])
    notes = str(h.get("notes") or "")
    for key in STRUCTURE_CATALOG:
        if key in notes:
            return key
    sid = str(h.get("id") or h.get("hypothesis_id") or "")
    for key in STRUCTURE_CATALOG:
        if key in sid:
            return key
    return "unknown"


def _status(h: dict) -> str:
    return str(h.get("status") or "unknown").lower()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true", default=True)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--stamp", help="override report stamp for deterministic run regeneration")
    args = ap.parse_args()
    write = args.write and not args.no_write

    hyps = _load_hyps()
    by_struct: dict[str, list[dict]] = defaultdict(list)
    status_counts: Counter[str] = Counter()
    for h in hyps:
        s = _structure_of(h)
        by_struct[s].append(h)
        status_counts[_status(h)] += 1

    sim_dir = REPO / ".cache" / "platform" / "evolve_backtests"
    sim_files = sorted(sim_dir.glob("*")) if sim_dir.exists() else []

    rows = []
    for name, meta in sorted(STRUCTURE_CATALOG.items()):
        engine = str(meta.get("sim_engine") or "single_leg")
        side = (meta.get("entry_plan") or {}).get("side_policy", "?")
        hs = by_struct.get(name, [])
        st = Counter(_status(h) for h in hs)
        rows.append(
            {
                "structure": name,
                "sim_engine": engine,
                "side_policy": side,
                "n_hyps": len(hs),
                "statuses": dict(st),
                "description": str(meta.get("description") or "")[:120],
            }
        )

    gaps = [
        "calendar_spread — explicit front/back IV + put-skew assumptions and chronological OOS built; observed historical option-surface inputs missing",
        "double_diagonal_spread — same-strike/inward protective four-leg BS daily-bar scaffold with American intrinsic floors, signed four-leg percentage/fixed-dollar costs, observed-path loss capital sizing, enforced one-lot operating cap with theoretical capacity separately labeled, and a reproducible eight-symbol chronological reject-unless lab built; 0/8 symbols passed both train/holdout cost axes, no hypothesis was registered, and observed option surfaces/assignment calibration remain missing",
        "diagonal_spread — BS defined-debit scaffold + B3/B4 + exact-DNA OOS/density plus announcement-time dividend/short-call assignment boundary built; AAPL has bounded 40/40 issuer corroboration for announcement date/amount/common-stock identity from 2016-07-26 through 2026-04-30, while the independent explicit-ex-date inventory covered only the latest 20/40 target events and closed that narrow route at partial L0; ambiguous/unsupported symbols fail closed and observed option surfaces remain missing",
        "convex/ratio family — long call, symmetric/broken-wing credit iron butterflies, and a 1x2 put ratio backspread have B3/B4/fixed-cost dispatch; ratio cost survivors still fail absolute DD/risk gates, and observed surfaces/assignment remain missing",
        "debit_vertical — bull-call and bear-put BS defined-debit scaffold + evolve/B3/B4 built; bull-call can use the archived Nasdaq declaration-date provider on supported eventful listings with bounded AAPL issuer corroboration for announcement date/amount/common-stock identity only, while the explicit-ex-date inventory was incomplete at 20/40 and observed surfaces plus short-put assignment remain missing",
        "collared_covered_call — capital-honest scaffold plus 1,152-row DTE/delta/management grid built; 258 rows were positive on both proxy cost axes but zero met the $75 window-DD gate, so the family is rejected this cycle; dividends/assignment unmodeled and no proxy SHIP registered",
        "time-bucket scoreboard — multi-hyp DTE/profit-target/DTE-stop + entry-weekday/cost grid plus a completed-30-minute open/midday/late PCS/CCS/IC chronological dual-cost lab are built; the first 8-symbol cycle was rejected at L0 (0/24 complete train+holdout passes), and usable feature history remains thin at 21 dates versus about 60 raw dates",
        "direction/volatility-bias lab — shared-window scoreboard + no-lookahead shared-position PCS/CCS/IC router built; asymmetric capped-jade IC, daily close-shock/momentum/pullback/vol-compression PCS, multi-horizon trend-pullback PCS, and bearish volatility-expansion CCS families failed complete proxy gates, so they remain rejected pending a genuinely new edge or observed-data density",
        "cost realism — exact PCS/CCS/IC leg/time join + reject gate, Friday abstraction, archive-backed date-aware expiry/strike-grid provider, and all-expiration atomic append capture built; density gate fails closed below three market dates, and the current TSLL archive covers 2/3 dates, so provider-backed historical simulation and observed-cost calibration remain blocked",
    ]

    stamp = args.stamp or datetime.now().strftime("%Y-%m-%dT%H%M")
    out = {
        "stamp": stamp,
        "n_catalog": len(STRUCTURE_CATALOG),
        "n_hyps": len(hyps),
        "status_counts": dict(status_counts),
        "structures": rows,
        "unknown_structure_hyps": len(by_struct.get("unknown", [])),
        "sim_artifact_count": len(sim_files),
        "gaps": gaps,
        "quality_leader_hint": "none; former reference hyp_dna_tsll_put_credit_spread_b195f5fe failed listed-expiry restress quality bar",
    }

    if args.json:
        print(json.dumps(out, indent=2))

    md_lines = [
        f"# Income strategy coverage — {stamp}",
        "",
        "Source: `scripts/trader_income_coverage.py` · doctrine: `docs/INCOME_STRATEGY_COVERAGE.md`",
        "",
        f"- Catalog structures: **{out['n_catalog']}**",
        f"- Hypotheses: **{out['n_hyps']}** ({out['status_counts']})",
        f"- Evolve sim artifacts: **{out['sim_artifact_count']}** under `.cache/platform/evolve_backtests/`",
        f"- Quality leader hint: `{out['quality_leader_hint']}`",
        "",
        "## Catalog × registry",
        "",
        "| structure | engine | side_policy | n_hyps | statuses |",
        "|---|---|---|---:|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| `{r['structure']}` | {r['sim_engine']} | {r['side_policy']} | {r['n_hyps']} | {r['statuses'] or '—'} |"
        )
    md_lines += [
        "",
        "## Gaps (BUILD targets)",
        "",
    ]
    for g in gaps:
        md_lines.append(f"- {g}")
    md_lines += [
        "",
        "## BUILD lab recipe",
        "",
        "1. Dual MoA: `just trader-build-lab`",
        "2. Rotate under-covered structures / time / direction axes",
        "3. Falsify new SHIP with B3+B4 + ml/dd quality bar",
        "4. RTH: wait for filters → paper open/close only",
        "",
        "Paper/research only. No live.",
        "",
    ]
    md = "\n".join(md_lines)
    if not args.json:
        print(md)

    if write:
        dest_dir = REPO / "reports" / "readiness"
        dest_dir.mkdir(parents=True, exist_ok=True)
        latest = dest_dir / "income-coverage-LATEST.md"
        dated = dest_dir / f"income-coverage-{stamp}.md"
        latest.write_text(md)
        dated.write_text(md)
        print(f"\nWrote {latest}", file=sys.stderr)
        print(f"Wrote {dated}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

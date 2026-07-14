#!/usr/bin/env python3
"""B4 cost / slippage sensitivity for registered defined-risk hyps (PCS/CCS/IC).

Paper/research only. Multi-symbol per DNA. Reuses pcs_sim slippage_pct.
Does not place orders or promote status to shadow/live.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data import build  # noqa: E402
from trader_platform.evolve_tick import score_sim_metrics  # noqa: E402
from trader_platform.research.butterfly_sim import run_butterfly_backtest  # noqa: E402
from trader_platform.research.calendar_sim import run_calendar_backtest  # noqa: E402
from trader_platform.research.debit_vertical_sim import run_debit_vertical_backtest  # noqa: E402
from trader_platform.research.diagonal_sim import run_diagonal_backtest  # noqa: E402
from trader_platform.research.iron_butterfly_sim import run_iron_butterfly_backtest  # noqa: E402
from trader_platform.research.pcs_sim import run_pcs_backtest  # noqa: E402
from trader_platform.research.put_ratio_backspread_sim import run_put_ratio_backspread_backtest  # noqa: E402
from trader_platform.strategy_dna import StrategyDNA  # noqa: E402

DEFAULT_HYP_IDS = [
    "hyp_dna_tsll_put_credit_spread_b195f5fe",
    "hyp_dna_amd_iron_condor_b3056133",
    "hyp_dna_xom_call_credit_spread_77766a47",
]
# Slip as fraction of option mark: 0 = mid, 0.05 ≈ 5% adverse each side.
DEFAULT_SLIPS = [0.0, 0.02, 0.05, 0.10]
OUT = _REPO / ".cache/platform/stress_cost_defined_risk.json"
HYPS_PATH = _REPO / "trader_platform/data/hypotheses.yaml"


def _load_hyps(ids: list[str]) -> list[dict[str, Any]]:
    store = yaml.safe_load(HYPS_PATH.read_text()) or {}
    by_id = {h["id"]: h for h in (store.get("hypotheses") or []) if isinstance(h, dict) and h.get("id")}
    out = []
    for hid in ids:
        if hid not in by_id:
            raise SystemExit(f"missing hyp {hid}")
        out.append(by_id[hid])
    return out


def _metrics_row(pcs, slip: float) -> dict[str, Any]:
    if not pcs.ok or pcs.skipped:
        return {
            "slippage_pct": slip,
            "ok": False,
            "reason": pcs.reason or "skipped",
            "n_trades": 0,
        }
    m = pcs.metrics or {}
    n = int(pcs.n_trades or m.get("n_trades") or 0)
    pnl = float(m.get("total_pnl_per_contract") or 0.0)
    wr = float(m.get("win_rate_pct") or 0.0)
    if wr == 0 and m.get("win_rate") is not None:
        wr = float(m["win_rate"])
        if wr <= 1:
            wr *= 100.0
    dd = float(m.get("max_dd_per_contract") or 0.0)
    try:
        pf = float(m.get("profit_factor") or 0.0)
    except (TypeError, ValueError):
        pf = float("nan")
    wr_unit = wr / 100.0 if wr > 1 else wr
    verdict, score, reason, pfc = score_sim_metrics(
        n_trades=n, pnl=pnl, win_rate=wr_unit, max_dd=dd, profit_factor=pf
    )
    cap = pcs.capital or {}
    return {
        "slippage_pct": slip,
        "ok": True,
        "n_trades": n,
        "pnl": round(pnl, 2),
        "gate_pnl": pnl,
        "wr_pct": round(wr if wr > 1 else wr * 100.0, 1),
        "dd": round(dd, 2),
        "gate_dd": dd,
        "pf": round(float(pfc), 3) if pfc == pfc else None,
        "verdict": verdict,
        "score": round(float(score), 2),
        "reason": reason,
        "max_loss_usd": cap.get("max_loss_usd"),
        "gate_max_loss_usd": cap.get("max_loss_usd"),
        "capital_fit": cap.get("capital_fit"),
        "median_max_loss_usd": cap.get("median_max_loss_usd"),
        "exit_reasons": m.get("exit_reasons") or {},
    }


def stress_hyp(hyp: dict[str, Any], df, slips: list[float], period: str) -> dict[str, Any]:
    hid = hyp["id"]
    dna = StrategyDNA.from_dict(hyp["dna"])
    assert dna is not None
    base_cfg = dna.pcs_config() if hasattr(dna, "pcs_config") else dict(dna.config or {})
    symbol = (dna.symbols or ["TSLL"])[0].upper()
    structure = str(getattr(dna, "structure", None) or hyp.get("structure") or "put_credit_spread")
    base_cfg = dict(base_cfg)
    base_cfg["structure"] = structure

    rows = []
    for slip in slips:
        cfg = deepcopy(base_cfg)
        cfg["slippage_pct"] = float(slip)
        if structure == "put_ratio_backspread":
            pcs = run_put_ratio_backspread_backtest(
                symbol,
                period=period,
                use_cache=True,
                config=cfg,
                sleeve_usd=3000.0,
                open_risk_budget_usd=750.0,
                df=df,
                min_bars=15,
            )
        elif structure in {"iron_butterfly", "broken_wing_iron_butterfly"}:
            pcs = run_iron_butterfly_backtest(
                symbol,
                period=period,
                use_cache=True,
                config=cfg,
                sleeve_usd=3000.0,
                open_risk_budget_usd=750.0,
                df=df,
                min_bars=15,
            )
        elif structure in {"bull_call_debit_spread", "bear_put_debit_spread"}:
            pcs = run_debit_vertical_backtest(
                symbol,
                structure=structure,
                period=period,
                use_cache=True,
                config=cfg,
                sleeve_usd=3000.0,
                open_risk_budget_usd=750.0,
                df=df,
                min_bars=15,
            )
        elif structure == "butterfly_spread":
            pcs = run_butterfly_backtest(
                symbol,
                period=period,
                use_cache=True,
                config=cfg,
                sleeve_usd=3000.0,
                open_risk_budget_usd=750.0,
                df=df,
                min_bars=15,
            )
        elif structure == "diagonal_spread":
            pcs = run_diagonal_backtest(
                symbol,
                period=period,
                use_cache=True,
                config=cfg,
                sleeve_usd=3000.0,
                open_risk_budget_usd=750.0,
                df=df,
                min_bars=15,
            )
        elif structure == "calendar_spread":
            pcs = run_calendar_backtest(
                symbol,
                period=period,
                use_cache=True,
                config=cfg,
                sleeve_usd=3000.0,
                open_risk_budget_usd=750.0,
                df=df,
                min_bars=15,
            )
        else:
            pcs = run_pcs_backtest(
                symbol,
                period=period,
                use_cache=True,
                config=cfg,
                sleeve_usd=3000.0,
                open_risk_budget_usd=750.0,
                df=df,
                min_bars=15,
                structure=structure,
            )
        rows.append(_metrics_row(pcs, float(slip)))

    baseline = next((r for r in rows if r.get("slippage_pct") == 0.0 and r.get("ok")), None)
    harsh = next((r for r in rows if abs(float(r.get("slippage_pct") or 0) - 0.05) < 1e-9), None)
    very = next((r for r in rows if abs(float(r.get("slippage_pct") or 0) - 0.10) < 1e-9), None)

    hold = False
    note = "no_baseline"
    if baseline and baseline.get("ok"):
        # B4 soft hold: non-catastrophic at 5% slip + capital_fit intact.
        # SHIP or non-negative at 5% = strong; mild defined-risk loss OK; big NULL/REJECT = fragile.
        harsh_ok = bool(harsh and harsh.get("ok"))
        pnl_5 = float(harsh.get("pnl") or 0) if harsh_ok and harsh is not None else None
        verd_5 = harsh.get("verdict") if harsh_ok and harsh is not None else None
        fit_rows_ok = all(
            (
                r.get("capital_fit") in ("fit_3k", "fit_sleeve", "fit_sleeve_soft")
                or int(r.get("n_trades") or 0) == 0
            )
            for r in rows
            if r.get("ok")
        )
        if not harsh_ok:
            hold = False
            note = "missing_5pct"
        elif verd_5 == "REJECT" and pnl_5 is not None and pnl_5 < -50:
            hold = False
            note = "fragile_at_5pct_slip"
        elif verd_5 == "SHIP" or (pnl_5 is not None and pnl_5 >= 0):
            hold = True
            note = "survives_5pct_slip"
        elif pnl_5 is not None and pnl_5 > -100:
            hold = True
            note = "soft_loss_at_5pct_defined_risk"
        else:
            hold = False
            note = "large_loss_at_5pct_fragile"

        if hold and not fit_rows_ok:
            hold = False
            note = "capital_fit_degraded_under_slip"

    return {
        "hyp_id": hid,
        "dna_id": dna.ensure_id(),
        "symbol": symbol,
        "base_config": base_cfg,
        "period": period,
        "n_bars": int(len(df)),
        "start": str(df.index[0].date()),
        "end": str(df.index[-1].date()),
        "by_slip": rows,
        "summary": {
            "baseline_verdict": baseline.get("verdict") if baseline else None,
            "baseline_pnl": baseline.get("pnl") if baseline else None,
            "slip_5_verdict": harsh.get("verdict") if harsh else None,
            "slip_5_pnl": harsh.get("pnl") if harsh else None,
            "slip_10_verdict": very.get("verdict") if very else None,
            "slip_10_pnl": very.get("pnl") if very else None,
            "cost_hold": hold,
            "note": note,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--period", default="5y", help="history period if rebuild needed (default 5y)")
    ap.add_argument(
        "--slips",
        default=",".join(str(s) for s in DEFAULT_SLIPS),
        help="comma-separated slippage_pct values",
    )
    ap.add_argument("--hyps", default=",".join(DEFAULT_HYP_IDS), help="comma hyp ids")
    ap.add_argument("--out", default=str(OUT), help="json output path")
    ap.add_argument("--write-hyps", action="store_true", help="append evidence_links on hyps")
    args = ap.parse_args(argv)

    slips = [float(x.strip()) for x in args.slips.split(",") if x.strip()]
    hyp_ids = [x.strip() for x in args.hyps.split(",") if x.strip()]
    hyps = _load_hyps(hyp_ids)

    df_cache: dict[str, Any] = {}
    results = []
    for h in hyps:
        dna = StrategyDNA.from_dict(h["dna"])
        assert dna is not None
        symbol = (dna.symbols or ["TSLL"])[0].upper()
        if symbol not in df_cache:
            print(f"loading {symbol} {args.period}…", file=sys.stderr)
            df_cache[symbol] = build(symbol, period=args.period, use_cache=True)
        results.append(stress_hyp(h, df_cache[symbol], slips, args.period))

    # Rank: prefer hyp that still SHIP/positive at 5% with fewest fragility
    ranked = sorted(
        results,
        key=lambda r: (
            0 if r["summary"].get("cost_hold") else 1,
            0 if r["summary"].get("slip_5_verdict") == "SHIP" else 1,
            -(float(r["summary"].get("slip_5_pnl") or -1e9)),
            -(float(r["summary"].get("baseline_pnl") or -1e9)),
        ),
    )
    preferred = ranked[0]["hyp_id"] if ranked else None

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sleeve_usd": 3000,
        "period": args.period,
        "slips": slips,
        "note": (
            "B4: BS marks + slippage_pct adverse on credit (entry) and debit (exit). "
            "RH equity options often $0 commission; bid-ask modeled as slip. "
            "cost_hold=soft survives ~5% slip without dense catastrophic REJECT."
        ),
        "preferred_under_cost": preferred,
        "results": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps({"out": str(out_path), "preferred": preferred, "summaries": [
        {"hyp": r["hyp_id"], **r["summary"]} for r in results
    ]}, indent=2))

    if args.write_hyps:
        store = yaml.safe_load(HYPS_PATH.read_text()) or {}
        by_id = {h["id"]: h for h in (store.get("hypotheses") or [])}
        link = f"file://{out_path.resolve()}"
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for r in results:
            h = by_id.get(r["hyp_id"])
            if not h:
                continue
            links = list(h.get("evidence_links") or [])
            entry = f"{stamp} B4 cost/slip stress: hold={r['summary'].get('cost_hold')} note={r['summary'].get('note')} → {link}"
            if entry not in links:
                links.append(entry)
            h["evidence_links"] = links
        HYPS_PATH.write_text(yaml.safe_dump(store, sort_keys=False, allow_unicode=True))
        print("wrote evidence_links on hyps", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

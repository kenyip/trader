#!/usr/bin/env python3
"""Regime-window stress for registered defined-risk hyps (PCS/CCS/IC).

Yearly + ~6m chunks + optional TSLL canonical windows via pcs_sim.
Multi-symbol: loads history per DNA symbol. Paper/research only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
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
OUT = _REPO / ".cache/platform/stress_regime_defined_risk.json"
HYPS_PATH = _REPO / "trader_platform/data/hypotheses.yaml"


def _row_from_pcs(
    label: str,
    sub: pd.DataFrame | None,
    symbol: str,
    cfg: dict,
    *,
    structure: str = "put_credit_spread",
) -> dict[str, Any]:
    if sub is None or len(sub) < 15:
        return {
            "label": label,
            "ok": False,
            "reason": "short_window",
            "n_bars": 0 if sub is None else int(len(sub)),
        }
    if structure == "put_ratio_backspread":
        pcs = run_put_ratio_backspread_backtest(
            symbol,
            period=label,
            use_cache=True,
            config=cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            df=sub,
            min_bars=15,
        )
    elif structure in {"iron_butterfly", "broken_wing_iron_butterfly"}:
        pcs = run_iron_butterfly_backtest(
            symbol,
            period=label,
            use_cache=True,
            config=cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            df=sub,
            min_bars=15,
        )
    elif structure in {"bull_call_debit_spread", "bear_put_debit_spread"}:
        pcs = run_debit_vertical_backtest(
            symbol,
            structure=structure,
            period=label,
            use_cache=True,
            config=cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            df=sub,
            min_bars=15,
        )
    elif structure == "butterfly_spread":
        pcs = run_butterfly_backtest(
            symbol,
            period=label,
            use_cache=True,
            config=cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            df=sub,
            min_bars=15,
        )
    elif structure == "diagonal_spread":
        pcs = run_diagonal_backtest(
            symbol,
            period=label,
            use_cache=True,
            config=cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            df=sub,
            min_bars=15,
        )
    elif structure == "calendar_spread":
        pcs = run_calendar_backtest(
            symbol,
            period=label,
            use_cache=True,
            config=cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            df=sub,
            min_bars=15,
        )
    else:
        pcs = run_pcs_backtest(
            symbol,
            period=label,
            use_cache=True,
            config=cfg,
            sleeve_usd=3000.0,
            open_risk_budget_usd=750.0,
            df=sub,
            min_bars=15,
            structure=structure,
        )
    if not pcs.ok or pcs.skipped:
        return {
            "label": label,
            "ok": False,
            "reason": pcs.reason or "skipped",
            "n_bars": int(len(sub)),
            "start": str(sub.index[0].date()),
            "end": str(sub.index[-1].date()),
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
        "label": label,
        "ok": True,
        "n_bars": int(len(sub)),
        "start": str(sub.index[0].date()),
        "end": str(sub.index[-1].date()),
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
        "exit_reasons": m.get("exit_reasons") or {},
    }


def stress_one(hyp: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    hid = hyp["id"]
    dna = StrategyDNA.from_dict(hyp["dna"])
    assert dna is not None
    cfg = dna.pcs_config() if hasattr(dna, "pcs_config") else dict(dna.config or {})
    symbol = (dna.symbols or ["TSLL"])[0].upper()
    structure = str(getattr(dna, "structure", None) or hyp.get("structure") or "put_credit_spread")
    cfg = dict(cfg)
    cfg["structure"] = structure

    rows: list[dict[str, Any]] = []
    for y in sorted(set(df.index.year)):
        rows.append(_row_from_pcs(f"year_{y}", df[df.index.year == y], symbol, cfg, structure=structure))

    chunk = 126
    for i, start in enumerate(range(0, max(0, len(df) - chunk + 1), chunk)):
        sub = df.iloc[start : start + chunk]
        rows.append(
            _row_from_pcs(
                f"chunk6m_{i}_{sub.index[0].date()}_{sub.index[-1].date()}",
                sub,
                symbol,
                cfg,
                structure=structure,
            )
        )

    canon_rows: list[dict[str, Any]] = []
    try:
        from scenarios import CANONICAL_SCENARIOS

        tsll = CANONICAL_SCENARIOS.get("TSLL") if isinstance(CANONICAL_SCENARIOS, dict) else None
        if isinstance(tsll, dict):
            for regime, val in tsll.items():
                if val is None:
                    canon_rows.append(
                        {
                            "label": f"canon_{regime}",
                            "ok": False,
                            "reason": "no_window",
                            "n_bars": 0,
                        }
                    )
                    continue
                if isinstance(val, (list, tuple)) and len(val) >= 2:
                    start, end = val[0], val[1]
                elif isinstance(val, dict):
                    start = val.get("start") or val.get("start_date")
                    end = val.get("end") or val.get("end_date")
                else:
                    continue
                start_ts = pd.Timestamp(start)
                end_ts = pd.Timestamp(end)
                sub = df[(df.index >= start_ts) & (df.index <= end_ts)]
                canon_rows.append(
                    _row_from_pcs(
                        f"canon_{regime}_{start_ts.date()}_{end_ts.date()}",
                        sub,
                        symbol,
                        cfg,
                        structure=structure,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        canon_rows.append({"label": "canon_error", "ok": False, "reason": str(exc), "n_bars": 0})

    # Full 5y reference (same path as ship bar)
    full = _row_from_pcs("full_history", df, symbol, cfg, structure=structure)

    neg = [
        r
        for r in rows + canon_rows
        if r.get("ok")
        and float(r.get("gate_pnl", r.get("pnl") or 0)) < 0
        and int(r.get("n_trades") or 0) >= 3
    ]
    ship_like = [
        r
        for r in rows + canon_rows
        if r.get("ok") and r.get("verdict") == "SHIP" and int(r.get("n_trades") or 0) >= 3
    ]
    reject_like = [
        r
        for r in rows + canon_rows
        if r.get("ok") and r.get("verdict") == "REJECT" and int(r.get("n_trades") or 0) >= 3
    ]

    # Falsify summary for $3k PCS: max loss always fits, no catastrophic regime
    max_dd = max(
        (
            float(r.get("gate_dd", r.get("dd") or 0))
            for r in rows + canon_rows
            if r.get("ok")
        ),
        default=0.0,
    )
    worst_pnl = min(
        (
            float(r.get("gate_pnl", r.get("pnl") or 0))
            for r in rows + canon_rows
            if r.get("ok")
        ),
        default=0.0,
    )
    n_neg = len(neg)
    n_ok = sum(1 for r in rows + canon_rows if r.get("ok"))
    # Soft hold: not more than ~half of trade-dense windows negative; worst window not
    # multi-width blowups (dd already defined-risk capped near width*lots).
    hold = n_ok > 0 and n_neg <= max(3, n_ok // 2) and worst_pnl > -400.0

    return {
        "hyp_id": hid,
        "dna_id": dna.ensure_id(),
        "symbol": symbol,
        "structure": structure,
        "config": cfg,
        "full_history": full,
        "yearly_and_chunks": rows,
        "canonical": canon_rows,
        "negative_windows_n_ge_3": neg,
        "ship_windows_n_ge_3": [
            {"label": r["label"], "pnl": r.get("pnl"), "n": r.get("n_trades"), "score": r.get("score")}
            for r in ship_like
        ],
        "reject_windows_n_ge_3": [
            {"label": r["label"], "pnl": r.get("pnl"), "n": r.get("n_trades"), "score": r.get("score")}
            for r in reject_like
        ],
        "summary": {
            "n_windows_ok": n_ok,
            "n_negative_n_ge_3": n_neg,
            "n_ship_n_ge_3": len(ship_like),
            "n_reject_n_ge_3": len(reject_like),
            "max_dd_across_windows": round(max_dd, 2),
            "gate_max_dd_across_windows": max_dd,
            "worst_window_pnl": round(worst_pnl, 2),
            "gate_worst_window_pnl": worst_pnl,
            "regime_hold": hold,
            "note": "regime_hold=soft: neg dense windows <= max(3, n_ok/2) and worst_pnl > -400",
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hyps", default=",".join(DEFAULT_HYP_IDS), help="comma hyp ids")
    ap.add_argument("--period", default="5y", help="history period (default 5y)")
    ap.add_argument("--out", default=str(OUT), help="json output path")
    ap.add_argument("--write-hyps", action="store_true", help="append evidence_links on hyps")
    args = ap.parse_args(argv)

    store = yaml.safe_load(HYPS_PATH.read_text())
    hyps = store.get("hypotheses") or []
    by_id = {h["id"]: h for h in hyps}
    ids = [x.strip() for x in args.hyps.split(",") if x.strip()]
    missing = [i for i in ids if i not in by_id]
    if missing:
        print("missing hyps", missing)
        return 1

    df_cache: dict[str, pd.DataFrame] = {}
    results = []
    for hid in ids:
        hyp = by_id[hid]
        dna = StrategyDNA.from_dict(hyp["dna"])
        assert dna is not None
        symbol = (dna.symbols or ["TSLL"])[0].upper()
        structure = str(getattr(dna, "structure", None) or "put_credit_spread")
        if symbol not in df_cache:
            print(f"loading {symbol} {args.period}…")
            df_cache[symbol] = build(symbol, period=args.period, use_cache=True)
            df = df_cache[symbol]
            print("df", symbol, len(df), df.index[0].date(), df.index[-1].date())
        df = df_cache[symbol]
        print(f"\n=== {hid} ({symbol} {structure}) ===")
        r = stress_one(hyp, df)
        r["symbol"] = symbol
        r["structure"] = structure
        results.append(r)
        s = r["summary"]
        print(
            f"full: {r['full_history'].get('verdict')} n={r['full_history'].get('n_trades')} "
            f"pnl={r['full_history'].get('pnl')} dd={r['full_history'].get('dd')}"
        )
        print(
            f"windows ok={s['n_windows_ok']} neg_ge3={s['n_negative_n_ge_3']} "
            f"ship_ge3={s['n_ship_n_ge_3']} reject_ge3={s['n_reject_n_ge_3']} "
            f"worst_pnl={s['worst_window_pnl']} max_dd={s['max_dd_across_windows']} "
            f"hold={s['regime_hold']}"
        )
        print("yearly:")
        for row in r["yearly_and_chunks"]:
            if str(row["label"]).startswith("year_"):
                print(" ", row)
        print("negative dense:")
        for row in r["negative_windows_n_ge_3"]:
            print(" ", row["label"], row.get("pnl"), "n", row.get("n_trades"), row.get("verdict"))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "at": pd.Timestamp.now(tz="UTC").isoformat(),
        "period": args.period,
        "sleeve_usd": 3000,
        "hyp_ids": ids,
        "symbols": sorted({r.get("symbol") for r in results}),
        "structures": sorted({r.get("structure") for r in results}),
        "results": results,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    print("\nwrote", out_path)

    if args.write_hyps:
        for r in results:
            h = by_id[r["hyp_id"]]
            s = r["summary"]
            path_note = (
                f"regime_stress:neg_ge3={s['n_negative_n_ge_3']}:hold={s['regime_hold']}:"
                f"worst_pnl={s['worst_window_pnl']}:max_dd={s['max_dd_across_windows']}:"
                f"path={out_path}"
            )
            links = list(h.get("evidence_links") or [])
            links = [e for e in links if not str(e).startswith("regime_stress:")]
            links.append(path_note)
            h["evidence_links"] = links
            notes = h.get("notes") or ""
            tag = (
                f"regime_stress_hold={s['regime_hold']};"
                f"neg_windows_ge3={s['n_negative_n_ge_3']};"
                f"worst_window_pnl={s['worst_window_pnl']}"
            )
            parts = [
                p.strip()
                for p in notes.split(";")
                if p.strip() and not p.strip().startswith("regime_stress")
            ]
            parts.append(tag)
            h["notes"] = "; ".join(parts)
        HYPS_PATH.write_text(yaml.safe_dump(store, sort_keys=False, allow_unicode=True, width=120))
        print("updated hyp evidence_links/notes (status unchanged)")
    else:
        print("skip hyp yaml write (pass --write-hyps to append evidence_links)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

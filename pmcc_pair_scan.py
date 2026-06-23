#!/usr/bin/env python3
"""Scan all PMCC strike pairs against full daily scenario suite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pmcc.config import apply_preset, PmccConfig
from pmcc.pair_scan import (
    KEY_PATHS,
    best_leaps_on_ladder,
    leaps_ladder,
    run_full_scan,
    scenario_matrix,
    short_ladder,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC pair scanner — all scenarios")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish", "managed"), default="managed")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--mode", choices=("pairs", "full"), default="pairs",
                    help="pairs=69 strike combos (fast); full=every grid DTE cell (slow)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch chain + re-scan")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--ladder-short", type=float, help="LEAPS ladder for this short strike")
    ap.add_argument("--ladder-leaps", type=float, help="short ladder for this LEAPS strike")
    ap.add_argument("--csv", type=Path)
    args = ap.parse_args()

    def _progress(i: int, n: int, pair: str) -> None:
        print(f"\r  [{i}/{n}] {pair}    ", end="", file=sys.stderr)

    if args.refresh:
        from pmcc.analyze import build_pmcc_grid
        from pmcc.pair_scan import scan_pairs, save_scan, ScanMeta
        import time

        cfg = apply_preset(PmccConfig(ticker=args.ticker), args.preset)
        cfg = PmccConfig(**{**cfg.__dict__, "chain_refresh": True, "path_sim_top_n": 0})
        t0 = time.perf_counter()
        spot, grid = build_pmcc_grid(cfg)
        scan = scan_pairs(
            grid, spot, preset=args.preset, mode=args.mode,
            r=cfg.risk_free_rate, progress=_progress,
        )
        print(file=sys.stderr)
        meta = ScanMeta(
            ticker=args.ticker, preset=args.preset, spot=spot,
            scanned_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            n_pairs=len(scan), elapsed_sec=time.perf_counter() - t0,
            scan_mode=args.mode,
        )
        save_scan(scan, meta)
    else:
        scan, meta = run_full_scan(
            preset=args.preset, ticker=args.ticker, mode=args.mode, refresh_chain=False,
        )

    if scan.empty:
        raise SystemExit("no scan results — run with --refresh")

    print(f"\n=== PMCC pair scan — {args.ticker} ({args.mode}) ===")
    if meta:
        unit = "cells" if args.mode == "full" else "pairs"
        print(f"Preset: {args.preset}  |  spot ${meta.spot:,.2f}  |  "
              f"{meta.n_pairs} {unit}  |  {meta.elapsed_sec:.0f}s")
    if args.mode == "full":
        print("Tip: run `just pmcc-calibrate` to compare static scores vs sim and tune weights.")
    print()

    print(f"TOP {args.top} by composite sim (return % on LEAPS + roll efficiency):\n")
    show = scan.head(args.top)
    cols = [
        "rank", "pair", "leaps_dte", "short_dte", "leaps_debit", "net_debit", "upside_pct",
        "path_sim_score", "path_return_score", "roll_eff_score", "roll_tax_burden",
        "roll_count_sim", "bear_worst", "path_moonshot",
    ]
    cols = [c for c in cols if c in show.columns]
    fmt = show[cols].copy()
    for c in fmt.columns:
        if c in ("net_debit", "short_credit", "leaps_debit"):
            fmt[c] = fmt[c].map(lambda x: f"${x:,.0f}")
        elif c.startswith("path_") or c in ("whipsaw_avg", "bull_avg", "bear_worst", "path_return_score"):
            fmt[c] = fmt[c].map(lambda x: f"{x:+.1f}%" if x == x else "—")
        elif c == "roll_tax_burden":
            fmt[c] = fmt[c].map(lambda x: f"{x:.1f}%" if x == x else "—")
        elif c in ("path_sim_score", "roll_eff_score"):
            fmt[c] = fmt[c].map(lambda x: f"{x:+.1f}" if x == x else "—")
        elif c == "roll_count_sim":
            fmt[c] = fmt[c].map(lambda x: f"{x:.1f}" if x == x else "—")
        elif c == "upside_pct":
            fmt[c] = fmt[c].map(lambda x: f"{x:.1f}%")
    print(fmt.to_string(index=False))
    print()

    if "path_return_score" in scan.columns:
        print("TOP by scenario return % (before roll-efficiency blend):\n")
        ret_top = scan.sort_values("path_return_score", ascending=False).head(min(5, args.top))
        for _, r in ret_top.iterrows():
            print(f"  #{int(r['rank']):>2} {r['pair']}  "
                  f"return {r['path_return_score']:+.1f}%  "
                  f"roll burden {r.get('roll_tax_burden', 0):.1f}%")
        print()

    print("=== Scenario matrix (top pairs × paths) ===\n")
    for _, r in scan.head(min(args.top, 10)).iterrows():
        cells = [f"sim={r['path_sim_score']:+.1f}%"]
        for p in KEY_PATHS:
            col = f"path_{p}"
            if col not in r.index:
                continue
            v = r[col]
            short = p.replace("_", "")[:8]
            cells.append(f"{short}={v:+.1f}%" if v == v else f"{short}=—")
        print(f"  {r['pair']}:  " + "  ".join(cells))
    print()

    if args.ladder_short:
        winners = best_leaps_on_ladder(scan, args.ladder_short)
        canon = winners.get("canonical_leaps_dte", "?")
        print(f"=== LEAPS ladder @ short ${args.ladder_short:.0f} "
              f"(DTE-normalized @ {canon}d) ===\n")
        if winners:
            norm_line = (
                f"Best norm: {winners.get('best_norm_pair', '—')} "
                f"({winners.get('best_norm_score', 0):+.1f})  |  "
                if "best_norm_pair" in winners else
                "Best norm: — (run --refresh)  |  "
            )
            print(
                f"  Best raw: {winners.get('best_raw_pair', '—')} "
                f"({winners.get('best_raw_score', 0):+.1f})  |  "
                f"{norm_line}\n"
            )
        lad = leaps_ladder(scan, args.ladder_short)
        if lad.empty:
            print("(no pairs)")
        else:
            print(lad.to_string(index=False, formatters={
                "net_debit": "${:,.0f}".format,
                "short_credit": "${:,.0f}".format,
                "upside_pct": "{:.1f}%".format,
                "path_sim_score": "{:+.1f}".format,
                "path_sim_norm": "{:+.1f}".format,
                "path_return_score": "{:+.1f}%".format,
                "roll_tax_burden": "{:.1f}%".format,
                "whipsaw_avg": "{:+.1f}%".format,
                "bull_avg": "{:+.1f}%".format,
                "bear_worst": "{:+.1f}%".format,
                "path_tsla_range_chop": "{:+.1f}%".format,
                "path_moonshot": "{:+.1f}%".format,
                "path_gap_whipsaw_double": "{:+.1f}%".format,
                "path_steady_bear": "{:+.1f}%".format,
            }))
        print()

    if args.ladder_leaps:
        print(f"=== Short ladder @ LEAPS ${args.ladder_leaps:.0f} ===\n")
        lad = short_ladder(scan, args.ladder_leaps)
        if lad.empty:
            print("(no pairs)")
        else:
            print(lad.to_string(index=False))
        print()

    if args.csv:
        scan.to_csv(args.csv, index=False)
        print(f"Wrote {len(scan)} rows → {args.csv}")


if __name__ == "__main__":
    main()
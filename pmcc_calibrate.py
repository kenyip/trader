#!/usr/bin/env python3
"""Compare full-grid path sim vs static PMCC scores — tune static weights."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pmcc.calibrate import (
    build_calibration_report,
    compare_static_collapse_to_sim,
    format_calibration_report,
    load_calibration_scan,
)
from pmcc.config import apply_preset, PmccConfig
from pmcc.pair_scan import run_full_scan


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Calibrate static PMCC scores against full-grid path simulation",
    )
    ap.add_argument("--preset", choices=("income", "balanced", "bullish", "managed"), default="managed")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--profile", default=None,
                    help="score profile for weight comparison (default: preset profile)")
    ap.add_argument("--refresh", action="store_true",
                    help="re-run full grid path sim (~15-40 min)")
    ap.add_argument("--csv", type=Path, help="write full scan+calibration merge to CSV")
    ap.add_argument("--dte-table", action="store_true", help="show per-pair static vs sim DTE picks")
    args = ap.parse_args()

    profile = args.profile
    if profile is None:
        cfg = apply_preset(PmccConfig(ticker=args.ticker), args.preset)
        profile = cfg.score_profile

    if args.refresh:
        def _progress(i: int, n: int, label: str) -> None:
            print(f"\r  [{i}/{n}] {label}    ", end="", file=sys.stderr)

        from pmcc.analyze import build_pmcc_grid
        from pmcc.pair_scan import scan_pairs, save_scan, ScanMeta
        import time

        cfg = apply_preset(PmccConfig(ticker=args.ticker), args.preset)
        cfg = PmccConfig(**{**cfg.__dict__, "chain_refresh": True, "path_sim_top_n": 0})
        t0 = time.perf_counter()
        spot, grid = build_pmcc_grid(cfg)
        print(f"Full grid: {len(grid)} cells → path sim…", file=sys.stderr)
        scan = scan_pairs(
            grid, spot, preset=args.preset, mode="full",
            r=cfg.risk_free_rate, progress=_progress,
        )
        print(file=sys.stderr)
        from datetime import datetime, timezone
        meta = ScanMeta(
            ticker=args.ticker, preset=args.preset, spot=spot,
            scanned_at=datetime.now(timezone.utc),
            n_pairs=len(scan), elapsed_sec=time.perf_counter() - t0,
            scan_mode="full",
        )
        save_scan(scan, meta)
    else:
        scan, label = load_calibration_scan(args.preset, args.ticker)
        if scan.empty:
            raise SystemExit(label)

    report = build_calibration_report(scan, profile=profile)
    print(format_calibration_report(report, profile=profile))

    if args.dte_table:
        print("\n=== Static vs sim DTE pick (per strike pair) ===\n")
        dte = compare_static_collapse_to_sim(scan)
        show = dte.head(20).copy()
        show["static_sim"] = show["static_sim"].map(lambda x: f"${x:,.0f}")
        show["best_sim"] = show["best_sim"].map(lambda x: f"${x:,.0f}")
        show["sim_delta"] = show["sim_delta"].map(lambda x: f"${x:+,.0f}")
        print(show.to_string(index=False))

    if args.csv:
        scan.to_csv(args.csv, index=False)
        print(f"\nWrote {len(scan)} rows → {args.csv}")


if __name__ == "__main__":
    main()
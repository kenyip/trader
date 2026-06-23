#!/usr/bin/env python3
"""Explain PMCC pair ranking — static score vs path-management sim."""

from __future__ import annotations

import argparse

from pmcc.analyze import build_pmcc_grid, format_table
from pmcc.chain_data import chain_fetch_meta, format_chain_source
from pmcc.config import PmccConfig, SCORE_PROFILES, apply_preset
from pmcc.pair_rank import compare_pairs_table, enrich_path_sim, explain_pair, blend_scores


COMPARE_DEFAULT = [(420, 430), (420, 455), (420, 510), (390, 510)]


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC pair ranking explainer")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish", "managed"), default="balanced")
    ap.add_argument("--profile", choices=tuple(SCORE_PROFILES), help="override score profile")
    ap.add_argument("--explain", help="pair to explain, e.g. 420/430")
    ap.add_argument("--compare", action="store_true", help="compare canonical pairs")
    ap.add_argument("--path-sim", action="store_true", help="run daily path sim on top 20 pairs")
    ap.add_argument("--blend", type=float, default=0.55, help="path-sim blend weight (with --path-sim)")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    cfg = apply_preset(PmccConfig(), args.preset)
    cfg = PmccConfig(**{**cfg.__dict__, "chain_use_cache": not args.no_cache})
    if args.profile:
        cfg = PmccConfig(**{**cfg.__dict__, "score_profile": args.profile})
    if args.path_sim:
        cfg = PmccConfig(**{**cfg.__dict__, "path_sim_top_n": 20, "path_sim_blend": args.blend})

    spot, df = build_pmcc_grid(cfg)
    profile = cfg.score_profile

    print(f"\n=== PMCC pair rank — {cfg.ticker} @ ${spot:,.2f} ===")
    print(f"Preset: {args.preset}  |  score profile: {profile}")
    if cfg.path_sim_blend > 0:
        print(f"Path sim: top {cfg.path_sim_top_n} pairs, blend {cfg.path_sim_blend:.0%}")
    print(format_chain_source(chain_fetch_meta()))
    print()

    if args.explain:
        lk, sk = [float(x) for x in args.explain.split("/")]
        m = df[(df.leaps_strike == lk) & (df.short_strike == sk)]
        if m.empty:
            raise SystemExit(f"pair {args.explain} not in grid")
        row = m.sort_values("score", ascending=False).iloc[0]
        print(explain_pair(row, profile=profile))
        if "path_sim_score" in row and pd_notna(row.get("path_sim_score")):
            print(f"\nPath sim score: {row['path_sim_score']:,.0f}  "
                  f"chop ${row.get('path_chop_pnl', 0):+,.0f}")
        print()

    if args.compare:
        print("=== Pair comparison ===\n")
        cmp = compare_pairs_table(df, COMPARE_DEFAULT, profile=profile)
        if not cmp.empty:
            print(cmp.to_string(index=False, formatters={
                "score": "{:.4f}".format,
                "coverage_pct": "{:.1f}".format,
                "upside_pct": "{:.1f}".format,
                "roll_tax": "{:.2f}".format,
                "short_credit": "${:,.0f}".format,
                "path_sim_score": lambda x: f"{x:,.0f}" if x == x else "—",
                "path_chop": lambda x: f"${x:+,.0f}" if x == x else "—",
            }))
        print()

    print("Why 420/430 tops *balanced* static score:")
    print("  • Highest coverage (~25%) and fastest breakeven — premium-heavy weights")
    print("  • Lowest roll tax (~0.09x) and best first-cycle net after roll")
    print("  • BUT: lowest upside room (7.4%) — challenged on small rips")
    print("  • Path sim ranks wider shorts higher (420/455, 390/510) for whipsaw/moonshot")
    print()

    print(f"Top 8 ranked pairs ({profile} score):")
    cols = ["score", "leaps_strike", "short_strike", "coverage_ratio", "upside_room_pct", "roll_tax_ratio"]
    if "path_sim_score" in df.columns:
        cols.append("path_sim_score")
    top = df.drop_duplicates(["leaps_strike", "short_strike"]).head(8)
    view = top[cols].copy()
    view["coverage_ratio"] = (view["coverage_ratio"] * 100).map(lambda x: f"{x:.1f}%")
    view["upside_room_pct"] = (view["upside_room_pct"] * 100).map(lambda x: f"{x:.1f}%")
    view["score"] = view["score"].map(lambda x: f"{x:.4f}")
    if "path_sim_score" in view.columns:
        view["path_sim_score"] = view["path_sim_score"].map(
            lambda x: f"{x:,.0f}" if x == x else "—",
        )
    print(view.to_string(index=False))
    print()
    print("Try:  just pmcc-rank --preset managed   (upside-weighted + path sim blend)")


def pd_notna(x) -> bool:
    import math
    try:
        return x == x and not (isinstance(x, float) and math.isnan(x))
    except Exception:
        return False


if __name__ == "__main__":
    main()
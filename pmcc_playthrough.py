#!/usr/bin/env python3
"""Monthly PMCC playthrough — best pair through LEAPS expiry on extreme paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from pmcc.analyze import build_pmcc_grid, format_table
from pmcc.chain_data import chain_fetch_meta, format_chain_source
from pmcc.config import MANAGEMENT_RULES, PmccConfig, apply_preset
from pmcc.paths import CANONICAL_PATHS
from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy, format_monthly_log, run_all_paths
from pmcc.scenarios import PmccPair


def main() -> None:
    ap = argparse.ArgumentParser(description="PMCC 12-month playthrough on canonical spot/IV paths")
    ap.add_argument("--preset", choices=("income", "balanced", "bullish"), default="balanced")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--path", help="single path name (default: all)")
    ap.add_argument("--leaps-strike", type=float)
    ap.add_argument("--short-strike", type=float)
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    cfg = apply_preset(PmccConfig(ticker=args.ticker), args.preset)
    cfg = PmccConfig(**{
        **cfg.__dict__,
        "chain_use_cache": not args.no_cache,
        "chain_refresh": args.refresh,
    })
    if args.preset == "bullish":
        cfg = PmccConfig(**{**cfg.__dict__, "target_spot": 550.0})

    spot, df = build_pmcc_grid(cfg)
    row = df.iloc[0]
    if args.leaps_strike and args.short_strike:
        m = df[(df.leaps_strike == args.leaps_strike) & (df.short_strike == args.short_strike)]
        if not m.empty:
            row = m.iloc[0]
    pair = PmccPair.from_row(row, spot)
    policy = POLICY_BY_PRESET.get(args.preset, PlayPolicy())

    paths = CANONICAL_PATHS
    if args.path:
        paths = tuple(p for p in paths if p.name == args.path)
        if not paths:
            raise SystemExit(f"unknown path {args.path!r}; choose {[p.name for p in CANONICAL_PATHS]}")

    print(f"\n=== PMCC playthrough — {cfg.ticker} @ ${spot:,.2f} ===")
    print(f"Preset: {args.preset}  |  policy: short {policy.short_delta_new:.2f}Δ / {policy.short_dte_new}d rolls")
    print(format_chain_source(chain_fetch_meta()))
    print()
    print("Selected pair:")
    print(f"  LEAPS  ${pair.leaps_strike:.0f}  {pair.leaps_dte}d  debit ${pair.leaps_debit:,.0f}")
    print(f"  Short  ${pair.short_strike:.0f}  {pair.short_dte}d  credit ${pair.short_credit:,.0f}")
    print(f"  Net debit ${pair.net_debit:,.0f}  score {pair.score:.3f}")
    print()
    print("Management rules:")
    key = "income" if args.preset == "income" else args.preset
    for rule in MANAGEMENT_RULES[key]:
        print(f"  • {rule}")
    print()

    detail, summary = run_all_paths(pair, paths, policy, r=cfg.risk_free_rate)

    print("=== PATH SUMMARY (final P/L at LEAPS expiry) ===\n")
    for _, s in summary.iterrows():
        label = next(p.label for p in CANONICAL_PATHS if p.name == s["path"])
        print(f"  {s['path']:<14} {label}")
        print(f"    final ${s['final_pnl']:+,.0f}  |  min ${s['min_pnl']:+,.0f}  |  max ${s['max_pnl']:+,.0f}")
    print()

    for p in paths:
        print(f"--- {p.name}: {p.label} ---\n")
        print(format_monthly_log(detail, p.name))
        print()

    worst = summary.iloc[0]
    best = summary.iloc[-1]
    print("=== STRATEGY PLAYBOOK (from playthrough) ===\n")
    print("  1. DROP (−8% month): harvest short at 55%+ profit; defer new short 45d if crash (−12%).")
    print("  2. DEEP CRASH (<75% entry): hold LEAPS only — no new shorts until recovery.")
    print("  3. BEAR (82–90% entry): sell wide shorts (0.18Δ), not tight strikes.")
    print("  4. RIP (≥ short strike): close short same day; roll up spot×1.08+ / +$35 min.")
    print("  5. FLAT/OTM near expiry: let short expire worthless; immediately sell next.")
    print(f"  6. Extremes on this pair: worst `{worst['path']}` ${worst['final_pnl']:+,.0f} | "
          f"best `{best['path']}` ${best['final_pnl']:+,.0f}")
    print()

    print("Ranked pair context (top 3 today):\n")
    print(format_table(df, 3))

    if args.csv:
        detail.to_csv(args.csv, index=False)
        print(f"Wrote {len(detail)} rows → {args.csv}")


if __name__ == "__main__":
    main()
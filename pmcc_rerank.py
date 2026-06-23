#!/usr/bin/env python3
"""Re-rank PMCC pairs using conditional LEAPS roll scoring.

Loads cached scan results, re-scores each pair with the conditional-roll
P/L (roll at 365 DTE unless LEAPS is deep ITM), and re-ranks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pmcc.daily_playthrough import (
    DailyPlayPath,
    MonthPoint,
    build_daily_paths,
    daily_policy,
    run_daily_path,
    pnl_return_pct,
)
from pmcc.playthrough import PlayPolicy, POLICY_BY_PRESET, _px
from pmcc.scenarios import PmccPair
from pmcc.config import apply_preset, PmccConfig


ROLL_DTE = 365
DEEP_ITM_THRESHOLD = 1.25


def compute_conditional_pnl(
    pair: PmccPair,
    path: DailyPlayPath,
    policy: PlayPolicy,
    *,
    r: float = 0.04,
) -> dict:
    """Compute P/L with conditional LEAPS roll.

    If LEAPS is deep ITM at roll point: use hold-to-expiry P/L.
    If not: use P/L at roll point (conservative — doesn't include cycle 2).
    """
    pol = daily_policy(policy)
    df = run_daily_path(pair, path, pol, r=r)
    if df.empty:
        return {"pnl": 0.0, "pnl_pct": 0.0, "mode": "empty"}

    final = df.iloc[-1]
    hold_pnl = float(final["net_pnl"])
    hold_pct = pnl_return_pct(hold_pnl, pair.net_debit)

    # Find P/L at roll DTE
    roll_mask = df["leaps_dte"] <= ROLL_DTE
    if not roll_mask.any():
        return {"pnl": hold_pnl, "pnl_pct": hold_pct, "mode": "hold (path short)"}

    roll_row = df[roll_mask].iloc[0]
    roll_spot = float(roll_row["spot"])
    roll_pnl = float(roll_row["net_pnl"])
    roll_pct = pnl_return_pct(roll_pnl, pair.net_debit)

    moneyness = roll_spot / pair.leaps_strike
    if moneyness >= DEEP_ITM_THRESHOLD:
        return {"pnl": hold_pnl, "pnl_pct": hold_pct, "mode": "hold (deep ITM)",
                "roll_spot": roll_spot, "moneyness": moneyness}
    else:
        return {"pnl": roll_pnl, "pnl_pct": roll_pct, "mode": "roll",
                "roll_spot": roll_spot, "moneyness": moneyness}


def score_pair_conditional(
    pair: PmccPair,
    paths: tuple[DailyPlayPath, ...],
    policy: PlayPolicy,
    *,
    r: float = 0.04,
) -> dict:
    """Score a pair using conditional-roll P/L with bull-biased weighting."""
    results = {}
    for p in paths:
        results[p.name] = compute_conditional_pnl(pair, p, policy, r=r)

    cap = pair.net_debit

    def avg_pnl(names: set[str]) -> float:
        vals = [results[n]["pnl_pct"] for n in names if n in results]
        return sum(vals) / max(len(vals), 1)

    bull_paths = {"steady_bull", "moonshot", "rip_continue", "v_recovery",
                  "single_day_rip_10"}
    whipsaw_paths = {"gap_whipsaw_double", "post_earnings_whipsaw",
                     "rip_pullback", "gap_rip_flush", "tsla_range_chop"}
    flat_paths = {"flat_chop", "flat_survival"}
    bear_paths = {"steady_bear", "crash_recover"}

    bull_avg = avg_pnl(bull_paths)
    whipsaw_avg = avg_pnl(whipsaw_paths)
    flat_avg = avg_pnl(flat_paths)
    bear_avg = avg_pnl(bear_paths)
    bear_worst = min((results[n]["pnl_pct"] for n in bear_paths if n in results),
                     default=0.0)

    # Bull-biased score: weight bull paths highest (user's directional view)
    # Whipsaw paths medium (they're common and the management works)
    # Flat paths as a gate (must survive)
    # Bear paths low weight but included (can't predict the future)
    score = (
        bull_avg * 2.0
        + whipsaw_avg * 1.5
        + flat_avg * 1.0
        + bear_avg * 0.5
    ) / 5.0

    # Penalty for bad flat/bear survival
    if flat_avg < -15:
        score -= abs(flat_avg + 15) * 0.5
    if bear_worst < -40:
        score -= abs(bear_worst + 40) * 0.3

    return {
        "score": score,
        "bull_avg": bull_avg,
        "whipsaw_avg": whipsaw_avg,
        "flat_avg": flat_avg,
        "bear_avg": bear_avg,
        "bear_worst": bear_worst,
        "flat_chop": results.get("flat_chop", {}).get("pnl_pct", 0),
        "flat_survival": results.get("flat_survival", {}).get("pnl_pct", 0),
        "rip_pullback": results.get("rip_pullback", {}).get("pnl_pct", 0),
        "rip_continue": results.get("rip_continue", {}).get("pnl_pct", 0),
        "moonshot": results.get("moonshot", {}).get("pnl_pct", 0),
        "steady_bull": results.get("steady_bull", {}).get("pnl_pct", 0),
        "steady_bear": results.get("steady_bear", {}).get("pnl_pct", 0),
        "gap_whipsaw": results.get("gap_whipsaw_double", {}).get("pnl_pct", 0),
        "by_path": results,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="managed")
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    cache_path = Path(f".cache/pmcc_pair_scan_{args.ticker}_{args.preset}.parquet")
    if not cache_path.exists():
        print(f"No cached scan at {cache_path}. Run 'just pmcc-scan --preset {args.preset}' first.")
        return

    scan = pd.read_parquet(cache_path)
    policy = POLICY_BY_PRESET[args.preset]

    # Build paths using the LEAPS DTE from the first row
    leaps_dte = int(scan.iloc[0]["leaps_dte"])
    all_paths = build_daily_paths(leaps_dte)

    # Add custom paths
    import math
    rip_pullback_days = []
    rip_continue_days = []
    flat_survival_days = []
    for d in range(1, leaps_dte + 1):
        if d < 45:
            s = 1.0
        elif d == 45:
            s = 1.15
        elif d <= 52:
            t = (d - 45) / 7
            s = 1.15 + t * (1.0 - 1.15)
        else:
            s = 1.0
        iv = max(0.75, 1.15 - 0.10 * (s - 1.0))
        rip_pullback_days.append(MonthPoint(s, iv))

        if d < 45:
            s2 = 1.0
        elif d == 45:
            s2 = 1.15
        else:
            t2 = (d - 45) / max(leaps_dte - 45, 1)
            s2 = 1.15 + t2 * (1.50 - 1.15)
        iv2 = max(0.65, 1.05 - 0.12 * (s2 - 1.0))
        rip_continue_days.append(MonthPoint(s2, iv2))

        s3 = 1.0 + 0.03 * math.sin(d / 21.0)
        flat_survival_days.append(MonthPoint(s3, 1.0))

    custom = (
        DailyPlayPath("rip_pullback", "+15% rip d45 then flush to entry",
                      tuple(rip_pullback_days)),
        DailyPlayPath("rip_continue", "+15% rip then grind to +50%",
                      tuple(rip_continue_days)),
        DailyPlayPath("flat_survival", "Flat ±3% sine wave",
                      tuple(flat_survival_days)),
    )
    paths = custom + all_paths

    print(f"\n{'='*80}")
    print(f"PMCC RE-RANK — conditional LEAPS roll (roll at {ROLL_DTE} DTE unless deep ITM)")
    print(f"{'='*80}")
    print(f"Preset: {args.preset}  |  Pairs: {len(scan)}  |  Spot: ${scan.iloc[0].get('spot', 400):.2f}")
    print(f"Scoring: bull-biased (2.0x bull, 1.5x whipsaw, 1.0x flat, 0.5x bear)")
    print(f"Gates: flat_avg > -15% penalty, bear_worst > -40% penalty")
    print()

    # Re-score each pair
    rows = []
    for i, (_, scan_row) in enumerate(scan.iterrows()):
        pair = PmccPair(
            spot_entry=float(scan_row.get("spot", 400.49)),
            leaps_strike=float(scan_row["leaps_strike"]),
            leaps_exp="2028-01-21",
            leaps_dte=int(scan_row["leaps_dte"]),
            leaps_iv=0.55,
            leaps_debit=float(scan_row["leaps_debit"]),
            short_strike=float(scan_row["short_strike"]),
            short_exp="2026-09-19",
            short_dte=int(scan_row["short_dte"]),
            short_iv=0.45,
            short_credit=float(scan_row["short_credit"]),
            leaps_delta_target=0.70,
            short_delta_target=0.20,
        )
        s = score_pair_conditional(pair, paths, policy, r=0.04)
        rows.append({
            "old_rank": int(scan_row.get("rank", 0)),
            "pair": scan_row["pair"],
            "leaps_dte": int(scan_row["leaps_dte"]),
            "short_dte": int(scan_row["short_dte"]),
            "leaps_debit": float(scan_row["leaps_debit"]),
            "short_credit": float(scan_row["short_credit"]),
            "coverage_pct": float(scan_row.get("coverage_pct", 0)),
            "new_score": s["score"],
            "bull_avg": s["bull_avg"],
            "whipsaw_avg": s["whipsaw_avg"],
            "flat_avg": s["flat_avg"],
            "bear_avg": s["bear_avg"],
            "bear_worst": s["bear_worst"],
            "flat_chop": s["flat_chop"],
            "rip_pullback": s["rip_pullback"],
            "rip_continue": s["rip_continue"],
            "moonshot": s["moonshot"],
            "steady_bull": s["steady_bull"],
            "steady_bear": s["steady_bear"],
            "gap_whipsaw": s["gap_whipsaw"],
        })
        if (i + 1) % 10 == 0:
            print(f"  ...scored {i+1}/{len(scan)} pairs")

    df = pd.DataFrame(rows).sort_values("new_score", ascending=False).reset_index(drop=True)
    df["new_rank"] = range(1, len(df) + 1)

    # Display top pairs
    print(f"\n{'TOP ' + str(args.top) + ' PAIRS — conditional roll scoring':^80}")
    print("-" * 80)
    cols = ["new_rank", "old_rank", "pair", "coverage_pct", "new_score",
            "bull_avg", "whipsaw_avg", "flat_avg", "bear_worst",
            "flat_chop", "rip_pullback", "moonshot", "steady_bear"]
    display = df[cols].head(args.top).copy()
    for c in ["bull_avg", "whipsaw_avg", "flat_avg", "bear_worst",
              "flat_chop", "rip_pullback", "moonshot", "steady_bear"]:
        display[c] = display[c].map(lambda x: f"{x:+.0f}%")
    display["new_score"] = display["new_score"].map(lambda x: f"{x:.1f}")
    display["coverage_pct"] = display["coverage_pct"].map(lambda x: f"{x:.1f}%")
    print(display.to_string(index=False))

    # Show the biggest rank changes
    print(f"\n{'BIGGEST RANK CHANGES':^80}")
    print("-" * 80)
    df["rank_change"] = df["old_rank"] - df["new_rank"]
    improved = df.nlargest(5, "rank_change")[["pair", "old_rank", "new_rank", "rank_change", "flat_chop", "new_score"]]
    declined = df.nsmallest(5, "rank_change")[["pair", "old_rank", "new_rank", "rank_change", "flat_chop", "new_score"]]
    print("Improved:")
    for _, r in improved.iterrows():
        print(f"  {r['pair']:<12} rank {int(r['old_rank']):>2} → {int(r['new_rank']):>2}  ({int(r['rank_change']):+3d})  flat={r['flat_chop']:+.0f}%  score={r['new_score']:.1f}")
    print("Declined:")
    for _, r in declined.iterrows():
        print(f"  {r['pair']:<12} rank {int(r['old_rank']):>2} → {int(r['new_rank']):>2}  ({int(r['rank_change']):+3d})  flat={r['flat_chop']:+.0f}%  score={r['new_score']:.1f}")


if __name__ == "__main__":
    main()

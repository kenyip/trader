from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from itertools import product

import pandas as pd

from pmcc.daily_playthrough import (
    BEAR_DAILY_PATHS,
    BULL_DAILY_PATHS,
    EXTREME_DAILY_PATHS,
    WHIPSAW_DAILY_PATHS,
    build_daily_paths,
    daily_policy,
    pnl_return_pct,
    run_all_daily_paths,
)
from pmcc.playthrough import PlayPolicy
from pmcc.scenarios import PmccPair


@dataclass(frozen=True)
class ScoreWeights:
    bull: float = 1.5
    extreme: float = 1.0
    whipsaw: float = 2.5
    bear_penalty: float = 0.25
    regression_penalty: float = 1.5
    bear_loss_cap: float = -3200.0


TUNE_PATH_NAMES = frozenset({
    "tsla_range_chop",
    "gap_whipsaw_double",
    "gap_rip_flush",
    "post_earnings_whipsaw",
    "steady_bull",
    "moonshot",
    "single_day_rip_10",
    "steady_bear",
})

WHIPSAW_STAGE = {
    "gap_rip_trigger_pct": (0.08, 0.10, 0.12),
    "gap_rip_proximity": (0.90, 0.93),
    "flush_harvest_pct": (-0.03, -0.05, -0.07),
    "flush_harvest_min_profit": (0.30, 0.40, 0.50),
    "reentry_cooldown_days": (7, 14, 21),
    "min_roll_gap_days": (7, 12, 18),
}

ROLL_STAGE = {
    "harvest_profit_pct": (0.40, 0.50, 0.60),
    "roll_up_pct": (0.06, 0.08, 0.10),
    "challenged_pct": (0.96, 0.98, 1.00),
    "short_delta_new": (0.22, 0.28, 0.32),
    "crash_defer_days": (30, 45, 60),
}


def _grid(stage: dict[str, tuple]) -> list[dict]:
    keys = list(stage.keys())
    return [dict(zip(keys, vals)) for vals in product(*(stage[k] for k in keys))]


def _filter_paths(all_paths: tuple, names: frozenset[str] | None) -> tuple:
    if names is None:
        return all_paths
    return tuple(p for p in all_paths if p.name in names)


def evaluate_policy(
    pair: PmccPair,
    policy: PlayPolicy,
    *,
    r: float = 0.04,
    weights: ScoreWeights | None = None,
    baseline_by_path: dict[str, float] | None = None,
    paths: tuple | None = None,
    path_names: frozenset[str] | None = None,
) -> dict:
    weights = weights or ScoreWeights()
    all_paths = paths or build_daily_paths(pair.leaps_dte)
    paths = _filter_paths(all_paths, path_names)
    pol = daily_policy(policy)
    _, summary = run_all_daily_paths(pair, paths, pol, r=r)
    by_path = {row["path"]: float(row["final_pnl"]) for _, row in summary.iterrows()}

    def _avg(names: frozenset[str]) -> float:
        vals = [pnl_return_pct(by_path[p], pair.net_debit) for p in names if p in by_path]
        return sum(vals) / max(len(vals), 1)

    bull_avg = _avg(BULL_DAILY_PATHS)
    extreme_avg = _avg({p for p in EXTREME_DAILY_PATHS if p not in WHIPSAW_DAILY_PATHS})
    whipsaw_avg = _avg(WHIPSAW_DAILY_PATHS)
    bear_vals = [by_path[p] for p in BEAR_DAILY_PATHS if p in by_path]
    bear_worst_pct = min(
        (pnl_return_pct(v, pair.net_debit) for v in bear_vals), default=0.0,
    )
    bear_pen = min(
        0.0,
        bear_worst_pct - pnl_return_pct(weights.bear_loss_cap, pair.net_debit),
    )

    pos_w = weights.bull + weights.extreme + weights.whipsaw
    score = (
        bull_avg * weights.bull
        + extreme_avg * weights.extreme
        + whipsaw_avg * weights.whipsaw
    ) / max(pos_w, 1e-9)
    score += bear_pen * weights.bear_penalty / max(pos_w, 1e-9)

    regress = 0.0
    if baseline_by_path:
        for path, old in baseline_by_path.items():
            new = by_path.get(path, old)
            if new < old:
                regress += (old - new) * weights.regression_penalty
        score -= regress

    chop_pnl = by_path.get("tsla_range_chop", 0.0)
    return {
        "score": score,
        "bull_avg": bull_avg,
        "extreme_avg": extreme_avg,
        "whipsaw_avg": whipsaw_avg,
        "bear_worst": bear_worst_pct,
        "chop_pnl": chop_pnl,
        "regression_cost": regress,
        "by_path": by_path,
    }


def _search_stage(
    pair: PmccPair,
    base: PlayPolicy,
    stage: dict[str, tuple],
    *,
    r: float,
    weights: ScoreWeights,
    baseline_by_path: dict[str, float],
    path_names: frozenset[str],
) -> tuple[PlayPolicy, dict]:
    best_p, best_s = base, evaluate_policy(
        pair, base, r=r, weights=weights, baseline_by_path=baseline_by_path, path_names=path_names,
    )
    for kw in _grid(stage):
        p = replace(base, **kw)
        s = evaluate_policy(pair, p, r=r, weights=weights, baseline_by_path=baseline_by_path, path_names=path_names)
        if s["score"] > best_s["score"]:
            best_p, best_s = p, s
    return best_p, best_s


def tune_policy(
    pair: PmccPair,
    base: PlayPolicy,
    *,
    r: float = 0.04,
    weights: ScoreWeights | None = None,
    fast: bool = True,
) -> tuple[PlayPolicy, dict, dict]:
    """Two-stage grid search: whipsaw anti-churn knobs, then roll/harvest knobs."""
    weights = weights or ScoreWeights()
    baseline = evaluate_policy(pair, base, r=r, weights=weights, path_names=None)
    baseline_by_path = baseline["by_path"]
    search_paths = TUNE_PATH_NAMES if fast else None

    p1, _ = _search_stage(
        pair, base, WHIPSAW_STAGE, r=r, weights=weights,
        baseline_by_path=baseline_by_path, path_names=search_paths,
    )
    p2, _ = _search_stage(
        pair, p1, ROLL_STAGE, r=r, weights=weights,
        baseline_by_path=baseline_by_path, path_names=search_paths,
    )
    tuned_score = evaluate_policy(pair, p2, r=r, weights=weights, path_names=None)
    return p2, tuned_score, baseline


def compare_path_table(
    baseline: dict,
    tuned: dict,
) -> pd.DataFrame:
    paths = sorted(set(baseline["by_path"]) | set(tuned["by_path"]))
    rows = []
    for p in paths:
        b = baseline["by_path"].get(p, 0.0)
        t = tuned["by_path"].get(p, 0.0)
        rows.append({
            "path": p,
            "baseline": b,
            "tuned": t,
            "delta": t - b,
            "category": (
                "whipsaw" if p in WHIPSAW_DAILY_PATHS
                else "bear" if p in BEAR_DAILY_PATHS
                else "bull" if p in BULL_DAILY_PATHS
                else "other"
            ),
        })
    return pd.DataFrame(rows).sort_values("delta", ascending=False)


def policy_knobs(policy: PlayPolicy) -> dict:
    keys = (
        "harvest_profit_pct", "roll_up_pct", "challenged_pct", "short_delta_new",
        "short_dte_new", "crash_defer_days", "gap_rip_trigger_pct", "gap_rip_proximity",
        "flush_harvest_pct", "flush_harvest_min_profit", "reentry_cooldown_days",
        "min_roll_gap_days",
    )
    return {k: getattr(policy, k) for k in keys}


def format_tune_report(
    pair: PmccPair,
    base: PlayPolicy,
    tuned: PlayPolicy,
    tuned_score: dict,
    baseline_score: dict,
    cmp: pd.DataFrame,
) -> str:
    lines = [
        f"# PMCC tune report — LEAPS ${pair.leaps_strike:.0f} / short ${pair.short_strike:.0f}",
        "",
        "## Score",
        f"- Baseline: {baseline_score['score']:,.0f}  (whipsaw avg ${baseline_score['whipsaw_avg']:+,.0f}, chop ${baseline_score['chop_pnl']:+,.0f})",
        f"- Tuned:    {tuned_score['score']:,.0f}  (whipsaw avg ${tuned_score['whipsaw_avg']:+,.0f}, chop ${tuned_score['chop_pnl']:+,.0f})",
        "",
        "## Knob changes",
    ]
    bk, tk = policy_knobs(base), policy_knobs(tuned)
    for k in bk:
        if bk[k] != tk[k]:
            lines.append(f"- {k}: {bk[k]} → {tk[k]}")
    lines.append("")
    lines.append("## Per-path delta (tuned − baseline)")
    for _, r in cmp.iterrows():
        sign = "+" if r["delta"] >= 0 else ""
        lines.append(f"- {r['path']:<22} [{r['category']}]  ${r['baseline']:+,.0f} → ${r['tuned']:+,.0f}  ({sign}${r['delta']:,.0f})")
    return "\n".join(lines)


TUNED_POLICY_BY_PRESET: dict[str, PlayPolicy] = {}


def load_tuned_policy(
    preset: str,
    leaps_strike: float,
    short_strike: float,
    base: PlayPolicy,
    *,
    cache_dir: Path | None = None,
) -> PlayPolicy:
    """Load pair-specific tuned knobs from .cache if present, else use preset base."""
    from pathlib import Path as P

    cache_dir = cache_dir or P(".cache")
    path = cache_dir / f"pmcc_tuned_{preset}_{int(leaps_strike)}_{int(short_strike)}.json"
    if not path.exists():
        return base
    import json
    data = json.loads(path.read_text())
    return replace(base, **data["knobs"])
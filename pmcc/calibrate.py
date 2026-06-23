from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pmcc.config import SCORE_PROFILES
from pmcc.pair_scan import STATIC_SCORE_COLS, load_scan
from pmcc.score import _apply_weights, _norm


@dataclass(frozen=True)
class CalibrationReport:
    n_cells: int
    n_strike_pairs: int
    spearman_static_sim: float
    spearman_static_sim_per_1k: float
    top_k_overlap: dict[int, float]
    component_corr: pd.DataFrame
    suggested_weights: dict[str, float]
    dte_picker_agreement: float
    static_surprises: pd.DataFrame
    sim_surprises: pd.DataFrame
    collapsed_static_top: pd.DataFrame


def _spearman(a: pd.Series, b: pd.Series) -> float:
    frame = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(frame) < 3:
        return float("nan")
    return float(frame["a"].corr(frame["b"], method="spearman"))


def _top_k_overlap(df: pd.DataFrame, k: int, col_a: str, col_b: str) -> float:
    sub = df.dropna(subset=[col_a, col_b])
    if len(sub) < k:
        return float("nan")
    top_a = set(sub.nlargest(k, col_a).index)
    top_b = set(sub.nlargest(k, col_b).index)
    return len(top_a & top_b) / k


def _component_correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in STATIC_SCORE_COLS:
        if col not in df.columns:
            continue
        key = col.removeprefix("score_")
        rows.append({
            "component": key,
            "corr_sim": _spearman(df[col], df["path_sim_score"]),
            "mean_norm": float(df[col].mean()),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["_abs"] = out["corr_sim"].abs()
        out = out.sort_values("_abs", ascending=False).drop(columns="_abs")
    return out.reset_index(drop=True)


def _suggest_weights(component_corr: pd.DataFrame) -> dict[str, float]:
    if component_corr.empty:
        return {}
    raw: dict[str, float] = {}
    for _, row in component_corr.iterrows():
        c = row["corr_sim"]
        if c != c:
            continue
        raw[str(row["component"])] = max(float(c), 0.0)
    total = sum(raw.values())
    if total <= 0:
        raw = {}
        for _, row in component_corr.iterrows():
            c = row["corr_sim"]
            if c != c:
                continue
            raw[str(row["component"])] = abs(float(c))
        total = sum(raw.values())
    if total <= 0:
        return {}
    return {k: round(v / total, 3) for k, v in raw.items()}


def _dte_picker_agreement(df: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    rows = []
    agree = 0
    total = 0
    for (_, _), g in df.groupby(["leaps_strike", "short_strike"]):
        if len(g) < 2:
            continue
        static_row = g.loc[g["grid_score"].idxmax()]
        sim_row = g.loc[g["path_sim_score"].idxmax()]
        same = (
            int(static_row["leaps_dte"]) == int(sim_row["leaps_dte"])
            and int(static_row["short_dte"]) == int(sim_row["short_dte"])
        )
        agree += int(same)
        total += 1
        rows.append({
            "pair": static_row["pair"],
            "static_pick": f"{int(static_row['leaps_dte'])}/{int(static_row['short_dte'])}",
            "sim_pick": f"{int(sim_row['leaps_dte'])}/{int(sim_row['short_dte'])}",
            "static_score": float(static_row["grid_score"]),
            "sim_score": float(sim_row["path_sim_score"]),
            "agree": same,
        })
    detail = pd.DataFrame(rows)
    rate = agree / total if total else float("nan")
    return rate, detail.sort_values("sim_score", ascending=False)


def _collapse_static_picks(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.groupby(["leaps_strike", "short_strike"])["grid_score"].idxmax()
    return df.loc[idx].sort_values("grid_score", ascending=False).reset_index(drop=True)


def _surprises(df: pd.DataFrame, *, kind: str, n: int = 10) -> pd.DataFrame:
    sub = df.drop_duplicates(subset=["pair_dte"] if "pair_dte" in df.columns else ["pair"]).copy()
    sub["rank_static"] = sub["grid_score"].rank(ascending=False, method="min")
    sub["rank_sim"] = sub["path_sim_score"].rank(ascending=False, method="min")
    sub["rank_gap"] = sub["rank_static"] - sub["rank_sim"]
    cols = [
        "pair_dte", "pair", "leaps_dte", "short_dte", "grid_score", "path_sim_score",
        "path_return_score", "roll_tax_burden", "rank_static", "rank_sim", "rank_gap", "bear_worst",
    ]
    cols = [c for c in cols if c in sub.columns]
    if kind == "static_high":
        return sub.nlargest(n, "rank_gap")[cols]
    return sub.nsmallest(n, "rank_gap")[cols]


def build_calibration_report(
    df: pd.DataFrame,
    *,
    profile: str = "balanced",
    top_k: tuple[int, ...] = (10, 20, 30),
) -> CalibrationReport:
    if df.empty:
        raise ValueError("empty scan — run `just pmcc-scan --mode full --refresh` first")
    work = df.copy()
    if profile == "managed" or not SCORE_PROFILES.get(profile):
        raise ValueError(
            f"profile {profile!r} is sim-only — calibrate balanced/bullish full scans instead",
        )

    component_corr = _component_correlations(work)
    dte_rate, _ = _dte_picker_agreement(work)

    return CalibrationReport(
        n_cells=len(work),
        n_strike_pairs=work.drop_duplicates(["leaps_strike", "short_strike"]).shape[0],
        spearman_static_sim=_spearman(work["grid_score"], work["path_sim_score"]),
        spearman_static_sim_per_1k=float("nan"),
        top_k_overlap={k: _top_k_overlap(work, k, "grid_score", "path_sim_score") for k in top_k},
        component_corr=component_corr,
        suggested_weights=_suggest_weights(component_corr),
        dte_picker_agreement=dte_rate,
        static_surprises=_surprises(work, kind="static_high"),
        sim_surprises=_surprises(work, kind="sim_high"),
        collapsed_static_top=_collapse_static_picks(work).head(15),
    )


def format_calibration_report(report: CalibrationReport, *, profile: str = "balanced") -> str:
    current = SCORE_PROFILES.get(profile, SCORE_PROFILES["balanced"])
    lines = [
        "=== PMCC static score calibration ===",
        f"Cells path-simmed: {report.n_cells}  |  unique strike pairs: {report.n_strike_pairs}",
        "",
        "Rank alignment (static grid_score vs path_sim_score):",
        f"  Spearman ρ:           {report.spearman_static_sim:+.3f}",

    ]
    for k, v in report.top_k_overlap.items():
        lines.append(f"  Top-{k} overlap:        {v * 100:.0f}%")
    lines.extend([
        f"  DTE picker agreement: {report.dte_picker_agreement * 100:.0f}% "
        f"(static best DTE == sim best DTE per strike pair)",
        "",
        f"Current {profile} weights:",
        "  " + ", ".join(f"{k}={v:.2f}" for k, v in current.items()),
        "",
        "Suggested weights (from component→sim correlation, renormalize to 1.0):",
    ])
    if report.suggested_weights:
        lines.append("  " + ", ".join(f"{k}={v:.3f}" for k, v in report.suggested_weights.items()))
    else:
        lines.append("  (insufficient data)")

    lines.extend(["", "Component correlations with path_sim_score:"])
    if report.component_corr.empty:
        lines.append("  (no score_* columns — run full scan)")
    else:
        for _, r in report.component_corr.iterrows():
            cs = r["corr_sim"]
            ck = r["corr_sim_per_1k"]
            cs_s = f"{cs:+.3f}" if cs == cs else "  nan"
            ck_s = f"{ck:+.3f}" if ck == ck else "  nan"
            lines.append(
                f"  {r['component']:<12} ρ={cs_s}  ρ($/1k)={ck_s}  mean_norm={r['mean_norm']:.2f}",
            )

    lines.extend([
        "",
        "Static over-rank (high static, low sim) — tweak DOWN these drivers:",
    ])
    for _, r in report.static_surprises.head(5).iterrows():
        lines.append(
            f"  {r.get('pair_dte', r['pair'])}  static #{int(r['rank_static'])} "
            f"sim #{int(r['rank_sim'])}  gap={int(r['rank_gap']):+d}",
        )

    lines.extend(["", "Sim gems (low static, high sim) — tweak UP these drivers:"])
    for _, r in report.sim_surprises.head(5).iterrows():
        lines.append(
            f"  {r.get('pair_dte', r['pair'])}  static #{int(r['rank_static'])} "
            f"sim #{int(r['rank_sim'])}  gap={int(r['rank_gap']):+d}",
        )

    lines.extend([
        "",
        "If you collapse full grid → best static per strike pair, top picks:",
    ])
    for _, r in report.collapsed_static_top.head(8).iterrows():
        lines.append(
            f"  {r.get('pair_dte', r['pair'])}  static={r['grid_score']:.3f}  "
            f"sim={r['path_sim_score']:,.0f}",
        )
    return "\n".join(lines)


def load_calibration_scan(
    preset: str = "managed",
    ticker: str = "TSLA",
) -> tuple[pd.DataFrame, str]:
    scan, meta = load_scan(preset, ticker, mode="full")
    if scan.empty:
        return scan, "no full scan — run `just pmcc-scan --mode full --refresh`"
    label = f"{len(scan)} cells"
    if meta:
        label = (
            f"{meta.n_pairs} cells @ ${meta.spot:,.2f}  "
            f"({meta.elapsed_sec:.0f}s, {meta.scanned_at.strftime('%Y-%m-%d %H:%M')} UTC)"
        )
    return scan, label


def rescore_cells(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Recompute static score from stored norm columns (calibration on balanced/bullish)."""
    return _apply_weights(df, weights)


def evaluate_weights(df: pd.DataFrame, weights: dict[str, float]) -> dict[str, float]:
    new_score = rescore_cells(df, weights)
    return {
        "spearman": _spearman(new_score, df["path_sim_score"]),
        "top10_overlap": _top_k_overlap(
            df.assign(_new=new_score), 10, "_new", "path_sim_score",
        ),
        "top20_overlap": _top_k_overlap(
            df.assign(_new=new_score), 20, "_new", "path_sim_score",
        ),
        "dte_agreement": _dte_picker_agreement(
            df.assign(grid_score=new_score.values),
        )[0],
    }


def compare_static_collapse_to_sim(df: pd.DataFrame) -> pd.DataFrame:
    """Per strike pair: static-best cell vs sim-best cell."""
    rows = []
    for (_, _), g in df.groupby(["leaps_strike", "short_strike"]):
        s = g.loc[g["grid_score"].idxmax()]
        m = g.loc[g["path_sim_score"].idxmax()]
        rows.append({
            "pair": s["pair"],
            "static_cell": s.get("pair_dte", s["pair"]),
            "sim_cell": m.get("pair_dte", m["pair"]),
            "static_sim": float(s["path_sim_score"]),
            "best_sim": float(m["path_sim_score"]),
            "sim_delta": float(m["path_sim_score"] - s["path_sim_score"]),
            "same_cell": s.get("pair_dte", s["pair"]) == m.get("pair_dte", m["pair"]),
        })
    return pd.DataFrame(rows).sort_values("sim_delta", ascending=False)
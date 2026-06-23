from __future__ import annotations

import pandas as pd

METRIC_COLS = {
    "path_sim": "path_sim_score",
    "return": "path_return_score",
    "roll_burden": "roll_tax_burden",
    "bear": "bear_worst",
}


def enrich_scan_axes(scan: pd.DataFrame, spot: float) -> pd.DataFrame:
    out = scan.copy()
    out["spread_width"] = out["short_strike"] - out["leaps_strike"]
    out["short_otm_pct"] = (out["short_strike"] - spot) / spot * 100.0
    return out


def width_bucket(width: float, step: int = 10) -> int:
    return int(round(width / step) * step)


def best_per_width(
    scan: pd.DataFrame,
    spot: float,
    *,
    metric: str = "path_sim",
    width_step: int = 10,
    min_width: int = 10,
    max_width: int = 180,
) -> pd.DataFrame:
    """Best cell in each spread-width bucket (all DTE combos)."""
    df = enrich_scan_axes(scan, spot)
    col = METRIC_COLS.get(metric, metric)
    df["width_bucket"] = df["spread_width"].map(lambda w: width_bucket(w, width_step))
    df = df[(df["width_bucket"] >= min_width) & (df["width_bucket"] <= max_width)]
    if df.empty:
        return pd.DataFrame()
    idx = df.groupby("width_bucket")[col].idxmax()
    best = df.loc[idx].sort_values("width_bucket").reset_index(drop=True)
    return best


def cells_near_width(
    scan: pd.DataFrame,
    spot: float,
    width: float,
    *,
    tolerance: float = 5.0,
) -> pd.DataFrame:
    df = enrich_scan_axes(scan, spot)
    lo, hi = width - tolerance, width + tolerance
    return df[(df["spread_width"] >= lo) & (df["spread_width"] <= hi)].copy()


def dte_matrix_at_width(
    scan: pd.DataFrame,
    spot: float,
    width: float,
    *,
    metric: str = "path_sim",
    tolerance: float = 5.0,
) -> pd.DataFrame:
    """Best pair per (leaps_dte, short_dte) near target spread width."""
    sub = cells_near_width(scan, spot, width, tolerance=tolerance)
    if sub.empty:
        return pd.DataFrame()
    col = METRIC_COLS.get(metric, metric)
    idx = sub.groupby(["leaps_dte", "short_dte"])[col].idxmax()
    picks = sub.loc[idx].sort_values(["leaps_dte", "short_dte"], ascending=[False, True])
    rows = []
    for _, r in picks.iterrows():
        rows.append({
            "leaps_dte": int(r["leaps_dte"]),
            "short_dte": int(r["short_dte"]),
            "pair": r.get("pair_dte", r["pair"]),
            "leaps": int(r["leaps_strike"]),
            "short": int(r["short_strike"]),
            "width": int(r["spread_width"]),
            "sim": float(r["path_sim_score"]),
            "return": float(r.get("path_return_score", r["path_sim_score"])),
            "roll_burden": float(r.get("roll_tax_burden", 0)),
            "bear": float(r["bear_worst"]),
            "metric": float(r[col]),
        })
    return pd.DataFrame(rows)


def top_cells_at_width(
    scan: pd.DataFrame,
    spot: float,
    width: float,
    *,
    metric: str = "path_sim",
    tolerance: float = 5.0,
    top_n: int = 8,
) -> pd.DataFrame:
    sub = cells_near_width(scan, spot, width, tolerance=tolerance)
    if sub.empty:
        return sub
    col = METRIC_COLS.get(metric, metric)
    asc = metric in ("roll_burden", "bear")
    return sub.sort_values(col, ascending=asc).head(top_n)


def compare_pairs_on_paths(
    scan: pd.DataFrame,
    pair_dtes: list[str],
    paths: tuple[str, ...] = (
        "moonshot", "gap_whipsaw_double", "steady_bear", "tsla_range_chop",
        "post_earnings_whipsaw", "steady_bull",
    ),
) -> pd.DataFrame:
    """Side-by-side path P/L for selected cells."""
    if "pair_dte" not in scan.columns:
        scan = scan.copy()
        scan["pair_dte"] = (
            scan["pair"] + "@" + scan["leaps_dte"].astype(int).astype(str)
            + "/" + scan["short_dte"].astype(int).astype(str)
        )
    rows = []
    for pdte in pair_dtes:
        m = scan[scan["pair_dte"] == pdte]
        if m.empty:
            continue
        r = m.iloc[0]
        row = {
            "cell": pdte,
            "width": int(r["short_strike"] - r["leaps_strike"]),
            "sim": r["path_sim_score"],
            "return": r.get("path_return_score", r["path_sim_score"]),
            "roll_burden": r.get("roll_tax_burden", float("nan")),
            "bear": r["bear_worst"],
        }
        for p in paths:
            col = f"path_{p}"
            row[p] = r.get(col, float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)
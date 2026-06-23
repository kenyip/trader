from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pmcc.config import PmccConfig, apply_preset
from pmcc.daily_playthrough import (
    BULL_DAILY_PATHS,
    WHIPSAW_DAILY_PATHS,
    daily_policy,
    pnl_return_pct,
    score_daily_policy,
)
from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy
from pmcc.scenarios import PmccPair
from pmcc.tune import ScoreWeights, load_tuned_policy

CACHE_DIR = Path(".cache")
SCAN_MODES = ("pairs", "full")
STATIC_SCORE_COLS = (
    "score_coverage", "score_breakeven", "score_upside", "score_challenge",
    "score_roll_eff", "score_first_cycle", "score_drop", "score_leaps_delta",
    "score_leaps_dte",
)

KEY_PATHS = (
    "tsla_range_chop",
    "gap_whipsaw_double",
    "gap_rip_flush",
    "post_earnings_whipsaw",
    "single_day_rip_10",
    "moonshot",
    "steady_bull",
    "rip_plateau",
    "v_recovery",
    "steady_bear",
    "crash_recover",
    "flat_chop",
)


@dataclass(frozen=True)
class ScanMeta:
    ticker: str
    preset: str
    spot: float
    scanned_at: datetime
    n_pairs: int
    elapsed_sec: float
    scan_mode: str = "pairs"


def _cache_path(preset: str, ticker: str, mode: str = "pairs") -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    suffix = "" if mode == "pairs" else f"_{mode}"
    return CACHE_DIR / f"pmcc_pair_scan_{ticker}_{preset}{suffix}.parquet"


def _meta_path(preset: str, ticker: str, mode: str = "pairs") -> Path:
    return _cache_path(preset, ticker, mode).with_suffix(".json")


def best_row_per_pair(df: pd.DataFrame) -> pd.DataFrame:
    """One row per strike pair — sim-best DTE cell (pairs scan collapses on path_sim_score)."""
    if "path_sim_score" in df.columns:
        return (
            df.sort_values("path_sim_score", ascending=False)
            .drop_duplicates(["leaps_strike", "short_strike"])
            .reset_index(drop=True)
        )
    return (
        df.sort_values(["leaps_dte", "short_dte"], ascending=[False, False])
        .drop_duplicates(["leaps_strike", "short_strike"])
        .reset_index(drop=True)
    )


def _path_values(score_result: dict, capital: float) -> dict[str, float]:
    by_path = score_result.get("by_path", [])
    if isinstance(by_path, list):
        return {
            x["path"]: float(x.get("final_pnl_pct", pnl_return_pct(x["final_pnl"], capital)))
            for x in by_path
        }
    return {k: pnl_return_pct(float(v), capital) for k, v in by_path.items()}


def canonical_leaps_dte_by_short(pairs_df: pd.DataFrame) -> dict[float, int]:
    """Median LEAPS DTE per short strike — fair tenor for ladder comparisons."""
    med = pairs_df.groupby("short_strike")["leaps_dte"].median()
    return {float(k): int(v) for k, v in med.items()}


def enrich_scan_metrics(scan: pd.DataFrame) -> pd.DataFrame:
    """Backfill rank_norm on older cached scans."""
    out = scan.copy()
    if "rank_norm" not in out.columns and "path_sim_norm" in out.columns:
        out["rank_norm"] = out["path_sim_norm"].rank(ascending=False, method="min").astype(int)
    return out


def dedupe_grid_cells(grid: pd.DataFrame) -> pd.DataFrame:
    """One row per physical contract combo (delta targets can map to same contract)."""
    sort_cols = [c for c in ("leaps_dte", "short_dte", "score") if c in grid.columns]
    asc = [False, False, False][: len(sort_cols)]
    return (
        grid.sort_values(sort_cols, ascending=asc)
        .drop_duplicates(["leaps_strike", "short_strike", "leaps_dte", "short_dte"])
        .reset_index(drop=True)
    )


def _scan_candidates(grid: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode not in SCAN_MODES:
        raise ValueError(f"scan mode {mode!r} not in {SCAN_MODES}")
    grid = dedupe_grid_cells(grid)
    if mode == "full":
        sort_cols = [c for c in ("path_sim_score", "leaps_dte", "short_dte") if c in grid.columns]
        if not sort_cols:
            sort_cols = ["leaps_dte", "short_dte"]
        return grid.sort_values(sort_cols, ascending=[False] * len(sort_cols)).reset_index(drop=True)
    return grid


def _scan_record(
    row: pd.Series,
    pair: PmccPair,
    ds: dict,
    paths: dict[str, float],
    *,
    canonical_dte: int | None,
    norm_score: float | None,
    include_static: bool,
) -> dict:
    bull_pnls = [paths[p] for p in BULL_DAILY_PATHS if p in paths]
    whip_pnls = [paths[p] for p in WHIPSAW_DAILY_PATHS if p in paths]
    rec: dict = {
        "leaps_strike": pair.leaps_strike,
        "short_strike": pair.short_strike,
        "pair": f"{int(pair.leaps_strike)}/{int(pair.short_strike)}",
        "pair_dte": (
            f"{int(pair.leaps_strike)}/{int(pair.short_strike)}"
            f"@{int(pair.leaps_dte)}/{int(pair.short_dte)}"
        ),
        "leaps_dte": pair.leaps_dte,
        "short_dte": pair.short_dte,
        "leaps_delta": row.get("leaps_delta", 0),
        "short_delta": row.get("short_delta", 0),
        "leaps_debit": pair.leaps_debit,
        "short_credit": pair.short_credit,
        "net_debit": pair.net_debit,
        "coverage_pct": row.get("coverage_ratio", 0) * 100,
        "upside_pct": row.get("upside_room_pct", 0) * 100,
        "roll_tax_static": row.get("roll_tax_ratio", 0),
        "grid_score": row.get("score", 0),
        "path_return_score": ds.get("path_return_score", ds["score"]),
        "roll_tax_burden": ds.get("roll_tax_burden", 0.0),
        "roll_eff_score": ds.get("roll_eff_score", 0.0),
        "roll_count_sim": ds.get("roll_count_avg", 0.0),
        "path_sim_score": ds["score"],
        "bull_avg": ds["bull_avg"],
        "whipsaw_avg": ds["whipsaw_avg"],
        "bear_worst": ds["bear_worst"],
        "bull_min": min(bull_pnls) if bull_pnls else 0.0,
        "whipsaw_min": min(whip_pnls) if whip_pnls else 0.0,
    }
    if canonical_dte is not None:
        rec["canonical_leaps_dte"] = canonical_dte
    if norm_score is not None:
        rec["path_sim_norm"] = norm_score
    if include_static:
        for col in (
            *STATIC_SCORE_COLS,
            "leaps_dte_target", "short_dte_target",
            "leaps_delta_target", "short_delta_target",
            "coverage_ratio", "cycles_to_breakeven", "challenge_pct",
            "first_cycle_net_after_roll", "drop_profit_ratio",
        ):
            if col in row.index:
                rec[col] = row[col]
    for p in KEY_PATHS:
        rec[f"path_{p}"] = paths.get(p, float("nan"))
    return rec


def _score_pair_at_dte(
    row: pd.Series,
    spot: float,
    leaps_dte: int,
    *,
    preset: str,
    policy: PlayPolicy | None,
    r: float,
    weights: ScoreWeights,
) -> float:
    pair = PmccPair.from_row(row, spot)
    if pair.leaps_dte != leaps_dte:
        pair = dataclasses.replace(pair, leaps_dte=leaps_dte)
    tune_preset = preset if preset in POLICY_BY_PRESET else "balanced"
    base = POLICY_BY_PRESET.get(preset, PlayPolicy())
    tuned = load_tuned_policy(tune_preset, pair.leaps_strike, pair.short_strike, base)
    pol = daily_policy(tuned if policy is None else policy)
    return score_daily_policy(pair, pol, r=r, bear_loss_cap=weights.bear_loss_cap)["score"]


def scan_pairs(
    grid: pd.DataFrame,
    spot: float,
    *,
    preset: str = "managed",
    mode: str = "pairs",
    policy: PlayPolicy | None = None,
    r: float = 0.04,
    weights: ScoreWeights | None = None,
    progress: callable | None = None,
) -> pd.DataFrame:
    """Run daily scenario suite on grid rows.

    pairs mode sims every DTE cell then keeps the sim-best per strike pair.
    full mode keeps every cell ranked separately.
    """
    weights = weights or ScoreWeights()
    base = POLICY_BY_PRESET.get(preset, PlayPolicy())
    candidates = _scan_candidates(grid, mode)
    dte_by_short = canonical_leaps_dte_by_short(grid)
    rows: list[dict] = []
    tune_preset = preset if preset in POLICY_BY_PRESET else "balanced"

    for i, (_, row) in enumerate(candidates.iterrows()):
        pair = PmccPair.from_row(row, spot)
        tuned = load_tuned_policy(tune_preset, pair.leaps_strike, pair.short_strike, base)
        pol = daily_policy(tuned if policy is None else policy)
        ds = score_daily_policy(pair, pol, r=r, bear_loss_cap=weights.bear_loss_cap)
        paths = _path_values(ds, pair.leaps_debit)

        label = (
            f"{int(pair.leaps_strike)}/{int(pair.short_strike)}"
            f"@{int(pair.leaps_dte)}/{int(pair.short_dte)}"
        )
        rec = _scan_record(
            row, pair, ds, paths,
            canonical_dte=None,
            norm_score=None,
            include_static=(mode == "full"),
        )
        rows.append(rec)
        if progress:
            progress(i + 1, len(candidates), str(label))

    out = pd.DataFrame(rows)
    if mode == "pairs":
        out = (
            out.sort_values("path_sim_score", ascending=False)
            .drop_duplicates(["leaps_strike", "short_strike"])
            .reset_index(drop=True)
        )
        norm_rows: list[float] = []
        canon_dtes: list[int] = []
        for _, row in out.iterrows():
            canon = int(dte_by_short.get(float(row["short_strike"]), row["leaps_dte"]))
            canon_dtes.append(canon)
            if int(row["leaps_dte"]) == canon:
                norm_rows.append(float(row["path_sim_score"]))
            else:
                grid_row = grid[
                    (grid.leaps_strike == row["leaps_strike"])
                    & (grid.short_strike == row["short_strike"])
                    & (grid.leaps_dte == canon)
                ]
                if grid_row.empty:
                    grid_row = grid[
                        (grid.leaps_strike == row["leaps_strike"])
                        & (grid.short_strike == row["short_strike"])
                    ].sort_values("leaps_dte", ascending=False).head(1)
                norm_rows.append(_score_pair_at_dte(
                    grid_row.iloc[0], spot, canon,
                    preset=preset, policy=policy, r=r, weights=weights,
                ))
        out["canonical_leaps_dte"] = canon_dtes
        out["path_sim_norm"] = norm_rows

    out = out.sort_values("path_sim_score", ascending=False).reset_index(drop=True)
    out["rank"] = range(1, len(out) + 1)
    if "grid_score" in out.columns:
        out["rank_static"] = out["grid_score"].rank(ascending=False, method="min").astype(int)
    if "path_sim_norm" in out.columns:
        out["rank_norm"] = out["path_sim_norm"].rank(ascending=False, method="min").astype(int)
    return out


def leaps_ladder(scan: pd.DataFrame, short_strike: float) -> pd.DataFrame:
    """Path sim by LEAPS strike for a fixed short (includes DTE-normalized score)."""
    scan = enrich_scan_metrics(scan)
    sub = scan[scan["short_strike"] == short_strike].sort_values("leaps_strike").copy()
    if not sub.empty and "canonical_leaps_dte" not in sub.columns and "leaps_dte" in sub.columns:
        sub["canonical_leaps_dte"] = int(sub["leaps_dte"].median())
    if not sub.empty and "canonical_leaps_dte" in sub.columns:
        sub["dte_note"] = sub.apply(
            lambda r: "ok" if int(r["leaps_dte"]) == int(r["canonical_leaps_dte"])
            else f"{int(r['leaps_dte'])}→{int(r['canonical_leaps_dte'])}",
            axis=1,
        )
    cols = [
        "leaps_strike", "pair", "leaps_dte", "canonical_leaps_dte", "dte_note",
        "net_debit", "short_credit", "upside_pct",
        "path_sim_score", "path_sim_norm", "path_return_score", "roll_tax_burden",
        "rank_norm", "whipsaw_avg", "bull_avg", "bear_worst",
        "path_tsla_range_chop", "path_moonshot", "path_gap_whipsaw_double",
        "path_steady_bear",
    ]
    cols = [c for c in cols if c in sub.columns]
    return sub[cols].copy()


def best_leaps_on_ladder(scan: pd.DataFrame, short_strike: float) -> dict[str, object]:
    """Summarize ladder winners by entry DTE and DTE-normalized sim."""
    lad = leaps_ladder(scan, short_strike)
    if lad.empty:
        return {}
    out: dict[str, object] = {}
    if "canonical_leaps_dte" in lad.columns:
        out["canonical_leaps_dte"] = int(lad["canonical_leaps_dte"].iloc[0])
    for key, col in (("raw", "path_sim_score"), ("norm", "path_sim_norm")):
        if col not in lad.columns:
            continue
        best = lad.loc[lad[col].idxmax()]
        out[f"best_{key}_pair"] = best["pair"]
        out[f"best_{key}_score"] = float(best[col])
    return out


def short_ladder(scan: pd.DataFrame, leaps_strike: float) -> pd.DataFrame:
    """Path sim by short strike for a fixed LEAPS."""
    sub = scan[scan["leaps_strike"] == leaps_strike].sort_values("short_strike")
    cols = [
        "short_strike", "pair", "net_debit", "short_credit", "upside_pct",
        "path_sim_score", "whipsaw_avg", "bull_avg", "bear_worst",
        "path_tsla_range_chop", "path_moonshot",
    ]
    cols = [c for c in cols if c in sub.columns]
    return sub[cols].copy()


def scenario_matrix(scan: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """Top pairs × key path final P/L (pair as index, sim_score column)."""
    top = scan.head(top_n)
    path_cols = [c for c in top.columns if c.startswith("path_")]
    mat = top[["pair", "path_sim_score"] + path_cols].copy()
    rename = {c: c.replace("path_", "") for c in path_cols}
    rename["path_sim_score"] = "sim_score"
    return mat.rename(columns=rename).set_index("pair")


def save_scan(scan: pd.DataFrame, meta: ScanMeta) -> Path:
    path = _cache_path(meta.preset, meta.ticker, meta.scan_mode)
    scan.to_parquet(path, index=False)
    _meta_path(meta.preset, meta.ticker, meta.scan_mode).write_text(json.dumps({
        "ticker": meta.ticker,
        "preset": meta.preset,
        "spot": meta.spot,
        "scanned_at": meta.scanned_at.isoformat(),
        "n_pairs": meta.n_pairs,
        "elapsed_sec": meta.elapsed_sec,
        "scan_mode": meta.scan_mode,
    }, indent=2))
    return path


def load_scan(
    preset: str,
    ticker: str = "TSLA",
    *,
    mode: str = "pairs",
) -> tuple[pd.DataFrame, ScanMeta | None]:
    path = _cache_path(preset, ticker, mode)
    meta_path = _meta_path(preset, ticker, mode)
    if not path.exists():
        return pd.DataFrame(), None
    scan = enrich_scan_metrics(pd.read_parquet(path))
    meta = None
    if meta_path.exists():
        raw = json.loads(meta_path.read_text())
        meta = ScanMeta(
            ticker=raw["ticker"],
            preset=raw["preset"],
            spot=raw["spot"],
            scanned_at=datetime.fromisoformat(raw["scanned_at"]),
            n_pairs=raw["n_pairs"],
            elapsed_sec=raw["elapsed_sec"],
            scan_mode=raw.get("scan_mode", mode),
        )
    return scan, meta


def run_full_scan(
    *,
    preset: str = "managed",
    ticker: str = "TSLA",
    mode: str = "pairs",
    refresh_chain: bool = False,
    use_cache: bool = True,
) -> tuple[pd.DataFrame, ScanMeta]:
    import time
    from pmcc.analyze import build_pmcc_grid

    if use_cache:
        cached, meta = load_scan(preset, ticker, mode=mode)
        if not cached.empty and meta is not None and not refresh_chain:
            return cached, meta

    t0 = time.perf_counter()
    cfg = apply_preset(PmccConfig(ticker=ticker), preset)
    cfg = PmccConfig(**{**cfg.__dict__, "chain_refresh": refresh_chain, "path_sim_top_n": 0})
    spot, grid = build_pmcc_grid(cfg)
    scan = scan_pairs(grid, spot, preset=preset, mode=mode, r=cfg.risk_free_rate)
    elapsed = time.perf_counter() - t0
    meta = ScanMeta(
        ticker=ticker,
        preset=preset,
        spot=spot,
        scanned_at=datetime.now(timezone.utc),
        n_pairs=len(scan),
        elapsed_sec=elapsed,
        scan_mode=mode,
    )
    save_scan(scan, meta)
    return scan, meta
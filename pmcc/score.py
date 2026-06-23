from __future__ import annotations

import pandas as pd

from pmcc.config import PmccConfig, SCORE_PROFILES


def _norm(series: pd.Series, higher_better: bool) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi <= lo:
        return pd.Series(0.5, index=series.index)
    scaled = (series - lo) / (hi - lo)
    return scaled if higher_better else 1.0 - scaled


def _apply_weights(out: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    score = pd.Series(0.0, index=out.index)
    for key, w in weights.items():
        col = f"score_{key}"
        if col in out.columns and w > 0:
            score += w * out[col]
    return score


def add_scores(df: pd.DataFrame, cfg: PmccConfig) -> pd.DataFrame:
    out = df.copy()
    profile = dict(SCORE_PROFILES[cfg.score_profile])

    if cfg.target_spot is None:
        profile.pop("path_net", None)
        profile.pop("rolls", None)
    else:
        total = sum(profile.values())
        if total > 0:
            profile = {k: v / total for k, v in profile.items()}

    norms: dict[str, tuple[str, bool]] = {
        "coverage": ("coverage_ratio", True),
        "breakeven": ("cycles_to_breakeven", False),
        "upside": ("upside_room_pct", True),
        "challenge": ("challenge_pct", True),
        "roll_eff": ("roll_tax_ratio", False),
        "first_cycle": ("first_cycle_net_after_roll", True),
        "leaps_delta": ("leaps_delta", True),
        "leaps_dte": ("leaps_dte", True),
        "drop": ("drop_profit_ratio", True),
        "path_net": ("path_short_net", True),
        "rolls": ("rolls_to_target", False),
    }
    for key, (col, higher) in norms.items():
        if key not in profile or col not in out.columns:
            continue
        out[f"score_{key}"] = _norm(out[col], higher_better=higher)

    if "clears_target" in out.columns and "score_path_net" in out.columns:
        out.loc[~out["clears_target"], "score_path_net"] *= 0.5

    if profile:
        out["score"] = _apply_weights(out, profile)
        out = out.sort_values("score", ascending=False)
    else:
        out["score"] = 0.0
        sort_cols = [c for c in ("leaps_dte", "short_dte") if c in out.columns]
        if sort_cols:
            out = out.sort_values(sort_cols, ascending=[False] * len(sort_cols))
    out["score_profile"] = cfg.score_profile
    return out.reset_index(drop=True)


def golden_ratio_summary(df: pd.DataFrame, top_n: int = 5) -> dict:
    top = df.head(top_n)
    if top.empty:
        return {}
    out = {
        "median_coverage_pct": float(top["coverage_ratio"].median() * 100),
        "median_cycles": float(top["cycles_to_breakeven"].median()),
        "median_upside_pct": float(top["upside_room_pct"].median() * 100),
        "median_roll_tax": float(top["roll_tax_ratio"].median()),
        "median_first_cycle_net": float(top["first_cycle_net_after_roll"].median()),
        "mode_leaps_dte": int(top["leaps_dte_target"].mode().iloc[0]),
        "mode_short_dte": int(top["short_dte_target"].mode().iloc[0]),
        "mode_leaps_delta": float(top["leaps_delta_target"].mode().iloc[0]),
        "mode_short_delta": float(top["short_delta_target"].mode().iloc[0]),
    }
    if "drop_profit_ratio" in top.columns:
        out["median_drop_profit_pct"] = float(top["drop_profit_ratio"].median() * 100)
    if "rolls_to_target" in top.columns:
        out["median_rolls_to_target"] = float(top["rolls_to_target"].median())
        out["median_path_short_net"] = float(top["path_short_net"].median())
    if "score_profile" in top.columns:
        out["score_profile"] = str(top["score_profile"].iloc[0])
    return out
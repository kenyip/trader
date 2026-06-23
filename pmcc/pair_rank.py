from __future__ import annotations

import pandas as pd

from pmcc.config import PmccConfig, SCORE_PROFILES
from pmcc.daily_playthrough import daily_policy, score_daily_policy
from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy
from pmcc.scenarios import PmccPair
from pmcc.score import _norm


def score_contributions(row: pd.Series, profile: str) -> pd.DataFrame:
    weights = SCORE_PROFILES[profile]
    rows = []
    for key, w in weights.items():
        col = f"score_{key}"
        if col not in row.index or w <= 0:
            continue
        norm = float(row[col])
        rows.append({
            "component": key,
            "norm": norm,
            "weight": w,
            "contrib": norm * w,
        })
    return pd.DataFrame(rows).sort_values("contrib", ascending=False)


def explain_pair(row: pd.Series, *, profile: str = "balanced") -> str:
    weights = SCORE_PROFILES.get(profile, {})
    if not weights:
        return (
            f"Pair LEAPS ${row['leaps_strike']:.0f} / short ${row['short_strike']:.0f}\n"
            f"Static score unused ({profile} is sim-only). "
            f"Use path sim rank — see `just pmcc-scan`."
        )
    lines = [
        f"Pair LEAPS ${row['leaps_strike']:.0f} / short ${row['short_strike']:.0f}  "
        f"(score {row['score']:.4f})",
        "",
        "Raw metrics:",
        f"  Coverage:      {row['coverage_ratio']*100:.1f}% of LEAPS debit  "
        f"(${row['short_credit']:,.0f} credit)",
        f"  Upside room:   {row['upside_room_pct']*100:.1f}% before short is challenged  "
        f"(${row['upside_room']:.0f})",
        f"  Roll tax:      {row['roll_tax_ratio']:.2f}x first-cycle credit",
        f"  1st-cycle net: ${row['first_cycle_net_after_roll']:+,.0f} after challenge roll",
        f"  Drop harvest:  {row.get('drop_profit_ratio', 0)*100:.0f}% profit on −10% dip",
        "",
        "Why this score (weighted components):",
    ]
    contrib = score_contributions(row, profile)
    for _, c in contrib.iterrows():
        bar = "█" * int(c["contrib"] * 20)
        lines.append(
            f"  {c['component']:<12} {c['contrib']:.4f}  "
            f"(norm {c['norm']:.2f} × weight {c['weight']:.2f})  {bar}",
        )
    top = contrib.iloc[0]["component"] if not contrib.empty else "?"
    lines.append("")
    lines.append(f"Top driver: **{top}**")
    if float(row["upside_room_pct"]) < 0.10:
        lines.append(
            "Note: low upside room — challenged quickly on rips; "
            "grid score may favor premium over path management.",
        )
    return "\n".join(lines)


PINNED_PAIRS = (
    (420, 430),
    (420, 455),
    (420, 480),
    (420, 510),
    (390, 510),
)


def _unique_pairs(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.sort_values("score", ascending=False)
        .drop_duplicates(["leaps_strike", "short_strike"])
        .reset_index(drop=True)
    )


def enrich_path_sim(
    df: pd.DataFrame,
    spot: float,
    *,
    top_n: int = 20,
    preset: str = "balanced",
    policy: PlayPolicy | None = None,
    r: float = 0.04,
) -> pd.DataFrame:
    """Run daily path sim on top-N unique strike pairs; add path_sim_score."""
    out = df.copy()
    policy = daily_policy(policy or POLICY_BY_PRESET.get(preset, PlayPolicy()))
    unique = _unique_pairs(out).head(top_n)
    pinned = out[
        out.apply(
            lambda r: (int(r["leaps_strike"]), int(r["short_strike"])) in PINNED_PAIRS,
            axis=1,
        )
    ].drop_duplicates(["leaps_strike", "short_strike"])
    candidates = pd.concat([unique, pinned]).drop_duplicates(["leaps_strike", "short_strike"])

    sim_map: dict[tuple[float, float], dict] = {}
    for _, row in candidates.iterrows():
        pair = PmccPair.from_row(row, spot)
        s = score_daily_policy(pair, policy, r=r)
        by_path = s.get("by_path", [])
        if isinstance(by_path, list):
            chop = next((x["final_pnl"] for x in by_path if x.get("path") == "tsla_range_chop"), float("nan"))
        else:
            chop = by_path.get("tsla_range_chop", float("nan"))
        sim_map[(float(row["leaps_strike"]), float(row["short_strike"]))] = {
            "score": s["score"],
            "whipsaw_avg": s.get("whipsaw_avg", float("nan")),
            "chop": chop,
        }

    def _lookup(r: pd.Series, key: str) -> float:
        k = (float(r["leaps_strike"]), float(r["short_strike"]))
        return sim_map.get(k, {}).get(key, float("nan"))

    out["path_sim_score"] = out.apply(lambda r: _lookup(r, "score"), axis=1)
    out["path_whipsaw_avg"] = out.apply(lambda r: _lookup(r, "whipsaw_avg"), axis=1)
    out["path_chop_pnl"] = out.apply(lambda r: _lookup(r, "chop"), axis=1)

    scored = out["path_sim_score"].dropna()
    if scored.empty:
        out["score_path_sim"] = 0.5
    else:
        out["score_path_sim"] = _norm(out["path_sim_score"].fillna(scored.median()), higher_better=True)

    return out


def blend_scores(df: pd.DataFrame, cfg: PmccConfig) -> pd.DataFrame:
    out = df.copy()
    blend = cfg.path_sim_blend
    if blend <= 0 or "score_path_sim" not in out.columns:
        return out
    out["score_static"] = out["score"]
    has_sim = out["path_sim_score"].notna()
    out.loc[has_sim, "score"] = (
        (1 - blend) * out.loc[has_sim, "score_static"]
        + blend * out.loc[has_sim, "score_path_sim"]
    )
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def compare_pairs_table(
    df: pd.DataFrame,
    pairs: list[tuple[float, float]],
    *,
    profile: str = "balanced",
) -> pd.DataFrame:
    rows = []
    for lk, sk in pairs:
        m = df[(df.leaps_strike == lk) & (df.short_strike == sk)]
        if m.empty:
            continue
        r = m.sort_values("score", ascending=False).iloc[0]
        c = score_contributions(r, profile)
        rows.append({
            "pair": f"{int(lk)}/{int(sk)}",
            "score": r["score"],
            "coverage_pct": r["coverage_ratio"] * 100,
            "upside_pct": r["upside_room_pct"] * 100,
            "roll_tax": r["roll_tax_ratio"],
            "short_credit": r["short_credit"],
            "top_driver": c.iloc[0]["component"] if not c.empty else "",
            "path_sim_score": r.get("path_sim_score", float("nan")),
            "path_chop": r.get("path_chop_pnl", float("nan")),
        })
    return pd.DataFrame(rows)
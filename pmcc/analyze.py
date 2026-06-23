from __future__ import annotations

import numpy as np
import pandas as pd

from pmcc.chain_data import fetch_call_chain, pick_contract, pick_contract_at_strike
from pmcc.config import PmccConfig, resolve_strike_grids
from pmcc.path_score import simulate_path_to_target
from pmcc.roll_cost import estimate_challenge_roll, estimate_drop_scenario
from pmcc.playthrough import POLICY_BY_PRESET
from pmcc.score import add_scores, golden_ratio_summary


def _pair_valid(
    leaps: pd.Series,
    short: pd.Series,
    spot: float,
    cfg: PmccConfig,
) -> bool:
    if short["dte"] >= leaps["dte"]:
        return False
    if short["strike"] < leaps["strike"] + cfg.min_short_strike_offset:
        return False
    if cfg.min_short_dte is not None and int(short["dte"]) < cfg.min_short_dte:
        return False
    if short["bid"] < cfg.min_short_bid:
        return False
    if leaps["ask"] <= 0:
        return False
    if cfg.leaps_delta_min is not None and leaps["delta"] < cfg.leaps_delta_min:
        return False
    if cfg.leaps_delta_max is not None and leaps["delta"] > cfg.leaps_delta_max:
        return False
    if short["spread_pct"] > cfg.max_bid_ask_spread_pct:
        return False
    if leaps["spread_pct"] > cfg.max_bid_ask_spread_pct:
        return False
    return True


def _build_row(
    leaps: pd.Series,
    short: pd.Series,
    spot: float,
    leaps_dte_tgt: int,
    short_dte_tgt: int,
    leaps_delta_tgt: float,
    short_delta_tgt: float,
    cfg: PmccConfig,
) -> dict:
    leaps_debit = leaps["ask"] * 100.0
    short_credit = short["bid"] * 100.0
    coverage = short_credit / leaps_debit if leaps_debit > 0 else 0.0
    cycles = leaps_debit / short_credit if short_credit > 0 else np.inf
    upside_room = short["strike"] - spot
    upside_pct = upside_room / spot if spot > 0 else 0.0
    spread_width = short["strike"] - leaps["strike"]
    net_theta = (short["theta_per_day"] - leaps["theta_per_day"]) * 100.0
    roll = estimate_challenge_roll(
        spot_entry=spot,
        leaps_strike=float(leaps["strike"]),
        short_strike=float(short["strike"]),
        short_dte=int(short["dte"]),
        short_iv=float(short["iv"]),
        short_credit=short_credit,
        challenge_day_frac=cfg.challenge_day_frac,
        roll_dte=cfg.roll_dte,
        r=cfg.risk_free_rate,
    )
    drop = estimate_drop_scenario(
        spot_entry=spot,
        short_strike=float(short["strike"]),
        short_dte=int(short["dte"]),
        short_iv=float(short["iv"]),
        short_credit=short_credit,
        challenge_day_frac=cfg.challenge_day_frac,
        r=cfg.risk_free_rate,
    )
    path = {}
    if cfg.target_spot is not None:
        path = simulate_path_to_target(
            spot_entry=spot,
            target_spot=cfg.target_spot,
            leaps_strike=float(leaps["strike"]),
            short_strike=float(short["strike"]),
            short_dte=int(short["dte"]),
            short_iv=float(short["iv"]),
            short_credit=short_credit,
            roll_dte=cfg.roll_dte,
            challenge_day_frac=cfg.challenge_day_frac,
            r=cfg.risk_free_rate,
        )

    return {
        "leaps_dte_target": leaps_dte_tgt,
        "short_dte_target": short_dte_tgt,
        "leaps_delta_target": leaps_delta_tgt,
        "short_delta_target": short_delta_tgt,
        "leaps_exp": leaps["expiration"],
        "leaps_dte": int(leaps["dte"]),
        "leaps_strike": leaps["strike"],
        "leaps_delta": leaps["delta"],
        "leaps_debit": leaps_debit,
        "leaps_spread_pct": leaps["spread_pct"],
        "short_exp": short["expiration"],
        "short_dte": int(short["dte"]),
        "short_strike": short["strike"],
        "short_delta": short["delta"],
        "short_credit": short_credit,
        "short_spread_pct": short["spread_pct"],
        "spread_width": spread_width,
        "coverage_ratio": coverage,
        "cycles_to_breakeven": cycles,
        "upside_room": upside_room,
        "upside_room_pct": upside_pct,
        "net_theta_per_day": net_theta,
        "leaps_iv": leaps["iv"],
        "short_iv": short["iv"],
        "spot": spot,
        **roll,
        **drop,
        **path,
    }


def _grid_cell_count(cfg: PmccConfig, spot: float) -> int:
    dte_cells = len(cfg.leaps_dte_grid) * len(cfg.short_dte_grid)
    if cfg.grid_mode == "strike":
        leaps_s, short_s = resolve_strike_grids(cfg, spot)
        return dte_cells * len(leaps_s) * len(short_s)
    return dte_cells * len(cfg.leaps_delta_grid) * len(cfg.short_delta_grid)


def _append_pair(
    rows: list[dict],
    leaps_leg: pd.Series,
    short_leg: pd.Series,
    spot: float,
    leaps_dte_tgt: int,
    short_dte_tgt: int,
    leaps_delta_tgt: float,
    short_delta_tgt: float,
    cfg: PmccConfig,
) -> None:
    if not _pair_valid(leaps_leg, short_leg, spot, cfg):
        return
    upside = (float(short_leg["strike"]) - spot) / spot
    if cfg.short_upside_min_pct is not None and upside < cfg.short_upside_min_pct:
        return
    if cfg.short_upside_max_pct is not None and upside > cfg.short_upside_max_pct:
        return
    rows.append(_build_row(
        leaps_leg, short_leg, spot,
        leaps_dte_tgt, short_dte_tgt, leaps_delta_tgt, short_delta_tgt, cfg,
    ))


def build_pmcc_grid(cfg: PmccConfig, chain: pd.DataFrame | None = None) -> tuple[float, pd.DataFrame]:
    if chain is None:
        spot, chain = fetch_call_chain(
            cfg.ticker,
            r=cfg.risk_free_rate,
            use_cache=cfg.chain_use_cache,
            refresh=cfg.chain_refresh,
            max_age_minutes=cfg.chain_max_age_minutes,
        )
    else:
        spot = float(chain["spot"].iloc[0])

    rows: list[dict] = []
    if cfg.grid_mode == "strike":
        leaps_strikes, short_strikes = resolve_strike_grids(cfg, spot)
        for leaps_dte in cfg.leaps_dte_grid:
            for leaps_strike in leaps_strikes:
                leaps_leg = pick_contract_at_strike(
                    chain, leaps_strike, leaps_dte,
                    dte_min=cfg.leaps_dte_min,
                    dte_max=cfg.leaps_dte_max,
                )
                if leaps_leg is None:
                    continue
                for short_dte in cfg.short_dte_grid:
                    for short_strike in short_strikes:
                        if short_strike <= leaps_strike:
                            continue
                        short_leg = pick_contract_at_strike(
                            chain, short_strike, short_dte,
                            dte_max=cfg.short_dte_max,
                        )
                        if short_leg is None:
                            continue
                        _append_pair(
                            rows, leaps_leg, short_leg, spot,
                            leaps_dte, short_dte,
                            float(leaps_leg["delta"]), float(short_leg["delta"]),
                            cfg,
                        )
    else:
        for leaps_dte in cfg.leaps_dte_grid:
            for leaps_delta in cfg.leaps_delta_grid:
                leaps_leg = pick_contract(
                    chain, leaps_dte, leaps_delta,
                    dte_min=cfg.leaps_dte_min,
                    dte_max=cfg.leaps_dte_max,
                )
                if leaps_leg is None:
                    continue
                for short_dte in cfg.short_dte_grid:
                    for short_delta in cfg.short_delta_grid:
                        short_leg = pick_contract(
                            chain, short_dte, short_delta, dte_max=cfg.short_dte_max,
                        )
                        if short_leg is None:
                            continue
                        _append_pair(
                            rows, leaps_leg, short_leg, spot,
                            leaps_dte, short_dte, leaps_delta, short_delta, cfg,
                        )

    if not rows:
        raise RuntimeError("no valid PMCC pairs found — widen grids or relax spread filters")

    df = add_scores(pd.DataFrame(rows), cfg)
    df = (
        df.sort_values("score", ascending=False)
        .drop_duplicates(["leaps_strike", "short_strike", "leaps_dte", "short_dte"])
        .reset_index(drop=True)
    )
    if cfg.path_sim_top_n > 0:
        from pmcc.pair_rank import blend_scores, enrich_path_sim
        preset_key = cfg.score_profile if cfg.score_profile in POLICY_BY_PRESET else "balanced"
        df = enrich_path_sim(df, spot, top_n=cfg.path_sim_top_n, preset=preset_key, r=cfg.risk_free_rate)
        df = blend_scores(df, cfg)
    return spot, df


def format_table(df: pd.DataFrame, n: int, *, show_roll: bool = True) -> str:
    cols = [
        "score", "leaps_dte_target", "short_dte_target",
        "leaps_delta_target", "short_delta_target",
        "leaps_strike", "short_strike", "leaps_debit", "short_credit",
        "coverage_ratio", "cycles_to_breakeven", "upside_room_pct",
    ]
    if show_roll and "roll_tax_ratio" in df.columns:
        cols.extend([
            "roll_tax_ratio", "first_cycle_net_after_roll", "drop_profit_ratio",
        ])
    if "rolls_to_target" in df.columns:
        cols.extend(["rolls_to_target", "path_short_net", "clears_target"])
    cols.extend(["net_theta_per_day", "leaps_exp", "short_exp"])
    view = df.head(n)[cols].copy()
    view["coverage_ratio"] = (view["coverage_ratio"] * 100).map(lambda x: f"{x:.2f}%")
    view["upside_room_pct"] = (view["upside_room_pct"] * 100).map(lambda x: f"{x:.1f}%")
    view["cycles_to_breakeven"] = view["cycles_to_breakeven"].map(lambda x: f"{x:.1f}")
    view["leaps_debit"] = view["leaps_debit"].map(lambda x: f"${x:,.0f}")
    view["short_credit"] = view["short_credit"].map(lambda x: f"${x:,.0f}")
    view["net_theta_per_day"] = view["net_theta_per_day"].map(lambda x: f"${x:+.1f}")
    view["score"] = view["score"].map(lambda x: f"{x:.3f}")
    if "roll_tax_ratio" in view.columns:
        view["roll_tax_ratio"] = view["roll_tax_ratio"].map(lambda x: f"{x:.2f}x")
        view["first_cycle_net_after_roll"] = view["first_cycle_net_after_roll"].map(
            lambda x: f"${x:+,.0f}",
        )
    if "drop_profit_ratio" in view.columns:
        view["drop_profit_ratio"] = view["drop_profit_ratio"].map(lambda x: f"{x:.0%}")
    if "rolls_to_target" in view.columns:
        view["path_short_net"] = view["path_short_net"].map(lambda x: f"${x:+,.0f}")
    return view.to_string(index=False)


def dte_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """Best score per (leaps_dte_target, short_dte_target) — the DTE ratio map."""
    return (
        df.groupby(["leaps_dte_target", "short_dte_target"])["score"]
        .max()
        .unstack("short_dte_target")
        .sort_index(ascending=False)
    )


def format_heatmap(pivot: pd.DataFrame) -> str:
    fmt = pivot.copy()
    for c in fmt.columns:
        fmt[c] = fmt[c].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    return fmt.to_string()


def run_analysis(cfg: PmccConfig, top: int = 30) -> dict:
    spot, df = build_pmcc_grid(cfg)
    summary = golden_ratio_summary(df, top_n=min(top, len(df)))
    return {
        "ticker": cfg.ticker,
        "spot": spot,
        "n_pairs": len(df),
        "n_grid": _grid_cell_count(cfg, spot),
        "top": df.head(top),
        "all": df,
        "summary": summary,
        "heatmap": dte_heatmap(df),
    }
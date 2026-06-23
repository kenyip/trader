from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pmcc.paths import CANONICAL_PATHS, MonthPoint, PlayPath
from pmcc.playthrough import PlayPolicy, run_path
from pmcc.scenarios import PmccPair

PATH_RETURN_WEIGHT = 0.55
ROLL_EFF_WEIGHT = 0.35
BEAR_BLEND_WEIGHT = 0.10
ROLL_EFF_SCALE = 3.0

PATH_RETURN_WEIGHTS: dict[str, float] = {
    "steady_bull": 2.0,
    "rip_plateau": 2.0,
    "v_recovery": 2.0,
    "moonshot": 2.0,
    "single_day_rip_10": 1.8,
    "gap_rip_then_plateau": 1.8,
    "double_gap_rip": 1.8,
    "gap_rip_flush": 1.8,
    "gap_whipsaw_double": 1.8,
    "tsla_range_chop": 1.8,
    "post_earnings_whipsaw": 1.8,
    "flat_chop": 1.0,
    "crash_recover": 1.0,
}

BEAR_PATHS = frozenset({"steady_bear", "crash_recover"})
BEAR_DAILY_PATHS = BEAR_PATHS
ROLL_BURDEN_PATHS = frozenset(k for k in PATH_RETURN_WEIGHTS if k not in BEAR_PATHS | {"flat_chop"})

BULL_DAILY_PATHS = frozenset({
    "steady_bull", "rip_plateau", "v_recovery", "moonshot",
    "single_day_rip_10", "gap_rip_then_plateau", "double_gap_rip",
})
WHIPSAW_DAILY_PATHS = frozenset({
    "gap_rip_flush", "gap_whipsaw_double", "tsla_range_chop", "post_earnings_whipsaw",
})
EXTREME_DAILY_PATHS = frozenset({
    "single_day_rip_10", "gap_rip_then_plateau", "double_gap_rip", *WHIPSAW_DAILY_PATHS,
})


@dataclass(frozen=True)
class DailyPlayPath:
    name: str
    label: str
    days: tuple[MonthPoint, ...]


def expand_monthly_to_daily(
    path: PlayPath,
    leaps_dte: int,
    *,
    shock_day: int | None = None,
    shock_pct: float = 0.10,
) -> DailyPlayPath:
    """Linearly interpolate monthly spot/IV points to one row per calendar day."""
    n_months = len(path.months)
    if n_months < 2:
        raise ValueError("path needs ≥2 monthly points")

    month_days = np.linspace(0, leaps_dte, n_months, dtype=int)
    spots = np.array([p.spot_mult for p in path.months])
    ivs = np.array([p.iv_mult for p in path.months])

    day_idx = np.arange(leaps_dte + 1)
    spot_mult = np.interp(day_idx, month_days, spots)
    iv_mult = np.interp(day_idx, month_days, ivs)

    if shock_day is not None and 0 < shock_day < len(spot_mult):
        prev = spot_mult[shock_day - 1]
        bump = prev * (1 + shock_pct) / max(spot_mult[shock_day], 1e-9)
        spot_mult[shock_day:] *= bump
        iv_mult[shock_day:] *= 1.03

    days = tuple(
        MonthPoint(float(spot_mult[d]), float(iv_mult[d]))
        for d in range(1, leaps_dte + 1)
    )
    suffix = f" (day {shock_day} +{shock_pct:.0%})" if shock_day else ""
    return DailyPlayPath(path.name, path.label + suffix, days)


def _flat_then_rip(leaps_dte: int, flat_days: int, rip_pct: float, end_mult: float) -> DailyPlayPath:
    days: list[MonthPoint] = []
    rip_spot = 1.0 * (1 + rip_pct)
    for d in range(1, leaps_dte + 1):
        if d < flat_days:
            spot = 1.0
        elif d == flat_days:
            spot = rip_spot
        else:
            t = (d - flat_days) / max(leaps_dte - flat_days, 1)
            spot = rip_spot + t * (end_mult - rip_spot)
        iv = max(0.70, 1.0 - 0.15 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "single_day_rip_10",
        f"Flat {flat_days}d then +{rip_pct:.0%} single-day rip",
        tuple(days),
    )


def _double_gap_rip(leaps_dte: int) -> DailyPlayPath:
    days: list[MonthPoint] = []
    spot = 1.0
    gaps = {30: 0.10, 90: 0.10}
    for d in range(1, leaps_dte + 1):
        if d in gaps:
            spot *= 1 + gaps[d]
        else:
            spot *= 1.002
        iv = max(0.65, 1.0 - 0.12 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "double_gap_rip",
        "Two +10% gap days (d30, d90) then grind up",
        tuple(days),
    )


def _gap_rip_flush(
    leaps_dte: int,
    *,
    rip_day: int = 45,
    rip_pct: float = 0.10,
    flush_pct: float = -0.06,
    flush_days: int = 5,
    end_mult: float = 1.20,
) -> DailyPlayPath:
    """+10% gap day then give back ~6% over 5d — 13 historical TSLA instances in 10y."""
    days: list[MonthPoint] = []
    spot = 1.0
    rip_spot = 1.0 * (1 + rip_pct)
    flush_end = rip_spot * (1 + flush_pct)
    for d in range(1, leaps_dte + 1):
        if d < rip_day:
            spot = 1.0
        elif d == rip_day:
            spot = rip_spot
        elif rip_day < d <= rip_day + flush_days:
            t = (d - rip_day) / flush_days
            spot = rip_spot + t * (flush_end - rip_spot)
        else:
            t = (d - rip_day - flush_days) / max(leaps_dte - rip_day - flush_days, 1)
            spot = flush_end + t * (end_mult - flush_end)
        iv = max(0.75, 1.08 - 0.08 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "gap_rip_flush",
        f"+{rip_pct:.0%} gap d{rip_day} then {flush_pct:.0%} flush over {flush_days}d",
        tuple(days),
    )


def _gap_whipsaw_double(leaps_dte: int) -> DailyPlayPath:
    """Rip → flush → rip → flush — two cycles, common TSLA quarterly chop."""
    rip_days = {30: 0.10, 90: 0.08}
    flush_cfg = {30: (5, -0.06), 90: (5, -0.05)}
    days: list[MonthPoint] = []
    spot = 1.0
    flush_state: tuple[float, float, int, int] | None = None

    for d in range(1, leaps_dte + 1):
        if flush_state is not None:
            start, end, left, total = flush_state
            step = total - left + 1
            spot = start + (step / total) * (end - start)
            left -= 1
            flush_state = (start, end, left, total) if left > 0 else None
        elif d in rip_days:
            spot *= 1 + rip_days[d]
            n, pct = flush_cfg[d]
            flush_state = (spot, spot * (1 + pct), n, n)
        else:
            spot *= 1.001
        iv = max(0.78, 1.08 - 0.06 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))

    return DailyPlayPath(
        "gap_whipsaw_double",
        "Rip+flush twice (d30 +10%/-6%, d90 +8%/-5%)",
        tuple(days),
    )


def _tsla_range_chop(leaps_dte: int) -> DailyPlayPath:
    """Flat net year but violent two-way ±6–8% swings every ~3 weeks."""
    days: list[MonthPoint] = []
    spot = 1.0
    swing_schedule = []
    d = 14
    direction = 1
    while d < leaps_dte:
        swing_schedule.append((d, direction * 0.07))
        d += 21
        direction *= -1

    swing_map = dict(swing_schedule)
    for day in range(1, leaps_dte + 1):
        if day in swing_map:
            spot *= 1 + swing_map[day]
        else:
            spot *= 1.0003
        iv = max(0.85, 1.05 - 0.03 * abs(spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "tsla_range_chop",
        "Flat net ±7% swings every ~3wk (60d whipsaw windows)",
        tuple(days),
    )


def _post_earnings_whipsaw(leaps_dte: int) -> DailyPlayPath:
    """Earnings-style gap up +12%, next week −8%, then slow recovery."""
    days: list[MonthPoint] = []
    spot = 1.0
    for d in range(1, leaps_dte + 1):
        if d == 60:
            spot *= 1.12
        elif 61 <= d <= 67:
            spot *= 0.988
        elif d > 67:
            spot *= 1.0018
        iv = max(0.70, 1.15 - 0.10 * (spot - 1.0)) if 58 <= d <= 70 else max(0.80, 1.0 - 0.04 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "post_earnings_whipsaw",
        "Earnings +12% gap then −8% week, slow recovery",
        tuple(days),
    )


def _gap_rip_then_plateau(leaps_dte: int) -> DailyPlayPath:
    days: list[MonthPoint] = []
    spot = 1.0
    for d in range(1, leaps_dte + 1):
        if d == 45:
            spot *= 1.10
        elif d > 45 and d <= 120:
            spot *= 1.003
        elif d > 120:
            spot *= 0.9995
        iv = max(0.72, 1.05 - 0.10 * (spot - 1.0))
        days.append(MonthPoint(spot, iv))
    return DailyPlayPath(
        "gap_rip_then_plateau",
        "+10% gap at d45 (short challenged) then plateau",
        tuple(days),
    )


def build_daily_paths(leaps_dte: int) -> tuple[DailyPlayPath, ...]:
    expanded = [
        expand_monthly_to_daily(p, leaps_dte)
        for p in CANONICAL_PATHS
    ]
    special = (
        _flat_then_rip(leaps_dte, flat_days=45, rip_pct=0.10, end_mult=1.55),
        _gap_rip_then_plateau(leaps_dte),
        _double_gap_rip(leaps_dte),
        _gap_rip_flush(leaps_dte),
        _gap_whipsaw_double(leaps_dte),
        _tsla_range_chop(leaps_dte),
        _post_earnings_whipsaw(leaps_dte),
    )
    names_seen = {p.name for p in expanded}
    extra = [p for p in special if p.name not in names_seen]
    return tuple(expanded) + tuple(extra)


def daily_to_play_path(daily: DailyPlayPath) -> PlayPath:
    return PlayPath(daily.name, daily.label, daily.days)


def daily_policy(base: PlayPolicy | None = None) -> PlayPolicy:
    p = base or PlayPolicy()
    return PlayPolicy(
        step_days=1,
        short_dte_new=p.short_dte_new,
        short_delta_new=p.short_delta_new,
        bear_short_delta=p.bear_short_delta,
        roll_up_pct=p.roll_up_pct,
        roll_min_bump=p.roll_min_bump,
        harvest_profit_pct=p.harvest_profit_pct,
        drop_trigger_pct=p.drop_trigger_pct / 30.0,
        crash_defer_pct=p.crash_defer_pct / 30.0,
        crash_defer_days=p.crash_defer_days,
        bear_zone_mult=p.bear_zone_mult,
        bear_pause_mult=p.bear_pause_mult,
        challenged_pct=p.challenged_pct,
        min_leaps_dte_for_short=p.min_leaps_dte_for_short,
        slippage_close=p.slippage_close,
        slippage_open=p.slippage_open,
        gap_rip_trigger_pct=p.gap_rip_trigger_pct,
        gap_rip_proximity=p.gap_rip_proximity,
        flush_harvest_pct=p.flush_harvest_pct,
        flush_harvest_min_profit=p.flush_harvest_min_profit,
        reentry_cooldown_days=p.reentry_cooldown_days,
        min_roll_gap_days=p.min_roll_gap_days,
        leaps_roll_dte=p.leaps_roll_dte,
        leaps_deep_itm_threshold=p.leaps_deep_itm_threshold,
        leaps_extreme_itm_threshold=p.leaps_extreme_itm_threshold,
        force_close_dte=p.force_close_dte,
    )


def run_daily_path(
    pair: PmccPair,
    path: DailyPlayPath,
    policy: PlayPolicy | None = None,
    *,
    r: float = 0.04,
) -> pd.DataFrame:
    pol = daily_policy(policy)
    df = run_path(pair, daily_to_play_path(path), pol, r=r)
    if not df.empty:
        df = df.rename(columns={"month": "step"})
        df["day"] = df["step"]
    return df


def run_all_daily_paths(
    pair: PmccPair,
    paths: tuple[DailyPlayPath, ...] | None = None,
    policy: PlayPolicy | None = None,
    *,
    r: float = 0.04,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    paths = paths or build_daily_paths(pair.leaps_dte)
    frames = [run_daily_path(pair, p, policy, r=r) for p in paths]
    detail = pd.concat(frames, ignore_index=True)
    summary = (
        detail.groupby("path")
        .agg(
            final_pnl=("net_pnl", "last"),
            min_pnl=("net_pnl", "min"),
            max_pnl=("net_pnl", "max"),
            days=("day", "max"),
            roll_tax=("roll_tax", "last"),
            roll_count=("roll_count", "last"),
        )
        .reset_index()
    )
    return detail, summary.sort_values("final_pnl")


def pnl_return_pct(pnl: float, capital: float) -> float:
    """P/L as % return on capital (LEAPS debit for PMCC ranking)."""
    return float(pnl) / max(float(capital), 1.0) * 100.0


def _weighted_return(rows: list[dict], capital: float) -> float:
    num = 0.0
    den = 0.0
    for row in rows:
        path = row["path"]
        if path in BEAR_PATHS:
            continue
        w = PATH_RETURN_WEIGHTS.get(path, 1.0)
        num += w * pnl_return_pct(row["final_pnl"], capital)
        den += w
    return num / max(den, 1e-9)


def score_daily_policy(
    pair: PmccPair,
    policy: PlayPolicy,
    *,
    r: float = 0.04,
    bear_loss_cap: float = -3200.0,
) -> dict:
    _, summary = run_all_daily_paths(pair, policy=policy, r=r)
    rows = summary.to_dict("records")
    capital = pair.leaps_debit

    def roll_burden_pct(row: dict) -> float:
        return float(row.get("roll_tax", 0.0)) / max(capital, 1.0) * 100.0

    bear_rows = [x for x in rows if x["path"] in BEAR_PATHS]
    roll_rows = [x for x in rows if x["path"] in ROLL_BURDEN_PATHS]
    whipsaw_rows = [
        x for x in rows
        if x["path"] in {
            "gap_rip_flush", "gap_whipsaw_double", "tsla_range_chop", "post_earnings_whipsaw",
        }
    ]
    bull_rows = [
        x for x in rows
        if x["path"] in {"steady_bull", "rip_plateau", "v_recovery", "moonshot"}
    ]

    path_return_score = _weighted_return(rows, capital)
    roll_tax_burden = (
        sum(roll_burden_pct(x) for x in roll_rows) / max(len(roll_rows), 1)
    )
    roll_count_avg = (
        sum(float(x.get("roll_count", 0)) for x in roll_rows) / max(len(roll_rows), 1)
    )
    roll_eff_score = max(0.0, 100.0 - roll_tax_burden * ROLL_EFF_SCALE)
    bear_worst_pct = min(
        (pnl_return_pct(x["final_pnl"], capital) for x in bear_rows),
        default=0.0,
    )
    bear_pen = min(0.0, bear_worst_pct - pnl_return_pct(bear_loss_cap, capital))

    bull_avg = (
        sum(pnl_return_pct(x["final_pnl"], capital) for x in bull_rows) / max(len(bull_rows), 1)
    )
    whipsaw_avg = (
        sum(pnl_return_pct(x["final_pnl"], capital) for x in whipsaw_rows) / max(len(whipsaw_rows), 1)
    )

    score = (
        PATH_RETURN_WEIGHT * path_return_score
        + ROLL_EFF_WEIGHT * roll_eff_score
        + BEAR_BLEND_WEIGHT * bear_pen
    )

    for row in rows:
        row["final_pnl_pct"] = pnl_return_pct(row["final_pnl"], capital)
        row["roll_tax_pct"] = roll_burden_pct(row)
    return {
        "score": score,
        "path_return_score": path_return_score,
        "roll_tax_burden": roll_tax_burden,
        "roll_eff_score": roll_eff_score,
        "roll_count_avg": roll_count_avg,
        "bull_avg": bull_avg,
        "whipsaw_avg": whipsaw_avg,
        "bear_worst": bear_worst_pct,
        "by_path": rows,
    }


def compare_pairs_daily(
    pairs: list[PmccPair],
    policy: PlayPolicy,
    *,
    r: float = 0.04,
) -> pd.DataFrame:
    rows = []
    for pair in pairs:
        s = score_daily_policy(pair, policy, r=r)
        rows.append({
            "leaps": pair.leaps_strike,
            "short": pair.short_strike,
            "short_dte": pair.short_dte,
            "net_debit": pair.net_debit,
            "score": s["score"],
            "path_return_score": s["path_return_score"],
            "roll_tax_burden": s["roll_tax_burden"],
            "bull_avg": s["bull_avg"],
            "whipsaw_avg": s["whipsaw_avg"],
            "bear_worst": s["bear_worst"],
        })
    return pd.DataFrame(rows).sort_values("score", ascending=False)


def format_daily_log(df: pd.DataFrame, path_name: str, *, max_rows: int = 40) -> str:
    sub = df[df["path"] == path_name].copy()
    if sub.empty:
        return f"(no data for {path_name})"
    action_mask = sub["action"].str.contains(
        "CHALLENGED|GAP RIP|ROLL|CRASH|LEAPS EXPIRE|DROP|SELL new",
        case=False,
        regex=True,
    )
    keep = sub[action_mask | (sub["day"] % 30 == 0) | (sub["day"] == sub["day"].max())]
    keep = keep.drop_duplicates(subset=["day"]).head(max_rows)
    view = keep[["day", "spot", "spot_chg_pct", "leaps_dte", "short_strike", "short_dte", "net_pnl", "action"]]
    view = view.copy()
    view["spot"] = view["spot"].map(lambda x: f"${x:,.0f}")
    view["spot_chg_pct"] = view["spot_chg_pct"].map(lambda x: f"{x*100:+.1f}%")
    view["net_pnl"] = view["net_pnl"].map(lambda x: f"${x:+,.0f}")
    return view.to_string(index=False)
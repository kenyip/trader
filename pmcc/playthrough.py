from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

import pricing
from pmcc.paths import CANONICAL_PATHS, PlayPath
from pmcc.scenarios import PmccPair


@dataclass
class PlayPolicy:
    step_days: int = 30
    short_dte_new: int = 60
    short_delta_new: float = 0.30
    bear_short_delta: float = 0.18
    roll_up_pct: float = 0.08
    roll_min_bump: float = 35.0
    harvest_profit_pct: float = 0.50
    drop_trigger_pct: float = -0.08
    crash_defer_pct: float = -0.12
    crash_defer_days: int = 45
    bear_zone_mult: float = 0.90
    bear_pause_mult: float = 0.75
    challenged_pct: float = 0.98
    min_leaps_dte_for_short: int = 45
    slippage_close: float = 1.01
    slippage_open: float = 0.97
    gap_rip_trigger_pct: float = 0.08
    gap_rip_proximity: float = 0.92
    flush_harvest_pct: float = -0.04
    flush_harvest_min_profit: float = 0.35
    reentry_cooldown_days: int = 14
    min_roll_gap_days: int = 10
    leaps_roll_dte: int = 365
    leaps_deep_itm_threshold: float = 1.25
    leaps_extreme_itm_threshold: float = 1.35
    force_close_dte: int = 14


@dataclass
class ShortLeg:
    strike: float
    dte: int
    iv: float
    open_credit: float


@dataclass
class PlayState:
    day: int = 0
    leaps_dte: int = 0
    short: ShortLeg | None = None
    short_credits: float = 0.0
    short_close_costs: float = 0.0
    roll_tax: float = 0.0
    roll_count: int = 0
    defer_short_days: int = 0
    reentry_cooldown_days: int = 0
    last_roll_day: int = 0
    naked_leaps: bool = False
    leaps_rolled: bool = False
    log: list[str] = field(default_factory=list)


def _px(S: float, K: float, dte: int, iv: float, r: float) -> float:
    if dte <= 0:
        return max(S - K, 0.0)
    return max(pricing.price(S, K, dte / 365.0, iv, "call", r=r), 0.0)


def _strike_for_delta(S: float, dte: int, iv: float, delta: float, r: float) -> float:
    try:
        k = pricing.strike_from_delta(S, dte / 365.0, iv, delta, "call", r=r)
        return pricing.round_strike(max(k, S * 1.02), 5.0)
    except ValueError:
        return pricing.round_strike(S * 1.12, 5.0)


def _open_short(
    spot: float,
    leaps_strike: float,
    iv: float,
    policy: PlayPolicy,
    r: float,
    *,
    spot_entry: float,
) -> ShortLeg:
    delta_tgt = policy.short_delta_new
    if spot < spot_entry * policy.bear_zone_mult:
        delta_tgt = policy.bear_short_delta
    k = _strike_for_delta(spot, policy.short_dte_new, iv, delta_tgt, r)
    k = max(k, leaps_strike + 5, pricing.round_strike(spot * 1.05, 5.0))
    credit = _px(spot, k, policy.short_dte_new, iv, r) * policy.slippage_open * 100.0
    return ShortLeg(strike=k, dte=policy.short_dte_new, iv=iv, open_credit=credit)


def _roll_strike(spot: float, old_k: float, leaps_k: float, policy: PlayPolicy) -> float:
    return pricing.round_strike(
        max(spot * (1 + policy.roll_up_pct), old_k + policy.roll_min_bump, leaps_k + 10),
        5.0,
    )


def _settle_short(state: PlayState, spot: float, r: float) -> str:
    assert state.short is not None
    sh = state.short
    if spot >= sh.strike:
        cost = (spot - sh.strike) * 100.0
        state.short_close_costs += cost
        action = f"short expired ITM ${sh.strike:.0f} — pay ${cost:,.0f} intrinsic"
    else:
        action = f"short expired OTM ${sh.strike:.0f} — keep ${sh.open_credit:,.0f}"
    state.short_credits += sh.open_credit
    state.short = None
    return action


def _close_short(
    state: PlayState,
    spot: float,
    policy: PlayPolicy,
    r: float,
    reason: str,
) -> str:
    assert state.short is not None
    sh = state.short
    cost = _px(spot, sh.strike, sh.dte, sh.iv, r) * policy.slippage_close * 100.0
    state.short_close_costs += cost
    state.short_credits += sh.open_credit
    profit = sh.open_credit - cost
    if "ROLL" in reason.upper():
        state.roll_tax += max(0.0, cost - sh.open_credit)
        state.roll_count += 1
    state.short = None
    return f"{reason}: close ${sh.strike:.0f} ({sh.dte}d) — credit ${sh.open_credit:,.0f} pay ${cost:,.0f} ({profit:+,.0f})"


def run_path(
    pair: PmccPair,
    path: PlayPath,
    policy: PlayPolicy | None = None,
    *,
    r: float = 0.04,
) -> pd.DataFrame:
    policy = policy or PlayPolicy()
    state = PlayState(
        leaps_dte=pair.leaps_dte,
        short=ShortLeg(
            strike=pair.short_strike,
            dte=pair.short_dte,
            iv=pair.short_iv,
            open_credit=pair.short_credit,
        ),
    )
    rows: list[dict] = []
    prev_spot = pair.spot_entry
    base_iv = pair.leaps_iv

    for i, pt in enumerate(path.months):
        if state.leaps_dte <= 0:
            break
        advance = min(policy.step_days, state.leaps_dte)
        state.day += advance
        state.leaps_dte -= advance
        if state.short is not None:
            state.short.dte = max(state.short.dte - advance, 0)

        spot = pair.spot_entry * pt.spot_mult
        iv = base_iv * pt.iv_mult
        spot_chg = (spot - prev_spot) / prev_spot if prev_spot else 0.0
        action_parts: list[str] = []

        if state.defer_short_days > 0:
            state.defer_short_days = max(state.defer_short_days - advance, 0)
        if state.reentry_cooldown_days > 0:
            state.reentry_cooldown_days = max(state.reentry_cooldown_days - advance, 0)

        roll_allowed = (state.day - state.last_roll_day) >= policy.min_roll_gap_days

        # --- short leg management (order matters) ---
        if state.short is not None:
            close_px = _px(spot, state.short.strike, max(state.short.dte, 0), state.short.iv, r)
            short_profit = state.short.open_credit - close_px * policy.slippage_close * 100.0
            profit_frac = short_profit / state.short.open_credit if state.short.open_credit else 0.0

            if state.short.dte <= 0:
                action_parts.append(_settle_short(state, spot, r))
            elif (
                spot_chg <= policy.flush_harvest_pct
                and profit_frac >= policy.flush_harvest_min_profit
            ):
                action_parts.append(_close_short(state, spot, policy, r, "FLUSH harvest short"))
                state.reentry_cooldown_days = policy.reentry_cooldown_days
                action_parts.append(f"COOLDOWN defer new short {policy.reentry_cooldown_days}d after flush")
            elif (
                roll_allowed
                and spot_chg >= policy.gap_rip_trigger_pct
                and spot < state.short.strike
                and spot >= state.short.strike * policy.gap_rip_proximity
            ):
                old_k = state.short.strike
                action_parts.append(_close_short(state, spot, policy, r, "GAP RIP roll"))
                roll_k = _roll_strike(spot, old_k, pair.leaps_strike, policy)
                roll_iv = iv
                if state.leaps_dte >= policy.min_leaps_dte_for_short:
                    cr = _px(spot, roll_k, policy.short_dte_new, roll_iv, r) * policy.slippage_open * 100.0
                    state.short = ShortLeg(roll_k, policy.short_dte_new, roll_iv, cr)
                    state.last_roll_day = state.day
                    action_parts.append(
                        f"ROLL sell ${roll_k:.0f} {policy.short_dte_new}d credit ${cr:,.0f}",
                    )
            elif roll_allowed and spot >= state.short.strike * policy.challenged_pct:
                old_k = state.short.strike
                action_parts.append(_close_short(state, spot, policy, r, "CHALLENGED roll"))
                roll_k = _roll_strike(spot, old_k, pair.leaps_strike, policy)
                roll_iv = iv
                if state.leaps_dte >= policy.min_leaps_dte_for_short:
                    cr = _px(spot, roll_k, policy.short_dte_new, roll_iv, r) * policy.slippage_open * 100.0
                    state.short = ShortLeg(roll_k, policy.short_dte_new, roll_iv, cr)
                    state.last_roll_day = state.day
                    action_parts.append(
                        f"ROLL sell ${roll_k:.0f} {policy.short_dte_new}d credit ${cr:,.0f}",
                    )
            elif spot_chg <= policy.drop_trigger_pct and profit_frac >= policy.harvest_profit_pct:
                action_parts.append(_close_short(state, spot, policy, r, "DROP harvest short"))
                state.reentry_cooldown_days = policy.reentry_cooldown_days
                if spot_chg <= policy.crash_defer_pct:
                    state.defer_short_days = policy.crash_defer_days
                    action_parts.append(f"CRASH defer new short {policy.crash_defer_days}d — hold LEAPS only")
            elif state.short.dte <= 7 and spot < state.short.strike * 0.95:
                action_parts.append(_settle_short(state, spot, r))

        force_roll_allowed = state.short is not None and roll_allowed and state.short.dte <= policy.force_close_dte
        if force_roll_allowed and spot >= state.short.strike:
            old_k = state.short.strike
            action_parts.append(_close_short(state, spot, policy, r, "FORCE CLOSE (ITM near expiry)"))
            roll_k = _roll_strike(spot, old_k, pair.leaps_strike, policy)
            if state.leaps_dte >= policy.min_leaps_dte_for_short and not state.naked_leaps:
                cr = _px(spot, roll_k, policy.short_dte_new, iv, r) * policy.slippage_open * 100.0
                state.short = ShortLeg(roll_k, policy.short_dte_new, iv, cr)
                state.last_roll_day = state.day
                action_parts.append(f"ROLL sell ${roll_k:.0f} {policy.short_dte_new}d credit ${cr:,.0f}")

        if (
            state.short is None
            and not state.naked_leaps
            and state.defer_short_days <= 0
            and state.reentry_cooldown_days <= 0
            and state.leaps_dte >= policy.min_leaps_dte_for_short
            and spot >= pair.spot_entry * policy.bear_pause_mult
        ):
            sh = _open_short(spot, pair.leaps_strike, iv, policy, r, spot_entry=pair.spot_entry)
            state.short = sh
            action_parts.append(
                f"SELL new short ${sh.strike:.0f} {sh.dte}d credit ${sh.open_credit:,.0f}",
            )

        leaps_mtm = _px(spot, pair.leaps_strike, state.leaps_dte, base_iv * pt.iv_mult, r) * 100.0
        short_mtm_cost = 0.0
        if state.short is not None:
            short_mtm_cost = _px(spot, state.short.strike, state.short.dte, state.short.iv, r) * 100.0

        realized_short = state.short_credits - state.short_close_costs
        open_short_credit = state.short.open_credit if state.short else 0.0
        net_pnl = (
            leaps_mtm - pair.leaps_debit
            + realized_short
            + (open_short_credit - short_mtm_cost if state.short else 0.0)
        )

        if state.leaps_dte <= 0:
            if state.short is not None:
                action_parts.append(_settle_short(state, spot, r))
            leaps_settle = max(spot - pair.leaps_strike, 0.0) * 100.0
            total = (
                leaps_settle + state.short_credits - state.short_close_costs - pair.leaps_debit
            )
            action_parts.append(
                f"LEAPS EXPIRE — intrinsic ${leaps_settle:,.0f} | TOTAL P/L ${total:+,.0f}",
            )
            rows.append({
                "month": i + 1,
                "day": state.day,
                "path": path.name,
                "spot": spot,
                "spot_chg_pct": spot_chg,
                "iv": iv,
                "leaps_dte": 0,
                "short_strike": None,
                "short_dte": None,
                "action": " | ".join(action_parts),
                "leaps_mtm": leaps_settle,
                "net_pnl": total,
                "realized_short_pnl": state.short_credits - state.short_close_costs,
                "roll_tax": state.roll_tax,
                "roll_count": state.roll_count,
            })
            break

        moneyness = spot / pair.leaps_strike
        if not state.leaps_rolled and state.leaps_dte <= policy.leaps_roll_dte:
            if moneyness >= policy.leaps_extreme_itm_threshold:
                if state.short is not None:
                    action_parts.append(
                        _close_short(state, spot, policy, r, "EXTREME ITM — close short, LEAPS naked")
                    )
                state.naked_leaps = True
                state.leaps_rolled = True
                action_parts.append(
                    f"EXTREME ITM (spot/strike={moneyness:.2f}) — stop selling shorts, "
                    f"LEAPS naked for upside"
                )
            elif moneyness >= policy.leaps_deep_itm_threshold:
                state.leaps_rolled = True
                action_parts.append(
                    f"DEEP ITM (spot/strike={moneyness:.2f}) — hold LEAPS, keep selling shorts"
                )
            else:
                if state.short is not None:
                    action_parts.append(_settle_short(state, spot, r))
                leaps_mark = _px(spot, pair.leaps_strike, state.leaps_dte, base_iv * pt.iv_mult, r) * 100.0
                total = (
                    leaps_mark + state.short_credits - state.short_close_costs - pair.leaps_debit
                )
                action_parts.append(
                    f"LEAPS ROLL at {state.leaps_dte}d — mark ${leaps_mark:,.0f} | "
                    f"TOTAL P/L ${total:+,.0f}"
                )
                rows.append({
                    "month": i + 1,
                    "day": state.day,
                    "path": path.name,
                    "spot": spot,
                    "spot_chg_pct": spot_chg,
                    "iv": iv,
                    "leaps_dte": state.leaps_dte,
                    "short_strike": None,
                    "short_dte": None,
                    "action": " | ".join(action_parts),
                    "leaps_mtm": leaps_mark,
                    "net_pnl": total,
                    "realized_short_pnl": state.short_credits - state.short_close_costs,
                    "roll_tax": state.roll_tax,
                    "roll_count": state.roll_count,
                })
                break

        rows.append({
            "month": i + 1,
            "day": state.day,
            "path": path.name,
            "spot": spot,
            "spot_chg_pct": spot_chg,
            "iv": iv,
            "leaps_dte": state.leaps_dte,
            "short_strike": state.short.strike if state.short else None,
            "short_dte": state.short.dte if state.short else None,
            "action": " | ".join(action_parts) if action_parts else "hold",
            "leaps_mtm": leaps_mtm,
            "net_pnl": net_pnl,
            "realized_short_pnl": realized_short,
            "roll_tax": state.roll_tax,
            "roll_count": state.roll_count,
        })
        prev_spot = spot

    return pd.DataFrame(rows)


def run_all_paths(
    pair: PmccPair,
    paths: tuple[PlayPath, ...] = CANONICAL_PATHS,
    policy: PlayPolicy | None = None,
    *,
    r: float = 0.04,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = [run_path(pair, p, policy, r=r) for p in paths]
    detail = pd.concat(frames, ignore_index=True)
    summary = (
        detail.groupby("path")
        .agg(
            final_pnl=("net_pnl", "last"),
            min_pnl=("net_pnl", "min"),
            max_pnl=("net_pnl", "max"),
            months=("month", "max"),
        )
        .reset_index()
    )
    return detail, summary.sort_values("final_pnl")


_WHIPSAW_TUNED = dict(
    flush_harvest_pct=-0.03,
    flush_harvest_min_profit=0.50,
    reentry_cooldown_days=21,
    min_roll_gap_days=18,
    gap_rip_proximity=0.90,
)

POLICY_BY_PRESET: dict[str, PlayPolicy] = {
    "income": PlayPolicy(short_delta_new=0.35, short_dte_new=90, roll_up_pct=0.06, **_WHIPSAW_TUNED),
    "balanced": PlayPolicy(
        short_delta_new=0.32,
        short_dte_new=75,
        roll_up_pct=0.10,
        harvest_profit_pct=0.60,
        challenged_pct=1.00,
        crash_defer_days=30,
        **_WHIPSAW_TUNED,
    ),
    "managed": PlayPolicy(
        short_delta_new=0.30,
        short_dte_new=60,
        roll_up_pct=0.10,
        roll_min_bump=45.0,
        challenged_pct=1.00,
        harvest_profit_pct=0.50,
        gap_rip_trigger_pct=0.10,
        gap_rip_proximity=0.85,
        flush_harvest_pct=-0.03,
        flush_harvest_min_profit=0.50,
        reentry_cooldown_days=21,
        min_roll_gap_days=18,
        leaps_roll_dte=365,
        leaps_deep_itm_threshold=1.25,
        leaps_extreme_itm_threshold=1.35,
        force_close_dte=14,
    ),
    "bullish": PlayPolicy(
        short_delta_new=0.22,
        short_dte_new=90,
        roll_up_pct=0.10,
        roll_min_bump=45.0,
        challenged_pct=1.00,
        **_WHIPSAW_TUNED,
    ),
}


def format_monthly_log(df: pd.DataFrame, path_name: str) -> str:
    sub = df[df["path"] == path_name].copy()
    view = sub[["month", "day", "spot", "leaps_dte", "short_strike", "short_dte", "net_pnl", "action"]]
    view["spot"] = view["spot"].map(lambda x: f"${x:,.0f}")
    view["net_pnl"] = view["net_pnl"].map(lambda x: f"${x:+,.0f}")
    return view.to_string(index=False)
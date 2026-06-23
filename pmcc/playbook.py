from __future__ import annotations

from dataclasses import dataclass

import pricing
from pmcc.playthrough import PlayPolicy
from pmcc.scenarios import PmccPair


@dataclass
class Trigger:
    phase: str
    condition: str
    action: str
    priority: int


def _px(S: float, K: float, dte: int, iv: float, r: float) -> float:
    if dte <= 0:
        return max(S - K, 0.0)
    return max(pricing.price(S, K, dte / 365.0, iv, "call", r=r), 0.0)


def _roll_target(spot: float, short_k: float, leaps_k: float, policy: PlayPolicy) -> float:
    return pricing.round_strike(
        max(spot * (1 + policy.roll_up_pct), short_k + policy.roll_min_bump, leaps_k + 10),
        5.0,
    )


def generate_triggers(
    pair: PmccPair,
    policy: PlayPolicy,
    *,
    r: float = 0.04,
) -> list[Trigger]:
    s0 = pair.spot_entry
    sh = pair.short_strike
    leaps = pair.leaps_strike
    iv = pair.short_iv
    dte = pair.short_dte
    credit = pair.short_credit / 100.0

    spots_down = [
        (0.75, "deep crash"),
        (0.85, "bear zone"),
        (0.88, "reentry floor"),
        (0.92, "mild dip"),
    ]
    spots_up = [
        (1.00, "unchanged"),
        (sh / s0, "short strike"),
        (sh / s0 * 1.05, "through short"),
        (1.20, "strong rip"),
        (1.35, "bull target"),
    ]

    triggers: list[Trigger] = []

    triggers.append(Trigger(
        "DAY 0 — OPEN",
        f"Buy LEAPS ${leaps:.0f} ({pair.leaps_dte}d) @ ${pair.leaps_debit:,.0f} | "
        f"Sell short ${sh:.0f} ({dte}d) @ ${credit:.2f} (${pair.short_credit:,.0f})",
        f"Net debit ~${pair.net_debit:,.0f}. Log short credit ${credit:.2f}/sh.",
        0,
    ))

    # --- daily / any day checks ---
    harvest_px = credit * (1 - policy.harvest_profit_pct)
    triggers.append(Trigger(
        "DAILY — SHORT PREMIUM",
        f"Short mark ≤ ${harvest_px:.2f}/sh ({policy.harvest_profit_pct:.0%}+ profit on ${credit:.2f} credit)",
        "BUY BACK short. Bank profit. Keep LEAPS. Schedule reentry (see REENTRY).",
        1,
    ))

    triggers.append(Trigger(
        "DAILY — SHORT PREMIUM (defensive)",
        f"Short mark ≤ ${credit * 0.25:.2f}/sh (≤25% of credit left / 75% profit)",
        "BUY BACK short early — theta won. Sell next only if reentry rules pass.",
        2,
    ))

    triggers.append(Trigger(
        "DAILY — CHALLENGED",
        f"Spot ≥ ${sh * policy.challenged_pct:.0f} (~short strike ${sh:.0f})",
        f"Same day: BUY BACK short. ROLL UP/OUT → sell ~${_roll_target(sh, sh, leaps, policy):.0f} "
        f"({policy.short_dte_new}d, ~{policy.short_delta_new:.2f}Δ). Never let assign.",
        1,
    ))

    gap_spot = s0 * (1 + policy.gap_rip_trigger_pct)
    gap_roll = _roll_target(gap_spot, sh, leaps, policy)
    gap_cr = _px(gap_spot, gap_roll, policy.short_dte_new, iv, r) * policy.slippage_open
    flush_px = credit * (1 - policy.flush_harvest_min_profit)
    triggers.append(Trigger(
        "DAILY — FLUSH GIVEBACK",
        f"Spot drops ≥{abs(policy.flush_harvest_pct):.0%} in a day AND short mark ≤ ${flush_px:.2f}/sh "
        f"(≥{policy.flush_harvest_min_profit:.0%} profit)",
        f"BUY BACK short — bank profit on the rip's giveback. Cooldown {policy.reentry_cooldown_days}d "
        f"before re-selling (avoids whipsaw roll tax).",
        1,
    ))

    triggers.append(Trigger(
        "DAILY — GAP RIP",
        f"Spot gaps ≥{policy.gap_rip_trigger_pct:.0%} vs prior close AND within 8% of short ${sh:.0f} "
        f"(spot ~${gap_spot:.0f})",
        f"Proactive roll BEFORE next session: buy back short, sell ~${gap_roll:.0f} "
        f"({policy.short_dte_new}d, est ~${gap_cr * 100:,.0f}/contract). TSLA can +10% in a day.",
        1,
    ))

    for mult, label in spots_down:
        spot = s0 * mult
        if mult <= policy.bear_pause_mult:
            triggers.append(Trigger(
                f"SPOT DOWN — {label}",
                f"Spot ≤ ${spot:.0f} ({(mult-1)*100:.0f}% vs entry ${s0:.0f})",
                f"NO new shorts. LEAPS only. Optional: buy back short if mark ≤ ${harvest_px:.2f}. "
                f"Loss-cap mode — don't add risk below LEAPS strike.",
                2,
            ))
        elif mult <= policy.bear_zone_mult:
            est_k = pricing.round_strike(spot * 1.12, 5.0)
            est_cr = _px(spot, est_k, policy.short_dte_new, iv * 1.1, r) * policy.slippage_open
            triggers.append(Trigger(
                f"SPOT DOWN — {label}",
                f"Spot ≤ ${spot:.0f}",
                f"If re-selling short: use WIDE strike ~${est_k:.0f} ({policy.bear_short_delta:.2f}Δ), "
                f"expect ~${est_cr:.2f}/sh. Prefer harvest + wait.",
                3,
            ))

    for mult, label in spots_up:
        spot = s0 * mult
        if spot <= sh:
            continue
        roll_k = _roll_target(spot, sh, leaps, policy)
        roll_cr = _px(spot, roll_k, policy.short_dte_new, iv, r) * policy.slippage_open
        triggers.append(Trigger(
            f"SPOT UP — {label}",
            f"Spot ≥ ${spot:.0f}",
            f"If short threatened or ITM: roll to ~${roll_k:.0f} {policy.short_dte_new}d "
            f"(est credit ~${roll_cr * 100:,.0f}/contract).",
            2,
        ))

    # --- calendar ---
    for d in (21, 14, 7, 3, 0):
        if d >= dte:
            continue
        triggers.append(Trigger(
            "CALENDAR — SHORT DTE",
            f"{d} DTE left on short (${sh:.0f})",
            "OTM: let expire worthless OR buy back if mark < $0.10. "
            "ITM: buy back today, roll up/out — do not hold into assignment.",
            3 if d > 7 else 1,
        ))

    triggers.append(Trigger(
        "CRASH — MONTHLY DROP",
        f"Spot drops ≥{abs(policy.crash_defer_pct)*100:.0f}% within ~30d",
        f"Harvest short. Defer new short {policy.crash_defer_days}d. LEAPS only.",
        1,
    ))

    # --- reentry ---
    re_spot = s0 * 0.88
    re_k = pricing.round_strike(re_spot * 1.10, 5.0)
    re_cr = _px(re_spot, re_k, policy.short_dte_new, iv, r) * policy.slippage_open
    triggers.append(Trigger(
        "REENTRY — after harvest/defer",
        f"Spot ≥ ${re_spot:.0f} (88% entry) AND IV not spiking (+15% vs entry)",
        f"Sell new short ~${re_k:.0f} {policy.short_dte_new}d (~{policy.short_delta_new:.2f}Δ), "
        f"target credit ~${re_cr * 100:,.0f}. If spot < ${s0 * policy.bear_pause_mult:.0f}, wait.",
        2,
    ))

    triggers.append(Trigger(
        "LEAPS — late life",
        f"LEAPS DTE ≤ {policy.min_leaps_dte_for_short}d",
        "Stop selling shorts. Decide: hold LEAPS to expiry or take profit if spot ≫ strike.",
        3,
    ))

    deep_itm_spot = leaps * policy.leaps_deep_itm_threshold
    extreme_itm_spot = leaps * policy.leaps_extreme_itm_threshold
    roll_spot = leaps  # at 1.0x, roll
    triggers.append(Trigger(
        "LEAPS — CONDITIONAL ROLL",
        f"LEAPS DTE ≤ {policy.leaps_roll_dte}d ({policy.leaps_roll_dte}d remaining)",
        f"If spot < ${deep_itm_spot:.0f} ({policy.leaps_deep_itm_threshold:.2f}x strike): "
        f"SELL LEAPS, buy new 727d at 0.70Δ. Avoids theta cliff.\n"
        f"  If spot ${deep_itm_spot:.0f}-${extreme_itm_spot:.0f} ({policy.leaps_deep_itm_threshold:.2f}-"
        f"{policy.leaps_extreme_itm_threshold:.2f}x): HOLD — deep ITM, keep selling shorts.\n"
        f"  If spot > ${extreme_itm_spot:.0f} ({policy.leaps_extreme_itm_threshold:.2f}x): "
        f"CLOSE SHORT, LEAPS NAKED. Position is capped, let LEAPS run free.\n"
        f"  NEVER reset LEAPS to higher strike — original strike is your anchor.",
        1,
    ))

    triggers.append(Trigger(
        "SHORT — FORCE CLOSE",
        f"Short DTE ≤ {policy.force_close_dte}d AND spot ≥ short strike ${sh:.0f}",
        f"FORCE CLOSE short — buy back immediately, roll up-and-out to ~"
        f"${_roll_target(s0 * 1.10, sh, leaps, policy):.0f} {policy.short_dte_new}d. "
        f"NEVER let short expire ITM — assignment forfeits LEAPS time value.",
        1,
    ))

    triggers.append(Trigger(
        "LEAPS — expiry",
        f"LEAPS DTE = 0",
        f"Settle intrinsic vs ${leaps:.0f}. Close any remaining short first.",
        0,
    ))

    phase_order = {
        "DAY 0 — OPEN": 0,
        "DAILY — SHORT PREMIUM": 1,
        "DAILY — SHORT PREMIUM (defensive)": 2,
        "DAILY — CHALLENGED": 3,
        "DAILY — FLUSH GIVEBACK": 4,
        "DAILY — GAP RIP": 5,
        "SPOT DOWN — deep crash": 10,
        "SPOT DOWN — bear zone": 11,
        "SPOT DOWN — reentry floor": 12,
        "SPOT DOWN — mild dip": 13,
        "SPOT UP — short strike": 20,
        "SPOT UP — through short": 21,
        "SPOT UP — strong rip": 22,
        "SPOT UP — bull target": 23,
        "CALENDAR — SHORT DTE": 30,
        "SHORT — FORCE CLOSE": 31,
        "CRASH — MONTHLY DROP": 40,
        "REENTRY — after harvest/defer": 50,
        "LEAPS — late life": 60,
        "LEAPS — CONDITIONAL ROLL": 61,
        "LEAPS — expiry": 70,
    }
    return sorted(triggers, key=lambda t: (phase_order.get(t.phase, 99), t.priority))


def format_playbook(triggers: list[Trigger]) -> str:
    lines = [
        "# PMCC daily playbook",
        "",
        "Check **every session** (theta decays daily). Priority: CHALLENGED > PREMIUM harvest > SPOT rules.",
        "",
    ]
    phase = None
    for t in triggers:
        if t.phase != phase:
            phase = t.phase
            lines.append(f"\n## {phase}\n")
        lines.append(f"**IF** {t.condition}")
        lines.append(f"  → {t.action}\n")
    return "\n".join(lines)


def evaluate_live_status(
    pair: PmccPair,
    policy: PlayPolicy,
    spot_now: float,
    *,
    r: float = 0.04,
) -> list[dict]:
    """Which playbook rules are active at spot_now (vs entry pair)."""
    s0 = pair.spot_entry
    sh = pair.short_strike
    leaps = pair.leaps_strike
    iv = pair.short_iv
    dte = pair.short_dte
    credit = pair.short_credit / 100.0
    short_mark = _px(spot_now, sh, dte, iv, r)

    checks: list[dict] = []

    if spot_now >= sh * policy.challenged_pct:
        roll_k = _roll_target(spot_now, sh, leaps, policy)
        checks.append({
            "level": "alert",
            "rule": "CHALLENGED",
            "detail": f"Spot ${spot_now:,.0f} ≥ ${sh * policy.challenged_pct:.0f} — roll to ~${roll_k:.0f}",
        })
    elif spot_now >= sh * 0.92 and spot_now < sh:
        checks.append({
            "level": "warn",
            "rule": "NEAR SHORT",
            "detail": f"Spot ${spot_now:,.0f} within 8% of short ${sh:.0f} — watch for gap rip",
        })

    harvest_px = credit * (1 - policy.harvest_profit_pct)
    if short_mark <= harvest_px:
        checks.append({
            "level": "ok",
            "rule": "HARVEST",
            "detail": f"Short mark ${short_mark:.2f}/sh ≤ ${harvest_px:.2f} — take profit",
        })

    if spot_now <= s0 * (1 + policy.flush_harvest_pct) and short_mark <= credit * (1 - policy.flush_harvest_min_profit):
        checks.append({
            "level": "ok",
            "rule": "FLUSH GIVEBACK",
            "detail": f"Spot flushed, short mark ${short_mark:.2f}/sh — harvest and cooldown {policy.reentry_cooldown_days}d",
        })

    if spot_now <= s0 * policy.bear_pause_mult:
        checks.append({
            "level": "warn",
            "rule": "DEEP CRASH",
            "detail": f"Spot ${spot_now:,.0f} ≤ ${s0 * policy.bear_pause_mult:.0f} — LEAPS only, no new shorts",
        })
    elif spot_now <= s0 * policy.bear_zone_mult:
        checks.append({
            "level": "info",
            "rule": "BEAR ZONE",
            "detail": f"Spot ${spot_now:,.0f} — use wide shorts ({policy.bear_short_delta:.2f}Δ) if re-selling",
        })

    moneyness = spot_now / leaps
    if moneyness >= policy.leaps_extreme_itm_threshold:
        roll_k = _roll_target(spot_now, sh, leaps, policy)
        checks.append({
            "level": "alert",
            "rule": "EXTREME ITM — LEAPS NAKED",
            "detail": f"Spot ${spot_now:,.0f} > {policy.leaps_extreme_itm_threshold:.2f}x LEAPS ${leaps:.0f} — "
                      f"position capped. Close short, let LEAPS run naked. Never reset to higher strike.",
        })
    elif moneyness >= policy.leaps_deep_itm_threshold:
        checks.append({
            "level": "info",
            "rule": "DEEP ITM — HOLD LEAPS",
            "detail": f"Spot ${spot_now:,.0f} > {policy.leaps_deep_itm_threshold:.2f}x LEAPS ${leaps:.0f} — "
                      f"LEAPS deep ITM. Keep selling shorts, capture upside.",
        })

    if not checks:
        checks.append({
            "level": "ok",
            "rule": "HOLD",
            "detail": f"Spot ${spot_now:,.0f} — no trigger fired; short mark ${short_mark:.2f}/sh",
        })
    return checks


def format_playbook_table(triggers: list[Trigger]) -> str:
    import pandas as pd
    df = pd.DataFrame([{"phase": t.phase, "if": t.condition, "then": t.action} for t in triggers])
    return df.to_string(index=False)
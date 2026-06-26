"""Pure helpers for the PMCC desk UI — no Streamlit, no duplicated pricing."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from data import _TSLA_EARNINGS_DATES
from pmcc.income import reentry_candidates
from pmcc.scenarios import PmccPair


def _parse_date(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def _today(value: date | None = None) -> date:
    return value or datetime.now(timezone.utc).date()


def next_earnings_date(*, today: date | None = None, staged_earnings: str | None = None) -> date | None:
    """Next TSLA earnings after today; staged date wins when still in the future."""
    today = _today(today)
    if staged_earnings:
        staged = _parse_date(staged_earnings)
        if staged >= today:
            return staged
    known = sorted(_parse_date(d) for d in _TSLA_EARNINGS_DATES)
    for d in known:
        if d >= today:
            return d
    return None


def patience_budget_label(statuses: list[dict]) -> str:
    """Human-readable patience budget from carry or closed-short clock."""
    for s in statuses:
        if s.get("no_open_short"):
            clock = s.get("closed_short_clock") or {}
            if clock:
                good = clock["targets"]["good"]
                wait = good["portfolio_wait_days"]
                mode = clock.get("reload_mode", "")
                return f"{wait:.0f}d good-budget left · {mode}"
            return "no open short — reload when safe"
        carry = s.get("carry")
        if carry:
            wait = carry.get("wait_good_days_after_harvest", 0.0)
            if carry.get("current_short_profit", 0) >= carry.get("harvest_profit", 0):
                return f"{wait:.0f}d good-budget after harvest"
            return f"harvest in progress · {carry.get('current_profit_daily', 0):+.1f}$/d"
    return "—"


def compute_patience_expires(
    *,
    staged_events: dict | None,
    statuses: list[dict],
    today: date | None = None,
) -> dict:
    """Earliest patience deadline across delivery window, premium clock, earnings − 5d."""
    today = _today(today)
    candidates: list[tuple[date, str]] = []

    if staged_events:
        delivery_start = staged_events.get("delivery_window", "").split(" to ")[0][:10]
        if delivery_start:
            try:
                d = _parse_date(delivery_start)
                soft = d - timedelta(days=2)
                if soft >= today:
                    candidates.append((soft, "delivery window soft deadline"))
            except ValueError:
                pass
        earnings = staged_events.get("earnings_date")
        earn = next_earnings_date(today=today, staged_earnings=earnings)
        if earn:
            hard = earn - timedelta(days=5)
            if hard >= today:
                candidates.append((hard, "earnings − 5 calendar days"))

    for s in statuses:
        if s.get("no_open_short"):
            clock = s.get("closed_short_clock") or {}
            good = (clock.get("targets") or {}).get("good") or {}
            until = good.get("portfolio_budget_until")
            if until:
                try:
                    d = _parse_date(until)
                    if d >= today:
                        candidates.append((d, "premium clock portfolio budget"))
                except ValueError:
                    pass
        carry = s.get("carry")
        if carry and carry.get("current_short_profit", 0) >= carry.get("harvest_profit", 0):
            days = carry.get("wait_good_days_after_harvest", 0)
            if days > 0:
                d = today + timedelta(days=round(days))
                candidates.append((d, "post-harvest good wait budget"))

    if not candidates:
        return {"date": None, "label": "—", "explanation": "no deadline computed"}
    best = min(candidates, key=lambda x: x[0])
    return {
        "date": best[0].isoformat(),
        "label": f"Patience expires ~{best[0].isoformat()}",
        "explanation": best[1],
    }


def build_situation(
    *,
    spot: float,
    chain_age_minutes: float | None,
    statuses: list[dict],
    staged: dict | None,
    today: date | None = None,
) -> dict:
    """Situation bar fields from check_pmcc_position + staged plan."""
    today = _today(today)
    primary_action = "—"
    primary_level = "info"
    primary_detail = ""
    if statuses:
        top = min(
            statuses,
            key=lambda s: {"alert": 0, "warn": 1, "ok": 2, "info": 3}.get(s.get("primary_level", "info"), 9),
        )
        primary_action = top.get("primary_action", "—")
        primary_level = top.get("primary_level", "info")
        primary_detail = top.get("primary_detail", "")

    events = (staged or {}).get("events") or {}
    patience = compute_patience_expires(staged_events=events, statuses=statuses, today=today)
    catalyst_parts = []
    if events.get("delivery_window"):
        catalyst_parts.append(f"delivery {events['delivery_window']}")
    if events.get("earnings_date"):
        catalyst_parts.append(f"earnings {events['earnings_date']}")
    elif next_earnings_date(today=today):
        catalyst_parts.append(f"earnings {next_earnings_date(today=today).isoformat()}")

    return {
        "spot": spot,
        "chain_age_minutes": chain_age_minutes,
        "primary_action": primary_action,
        "primary_level": primary_level,
        "primary_detail": primary_detail,
        "patience_budget": patience_budget_label(statuses),
        "catalyst": " · ".join(catalyst_parts) if catalyst_parts else "—",
        "patience_expires": patience,
        "events": events,
    }


def build_position_rows(statuses: list[dict], spot: float) -> list[dict]:
    """Flatten check_pmcc_position results into rich per-leg table rows."""
    rows: list[dict] = []
    for s in statuses:
        p: PmccPair = s["pair"]
        rec = s["record"]
        contracts = s.get("contracts", 1)
        diag = f"{int(p.leaps_strike)}/{int(p.short_strike) if not s.get('no_open_short') else '—'}"

        leaps_m = s["leaps_mark"]
        leaps_mark = leaps_m["price"] * 100
        rows.append({
            "diagonal": diag,
            "leg": "LEAPS",
            "strike_exp_dte": f"${p.leaps_strike:.0f} · {str(p.leaps_exp)[:10]} · {p.leaps_dte}d",
            "entry_cost": f"${p.leaps_debit:,.0f}",
            "mark": f"${leaps_mark:,.0f}",
            "leg_pnl": f"${s['leaps_leg_pnl']:+,.0f}",
            "net_pnl": f"${s['net_pnl']:+,.0f}/ct",
            "delta": f"{leaps_m.get('delta', 0):.3f}",
            "per_day": "—",
            "upside_pct": f"{(p.leaps_strike / spot - 1) * 100:+.1f}%",
            "status": s.get("primary_action", "—"),
            "contracts": contracts,
            "_status_key": s,
        })

        if s.get("no_open_short"):
            realized = float(s.get("realized_short_total", 0.0))
            rows.append({
                "diagonal": diag,
                "leg": "Closed shorts",
                "strike_exp_dte": "realized P/L",
                "entry_cost": "—",
                "mark": "—",
                "leg_pnl": f"${realized:+,.0f}",
                "net_pnl": f"${s['net_pnl_total']:+,.0f} total",
                "delta": "—",
                "per_day": "—",
                "upside_pct": "—",
                "status": "LEAPS ONLY",
                "contracts": contracts,
                "_status_key": s,
            })
            continue

        short_m = s["short_mark"] or {}
        carry = s.get("carry") or {}
        short_mark = short_m.get("price", 0) * 100
        upside = (p.short_strike / spot - 1) * 100
        pace = carry.get("current_profit_daily")
        per_day = f"${pace:+.1f}/d" if pace is not None else "—"
        rows.append({
            "diagonal": diag,
            "leg": "Short",
            "strike_exp_dte": f"${p.short_strike:.0f} · {str(p.short_exp)[:10]} · {p.short_dte}d",
            "entry_cost": f"${p.short_credit:,.0f}",
            "mark": f"${short_mark:,.0f}",
            "leg_pnl": f"${s['short_leg_pnl']:+,.0f}",
            "net_pnl": f"${s['net_pnl']:+,.0f}/ct",
            "delta": f"{short_m.get('delta', 0):.3f}",
            "per_day": per_day,
            "upside_pct": f"{upside:+.1f}%",
            "status": s.get("primary_action", "—"),
            "contracts": contracts,
            "_status_key": s,
        })
    return rows


def _reload_mode(statuses: list[dict], staged: dict | None) -> str:
    for s in statuses:
        clock = s.get("closed_short_clock") or {}
        if clock.get("reload_mode"):
            return str(clock["reload_mode"])
    pos = (staged or {}).get("position") or {}
    if pos.get("open_short_contracts", 0) < pos.get("target_short_contracts", 0):
        return "building stack"
    return "normal"


def _days_to_catalyst(staged: dict | None, *, today: date | None = None) -> int:
    today = _today(today)
    events = (staged or {}).get("events") or {}
    days = []
    if events.get("days_to_delivery_window") is not None:
        days.append(int(events["days_to_delivery_window"]))
    if events.get("days_to_earnings") is not None:
        days.append(int(events["days_to_earnings"]))
    return min(days) if days else 999


def _pick_reentry(
    candidates: list[dict],
    *,
    income_needed: bool,
    days_to_catalyst: int,
) -> dict | None:
    if not candidates:
        return None
    if income_needed or days_to_catalyst < 7:
        floor_income = {"low", "carry", "good", "strong"}
        allowed_risk = {"balanced", "wide", "aggressive"}
    else:
        floor_income = {"carry", "good", "strong"}
        allowed_risk = {"balanced", "wide"}
    preferred = [
        c for c in candidates
        if c.get("income") in floor_income and c.get("risk") in allowed_risk
    ]
    pool = preferred or candidates
    if not income_needed and days_to_catalyst >= 7:
        balanced = [c for c in pool if c.get("risk") in {"balanced", "wide"}]
        if balanced:
            pool = balanced
    return max(pool, key=lambda c: (c.get("daily", 0), -c.get("upside_pct", 0)))


def _format_candidate_row(c: dict, *, pick: bool = False) -> dict:
    credit = c.get("bid_credit") or c.get("credit") or 0
    return {
        "strike": f"${c['strike']:.0f}",
        "exp": str(c.get("expiration", ""))[:10] or f"{c.get('dte', 60)}d",
        "bid": f"${credit:,.0f}",
        "$/day": f"${c.get('daily', 0):.1f}",
        "delta": f"{c.get('delta', 0):.2f}",
        "upside %": f"{c.get('upside_pct', 0):.1f}%",
        "income": c.get("income", "—"),
        "risk": c.get("risk", "—"),
        "pick": "◀" if pick else "",
        "_raw": c,
    }


def select_next_short(
    *,
    spot: float,
    chain: pd.DataFrame | None,
    records: list[dict],
    statuses: list[dict],
    staged: dict | None,
    preset: str = "managed",
    today: date | None = None,
) -> dict:
    """State machine: one hero recommendation + 5-8 candidate rows."""
    today = _today(today)
    income_needed = "income needed" in _reload_mode(statuses, staged).lower()
    days_cat = _days_to_catalyst(staged, today=today)

    pair: PmccPair | None = statuses[0]["pair"] if statuses else None
    if pair is None and records:
        r = records[0]
        if r.get("short_strike") and r.get("short_expiration") and r.get("open_short", True) is not False:
            from pmcc.positions import record_to_pair
            pair = record_to_pair(r, spot)
        else:
            from pmcc.positions import _calendar_dte
            leaps_strike = float(r["leaps_strike"])
            short_exp = (staged or {}).get("short_expiration", "")
            pair = PmccPair(
                spot_entry=float(r.get("spot_at_entry", spot)),
                leaps_strike=leaps_strike,
                leaps_exp=str(r["leaps_expiration"]),
                leaps_dte=_calendar_dte(str(r["leaps_expiration"])),
                leaps_iv=float(r.get("leaps_iv", 0.55)),
                leaps_debit=float(r.get("leaps_debit", 0.0)),
                short_strike=float(r.get("last_short_strike") or max(leaps_strike + 90, spot * 1.25)),
                short_exp=short_exp,
                short_dte=60,
                short_iv=float(r.get("short_iv", 0.45)),
                short_credit=0.0,
                leaps_delta_target=float(r.get("leaps_delta", 0.65)),
                short_delta_target=float(r.get("short_delta", 0.30)),
            )

    exp = (staged or {}).get("short_expiration", "")
    dte = 60
    if staged and staged.get("packages"):
        dte = int(staged["packages"].get("initial", {}).get("dte", 60))

    candidates = []
    if pair is not None:
        iv = pair.short_iv
        candidates = reentry_candidates(spot, pair, dte=dte, iv=iv, chain=chain, expiration=exp or None)

    lo = max((pair.leaps_strike + 5) if pair else spot * 1.05, spot * 1.05)
    hi = spot * 1.35
    candidates = [c for c in candidates if lo <= c["strike"] <= hi]
    candidates = sorted(candidates, key=lambda c: c.get("daily", 0), reverse=True)[:8]

    pos = (staged or {}).get("position") or {}
    building = pos.get("open_short_contracts", 0) < pos.get("target_short_contracts", 0)

    # Priority: challenged roll > harvest > bear pause > building stack > reentry
    for s in statuses:
        if s.get("no_open_short"):
            continue
        action = (s.get("primary_action") or "").upper()
        p = s["pair"]
        carry = s.get("carry") or {}
        if "CHALLENGED" in action or "FORCE CLOSE" in action or "ROLL" in action:
            roll_k = s.get("roll_target", 0)
            hero = (
                f"Roll short ${p.short_strike:.0f} → ~${roll_k:.0f} "
                f"({p.short_dte}d left) — spot ${spot:,.0f} near strike"
            )
            return {
                "source": "roll",
                "hero": hero,
                "candidates": [_format_candidate_row(c, pick=i == 0) for i, c in enumerate(candidates)],
            }
        if carry and carry.get("current_short_profit", 0) >= carry.get("harvest_profit", 0):
            hero = (
                f"Hold / harvest at mark ≤ ${carry['harvest_mark']:,.0f} "
                f"({carry['harvest_profit']:,.0f} profit) — then reload"
            )
            pick = _pick_reentry(candidates, income_needed=income_needed, days_to_catalyst=days_cat)
            if pick:
                hero += (
                    f"; preview reload ${pick['strike']:.0f} "
                    f"~${pick.get('bid_credit', pick['credit']):,.0f} (${pick['daily']:.1f}/d)"
                )
            return {
                "source": "harvest",
                "hero": hero,
                "candidates": [_format_candidate_row(c, pick=c is pick) for c in candidates],
            }
        if "DEEP CRASH" in action or "BEAR" in action:
            hero = f"Widen/pause — {s.get('primary_detail', 'bear zone; no tight shorts')}"
            return {
                "source": "bear",
                "hero": hero,
                "candidates": [_format_candidate_row(c) for c in candidates if c.get("risk") == "wide"],
            }

    if building and staged:
        ns = staged.get("next_step") or {}
        pkg_key = ns.get("preferred_package", "initial")
        pkg = staged.get("packages", {}).get(pkg_key, {})
        hero = ns.get("action", "Build staged short stack")
        if pkg.get("order_limit_text"):
            hero += f" — `{pkg['order_limit_text']}`"
        return {
            "source": "staged",
            "hero": hero,
            "candidates": [_format_candidate_row(c, pick=i == 0) for i, c in enumerate(candidates)],
            "staged_package": pkg,
        }

    pick = _pick_reentry(candidates, income_needed=income_needed, days_to_catalyst=days_cat)
    if pick:
        credit = pick.get("bid_credit", pick.get("credit", 0))
        exp_label = str(pick.get("expiration", exp))[:10]
        if not exp_label:
            exp_label = f"~{pick.get('dte', 60)}d"
        hero = (
            f"Sell ${pick['strike']:.0f} call {exp_label} · "
            f"target ≥ ${credit:,.0f} · ${pick['daily']:.1f}/day · "
            f"+{pick['upside_pct']:.1f}% upside · {pick.get('risk', '')}"
        )
    else:
        hero = "No candidates in safe range — wait for IV pop or widen strikes"
    return {
        "source": "reentry",
        "hero": hero,
        "candidates": [_format_candidate_row(c, pick=c is pick) for c in candidates],
    }
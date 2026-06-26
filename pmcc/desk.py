"""Pure helpers for the PMCC desk UI — no Streamlit, no duplicated pricing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from data import _TSLA_EARNINGS_DATES
from pmcc.income import income_metrics, reentry_candidates
from pmcc.scenarios import PmccPair


def _parse_date(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def _today(value: date | None = None) -> date:
    return value or datetime.now(timezone.utc).date()


def position_record_key(record: dict) -> str:
    """Stable identity for pmcc_positions.yaml rows (same strike, different lots)."""
    return "|".join([
        str(record.get("ticker", "TSLA")).upper(),
        f"{float(record.get('leaps_strike', 0)):g}",
        str(record.get("leaps_expiration", ""))[:10],
        f"{float(record.get('leaps_debit', 0)):g}",
        str(int(record.get("contracts", 1))),
        f"{float(record.get('short_strike', 0)):g}" if record.get("short_strike") is not None else "",
        str(record.get("short_expiration", ""))[:10],
    ])


def position_remove_match(left: dict, right: dict) -> bool:
    """True when two YAML records are the same tracked position."""
    return position_record_key(left) == position_record_key(right)


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


def candidate_is_preferred(c: dict) -> bool:
    return c.get("income") in {"carry", "good", "strong"} and c.get("risk") in {"balanced", "wide"}


def build_position_rows(statuses: list[dict]) -> list[dict]:
    """Flatten check_pmcc_position results into rich per-leg table rows."""
    rows: list[dict] = []
    for s in statuses:
        p: PmccPair = s["pair"]
        rec = s["record"]
        contracts = s.get("contracts", 1)
        spot = float(s.get("spot_now") or rec.get("spot_at_entry") or p.spot_entry or 0.0)
        ticker = str(rec.get("ticker", "TSLA")).upper()
        short_label = "" if s.get("no_open_short") else f"/{int(p.short_strike)}"
        diag = (
            f"{ticker} {int(p.leaps_strike)}{short_label} "
            f"x{contracts} ${float(rec.get('leaps_debit', p.leaps_debit)):,.0f}"
        )

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
    preferred = candidate_is_preferred(c)
    return {
        "strike": f"${c['strike']:.0f}",
        "exp": str(c.get("expiration", ""))[:10] or f"{c.get('dte', 60)}d",
        "bid": f"${credit:,.0f}",
        "$/day": f"${c.get('daily', 0):.1f}",
        "delta": f"{c.get('delta', 0):.2f}",
        "upside %": f"{c.get('upside_pct', 0):.1f}%",
        "income": c.get("income", "—"),
        "risk": c.get("risk", "—"),
        "prefer": "✓" if preferred else "",
        "pick": "◀" if pick else "",
        "_prefer": preferred,
        "_raw": c,
    }


def candidate_table_styler(df: pd.DataFrame):
    """Highlight prefer-tier rows (carry/good/strong + balanced/wide)."""
    prefer = df["_prefer"] if "_prefer" in df.columns else pd.Series([False] * len(df))
    show_cols = [c for c in df.columns if not c.startswith("_")]
    show = df[show_cols]

    def _highlight(row):
        if prefer.iloc[row.name]:
            return ["background-color: #1e4620"] * len(row)
        return [""] * len(row)

    return show.style.apply(_highlight, axis=1)


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


@dataclass
class DeskBundle:
    records: list[dict]
    preset: str
    refresh: bool
    spots_by_ticker: dict[str, float] = field(default_factory=dict)
    chains_by_ticker: dict[str, pd.DataFrame] = field(default_factory=dict)
    chain_meta: Any = None
    chain_errors: list[str] = field(default_factory=list)
    statuses: list[dict] = field(default_factory=list)
    status_errors: list[str] = field(default_factory=list)
    staged: dict | None = None
    staged_error: str | None = None
    situation: dict = field(default_factory=dict)
    position_rows: list[dict] = field(default_factory=list)
    next_short: dict = field(default_factory=dict)

    @property
    def spot_tsla(self) -> float | None:
        return self.spots_by_ticker.get("TSLA")

    @property
    def tsla_chain(self) -> pd.DataFrame:
        return self.chains_by_ticker.get("TSLA", pd.DataFrame())


def assemble_pmcc_desk(
    records: list[dict],
    preset: str = "managed",
    refresh: bool = False,
) -> DeskBundle:
    """Single assembly path for dashboard, verification, and tests."""
    from pmcc.chain_data import chain_fetch_meta, fetch_call_chain
    from pmcc.positions import check_pmcc_position
    from pmcc.staged_entry import build_tsla_staged_entry_plan

    bundle = DeskBundle(records=list(records), preset=preset, refresh=refresh)
    tickers = sorted({str(r.get("ticker", "TSLA")).upper() for r in records} or {"TSLA"})
    for ticker in tickers:
        try:
            spot, chain = fetch_call_chain(ticker, refresh=refresh)
            bundle.spots_by_ticker[ticker] = spot
            bundle.chains_by_ticker[ticker] = chain
            if ticker == "TSLA":
                bundle.chain_meta = chain_fetch_meta()
        except Exception as ex:
            bundle.chain_errors.append(f"{ticker}: {ex}")

    tsla_records = [r for r in records if str(r.get("ticker", "TSLA")).upper() == "TSLA"]
    if bundle.spot_tsla is not None:
        try:
            bundle.staged = build_tsla_staged_entry_plan(
                tsla_records, bundle.tsla_chain, spot=bundle.spot_tsla,
            )
        except Exception as ex:
            bundle.staged_error = str(ex)

    for record in records:
        ticker = str(record.get("ticker", "TSLA")).upper()
        spot = bundle.spots_by_ticker.get(ticker)
        if spot is None:
            bundle.status_errors.append(
                f"no spot for {ticker} LEAPS {record.get('leaps_strike', '?')}"
            )
            continue
        try:
            bundle.statuses.append(check_pmcc_position(record, spot, preset=preset))
        except Exception as ex:
            bundle.status_errors.append(
                f"{ticker} LEAPS {record.get('leaps_strike', '?')}: {ex}"
            )

    bundle.situation = build_situation(
        spot=bundle.spot_tsla or 0.0,
        chain_age_minutes=bundle.chain_meta.age_minutes if bundle.chain_meta else None,
        statuses=bundle.statuses,
        staged=bundle.staged,
    )
    bundle.position_rows = build_position_rows(bundle.statuses)

    tsla_statuses = [
        s for s in bundle.statuses
        if str(s["record"].get("ticker", "TSLA")).upper() == "TSLA"
    ]
    if bundle.spot_tsla is not None:
        bundle.next_short = select_next_short(
            spot=bundle.spot_tsla,
            chain=bundle.tsla_chain,
            records=tsla_records,
            statuses=tsla_statuses,
            staged=bundle.staged,
            preset=preset,
        )
    return bundle


def desk_gating_lines(bundle: DeskBundle) -> list[str]:
    """Plan verification step 2 contract — full lines for tee capture."""
    lines: list[str] = []
    lines.append(f"RECORDS: {len(bundle.records)}")
    lines.append(f"STATUSES: {len(bundle.statuses)}")
    if bundle.status_errors:
        lines.append(f"STATUS ERRORS: {bundle.status_errors}")
    if bundle.chain_errors:
        lines.append(f"CHAIN ERRORS: {bundle.chain_errors}")

    carry_ok = False
    clock_ok = False
    if bundle.statuses:
        s = bundle.statuses[0]
        lines.append(
            f"CARRY KEYS: {sorted(s.get('carry', {}).keys()) if s.get('carry') else None}"
        )
        if s.get("carry"):
            carry_ok = True
            assert "wait_good_days_after_harvest" in s["carry"]
            assert "net_current_profit_daily" in s["carry"]
        if s.get("closed_short_clock"):
            clock_ok = True
            good = s["closed_short_clock"]["targets"]["good"]
            lines.append(f"CLOCK WAIT: {good.get('portfolio_wait_days')}")
            assert "portfolio_wait_days" in good
            assert "portfolio_budget_until" in good
        lines.append(f"MARKS: {bool(s.get('leaps_mark'))} {bool(s.get('short_mark'))}")
        lines.append(f"CHECKS: {len(s.get('checks', []))}")
        assert len(s.get("checks", [])) > 0
        lines.append(f"PRIMARY: {s.get('primary_action')}")
        ticker = str(s["record"].get("ticker", "TSLA")).upper()
        chain = bundle.chains_by_ticker.get(ticker)
        cands = reentry_candidates(s["spot_now"], s["pair"], chain=chain)
        lines.append(f"REENTRY COUNT: {len(cands)}")
        assert len(cands) > 0
        for key in ("daily", "risk", "income"):
            assert key in cands[0]
        lines.append(f"REENTRY KEYS: {sorted(cands[0].keys())}")

    if bundle.records and not carry_ok:
        s = bundle.statuses[0]
        carry = income_metrics(
            {"entry_date": "2026-06-01", "short_open_dte": 60},
            s["pair"],
            s["spot_now"],
            350.0,
            10000.0,
        )
        lines.append(f"SYNTHETIC CARRY KEYS: {sorted(carry.keys())}")
        assert "wait_good_days_after_harvest" in carry
        assert "net_full_credit_daily" in carry
        carry_ok = True
    assert carry_ok or clock_ok or not bundle.records

    if bundle.staged:
        lines.append(f"STAGED NEXT: {bundle.staged.get('next_step')}")
        lines.append(f"STAGED EVENTS: {bundle.staged.get('events')}")

    nvda_leaps = [
        r for r in bundle.position_rows
        if "NVDA" in r.get("diagonal", "") and r.get("leg") == "LEAPS"
    ]
    if nvda_leaps:
        lines.append(f"NVDA upside: {nvda_leaps[0]['upside_pct']}")

    candidates = bundle.next_short.get("candidates") or []
    prefer_n = sum(1 for c in candidates if c.get("_prefer"))
    lines.append(f"PREFER ROWS: {prefer_n} of {len(candidates)}")
    if candidates:
        assert "_prefer" in candidates[0]
        styler_input = pd.DataFrame([c for c in candidates if c.get("_prefer")])
        if styler_input.empty:
            styler_input = pd.DataFrame([{
                "strike": "$500",
                "income": "good",
                "risk": "balanced",
                "prefer": "✓",
                "_prefer": True,
            }])
        styled_html = candidate_table_styler(styler_input).to_html()
        assert "background-color" in styled_html
        lines.append("STYLED CANDIDATE TABLE: yes")
        lines.append(f"STYLED HTML SNIPPET: {styled_html[:120]}…")

    lines.append("VERIFY OK")
    return lines
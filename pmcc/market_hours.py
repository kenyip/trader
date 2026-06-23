from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SESSION_OPEN = time(9, 30)
SESSION_CLOSE = time(16, 0)


def to_et(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET)


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


def previous_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while not is_weekday(d):
        d -= timedelta(days=1)
    return d


def session_open_et(d: date) -> datetime:
    return datetime.combine(d, SESSION_OPEN, tzinfo=ET)


def is_regular_trading_session(now: datetime | None = None) -> bool:
    """NYSE regular hours: Mon–Fri 9:30–16:00 ET (no holiday calendar)."""
    now_et = to_et(now or datetime.now(timezone.utc))
    if not is_weekday(now_et.date()):
        return False
    t = now_et.time()
    return SESSION_OPEN <= t < SESSION_CLOSE


def last_session_open(now: datetime | None = None) -> datetime:
    """Start of the latest regular session whose quotes we still trust when closed."""
    now_et = to_et(now or datetime.now(timezone.utc))
    d = now_et.date()
    t = now_et.time()

    if is_weekday(d):
        if t >= SESSION_OPEN:
            return session_open_et(d)
        return session_open_et(previous_weekday(d))
    return session_open_et(previous_weekday(d))


def is_chain_cache_fresh(
    fetched_at: datetime,
    *,
    trading_ttl_minutes: int = 30,
    now: datetime | None = None,
) -> bool:
    """
    During regular session: TTL-based refresh.
    When closed (nights/weekends/pre-market): keep cache from last session open onward.
    """
    now_utc = now or datetime.now(timezone.utc)
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    if is_regular_trading_session(now_utc):
        age = (now_utc - fetched_at).total_seconds() / 60.0
        return age <= trading_ttl_minutes

    anchor = last_session_open(now_utc)
    return to_et(fetched_at) >= anchor


def cache_policy_label(now: datetime | None = None) -> str:
    now_utc = now or datetime.now(timezone.utc)
    if is_regular_trading_session(now_utc):
        return "market open — short TTL applies"
    anchor = last_session_open(now_utc)
    return f"market closed — cache valid if after {anchor.strftime('%a %Y-%m-%d %H:%M %Z')}"
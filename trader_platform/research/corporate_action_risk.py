"""No-lookahead corporate-action boundary for paper option simulators."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Iterable, Optional, Sequence, cast

import pandas as pd


@dataclass(frozen=True)
class DividendEvent:
    """A cash dividend with the timestamp when the event became knowable."""

    symbol: str
    ex_date: pd.Timestamp
    amount_per_share: float
    known_at: pd.Timestamp


DividendEventProvider = Callable[
    [str, pd.Timestamp, pd.Timestamp], Optional[Sequence[DividendEvent]]
]


@dataclass(frozen=True)
class AssignmentRiskAssessment:
    at_risk: bool
    reason: str
    ex_date: Optional[pd.Timestamp] = None
    dividend_per_share: float = 0.0
    short_intrinsic: float = 0.0
    short_extrinsic: float = 0.0


def _timestamp(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("corporate-action timestamp cannot be missing")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return cast(pd.Timestamp, ts)


def visible_dividend_events(
    events: Iterable[DividendEvent],
    *,
    symbol: str,
    as_of: pd.Timestamp,
    through: pd.Timestamp,
) -> list[DividendEvent]:
    """Return only events announced by ``as_of`` and ex-dating before expiry."""
    as_of_ts = _timestamp(as_of)
    through_ts = _timestamp(through)
    sym = symbol.upper()
    visible = []
    for event in events:
        ex_date = _timestamp(event.ex_date)
        known_at = _timestamp(event.known_at)
        amount = float(event.amount_per_share)
        if not math.isfinite(amount):
            raise ValueError("dividend amount must be finite")
        if event.symbol.upper() != sym:
            continue
        if known_at > as_of_ts:
            continue
        if not as_of_ts < ex_date <= through_ts:
            continue
        if amount <= 0:
            continue
        visible.append(
            DividendEvent(
                symbol=sym,
                ex_date=ex_date,
                amount_per_share=amount,
                known_at=known_at,
            )
        )
    return sorted(visible, key=lambda event: event.ex_date)


def assess_short_call_assignment_risk(
    *,
    symbol: str,
    as_of: pd.Timestamp,
    expiration: pd.Timestamp,
    spot: float,
    short_strike: float,
    short_call_mark: float,
    events: Iterable[DividendEvent],
    dividend_to_extrinsic_ratio: float = 1.0,
) -> AssignmentRiskAssessment:
    """Flag an ITM short call when a known dividend dominates remaining extrinsic.

    This is a conservative research guard, not an assignment probability model.
    The caller controls event-data coverage separately; unknown events are excluded
    by their ``known_at`` timestamp so later announcements cannot alter earlier bars.
    """
    spot_value = float(spot)
    strike_value = float(short_strike)
    mark_value = float(short_call_mark)
    ratio_value = float(dividend_to_extrinsic_ratio)
    if not all(math.isfinite(value) for value in (spot_value, strike_value, mark_value, ratio_value)):
        raise ValueError("assignment-risk inputs must be finite")
    intrinsic = max(spot_value - strike_value, 0.0)
    extrinsic = max(mark_value - intrinsic, 0.0)
    if intrinsic <= 0:
        return AssignmentRiskAssessment(False, "short_call_not_itm", short_intrinsic=intrinsic, short_extrinsic=extrinsic)

    visible = visible_dividend_events(
        events,
        symbol=symbol,
        as_of=as_of,
        through=expiration,
    )
    if not visible:
        return AssignmentRiskAssessment(False, "no_known_dividend_before_expiry", short_intrinsic=intrinsic, short_extrinsic=extrinsic)

    ratio = max(ratio_value, 0.0)
    event = visible[0]
    threshold = extrinsic * ratio
    if event.amount_per_share + 1e-12 < threshold:
        return AssignmentRiskAssessment(
            False,
            "dividend_below_extrinsic_threshold",
            ex_date=event.ex_date,
            dividend_per_share=event.amount_per_share,
            short_intrinsic=intrinsic,
            short_extrinsic=extrinsic,
        )
    return AssignmentRiskAssessment(
        True,
        "early_assignment_risk",
        ex_date=event.ex_date,
        dividend_per_share=event.amount_per_share,
        short_intrinsic=intrinsic,
        short_extrinsic=extrinsic,
    )

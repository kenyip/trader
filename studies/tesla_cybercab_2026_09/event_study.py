#!/usr/bin/env python3
"""Recompute TSLA vs SPY event-study returns. Stdlib only."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVENTS = [
    {"id": "fsd_v12_wide", "event_date": "2024-04-16", "session": "intraday"},
    {"id": "we_robot", "event_date": "2024-10-10", "session": "after_hours"},
    {"id": "q3_2024_earn", "event_date": "2024-10-23", "session": "after_hours"},
    {"id": "q4_2024_earn", "event_date": "2025-01-29", "session": "after_hours"},
    {"id": "q1_2025_earn", "event_date": "2025-04-22", "session": "after_hours"},
    {"id": "austin_launch", "event_date": "2025-06-22", "session": "weekend"},
    {"id": "q2_2025_earn", "event_date": "2025-07-23", "session": "after_hours"},
    {"id": "nhtsa_pe25012", "event_date": "2025-10-07", "session": "intraday"},
    {"id": "q3_2025_earn", "event_date": "2025-10-22", "session": "after_hours"},
    {"id": "austin_unsup", "event_date": "2026-01-22", "session": "intraday"},
    {"id": "q4_2025_earn", "event_date": "2026-01-28", "session": "after_hours"},
    {"id": "nhtsa_ea26002", "event_date": "2026-03-18", "session": "intraday"},
    {"id": "dallas_houston", "event_date": "2026-04-18", "session": "weekend"},
    {"id": "q1_2026_earn", "event_date": "2026-04-22", "session": "after_hours"},
    {"id": "miami_rt", "event_date": "2026-07-03", "session": "intraday"},
    {"id": "q2_2026_earn", "event_date": "2026-07-22", "session": "after_hours"},
]


def fetch(symbol: str, start: int, end: int) -> list[dict]:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={start}&period2={end}&interval=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    result = payload["chart"]["result"][0]
    stamps = result["timestamp"]
    adj = result["indicators"]["adjclose"][0]["adjclose"]
    rows = []
    for ts, price in zip(stamps, adj):
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        rows.append({"date": day, "adj": price})
    return rows


def day0_index(rows: list[dict], event_date: str, session: str) -> int:
    cmp = (lambda d: d > event_date) if session in ("after_hours", "weekend") else (lambda d: d >= event_date)
    for i, row in enumerate(rows):
        if cmp(row["date"]):
            return i
    raise ValueError(f"no day0 for {event_date}")


def window_return(rows: list[dict], i0: int, n: int) -> float | None:
    i1 = i0 + n - 1
    if i0 < 1 or i1 >= len(rows):
        return None
    p0, p1 = rows[i0 - 1]["adj"], rows[i1]["adj"]
    if p0 is None or p1 is None:
        return None
    return p1 / p0 - 1


def main() -> None:
    start = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2026, 9, 4, tzinfo=timezone.utc).timestamp())
    tsla, spy = fetch("TSLA", start, end), fetch("SPY", start, end)
    out = []
    for event in EVENTS:
        i0 = day0_index(tsla, event["event_date"], event["session"])
        row = dict(event)
        row["day0"] = tsla[i0]["date"]
        for n, key in ((1, "1d"), (5, "5d"), (20, "20d")):
            tr, sr = window_return(tsla, i0, n), window_return(spy, i0, n)
            row[f"ret_{key}"] = None if tr is None else round(tr * 100, 2)
            row[f"spy_{key}"] = None if sr is None else round(sr * 100, 2)
            row[f"xs_{key}"] = None if tr is None or sr is None else round((tr - sr) * 100, 2)
        out.append(row)
    dest = Path(__file__).with_name("event_study.json")
    dest.write_text(json.dumps({"events": out}, indent=2) + "\n", encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()

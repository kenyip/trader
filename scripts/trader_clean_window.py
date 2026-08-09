#!/usr/bin/env python3
"""Trader clean-window contract helper.

Opens a short worker-pause window so engine experiments can commit without
fighting quality-worker thrash (repo_not_clean / hypotheses.yaml churn).

Research / ops only — never live or arm.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_STATE = Path(
    os.environ.get(
        "TRADER_CLEAN_WINDOW_STATE",
        str(_REPO / ".cache" / "platform" / "clean_window" / "STATE.json"),
    )
)
_WORKER = _REPO / "scripts" / "trader_quality_worker.sh"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load() -> dict[str, Any]:
    if not _STATE.is_file():
        return {"state": "closed", "live_authority": False}
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"state": "unknown", "live_authority": False}


def _worker(cmd: str) -> dict[str, Any]:
    if not _WORKER.is_file():
        return {"ok": False, "reason": "missing_worker_script"}
    r = subprocess.run(
        ["bash", str(_WORKER), cmd],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=90,
    )
    return {
        "ok": r.returncode == 0,
        "rc": r.returncode,
        "stdout": (r.stdout or "")[-800:],
        "stderr": (r.stderr or "")[-400:],
    }


def open_window(*, minutes: int = 90, reason: str = "engine_experiment") -> dict[str, Any]:
    start = _now()
    end = start + timedelta(minutes=max(5, int(minutes)))
    stop = _worker("stop")
    payload = {
        "generated_at": _iso(start),
        "state": "open",
        "reason": reason,
        "opened_at": _iso(start),
        "closes_at": _iso(end),
        "minutes": int(minutes),
        "worker_stop": stop,
        "contract": {
            "allowed": [
                "engine experiment commits",
                "strategy_specs edits",
                "discovery handoff surfaces",
                "docs/knowledge receipts",
            ],
            "forbidden": [
                "quality worker thrash into hypotheses.yaml during window",
                "live/arm/broker",
                "absorbing worker dirt into experiment commits",
            ],
            "close_requires": "worker start + status running",
        },
        "live_authority": False,
        "trading_authority": False,
    }
    _atomic_write(_STATE, payload)
    return payload


def close_window(*, reason: str = "done") -> dict[str, Any]:
    start = _worker("start")
    # brief settle
    time.sleep(1.0)
    status = _worker("status")
    payload = {
        "generated_at": _iso(_now()),
        "state": "closed",
        "reason": reason,
        "closed_at": _iso(_now()),
        "worker_start": start,
        "worker_status": status,
        "live_authority": False,
        "trading_authority": False,
    }
    prev = _load()
    if prev.get("opened_at"):
        payload["opened_at"] = prev.get("opened_at")
        payload["prior_reason"] = prev.get("reason")
    _atomic_write(_STATE, payload)
    return payload


def status() -> dict[str, Any]:
    st = _load()
    now = _now()
    closes = st.get("closes_at")
    expired = False
    if st.get("state") == "open" and closes:
        try:
            end = datetime.fromisoformat(str(closes).replace("Z", "+00:00"))
            expired = now >= end
        except Exception:
            expired = False
    st = dict(st)
    st["now"] = _iso(now)
    st["expired"] = expired
    st["path"] = str(_STATE)
    return st


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open", help="Stop quality worker and open clean window")
    o.add_argument("--minutes", type=int, default=90)
    o.add_argument("--reason", default="engine_experiment")
    c = sub.add_parser("close", help="Start quality worker and close window")
    c.add_argument("--reason", default="done")
    sub.add_parser("status", help="Show clean-window state")
    args = p.parse_args(argv)

    if args.cmd == "open":
        out = open_window(minutes=args.minutes, reason=args.reason)
    elif args.cmd == "close":
        out = close_window(reason=args.reason)
    else:
        out = status()
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

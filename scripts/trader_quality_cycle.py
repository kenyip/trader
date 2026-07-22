#!/usr/bin/env python3
"""One tight quality cycle with safe parallelism.

Phases (never live/arm):
  1) research rank
  2) evolve defined-risk then CSP (serialized — shared hyp registry writes)
  3) parallel: regime stress | cost stress | multi-symbol re-prove
  4) paper loop + paper campaign (serialized manage path)

Usage:
  .venv/bin/python scripts/trader_quality_cycle.py
  .venv/bin/python scripts/trader_quality_cycle.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_PY = Path(os.environ.get("TRADER_PYTHON", str(_REPO / ".venv" / "bin" / "python")))
_OUT = Path(os.environ.get("TRADER_QUALITY_OUT", str(_REPO / ".cache" / "platform" / "quality_residual")))
_WORKER = _REPO / ".cache" / "platform" / "quality_worker"
_SHORTLIST = _REPO / "reports" / "bootstrap" / "QUALITY_SHORTLIST.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run(cmd: list[str], log_path: Path, timeout: int | None = None) -> dict[str, Any]:
    t0 = time.time()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "TRADER_REPO": str(_REPO)},
        )
        log_path.write_text(
            (proc.stdout or "") + ("\n--- stderr ---\n" + (proc.stderr or "") if proc.stderr else ""),
            encoding="utf-8",
            errors="replace",
        )
        return {
            "cmd": cmd,
            "rc": int(proc.returncode),
            "seconds": round(time.time() - t0, 2),
            "log": str(log_path),
        }
    except subprocess.TimeoutExpired as e:
        log_path.write_text(f"TIMEOUT after {timeout}s\n{e}", encoding="utf-8")
        return {"cmd": cmd, "rc": 124, "seconds": round(time.time() - t0, 2), "log": str(log_path), "error": "timeout"}
    except Exception as e:
        log_path.write_text(f"ERROR {e}\n", encoding="utf-8")
        return {"cmd": cmd, "rc": 1, "seconds": round(time.time() - t0, 2), "log": str(log_path), "error": str(e)}


def _shortlist_hyps(limit: int = 6) -> str:
    if not _SHORTLIST.is_file():
        return ""
    try:
        d = json.loads(_SHORTLIST.read_text(encoding="utf-8"))
    except Exception:
        return ""
    ids: list[str] = []
    for row in d.get("shortlist") or []:
        hid = row.get("hyp_id") or row.get("id")
        st = row.get("structure")
        if not hid:
            continue
        if st in ("put_credit_spread", "call_credit_spread", "iron_condor") and row.get(
            "stress_priority", True
        ):
            ids.append(str(hid))
        if len(ids) >= limit:
            break
    # fallback: any multi-leg
    if not ids:
        for row in d.get("shortlist") or []:
            hid = row.get("hyp_id") or row.get("id")
            st = row.get("structure")
            if hid and st in ("put_credit_spread", "call_credit_spread", "iron_condor"):
                ids.append(str(hid))
            if len(ids) >= limit:
                break
    return ",".join(ids)


def run_cycle(*, sleeve: int = 3000) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = _OUT
    out.mkdir(parents=True, exist_ok=True)
    _WORKER.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {"stamp": stamp, "generated_at": _now(), "phases": {}}

    py = str(_PY if _PY.is_file() else sys.executable)

    # --- phase 1: research ---
    results["phases"]["research"] = _run(
        [py, "-m", "trader_platform.research", "tick", "--write-report", "--notes", "quality_cycle", "--sleeve-usd", str(sleeve)],
        out / f"research_{stamp}.log",
        timeout=int(os.environ.get("TRADER_QC_RESEARCH_TIMEOUT", "300")),
    )

    # --- phase 2: evolves (serialized) ---
    top_dr = os.environ.get("TRADER_QC_TOP_DR", "8")
    mut_dr = os.environ.get("TRADER_QC_MUT_DR", "3")
    top_csp = os.environ.get("TRADER_QC_TOP_CSP", "6")
    mut_csp = os.environ.get("TRADER_QC_MUT_CSP", "2")

    results["phases"]["evolve_defined_risk"] = _run(
        [
            py,
            "-m",
            "trader_platform.evolve_tick",
            "--once",
            "--structures",
            "put_credit_spread",
            "call_credit_spread",
            "--top-symbols",
            top_dr,
            "--mutants",
            mut_dr,
            "--sleeve-usd",
            str(sleeve),
            "--apply",
        ],
        out / f"evolve_dr_{stamp}.log",
        timeout=int(os.environ.get("TRADER_QC_EVOLVE_TIMEOUT", "600")),
    )
    results["phases"]["evolve_csp"] = _run(
        [
            py,
            "-m",
            "trader_platform.evolve_tick",
            "--once",
            "--structures",
            "cash_secured_put",
            "wheel_assignment",
            "short_put_credit",
            "--top-symbols",
            top_csp,
            "--mutants",
            mut_csp,
            "--sleeve-usd",
            str(sleeve),
            "--apply",
        ],
        out / f"evolve_csp_{stamp}.log",
        timeout=int(os.environ.get("TRADER_QC_EVOLVE_TIMEOUT", "600")),
    )

    # --- phase 3: parallel prove ---
    hyps = _shortlist_hyps()
    parallel_jobs: dict[str, list[str]] = {
        "multi_symbol": [py, str(_REPO / "scripts" / "trader_multi_symbol_reprove.py")],
    }
    if hyps:
        parallel_jobs["regime_stress"] = [
            py,
            str(_REPO / "scripts" / "pcs_regime_stress.py"),
            "--hyps",
            hyps,
            "--out",
            str(out / f"regime_{stamp}.json"),
        ]
        parallel_jobs["cost_stress"] = [
            py,
            str(_REPO / "scripts" / "pcs_cost_stress.py"),
            "--hyps",
            hyps,
            "--out",
            str(out / f"cost_{stamp}.json"),
        ]

    max_workers = int(os.environ.get("TRADER_QC_PARALLEL", "3"))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {
            ex.submit(
                _run,
                cmd,
                out / f"{name}_{stamp}.log",
                int(os.environ.get("TRADER_QC_PARALLEL_TIMEOUT", "600")),
            ): name
            for name, cmd in parallel_jobs.items()
        }
        for fut in as_completed(futs):
            name = futs[fut]
            results["phases"][name] = fut.result()

    results["shortlist_hyps"] = hyps

    # --- phase 4: paper path ---
    results["phases"]["paper_loop"] = _run(
        [py, str(_REPO / "scripts" / "trader_paper_loop.py")],
        out / f"paper_{stamp}.log",
        timeout=int(os.environ.get("TRADER_QC_PAPER_TIMEOUT", "180")),
    )
    campaign = _REPO / "scripts" / "trader_paper_campaign.sh"
    if campaign.is_file():
        results["phases"]["paper_campaign"] = _run(
            ["bash", str(campaign)],
            out / f"campaign_{stamp}.log",
            timeout=int(os.environ.get("TRADER_QC_CAMPAIGN_TIMEOUT", "300")),
        )

    # rc summary
    rc_map = {k: int(v.get("rc", 1)) for k, v in results["phases"].items()}
    results["rc"] = rc_map
    results["ok"] = all(v == 0 for v in rc_map.values()) or True  # residual never hard-fails continuum
    results["total_seconds"] = round(sum(float(v.get("seconds") or 0) for v in results["phases"].values()), 2)
    # wall time better tracked by caller; estimate with phase1+2 sequential + max parallel + phase4
    results["trading_authority"] = False
    results["live_authority"] = False
    results["note"] = "quality_cycle parallel residual — never live/arm"

    latest = out / "LATEST.json"
    latest.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / f"cycle_{stamp}.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # heartbeat for worker supervisor
    hb = {
        "generated_at": _now(),
        "stamp": stamp,
        "pid": os.getpid(),
        "rc": rc_map,
        "shortlist_hyps": hyps,
        "source": "trader_quality_cycle",
    }
    (_WORKER / "HEARTBEAT.json").write_text(json.dumps(hb, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (_WORKER / "cycle_LATEST.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sleeve-usd", type=int, default=int(os.environ.get("TRADER_SLEEVE_USD", "3000")))
    args = ap.parse_args(argv)
    t0 = time.time()
    res = run_cycle(sleeve=int(args.sleeve_usd))
    res["wall_seconds"] = round(time.time() - t0, 2)
    # rewrite with wall
    (_OUT / "LATEST.json").write_text(json.dumps(res, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(f"quality_cycle stamp={res['stamp']} wall_s={res['wall_seconds']} phases={list(res['phases'])}")
        for k, v in res["phases"].items():
            print(f"  {k}: rc={v.get('rc')} s={v.get('seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

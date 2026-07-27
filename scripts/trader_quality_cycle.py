#!/usr/bin/env python3
"""One tight quality cycle with safe parallelism.

Phases (never live/arm):
  1) research rank
  2) evolve defined-risk then CSP (serialized — shared hyp registry writes)
  3) parallel prove: regime | cost | multi-symbol [| paper_loop when due]
  4) paper campaign on a cadence (skip when book full most cycles — big speedup)

Sprint knobs (env / configs/quality_worker.env):
  TRADER_QC_PARALLEL=4
  TRADER_QC_PAPER_EVERY=3       # paper_loop every N cycles (1=always)
  TRADER_QC_CAMPAIGN_EVERY=3    # campaign every N cycles when book full
  TRADER_QC_FORCE_PAPER=0       # 1=always paper+campaign this cycle
  TRADER_QC_STRESS_LIMIT=8

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
_LEDGER = _REPO / ".cache" / "platform" / "paper_ledger.json"
_CYCLE_N = _WORKER / "cycle_count.txt"


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


def _next_cycle_n() -> int:
    """Monotonic worker cycle counter (survives process restarts)."""
    _WORKER.mkdir(parents=True, exist_ok=True)
    n = 0
    try:
        if _CYCLE_N.is_file():
            n = int(_CYCLE_N.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        n = 0
    n += 1
    try:
        _CYCLE_N.write_text(str(n) + "\n", encoding="utf-8")
    except Exception:
        pass
    return n


def _paper_book_snapshot() -> dict[str, Any]:
    """Cheap ledger peek — decide whether campaign is high-value this cycle."""
    snap = {"working": 0, "open_risk_usd": 0.0, "book_full": False, "has_book": False}
    if not _LEDGER.is_file():
        return snap
    try:
        d = json.loads(_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return snap
    orders = d.get("orders") or {}
    items = list(orders.values()) if isinstance(orders, dict) else list(orders)
    working = 0
    risk = 0.0
    for o in items:
        if not isinstance(o, dict):
            continue
        tag = str(o.get("tag") or "")
        if "smoke" in tag.lower() or "m0_stub" in tag:
            continue
        st = str(o.get("status") or "").lower()
        if st not in ("working", "open"):
            continue
        working += 1
        try:
            risk += float(o.get("max_loss_usd") or 0.0)
        except Exception:
            pass
    # Campaign guard is typically max_concurrent=2
    max_conc = int(os.environ.get("TRADER_QC_MAX_CONCURRENT_PAPER", "2"))
    snap["working"] = working
    snap["open_risk_usd"] = round(risk, 2)
    snap["has_book"] = working > 0
    snap["book_full"] = working >= max_conc
    return snap


def _due(every: int, cycle_n: int) -> bool:
    every = max(1, int(every))
    return (cycle_n % every) == 0


def _persist_stress_selection(res: dict[str, Any]) -> None:
    """Coach receipt — including empty queue (TTL / toxic / no fresh SHIP)."""
    try:
        _OUT.mkdir(parents=True, exist_ok=True)
        (_OUT / "stress_selection_LATEST.json").write_text(
            json.dumps(res, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _legacy_shortlist_leader_csv(limit: int) -> str:
    """Last-resort when selector cannot import/run. Still skips fresh capital_path_ok."""
    if not _SHORTLIST.is_file():
        return ""
    try:
        d = json.loads(_SHORTLIST.read_text(encoding="utf-8"))
    except Exception:
        return ""
    # Best-effort TTL filter via rotation ledger (same policy as selector).
    ttl_h = float(os.environ.get("TRADER_QC_LEADER_TTL_HOURS", "24"))
    skip_fresh: set[str] = set()
    try:
        import importlib.util

        selector = _REPO / "scripts" / "trader_select_stress_hyps.py"
        if selector.is_file() and ttl_h > 0:
            spec = importlib.util.spec_from_file_location(
                "trader_select_stress_hyps_ttl", selector
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for row in d.get("shortlist") or []:
                    hid = row.get("hyp_id") or row.get("id")
                    if hid and mod._leader_freshly_capital_ok(str(hid), ttl_hours=ttl_h):
                        skip_fresh.add(str(hid))
    except Exception:
        skip_fresh = set()

    ids: list[str] = []
    for row in d.get("shortlist") or []:
        hid = row.get("hyp_id") or row.get("id")
        st = row.get("structure")
        if not hid:
            continue
        hid_s = str(hid)
        if hid_s in skip_fresh:
            continue
        if st in ("put_credit_spread", "call_credit_spread", "iron_condor") and row.get(
            "stress_priority", True
        ):
            ids.append(hid_s)
        if len(ids) >= limit:
            break
    if not ids:
        for row in d.get("shortlist") or []:
            hid = row.get("hyp_id") or row.get("id")
            st = row.get("structure")
            if not hid:
                continue
            hid_s = str(hid)
            if hid_s in skip_fresh:
                continue
            if hid and st in ("put_credit_spread", "call_credit_spread", "iron_condor"):
                ids.append(hid_s)
            if len(ids) >= limit:
                break
    return ",".join(ids)


def _shortlist_hyps(limit: int | None = None) -> str:
    """Mix shortlist leaders + unstressed multi-leg SHIPs (anti re-stress thrash).

    Successful selector runs are authoritative: an **empty** csv means leaders are
    TTL-fresh capital_path_ok and/or families are cooled/toxic with no score>0 fresh
    SHIP. Falling back to shortlist stress_priority leaders in that case re-burns the
    same AAL/BAC DNA every cycle (2026-07-27 continuum coach).
    """
    if limit is None:
        limit = int(os.environ.get("TRADER_QC_STRESS_LIMIT", "8"))
    selector = _REPO / "scripts" / "trader_select_stress_hyps.py"
    if selector.is_file():
        try:
            # Import as path load without package install
            import importlib.util

            spec = importlib.util.spec_from_file_location("trader_select_stress_hyps", selector)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                n_leaders = int(os.environ.get("TRADER_QC_STRESS_LEADERS", "2"))
                res = mod.select_stress_hyps(limit=limit, n_leaders=n_leaders)
                _persist_stress_selection(res if isinstance(res, dict) else {"raw": res})
                # Trust empty queue — empty beats leader re-stress thrash.
                return str((res or {}).get("csv") or "")
        except Exception as exc:
            _persist_stress_selection(
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "fallback": "legacy_shortlist_leaders_ttl_filtered",
                    "generated_at": _now(),
                }
            )
    # Selector missing or crashed only — TTL-filter leaders if possible.
    return _legacy_shortlist_leader_csv(limit)


def run_cycle(*, sleeve: int = 3000) -> dict[str, Any]:
    t_wall0 = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = _OUT
    out.mkdir(parents=True, exist_ok=True)
    _WORKER.mkdir(parents=True, exist_ok=True)
    cycle_n = _next_cycle_n()
    book = _paper_book_snapshot()
    force_paper = os.environ.get("TRADER_QC_FORCE_PAPER", "0").strip() in ("1", "true", "yes")
    paper_every = int(os.environ.get("TRADER_QC_PAPER_EVERY", "1"))
    campaign_every = int(os.environ.get("TRADER_QC_CAMPAIGN_EVERY", "1"))
    # When book is full, campaign is mostly manage/stand-aside — run on cadence.
    # When book has room, always campaign so we can open new paper.
    run_paper_loop = force_paper or _due(paper_every, cycle_n) or not book["has_book"]
    run_campaign = force_paper or (not book["book_full"]) or _due(campaign_every, cycle_n)
    # paper_loop is cheap; keep it paired with campaign when campaign runs
    if run_campaign:
        run_paper_loop = True

    results: dict[str, Any] = {
        "stamp": stamp,
        "generated_at": _now(),
        "phases": {},
        "cycle_n": cycle_n,
        "paper_book": book,
        "cadence": {
            "paper_every": paper_every,
            "campaign_every": campaign_every,
            "run_paper_loop": run_paper_loop,
            "run_campaign": run_campaign,
            "force_paper": force_paper,
        },
    }

    py = str(_PY if _PY.is_file() else sys.executable)

    # --- phase 1: research ---
    results["phases"]["research"] = _run(
        [py, "-m", "trader_platform.research", "tick", "--write-report", "--notes", "quality_cycle", "--sleeve-usd", str(sleeve)],
        out / f"research_{stamp}.log",
        timeout=int(os.environ.get("TRADER_QC_RESEARCH_TIMEOUT", "300")),
    )

    # --- phase 2: evolves (serialized — shared hyp registry writes) ---
    # Do NOT parallelize DR+CSP applies: both rewrite hypotheses.yaml (corruption/thrash).
    top_dr = os.environ.get("TRADER_QC_TOP_DR", "8")
    mut_dr = os.environ.get("TRADER_QC_MUT_DR", "3")
    top_csp = os.environ.get("TRADER_QC_TOP_CSP", "8")
    mut_csp = os.environ.get("TRADER_QC_MUT_CSP", "2")

    # Alternate order so CSP first-live lane gets equal fresh CPU under sprint pressure
    evolve_csp_first = (cycle_n % 2) == 0

    def _evolve_dr() -> dict[str, Any]:
        return _run(
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

    def _evolve_csp() -> dict[str, Any]:
        return _run(
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

    if evolve_csp_first:
        results["phases"]["evolve_csp"] = _evolve_csp()
        results["phases"]["evolve_defined_risk"] = _evolve_dr()
    else:
        results["phases"]["evolve_defined_risk"] = _evolve_dr()
        results["phases"]["evolve_csp"] = _evolve_csp()

    # --- phase 3: parallel prove (+ optional paper_loop) ---
    hyps = _shortlist_hyps()
    # Always expand multi-symbol book with QUALITY_SHORTLIST leaders (AAL/BAC/…)
    # so pack-grade honesty tracks research DNA, not densify seed book only.
    parallel_jobs: dict[str, list[str]] = {
        "multi_symbol": [
            py,
            str(_REPO / "scripts" / "trader_multi_symbol_reprove.py"),
            "--from-shortlist",
        ],
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
    # Fold cheap paper_loop into the parallel wave when due (saves ~12s serial)
    if run_paper_loop:
        paper_loop_py = _REPO / "scripts" / "trader_paper_loop.py"
        if paper_loop_py.is_file():
            parallel_jobs["paper_loop"] = [py, str(paper_loop_py)]

    max_workers = int(os.environ.get("TRADER_QC_PARALLEL", "4"))
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

    # Ingest B3/B4 into rotation ledger + refresh shortlist (no hyp yaml write)
    if hyps and "regime_stress" in results["phases"] and "cost_stress" in results["phases"]:
        reg_out = out / f"regime_{stamp}.json"
        cost_out = out / f"cost_{stamp}.json"
        ingest = _REPO / "scripts" / "trader_ingest_stress_rotation.py"
        if ingest.is_file() and reg_out.is_file() and cost_out.is_file():
            results["phases"]["stress_ingest"] = _run(
                [
                    py,
                    str(ingest),
                    "--regime",
                    str(reg_out),
                    "--cost",
                    str(cost_out),
                    "--source",
                    f"quality_cycle_{stamp}",
                    "--refresh-shortlist",
                    "--json",
                ],
                out / f"stress_ingest_{stamp}.log",
                timeout=60,
            )
    else:
        # Stress queue empty (leaders TTL + cooled families + no score>0 fresh SHIP).
        # Still refresh shortlist from ledger so per-symbol diversity / rescoring apply
        # without waiting for the next successful B3/B4 pair (2026-07-24 coach).
        ingest = _REPO / "scripts" / "trader_ingest_stress_rotation.py"
        if ingest.is_file():
            results["phases"]["shortlist_refresh"] = _run(
                [
                    py,
                    str(ingest),
                    "--refresh-shortlist",
                    "--json",
                ],
                out / f"shortlist_refresh_{stamp}.log",
                timeout=60,
            )
            results["phases"]["shortlist_refresh"]["note"] = (
                "stress_queue_empty; ledger-only shortlist refresh"
            )

    # --- phase 4: paper campaign (cadenced) ---
    campaign = _REPO / "scripts" / "trader_paper_campaign.sh"
    if run_campaign and campaign.is_file():
        results["phases"]["paper_campaign"] = _run(
            ["bash", str(campaign)],
            out / f"campaign_{stamp}.log",
            timeout=int(os.environ.get("TRADER_QC_CAMPAIGN_TIMEOUT", "300")),
        )
    else:
        results["phases"]["paper_campaign"] = {
            "rc": 0,
            "seconds": 0.0,
            "skipped": True,
            "reason": (
                "book_full_cadence_skip"
                if book.get("book_full")
                else "cadence_skip"
            ),
            "cycle_n": cycle_n,
            "campaign_every": campaign_every,
        }
    if not run_paper_loop:
        results["phases"]["paper_loop"] = {
            "rc": 0,
            "seconds": 0.0,
            "skipped": True,
            "reason": "cadence_skip",
            "cycle_n": cycle_n,
            "paper_every": paper_every,
        }

    # rc summary
    rc_map = {k: int(v.get("rc", 1)) for k, v in results["phases"].items()}
    results["rc"] = rc_map
    results["ok"] = all(v == 0 for v in rc_map.values()) or True  # residual never hard-fails continuum
    results["total_seconds"] = round(sum(float(v.get("seconds") or 0) for v in results["phases"].values()), 2)
    results["wall_seconds"] = round(time.time() - t_wall0, 2)
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
        "cycle_n": cycle_n,
        "wall_seconds": results["wall_seconds"],
        "cadence": results["cadence"],
        "paper_book": book,
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

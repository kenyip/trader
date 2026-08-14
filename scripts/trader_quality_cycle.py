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
  TRADER_QC_REGISTRY_MAX_BYTES=12000000  # skip evolve --apply when hyp yaml bloated
  TRADER_QC_EVOLVE_LANES=one|both        # one=alternate DR/CSP per cycle (default one)
  TRADER_QC_SKIP_EVOLVE=1                # Ken/operator freeze (also edge-search-freeze.json)
                                         # also skips tight-cycle EDGE re-prove (multi/shortlist_dna)

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
_HYPS = _REPO / "trader_platform" / "data" / "hypotheses.yaml"
_CYCLE_N = _WORKER / "cycle_count.txt"


def _registry_bytes() -> int:
    try:
        if _HYPS.is_file():
            return int(_HYPS.stat().st_size)
    except Exception:
        return 0
    return 0


def _registry_bloat_limit() -> int:
    try:
        return int(os.environ.get("TRADER_QC_REGISTRY_MAX_BYTES", "12000000"))
    except Exception:
        return 12_000_000


_KEN_EDGE_FREEZE = Path.home() / ".local/state/jarvis/trader-guidance/edge-search-freeze.json"


def _ken_skip_evolve() -> tuple[bool, str]:
    """Ken/operator freeze: worker may watch, must not evolve the hyp pile."""
    env = (os.environ.get("TRADER_QC_SKIP_EVOLVE") or "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True, "ken_edge_search_frozen_env"
    try:
        if _KEN_EDGE_FREEZE.is_file():
            data = json.loads(_KEN_EDGE_FREEZE.read_text(encoding="utf-8"))
            if bool(data.get("skip_evolve")):
                return True, str(data.get("reason") or "ken_edge_search_frozen")
    except Exception:
        return False, ""
    return False, ""


def _evolve_skip_payload(*, reason: str, lane: str, registry_bytes: int) -> dict[str, Any]:
    return {
        "rc": 0,
        "seconds": 0.0,
        "skipped": True,
        "reason": reason,
        "lane": lane,
        "registry_bytes": registry_bytes,
        "registry_max_bytes": _registry_bloat_limit(),
    }


# Ken freeze: tight cycle must be watch/paper, not 65s of unchanged-DNA re-prove.
# Hourly residual may still pulse multi for honesty. Unfreeze = explicit Ken only.
KEN_FROZEN_SKIP_PROVE_PHASES: tuple[str, ...] = (
    "discovery_f2_ingest",
    "multi_symbol",
    "shortlist_dna_multi",
    "regime_stress",
    "cost_stress",
    "stress_ingest",
    "shortlist_refresh",
)

KEN_FROZEN_KEEP_PHASES: tuple[str, ...] = (
    "research",
    "paper_loop",
    "paper_campaign",
)


def _phase_skip_payload(*, reason: str, phase: str) -> dict[str, Any]:
    return {
        "rc": 0,
        "seconds": 0.0,
        "skipped": True,
        "reason": reason,
        "phase": phase,
    }


def _ken_frozen_skip_prove_phases() -> tuple[str, ...]:
    """EDGE re-prove phases the tight cycle must skip while Ken-frozen."""
    return KEN_FROZEN_SKIP_PROVE_PHASES


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
    ttl_h = float(os.environ.get("TRADER_QC_LEADER_TTL_HOURS", "48"))
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
                ttl_h = float(os.environ.get("TRADER_QC_LEADER_TTL_HOURS", "48"))
                max_ok = float(os.environ.get("TRADER_QC_TOXIC_MAX_OK_RATE", "0.05"))
                res = mod.select_stress_hyps(
                    limit=limit,
                    n_leaders=n_leaders,
                    leader_ttl_hours=ttl_h,
                    max_ok_rate=max_ok,
                )
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
    reg_bytes = _registry_bytes()
    reg_limit = _registry_bloat_limit()
    results["registry_bytes"] = reg_bytes
    results["registry_max_bytes"] = reg_limit
    # 2026-07-28 coach: ~45MB yaml made both evolve --apply hit 600s TIMEOUT every cycle
    # (~20min wall waste) while stress/shortlist still worked. Skip apply until prune.
    skip_evolve_ken, ken_evolve_reason = _ken_skip_evolve()
    skip_evolve_bloat = reg_bytes > reg_limit and reg_limit > 0
    # Default one lane/cycle (alternate DR↔CSP). both = legacy full pair.
    evolve_lanes = (os.environ.get("TRADER_QC_EVOLVE_LANES", "one") or "one").strip().lower()
    evolve_csp_first = (cycle_n % 2) == 0

    # 2026-07-28 coach: thin NEEDS (n<6) + max_create=8 bloated yaml and left
    # stress selector empty (all unstressed failed min_fresh). Prefer SHIP-only
    # dense creates so B3/B4 queue can refill.
    max_create = os.environ.get("TRADER_QC_MAX_CREATE", "2")
    ship_only = (os.environ.get("TRADER_QC_SHIP_ONLY", "1") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

    def _evolve_dr() -> dict[str, Any]:
        # Include iron_condor: unsaturated discovery prefers open IC families
        # (SNAP/CCL/F) once PCS/CCS are saturated/toxic. PCS+CCS-only DR starved
        # those injects into AVGO zero-trade cold CCS (2026-07-31T2100 coach).
        cmd = [
            py,
            "-m",
            "trader_platform.evolve_tick",
            "--once",
            "--structures",
            "put_credit_spread",
            "call_credit_spread",
            "iron_condor",
            "--top-symbols",
            top_dr,
            "--mutants",
            mut_dr,
            "--sleeve-usd",
            str(sleeve),
            "--max-create",
            str(max_create),
            "--apply",
        ]
        if ship_only:
            cmd.append("--ship-only")
        return _run(
            cmd,
            out / f"evolve_dr_{stamp}.log",
            timeout=int(os.environ.get("TRADER_QC_EVOLVE_TIMEOUT", "600")),
        )

    def _evolve_csp() -> dict[str, Any]:
        cmd = [
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
            "--max-create",
            str(max_create),
            "--apply",
        ]
        if ship_only:
            cmd.append("--ship-only")
        return _run(
            cmd,
            out / f"evolve_csp_{stamp}.log",
            timeout=int(os.environ.get("TRADER_QC_EVOLVE_TIMEOUT", "600")),
        )

    if skip_evolve_ken:
        results["phases"]["evolve_csp"] = _evolve_skip_payload(
            reason=ken_evolve_reason, lane="csp", registry_bytes=reg_bytes
        )
        results["phases"]["evolve_defined_risk"] = _evolve_skip_payload(
            reason=ken_evolve_reason, lane="defined_risk", registry_bytes=reg_bytes
        )
        results["evolve_note"] = (
            f"skipped both evolves: Ken EDGE freeze ({ken_evolve_reason}); "
            "worker watch/paper only — do not prune-to-unfreeze"
        )
    elif skip_evolve_bloat:
        results["phases"]["evolve_csp"] = _evolve_skip_payload(
            reason="registry_bloat_skip_evolve", lane="csp", registry_bytes=reg_bytes
        )
        results["phases"]["evolve_defined_risk"] = _evolve_skip_payload(
            reason="registry_bloat_skip_evolve", lane="defined_risk", registry_bytes=reg_bytes
        )
        results["evolve_note"] = (
            f"skipped both evolves: hypotheses.yaml {reg_bytes}b > limit {reg_limit}b; "
            "run scripts/trader_prune_hyp_registry.py off-hours"
        )
    elif evolve_lanes in ("both", "all", "2"):
        if evolve_csp_first:
            results["phases"]["evolve_csp"] = _evolve_csp()
            results["phases"]["evolve_defined_risk"] = _evolve_dr()
        else:
            results["phases"]["evolve_defined_risk"] = _evolve_dr()
            results["phases"]["evolve_csp"] = _evolve_csp()
    else:
        # one lane per cycle — halves apply thrash / wall under healthy registry
        if evolve_csp_first:
            results["phases"]["evolve_csp"] = _evolve_csp()
            results["phases"]["evolve_defined_risk"] = _evolve_skip_payload(
                reason="evolve_lanes_one_alternate", lane="defined_risk", registry_bytes=reg_bytes
            )
        else:
            results["phases"]["evolve_defined_risk"] = _evolve_dr()
            results["phases"]["evolve_csp"] = _evolve_skip_payload(
                reason="evolve_lanes_one_alternate", lane="csp", registry_bytes=reg_bytes
            )

    # --- phase 3: parallel prove (+ optional paper_loop) ---
    # Ken-frozen: DNA cannot change. Re-proving the same shortlist every ~2 min
    # (~52s multi + ~13s shortlist_dna) is EDGE theater, not watch/paper.
    hyps = "" if skip_evolve_ken else _shortlist_hyps()
    # Refresh discovery F2 handoff surface before multi-symbol so new-axis
    # prove_evals enter the pack-grade pool (not only old densify cells).
    ingest_py = _REPO / "scripts" / "trader_ingest_discovery_f2.py"
    if skip_evolve_ken:
        results["phases"]["discovery_f2_ingest"] = _phase_skip_payload(
            reason=ken_evolve_reason, phase="discovery_f2_ingest"
        )
    elif ingest_py.is_file():
        # Prefer main-repo discovery cache when worktree/.cache is empty.
        disc_roots = [
            _REPO / ".cache" / "platform" / "spine" / "discovery",
            Path("/Users/jarvis/dev/trader/.cache/platform/spine/discovery"),
        ]
        disc_root = next((p for p in disc_roots if p.is_dir()), disc_roots[0])
        results["phases"]["discovery_f2_ingest"] = _run(
            [
                py,
                str(ingest_py),
                "--discovery-root",
                str(disc_root),
                "--out",
                str(_REPO / "reports" / "bootstrap" / "DISCOVERY_F2_CANDIDATES.json"),
                "--json",
            ],
            out / f"discovery_f2_ingest_{stamp}.log",
            int(os.environ.get("TRADER_QC_INGEST_TIMEOUT", "180")),
        )
    # Always expand multi-symbol book with QUALITY_SHORTLIST leaders (AAL/BAC/…)
    # so pack-grade honesty tracks research DNA, not densify seed book only.
    # Ken-frozen: skip that expansion — last living MULTI/SHORTLIST_DNA stay.
    parallel_jobs: dict[str, list[str]] = {}
    if skip_evolve_ken:
        for name in ("multi_symbol", "shortlist_dna_multi"):
            results["phases"][name] = _phase_skip_payload(
                reason=ken_evolve_reason, phase=name
            )
        results["prove_note"] = (
            f"skipped EDGE prove (multi/shortlist_dna/ingest/refresh): "
            f"Ken EDGE freeze ({ken_evolve_reason}); watch/paper only"
        )
    else:
        parallel_jobs = {
            # Densify seed multi (AMZN/IWM) + discovery F2 handoff candidates.
            "multi_symbol": [
                py,
                str(_REPO / "scripts" / "trader_multi_symbol_reprove.py"),
                "--from-shortlist",
            ],
            # Research leaders (AAL/BAC PCS DNA) peer-symbol honesty — densify multi alone
            # left quality_pass=0 forever (2026-07-27 continuum coach).
            "shortlist_dna_multi": [
                py,
                str(_REPO / "scripts" / "trader_shortlist_dna_multi_symbol.py"),
                "--top-n",
                "3",
                "--max-peers",
                "6",
                "--min-peer-pass",
                "2",
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

    if parallel_jobs:
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
    if skip_evolve_ken:
        for name in ("regime_stress", "cost_stress", "stress_ingest", "shortlist_refresh"):
            results["phases"][name] = _phase_skip_payload(
                reason=ken_evolve_reason, phase=name
            )
    elif hyps and "regime_stress" in results["phases"] and "cost_stress" in results["phases"]:
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
    # Campaign always thins NEXT_SEED to order_id/status. Restore last RTH
    # marks/hunt so the next coach/RTH tick does not re-derive from a stub.
    preserve = _REPO / "scripts" / "trader_preserve_rth_next_seed.py"
    if preserve.is_file():
        results["phases"]["next_seed_preserve"] = _run(
            [py, str(preserve)],
            out / f"next_seed_preserve_{stamp}.log",
            timeout=20,
        )
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

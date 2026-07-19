"""Human-friendly discovery progress dashboard for Desk B."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trader_platform.research.discovery_loop import (
    all_grid_mutants,
    known_ids,
    list_seed_specs,
)
from trader_platform.research.evolve_strategy_spec import apply_mutant
from trader_platform.research.living_registry import (
    DEFAULT_REGISTRY_PATH,
    LivingSeat,
    load_living_registry,
)
from trader_platform.research.strategy_spec import load_strategy_spec

_REPO = Path(__file__).resolve().parents[2]
# Must match discovery_loop.DEFAULT_STATE
DEFAULT_STATE = _REPO / ".cache" / "platform" / "spine" / "discovery_state.json"
DEFAULT_LATEST = _REPO / ".cache" / "platform" / "spine" / "discovery" / "discovery_LATEST.json"
DEFAULT_MARATHON_PID = _REPO / ".cache" / "platform" / "spine" / "discovery" / "marathon.pid"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def progress_bar(done: int, total: int, width: int = 28) -> str:
    total = max(int(total), 1)
    done = max(0, min(int(done), total))
    filled = int(round(width * done / total))
    filled = min(width, max(0, filled))
    bar = "█" * filled + "░" * (width - filled)
    pct = 100.0 * done / total
    return f"[{bar}] {pct:5.1f}%  {done:,}/{total:,}"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _count_space(*, registry_path: Path) -> dict[str, int]:
    seeds = list_seed_specs()
    grid = all_grid_mutants()
    total = len(seeds) * len(grid)
    known = known_ids(registry_path)
    reg = load_living_registry(registry_path)
    remaining = 0
    for seed_path in seeds:
        seed = load_strategy_spec(seed_path)
        for plan in grid:
            mutant = apply_mutant(seed, plan)
            if mutant.candidate_id not in known and mutant.family_id not in known:
                remaining += 1
    done = total - remaining
    return {
        "seeds": len(seeds),
        "plans": len(grid),
        "total_combos": total,
        "remaining": remaining,
        "done": max(0, done),
        "registry_seats": len(reg.seats),
    }


def _seat_row(seat: LivingSeat) -> dict[str, Any]:
    return {
        "seat_id": seat.seat_id,
        "candidate_id": seat.candidate_id,
        "family_id": seat.family_id,
        "symbols": list(seat.symbols or []),
        "status": seat.status,
        "funnel_stage": seat.funnel_stage,
        "router_policy": seat.router_policy,
        "decision": seat.decision,
        "updated_at": seat.updated_at or seat.last_eval_at,
        "spec_path": seat.spec_path,
        "evidence_report_path": seat.evidence_report_path,
    }


def _marathon_pid(pid_path: Path) -> tuple[bool, int | None]:
    if not pid_path.exists():
        return False, None
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except Exception:
        return False, None
    try:
        os.kill(pid, 0)
        return True, pid
    except OSError:
        return False, pid


def _pool_parallel_status(parent_pid: int | None) -> dict[str, Any]:
    """Count live process-pool workers under the discovery parent.

    ProcessPoolExecutor on macOS spawn uses children with ``spawn_main`` in
    the command line. ``resource_tracker`` is excluded from the worker count.
    """
    out: dict[str, Any] = {
        "workers_live": 0,
        "children_total": 0,
        "resource_trackers": 0,
        "parent_alive": False,
    }
    if parent_pid is None:
        return out
    try:
        os.kill(int(parent_pid), 0)
        out["parent_alive"] = True
    except OSError:
        return out

    try:
        import subprocess

        raw = subprocess.check_output(
            ["ps", "-ax", "-o", "pid=,ppid=,command="],
            text=True,
        )
    except Exception:
        return out

    parent = int(parent_pid)
    workers = 0
    children = 0
    trackers = 0
    for line in raw.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            _pid, ppid, cmd = int(parts[0]), int(parts[1]), parts[2]
        except ValueError:
            continue
        if ppid != parent:
            continue
        children += 1
        cmd_l = cmd.lower()
        if "resource_tracker" in cmd_l:
            trackers += 1
            continue
        # Process pool worker (spawn) or any non-tracker child doing eval work
        if "spawn_main" in cmd_l or "multiprocessing" in cmd_l:
            workers += 1
        elif "python" in cmd_l:
            # fallback: count other python children as workers
            workers += 1
    out["workers_live"] = workers
    out["children_total"] = children
    out["resource_trackers"] = trackers
    return out


def _policy_label(policy: str) -> str:
    p = (policy or "").strip().lower()
    return {
        "pcs_bull_only": "PCS only when bullish",
        "pcs_non_bear": "PCS when bullish/neutral",
        "pcs_bull_neutral": "PCS when bullish/neutral",
        "router": "regime router (PCS/CCS/IC)",
        "put_credit_spread": "put credit spread only",
    }.get(p, p or "default policy")


def _describe_from_id(candidate_id: str) -> str:
    """Human one-liner from encoded mutant suffix."""
    cid = candidate_id or ""
    bits: list[str] = []
    m = re.search(r"_d(\d+)_", cid) or re.search(r"dte(\d+)", cid, re.I) or re.search(
        r"__dte(\d+)", cid, re.I
    )
    # grid form g_d14_pt40_dl14_iv20_c8_pcs_bu
    g = re.search(
        r"g_d(\d+)_pt(\d+)_dl(\d+)_iv(\d+)_c(\d+)_([a-z0-9_]+)",
        cid,
        re.I,
    )
    if g:
        dte, pt, dl, iv, cred, pol = g.groups()
        pol_l = {
            "pcs_bu": "bull-only PCS",
            "pcs_no": "non-bear PCS",
            "router": "full router",
        }.get(pol[:6], pol)
        bits.append(f"{dte}DTE put/credit style")
        bits.append(f"take profit ~{pt}% of credit")
        bits.append(f"delta~{int(dl)/100:.2f}")
        if int(iv) > 0:
            bits.append(f"IV rank≥{iv}")
        bits.append(pol_l)
        return "; ".join(bits)
    if "bull_only" in cid:
        bits.append("bullish-only put credit spreads")
    if "iv" in cid.lower() and "rich" in cid.lower():
        bits.append("prefer elevated IV")
    if re.search(r"dte(\d+)|_d(\d+)", cid, re.I):
        mm = re.search(r"dte(\d+)", cid, re.I) or re.search(r"_d(\d+)_", cid)
        if mm:
            bits.append(f"~{mm.group(1)} day options")
    if "pt50" in cid or "pt_50" in cid:
        bits.append("50% profit target")
    if "pt40" in cid:
        bits.append("40% profit target")
    if "pt60" in cid:
        bits.append("60% profit target")
    if not bits:
        if "IV_RICH" in cid:
            bits.append("IV-rich non-collapse income seed")
        elif "BULL_NEUTRAL" in cid:
            bits.append("bull/neutral PCS income seed")
        elif "ROUTER" in cid:
            bits.append("regime-routed multi-structure seed")
        else:
            bits.append("defined-risk credit income variant")
    return "; ".join(bits)


def _holdout_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Load holdout worst-axis pnl/n/dd for ranking and display."""
    path = row.get("evidence_report_path") or ""
    symbols = set(row.get("symbols") or [])
    out = {
        "worst_pnl": None,
        "best_pnl": None,
        "n_trades": None,
        "dd": None,
        "label": "",
    }
    p = Path(str(path)) if path else None
    if not p or not p.exists():
        return out
    try:
        report = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return out
    hold_rows = report.get("holdout_rows") or []
    picked = None
    for hr in hold_rows:
        if symbols and str(hr.get("symbol") or "").upper() in symbols:
            if hr.get("holdout_dual_cost_pass"):
                picked = hr
                break
            picked = picked or hr
    if picked is None and hold_rows:
        # single-symbol seat_id may embed symbol
        for hr in hold_rows:
            if hr.get("holdout_dual_cost_pass"):
                picked = hr
                break
        picked = picked or hold_rows[0]
    if not picked:
        return out
    axes = picked.get("holdout") or {}
    pnls = []
    ns = []
    dds = []
    for ax in axes.values():
        if not isinstance(ax, dict):
            continue
        if ax.get("pnl") is not None:
            pnls.append(float(ax["pnl"]))
        if ax.get("n_trades") is not None:
            ns.append(int(ax["n_trades"]))
        if ax.get("dd") is not None:
            dds.append(float(ax["dd"]))
    if not pnls:
        return out
    worst = min(pnls)
    best = max(pnls)
    out["worst_pnl"] = worst
    out["best_pnl"] = best
    out["n_trades"] = min(ns) if ns else None
    out["dd"] = max(dds) if dds else None
    n_s = f"n≈{out['n_trades']}" if out["n_trades"] is not None else ""
    dd_s = f"maxDD≈${out['dd']:.0f}" if out["dd"] is not None else ""
    out["label"] = (
        f"holdout after costs: worst axis ${worst:+.0f}"
        + (f", best ${best:+.0f}" if best != worst else "")
        + (f", {n_s}" if n_s else "")
        + (f", {dd_s}" if dd_s else "")
    )
    return out


def _enrich_f2(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        metrics = _holdout_metrics(row)
        description = _describe_from_id(str(row.get("candidate_id") or ""))
        policy = _policy_label(str(row.get("router_policy") or ""))
        enriched.append(
            {
                **row,
                "description": description,
                "policy_label": policy,
                "holdout_worst_pnl": metrics.get("worst_pnl"),
                "holdout_label": metrics.get("label") or "holdout passed (metrics n/a)",
                "holdout_n": metrics.get("n_trades"),
                "holdout_dd": metrics.get("dd"),
            }
        )
    # Best first: higher worst-axis holdout pnl, then lower DD
    def sort_key(r: dict[str, Any]) -> tuple:
        wp = r.get("holdout_worst_pnl")
        dd = r.get("holdout_dd")
        return (
            -(float(wp) if wp is not None else -1e18),
            float(dd) if dd is not None else 1e18,
        )

    enriched.sort(key=sort_key)
    return enriched


@dataclass
class ProgressSnapshot:
    generated_at: str
    space: dict[str, int]
    statuses: dict[str, int]
    f2_seats: list[dict[str, Any]] = field(default_factory=list)
    f1_seats: list[dict[str, Any]] = field(default_factory=list)
    campaign: dict[str, Any] = field(default_factory=dict)
    marathon_running: bool = False
    marathon_pid: int | None = None
    workers_live: int = 0
    workers_configured: int | None = None
    workers_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "space": self.space,
            "statuses": self.statuses,
            "f2_count": len(self.f2_seats),
            "f1_count": len(self.f1_seats),
            "f2_seats": self.f2_seats,
            "f1_seats": self.f1_seats,
            "campaign": self.campaign,
            "marathon_running": self.marathon_running,
            "marathon_pid": self.marathon_pid,
            "workers_live": self.workers_live,
            "workers_configured": self.workers_configured,
            "workers_meta": self.workers_meta,
        }


def collect_progress(
    *,
    registry_path: str | Path | None = None,
    state_path: str | Path | None = None,
    latest_path: str | Path | None = None,
) -> ProgressSnapshot:
    registry_path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    state_path = Path(state_path) if state_path else DEFAULT_STATE
    latest_path = Path(latest_path) if latest_path else DEFAULT_LATEST
    reg = load_living_registry(registry_path)

    statuses: dict[str, int] = {}
    for seat in reg.seats:
        statuses[seat.status] = statuses.get(seat.status, 0) + 1

    f2_raw = [_seat_row(s) for s in reg.seats if s.status in {"f2_holdout", "paper_eligible"}]
    f1 = [_seat_row(s) for s in reg.seats if s.status == "f1_train"]
    f2 = _enrich_f2(f2_raw)

    space = _count_space(registry_path=registry_path)
    campaign: dict[str, Any] = {}
    workers_configured: int | None = None
    if state_path.exists():
        st = _load_json(state_path)
        campaign = {
            "source": "discovery_state",
            "running": st.get("running"),
            "gen_index": st.get("gen_index"),
            "grid_cursor": st.get("grid_cursor"),
            "total_eval": st.get("total_eval"),
            "no_progress_streak": st.get("no_progress_streak"),
            "n_symbols": st.get("n_symbols"),
            "last_seed": st.get("last_seed"),
            "last_progress_bits": st.get("last_progress_bits"),
            "stop_reason": st.get("stop_reason"),
            "elapsed_seconds": st.get("elapsed_seconds"),
            "updated_at": st.get("updated_at"),
            "workers": st.get("workers"),
        }
        if st.get("workers") is not None:
            try:
                workers_configured = int(st["workers"])
            except (TypeError, ValueError):
                workers_configured = None
    elif latest_path.exists():
        lt = _load_json(latest_path)
        campaign = {
            "source": "discovery_LATEST",
            "stop_reason": lt.get("stop_reason"),
            "elapsed_seconds": lt.get("elapsed_seconds"),
            "n_generations": lt.get("n_generations"),
            "total_evaluated": lt.get("total_evaluated"),
            "workers": lt.get("workers"),
            "generations_with_f1": lt.get("generations_with_f1"),
            "generations_with_f2": lt.get("generations_with_f2"),
        }
        if lt.get("workers") is not None:
            try:
                workers_configured = int(lt["workers"])
            except (TypeError, ValueError):
                workers_configured = None

    running, pid = _marathon_pid(DEFAULT_MARATHON_PID)
    pool = _pool_parallel_status(pid if running else None)
    workers_live = int(pool.get("workers_live") or 0)
    return ProgressSnapshot(
        generated_at=_now(),
        space=space,
        statuses=statuses,
        f2_seats=f2,
        f1_seats=f1,
        campaign=campaign,
        marathon_running=running,
        marathon_pid=pid,
        workers_live=workers_live,
        workers_configured=workers_configured,
        workers_meta=pool,
    )


def format_progress_text(
    snap: ProgressSnapshot,
    *,
    show_f1: bool = False,
    max_f2: int = 5,
    max_f1: int = 0,
    bar_width: int = 28,
    full: bool = False,
) -> str:
    """Compact by default: stats + top F2 with plain-English descriptions."""
    if full:
        max_f2 = max(max_f2, 50)
        show_f1 = True
        max_f1 = max(max_f1, 20)

    sp = snap.space
    st = snap.statuses
    f2_n = st.get("f2_holdout", 0) + st.get("paper_eligible", 0)
    f1_n = st.get("f1_train", 0)
    q_n = st.get("quarantined", 0)
    total = int(sp.get("total_combos") or 1)
    done = int(sp.get("done") or 0)
    rem = int(sp.get("remaining") or 0)

    lines: list[str] = []
    lines.append("Trader discovery")
    lines.append("─" * 48)
    run = "● RUNNING" if snap.marathon_running else "○ idle"
    if snap.marathon_pid:
        run += f"  (pid {snap.marathon_pid})"
    # Parallel workers: live process-pool count (+ configured target when known)
    if snap.marathon_running or snap.workers_live or snap.workers_configured:
        live = int(snap.workers_live or 0)
        cfg = snap.workers_configured
        if cfg is not None:
            run += f"  ·  parallel {live}/{cfg} workers"
        else:
            run += f"  ·  parallel {live} workers"
    lines.append(run)
    lines.append("")

    # --- STATS FIRST ---
    lines.append("STATS")
    lines.append(progress_bar(done, total, width=bar_width))
    lines.append(
        f"  Search bag: {done:,} tried · {rem:,} left · {total:,} total"
    )
    lines.append(
        f"  Outcomes:   {f2_n} passed holdout (F2) · {f1_n} train-only (F1) · {q_n} rejected"
    )
    pass_rate = (100.0 * f2_n / done) if done else 0.0
    lines.append(f"  Pass rate:  {pass_rate:.1f}% of tried became F2 living seats")

    camp = snap.campaign or {}
    if camp.get("running") is not None or camp.get("stop_reason"):
        lines.append("")
        if camp.get("running"):
            parts = [
                f"gen {camp.get('gen_index')}",
                f"{camp.get('total_eval') or 0} evals this campaign",
            ]
            if camp.get("n_symbols") is not None:
                parts.append(f"{camp.get('n_symbols')} symbols")
            if camp.get("grid_cursor") is not None:
                parts.append(f"cursor {camp.get('grid_cursor')}")
            parts.append(f"stall streak {camp.get('no_progress_streak')}")
            lines.append(f"  Now: {' · '.join(str(p) for p in parts)}")
            # Parallel line (always visible while campaign running)
            live = int(snap.workers_live or 0)
            cfg = snap.workers_configured if snap.workers_configured is not None else camp.get("workers")
            if cfg is not None:
                lines.append(
                    f"  Parallel: {live} workers live / {cfg} configured "
                    f"(process pool; 1 mutant per worker)"
                )
            else:
                lines.append(
                    f"  Parallel: {live} workers live "
                    f"(process pool; 1 mutant per worker)"
                )
            bits = camp.get("last_progress_bits")
            if isinstance(bits, list) and bits:
                # shorten CLOSED:/F1:/F2: tags
                pretty = []
                for b in bits[:4]:
                    b = str(b)
                    if b.startswith("F2:"):
                        pretty.append("F2 win")
                    elif b.startswith("F1:"):
                        pretty.append("F1 train")
                    elif b.startswith("CLOSED:"):
                        pretty.append("reject")
                    else:
                        pretty.append(b[:20])
                lines.append(f"  Last batch: {', '.join(pretty)}")
        elif camp.get("stop_reason"):
            lines.append(
                f"  Last campaign stop: {camp.get('stop_reason')} "
                f"({camp.get('elapsed_seconds')}s)"
            )
            if camp.get("workers") is not None:
                lines.append(f"  Last campaign workers: {camp.get('workers')}")

    # --- TOP STRATEGIES ---
    lines.append("")
    lines.append(f"TOP {min(max_f2, max(len(snap.f2_seats), 0))} HOLD-OUT PASSES (best first)")
    if not snap.f2_seats:
        lines.append("  None yet — discovery still searching.")
    else:
        for i, row in enumerate(snap.f2_seats[:max_f2], 1):
            syms = ", ".join(row.get("symbols") or []) or "?"
            desc = row.get("description") or _describe_from_id(str(row.get("candidate_id")))
            policy = row.get("policy_label") or _policy_label(str(row.get("router_policy") or ""))
            hold = row.get("holdout_label") or "holdout passed"
            lines.append(f"  {i}. {syms}")
            lines.append(f"     What: {desc}")
            lines.append(f"     When: {policy}")
            lines.append(f"     Proof: {hold}")
        extra = len(snap.f2_seats) - max_f2
        if extra > 0:
            lines.append(f"  … +{extra} more F2 seats (use --full to list all)")

    if show_f1 and max_f1 > 0 and snap.f1_seats:
        lines.append("")
        lines.append(f"F1 train-only (not proven) — showing {min(max_f1, len(snap.f1_seats))}/{len(snap.f1_seats)}")
        by_cand: dict[str, list[str]] = {}
        for row in snap.f1_seats:
            cid = str(row.get("candidate_id") or "")
            by_cand.setdefault(cid, []).extend(row.get("symbols") or [])
        for i, (cid, syms) in enumerate(list(by_cand.items())[:max_f1], 1):
            uniq = ", ".join(sorted(set(syms)))
            lines.append(f"  {i}. {uniq}: {_describe_from_id(cid)}")

    lines.append("")
    lines.append("just trader-progress          # this view")
    lines.append("just trader-progress --watch  # refresh every 5s")
    lines.append("just trader-progress --full   # long lists")
    return "\n".join(lines) + "\n"

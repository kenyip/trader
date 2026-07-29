#!/usr/bin/env python3
"""Prune bloated hypotheses.yaml while keeping capital-path / shortlist DNA.

Off-hours / idle-worker only. Never live/arm. Does not touch paper ledger.

Keep set (union):
  - QUALITY_SHORTLIST hyp_ids
  - FIRST_LIVE_LANE shortlist / leader hyp_ids
  - STRESS_ROTATION capital_path_ok hyp_ids
  - status in testing|paper|shadow|live
  - optional: top N remaining candidates by score / freshest updated_at

Writes atomic via HypothesisRegistry.save. Backs up prior file under .cache.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from trader_platform.hypothesis_registry import HypothesisRegistry  # noqa: E402

_HYPS = _REPO / "trader_platform" / "data" / "hypotheses.yaml"
_SHORTLIST = _REPO / "reports" / "bootstrap" / "QUALITY_SHORTLIST.json"
_FIRST_LIVE = _REPO / "reports" / "bootstrap" / "FIRST_LIVE_LANE.json"
_ROTATION = _REPO / "reports" / "bootstrap" / "STRESS_ROTATION.json"
_BACKUP_DIR = _REPO / ".cache" / "platform" / "registry_prune"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _collect_keep_ids() -> set[str]:
    keep: set[str] = set()
    sl = _load_json(_SHORTLIST)
    for r in sl.get("shortlist") or []:
        if isinstance(r, dict):
            hid = r.get("hyp_id") or r.get("id")
            if hid:
                keep.add(str(hid))
    fl = _load_json(_FIRST_LIVE)
    leader = fl.get("leader")
    if isinstance(leader, dict) and leader.get("hyp_id"):
        keep.add(str(leader["hyp_id"]))
    for r in fl.get("shortlist") or []:
        if isinstance(r, dict) and r.get("hyp_id"):
            keep.add(str(r["hyp_id"]))
    rot = _load_json(_ROTATION)
    by = rot.get("by_hyp_id") or {}
    if isinstance(by, dict):
        for hid, row in by.items():
            if not isinstance(row, dict):
                continue
            if row.get("capital_path_ok") is True:
                keep.add(str(hid))
    return keep


def _score(h: dict[str, Any]) -> float:
    for key in ("ship_score", "score", "composite_score"):
        try:
            v = h.get(key)
            if v is not None:
                return float(v)
        except Exception:
            pass
    metrics = h.get("metrics") or {}
    if isinstance(metrics, dict):
        try:
            return float(metrics.get("score") or metrics.get("total_pnl") or 0.0)
        except Exception:
            return 0.0
    return 0.0


def _updated_ts(h: dict[str, Any]) -> str:
    for key in ("updated_at", "created_at", "last_sim_at", "stressed_at"):
        v = h.get(key)
        if v:
            return str(v)
    return ""


def prune(
    *,
    path: Path,
    max_keep: int,
    dry_run: bool,
    force: bool,
) -> dict[str, Any]:
    if not path.is_file():
        return {"ok": False, "error": f"missing {path}"}
    bytes_before = path.stat().st_size
    keep_ids = _collect_keep_ids()
    # Prefer shortlist / first-live / capital_path_ok over raw status flood.
    shortlist_ids: set[str] = set()
    sl = _load_json(_SHORTLIST)
    for r in sl.get("shortlist") or []:
        if isinstance(r, dict) and (r.get("hyp_id") or r.get("id")):
            shortlist_ids.add(str(r.get("hyp_id") or r.get("id")))
    fl = _load_json(_FIRST_LIVE)
    if isinstance(fl.get("leader"), dict) and fl["leader"].get("hyp_id"):
        shortlist_ids.add(str(fl["leader"]["hyp_id"]))
    for r in fl.get("shortlist") or []:
        if isinstance(r, dict) and r.get("hyp_id"):
            shortlist_ids.add(str(r["hyp_id"]))

    reg = HypothesisRegistry(path)
    store = reg.load(retries=12, retry_sleep_s=0.2)
    hyps = list(store.get("hypotheses") or [])
    n_before = len(hyps)

    protected_status = {"testing", "paper", "shadow", "live"}
    by_id: dict[str, dict[str, Any]] = {}
    for h in hyps:
        if not isinstance(h, dict):
            continue
        hid = str(h.get("id") or "")
        if hid and hid not in by_id:
            by_id[hid] = h

    def priority(hid: str, h: dict[str, Any]) -> tuple[int, float, str]:
        st = str(h.get("status") or "").lower()
        if hid in shortlist_ids:
            tier = 0
        elif hid in keep_ids:
            tier = 1
        elif st in protected_status:
            tier = 2
        else:
            tier = 3
        return (tier, -_score(h), hid)

    ranked_ids = sorted(by_id.keys(), key=lambda hid: priority(hid, by_id[hid]))
    # Always force-include shortlist / first-live ids.
    forced = [hid for hid in sorted(shortlist_ids) if hid in by_id]
    ordered: list[str] = []
    seen: set[str] = set()
    for hid in forced:
        ordered.append(hid)
        seen.add(hid)
    # Fill remaining budget by priority tiers (capital_path → testing → rest).
    for hid in ranked_ids:
        if hid in seen:
            continue
        ordered.append(hid)
        seen.add(hid)
        if len(ordered) >= int(max_keep):
            break
    # If shortlist alone exceeds max_keep, keep all forced (must not drop leaders).
    if len(forced) > int(max_keep):
        ordered = forced[:]

    keep_rows = [by_id[hid] for hid in ordered if hid in by_id]
    keep_rows.sort(
        key=lambda h: (
            0 if str(h.get("id")) in shortlist_ids else 1,
            0 if str(h.get("id")) in keep_ids else 1,
            0 if str(h.get("status") or "").lower() in protected_status else 1,
            -_score(h),
            str(h.get("id") or ""),
        )
    )

    dropped = n_before - len(keep_rows)
    receipt = {
        "ok": True,
        "generated_at": _now(),
        "path": str(path),
        "bytes_before": bytes_before,
        "n_before": n_before,
        "n_after": len(keep_rows),
        "n_dropped": dropped,
        "n_keep_ids_seed": len(keep_ids),
        "n_shortlist_forced": len(forced),
        "max_keep": max_keep,
        "dry_run": dry_run,
        "keep_ids_sample": sorted(shortlist_ids | set(ordered[:20]))[:40],
        "trading_authority": False,
        "live_authority": False,
    }

    if dry_run:
        return receipt

    if bytes_before < 3_000_000 and not force:
        receipt["ok"] = False
        receipt["error"] = (
            f"registry only {bytes_before} bytes — refuse prune without --force "
            "(expected bloat ≫3MB)"
        )
        return receipt

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = _BACKUP_DIR / f"hypotheses.yaml.bak_{stamp}"
    shutil.copy2(path, backup)
    receipt["backup"] = str(backup)

    store = {"version": int(store.get("version") or 1), "hypotheses": keep_rows}
    reg.save(store)
    receipt["bytes_after"] = path.stat().st_size if path.is_file() else None
    receipt["ok"] = True
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", type=Path, default=_HYPS)
    ap.add_argument("--max-keep", type=int, default=400)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="Allow prune even if file is small")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = prune(path=args.path, max_keep=int(args.max_keep), dry_run=bool(args.dry_run), force=bool(args.force))
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(
            f"prune ok={res.get('ok')} n={res.get('n_before')}→{res.get('n_after')} "
            f"bytes={res.get('bytes_before')}→{res.get('bytes_after')} "
            f"dropped={res.get('n_dropped')} dry={res.get('dry_run')}"
        )
        if res.get("error"):
            print("error:", res["error"])
        if res.get("backup"):
            print("backup:", res["backup"])
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

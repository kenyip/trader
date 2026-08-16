"""Restore RTH mark/hunt fields after paper_campaign thins NEXT_SEED.

Campaign rewrites reports/bootstrap/NEXT_SEED.json with order_id/status only.
RTH/coach wakes then re-derive marks. Worker cycles do this every few minutes
while EDGE is frozen. Merge last rich sidecar + rth_eval_marks_latest.json
back onto the current working order ids.

Never places, never arms, never touches hypotheses.yaml.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_SEED = _REPO / "reports" / "bootstrap" / "NEXT_SEED.json"
DEFAULT_MARKS = _REPO / ".cache" / "platform" / "rth_eval_marks_latest.json"
DEFAULT_SIDECAR = _REPO / ".cache" / "platform" / "rth_next_seed_rich.json"

ORDER_MARK_KEYS = (
    "decision",
    "spot",
    "mtm_usd",
    "mtm_adverse_usd",
    "pt_usd",
    "dual_pt_ready",
    "put_otm",
    "call_otm",
    "short_put_delta",
    "short_call_delta",
)
DETAIL_HUNT_KEYS = ("f_ic", "pack", "closed_this_session", "hunt")
PACK_DOOR_ACTIONS = {"monday_pack_open_on_bullish_bar"}


def seed_has_pack_door(seed: dict[str, Any] | None) -> bool:
    """True when residue names the first-live bu_4/bu_6 consume seats."""
    if not isinstance(seed, dict):
        return False
    if str(seed.get("next_action") or "") in PACK_DOOR_ACTIONS:
        return True
    if str(seed.get("source") or "").startswith("offhours_pack"):
        return True
    detail_raw = seed.get("detail")
    detail = detail_raw if isinstance(detail_raw, dict) else {}
    pack_raw = detail.get("pack")
    pack = pack_raw if isinstance(pack_raw, dict) else {}
    return bool(pack.get("primary_seat") or pack.get("backup_seat"))


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def order_is_thin(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return True
    return not any(order.get(k) is not None for k in ("mtm_usd", "decision", "dual_pt_ready", "spot"))


def seed_is_thin(seed: dict[str, Any] | None) -> bool:
    """True when open working rows exist but carry no mark/hunt residue."""
    if not isinstance(seed, dict):
        return False
    raw_detail = seed.get("detail")
    detail: dict[str, Any] = raw_detail if isinstance(raw_detail, dict) else {}
    orders = list(detail.get("open_orders") or [])
    if not orders:
        return False
    hunt = any(detail.get(k) not in (None, {}, []) for k in DETAIL_HUNT_KEYS)
    if hunt:
        return False
    return all(order_is_thin(o) for o in orders if isinstance(o, dict))


def _marks_by_order(marks: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(marks, dict):
        return out
    for row in marks.get("marks") or []:
        if isinstance(row, dict) and row.get("order_id"):
            out[str(row["order_id"])] = row
    return out


def merge_preserved_seed(
    campaign: dict[str, Any],
    *,
    rich: dict[str, Any] | None = None,
    marks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Overlay last RTH marks/hunt onto the current campaign working book."""
    camp = dict(campaign)
    camp_detail = dict(camp.get("detail") or {}) if isinstance(camp.get("detail"), dict) else {}
    rich = rich if isinstance(rich, dict) else {}
    rich_detail = dict(rich.get("detail") or {}) if isinstance(rich.get("detail"), dict) else {}
    rich_by_id = {
        str(o["order_id"]): o
        for o in (rich_detail.get("open_orders") or [])
        if isinstance(o, dict) and o.get("order_id")
    }
    mark_by_id = _marks_by_order(marks)

    merged_orders: list[dict[str, Any]] = []
    for raw in camp_detail.get("open_orders") or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        oid = str(row.get("order_id") or "")
        if oid and oid in rich_by_id:
            for key in ORDER_MARK_KEYS:
                if rich_by_id[oid].get(key) is not None:
                    row[key] = rich_by_id[oid][key]
        if oid and oid in mark_by_id:
            src = mark_by_id[oid]
            for key in ORDER_MARK_KEYS:
                if src.get(key) is not None:
                    row[key] = src[key]
        merged_orders.append(row)

    detail = dict(camp_detail)
    if merged_orders:
        detail["open_orders"] = merged_orders
    for key in DETAIL_HUNT_KEYS:
        rich_val = rich_detail.get(key)
        if rich_val in (None, {}, []):
            continue
        living_val = detail.get(key)
        if living_val in (None, {}, []):
            detail[key] = rich_val
            continue
        if key == "pack" and seed_has_pack_door({"detail": {"pack": rich_val}}) and not seed_has_pack_door(
            {"detail": {"pack": living_val}}
        ):
            detail[key] = rich_val
    hint = str(camp_detail.get("hint") or "")
    rich_hint = str(rich_detail.get("hint") or "")
    if rich_hint and (
        not hint
        or hint.startswith("RTH: mark/manage paper")
        or (seed_has_pack_door(rich) and not seed_has_pack_door(camp))
    ):
        detail["hint"] = rich_hint

    out = dict(camp)
    out["detail"] = detail
    if seed_has_pack_door(rich) and not seed_has_pack_door(camp):
        if rich.get("next_action"):
            out["next_action"] = rich["next_action"]
        if str(rich.get("source") or "").startswith("offhours_pack"):
            out["source"] = rich["source"]
            if rich.get("stamp"):
                out["stamp"] = rich["stamp"]
    restored = bool(merged_orders) and not all(order_is_thin(o) for o in merged_orders)
    if restored:
        src = str(rich.get("source") or "")
        if src.startswith("rth_eval") or src.startswith("continuum_judgment"):
            out["source"] = src
            if rich.get("stamp"):
                out["stamp"] = rich["stamp"]
        out["preserved_from"] = "trader_preserve_rth_next_seed"
        out["ken_required"] = False
        out["trading_authority"] = False
        out["live_authority"] = False
    return out


def apply_preserve(
    *,
    seed_path: Path = DEFAULT_SEED,
    marks_path: Path = DEFAULT_MARKS,
    sidecar_path: Path = DEFAULT_SIDECAR,
) -> dict[str, Any]:
    seed = _load(seed_path)
    marks = _load(marks_path)
    sidecar = _load(sidecar_path)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if seed and not seed_is_thin(seed):
        if seed_has_pack_door(sidecar) and not seed_has_pack_door(seed):
            merged = merge_preserved_seed(seed, rich=sidecar, marks=marks)
            seed_path.parent.mkdir(parents=True, exist_ok=True)
            seed_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
            return {
                "action": "restored_pack_door",
                "thin": False,
                "seed_path": str(seed_path),
                "sidecar_path": str(sidecar_path),
                "source": merged.get("source"),
            }
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(seed)
        payload["sidecar_saved_at"] = now
        sidecar_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return {
            "action": "sidecar_refresh",
            "thin": False,
            "seed_path": str(seed_path),
            "sidecar_path": str(sidecar_path),
        }

    if not seed:
        return {"action": "skip", "reason": "missing_seed", "seed_path": str(seed_path)}

    merged = merge_preserved_seed(seed, rich=sidecar, marks=marks)
    if seed_is_thin(merged):
        return {
            "action": "unchanged_still_thin",
            "thin": True,
            "seed_path": str(seed_path),
            "had_sidecar": bool(sidecar),
            "had_marks": bool(_marks_by_order(marks)),
        }

    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_blob = dict(merged)
    sidecar_blob["sidecar_saved_at"] = now
    sidecar_path.write_text(json.dumps(sidecar_blob, indent=2) + "\n", encoding="utf-8")
    return {
        "action": "restored",
        "thin": False,
        "seed_path": str(seed_path),
        "source": merged.get("source"),
        "n_open": len((merged.get("detail") or {}).get("open_orders") or []),
    }

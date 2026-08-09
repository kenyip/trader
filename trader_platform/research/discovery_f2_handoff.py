"""Discovery F2 → pack-grade reprove handoff.

Scans discovery marathon prove_evals and writes a loadable candidate surface
that multi-symbol reprove can include. Closes the handoff gap where new-axis
F2 survivors lived only under .cache and never entered MULTI_SYMBOL_REPROVE.

Honesty:
- Discovery F2 is NOT B3/B4 capital_path_ok and NOT live edge.
- pack_grade_shaped means ≥2 thick dual-cost holdout symbols in the prove_eval;
  official pack-grade still requires multi_symbol_reprove quality_pass.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_DISCOVERY_ROOT = _REPO / ".cache" / "platform" / "spine" / "discovery"
DEFAULT_OUT = _REPO / "reports" / "bootstrap" / "DISCOVERY_F2_CANDIDATES.json"

_AXIS_RE = re.compile(r"(?:^|__)((?:dn|g)_d[57])(?:_|$)", re.IGNORECASE)
_F2_DECISIONS = frozenset(
    {
        "STRATEGY_ADVANCED_F2",
        "F2_UNTOUCHED_HOLDOUT",
        "STRATEGY_ADVANCED",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    return path


def axis_markers(candidate_id: str) -> list[str]:
    found = [m.group(1).lower() for m in _AXIS_RE.finditer(str(candidate_id or ""))]
    # stable unique order
    out: list[str] = []
    for m in found:
        if m not in out:
            out.append(m)
    return out


def _worst_axis_n_trades(holdout: Mapping[str, Any] | None) -> int:
    if not isinstance(holdout, Mapping):
        return 0
    ns: list[int] = []
    for key in ("fixed_0p01", "slip_5pct"):
        block = holdout.get(key) or {}
        if not isinstance(block, Mapping):
            continue
        try:
            n = int(block.get("n_trades") or 0)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            ns.append(n)
    return min(ns) if ns else 0


def thick_dual_cost_symbols(
    prove_eval: Mapping[str, Any],
    *,
    min_trades_worst_axis: int = 12,
) -> list[str]:
    """Symbols that pass holdout dual-cost with thick enough worst-axis trades."""
    out: list[str] = []
    for row in prove_eval.get("holdout_rows") or []:
        if not isinstance(row, Mapping):
            continue
        if not row.get("holdout_dual_cost_pass"):
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if _worst_axis_n_trades(row.get("holdout")) < int(min_trades_worst_axis):
            continue
        if sym not in out:
            out.append(sym)
    return out


def is_f2_admit(prove_eval: Mapping[str, Any]) -> bool:
    decision = str(prove_eval.get("decision") or "").strip().upper()
    stage = str(prove_eval.get("funnel_stage_after") or "").strip().upper()
    if decision in _F2_DECISIONS or decision.endswith("_F2"):
        return True
    if stage == "F2_UNTOUCHED_HOLDOUT" or stage.startswith("F2_"):
        return True
    return False


def resolve_spec_path(prove_eval_path: Path, prove_eval: Mapping[str, Any]) -> Path | None:
    """Prefer sibling __prove.json, then __screen.json, then payload paths."""
    name = prove_eval_path.name
    parent = prove_eval_path.parent
    if name.endswith("__prove_eval.json"):
        stem = name[: -len("__prove_eval.json")]
        for suffix in ("__prove.json", "__screen.json"):
            cand = parent / f"{stem}{suffix}"
            if cand.is_file():
                return cand.resolve()
    for key in ("spec_path", "prove_spec_path", "source_spec_path"):
        raw = prove_eval.get(key)
        if raw and Path(str(raw)).is_file():
            return Path(str(raw)).resolve()
    return None


def candidate_from_prove_eval(
    prove_eval_path: Path,
    prove_eval: Mapping[str, Any],
    *,
    min_trades_worst_axis: int = 12,
    min_dual_cost_symbols: int = 1,
) -> dict[str, Any] | None:
    if not is_f2_admit(prove_eval):
        return None
    symbols = thick_dual_cost_symbols(
        prove_eval, min_trades_worst_axis=min_trades_worst_axis
    )
    if len(symbols) < int(min_dual_cost_symbols):
        return None
    spec = resolve_spec_path(prove_eval_path, prove_eval)
    if spec is None:
        return None
    cid = str(prove_eval.get("candidate_id") or prove_eval_path.stem).strip()
    if not cid:
        return None
    markers = axis_markers(cid)
    pack_shaped = len(symbols) >= 2
    return {
        "candidate_id": cid,
        "family_id": prove_eval.get("family_id"),
        "spec_path": str(spec),
        "prove_eval_path": str(prove_eval_path.resolve()),
        "symbols_proved": symbols,
        "n_holdout_pass": int(prove_eval.get("n_holdout_pass") or len(symbols)),
        "funnel_stage_after": prove_eval.get("funnel_stage_after"),
        "decision": prove_eval.get("decision"),
        "generated_at": prove_eval.get("generated_at"),
        "source": "discovery_prove_eval",
        "axis_markers": markers,
        "new_axis": bool(markers),
        "pack_grade_shaped": pack_shaped,
        "capital_path_ok": False,
        "live_authority": False,
        "trading_authority": False,
        "honesty": (
            "Discovery F2 prove_eval handoff only. Not B3/B4 capital_path_ok; "
            "not pack-grade until multi_symbol_reprove quality_pass; not live."
        ),
    }


def _parse_ts(value: Any) -> str:
    return str(value or "")


def scan_discovery_f2_candidates(
    discovery_root: str | Path | None = None,
    *,
    min_generated_at: str | None = "2026-08-05",
    require_f2: bool = True,
    min_dual_cost_symbols: int = 1,
    min_trades_worst_axis: int = 12,
) -> list[dict[str, Any]]:
    root = Path(discovery_root) if discovery_root else DEFAULT_DISCOVERY_ROOT
    if not root.is_dir():
        return []
    by_id: dict[str, dict[str, Any]] = {}
    for path in root.glob("**/gen_*/**/*__prove_eval.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if require_f2 and not is_f2_admit(data):
            continue
        gen_at = _parse_ts(data.get("generated_at"))
        if min_generated_at and gen_at and gen_at < str(min_generated_at):
            continue
        row = candidate_from_prove_eval(
            path,
            data,
            min_trades_worst_axis=min_trades_worst_axis,
            min_dual_cost_symbols=min_dual_cost_symbols,
        )
        if row is None:
            continue
        cid = str(row["candidate_id"])
        prev = by_id.get(cid)
        if prev is None:
            by_id[cid] = row
            continue
        # Prefer more thick symbols, then newer generated_at
        prev_n = len(prev.get("symbols_proved") or [])
        cur_n = len(row.get("symbols_proved") or [])
        if cur_n > prev_n or (
            cur_n == prev_n and _parse_ts(row.get("generated_at")) > _parse_ts(prev.get("generated_at"))
        ):
            by_id[cid] = row
    rows = list(by_id.values())
    rows.sort(
        key=lambda r: (
            0 if r.get("pack_grade_shaped") else 1,
            0 if r.get("new_axis") else 1,
            -len(r.get("symbols_proved") or []),
            str(r.get("candidate_id") or ""),
        )
    )
    return rows


def write_discovery_f2_candidates(
    candidates: Sequence[Mapping[str, Any]],
    path: str | Path | None = None,
    *,
    discovery_root: str | Path | None = None,
) -> dict[str, Any]:
    out_path = Path(path) if path else DEFAULT_OUT
    rows = [dict(c) for c in candidates]
    payload = {
        "generated_at": _now(),
        "mode": "discovery_f2_handoff",
        "schema_version": 1,
        "discovery_root": str(Path(discovery_root) if discovery_root else DEFAULT_DISCOVERY_ROOT),
        "n_candidates": len(rows),
        "n_pack_grade_shaped": sum(1 for r in rows if r.get("pack_grade_shaped")),
        "n_new_axis": sum(1 for r in rows if r.get("new_axis")),
        "candidates": rows,
        "capital_path_ok": False,
        "live_authority": False,
        "trading_authority": False,
        "honesty": (
            "Loadable discovery F2 surface for multi-symbol reprove. "
            "Does not grant capital_path_ok, paper/live, or pack-grade by itself."
        ),
    }
    write_path = _atomic_write_json(out_path, payload)
    payload["report_path"] = str(write_path)
    return payload


def ingest_discovery_f2(
    *,
    discovery_root: str | Path | None = None,
    out_path: str | Path | None = None,
    min_generated_at: str | None = "2026-08-05",
    min_dual_cost_symbols: int = 1,
    min_trades_worst_axis: int = 12,
) -> dict[str, Any]:
    root = Path(discovery_root) if discovery_root else DEFAULT_DISCOVERY_ROOT
    rows = scan_discovery_f2_candidates(
        root,
        min_generated_at=min_generated_at,
        min_dual_cost_symbols=min_dual_cost_symbols,
        min_trades_worst_axis=min_trades_worst_axis,
    )
    return write_discovery_f2_candidates(rows, out_path, discovery_root=root)


def load_discovery_f2_items(
    path: str | Path | None = None,
    *,
    pack_grade_shaped_only: bool = False,
    new_axis_only: bool = False,
    max_n: int | None = None,
) -> list[dict[str, Any]]:
    p = Path(path) if path else DEFAULT_OUT
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for row in data.get("candidates") or []:
        if not isinstance(row, Mapping):
            continue
        if pack_grade_shaped_only and not row.get("pack_grade_shaped"):
            continue
        if new_axis_only and not row.get("new_axis"):
            continue
        sp = str(row.get("spec_path") or "")
        cid = str(row.get("candidate_id") or "")
        if not cid or not sp or not Path(sp).is_file():
            continue
        items.append(
            {
                "candidate_id": cid,
                "family_id": row.get("family_id"),
                "spec_path": sp,
                "symbols": list(row.get("symbols_proved") or []),
                "symbols_proved": list(row.get("symbols_proved") or []),
                "source": "discovery_f2",
                "pack_grade_shaped": bool(row.get("pack_grade_shaped")),
                "new_axis": bool(row.get("new_axis")),
                "axis_markers": list(row.get("axis_markers") or []),
                "prove_eval_path": row.get("prove_eval_path"),
            }
        )
        if max_n is not None and len(items) >= int(max_n):
            break
    return items

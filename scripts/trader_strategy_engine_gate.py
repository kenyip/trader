#!/usr/bin/env python3
"""Fail-closed handoff gate from Strategy Discovery Engine to Trader BUILD.

This gate intentionally does not run strategies. It validates a precomputed
Strategy Discovery Engine report and emits a compact handoff context for a new
MoA BUILD. Missing/no-qualified/unsafe reports block new autonomous BUILD
launches before a run branch is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_AUTHORITY_FALSE = ("paper", "shadow", "broker", "funding", "arm", "live", "l1")
FORBIDDEN_HOLDOUT_KEYS = {"event_return", "control_return", "metrics", "pnl", "return", "returns"}
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
DEFAULT_MAX_REPORT_AGE_SECONDS = 6 * 60 * 60
DEFAULT_MAX_REPORT_FUTURE_SKEW_SECONDS = 5 * 60


class StrategyEngineGateError(RuntimeError):
    """Raised for fail-closed handoff rejection."""


class StrategyEngineNoQualified(StrategyEngineGateError):
    """Raised when the engine explicitly reports no qualified strategy."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StrategyEngineGateError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StrategyEngineGateError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StrategyEngineGateError(f"JSON root must be object: {path}")
    return data


def _repo_path(repo: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo / path
    return path


def load_config(repo: Path, config_path: str | None = None) -> dict[str, Any]:
    path = _repo_path(repo, config_path or "configs/strategy_engine_handoff.json")
    cfg = _load_json(path)
    cfg.setdefault("schema_version", 1)
    cfg.setdefault("required_for_new_build", True)
    cfg.setdefault("allowed_statuses", ["NEXT_SURVIVOR"])
    cfg.setdefault("block_statuses", ["NO_QUALIFIED_STRATEGY"])
    cfg.setdefault("report_schema_version", 1)
    cfg.setdefault("require_provenance", True)
    cfg.setdefault("max_report_age_seconds", DEFAULT_MAX_REPORT_AGE_SECONDS)
    cfg.setdefault("max_report_future_skew_seconds", DEFAULT_MAX_REPORT_FUTURE_SKEW_SECONDS)
    cfg["_config_path"] = str(path)
    return cfg


def _parse_generated_at(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise StrategyEngineGateError("strategy engine report missing generated_at timestamp")
    raw = value.strip()
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise StrategyEngineGateError(f"generated_at is not ISO-8601: {raw!r}") from exc
    if dt.tzinfo is None:
        raise StrategyEngineGateError("generated_at must include timezone")
    return dt.astimezone(timezone.utc)


def _require_hex64(report: dict[str, Any], key: str) -> None:
    value = report.get(key)
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
        raise StrategyEngineGateError(f"strategy engine report {key} must be sha256 hex")


def _require_git_sha(report: dict[str, Any], key: str) -> None:
    value = report.get(key)
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise StrategyEngineGateError(f"strategy engine report {key} must be git sha")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_sha(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise StrategyEngineGateError(
            f"could not read git sha for {repo}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _git_dirty(repo: Path) -> bool:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise StrategyEngineGateError(
            f"could not read git status for {repo}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return bool(proc.stdout.strip())


def _provenance_path(report: dict[str, Any], key: str) -> Path | None:
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        return None
    value = provenance.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).expanduser()


def validate_report_provenance(report: dict[str, Any], cfg: dict[str, Any], *, now: datetime | None = None) -> None:
    """Reject stale or untraceable handoff reports before status handling."""
    if not cfg.get("require_provenance", True):
        return
    expected_schema = int(cfg.get("report_schema_version", 1))
    if report.get("schema_version") != expected_schema:
        raise StrategyEngineGateError(
            f"strategy engine report schema_version {report.get('schema_version')!r} != {expected_schema}"
        )
    generated_at = _parse_generated_at(report.get("generated_at"))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = (now - generated_at).total_seconds()
    max_age = int(cfg.get("max_report_age_seconds", DEFAULT_MAX_REPORT_AGE_SECONDS))
    if age > max_age:
        raise StrategyEngineGateError(
            f"strategy engine report stale: age_seconds={int(age)} max={max_age}"
        )
    future_skew = (generated_at - now).total_seconds()
    max_future = int(cfg.get("max_report_future_skew_seconds", DEFAULT_MAX_REPORT_FUTURE_SKEW_SECONDS))
    if future_skew > max_future:
        raise StrategyEngineGateError(
            f"strategy engine report generated_at is in the future: skew_seconds={int(future_skew)} max={max_future}"
        )
    _require_git_sha(report, "engine_git_sha")
    _require_git_sha(report, "trader_git_sha")
    _require_hex64(report, "manifest_sha256")
    _require_hex64(report, "panel_sha256")
    route_count = report.get("route_count")
    if not isinstance(route_count, int) or route_count < 1:
        raise StrategyEngineGateError("strategy engine report route_count must be positive integer")


def verify_report_provenance_sources(repo: Path, report: dict[str, Any], cfg: dict[str, Any]) -> None:
    """Reject reports that no longer match configured source repos/input files."""
    if not cfg.get("require_provenance", True):
        return
    engine_repo_value = cfg.get("engine_repo")
    if engine_repo_value:
        engine_repo = _repo_path(repo, str(engine_repo_value)).resolve()
        if not engine_repo.exists():
            raise StrategyEngineGateError(f"configured engine_repo does not exist: {engine_repo}")
        if _git_sha(engine_repo) != report.get("engine_git_sha"):
            raise StrategyEngineGateError(
                "strategy engine report engine_git_sha does not match configured engine repo HEAD"
            )
        if cfg.get("require_clean_engine_repo", True) and _git_dirty(engine_repo):
            raise StrategyEngineGateError("configured engine_repo has uncommitted changes")
    if _git_sha(repo) != report.get("trader_git_sha"):
        raise StrategyEngineGateError("strategy engine report trader_git_sha does not match Trader repo HEAD")
    for path_key, hash_key in (("routes_path", "manifest_sha256"), ("panel_path", "panel_sha256")):
        source_path = _provenance_path(report, path_key)
        if source_path is None:
            raise StrategyEngineGateError(f"strategy engine report provenance missing {path_key}")
        if not source_path.is_file():
            raise StrategyEngineGateError(f"strategy engine report provenance file missing: {source_path}")
        if _sha256_file(source_path) != report.get(hash_key):
            raise StrategyEngineGateError(f"strategy engine report {hash_key} does not match current {path_key}")


def _walk_holdout_forbidden(value: Any, path: str = "holdout") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_l = str(key).lower()
            child_path = f"{path}.{key}"
            if key_l in FORBIDDEN_HOLDOUT_KEYS:
                findings.append(child_path)
            findings.extend(_walk_holdout_forbidden(child, child_path))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            findings.extend(_walk_holdout_forbidden(child, f"{path}[{i}]"))
    return findings


def validate_report(report: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    status = str(report.get("status", ""))
    authority = report.get("authority")
    if not isinstance(authority, dict):
        raise StrategyEngineGateError("strategy engine report missing authority object")
    bad_auth = [key for key in EXPECTED_AUTHORITY_FALSE if authority.get(key) is not False]
    if bad_auth:
        raise StrategyEngineGateError(f"authority firewall not false for: {', '.join(bad_auth)}")

    if status in set(cfg.get("block_statuses") or []):
        raise StrategyEngineNoQualified(f"strategy engine reported {status}; do not launch BUILD")
    if status not in set(cfg.get("allowed_statuses") or []):
        raise StrategyEngineGateError(
            f"strategy engine status {status!r} not allowed; expected {cfg.get('allowed_statuses')}"
        )

    survivors = report.get("survivors")
    if not isinstance(survivors, list) or not survivors:
        raise StrategyEngineGateError("NEXT_SURVIVOR report must contain at least one survivor")

    selected = survivors[0]
    if not isinstance(selected, dict):
        raise StrategyEngineGateError("first survivor must be an object")
    if selected.get("status") not in {"F1_TRAIN_SURVIVOR", "F1", "TRAIN_SURVIVOR"}:
        raise StrategyEngineGateError(
            f"first survivor has unexpected status: {selected.get('status')!r}"
        )
    holdout = selected.get("holdout")
    if not isinstance(holdout, dict):
        raise StrategyEngineGateError("selected survivor missing sealed holdout object")
    if not holdout.get("identity_hash"):
        raise StrategyEngineGateError("sealed holdout missing identity_hash")
    forbidden = _walk_holdout_forbidden(holdout)
    if forbidden:
        raise StrategyEngineGateError(
            "sealed holdout contains forbidden outcome fields: " + ", ".join(forbidden)
        )

    promotion_blocked = set(selected.get("promotion_blocked") or [])
    missing_blocks = [key for key in EXPECTED_AUTHORITY_FALSE if key not in promotion_blocked and key != "paper"]
    # Some engine reports use authority firewall as the canonical block list; require
    # at least l1/live/broker/funding/shadow/arm in survivor-level blocks.
    if missing_blocks:
        raise StrategyEngineGateError(
            "selected survivor missing promotion_blocked entries: " + ", ".join(missing_blocks)
        )

    return selected


def _safe_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "n_train_events",
        "event_mean_after_cost",
        "paired_excess_mean",
        "lower_bound",
        "hit_rate",
        "worst_decile_tail",
        "cost_per_event",
    )
    return {key: metrics[key] for key in keep if key in metrics}


def build_receipt(repo: Path, cfg: dict[str, Any], report_path: Path, report: dict[str, Any], selected: dict[str, Any], report_sha256: str, stamp: str) -> dict[str, Any]:
    holdout = selected.get("holdout") or {}
    return {
        "schema_version": 1,
        "stamp": stamp,
        "gate": "STRATEGY_ENGINE_NEXT_SURVIVOR",
        "config_path": cfg.get("_config_path"),
        "engine_repo": cfg.get("engine_repo"),
        "report_path": str(report_path),
        "report_sha256": report_sha256,
        "report_status": report.get("status"),
        "engine_version": report.get("engine_version"),
        "authority": report.get("authority"),
        "selected": {
            "route_id": selected.get("route_id"),
            "family": selected.get("family"),
            "status": selected.get("status"),
            "rank": selected.get("rank"),
            "evidence_class": selected.get("evidence_class"),
            "metrics": _safe_metrics(selected.get("metrics") or {}),
            "holdout": {
                "event_count": holdout.get("event_count"),
                "control_count": holdout.get("control_count"),
                "identity_hash": holdout.get("identity_hash"),
                "dates": holdout.get("dates", []),
                "symbols": holdout.get("symbols", []),
            },
            "promotion_blocked": selected.get("promotion_blocked") or [],
        },
        "authority_statement": "research handoff only; no L1/paper/shadow/broker/funding/arm/live authority",
    }


def render_context(receipt: dict[str, Any]) -> str:
    selected = receipt["selected"]
    metrics = selected.get("metrics") or {}
    holdout = selected.get("holdout") or {}
    lines = [
        "# Strategy Engine Handoff",
        "",
        "This new BUILD launch passed the Strategy Discovery Engine handoff gate.",
        "The engine supplies a train-only F0 survivor for deeper Trader reasoning; it does not grant L1, paper, shadow, broker, funding, arm, or live authority.",
        "",
        f"- Report status: `{receipt['report_status']}`",
        f"- Report path: `{receipt['report_path']}`",
        f"- Report sha256: `{receipt['report_sha256']}`",
        f"- Selected route: `{selected.get('route_id')}`",
        f"- Family: `{selected.get('family')}`",
        f"- Survivor status: `{selected.get('status')}`",
        f"- Evidence class: `{selected.get('evidence_class')}`",
        "- Authority: research handoff only; all execution authority remains false.",
        "",
        "## Train-only metrics",
    ]
    if metrics:
        for key in sorted(metrics):
            lines.append(f"- {key}: `{metrics[key]}`")
    else:
        lines.append("- No metrics supplied; executor must fail closed if claim depends on missing metrics.")
    lines.extend([
        "",
        "## Sealed holdout identity only",
        f"- event_count: `{holdout.get('event_count')}`",
        f"- control_count: `{holdout.get('control_count')}`",
        f"- identity_hash: `{holdout.get('identity_hash')}`",
        f"- symbols: `{holdout.get('symbols')}`",
        f"- dates: `{holdout.get('dates')}`",
        "- Forbidden here: holdout outcomes, returns, pnl, or metrics.",
        "",
        "## Executor instruction",
        "Start from this selected survivor unless you find a claim-invalidating defect. If rejecting it, close that reason explicitly before choosing another independent route; do not rerun adjacent variants of a closed family. Proxy/underlying F0 evidence can support only a discovery claim and cannot earn L1 or paper authority.",
    ])
    return "\n".join(lines) + "\n"


def run_gate(repo: Path, stamp: str, config_path: str | None, out_context: Path | None, out_json: Path | None) -> dict[str, Any]:
    cfg = load_config(repo, config_path)
    if not cfg.get("required_for_new_build", True):
        raise StrategyEngineGateError("strategy engine handoff is disabled; fail closed for new BUILD")

    engine_repo = cfg.get("engine_repo")
    if engine_repo and not _repo_path(repo, str(engine_repo)).exists():
        raise StrategyEngineGateError(f"configured engine_repo does not exist: {engine_repo}")

    report_value = cfg.get("report_path")
    if not report_value:
        raise StrategyEngineGateError("config missing report_path")
    report_path = _repo_path(repo, str(report_value))
    report_bytes = report_path.read_bytes() if report_path.exists() else None
    if report_bytes is None:
        raise StrategyEngineGateError(
            f"strategy engine report missing: {report_path}; run the strategy engine and write a current report before launching BUILD"
        )
    report = json.loads(report_bytes.decode("utf-8"))
    if not isinstance(report, dict):
        raise StrategyEngineGateError("strategy engine report root must be object")
    validate_report_provenance(report, cfg)
    verify_report_provenance_sources(repo, report, cfg)
    selected = validate_report(report, cfg)
    receipt = build_receipt(
        repo=repo,
        cfg=cfg,
        report_path=report_path,
        report=report,
        selected=selected,
        report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        stamp=stamp,
    )
    if out_context:
        out_context.parent.mkdir(parents=True, exist_ok=True)
        out_context.write_text(render_context(receipt), encoding="utf-8")
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def write_no_strategy_receipt(stamp: str, message: str, out_context: Path | None, out_json: Path | None) -> None:
    receipt = {
        "schema_version": 1,
        "stamp": stamp,
        "gate": "NO_STRATEGY_STATUS",
        "status": "NO_QUALIFIED_STRATEGY",
        "message": message,
        "launch_allowed": False,
        "authority_statement": "research no-op; no L1/paper/shadow/broker/funding/arm/live authority",
    }
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_context:
        out_context.parent.mkdir(parents=True, exist_ok=True)
        out_context.write_text(
            "# Strategy Engine Handoff: NO_QUALIFIED_STRATEGY\n\n"
            + "The Strategy Discovery Engine found no qualified survivor. Trader BUILD launch is intentionally skipped; this is a safe no-strategy no-op, not a RUN INCOMPLETE.\n\n"
            + "- Authority: no L1, paper, shadow, broker, funding, arm, or live authority.\n"
            + f"- Detail: {message}\n",
            encoding="utf-8",
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".", help="Trader repo root")
    ap.add_argument("--stamp", required=True, help="BUILD stamp receiving the handoff")
    ap.add_argument("--config", default=None, help="strategy_engine_handoff.json path")
    ap.add_argument("--out-context", default=None, help="write markdown context here")
    ap.add_argument("--out-json", default=None, help="write machine receipt here")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        receipt = run_gate(
            repo=repo,
            stamp=args.stamp,
            config_path=args.config,
            out_context=Path(args.out_context).expanduser() if args.out_context else None,
            out_json=Path(args.out_json).expanduser() if args.out_json else None,
        )
    except StrategyEngineNoQualified as exc:
        out_context = Path(args.out_context).expanduser() if args.out_context else None
        out_json = Path(args.out_json).expanduser() if args.out_json else None
        write_no_strategy_receipt(args.stamp, str(exc), out_context, out_json)
        print(f"NO_STRATEGY_STATUS: NO_QUALIFIED_STRATEGY — {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, StrategyEngineGateError) as exc:
        print(f"STRATEGY_ENGINE_GATE_FAILED: {exc}", file=sys.stderr)
        return 3
    print(json.dumps({"ok": True, "gate": receipt["gate"], "route_id": receipt["selected"].get("route_id")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

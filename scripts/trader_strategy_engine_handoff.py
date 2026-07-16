#!/usr/bin/env python3
"""Run Strategy Discovery Engine and install a provenance-stamped Trader handoff.

This script is the safe bridge between the separate `trader-strategy-engine`
repo and Trader. It does not launch BUILD, place orders, touch broker/paper
state, or grant authority. It only runs the engine, stamps source provenance,
writes `.cache/strategy-engine/latest.json`, and validates that Trader's gate can
interpret the report.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.trader_strategy_engine_gate import (
    StrategyEngineGateError,
    StrategyEngineNoQualified,
    _repo_path,
    load_config,
    run_gate,
    validate_report,
    validate_report_provenance,
    verify_report_provenance_sources,
)


def _sha256_file(path: Path) -> str:
    import hashlib

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


def _route_count(routes_path: Path) -> int:
    try:
        data = json.loads(routes_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StrategyEngineGateError(f"routes manifest is not valid JSON: {exc}") from exc
    routes = data.get("routes") if isinstance(data, dict) else None
    if not isinstance(routes, list) or not routes:
        raise StrategyEngineGateError("routes manifest must contain a non-empty routes list")
    return len(routes)


def _resolve_input(repo: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo / path
    return path.resolve()


def _run_engine(engine_repo: Path, routes_path: Path, panel_path: Path, out_path: Path) -> None:
    env = os.environ.copy()
    src = str(engine_repo / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "strategy_engine.cli",
            "--routes",
            str(routes_path),
            "--panel",
            str(panel_path),
            "--out",
            str(out_path),
        ],
        cwd=engine_repo,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise StrategyEngineGateError(
            "strategy engine CLI failed: "
            + (proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
        )


def build_handoff_report(
    *,
    repo: Path,
    cfg: dict[str, Any],
    routes_path: Path,
    panel_path: Path,
    engine_report: dict[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Return an engine report augmented with Trader-required provenance."""
    engine_repo_value = cfg.get("engine_repo")
    if not engine_repo_value:
        raise StrategyEngineGateError("config missing engine_repo")
    engine_repo = _repo_path(repo, str(engine_repo_value)).resolve()
    if not engine_repo.exists():
        raise StrategyEngineGateError(f"configured engine_repo does not exist: {engine_repo}")

    generated_at = generated_at or datetime.now(timezone.utc)
    report = dict(engine_report)
    report["schema_version"] = int(cfg.get("report_schema_version", 1))
    report["generated_at"] = generated_at.isoformat().replace("+00:00", "Z")
    report["engine_git_sha"] = _git_sha(engine_repo)
    report["trader_git_sha"] = _git_sha(repo)
    report["manifest_sha256"] = _sha256_file(routes_path)
    report["panel_sha256"] = _sha256_file(panel_path)
    report["route_count"] = _route_count(routes_path)
    report["provenance"] = {
        "producer": "scripts/trader_strategy_engine_handoff.py",
        "engine_repo_config": engine_repo_value,
        "routes_path": str(routes_path),
        "panel_path": str(panel_path),
    }
    return report


def run_handoff(
    repo: Path,
    routes: str,
    panel: str,
    config_path: str | None,
    stamp: str,
    validate: bool = True,
) -> dict[str, Any]:
    repo = repo.resolve()
    cfg = load_config(repo, config_path)
    engine_repo_value = cfg.get("engine_repo")
    if not engine_repo_value:
        raise StrategyEngineGateError("config missing engine_repo")
    engine_repo = _repo_path(repo, str(engine_repo_value)).resolve()
    if not engine_repo.exists():
        raise StrategyEngineGateError(f"configured engine_repo does not exist: {engine_repo}")

    routes_path = _resolve_input(repo, routes)
    panel_path = _resolve_input(repo, panel)
    if not routes_path.exists():
        raise StrategyEngineGateError(f"routes manifest missing: {routes_path}")
    if not panel_path.exists():
        raise StrategyEngineGateError(f"panel CSV missing: {panel_path}")

    out_value = cfg.get("report_path")
    if not out_value:
        raise StrategyEngineGateError("config missing report_path")
    final_report_path = _repo_path(repo, str(out_value))

    routes_hash_before = _sha256_file(routes_path)
    panel_hash_before = _sha256_file(panel_path)
    with tempfile.TemporaryDirectory(prefix="strategy-engine-handoff-") as td:
        tmp_out = Path(td) / "engine-report.json"
        _run_engine(engine_repo, routes_path, panel_path, tmp_out)
        engine_report = json.loads(tmp_out.read_text(encoding="utf-8"))
        if not isinstance(engine_report, dict):
            raise StrategyEngineGateError("engine report root must be object")
    if _sha256_file(routes_path) != routes_hash_before:
        raise StrategyEngineGateError("routes manifest changed while strategy engine was running")
    if _sha256_file(panel_path) != panel_hash_before:
        raise StrategyEngineGateError("panel CSV changed while strategy engine was running")

    handoff_report = build_handoff_report(
        repo=repo,
        cfg=cfg,
        routes_path=routes_path,
        panel_path=panel_path,
        engine_report=engine_report,
    )
    validate_report_provenance(handoff_report, cfg)
    verify_report_provenance_sources(repo, handoff_report, cfg)
    try:
        validate_report(handoff_report, cfg)
    except StrategyEngineNoQualified:
        pass

    final_report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(handoff_report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=final_report_path.parent,
        prefix=f".{final_report_path.name}.",
        delete=False,
    ) as handle:
        handle.write(payload)
        tmp_report = Path(handle.name)
    os.replace(tmp_report, final_report_path)

    gate_status = "not_validated"
    if validate:
        try:
            run_gate(repo, stamp, config_path, None, None)
            gate_status = "validated_next_survivor"
        except StrategyEngineNoQualified:
            gate_status = "validated_no_qualified_strategy"

    return {
        "ok": True,
        "status": handoff_report.get("status"),
        "gate_status": gate_status,
        "report_path": str(final_report_path),
        "route_count": handoff_report.get("route_count"),
        "manifest_sha256": handoff_report.get("manifest_sha256"),
        "panel_sha256": handoff_report.get("panel_sha256"),
        "engine_git_sha": handoff_report.get("engine_git_sha"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".", help="Trader repo root")
    ap.add_argument("--routes", required=True, help="Route manifest JSON path; relative paths resolve under Trader repo")
    ap.add_argument("--panel", required=True, help="Panel CSV path; relative paths resolve under Trader repo")
    ap.add_argument("--config", default=None, help="strategy_engine_handoff.json path")
    ap.add_argument("--stamp", default="handoff", help="Validation stamp used only for gate context")
    ap.add_argument("--no-validate", action="store_true", help="write report without running Trader gate validation")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        receipt = run_handoff(
            repo=Path(args.repo),
            routes=args.routes,
            panel=args.panel,
            config_path=args.config,
            stamp=args.stamp,
            validate=not args.no_validate,
        )
    except (OSError, ValueError, StrategyEngineGateError) as exc:
        print(f"STRATEGY_ENGINE_HANDOFF_FAILED: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

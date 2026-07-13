#!/usr/bin/env python3
"""Build and validate cumulative learning state for zero-input Trader BUILD wakes."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DELTA_KINDS = {"candidate", "falsification", "capability", "repair", "evidence", "stop_rule"}
OUTCOMES = {"CANDIDATE", "FALSIFIED", "CAPABILITY", "REPAIRED", "DIMINISHING_RETURNS"}

HISTORICAL_SIM_MODULES = (
    "trader_platform/research/pcs_sim.py",
    "trader_platform/research/calendar_sim.py",
    "trader_platform/research/diagonal_sim.py",
    "trader_platform/research/butterfly_sim.py",
    "trader_platform/research/debit_vertical_sim.py",
    "trader_platform/research/iron_butterfly_sim.py",
    "trader_platform/research/put_ratio_backspread_sim.py",
    "trader_platform/research/collar_sim.py",
)


class CompoundingError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompoundingError(f"cannot read valid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompoundingError(f"expected JSON object: {path}")
    return value


def _hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_path(repo: Path, value: str) -> Path:
    path = (repo / value).resolve()
    try:
        path.relative_to(repo.resolve())
    except ValueError as exc:
        raise CompoundingError(f"artifact escapes repository: {value}") from exc
    return path


def _tracked_on_origin_main(repo: Path, path: Path) -> bool:
    try:
        rel = str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return False
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", rel],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    sha = commit.stdout.strip()
    if commit.returncode or not sha:
        return False
    integrated = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, "origin/main"],
        cwd=repo,
        capture_output=True,
    )
    return integrated.returncode == 0


def _previous_records(repo: Path, current_stamp: str) -> list[dict[str, Any]]:
    root = repo / "reports" / "trader-wakes" / "moa"
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.glob("*/compounding.json")):
        if path.parent.name == current_stamp or not _tracked_on_origin_main(repo, path):
            continue
        try:
            row = _load(path)
        except CompoundingError:
            continue
        if row.get("schema_version") == SCHEMA_VERSION:
            rows.append(row)
    return rows


def assess_research_routes(repo: Path) -> dict[str, Any]:
    """Describe independent BUILD evidence routes without selecting strategy DNA.

    A forward option archive is one route. It must never mask executable historical
    underlying/proxy simulation or simulator-capability work.
    """
    cache = repo / ".cache"
    underlying_files = sorted(cache.glob("*_*.csv")) if cache.is_dir() else []
    historical_underlyings = [
        path for path in underlying_files
        if path.stem.rsplit("_", 1)[-1] in {"1y", "2y", "5y", "10y"}
    ]
    sim_modules = [path for value in HISTORICAL_SIM_MODULES if (path := repo / value).is_file()]

    archive_root = repo / ".cache" / "platform" / "option_quotes"
    archive_dates: dict[str, int] = {}
    if archive_root.is_dir():
        import csv

        for archive_path in sorted(archive_root.glob("*_archive.csv")):
            try:
                with archive_path.open(newline="", encoding="utf-8") as handle:
                    archive_dates[archive_path.stem.removesuffix("_archive")] = len(
                        {
                            datetime.fromisoformat(str(row["observed_at"]).replace("Z", "+00:00"))
                            .astimezone(ZoneInfo("America/New_York"))
                            .date()
                            .isoformat()
                            for row in csv.DictReader(handle)
                            if row.get("observed_at")
                        }
                    )
            except (OSError, ValueError):
                continue
    observed_market_dates = max(archive_dates.values(), default=0)
    plumbing_gate_met = observed_market_dates >= 3
    historical_proxy_executable = bool(historical_underlyings and sim_modules)
    routes = {
        "historical_underlying_proxy_discovery": {
            "executable": historical_proxy_executable,
            "historical_dataset_count": len(historical_underlyings),
            "simulator_count": len(sim_modules),
            "option_mark_provenance": "black_scholes_proxy",
            "claim_limit": "discovery/falsification only; cannot earn L1",
        },
        "observed_historical_option_replay": {
            "executable": False,
            "archive_market_dates_by_symbol": archive_dates,
            "maximum_observed_market_dates": observed_market_dates,
            "minimum_plumbing_dates": 3,
            "plumbing_gate_met": plumbing_gate_met,
            "blocked_reason": "no broad historical observed option surfaces with complete entry/exit joins",
            "claim_limit": (
                "three dates validate capture/join plumbing or begin cost calibration; "
                "they do not establish strategy edge or L1"
            ),
        },
        "simulator_capability_work": {
            "executable": bool(historical_underlyings),
            "claim_limit": "strategy-free capability/negative-control work",
        },
    }
    executable = [name for name, route in routes.items() if route["executable"]]
    return {
        "routes": routes,
        "executable_routes": executable,
        "global_build_blocked": not executable,
        "archive_density_alone_can_justify_diminishing_returns": False,
        "rule": (
            "A blocked observed-option route blocks only observed-option claims. Archive density alone cannot "
            "justify DIMINISHING_RETURNS while another independent route remains informative; honest "
            "information-exhaustion stops remain valid."
        ),
    }


def build_context(repo: Path, stamp: str, out: Path) -> dict[str, Any]:
    records = _previous_records(repo, stamp)
    closed = sorted(
        {
            str(family)
            for row in records
            for family in row.get("closed_families", [])
            if str(family).strip()
        }
    )
    recent = records[-5:]
    signatures = [str(row.get("loop_signature", "")) for row in recent]
    novelty = sorted(
        {
            str(delta.get("novelty_key"))
            for row in records
            for delta in row.get("useful_deltas", [])
            if isinstance(delta, dict) and delta.get("novelty_key")
        }
    )
    redirect_reasons: list[str] = []
    if records and records[-1].get("outcome") == "DIMINISHING_RETURNS":
        redirect_reasons.append("last completed wake declared DIMINISHING_RETURNS")
    if len(signatures) >= 2 and signatures[-1] and signatures[-1] == signatures[-2]:
        redirect_reasons.append(f"last two completed wakes repeated loop signature {signatures[-1]!r}")
    research_routes = assess_research_routes(repo)
    last = records[-1] if records else {}
    last_dependency_text = " ".join(
        [str(last.get("next", "")), *(str(value) for value in last.get("data_dependencies", []))]
    ).lower()
    archive_dependent_stop = bool(
        last.get("outcome") == "DIMINISHING_RETURNS"
        and any(token in last_dependency_text for token in ("archive", "observed option", "market date"))
    )
    independent_route_open = any(
        name != "observed_historical_option_replay" for name in research_routes["executable_routes"]
    )
    archive_stop_invalidated = archive_dependent_stop and independent_route_open
    if archive_stop_invalidated:
        redirect_reasons.append(
            "archive-dependent DIMINISHING_RETURNS is invalidated by an executable independent research route"
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "stamp": stamp,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "integrated prior compounding.json records",
        "prior_record_count": len(records),
        "closed_families": closed,
        "prior_novelty_keys": novelty,
        "recent_runs": [
            {
                "stamp": row.get("stamp"),
                "loop_signature": row.get("loop_signature"),
                "outcome": row.get("outcome"),
                "novelty_keys": [
                    delta.get("novelty_key")
                    for delta in row.get("useful_deltas", [])
                    if isinstance(delta, dict)
                ],
                "next": row.get("next"),
            }
            for row in recent
        ],
        "redirect_required": bool(redirect_reasons),
        "redirect_reasons": redirect_reasons,
        "research_routes": research_routes,
        "archive_dependent_stop_invalidated": archive_stop_invalidated,
        "choice_rule": (
            "Closed families and prior NEXT are context, not allowlists. Reopen only with a named "
            "new evidence class or repaired capability. A blocked observed-option route blocks only dependent "
            "claims and cannot alone justify DIMINISHING_RETURNS while another historical/capability route remains "
            "informative. Honest information-exhaustion stops remain valid after open routes are assessed for "
            "material novelty."
        ),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def snapshot(repo: Path, stamp: str, out: Path) -> dict[str, Any]:
    run = repo / "reports" / "trader-wakes" / "moa" / stamp
    paths = [run / "learning-promotion.md", run / "compounding.json"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "stamp": stamp,
        "files": {str(path.relative_to(repo)): _hash(path) for path in paths},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _changed_paths(repo: Path, base_head: str) -> set[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", base_head, "--"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    changed = {line for line in proc.stdout.splitlines() if line}
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, text=True, capture_output=True, check=True
    )
    for line in status.stdout.splitlines():
        if len(line) >= 4:
            changed.add(line[3:].split(" -> ")[-1])
    return changed


def validate(repo: Path, stamp: str, base_head: str, baseline: Path | None) -> dict[str, Any]:
    run = repo / "reports" / "trader-wakes" / "moa" / stamp
    handoff_path = run / "compounding.json"
    learning_path = run / "learning-promotion.md"
    handoff = _load(handoff_path)
    if handoff.get("schema_version") != SCHEMA_VERSION or handoff.get("stamp") != stamp:
        raise CompoundingError("compounding handoff schema/stamp mismatch")
    outcome = handoff.get("outcome")
    if outcome not in OUTCOMES:
        raise CompoundingError(f"invalid outcome: {outcome!r}")
    signature = str(handoff.get("loop_signature", "")).strip()
    if not signature:
        raise CompoundingError("loop_signature is required")
    next_seed = str(handoff.get("next", "")).strip()
    if not next_seed:
        raise CompoundingError("exactly one non-empty next value is required")
    deltas = handoff.get("useful_deltas")
    if not isinstance(deltas, list):
        raise CompoundingError("useful_deltas must be a list")
    diminishing = outcome == "DIMINISHING_RETURNS"
    if diminishing != (next_seed == "DIMINISHING_RETURNS"):
        raise CompoundingError("DIMINISHING_RETURNS outcome and next must agree")
    if not deltas and not diminishing:
        raise CompoundingError("non-diminishing wake requires at least one measurable useful delta")

    changed = _changed_paths(repo, base_head)
    novelty_keys: set[str] = set()
    for index, delta in enumerate(deltas):
        if not isinstance(delta, dict) or delta.get("kind") not in DELTA_KINDS:
            raise CompoundingError(f"useful_deltas[{index}] has invalid kind")
        summary = str(delta.get("summary", "")).strip()
        novelty = str(delta.get("novelty_key", "")).strip()
        artifacts = delta.get("artifacts")
        if not summary or not novelty or not isinstance(artifacts, list) or not artifacts:
            raise CompoundingError(f"useful_deltas[{index}] requires summary, novelty_key, artifacts")
        if novelty in novelty_keys:
            raise CompoundingError(f"duplicate novelty_key in handoff: {novelty}")
        novelty_keys.add(novelty)
        artifact_names = [str(value) for value in artifacts]
        for value in artifact_names:
            if not _relative_path(repo, value).is_file():
                raise CompoundingError(f"missing useful-delta artifact: {value}")
        if not any(value in changed for value in artifact_names):
            raise CompoundingError(f"useful delta has no artifact changed from base: {novelty}")
        if delta["kind"] in {"capability", "repair"}:
            machinery = [
                value for value in artifact_names
                if value.startswith(("scripts/", "trader_platform/"))
            ]
            tests = [value for value in artifact_names if value.startswith("tests/")]
            if not machinery:
                raise CompoundingError(f"{delta['kind']} delta requires a machinery artifact")
            if not tests:
                raise CompoundingError(f"{delta['kind']} delta requires a test artifact")
            if not any(value in changed for value in machinery):
                raise CompoundingError(f"{delta['kind']} delta requires changed machinery")
            if not any(value in changed for value in tests):
                raise CompoundingError(f"{delta['kind']} delta requires changed tests")

    findings = handoff.get("critic_findings", [])
    if not isinstance(findings, list):
        raise CompoundingError("critic_findings must be a list")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict) or finding.get("status") not in {"repaired", "rejected"}:
            raise CompoundingError(f"critic_findings[{index}] must be repaired or rejected")
        if not str(finding.get("finding", "")).strip() or not str(finding.get("rationale", "")).strip():
            raise CompoundingError(f"critic_findings[{index}] requires finding and rationale")
        if finding["status"] == "repaired":
            repairs = [str(v) for v in finding.get("repair_artifacts", [])]
            tests = [str(v) for v in finding.get("test_artifacts", [])]
            if not repairs or not tests:
                raise CompoundingError(f"critic_findings[{index}] repair lacks machinery/tests")
            if not all(_relative_path(repo, value).is_file() for value in repairs + tests):
                raise CompoundingError(f"critic_findings[{index}] cites missing repair/test artifact")
            if not all(value.startswith(("scripts/", "trader_platform/")) for value in repairs):
                raise CompoundingError(f"critic_findings[{index}] repair artifacts are not machinery")
            if not all(value.startswith("tests/") for value in tests):
                raise CompoundingError(f"critic_findings[{index}] test artifacts are not tests")
            if not any(value in changed for value in repairs):
                raise CompoundingError(f"critic_findings[{index}] machinery was not changed")
            if not any(value in changed for value in tests):
                raise CompoundingError(f"critic_findings[{index}] tests were not changed")

    previous = _previous_records(repo, stamp)
    prior_novelty = {
        str(delta.get("novelty_key"))
        for row in previous
        for delta in row.get("useful_deltas", [])
        if isinstance(delta, dict)
    }
    if deltas and novelty_keys.issubset(prior_novelty):
        raise CompoundingError("handoff claims no new novelty key versus integrated prior records")

    if not learning_path.is_file():
        raise CompoundingError("learning-promotion.md is required")
    learning = learning_path.read_text(encoding="utf-8")
    for heading in ("## VERIFICATION", "## DURABLE", "## LESSON", "## NEXT"):
        if heading not in learning:
            raise CompoundingError(f"learning-promotion.md missing {heading}")

    if baseline is not None:
        before = _load(baseline)
        files = before.get("files", {})
        for path in (learning_path, handoff_path):
            rel = str(path.relative_to(repo))
            if _hash(path) == files.get(rel):
                raise CompoundingError(f"finalizer did not materially write role artifact: {rel}")

    return {
        "ok": True,
        "mode": "validate-handoff",
        "stamp": stamp,
        "outcome": outcome,
        "loop_signature": signature,
        "useful_delta_count": len(deltas),
        "novelty_keys": sorted(novelty_keys),
        "critic_findings_closed": len(findings),
        "role_ready": True,
        "role_ready_basis": "validated changed learning + structured handoff; session text ignored",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    context = sub.add_parser("context")
    context.add_argument("--repo", default=".")
    context.add_argument("--stamp", required=True)
    context.add_argument("--out", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--repo", default=".")
    snap.add_argument("--stamp", required=True)
    snap.add_argument("--out", required=True)
    check = sub.add_parser("validate-handoff")
    check.add_argument("--repo", default=".")
    check.add_argument("--stamp", required=True)
    check.add_argument("--base-head", required=True)
    check.add_argument("--baseline")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    try:
        if args.mode == "context":
            result = build_context(repo, args.stamp, _relative_path(repo, args.out))
        elif args.mode == "snapshot":
            result = snapshot(repo, args.stamp, _relative_path(repo, args.out))
        else:
            baseline = _relative_path(repo, args.baseline) if args.baseline else None
            result = validate(repo, args.stamp, args.base_head, baseline)
    except (CompoundingError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "mode": args.mode, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

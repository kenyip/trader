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

# New finalizer handoffs must use schema 2. Historical schema-1 records remain
# readable for orientation/progress, but are never accepted as a new handoff.
SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
READABLE_SCHEMA_VERSIONS = {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}

DELTA_KINDS = {"candidate", "falsification", "capability", "repair", "evidence", "stop_rule"}
LEGACY_OUTCOMES = {"CANDIDATE", "FALSIFIED", "CAPABILITY", "REPAIRED", "DIMINISHING_RETURNS"}
STRATEGY_OUTCOMES = {
    "STRATEGY_ADVANCED",
    "FAMILY_CLOSED",
    "BLOCKER_REMOVED_AND_RETESTED",
    "EVIDENCE_WAIT",
}
OUTCOMES = STRATEGY_OUTCOMES  # new handoffs
FUNNEL_STAGES = (
    "F0_MECHANISM",
    "F1_TRAIN",
    "F2_UNTOUCHED_HOLDOUT",
    "F3_ROBUST_PAPER_PLAN",
    "F4_OBSERVED_PAPER",
)
FUNNEL_RANK = {name: index for index, name in enumerate(FUNNEL_STAGES)}
RETEST_DECISIONS = {"STRATEGY_ADVANCED", "FAMILY_CLOSED"}
EXPERIMENT_DELTA_KINDS = {"candidate", "falsification", "evidence"}
CAPABILITY_DELTA_KINDS = {"capability", "repair"}

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


SEARCH_EPOCH_PATH = Path("configs/search_epoch.json")


def load_search_epoch(repo: Path) -> dict[str, Any] | None:
    """Load optional active search epoch (anti-drift + streak scoping)."""
    path = repo / SEARCH_EPOCH_PATH
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    status = str(value.get("status") or "active").strip().lower()
    if status != "active":
        return None
    return value


def _epoch_started_stamp(epoch: dict[str, Any] | None) -> str | None:
    if not isinstance(epoch, dict):
        return None
    stamp = str(epoch.get("started_stamp") or "").strip()
    return stamp or None


def records_for_epoch(
    records: list[dict[str, Any]], epoch: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Return records at-or-after the active epoch started_stamp (exclusive prior history)."""
    started = _epoch_started_stamp(epoch)
    if not started:
        return list(records)
    scoped: list[dict[str, Any]] = []
    for row in records:
        stamp = str(row.get("stamp") or "").strip()
        if stamp and stamp >= started:
            scoped.append(row)
    return scoped


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
        if row.get("schema_version") in READABLE_SCHEMA_VERSIONS:
            rows.append(row)
    return rows


def strategy_advanced(row: dict[str, Any]) -> bool:
    """True when a completed wake advanced a named candidate at least one funnel stage."""
    if not isinstance(row, dict):
        return False
    version = row.get("schema_version")
    if version == SCHEMA_VERSION:
        if row.get("outcome") == "STRATEGY_ADVANCED":
            return True
        if (
            row.get("outcome") == "BLOCKER_REMOVED_AND_RETESTED"
            and row.get("retest_decision") == "STRATEGY_ADVANCED"
        ):
            return True
        advancement = row.get("strategy_advancement")
        if isinstance(advancement, dict) and advancement.get("advanced") is True:
            return True
        return False
    if version == LEGACY_SCHEMA_VERSION:
        # Legacy CAPABILITY/REPAIRED/FALSIFIED never counted as strategy advancement.
        return row.get("outcome") == "CANDIDATE"
    return False


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
    epoch = load_search_epoch(repo)
    epoch_records = records_for_epoch(records, epoch)
    closed = sorted(
        {
            str(family)
            for row in records
            for family in row.get("closed_families", [])
            if str(family).strip()
        }
    )
    # Recent / signature thrash checks stay global so repeated DNA is still visible,
    # but pivot/burst-stop streaks are epoch-scoped after a search restart.
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
    last_global = records[-1] if records else {}
    last_global_stamp = str(last_global.get("stamp") or "").strip()
    epoch_started = _epoch_started_stamp(epoch)
    last_is_pre_epoch = bool(
        epoch_started and last_global_stamp and last_global_stamp < epoch_started
    )
    if (
        records
        and last_global.get("outcome") in {"DIMINISHING_RETURNS", "EVIDENCE_WAIT"}
        and not (last_is_pre_epoch and isinstance(epoch, dict) and epoch.get("reassessment_complete"))
    ):
        if last_global.get("outcome") == "DIMINISHING_RETURNS":
            redirect_reasons.append("last completed wake declared DIMINISHING_RETURNS")
        else:
            redirect_reasons.append("last completed wake declared EVIDENCE_WAIT")
    elif (
        last_is_pre_epoch
        and isinstance(epoch, dict)
        and epoch.get("reassessment_complete")
        and last_global.get("outcome") in {"DIMINISHING_RETURNS", "EVIDENCE_WAIT"}
    ):
        redirect_reasons.append(
            "prior-epoch stop/wait was superseded by completed search-design reassessment; "
            f"active epoch {epoch.get('epoch_id')!r} starts at stamp {epoch_started!r}"
        )
    if len(signatures) >= 2 and signatures[-1] and signatures[-1] == signatures[-2]:
        redirect_reasons.append(f"last two completed wakes repeated loop signature {signatures[-1]!r}")

    consecutive_no_advance = 0
    for row in reversed(epoch_records):
        if strategy_advanced(row):
            break
        consecutive_no_advance += 1
    strategy_pivot_required = consecutive_no_advance >= 2
    strategy_burst_stop_required = consecutive_no_advance >= 3
    if strategy_pivot_required:
        redirect_reasons.append(
            f"{consecutive_no_advance} consecutive epoch wakes without STRATEGY_ADVANCED; "
            "pivot to a materially different economic mechanism or evidence class"
        )
    if strategy_burst_stop_required:
        redirect_reasons.append(
            "three or more consecutive epoch wakes without STRATEGY_ADVANCED; "
            "stop the burst and reassess search design/data rather than buying wake volume"
        )

    research_routes = assess_research_routes(repo)
    last = last_global
    last_dependency_text = " ".join(
        [str(last.get("next", "")), *(str(value) for value in last.get("data_dependencies", []))]
    ).lower()
    archive_dependent_stop = bool(
        last.get("outcome") in {"DIMINISHING_RETURNS", "EVIDENCE_WAIT"}
        and any(token in last_dependency_text for token in ("archive", "observed option", "market date"))
        and not (last_is_pre_epoch and isinstance(epoch, dict) and epoch.get("reassessment_complete"))
    )
    independent_route_open = any(
        name != "observed_historical_option_replay" for name in research_routes["executable_routes"]
    )
    archive_stop_invalidated = archive_dependent_stop and independent_route_open
    if archive_stop_invalidated:
        redirect_reasons.append(
            "archive-dependent stop is invalidated by an executable independent research route"
        )

    discovery_bar = (epoch or {}).get("discovery_bar") if isinstance(epoch, dict) else None
    capital_seat_bar = (epoch or {}).get("capital_seat_bar") if isinstance(epoch, dict) else None
    if not isinstance(discovery_bar, dict):
        discovery_bar = {
            "purpose": "F0→F1 / F1→F2 signal only",
            "cannot_earn_L1_or_capital_seat": True,
        }
    if not isinstance(capital_seat_bar, dict):
        capital_seat_bar = {
            "purpose": "L1 / paper-path eligibility",
            "max_loss_usd_one_lot": 300,
            "window_max_dd_usd": 75,
            "dense_negative_windows_max": 5,
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "stamp": stamp,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "integrated prior compounding.json records",
        "prior_record_count": len(records),
        "epoch_record_count": len(epoch_records),
        "search_epoch": {
            "epoch_id": (epoch or {}).get("epoch_id") if isinstance(epoch, dict) else None,
            "started_stamp": epoch_started,
            "reassessment_complete": bool(
                isinstance(epoch, dict) and epoch.get("reassessment_complete")
            ),
            "reassessment_doc": (epoch or {}).get("reassessment_doc")
            if isinstance(epoch, dict)
            else None,
            "charter_doc": (epoch or {}).get("charter_doc") if isinstance(epoch, dict) else None,
            "epoch_success_definition": (epoch or {}).get("epoch_success_definition")
            if isinstance(epoch, dict)
            else None,
        },
        "discovery_bar": discovery_bar,
        "capital_seat_bar": capital_seat_bar,
        "closed_families": closed,
        "prior_novelty_keys": novelty,
        "recent_runs": [
            {
                "stamp": row.get("stamp"),
                "schema_version": row.get("schema_version"),
                "loop_signature": row.get("loop_signature"),
                "outcome": row.get("outcome"),
                "strategy_advanced": strategy_advanced(row),
                "economic_mechanism": row.get("economic_mechanism"),
                "candidate_or_family_scope": row.get("candidate_or_family_scope"),
                "funnel_stage_before": row.get("funnel_stage_before"),
                "funnel_stage_after": row.get("funnel_stage_after"),
                "novelty_keys": [
                    delta.get("novelty_key")
                    for delta in row.get("useful_deltas", [])
                    if isinstance(delta, dict)
                ],
                "next": row.get("next"),
            }
            for row in recent
        ],
        "consecutive_no_strategy_advance": consecutive_no_advance,
        "strategy_pivot_required": strategy_pivot_required,
        "strategy_burst_stop_required": strategy_burst_stop_required,
        "redirect_required": bool(redirect_reasons),
        "redirect_reasons": redirect_reasons,
        "research_routes": research_routes,
        "archive_dependent_stop_invalidated": archive_stop_invalidated,
        "choice_rule": (
            "Closed families and prior NEXT are context, not allowlists. Reopen only with a named "
            "new evidence class or repaired capability. Operational completion is separate from strategy "
            "advancement. Use discovery_bar for F0→F1/F1→F2 signals and capital_seat_bar for L1/paper seats; "
            "discovery survivors never earn L1 alone. A blocked observed-option route blocks only dependent "
            "claims and cannot alone justify stop while another historical route remains informative. "
            "After two consecutive epoch wakes without STRATEGY_ADVANCED, pivot mechanism/evidence class; "
            "after three, stop the burst and reassess search design/data. Prior-epoch DIMINISHING_RETURNS "
            "is superseded once configs/search_epoch.json marks reassessment_complete. Honest "
            "information-exhaustion stops remain valid after open routes are assessed for material novelty."
        ),
        "strategy_run_contract": {
            "required_outcome_set": sorted(STRATEGY_OUTCOMES),
            "funnel_stages": list(FUNNEL_STAGES),
            "rule": (
                "Every BUILD wake must declare economic_mechanism, candidate_or_family_scope, "
                "funnel_stage_before/after, falsifier, and exactly one strategy outcome. "
                "Capability/tooling alone is not strategy progress unless the unlocked experiment "
                "is exercised in-wake to STRATEGY_ADVANCED or FAMILY_CLOSED via "
                "BLOCKER_REMOVED_AND_RETESTED. STRATEGY_ADVANCED at F0→F1 may use discovery_bar when "
                "claim scope is labeled L0 discovery; capital path/L1 still requires capital_seat_bar."
            ),
        },
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


def _require_nonempty_str(handoff: dict[str, Any], key: str) -> str:
    value = str(handoff.get(key, "")).strip()
    if not value:
        raise CompoundingError(f"{key} is required")
    return value


def _require_stage(handoff: dict[str, Any], key: str) -> str:
    value = _require_nonempty_str(handoff, key)
    if value not in FUNNEL_RANK:
        raise CompoundingError(f"invalid {key}: {value!r}")
    return value


def _validate_useful_deltas(
    repo: Path,
    deltas: list[Any],
    changed: set[str],
    *,
    allow_empty: bool,
) -> tuple[set[str], set[str]]:
    if not isinstance(deltas, list):
        raise CompoundingError("useful_deltas must be a list")
    if not deltas and not allow_empty:
        raise CompoundingError("non-wait strategy outcome requires at least one measurable useful delta")

    novelty_keys: set[str] = set()
    kinds: set[str] = set()
    for index, delta in enumerate(deltas):
        if not isinstance(delta, dict) or delta.get("kind") not in DELTA_KINDS:
            raise CompoundingError(f"useful_deltas[{index}] has invalid kind")
        kinds.add(str(delta["kind"]))
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
        if delta["kind"] in CAPABILITY_DELTA_KINDS:
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
    return novelty_keys, kinds


def _validate_critic_findings(repo: Path, findings: Any, changed: set[str]) -> int:
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
    return len(findings)


def _validate_strategy_contract(
    handoff: dict[str, Any],
    *,
    kinds: set[str],
) -> dict[str, Any]:
    mechanism = _require_nonempty_str(handoff, "economic_mechanism")
    scope = _require_nonempty_str(handoff, "candidate_or_family_scope")
    stage_before = _require_stage(handoff, "funnel_stage_before")
    stage_after = _require_stage(handoff, "funnel_stage_after")
    falsifier = _require_nonempty_str(handoff, "falsifier")
    outcome = handoff.get("outcome")
    if outcome not in STRATEGY_OUTCOMES:
        raise CompoundingError(f"invalid strategy outcome: {outcome!r}")

    advancement = handoff.get("strategy_advancement")
    if not isinstance(advancement, dict):
        raise CompoundingError("strategy_advancement object is required")
    advanced = advancement.get("advanced")
    if advanced is not True and advanced is not False:
        raise CompoundingError("strategy_advancement.advanced must be boolean")
    adv_summary = str(advancement.get("summary", "")).strip()
    if not adv_summary:
        raise CompoundingError("strategy_advancement.summary is required")

    search_info = handoff.get("search_information")
    if not isinstance(search_info, dict):
        raise CompoundingError("search_information object is required")
    search_summary = str(search_info.get("summary", "")).strip()
    if not search_summary:
        raise CompoundingError("search_information.summary is required")
    reported_kinds = search_info.get("delta_kinds")
    if not isinstance(reported_kinds, list):
        raise CompoundingError("search_information.delta_kinds must be a list")
    if set(str(value) for value in reported_kinds) != kinds:
        raise CompoundingError("search_information.delta_kinds must match useful_deltas kinds")

    stage_advanced = FUNNEL_RANK[stage_after] > FUNNEL_RANK[stage_before]
    if advanced and not stage_advanced:
        raise CompoundingError("strategy_advancement.advanced requires funnel stage movement")
    if stage_advanced and not advanced:
        raise CompoundingError("funnel stage movement requires strategy_advancement.advanced=true")

    closed_families = handoff.get("closed_families", [])
    if not isinstance(closed_families, list):
        raise CompoundingError("closed_families must be a list")
    closed_nonempty = any(str(value).strip() for value in closed_families)

    capability_only = bool(kinds) and kinds.issubset(CAPABILITY_DELTA_KINDS)
    has_experiment = bool(kinds & EXPERIMENT_DELTA_KINDS)
    has_capability = bool(kinds & CAPABILITY_DELTA_KINDS)

    retest_decision = handoff.get("retest_decision")
    evidence_wake_condition = str(handoff.get("evidence_wake_condition", "") or "").strip()
    data_dependencies = handoff.get("data_dependencies", [])
    if not isinstance(data_dependencies, list):
        raise CompoundingError("data_dependencies must be a list")

    if capability_only and outcome != "BLOCKER_REMOVED_AND_RETESTED":
        raise CompoundingError(
            "capability-only handoff is not a strategy outcome; "
            "exercise the unlocked experiment in-wake or use BLOCKER_REMOVED_AND_RETESTED"
        )

    if outcome == "STRATEGY_ADVANCED":
        if not advanced or not stage_advanced:
            raise CompoundingError("STRATEGY_ADVANCED requires stage movement and advanced=true")
        if not has_experiment:
            raise CompoundingError("STRATEGY_ADVANCED requires candidate/evidence experiment residue")
        if retest_decision not in (None, "", "STRATEGY_ADVANCED"):
            raise CompoundingError("STRATEGY_ADVANCED retest_decision must be absent or STRATEGY_ADVANCED")
    elif outcome == "FAMILY_CLOSED":
        if advanced:
            raise CompoundingError("FAMILY_CLOSED cannot claim strategy_advancement.advanced=true")
        if stage_advanced:
            raise CompoundingError("FAMILY_CLOSED cannot advance funnel stage")
        if not closed_nonempty:
            raise CompoundingError("FAMILY_CLOSED requires non-empty closed_families")
        if "falsification" not in kinds:
            raise CompoundingError("FAMILY_CLOSED requires a falsification useful delta")
    elif outcome == "BLOCKER_REMOVED_AND_RETESTED":
        if retest_decision not in RETEST_DECISIONS:
            raise CompoundingError(
                "BLOCKER_REMOVED_AND_RETESTED requires retest_decision "
                "STRATEGY_ADVANCED or FAMILY_CLOSED"
            )
        if not has_capability:
            raise CompoundingError(
                "BLOCKER_REMOVED_AND_RETESTED requires a capability/repair useful delta"
            )
        if not has_experiment:
            raise CompoundingError(
                "BLOCKER_REMOVED_AND_RETESTED requires the dependent experiment to be exercised "
                "with candidate/falsification/evidence residue in the same wake"
            )
        if retest_decision == "STRATEGY_ADVANCED":
            if not advanced or not stage_advanced:
                raise CompoundingError(
                    "retest_decision STRATEGY_ADVANCED requires stage movement and advanced=true"
                )
        else:
            if advanced or stage_advanced:
                raise CompoundingError(
                    "retest_decision FAMILY_CLOSED cannot claim stage advancement"
                )
            if not closed_nonempty:
                raise CompoundingError(
                    "retest_decision FAMILY_CLOSED requires non-empty closed_families"
                )
            if "falsification" not in kinds:
                raise CompoundingError(
                    "retest_decision FAMILY_CLOSED requires a falsification useful delta"
                )
    elif outcome == "EVIDENCE_WAIT":
        if advanced or stage_advanced:
            raise CompoundingError("EVIDENCE_WAIT cannot claim strategy advancement")
        if not evidence_wake_condition:
            raise CompoundingError("EVIDENCE_WAIT requires evidence_wake_condition")
        if not any(str(value).strip() for value in data_dependencies):
            raise CompoundingError("EVIDENCE_WAIT requires non-empty data_dependencies")
        if capability_only:
            raise CompoundingError(
                "EVIDENCE_WAIT cannot be used to launder capability-only work"
            )

    return {
        "economic_mechanism": mechanism,
        "candidate_or_family_scope": scope,
        "funnel_stage_before": stage_before,
        "funnel_stage_after": stage_after,
        "falsifier": falsifier,
        "strategy_advanced": bool(advanced),
        "search_information_summary": search_summary,
    }


def validate(repo: Path, stamp: str, base_head: str, baseline: Path | None) -> dict[str, Any]:
    run = repo / "reports" / "trader-wakes" / "moa" / stamp
    handoff_path = run / "compounding.json"
    learning_path = run / "learning-promotion.md"
    handoff = _load(handoff_path)
    if handoff.get("schema_version") != SCHEMA_VERSION or handoff.get("stamp") != stamp:
        raise CompoundingError(
            f"compounding handoff requires schema_version={SCHEMA_VERSION} and matching stamp "
            f"(legacy schema {LEGACY_SCHEMA_VERSION} is read-only history)"
        )
    outcome = handoff.get("outcome")
    if outcome not in STRATEGY_OUTCOMES:
        raise CompoundingError(
            f"invalid outcome: {outcome!r}; required one of {sorted(STRATEGY_OUTCOMES)}"
        )
    signature = str(handoff.get("loop_signature", "")).strip()
    if not signature:
        raise CompoundingError("loop_signature is required")
    next_seed = str(handoff.get("next", "")).strip()
    if not next_seed:
        raise CompoundingError("exactly one non-empty next value is required")

    # EVIDENCE_WAIT may carry zero useful deltas when the only honest residue is the wait condition.
    allow_empty_deltas = outcome == "EVIDENCE_WAIT"
    changed = _changed_paths(repo, base_head)
    deltas = handoff.get("useful_deltas")
    if deltas is None:
        deltas = []
    novelty_keys, kinds = _validate_useful_deltas(
        repo,
        deltas,
        changed,
        allow_empty=allow_empty_deltas,
    )
    if next_seed == "DIMINISHING_RETURNS" and outcome not in {"EVIDENCE_WAIT"}:
        # Still allowed as a NEXT seed after a closed decision, but not as a fake strategy outcome.
        pass

    contract = _validate_strategy_contract(handoff, kinds=kinds)
    findings_count = _validate_critic_findings(repo, handoff.get("critic_findings", []), changed)

    previous = _previous_records(repo, stamp)
    prior_novelty = {
        str(delta.get("novelty_key"))
        for row in previous
        for delta in row.get("useful_deltas", [])
        if isinstance(delta, dict)
    }
    if handoff.get("useful_deltas") and novelty_keys.issubset(prior_novelty):
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
        "schema_version": SCHEMA_VERSION,
        "outcome": outcome,
        "loop_signature": signature,
        "strategy_advanced": contract["strategy_advanced"],
        "economic_mechanism": contract["economic_mechanism"],
        "candidate_or_family_scope": contract["candidate_or_family_scope"],
        "funnel_stage_before": contract["funnel_stage_before"],
        "funnel_stage_after": contract["funnel_stage_after"],
        "useful_delta_count": len(handoff.get("useful_deltas") or []),
        "novelty_keys": sorted(novelty_keys),
        "critic_findings_closed": findings_count,
        "role_ready": True,
        "role_ready_basis": (
            "validated changed learning + structured strategy-run handoff; session text ignored"
        ),
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

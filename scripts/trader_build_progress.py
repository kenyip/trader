#!/usr/bin/env python3
"""Strategy-first BUILD progress scoreboard from recent MoA stamps.

Answers Ken's question "are the new runs better?" using the machine-enforced
strategy-run outcome contract (compounding schema v2 + legacy-readable v1),
not operational wake volume or a blended research-process score.

Usage:
  .venv/bin/python scripts/trader_build_progress.py
  .venv/bin/python scripts/trader_build_progress.py --write
  .venv/bin/python scripts/trader_build_progress.py --limit 8
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
MOA = REPO / "reports" / "trader-wakes" / "moa"
OUT_DIR = REPO / "reports" / "readiness"

# scripts/ is first on path when this file is executed directly; package import
# works when tests load via `from scripts import trader_build_progress`.
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

try:
    from trader_build_compounding import (  # type: ignore
        FUNNEL_RANK,
        FUNNEL_STAGES,
        LEGACY_OUTCOMES,
        LEGACY_SCHEMA_VERSION,
        SCHEMA_VERSION,
        STRATEGY_OUTCOMES,
        counts_toward_no_advance_streak,
        load_search_epoch,
        records_for_epoch,
        strategy_advanced,
    )
except ImportError:  # pragma: no cover
    from scripts.trader_build_compounding import (  # type: ignore
        FUNNEL_RANK,
        FUNNEL_STAGES,
        LEGACY_OUTCOMES,
        LEGACY_SCHEMA_VERSION,
        SCHEMA_VERSION,
        STRATEGY_OUTCOMES,
        counts_toward_no_advance_streak,
        load_search_epoch,
        records_for_epoch,
        strategy_advanced,
    )

VERDICT_BETTER = "BETTER"
VERDICT_INFORMATIVE = "INFORMATIVE_BUT_NOT_CLOSER"
VERDICT_THRASH = "INVALID_THRASH"
VALID_VERDICTS = {VERDICT_BETTER, VERDICT_INFORMATIVE, VERDICT_THRASH}

# Legacy prose-heuristic outcomes that are informative search residue, not thrash.
LEGACY_INFORMATIVE_OUTCOMES = {
    "FALSIFIED",
    "CAPABILITY",
    "REPAIRED",
    "DIMINISHING_RETURNS",
}
# Schema-v2 non-advancing outcomes that still close a valid decision.
V2_INFORMATIVE_OUTCOMES = {
    "FAMILY_CLOSED",
    "EVIDENCE_WAIT",
    "BLOCKER_REMOVED_AND_RETESTED",
}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _tracked_on_origin_main(path: Path) -> bool:
    """True when the path's latest committed version is integrated into origin/main."""
    if not path.is_absolute():
        path = REPO / path
    try:
        rel = str(path.relative_to(REPO))
    except ValueError:
        return False
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", rel],
        cwd=REPO,
        text=True,
        capture_output=True,
    )
    sha = commit.stdout.strip()
    if commit.returncode or not sha:
        return False
    integrated = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, "origin/main"],
        cwd=REPO,
        text=True,
        capture_output=True,
    )
    return integrated.returncode == 0


def _load_compounding(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def classify_strategy_verdict(
    *,
    complete: bool,
    compounding: dict[str, Any],
    prior_loop_signature: str | None = None,
    novelty_keys: list[Any] | None = None,
    prior_novelty_keys: set[str] | None = None,
) -> str:
    """Map a stamp onto the strategy-convergence verdict.

    BETTER — independently declared/valid strategy funnel advancement.
    INFORMATIVE_BUT_NOT_CLOSER — valid family closure / evidence wait /
        non-advancing retest / legacy informative non-advance.
    INVALID_THRASH — incomplete, contract-invalid, or forbidden repetition.
    """
    if not complete:
        return VERDICT_THRASH
    if not compounding:
        # Complete dual without a structured handoff cannot prove strategy movement.
        return VERDICT_THRASH

    version = compounding.get("schema_version")
    outcome = str(compounding.get("outcome") or "")

    if strategy_advanced(compounding):
        return VERDICT_BETTER

    # Forbidden repetition: identical loop signature with zero new novelty and
    # no strategy advance — operational completion is not progress.
    signature = str(compounding.get("loop_signature") or "").strip()
    novelty = {
        str(key)
        for key in (novelty_keys or [])
        if key is not None and str(key).strip()
    }
    prior_nov = prior_novelty_keys or set()
    if (
        prior_loop_signature
        and signature
        and signature == prior_loop_signature
        and (not novelty or novelty.issubset(prior_nov))
    ):
        return VERDICT_THRASH

    if version == SCHEMA_VERSION:
        if outcome in V2_INFORMATIVE_OUTCOMES:
            return VERDICT_INFORMATIVE
        if outcome in STRATEGY_OUTCOMES:
            # STRATEGY_ADVANCED already returned BETTER above.
            return VERDICT_INFORMATIVE
        return VERDICT_THRASH

    if version == LEGACY_SCHEMA_VERSION:
        if outcome in LEGACY_INFORMATIVE_OUTCOMES:
            return VERDICT_INFORMATIVE
        if outcome in LEGACY_OUTCOMES:
            return VERDICT_INFORMATIVE
        return VERDICT_THRASH

    return VERDICT_THRASH


def _research_process_score(
    *,
    complete: bool,
    compounding: dict[str, Any],
    close_text: str,
) -> tuple[int, list[str]]:
    """Secondary capability/evidence/research-process score (0–5).

    Never used as strategy-closeness. Zero-advance runs may score high here
    when tooling/falsification residue is real — that is search information,
    not a living strategy.
    """
    types: list[str] = []
    if not complete:
        return 0, ["failed_or_incomplete"]

    latest_bits = close_text.lower()
    if compounding:
        outcome = str(compounding.get("outcome", ""))
        delta_kinds = sorted(
            {
                str(delta.get("kind"))
                for delta in compounding.get("useful_deltas", [])
                if isinstance(delta, dict) and delta.get("kind")
            }
        )
        types = [f"delta_{kind}" for kind in delta_kinds] or ["no_useful_delta"]
        advanced = strategy_advanced(compounding)
        if compounding.get("schema_version") == SCHEMA_VERSION:
            score = {
                "STRATEGY_ADVANCED": 5,
                "BLOCKER_REMOVED_AND_RETESTED": 5 if advanced else 4,
                "FAMILY_CLOSED": 3,
                "EVIDENCE_WAIT": 2,
            }.get(outcome, 0)
            types.append("strategy_advanced" if advanced else "strategy_no_advance")
        else:
            # Legacy schema-1 handoffs: capability/repair never counted as strategy advance.
            score = {
                "CANDIDATE": 5,
                "CAPABILITY": 4,
                "REPAIRED": 4,
                "FALSIFIED": 3,
                "DIMINISHING_RETURNS": 1,
            }.get(outcome, 0)
            types.append("strategy_advanced" if advanced else "strategy_no_advance")
        return score, types

    # Prose-heuristic path for pre-compounding stamps only.
    explicit_scores = [
        int(value)
        for value in re.findall(
            r"(?im)^\s*(?:[-*]\s*)?(?:\|\s*)?(?:progress\s+)?score\s*(?::|\|)\s*\**([0-5])\s*/\s*5",
            close_text,
        )
    ]
    p1 = bool(
        re.search(
            r"\bp1\b|added `?calendar|implemented .*calendar_sim|new sim class scaffold|created .*_sim\.py",
            latest_bits,
        )
    )
    p2 = bool(
        re.search(
            r"\bp2\b|36-cell|time_bias_lab_|pcs_time_bias_grid|direction-bias scoreboard|regime scoreboard",
            latest_bits,
        )
    )
    p3 = bool(re.search(r"\bp3\b|b3\+b4|dated b3|stress_regime_lab_|stress_cost_lab_", latest_bits))
    capital_unchanged = bool(
        re.search(r"capital path unchanged|no capital-path|not promoted|research-only reject", latest_bits)
    )
    p4 = bool(
        re.search(
            r"new quality leader|beats? (the )?leader on after-cost|non-vacuous after-cost (edge|superior|ship)",
            latest_bits,
        )
    ) and not re.search(
        r"not readiness|no positive after-cost|still.*soft loss|no living (?:quality )?leader|\bl0 build\b",
        latest_bits,
    )
    noise = bool(re.search(r"single-leg.*research toy|no defined-risk ship", latest_bits))

    if p1:
        types.append("P1_sim_class")
    if p2:
        types.append("P2_axis_scoreboard")
    if p3:
        types.append("P3_quality_falsify")
    if capital_unchanged:
        types.append("capital_unchanged")
    if p4:
        types.append("P4_edge_candidate")
    if noise and not p1:
        types.append("P0_noise_risk")

    if p4:
        score = 5
    elif p1:
        score = 5
    elif p2:
        score = 4
    elif p3 and not noise:
        score = 3
    elif p3 and noise:
        score = 2
    else:
        score = 2
    if score >= 3 and not re.search(
        r"added |implemented |built |wrote |\.py`|time_bias_lab_|calendar_sim", latest_bits
    ):
        score = min(score, 3 if p3 else 2)
    if explicit_scores:
        score = explicit_scores[-1]
    types.append("strategy_no_advance")
    return score, types


def score_stamp(
    d: Path,
    *,
    prior_loop_signature: str | None = None,
    prior_novelty_keys: set[str] | None = None,
) -> dict[str, Any]:
    if not d.is_absolute():
        d = REPO / d
    meta_p = d / "meta.json"
    close = _read(d / "executor-closeout.md") + "\n" + _read(d / "challenger-critique.md")
    meta: dict[str, Any] = {}
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text())
        except Exception:
            meta = {}
    ex = _read(d / "executor-exit.txt").strip()
    ch = _read(d / "challenger-exit.txt").strip()
    complete = (
        ex == "0"
        and ch == "0"
        and (d / "executor-closeout.md").exists()
        and (d / "challenger-critique.md").exists()
        and (d / "merged-next-seed.md").exists()
    )
    contract_version = int(meta.get("completion_contract_version", 1) or 1)
    if contract_version >= 2:
        learning = d / "learning-promotion.md"
        complete = complete and learning.exists() and _tracked_on_origin_main(learning)
    compounding_path = d / "compounding.json"
    compounding = _load_compounding(compounding_path)
    if contract_version >= 3:
        schema_version = compounding.get("schema_version")
        complete = (
            complete
            and schema_version in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}
            and _tracked_on_origin_main(compounding_path)
        )

    novelty_keys = [
        delta.get("novelty_key")
        for delta in compounding.get("useful_deltas", [])
        if isinstance(delta, dict)
    ]
    process_score, types = _research_process_score(
        complete=complete, compounding=compounding, close_text=close
    )
    advanced = bool(complete and compounding and strategy_advanced(compounding))
    verdict = classify_strategy_verdict(
        complete=complete,
        compounding=compounding,
        prior_loop_signature=prior_loop_signature,
        novelty_keys=novelty_keys,
        prior_novelty_keys=prior_novelty_keys,
    )

    readiness_blockers = []
    latest_bits = close.lower()
    for key, pat in [
        ("after_cost_edge", r"after-cost|5% slip|soft (cost_)?hold"),
        ("b6_paper", r"\bb6\b|multi-session paper"),
        ("b7_shadow", r"\bb7\b|shadow"),
        ("funding", r"unfunded|options level|\$0"),
    ]:
        if re.search(pat, latest_bits):
            readiness_blockers.append(key)

    advancement = compounding.get("strategy_advancement")
    advancement_summary = None
    if isinstance(advancement, dict):
        advancement_summary = advancement.get("summary")

    return {
        "stamp": d.name,
        "complete": complete,
        "executor_exit": ex or None,
        "challenger_exit": ch or None,
        "executor": meta.get("executor"),
        "challenger": meta.get("challenger"),
        # Primary strategy-convergence surface
        "strategy_verdict": verdict,
        "strategy_advanced": advanced,
        "schema_version": compounding.get("schema_version"),
        "compounding_outcome": compounding.get("outcome"),
        "economic_mechanism": compounding.get("economic_mechanism"),
        "candidate_or_family_scope": compounding.get("candidate_or_family_scope"),
        "funnel_stage_before": compounding.get("funnel_stage_before"),
        "funnel_stage_after": compounding.get("funnel_stage_after"),
        "strategy_advancement_summary": advancement_summary,
        "retest_decision": compounding.get("retest_decision"),
        "closed_families": list(compounding.get("closed_families") or []),
        "loop_signature": compounding.get("loop_signature"),
        # Secondary research-process / capability surface (legacy key retained)
        "progress_types": types,
        "progress_score_0_5": process_score,
        "research_process_score_0_5": process_score,
        "useful_delta_count": len(compounding.get("useful_deltas", [])) if compounding else None,
        "novelty_keys": novelty_keys,
        "readiness_blockers_mentioned": readiness_blockers,
        "has_merged_seed": (d / "merged-next-seed.md").exists(),
    }


def _iter_integrated_compounding(limit: int | None = None) -> list[dict[str, Any]]:
    """Chronological integrated compounding rows (origin/main), oldest first."""
    if not MOA.is_dir():
        return []
    stamps = sorted([p for p in MOA.iterdir() if p.is_dir()], key=lambda p: p.name)
    rows: list[dict[str, Any]] = []
    for path in stamps:
        compounding_path = path / "compounding.json"
        if not compounding_path.exists() or not _tracked_on_origin_main(compounding_path):
            continue
        row = _load_compounding(compounding_path)
        if row.get("schema_version") not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
            continue
        row = dict(row)
        row.setdefault("stamp", path.name)
        rows.append(row)
    if limit is not None and limit > 0:
        rows = rows[-limit:]
    return rows


def _candidate_lineage_keys(value: Any) -> set[str]:
    """Stable closure keys for descriptive candidate/family prose.

    Handoffs historically stored the full Layered Edge scope as prose while
    ``closed_families`` often stored a compact candidate ID plus a qualifier.
    Exact-string matching therefore resurrected the same candidate once its
    train and holdout scopes used different descriptions. Keep exact matching
    for legacy/lowercase IDs and additionally match whole uppercase underscore
    identifiers. Whole-token matching deliberately avoids prefix closure.
    """
    text = " ".join(str(value or "").split())
    if not text:
        return set()
    keys = {text}
    keys.update(re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){2,}\b", text))
    return keys


def living_strategy_state(records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Derive living candidates + furthest funnel stage from integrated records."""
    rows = records if records is not None else _iter_integrated_compounding()
    living: dict[str, str] = {}
    closed: set[str] = set()
    closed_lineage_keys: set[str] = set()
    for row in rows:
        for family in row.get("closed_families") or []:
            name = str(family).strip()
            if name:
                closed.add(name)
                family_keys = _candidate_lineage_keys(name)
                closed_lineage_keys.update(family_keys)
                for scope in list(living):
                    if _candidate_lineage_keys(scope) & family_keys:
                        living.pop(scope, None)
        if not strategy_advanced(row):
            continue
        scope = str(row.get("candidate_or_family_scope") or "").strip()
        stage = str(row.get("funnel_stage_after") or "").strip()
        if not scope:
            # Legacy CANDIDATE rows may lack charter fields; still count a living seat.
            scope = f"legacy-candidate:{row.get('stamp', 'unknown')}"
        if _candidate_lineage_keys(scope) & closed_lineage_keys:
            continue
        if stage not in FUNNEL_RANK:
            stage = "F0_MECHANISM"
        prev = living.get(scope)
        if prev is None or FUNNEL_RANK.get(stage, -1) >= FUNNEL_RANK.get(prev, -1):
            living[scope] = stage

    furthest = None
    if living:
        furthest = max(living.values(), key=lambda s: FUNNEL_RANK.get(s, -1))
    return {
        "living_candidates": sorted(living),
        "living_candidate_count": len(living),
        "living_candidate_stages": dict(sorted(living.items())),
        "furthest_living_funnel_stage": furthest,
        "closed_families": sorted(closed),
        "closed_lineage_keys": sorted(closed_lineage_keys),
        "funnel_stages": list(FUNNEL_STAGES),
    }


def consecutive_no_strategy_advance(
    records: list[dict[str, Any]] | None = None, *, epoch_scope: bool = True
) -> int:
    rows = records if records is not None else _iter_integrated_compounding()
    if epoch_scope:
        rows = records_for_epoch(rows, load_search_epoch(REPO))
    streak = 0
    for row in reversed(rows):
        if strategy_advanced(row):
            break
        if not counts_toward_no_advance_streak(row):
            continue
        streak += 1
    return streak


def pivot_stop_state(streak: int) -> dict[str, Any]:
    pivot = streak >= 2
    stop = streak >= 3
    if stop:
        label = "strategy_burst_stop_required"
    elif pivot:
        label = "strategy_pivot_required"
    else:
        label = "none"
    return {
        "consecutive_no_strategy_advance": streak,
        "strategy_pivot_required": pivot,
        "strategy_burst_stop_required": stop,
        "pivot_stop_state": label,
    }


def score_recent_stamps(limit: int = 12) -> list[dict[str, Any]]:
    """Score the most recent ``limit`` MoA stamp dirs chronologically with thrash context."""
    if not MOA.is_dir():
        return []
    stamps = sorted([p for p in MOA.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)[
        :limit
    ]
    stamps = list(reversed(stamps))  # chronological
    rows: list[dict[str, Any]] = []
    prior_sig: str | None = None
    prior_novelty: set[str] = set()
    for path in stamps:
        row = score_stamp(
            path,
            prior_loop_signature=prior_sig,
            prior_novelty_keys=set(prior_novelty),
        )
        rows.append(row)
        if row["complete"] and row.get("loop_signature"):
            prior_sig = str(row["loop_signature"])
        for key in row.get("novelty_keys") or []:
            if key is not None and str(key).strip():
                prior_novelty.add(str(key))
    return rows


def render_scoreboard(rows: list[dict[str, Any]], *, all_records: list[dict[str, Any]] | None = None) -> str:
    complete = [r for r in rows if r["complete"]]
    better = [r for r in complete if r["strategy_verdict"] == VERDICT_BETTER]
    informative = [r for r in complete if r["strategy_verdict"] == VERDICT_INFORMATIVE]
    thrash = [r for r in rows if r["strategy_verdict"] == VERDICT_THRASH]
    advance_count = sum(1 for r in complete if r["strategy_advanced"])
    advance_rate = (advance_count / len(complete)) if complete else 0.0

    records = all_records if all_records is not None else _iter_integrated_compounding()
    living = living_strategy_state(records)
    historical_streak = consecutive_no_strategy_advance(records, epoch_scope=False)
    streak = consecutive_no_strategy_advance(records, epoch_scope=True)
    pivot = pivot_stop_state(streak)
    epoch = load_search_epoch(REPO) or {}
    epoch_id = epoch.get("epoch_id") or "none"
    epoch_status = epoch.get("status") or "none"
    epoch_started = epoch.get("started_stamp") or "—"

    # Secondary research-process stats (clearly labeled; never strategy closeness).
    process_scores = [r["research_process_score_0_5"] for r in complete]
    avg_process = (sum(process_scores) / len(process_scores)) if process_scores else 0.0
    high_process = sum(1 for s in process_scores if s >= 4)
    low_process = sum(1 for s in process_scores if s <= 2)

    lines = [
        f"# BUILD strategy-convergence scoreboard — {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%dT%H%M')}",
        "",
        "Primary question: **are the new runs better toward a living strategy?**",
        "Uses the machine-enforced strategy-run outcome contract (`compounding.json` schema v2;",
        "legacy schema v1 remains readable). Operational wake completion and research-process",
        "scores are **not** strategy closeness. See `docs/BUILD_PROGRESS_AND_CONFIDENCE.md`.",
        "",
        "## Strategy-convergence scorecard",
        "",
        f"- Search epoch: **{epoch_id}** (status `{epoch_status}`, started_stamp `{epoch_started}`)",
        f"- Stamps scored: **{len(rows)}** (complete **{len(complete)}**)",
        f"- Strategy advances (BETTER): **{advance_count}** · rate **{advance_rate:.0%}** of complete",
        f"- INFORMATIVE_BUT_NOT_CLOSER: **{len(informative)}** · INVALID_THRASH: **{len(thrash)}**",
        f"- Living candidates: **{living['living_candidate_count']}**"
        + (
            f" (`{', '.join(living['living_candidates'])}`)"
            if living["living_candidates"]
            else " (none)"
        ),
        f"- Furthest living funnel stage: **{living['furthest_living_funnel_stage'] or '—'}**",
        f"- Consecutive no-advance streak (**configured epoch**): **{pivot['consecutive_no_strategy_advance']}**",
        f"- Historical no-advance streak (all integrated, context only): **{historical_streak}**",
        f"- Pivot/stop state: **{pivot['pivot_stop_state']}**"
        + (
            f" (pivot≥2={pivot['strategy_pivot_required']}, burst-stop≥3={pivot['strategy_burst_stop_required']})"
        ),
        "",
        "### Per-run strategy verdicts",
        "",
        "| stamp | verdict | advanced | outcome | funnel | scope | process_score* |",
        "|---|---|---:|---|---|---|---:|",
    ]
    for r in rows:
        models_scope = r.get("candidate_or_family_scope") or "—"
        if isinstance(models_scope, str) and len(models_scope) > 40:
            models_scope = models_scope[:37] + "…"
        funnel = "—"
        if r.get("funnel_stage_before") or r.get("funnel_stage_after"):
            funnel = f"{r.get('funnel_stage_before') or '?'}→{r.get('funnel_stage_after') or '?'}"
        lines.append(
            f"| `{r['stamp']}` | **{r['strategy_verdict']}** | "
            f"{'yes' if r['strategy_advanced'] else 'no'} | "
            f"{r.get('compounding_outcome') or '—'} | {funnel} | {models_scope} | "
            f"{r['research_process_score_0_5']} |"
        )
    lines += [
        "",
        "Verdict definitions:",
        "",
        f"- **{VERDICT_BETTER}** — independently declared/valid strategy funnel advancement",
        f"  (`STRATEGY_ADVANCED`, advancing retest, or legacy `CANDIDATE`).",
        f"- **{VERDICT_INFORMATIVE}** — valid family closure, evidence wait, non-advancing",
        "  retest, or legacy informative non-advance (capability/repair/falsify). Search",
        "  information only — **not closer to a living strategy seat**.",
        f"- **{VERDICT_THRASH}** — incomplete, contract-invalid, or forbidden loop repetition",
        "  without new novelty.",
        "",
        "## Secondary context (research-process / capability — not strategy closeness)",
        "",
        f"- Avg research-process score (complete): **{avg_process:.2f} / 5**",
        f"- High process-score runs (≥4): **{high_process}** · Low (≤2): **{low_process}**",
        "- These counts measure tooling, falsification density, and operational residue.",
        "  A window of **4+ capability runs with strategy_no_advance is still zero strategy advance.**",
        "",
        "| stamp | process_score | progress_types | exits | models |",
        "|---|---:|---|---|---|",
    ]
    for r in rows:
        models = (
            f"{(r.get('executor') or {}).get('model', '?')}→"
            f"{(r.get('challenger') or {}).get('model', '?')}"
        )
        lines.append(
            f"| `{r['stamp']}` | {r['research_process_score_0_5']} | "
            f"{', '.join(r['progress_types']) or '—'} | "
            f"{r['executor_exit']}/{r['challenger_exit']} | {models} |"
        )
    lines += [
        "",
        "## Real-trade confidence (manual ladder)",
        "",
        "- **L0 BUILD** — current unless L1 evidence appears",
        "- **L1 sim edge** — non-vacuous after-cost + B3 density + competitive ml/dd",
        "- **L2 paper B6** — multi-session open/manage/close",
        "- **L3 shadow B7** — propose→risk→log window",
        "- **L4 first real $** — Ken fund + arm + 1-lot only",
        "",
        "Strategy-convergence leads; process plumbing is secondary. **L0 for live money**",
        "until a BETTER advance survives L1 gates + B6.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rows = score_recent_stamps(limit=args.limit)
    text = render_scoreboard(rows)
    print(text)
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H%M")
        (OUT_DIR / "build-progress-LATEST.md").write_text(text)
        (OUT_DIR / f"build-progress-{stamp}.md").write_text(text)
        print(f"Wrote {OUT_DIR / 'build-progress-LATEST.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

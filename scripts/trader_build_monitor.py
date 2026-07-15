#!/usr/bin/env python3
"""Monitor-only BUILD fast-track: strategy-convergence + drift snapshot.

Does not launch labs. Writes reports/readiness/build-monitor-LATEST.md
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

from trader_build_progress import (  # noqa: E402
    VERDICT_BETTER,
    VERDICT_INFORMATIVE,
    VERDICT_THRASH,
    consecutive_no_strategy_advance,
    living_strategy_state,
    pivot_stop_state,
    score_stamp,
)

MOA = REPO / "reports" / "trader-wakes" / "moa"
OUT = REPO / "reports" / "readiness"
LOCK = REPO / ".cache" / "platform" / "build_lab.lock"
LATEST = REPO / "reports" / "trader-wakes" / "LATEST.md"
READINESS = REPO / "reports" / "readiness" / "LATEST.md"


def _run_progress() -> str:
    try:
        r = subprocess.run(
            [
                str(REPO / ".venv" / "bin" / "python"),
                str(REPO / "scripts" / "trader_build_progress.py"),
                "--limit",
                "10",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return f"(progress script failed: {e})"


def _complete_stamps(limit: int = 8) -> list[Path]:
    stamps = sorted([p for p in MOA.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    out = []
    for p in stamps:
        if score_stamp(p)["complete"]:
            out.append(p)
        if len(out) >= limit:
            break
    return list(reversed(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).astimezone()
    complete = _complete_stamps(6)
    scores = []
    drift = []
    prior_sig = None
    prior_novelty: set[str] = set()
    for p in complete:
        row = score_stamp(
            p,
            prior_loop_signature=prior_sig,
            prior_novelty_keys=set(prior_novelty),
        )
        kind = ", ".join(row["progress_types"]) or "unclassified"
        scores.append(
            (
                p.name,
                row["strategy_verdict"],
                row["strategy_advanced"],
                row["research_process_score_0_5"],
                kind,
                row.get("compounding_outcome"),
            )
        )
        if row["complete"] and row.get("loop_signature"):
            prior_sig = str(row["loop_signature"])
        for key in row.get("novelty_keys") or []:
            if key is not None and str(key).strip():
                prior_novelty.add(str(key))

    living = living_strategy_state()
    streak = consecutive_no_strategy_advance()
    pivot = pivot_stop_state(streak)

    better_n = sum(1 for _, v, *_ in scores if v == VERDICT_BETTER)
    informative_n = sum(1 for _, v, *_ in scores if v == VERDICT_INFORMATIVE)
    thrash_n = sum(1 for _, v, *_ in scores if v == VERDICT_THRASH)

    if pivot["strategy_burst_stop_required"]:
        drift.append(
            f"ALERT: {streak} consecutive epoch wakes without strategy advance "
            "(strategy_burst_stop_required — stop burst; reassess search design/data)"
        )
    elif pivot["strategy_pivot_required"]:
        drift.append(
            f"ALERT: {streak} consecutive epoch wakes without strategy advance "
            "(strategy_pivot_required — pivot mechanism/evidence class)"
        )
    if len(scores) >= 3 and all(v == VERDICT_THRASH for _, v, *_ in scores[-3:]):
        drift.append("ALERT: last 3 complete duals are INVALID_THRASH")
    if (
        len(scores) >= 3
        and better_n == 0
        and all(process_score >= 4 for _, _, _, process_score, _, _ in scores[-3:])
    ):
        # High research-process scores with zero BETTER — do not read as strategy progress.
        drift.append(
            "INFO: recent duals show high research-process scores with zero BETTER advances "
            "(capability ≠ strategy closeness)"
        )
    if LOCK.exists():
        try:
            age = now.timestamp() - LOCK.stat().st_mtime
            if age > 45 * 60:
                drift.append(f"ALERT: build_lab.lock age {int(age/60)}m — possible stuck dual")
            else:
                drift.append(f"INFO: dual running (lock age {int(age/60)}m)")
        except Exception:
            drift.append("INFO: lock present")

    latest = LATEST.read_text(encoding="utf-8", errors="replace") if LATEST.exists() else ""
    l0 = bool(re.search(r"\bL0\b|PHASE: BUILD", latest))
    l1 = bool(re.search(r"\bL1\b", latest)) and not re.search(
        r"(?:not|no) L1|L0(?:/| )BUILD(?: only)?", latest, re.I
    )
    live_claim = bool(
        re.search(r"LIVE_PACKET|agentic arm|shadow auto-promote|ready for real", latest, re.I)
    )

    if live_claim and re.search(r"no live|not readiness|L0", latest, re.I):
        pass  # negated
    elif live_claim and not re.search(r"no live|not readiness|L0 BUILD", latest, re.I):
        drift.append("ALERT: possible live/readiness language — inspect LATEST")

    readiness = READINESS.read_text(encoding="utf-8", errors="replace") if READINESS.exists() else ""
    next_match = re.search(r"(?im)^NEXT:\s*(.+)$", readiness)
    current_next = (
        next_match.group(1).strip() if next_match else "See readiness/LATEST.md; no NEXT assertion parsed."
    )

    lines = [
        f"# BUILD fast-track monitor — {now.strftime('%Y-%m-%dT%H%M %Z')}",
        "",
        "Monitor-only. Program goal: **strategy-funnel advancement → L1 high-confidence strategy** "
        "(then B6 paper). Research-process/capability residue is secondary context. "
        "Ken/Jarvis do not micromanage axes.",
        "",
        "## Strategy-convergence status",
        f"- Complete duals scored (recent): **{len(scores)}**",
        f"- BETTER / INFORMATIVE / THRASH: **{better_n}** / **{informative_n}** / **{thrash_n}**",
        f"- Living candidates: **{living['living_candidate_count']}** · furthest stage: "
        f"**{living['furthest_living_funnel_stage'] or '—'}**",
        f"- Consecutive no-advance streak (**active epoch**): **{streak}** · pivot/stop: **{pivot['pivot_stop_state']}**",
        f"- Latest wake file present: **{LATEST.exists()}**",
        f"- Readiness language: **{'L1-positive?' if l1 else 'L0/BUILD (expected until edge)'}**",
        f"- Lock: **{'yes' if LOCK.exists() else 'no'}**",
        "",
        "## Recent complete duals (strategy verdict first)",
        "",
        "| stamp | verdict | advanced | process_score* | outcome | kind |",
        "|---|---|---:|---:|---|---|",
    ]
    for name, verdict, advanced, process_score, kind, outcome in scores:
        lines.append(
            f"| `{name}` | **{verdict}** | {'yes' if advanced else 'no'} | "
            f"{process_score} | {outcome or '—'} | {kind} |"
        )
    if not scores:
        lines.append("| — | — | — | — | — | no complete duals |")

    lines += [
        "",
        "*process_score is research-process/capability secondary context only; "
        "it must not be read as strategy closeness.",
        "",
        "## Drift / alerts",
        "",
    ]
    if drift:
        lines.extend(f"- {d}" for d in drift)
    else:
        lines.append("- none")

    lines += [
        "",
        "## Current NEXT (from readiness/LATEST.md)",
        "",
        f"- {current_next}",
        "",
        "## Confidence ladder",
        "",
        "- **L0** BUILD — current until non-vacuous after-cost edge DNA",
        "- **L1** sim edge — first high-confidence strategy *in sim*",
        "- **L2+** paper/shadow/real — after L1; not dual-count",
        "",
        "## Progress script (strategy-first)",
        "",
        "```",
        _run_progress().strip()[:3500],
        "```",
        "",
    ]
    text = "\n".join(lines).rstrip() + "\n"
    print(text)
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        stamp = now.strftime("%Y-%m-%dT%H%M")
        (OUT / "build-monitor-LATEST.md").write_text(text)
        (OUT / f"build-monitor-{stamp}.md").write_text(text)
        print(f"Wrote {OUT / 'build-monitor-LATEST.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

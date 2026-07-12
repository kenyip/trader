#!/usr/bin/env python3
"""Read-only progress scoreboard from recent BUILD MoA stamps.

Usage:
  .venv/bin/python scripts/trader_build_progress.py
  .venv/bin/python scripts/trader_build_progress.py --write
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOA = REPO / "reports" / "trader-wakes" / "moa"
OUT_DIR = REPO / "reports" / "readiness"


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


def score_stamp(d: Path) -> dict:
    if not d.is_absolute():
        d = REPO / d
    meta_p = d / "meta.json"
    close = _read(d / "executor-closeout.md") + "\n" + _read(d / "challenger-critique.md")
    latest_bits = close.lower()
    meta = {}
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
    if int(meta.get("completion_contract_version", 1) or 1) >= 2:
        learning = d / "learning-promotion.md"
        complete = complete and learning.exists() and _tracked_on_origin_main(learning)

    types: list[str] = []
    score = 0
    if not complete:
        score = 0
        types = ["failed_or_incomplete"]
    else:
        explicit_scores = [
            int(value)
            for value in re.findall(
                r"(?im)^\s*(?:[-*]\s*)?(?:\|\s*)?(?:progress\s+)?score\s*(?::|\|)\s*\**([0-5])\s*/\s*5",
                close,
            )
        ]
        # Prefer strong evidence of *new* work this stamp
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
        # P4 only if language claims a real after-cost beat (rare)
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
        # pure reconfirm without new artifacts
        if score >= 3 and not re.search(
            r"added |implemented |built |wrote |\.py`|time_bias_lab_|calendar_sim", latest_bits
        ):
            score = min(score, 3 if p3 else 2)
        if explicit_scores:
            score = explicit_scores[-1]

    readiness_blockers = []
    for key, pat in [
        ("after_cost_edge", r"after-cost|5% slip|soft (cost_)?hold"),
        ("b6_paper", r"\bb6\b|multi-session paper"),
        ("b7_shadow", r"\bb7\b|shadow"),
        ("funding", r"unfunded|options level|\$0"),
    ]:
        if re.search(pat, latest_bits):
            readiness_blockers.append(key)

    return {
        "stamp": d.name,
        "complete": complete,
        "executor_exit": ex or None,
        "challenger_exit": ch or None,
        "executor": meta.get("executor"),
        "challenger": meta.get("challenger"),
        "progress_types": types,
        "progress_score_0_5": score,
        "readiness_blockers_mentioned": readiness_blockers,
        "has_merged_seed": (d / "merged-next-seed.md").exists(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    stamps = sorted([p for p in MOA.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)[
        : args.limit
    ]
    rows = [score_stamp(p) for p in reversed(stamps)]  # chronological
    complete = [r for r in rows if r["complete"]]
    avg = (
        sum(r["progress_score_0_5"] for r in complete) / len(complete) if complete else 0.0
    )
    high = sum(1 for r in complete if r["progress_score_0_5"] >= 4)
    low = sum(1 for r in complete if r["progress_score_0_5"] <= 2)

    lines = [
        f"# BUILD progress scoreboard — {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%dT%H%M')}",
        "",
        "Heuristic from MoA closeouts (not a live arm). See `docs/BUILD_PROGRESS_AND_CONFIDENCE.md`.",
        "",
        f"- Stamps scored: **{len(rows)}** (complete **{len(complete)}**)",
        f"- Avg progress score (complete): **{avg:.2f} / 5**",
        f"- High-value runs (≥4): **{high}** · Low-value (≤2): **{low}**",
        "",
        "| stamp | score | types | exits | models |",
        "|---|---:|---|---|---|",
    ]
    for r in rows:
        models = f"{(r.get('executor') or {}).get('model','?')}→{(r.get('challenger') or {}).get('model','?')}"
        lines.append(
            f"| `{r['stamp']}` | {r['progress_score_0_5']} | {', '.join(r['progress_types']) or '—'} | "
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
        "Tonight’s pattern: high coverage/plumbing scores, **L0 for live money** until after-cost edge + B6.",
        "",
    ]
    text = "\n".join(lines) + "\n"
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

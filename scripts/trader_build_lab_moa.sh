#!/usr/bin/env bash
# Dual-model BUILD lab: GPT 5.6 Sol executes discovery/sims → Grok 4.5 challenges.
# Income-focused multi-strategy research with time + direction bias axes.
#
# Usage:
#   scripts/trader_build_lab_moa.sh
#   scripts/trader_build_lab_moa.sh --goal "..."
#   scripts/trader_build_lab_moa.sh --structures put_credit_spread,call_credit_spread,iron_condor
#   scripts/trader_build_lab_moa.sh --executor-only
#   scripts/trader_build_lab_moa.sh --challenger-only --stamp 2026-07-10T2000
#   scripts/trader_build_lab_moa.sh --resume --stamp 2026-07-10T2000
#   scripts/trader_build_lab_moa.sh --finalizer-only --stamp 2026-07-10T2000
#   scripts/trader_build_lab_moa.sh --slot premarket|postclose|daily|evening|weekend|weekly
#
# Env:
#   MOA_EXEC_PROVIDER / MOA_EXEC_MODEL (default openai-codex / gpt-5.6-sol)
#   MOA_CHALL_PROVIDER / MOA_CHALL_MODEL (default xai-oauth / grok-4.5)
#   MOA_MAX_TURNS_EXEC / MOA_MAX_TURNS_CHALL
# Note: Ken 2026-07-10 pin — Sol executor, Grok challenger for BUILD lab.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

EXEC_PROVIDER="${MOA_EXEC_PROVIDER:-openai-codex}"
EXEC_MODEL="${MOA_EXEC_MODEL:-gpt-5.6-sol}"
CHALL_PROVIDER="${MOA_CHALL_PROVIDER:-xai-oauth}"
CHALL_MODEL="${MOA_CHALL_MODEL:-grok-4.5}"
MAX_EXEC="${MOA_MAX_TURNS_EXEC:-60}"
MAX_CHALL="${MOA_MAX_TURNS_CHALL:-35}"
MAX_FINAL="${MOA_MAX_TURNS_FINAL:-45}"
GATE="$REPO/scripts/trader_run_completion_gate.py"

GOAL=""
MODE="both"
STAMP=""
SLOT="daily"
STRUCTURES=""
TOP_SYMBOLS="${MOA_TOP_SYMBOLS:-8}"
MUTANTS="${MOA_MUTANTS:-2}"
SLEEVE="${MOA_SLEEVE_USD:-3000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --) shift ;; # ignore bare -- from `just recipe -- args`
    --goal) GOAL="$2"; shift 2 ;;
    --executor-only) MODE="executor-only"; shift ;;
    --challenger-only) MODE="challenger-only"; shift ;;
    --finalizer-only) MODE="finalizer-only"; shift ;;
    --resume) MODE="resume"; shift ;;
    --stamp) STAMP="$2"; shift 2 ;;
    --slot) SLOT="$2"; shift 2 ;;
    --structures) STRUCTURES="$2"; shift 2 ;;
    --top-symbols) TOP_SYMBOLS="$2"; shift 2 ;;
    --mutants) MUTANTS="$2"; shift 2 ;;
    --sleeve-usd) SLEEVE="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$STAMP" ]]; then
  STAMP="$(date +%Y-%m-%dT%H%M)"
fi

BASE_HEAD=""
RUN_BRANCH=""

# Single-flight: refuse overlapping duals on this repo (stale lock >90m may be stolen)
LOCK_DIR="$REPO/.cache/platform"
mkdir -p "$LOCK_DIR"
LOCK_FILE="$LOCK_DIR/build_lab.lock"
if [[ -f "$LOCK_FILE" ]]; then
  age=$(python3 -c "import time; from pathlib import Path; p=Path(r'$LOCK_FILE'); print(int(time.time()-p.stat().st_mtime) if p.exists() else 99999)")
  if [[ "$age" -lt 5400 ]]; then
    echo "BUILD lab already running (lock age ${age}s). Skip. See $LOCK_FILE" >&2
    exit 0
  fi
  echo "WARN: stealing stale build_lab.lock age ${age}s" >&2
fi
echo "pid=$$ ts=$(date -Iseconds) slot=${SLOT:-?} mode=${MODE:-?}" >"$LOCK_FILE"
cleanup_lock() { rm -f "$LOCK_FILE" 2>/dev/null || true; }
trap cleanup_lock EXIT

if [[ "$MODE" == "both" || "$MODE" == "executor-only" ]]; then
  if [[ ! -x "$GATE" ]]; then
    echo "ERROR: completion gate is missing or not executable: $GATE" >&2
    exit 1
  fi
  python3 "$GATE" preflight --repo "$REPO"
  BASE_HEAD="$(git rev-parse HEAD)"
  RUN_BRANCH="trader/run-${STAMP}"
  if git show-ref --verify --quiet "refs/heads/$RUN_BRANCH"; then
    echo "ERROR: run branch already exists: $RUN_BRANCH" >&2
    exit 1
  fi
  git switch -c "$RUN_BRANCH"
fi

case "$SLOT" in
  premarket)
    SLOT_FOCUS="Pre-market BUILD: refresh research rank; prefer defined-risk evolve; prep RTH paper conditions; no live."
    ;;
  postclose)
    SLOT_FOCUS="Post-close BUILD: free multi-structure discovery + falsify new SHIP; rotate away from last structure if tunnel risk."
    ;;
  evening)
    SLOT_FOCUS="Evening BUILD: close a structure/time/direction gap or implement one missing sim class scaffold if justified."
    ;;
  weekend)
    SLOT_FOCUS="Weekend lab: broader coverage pass — under-simmed structures, time-bias grids, systems improvements."
    ;;
  weekly)
    SLOT_FOCUS="Weekly critic: coverage matrix, sticky bad DNA, ship-bar honesty, one systems improvement."
    ;;
  daily|*)
    SLOT_FOCUS="Daily income lab: research → multi-structure sims → quality falsify → one capital-honest NEXT."
    ;;
esac

STRUCT_LINE="catalog-free exploration across any liquid symbol and any strategy DNA; defined-risk is required for a \$3k capital candidate, not for forming or falsifying research hypotheses"
EVOLVE_STRUCT_ARGS=""
if [[ -n "$STRUCTURES" ]]; then
  STRUCT_LINE="structures focus: ${STRUCTURES}"
  # shell-split structures on comma into evolve --structures args
  EVOLVE_STRUCT_ARGS="$STRUCTURES"
fi

if [[ -z "$GOAL" ]]; then
  GOAL="BUILD LAB (${SLOT}). Discover a robust, paper-testable edge for the \$${SLEEVE} sleeve. ${SLOT_FOCUS} Explore creatively across symbols, structures, volatility/time/direction/regime, entries, exits, management, and stand-aside logic. ${STRUCT_LINE}. Use valid evidence and falsify promotion candidates with relevant B3/B4 + ml/dd gates. Paper/research only. No live/agentic/shadow promote. Leave ONE highest-information NEXT seed."
fi

EVOLVE_HINT="just evolve-tick --apply --top-symbols $TOP_SYMBOLS --mutants $MUTANTS --max-population 36 --sleeve-usd $SLEEVE"
if [[ -n "$EVOLVE_STRUCT_ARGS" ]]; then
  EVOLVE_HINT+=" --structures ${EVOLVE_STRUCT_ARGS//,/ }"
fi

MOA_DIR="reports/trader-wakes/moa/${STAMP}"
mkdir -p "$MOA_DIR/prompts" reports/trader-wakes reports/readiness

if [[ "$MODE" == "challenger-only" || "$MODE" == "finalizer-only" || "$MODE" == "resume" ]]; then
  if [[ ! -f "$MOA_DIR/meta.json" ]]; then
    echo "ERROR: recovery mode requires existing $MOA_DIR/meta.json" >&2
    exit 1
  fi
  BASE_HEAD="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("base_head", ""))' "$MOA_DIR/meta.json")"
  RUN_BRANCH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("run_branch", ""))' "$MOA_DIR/meta.json")"
  if [[ -z "$BASE_HEAD" || -z "$RUN_BRANCH" ]]; then
    echo "ERROR: stamp $STAMP predates the recoverable completion contract" >&2
    exit 1
  fi
  if [[ "$(git branch --show-current)" != "$RUN_BRANCH" ]]; then
    echo "ERROR: recovery must run from $RUN_BRANCH (current: $(git branch --show-current))" >&2
    exit 1
  fi
fi

# Preflight coverage (non-fatal)
set +e
.venv/bin/python scripts/trader_income_coverage.py --write >/dev/null 2>"$MOA_DIR/coverage-preflight.err"
set -e

if [[ "$MODE" == "both" || "$MODE" == "executor-only" ]]; then
python3 - <<PY
import json
from pathlib import Path
meta = {
  "stamp": "$STAMP",
  "lab": "income_build_lab",
  "completion_contract_version": 2,
  "slot": "$SLOT",
  "goal": """$GOAL""",
  "mode": "$MODE",
  "executor": {"provider": "$EXEC_PROVIDER", "model": "$EXEC_MODEL"},
  "challenger": {"provider": "$CHALL_PROVIDER", "model": "$CHALL_MODEL"},
  "finalizer": {"provider": "$EXEC_PROVIDER", "model": "$EXEC_MODEL"},
  "base_head": "$BASE_HEAD",
  "run_branch": "$RUN_BRANCH",
  "structures": """$STRUCTURES""",
  "top_symbols": int("$TOP_SYMBOLS"),
  "mutants": int("$MUTANTS"),
  "sleeve_usd": float("$SLEEVE"),
  "repo": "$REPO",
}
Path("$MOA_DIR/meta.json").write_text(json.dumps(meta, indent=2) + "\n")
PY
fi

# --- Executor prompt ---
cat > "$MOA_DIR/prompts/01-executor.txt" <<EOF
MOA BUILD LAB — PHASE 1 EXECUTOR (ONLY writer) — GPT 5.6 Sol.
You are Trader. Load skill trader-self-evolution.
Also read: docs/BUILD_LAB_ENVIRONMENT.md, docs/INCOME_STRATEGY_COVERAGE.md,
reports/readiness/income-coverage-LATEST.md (if present),
reports/trader-wakes/LATEST.md, reports/readiness/LATEST.md.

PHASE: BUILD. Sleeve USD $SLEEVE. Paper/research only.
Models: YOU = GPT 5.6 Sol executor. Grok 4.5 will challenge after you. Do not wait for Grok mid-loop.

GOAL:
$GOAL

SLOT: $SLOT
STRUCTURE FOCUS: $STRUCT_LINE
DEFAULT EVOLVE KNOBS: --top-symbols $TOP_SYMBOLS --mutants $MUTANTS --sleeve-usd $SLEEVE

OPERATING CONTRACT (goal-driven, not a checklist):
1) Orient from the latest evidence, then choose ONE highest-information loop. You may take or supersede NEXT and may propose an axis absent from prior reports.
2) State the hypothesis and what would falsify it. Check only the validity prerequisites needed for that claim. If one path is data-blocked, either repair it or pursue a valid independent path; do not let one missing dataset freeze the whole research program.
3) Use any relevant combination of research, simulation, tests, negative controls, new strategy DNA, new tools, or cross-symbol/time/regime comparisons. Commands below are available examples, never mandatory ritual:
   - just research-tick-paper --sleeve-usd $SLEEVE
   - $EVOLVE_HINT
   - .venv/bin/python scripts/pcs_regime_stress.py --hyps "<ids>" --out .cache/platform/stress_regime_lab_${STAMP}.json
   - .venv/bin/python scripts/pcs_cost_stress.py --hyps "<ids>" --out .cache/platform/stress_cost_lab_${STAMP}.json
4) Promotion claims require relevant B3/B4, non-vacuous after-cost evidence, and explicit risk. Proxy-only experiments are allowed for discovery when labeled, but cannot earn L1 without evidence appropriate to the claim. Tests must exercise behavior and failure boundaries relevant to the claim; avoid self-fulfilling fixtures or assertions that merely restate implementation output.
5) Compare against the CURRENT living leader from readiness. If none exists, use explicit absolute risk/evidence gates and say there is no leader; historical candidates are context, not seats.
6) A null result, rejected family, discovered flaw, or novel capability is valid progress when it changes what should be tried next. Include a one-line freedom audit: did any prompt rule or tool constraint block a higher-information valid experiment?
7) Durable executor residue (this is a PARTIAL phase, not a completed run):
   - reports/trader-wakes/moa/${STAMP}/executor-closeout.md
   - reports/trader-wakes/${STAMP}-moa-exec.md
   - Update reports/trader-wakes/LATEST.md + prepend INDEX.md
   - Update reports/readiness/LATEST.md if phase/B checks change
   - Refresh coverage: .venv/bin/python scripts/trader_income_coverage.py --write
8) Do not commit, push, merge, or claim RUN COMPLETE in this phase. The challenger must critique and the finalizer must repair, verify, promote learning, and prepare clean integration.

HARD STOPS:
- No live / broker login / agentic arm / shadow auto-promote
- No diversify-for-fear capital seats
- No vanity SHIP → capital path without B3+B4 + competitive ml/dd
- No volume for its own sake; run the smallest experiment that can change the decision
- A fail-closed data boundary blocks dependent promotion claims, not unrelated creative exploration
- No stale leader, mixed-population label, incomplete ranking, or proxy-cost claim may survive into NEXT unmarked
- Do not invent numbers — cite JSON/CSV paths

Close with: MOA_EXEC_DONE and paths written.
EOF

# --- Challenger prompt ---
cat > "$MOA_DIR/prompts/02-challenger.txt" <<EOF
MOA BUILD LAB — PHASE 2 CHALLENGER (read-only judgment) — Grok 4.5.
You are Trader critic (Grok 4.5). Load skill trader-self-evolution.
Read docs/BUILD_LAB_ENVIRONMENT.md and docs/INCOME_STRATEGY_COVERAGE.md.

PHASE: BUILD. Sleeve USD $SLEEVE.
You do NOT evolve --apply, do NOT broker, do NOT arm live.
You MAY read files and run read-only jq/python inspects.

GOAL of executor wake:
$GOAL

READ FIRST:
- reports/trader-wakes/moa/${STAMP}/meta.json
- reports/trader-wakes/moa/${STAMP}/executor-closeout.md
- reports/trader-wakes/${STAMP}-moa-exec.md or LATEST
- reports/readiness/income-coverage-LATEST.md
- Any stress JSON paths cited by executor
- reports/readiness/LATEST.md

RUBRIC (PASS/FAIL + one line):
1. Goal progress: did the wake materially improve the chance of finding a robust paper-testable edge?
2. Creativity and independence: original hypothesis/axis or a justified reason to continue prior NEXT; no familiar-recipe tunnel
3. Claim validity: only prerequisites relevant to the chosen experiment; invalid evidence fails closed or the claim is narrowed honestly
4. Evidence and test quality: real tools/tests/sims with cited paths; tests include useful behavioral/boundary/negative checks rather than mirroring the implementation; observed/proxy semantics, populations, and rankings are labeled correctly
5. Falsification: clear failure condition and honest promote/reject/learn judgment, including negative controls where useful
6. Capital honesty: current living leader and relevant B3/B4/after-cost/risk gates before any seat; stale references are not seats
7. Research freedom: a blocked data path or prompt rule did not unnecessarily freeze unrelated valid exploration; flag any removable restriction
8. ONE highest-information NEXT seed; no live/shadow promotion

OUTPUT:
1) reports/trader-wakes/moa/${STAMP}/challenger-critique.md
2) reports/trader-wakes/moa/${STAMP}/merged-next-seed.md
3) reports/trader-wakes/${STAMP}-moa-merge.md
4) Update LATEST.md to merge summary; prepend INDEX.md
5) Patch readiness NEXT only if wrong
6) This is a PARTIAL critique phase. Do not commit, push, merge, or claim RUN COMPLETE. The Sol finalizer will repair accepted findings, run verification, promote learning, and prepare integration.

HARD STOPS: no evolve --apply; no live; challenge uncited claims.

Close with: MOA_CHALL_DONE and paths written.
EOF

# --- Finalizer prompt ---
cat > "$MOA_DIR/prompts/03-finalizer.txt" <<EOF
MOA BUILD LAB — PHASE 3 FINALIZER (single writer) — GPT 5.6 Sol.
You are Trader finalizer. Load skill trader-self-evolution and enforce its completion contract.

This phase exists to turn executor work + challenger judgment into a complete, durable, verifiable run. It is not another broad discovery loop.

READ FIRST:
- reports/trader-wakes/moa/${STAMP}/meta.json
- reports/trader-wakes/moa/${STAMP}/executor-closeout.md
- reports/trader-wakes/moa/${STAMP}/challenger-critique.md
- reports/trader-wakes/moa/${STAMP}/merged-next-seed.md
- reports/trader-wakes/${STAMP}-moa-exec.md
- reports/trader-wakes/${STAMP}-moa-merge.md
- reports/trader-wakes/LATEST.md
- reports/readiness/LATEST.md
- git status and the complete diff from base $BASE_HEAD

FINALIZATION CONTRACT:
1) Reconcile every material challenger finding. Repair code, tests, evidence labels, readiness, reports, or NEXT when needed. If a finding is rejected, explain why with evidence in learning-promotion.md.
2) Close the scoped work. Do not leave a claim-invalidating defect, unstated TODO, stale generated surface, or misleading readiness label behind a completion claim.
3) Run focused behavioral/boundary/negative-control tests plus the full suite: .venv/bin/python -m unittest discover -s tests. Fix failures; never weaken a useful test or normalize red to finish.
4) Inspect the complete diff for unintended files, generated debris, private positions, credentials, tokens, raw secrets, or stale contradictory docs. Remove only run-created debris; preserve evidence.
5) Promote learning:
   - dated outcome/current project truth → repo docs/reports;
   - reusable procedure/pitfall/test lesson → trader-self-evolution or narrow skill;
   - compact stable stance/preference/routing fact → trader profile memory;
   - rewrite/remove superseded guidance instead of stacking contradictions.
6) Write reports/trader-wakes/moa/${STAMP}/learning-promotion.md with exact headings:
   - ## VERIFICATION — commands and exact results
   - ## DURABLE — files/skills/memory updated, or evidence-backed no-promotion reason
   - ## LESSON — what future Trader now knows/can do
   - ## NEXT — exactly one seed or DIMINISHING_RETURNS
   Include accepted/rejected critique findings and state that integration is pending the deterministic wrapper gate.
7) Regenerate every touched derived report and ensure executor/challenger/merge/LATEST/INDEX/readiness surfaces agree.
8) Do NOT commit, push, merge, switch branches, edit .gitignore merely to hide residue, or claim RUN COMPLETE. The deterministic wrapper performs integration only after your green handoff.

If anything cannot be closed safely, state RUN INCOMPLETE with the exact blocker and recovery step, and exit non-successfully rather than printing readiness.

Close only when ready for deterministic integration with: MOA_FINALIZE_READY and the verification + learning paths.
EOF

run_exec() {
  echo "=== BUILD LAB EXECUTOR: $EXEC_PROVIDER / $EXEC_MODEL (slot=$SLOT) ==="
  set +e
  hermes -p trader chat \
    -q "$(cat "$MOA_DIR/prompts/01-executor.txt")" \
    --provider "$EXEC_PROVIDER" \
    -m "$EXEC_MODEL" \
    --max-turns "$MAX_EXEC" \
    2>&1 | tee "$MOA_DIR/executor-session.log"
  ec=${PIPESTATUS[0]}
  set -e
  echo "$ec" > "$MOA_DIR/executor-exit.txt"
  if [[ $ec -ne 0 ]]; then
    echo "WARN: executor exit $ec — challenger may still review partial residue" >&2
  fi
}

run_chall() {
  if [[ ! -f "$MOA_DIR/executor-closeout.md" ]] && [[ ! -f "reports/trader-wakes/${STAMP}-moa-exec.md" ]]; then
    echo "ERROR: no executor closeout under $MOA_DIR or ${STAMP}-moa-exec.md" >&2
    exit 1
  fi
  echo "=== BUILD LAB CHALLENGER: $CHALL_PROVIDER / $CHALL_MODEL ==="
  set +e
  hermes -p trader chat \
    -q "$(cat "$MOA_DIR/prompts/02-challenger.txt")" \
    --provider "$CHALL_PROVIDER" \
    -m "$CHALL_MODEL" \
    --max-turns "$MAX_CHALL" \
    2>&1 | tee "$MOA_DIR/challenger-session.log"
  ec=${PIPESTATUS[0]}
  set -e
  echo "$ec" > "$MOA_DIR/challenger-exit.txt"
  return "$ec"
}

run_finalize() {
  [[ "$(cat "$MOA_DIR/executor-exit.txt" 2>/dev/null)" == "0" ]] || {
    echo "ERROR: executor did not exit 0; run remains incomplete" >&2
    return 1
  }
  [[ "$(cat "$MOA_DIR/challenger-exit.txt" 2>/dev/null)" == "0" ]] || {
    echo "ERROR: challenger did not exit 0; run remains incomplete" >&2
    return 1
  }
  for required in executor-closeout.md challenger-critique.md merged-next-seed.md; do
    [[ -f "$MOA_DIR/$required" ]] || {
      echo "ERROR: missing $MOA_DIR/$required; run remains incomplete" >&2
      return 1
    }
  done

  echo "=== BUILD LAB FINALIZER: $EXEC_PROVIDER / $EXEC_MODEL ==="
  set +e
  hermes -p trader chat \
    -q "$(cat "$MOA_DIR/prompts/03-finalizer.txt")" \
    --provider "$EXEC_PROVIDER" \
    -m "$EXEC_MODEL" \
    --max-turns "$MAX_FINAL" \
    2>&1 | tee "$MOA_DIR/finalizer-session.log"
  ec=${PIPESTATUS[0]}
  set -e
  mkdir -p "$LOCK_DIR/completion"
  echo "$ec" > "$LOCK_DIR/completion/${STAMP}-finalizer-exit.txt"
  if [[ $ec -eq 0 ]] && ! grep -q "MOA_FINALIZE_READY" "$MOA_DIR/finalizer-session.log"; then
    echo "ERROR: finalizer exited 0 without MOA_FINALIZE_READY; run remains incomplete" >&2
    return 1
  fi
  return "$ec"
}

integrate_run() {
  echo "=== BUILD LAB DETERMINISTIC VERIFICATION + INTEGRATION ==="
  [[ "$(git branch --show-current)" == "$RUN_BRANCH" ]] || {
    echo "ERROR: expected $RUN_BRANCH before integration" >&2
    return 1
  }

  .venv/bin/python -m unittest discover -s tests
  git diff --check
  git add -A
  python3 "$GATE" prepare \
    --repo "$REPO" \
    --stamp "$STAMP" \
    --base-head "$BASE_HEAD" \
    --run-branch "$RUN_BRANCH"

  git commit -m "trader: complete BUILD lab ${STAMP}"
  RUN_HEAD="$(git rev-parse HEAD)"
  git push -u origin "$RUN_BRANCH"

  git switch main
  [[ "$(git rev-parse HEAD)" == "$BASE_HEAD" ]] || {
    echo "ERROR: local main changed during run; preserving $RUN_BRANCH for review" >&2
    return 1
  }
  python3 "$GATE" preflight --repo "$REPO" >/dev/null

  git merge --ff-only "$RUN_BRANCH"
  git push origin main
  mkdir -p "$LOCK_DIR/completion"
  python3 "$GATE" postflight \
    --repo "$REPO" \
    --stamp "$STAMP" \
    --base-head "$BASE_HEAD" \
    | tee "$LOCK_DIR/completion/${STAMP}.json"

  git branch -d "$RUN_BRANCH"
  git push origin --delete "$RUN_BRANCH" >/dev/null 2>&1 || true
  echo "RUN COMPLETE: $STAMP integrated as $RUN_HEAD and verified on origin/main"
}

case "$MODE" in
  both)
    run_exec
    run_chall
    run_finalize
    integrate_run
    ;;
  executor-only)
    run_exec
    echo "PARTIAL PHASE COMPLETE: executor residue written; RUN INCOMPLETE until challenge, finalization, verification, and integration"
    ;;
  challenger-only)
    run_chall
    echo "PARTIAL PHASE COMPLETE: challenger residue written; RUN INCOMPLETE until finalization, verification, and integration"
    ;;
  resume)
    run_chall
    run_finalize
    integrate_run
    ;;
  finalizer-only)
    run_finalize
    integrate_run
    ;;
esac

echo
echo "=== BUILD LAB MoA status ==="
echo "stamp:  $STAMP"
echo "slot:   $SLOT"
echo "dir:    $REPO/$MOA_DIR"
echo "meta:   $MOA_DIR/meta.json"
ls -la "$MOA_DIR" || true
echo "Front door: just trader-wakes"
echo "Coverage:   just trader-income-coverage"

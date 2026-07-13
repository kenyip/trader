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
#   scripts/trader_build_lab_moa.sh --slot LABEL  # debug/recovery metadata override only
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
COMPOUNDING="$REPO/scripts/trader_build_compounding.py"
GOAL_FILE="$REPO/configs/build_lab_free_goal.txt"

GOAL=""
MODE="both"
STAMP=""
STAMP_EXPLICIT=0
AUTO_RECOVERY=0
SLOT=""
SLOT_SOURCE="auto"
GOAL_SOURCE="canonical"
SLOT_EXPLICIT=0
GOAL_EXPLICIT=0
STRUCTURES=""
TOP_SYMBOLS="${MOA_TOP_SYMBOLS:-8}"
MUTANTS="${MOA_MUTANTS:-2}"
SLEEVE="${MOA_SLEEVE_USD:-3000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --) shift ;; # ignore bare -- from `just recipe -- args`
    --goal) GOAL="$2"; GOAL_SOURCE="override"; GOAL_EXPLICIT=1; shift 2 ;;
    --executor-only) MODE="executor-only"; shift ;;
    --challenger-only) MODE="challenger-only"; shift ;;
    --finalizer-only) MODE="finalizer-only"; shift ;;
    --resume) MODE="resume"; shift ;;
    --stamp) STAMP="$2"; STAMP_EXPLICIT=1; shift 2 ;;
    --slot) SLOT="$2"; SLOT_SOURCE="override"; SLOT_EXPLICIT=1; shift 2 ;;
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

# A zero-input launch on an interrupted run branch resumes that exact stamp.
# This is recovery, not caller strategy judgment. Explicit modes/stamps retain
# their diagnostic meaning and never get silently rewritten.
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [[ "$MODE" == "both" && "$STAMP_EXPLICIT" == "0" && "$CURRENT_BRANCH" == trader/run-* ]]; then
  STAMP="${CURRENT_BRANCH#trader/run-}"
  MODE="resume"
  AUTO_RECOVERY=1
  echo "AUTO-RECOVERY: resuming interrupted BUILD stamp $STAMP from $CURRENT_BRANCH" >&2
fi
if [[ -z "$STAMP" ]]; then
  STAMP="$(date +%Y-%m-%dT%H%M)"
fi

# Caller supplies no judgment by default. Time/session is metadata that Trader
# evaluates alongside SOUL, readiness, prior learning, and current market data.
if [[ -z "$SLOT" ]]; then
  weekday="$(date +%u)"
  hour="$(date +%H)"
  if (( weekday >= 6 )); then
    SLOT="weekend"
  elif (( 10#$hour < 6 )); then
    SLOT="premarket"
  elif (( 10#$hour < 13 )); then
    SLOT="rth"
  elif (( 10#$hour < 17 )); then
    SLOT="postclose"
  else
    SLOT="offhours"
  fi
fi

if [[ -z "$GOAL" ]]; then
  if [[ ! -s "$GOAL_FILE" ]]; then
    echo "ERROR: canonical Trader program goal missing or empty: $GOAL_FILE" >&2
    exit 1
  fi
  GOAL="$(<"$GOAL_FILE")"
fi

# Debug/test hook: assembles the exact no-input launch context without starting
# a branch, lock, model session, or market action.
if [[ "${TRADER_BUILD_CONTEXT_ONLY:-0}" == "1" ]]; then
  printf 'goal_source=%s\ncontext=%s\ncontext_source=%s\nmode=%s\nstamp=%s\ngoal_file=%s\n--- CANONICAL GOAL ---\n%s\n--- END GOAL ---\n' \
    "$GOAL_SOURCE" "$SLOT" "$SLOT_SOURCE" "$MODE" "$STAMP" "$GOAL_FILE" "$GOAL"
  exit 0
fi

BASE_HEAD=""
RUN_BRANCH=""
PHASE="startup"

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
on_exit() {
  ec=$?
  cleanup_lock
  if [[ $ec -ne 0 ]]; then
    current="$(git branch --show-current 2>/dev/null || true)"
    echo "RUN INCOMPLETE: stamp=$STAMP phase=$PHASE exit=$ec branch=${current:-unknown}" >&2
    if [[ -n "$RUN_BRANCH" && "$current" == "$RUN_BRANCH" && -f "reports/trader-wakes/moa/$STAMP/meta.json" ]]; then
      echo "RECOVERY: scripts/trader_build_lab_moa.sh --stamp $STAMP --resume" >&2
    else
      echo "RECOVERY: resolve the reported preflight/startup blocker, return to clean synchronized main, and rerun" >&2
    fi
  fi
}
trap on_exit EXIT

if [[ "$MODE" == "both" || "$MODE" == "executor-only" ]]; then
  if [[ ! -x "$GATE" ]]; then
    echo "ERROR: completion gate is missing or not executable: $GATE" >&2
    exit 1
  fi
  PHASE="preflight"
  python3 "$GATE" preflight --repo "$REPO"
  BASE_HEAD="$(git rev-parse HEAD)"
  RUN_BRANCH="trader/run-${STAMP}"
  if git show-ref --verify --quiet "refs/heads/$RUN_BRANCH"; then
    echo "ERROR: run branch already exists: $RUN_BRANCH" >&2
    exit 1
  fi
  git switch -c "$RUN_BRANCH"
  PHASE="executor"
fi

STRUCT_LINE="catalog-free exploration across any liquid symbol and any strategy DNA; defined-risk is required for a \$3k capital candidate, not for forming or falsifying research hypotheses"
EVOLVE_STRUCT_ARGS=""
if [[ -n "$STRUCTURES" ]]; then
  STRUCT_LINE="structures focus override (debug/recovery): ${STRUCTURES}"
  EVOLVE_STRUCT_ARGS="$STRUCTURES"
fi

EVOLVE_HINT="just evolve-tick --apply --top-symbols $TOP_SYMBOLS --mutants $MUTANTS --max-population 36 --sleeve-usd $SLEEVE"
if [[ -n "$EVOLVE_STRUCT_ARGS" ]]; then
  EVOLVE_HINT+=" --structures ${EVOLVE_STRUCT_ARGS//,/ }"
fi

MOA_DIR="reports/trader-wakes/moa/${STAMP}"
mkdir -p "$MOA_DIR/prompts" reports/trader-wakes reports/readiness

if [[ "$MODE" == "challenger-only" || "$MODE" == "finalizer-only" || "$MODE" == "resume" || "$MODE" == "integrate-only" ]]; then
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
  # Recovery reuses the original assembled goal/context unless explicitly
  # overridden for diagnosis. NEXT and strategy judgment still belong to Trader.
  if (( GOAL_EXPLICIT == 0 )); then
    GOAL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("goal", ""))' "$MOA_DIR/meta.json")"
    GOAL_SOURCE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("goal_source", "canonical"))' "$MOA_DIR/meta.json")"
  fi
  if (( SLOT_EXPLICIT == 0 )); then
    SLOT="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("context", d.get("slot", "recovery")))' "$MOA_DIR/meta.json")"
    SLOT_SOURCE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("context_source", "recovered"))' "$MOA_DIR/meta.json")"
  fi
  if [[ "$(git branch --show-current)" != "$RUN_BRANCH" ]]; then
    echo "ERROR: recovery must run from $RUN_BRANCH (current: $(git branch --show-current))" >&2
    exit 1
  fi
  if [[ "$AUTO_RECOVERY" == "1" && "$(git rev-parse HEAD)" != "$BASE_HEAD" ]]; then
    if [[ -n "$(git status --porcelain)" ]]; then
      echo "ERROR: interrupted committed run branch is dirty; preserve it and use explicit recovery" >&2
      exit 1
    fi
    MODE="integrate-only"
    echo "AUTO-RECOVERY: committed run detected; validating and continuing integration only" >&2
  fi
fi

# A committed recovery must remain byte-clean until deterministic integration.
if [[ "$MODE" != "integrate-only" ]]; then

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
  "completion_contract_version": 3,
  "context": "$SLOT",
  "context_source": "$SLOT_SOURCE",
  "goal_source": "$GOAL_SOURCE",
  "goal_file": "$GOAL_FILE",
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

# Machine-readable cumulative orientation is generated from prior integrated
# handoffs. It informs Trader without selecting a symbol, structure, or loop.
python3 "$COMPOUNDING" context \
  --repo "$REPO" --stamp "$STAMP" --out "$MOA_DIR/orientation.json" >/dev/null

# --- Executor prompt ---
cat > "$MOA_DIR/prompts/01-executor.txt" <<EOF
MOA BUILD LAB — PHASE 1 EXECUTOR (ONLY writer) — GPT 5.6 Sol.
You are Trader. Your profile SOUL is authoritative; load skill trader-self-evolution.
Before choosing, orient from the canonical goal above plus:
- docs/TRADER_PLATFORM_GOAL.md, docs/TRADER_LOOPS.md,
  docs/AGENTIC_AUTONOMY_POLICY.md, docs/GO_LIVE_READINESS.md
- docs/BUILD_LAB_ENVIRONMENT.md, docs/INCOME_STRATEGY_COVERAGE.md
- reports/readiness/income-coverage-LATEST.md (if present)
- reports/trader-wakes/LATEST.md, reports/readiness/LATEST.md
- reports/trader-wakes/moa/${STAMP}/orientation.json (closed families, prior novelty, redirect signal)
- hypothesis registry, learn/evolve audits, coverage, current local time,
  market/session state, and relevant current data.
The caller supplied no loop judgment unless meta explicitly says override.

PHASE: BUILD. Sleeve USD $SLEEVE. Paper/research only.
Models: YOU = GPT 5.6 Sol executor. Grok 4.5 will challenge after you. Do not wait for Grok mid-loop.

GOAL:
$GOAL

CALLER CONTEXT (internally derived metadata, not an assignment): $SLOT (source=$SLOT_SOURCE)
CANONICAL GOAL SOURCE: $GOAL_SOURCE ($GOAL_FILE)
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
6) A null result, rejected family, discovered flaw, or novel capability is valid progress when it changes what should be tried next. Honor orientation.json: closed families require a genuinely new evidence class to reopen, redirect_required forbids an unchanged repeat, and research_routes prevents a blocked forward option archive from globally forcing DIMINISHING_RETURNS while historical/capability work remains informative; it does not forbid an honest information-exhaustion stop. It is context, never an allowlist or a recipe selector. Include a one-line freedom audit.
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
- reports/trader-wakes/moa/${STAMP}/orientation.json
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
7) Write reports/trader-wakes/moa/${STAMP}/compounding.json using the stable schema in docs/BUILD_LAB_ENVIRONMENT.md. Every useful delta needs a unique novelty_key and changed artifact paths; repaired critic findings need machinery + test paths, while rejected findings need evidence-backed rationale. Use DIMINISHING_RETURNS when no measurable delta exists.
8) Regenerate every touched derived report and ensure executor/challenger/merge/LATEST/INDEX/readiness surfaces agree.
9) Do NOT commit, push, merge, switch branches, edit .gitignore merely to hide residue, or claim RUN COMPLETE. The deterministic wrapper performs integration only after your green handoff.

If anything cannot be closed safely, state RUN INCOMPLETE with the exact blocker and recovery step, and exit non-successfully rather than printing readiness.

Close only when ready for deterministic integration with: MOA_FINALIZE_READY and the verification + learning paths.
EOF

fi  # generation is skipped for clean committed integrate-only recovery

run_exec() {
  PHASE="executor"
  echo "=== BUILD LAB EXECUTOR: $EXEC_PROVIDER / $EXEC_MODEL (context=$SLOT, source=$SLOT_SOURCE) ==="
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
  PHASE="challenger"
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

  PHASE="finalizer"
  echo "=== BUILD LAB FINALIZER: $EXEC_PROVIDER / $EXEC_MODEL ==="
  baseline="$LOCK_DIR/completion/${STAMP}-finalizer-baseline.json"
  mkdir -p "$LOCK_DIR/completion"
  python3 "$COMPOUNDING" snapshot \
    --repo "$REPO" --stamp "$STAMP" --out "$baseline" >/dev/null
  set +e
  hermes -p trader chat \
    -q "$(cat "$MOA_DIR/prompts/03-finalizer.txt")" \
    --provider "$EXEC_PROVIDER" \
    -m "$EXEC_MODEL" \
    --max-turns "$MAX_FINAL" \
    2>&1 | tee "$MOA_DIR/finalizer-session.log"
  ec=${PIPESTATUS[0]}
  set -e
  echo "$ec" > "$LOCK_DIR/completion/${STAMP}-finalizer-exit.txt"
  [[ $ec -eq 0 ]] || return "$ec"
  # Session prose is deliberately ignored: role readiness requires changed,
  # schema-valid learning and measurable handoff artifacts.
  python3 "$COMPOUNDING" validate-handoff \
    --repo "$REPO" --stamp "$STAMP" --base-head "$BASE_HEAD" --baseline "$baseline"
}

integrate_run() {
  PHASE="integration"
  echo "=== BUILD LAB DETERMINISTIC VERIFICATION + INTEGRATION ==="
  [[ "$(git branch --show-current)" == "$RUN_BRANCH" ]] || {
    echo "ERROR: expected $RUN_BRANCH before integration" >&2
    return 1
  }

  .venv/bin/python -m unittest discover -s tests
  git diff --check
  if [[ "$(git rev-parse HEAD)" == "$BASE_HEAD" ]]; then
    git add -A
    python3 "$GATE" prepare \
      --repo "$REPO" \
      --stamp "$STAMP" \
      --base-head "$BASE_HEAD" \
      --run-branch "$RUN_BRANCH"
    git commit -m "trader: complete BUILD lab ${STAMP}"
  else
    git merge-base --is-ancestor "$BASE_HEAD" HEAD || {
      echo "ERROR: recovered run HEAD does not descend from base; preserving branch" >&2
      return 1
    }
    [[ -z "$(git status --porcelain)" ]] || {
      echo "ERROR: recovered committed run branch is dirty; preserving branch" >&2
      return 1
    }
    python3 "$COMPOUNDING" validate-handoff \
      --repo "$REPO" --stamp "$STAMP" --base-head "$BASE_HEAD"
    echo "AUTO-RECOVERY: reusing existing verified run commit $(git rev-parse HEAD)" >&2
  fi
  RUN_HEAD="$(git rev-parse HEAD)"
  git push -u origin "$RUN_BRANCH"

  git switch main
  [[ "$(git rev-parse HEAD)" == "$BASE_HEAD" || "$(git rev-parse HEAD)" == "$RUN_HEAD" ]] || {
    echo "ERROR: local main changed during run; preserving $RUN_BRANCH for review" >&2
    return 1
  }
  if [[ "$(git rev-parse HEAD)" == "$BASE_HEAD" ]]; then
    python3 "$GATE" preflight --repo "$REPO" >/dev/null
    git merge --ff-only "$RUN_BRANCH"
  fi
  git push origin main
  mkdir -p "$LOCK_DIR/completion"
  python3 "$GATE" postflight \
    --repo "$REPO" \
    --stamp "$STAMP" \
    --base-head "$BASE_HEAD" \
    --run-head "$RUN_HEAD" \
    --receipt ".cache/platform/completion/${STAMP}.json"

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
  integrate-only)
    integrate_run
    ;;
esac

echo
echo "=== BUILD LAB MoA status ==="
echo "stamp:  $STAMP"
echo "context: $SLOT ($SLOT_SOURCE)"
echo "dir:    $REPO/$MOA_DIR"
echo "meta:   $MOA_DIR/meta.json"
ls -la "$MOA_DIR" || true
echo "Front door: just trader-wakes"
echo "Coverage:   just trader-income-coverage"

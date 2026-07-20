#!/usr/bin/env bash
# Autonomous continuum tick for Desk B (Trader).
#
# Keeps next-step work moving without Ken in the loop:
#   1) single-flight (skip if BUILD already running)
#   2) refresh Strategy Engine routes + handoff (freshness gate)
#   3) NEXT_SURVIVOR → one zero-input BUILD MoA lab
#   4) NO_QUALIFIED  → cheap multi-symbol quality work + dry paper residual
#   5) never live / shadow / arm / execute-paper
#
# Exit 0 on expected no-ops (no survivor, already running, dirty foreign WIP).
# Exit nonzero only on unexpected infrastructure failures.
set -euo pipefail

REPO="${TRADER_REPO:-/Users/jarvis/dev/trader}"
cd "$REPO"

PY="${TRADER_PYTHON:-$REPO/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "trader_autonomous_tick: missing $PY" >&2
  exit 1
fi

LOCK_DIR="$REPO/.cache/platform"
LOCK_FILE="$LOCK_DIR/build_lab.lock"
RECEIPT_DIR="$REPO/.cache/platform/autonomous"
RECEIPT="$RECEIPT_DIR/tick_LATEST.json"
ROUTES="$REPO/.cache/strategy-engine/routes-latest.json"
PANEL="$REPO/.cache/strategy-engine/panel-latest.csv"
HANDOFF_REPORT="$REPO/.cache/strategy-engine/latest.json"
MOA="$REPO/scripts/trader_build_lab_moa.sh"
ROUTE_BATCH="$REPO/scripts/trader_strategy_engine_route_batch.py"
HANDOFF_PY="$REPO/scripts/trader_strategy_engine_handoff.py"
MULTI="$REPO/scripts/trader_multi_symbol_reprove.py"
PAPER="$REPO/scripts/trader_paper_loop.py"

mkdir -p "$RECEIPT_DIR" "$LOCK_DIR" "$(dirname "$ROUTES")"

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

write_receipt() {
  # usage: write_receipt ACTION key=val key=val ...
  local action="$1"
  shift
  ACTION="$action" RECEIPT_PATH="$RECEIPT" "$PY" - "$@" <<'PY'
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
path = Path(os.environ["RECEIPT_PATH"])
action = os.environ["ACTION"]
detail = {}
for item in sys.argv[1:]:
    if "=" not in item:
        continue
    k, v = item.split("=", 1)
    # coerce ints/bools/json-ish
    if v.lower() in ("true", "false"):
        detail[k] = v.lower() == "true"
    else:
        try:
            detail[k] = int(v)
        except ValueError:
            try:
                detail[k] = float(v)
            except ValueError:
                detail[k] = v
payload = {
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "action": action,
    "trading_authority": False,
    "live_authority": False,
    "execute_paper": False,
    **detail,
}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "action": action, **detail}, sort_keys=True))
PY
}

lock_live() {
  [[ -f "$LOCK_FILE" ]] || return 1
  local token pid
  read -r token _ <"$LOCK_FILE" || true
  pid="${token#pid=}"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  return 1
}

# --- 1) single flight ---
if lock_live; then
  write_receipt "skip_build_running" "lock=$LOCK_FILE" >/dev/null
  echo "trader_autonomous_tick: BUILD already running; skip"
  exit 0
fi

# --- 2) refresh strategy engine handoff ---
echo "trader_autonomous_tick: refreshing route batch + engine handoff"
set +e
"$PY" "$ROUTE_BATCH" --repo "$REPO" --routes-out "$ROUTES" --panel-out "$PANEL" >"$RECEIPT_DIR/route_batch_LATEST.json"
rb_rc=$?
set -e
if [[ $rb_rc -ne 0 ]]; then
  write_receipt "route_batch_failed" "exit_code=$rb_rc" >/dev/null
  echo "trader_autonomous_tick: route_batch failed rc=$rb_rc" >&2
  exit 3
fi

set +e
"$PY" "$HANDOFF_PY" --repo "$REPO" --routes "$ROUTES" --panel "$PANEL" --stamp "autonomous-$(date +%Y%m%dT%H%M%S)" \
  >"$RECEIPT_DIR/handoff_LATEST.json"
ho_rc=$?
set -e
if [[ $ho_rc -ne 0 ]]; then
  write_receipt "handoff_failed" "exit_code=$ho_rc" >/dev/null
  echo "trader_autonomous_tick: handoff failed rc=$ho_rc" >&2
  exit 3
fi

STATUS="$("$PY" - "$HANDOFF_REPORT" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
d = json.loads(p.read_text()) if p.is_file() else {}
print(d.get("status") or "MISSING")
PY
)"

echo "trader_autonomous_tick: handoff status=$STATUS"

# --- 3a) survivor → BUILD MoA (one lab) ---
if [[ "$STATUS" == "NEXT_SURVIVOR" ]]; then
  # Prefer clean main; MoA preflight will enforce. Skip if obviously on foreign dirty branch.
  branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo DETACHED)
  if [[ "$branch" != "main" && "$branch" != trader/run-* ]]; then
    write_receipt "skip_foreign_branch" "branch=$branch" "status=$STATUS" >/dev/null
    echo "trader_autonomous_tick: foreign branch $branch; skip BUILD"
    exit 0
  fi
  write_receipt "launch_build_moa" "status=$STATUS" "branch=$branch" >/dev/null
  echo "trader_autonomous_tick: launching zero-input BUILD MoA"
  # Foreground so cron serializes; lock inside MoA.
  exec bash "$MOA"
fi

# --- 3b) no qualified / other → cheap quality residual (still autonomous progress) ---
# Multi-symbol quality bar work does not need MoA tokens; keeps pack-grade search moving.
if [[ "$STATUS" == "NO_QUALIFIED_STRATEGY" || "$STATUS" == "MISSING" ]]; then
  multi_rc=0
  paper_rc=0
  if [[ -f "$MULTI" ]]; then
    set +e
    "$PY" "$MULTI" >"$RECEIPT_DIR/multi_symbol_LATEST.json" 2>"$RECEIPT_DIR/multi_symbol_LATEST.err"
    multi_rc=$?
    set -e
  fi
  if [[ -f "$PAPER" ]]; then
    set +e
    "$PY" "$PAPER" >"$RECEIPT_DIR/paper_loop_stdout.txt" 2>"$RECEIPT_DIR/paper_loop_stderr.txt"
    paper_rc=$?
    set -e
  fi
  write_receipt "no_survivor_cheap_residual" "status=$STATUS" "multi_symbol_rc=$multi_rc" "paper_loop_rc=$paper_rc" "note=expected_no_survivor_cheap_residual" >/dev/null
  echo "trader_autonomous_tick: no survivor — multi_rc=$multi_rc paper_rc=$paper_rc (MoA not launched)"
  # Exit 0 so cron is green on honest no-edge engine results.
  exit 0
fi

write_receipt "unhandled_status" "status=$STATUS" >/dev/null
echo "trader_autonomous_tick: unhandled handoff status=$STATUS" >&2
exit 3

#!/usr/bin/env bash
# Non-stop tight quality worker (programmatic, no LLM).
#
# Runs parallel quality cycles back-to-back with a short sleep.
# Never densify-bag thrash. Never live/shadow/arm.
#
# Usage:
#   just trader-quality-worker start
#   just trader-quality-worker stop
#   just trader-quality-worker status
#   just trader-quality-worker once
#   just trader-quality-worker ensure   # cron: restart if dead
#
# Env:
#   TRADER_QUALITY_SLEEP=20          seconds between cycles (default 20)
#   TRADER_QUALITY_MAX_CYCLES=0      0 = forever
#   TRADER_QC_PARALLEL=3
set -euo pipefail

REPO="${TRADER_REPO:-/Users/jarvis/dev/trader}"
cd "$REPO"
PY="${TRADER_PYTHON:-$REPO/.venv/bin/python}"
STATE="$REPO/.cache/platform/quality_worker"
PIDFILE="$STATE/worker.pid"
STOPFILE="$STATE/STOP"
LOGDIR="$STATE/logs"
LOCK="$STATE/worker.lock"
HEARTBEAT="$STATE/HEARTBEAT.json"
CYCLE_PY="$REPO/scripts/trader_quality_cycle.py"
SLEEP_S="${TRADER_QUALITY_SLEEP:-20}"
MAX_CYCLES="${TRADER_QUALITY_MAX_CYCLES:-0}"
CMD="${1:-status}"

mkdir -p "$STATE" "$LOGDIR"

is_running() {
  if [[ ! -f "$PIDFILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  return 1
}

write_status() {
  local state="$1"
  shift || true
  "$PY" - "$STATE/STATUS.json" "$state" "$@" <<'PY'
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
path = Path(sys.argv[1])
state = sys.argv[2]
extra = {}
for item in sys.argv[3:]:
    if "=" in item:
        k, v = item.split("=", 1)
        extra[k] = v
payload = {
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "state": state,
    "pid": extra.get("pid"),
    "note": extra.get("note", ""),
    "trading_authority": False,
    "live_authority": False,
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

run_loop() {
  local cycles=0
  rm -f "$STOPFILE"
  write_status "running" "pid=$$" "note=quality_worker_loop"
  echo "trader_quality_worker: loop start pid=$$ sleep=${SLEEP_S}s max_cycles=${MAX_CYCLES}"
  while true; do
    if [[ -f "$STOPFILE" ]]; then
      echo "trader_quality_worker: STOP file seen; exit"
      write_status "stopped" "pid=$$" "note=stop_file"
      rm -f "$PIDFILE"
      exit 0
    fi
    # Skip cycle if BUILD MoA lock live
    if [[ -f "$REPO/.cache/platform/build_lab.lock" ]]; then
      local token pid
      read -r token _ <"$REPO/.cache/platform/build_lab.lock" || true
      pid="${token#pid=}"
      if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
        echo "trader_quality_worker: BUILD lock live; sleep"
        sleep "$SLEEP_S"
        continue
      fi
    fi

    local stamp wall
    stamp="$(date -u +%Y%m%dT%H%M%S)"
    echo "trader_quality_worker: cycle $stamp begin"
    set +e
    "$PY" "$CYCLE_PY" --json >"$LOGDIR/cycle_${stamp}.json" 2>"$LOGDIR/cycle_${stamp}.err"
    local rc=$?
    set -e
    echo "trader_quality_worker: cycle $stamp rc=$rc"
    cycles=$((cycles + 1))
    if [[ "$MAX_CYCLES" != "0" && "$cycles" -ge "$MAX_CYCLES" ]]; then
      echo "trader_quality_worker: max cycles $MAX_CYCLES reached"
      write_status "completed" "pid=$$" "note=max_cycles"
      rm -f "$PIDFILE"
      exit 0
    fi
    sleep "$SLEEP_S"
  done
}

case "$CMD" in
  once)
    exec "$PY" "$CYCLE_PY" --json
    ;;
  status)
    if is_running; then
      echo "quality_worker: RUNNING pid=$(cat "$PIDFILE")"
    else
      echo "quality_worker: STOPPED"
    fi
    if [[ -f "$HEARTBEAT" ]]; then
      echo "heartbeat:"
      cat "$HEARTBEAT"
    fi
    if [[ -f "$STATE/STATUS.json" ]]; then
      echo "status:"
      cat "$STATE/STATUS.json"
    fi
    exit 0
    ;;
  stop)
    if is_running; then
      touch "$STOPFILE"
      pid="$(cat "$PIDFILE")"
      echo "quality_worker: signaling stop to pid=$pid"
      # polite wait
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        if ! kill -0 "$pid" 2>/dev/null; then
          break
        fi
        sleep 1
      done
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$PIDFILE"
      write_status "stopped" "pid=$pid" "note=stop_cmd"
      echo "quality_worker: stopped"
    else
      rm -f "$PIDFILE" "$STOPFILE"
      write_status "stopped" "note=already_stopped"
      echo "quality_worker: already stopped"
    fi
    exit 0
    ;;
  start)
    if is_running; then
      echo "quality_worker: already running pid=$(cat "$PIDFILE")"
      exit 0
    fi
    rm -f "$STOPFILE"
    # detach
    nohup bash "$0" _run >>"$LOGDIR/worker.out" 2>&1 &
    echo $! >"$PIDFILE"
    sleep 0.5
    if is_running; then
      write_status "running" "pid=$(cat "$PIDFILE")" "note=started"
      echo "quality_worker: started pid=$(cat "$PIDFILE")"
      echo "  log: $LOGDIR/worker.out"
      echo "  heartbeat: $HEARTBEAT"
    else
      echo "quality_worker: failed to start — see $LOGDIR/worker.out" >&2
      exit 1
    fi
    exit 0
    ;;
  ensure)
    # cron supervisor: keep worker alive
    if is_running; then
      # stale heartbeat > 30 min → restart
      if [[ -f "$HEARTBEAT" ]]; then
        stale="$("$PY" - "$HEARTBEAT" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
p = Path(sys.argv[1])
try:
    d = json.loads(p.read_text())
    ts = d.get("generated_at") or ""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - dt).total_seconds()
    print(int(age))
except Exception:
    print(999999)
PY
)"
        if [[ "$stale" -gt 1800 ]]; then
          echo "quality_worker: heartbeat stale ${stale}s — restart"
          bash "$0" stop || true
          bash "$0" start
          exit 0
        fi
      fi
      echo "quality_worker: ok pid=$(cat "$PIDFILE")"
      exit 0
    fi
    echo "quality_worker: not running — start"
    bash "$0" start
    exit 0
    ;;
  _run)
    echo $$ >"$PIDFILE"
    run_loop
    ;;
  *)
    echo "usage: $0 {start|stop|status|once|ensure}" >&2
    exit 2
    ;;
esac

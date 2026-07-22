#!/usr/bin/env bash
# Trigger a continuum residual now and print go-live funnel progress.
#
# Usage:
#   just trader-run-now              # full autonomous tick (quality residual path)
#   just trader-run-now campaign     # paper campaign only (faster)
#   just trader-run-now quality      # quality residual only
#   just trader-run-now status       # funnel only (no run)
set -euo pipefail

REPO="${TRADER_REPO:-/Users/jarvis/dev/trader}"
cd "$REPO"
PY="${TRADER_PYTHON:-$REPO/.venv/bin/python}"
MODE="${1:-tick}"

echo "════════════════════════════════════════════════════"
echo " trader-run-now  mode=$MODE  $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "════════════════════════════════════════════════════"

run_status() {
  echo
  echo "──────── go-live funnel ────────"
  "$PY" "$REPO/scripts/trader_go_live_status.py" --write
}

case "$MODE" in
  status|funnel|s)
    run_status
    exit 0
    ;;
  campaign|paper|c)
    echo "→ paper campaign…"
    bash "$REPO/scripts/trader_paper_campaign.sh"
    ;;
  quality|q)
    echo "→ parallel quality cycle…"
    "$PY" "$REPO/scripts/trader_quality_cycle.py" --json | tail -40
    ;;
  worker|w)
    echo "→ quality worker ensure (non-stop)…"
    bash "$REPO/scripts/trader_quality_worker.sh" ensure
    bash "$REPO/scripts/trader_quality_worker.sh" status
    ;;
  tick|auto|full|f|"")
    echo "→ autonomous tick (handoff → MoA or quality residual)…"
    bash "$REPO/scripts/trader_autonomous_tick.sh"
    ;;
  *)
    echo "unknown mode: $MODE" >&2
    echo "use: tick | campaign | quality | status" >&2
    exit 2
    ;;
esac

echo
echo "──────── receipts ────────"
if [[ -f .cache/platform/autonomous/tick_LATEST.json ]]; then
  echo "autonomous tick:"
  "$PY" -c 'import json;print(json.dumps(json.load(open(".cache/platform/autonomous/tick_LATEST.json")),indent=2))' 2>/dev/null || cat .cache/platform/autonomous/tick_LATEST.json
fi
if [[ -f .cache/platform/paper_campaign/LATEST.json ]]; then
  echo
  echo "paper campaign (summary):"
  "$PY" -c 'import json;d=json.load(open(".cache/platform/paper_campaign/LATEST.json"));print(json.dumps({k:d.get(k) for k in ("generated_at","next_action","open_risk","placed","open_orders","scout_n_intents")},indent=2))' 2>/dev/null || true
fi
if [[ -f reports/bootstrap/NEXT_SEED.json ]]; then
  echo
  echo "NEXT_SEED:"
  cat reports/bootstrap/NEXT_SEED.json
fi

run_status
echo "done."

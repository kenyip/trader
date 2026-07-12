#!/usr/bin/env bash
# Compatibility entrypoint for a named stress/judgment MoA wake.
# All execution is delegated to the contract-v2 BUILD orchestrator so this
# entrypoint cannot bypass clean preflight, finalization, learning promotion,
# commit/push/main integration, or postflight verification.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_WRAPPER="$REPO/scripts/trader_build_lab_moa.sh"

GOAL=""
STAMP=""
MODE_FLAG=""
EXTRA_HYP_IDS=""

usage() {
  cat <<'EOF'
Usage: scripts/trader_wake_moa.sh [--goal TEXT] [--hyps CSV] [--stamp STAMP]
                                  [--executor-only|--challenger-only|--finalizer-only|--resume]

This compatibility adapter routes stress/judgment MoA work through
trader_build_lab_moa.sh and its deterministic completion contract.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --) shift ;;
    --goal) GOAL="$2"; shift 2 ;;
    --hyps) EXTRA_HYP_IDS="$2"; shift 2 ;;
    --stamp) STAMP="$2"; shift 2 ;;
    --executor-only|--challenger-only|--finalizer-only|--resume)
      MODE_FLAG="$1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -x "$BUILD_WRAPPER" ]] || {
  echo "ERROR: missing BUILD completion orchestrator: $BUILD_WRAPPER" >&2
  exit 1
}

# Zero input is the same canonical autonomous BUILD wake. Supplying named hyps
# intentionally turns this compatibility adapter into a diagnostic override.
if [[ -z "$GOAL" && -n "$EXTRA_HYP_IDS" ]]; then
  GOAL="Diagnostic named-hypothesis stress override for: ${EXTRA_HYP_IDS}. Trader still orients independently; use these IDs only if they remain the highest-information valid loop."
fi

args=()
[[ -n "$GOAL" ]] && args+=(--goal "$GOAL")
[[ -n "$STAMP" ]] && args+=(--stamp "$STAMP")
[[ -n "$MODE_FLAG" ]] && args+=("$MODE_FLAG")

if (( ${#args[@]} == 0 )); then
  exec "$BUILD_WRAPPER"
fi
exec "$BUILD_WRAPPER" "${args[@]}"

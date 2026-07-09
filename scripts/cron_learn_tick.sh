#!/usr/bin/env bash
# Learn tick: evaluate outcomes → safe hyp transitions. Never live/shadow auto.
set -euo pipefail
cd /Users/jarvis/dev/tsla-tsll-options-tracker
mkdir -p .cache/platform
{
  echo "=== learn_tick $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  .venv/bin/python -m trader_platform.learn_tick --once --apply --append-scoreboard
  echo "=== done ==="
} >> .cache/platform/learn_cron.log 2>&1
exit 0

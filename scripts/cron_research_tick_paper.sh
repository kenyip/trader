#!/usr/bin/env bash
# Paper-only multi-symbol research tick. No orders. No agentic.
set -euo pipefail
cd /Users/jarvis/dev/tsla-tsll-options-tracker
mkdir -p .cache/platform
{
  echo "=== research_tick_paper $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  .venv/bin/python -m trader_platform.research tick \
    --write-report \
    --sleeve-usd 5000 \
    --notes research_cron_paper \
    --promote --promote-top 5
  echo "=== done ==="
} >> .cache/platform/research_cron.log 2>&1
# Silent for no_agent delivery unless something failed (exit non-zero already)
exit 0

#!/usr/bin/env bash
# Write a masked RH readiness receipt from values supplied by a Hermes MCP probe.
# Does NOT call the broker. Safe for continuum / docs.
set -euo pipefail
REPO="${TRADER_REPO:-/Users/jarvis/dev/trader}"
OUT="${1:-$REPO/.cache/platform/rh_mcp_probe_LATEST.json}"
mkdir -p "$(dirname "$OUT")"
python3 - "$OUT" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
out = Path(sys.argv[1])
# Values from live MCP probe 2026-07-20 — refresh by re-probing in Hermes, not guessing.
payload = {
  "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
  "probe_session": "hermes-trader-mcp-2026-07-20",
  "trading_authority": False,
  "agentic_live": False,
  "accounts": [
    {
      "mask": "••••8507",
      "nickname": "Agentic",
      "agentic_allowed": True,
      "type": "cash",
      "option_level": "",
      "total_value_usd": 0.0,
      "cash_usd": 0.0,
      "buying_power_usd": 0.0,
      "equity_positions": 0,
      "option_positions": 0,
    },
    {
      "mask": "••••5223",
      "nickname": "Individual",
      "agentic_allowed": False,
      "type": "margin",
      "option_level": "option_level_3",
      "note": "main book — never agent trade target",
    },
  ],
  "mcp_read_ok": [
    "get_accounts",
    "get_portfolio",
    "get_equity_positions",
    "get_option_positions",
    "get_equity_quotes",
    "get_option_chains",
    "get_option_level_upgrade_info",
  ],
  "mcp_write_policy": "place_* forbidden until Ken arm + platform place wire",
  "mcp_options_place_shape": "single_leg_only",
  "blockers_for_live": [
    "agentic_unfunded",
    "agentic_no_options_level",
    "platform_place_not_implemented",
    "no_quality_top_hyp",
    "agentic.enabled=false",
  ],
  "ken_actions": [
    "options_upgrade_agentic",
    "optional_test_deposit_300_500",
    "transfer_3000_only_at_live_packet",
  ],
  "upgrade_url_note": "https://applink.robinhood.com/upgrade_options?account_number=987168507",
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(out)
PY

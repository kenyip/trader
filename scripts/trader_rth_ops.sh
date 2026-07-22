#!/usr/bin/env bash
# Deterministic RTH residual: scout + autonomy dry-run on shortlist symbols.
# Never live / shadow / arm / execute-paper.
# Use when agent RTH eval is down (Hermes import/gateway) or as parallel plumbing check.
set -euo pipefail
REPO="${TRADER_REPO:-/Users/jarvis/dev/trader}"
cd "$REPO"
PY="${TRADER_PYTHON:-$REPO/.venv/bin/python}"
OUT_DIR="${TRADER_RTH_OUT:-$REPO/.cache/platform/rth_ops}"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%S)"
DAY="$(date +%Y-%m-%d)"
LOG="$OUT_DIR/run_${STAMP}.log"
SUMMARY="$OUT_DIR/LATEST.json"

if [[ ! -x "$PY" ]]; then
  echo "trader_rth_ops: missing $PY" >&2
  exit 1
fi

# Default symbols: paper leader + MCP-native cheap names + liquid shortlist.
SYMBOLS="${TRADER_RTH_SYMBOLS:-BAC PLTR NFLX TSLL SMCI CCL AAL KO IWM}"

exec > >(tee -a "$LOG") 2>&1
echo "trader_rth_ops: start $STAMP symbols=$SYMBOLS"

rc_scout=0
rc_auto=0
set +e
"$PY" -m trader_platform.premium_scout --symbols $SYMBOLS --json --max-intents 8 --event rth_ops \
  >"$OUT_DIR/scout_${STAMP}.json"
rc_scout=$?
"$PY" -m trader_platform.autonomy_loop --mode paper --once --dry-run --symbols $SYMBOLS \
  --json --event rth_ops --max-intents 5 \
  >"$OUT_DIR/autonomy_${STAMP}.json"
rc_auto=$?
set -e

"$PY" - "$SUMMARY" "$STAMP" "$DAY" "$rc_scout" "$rc_auto" "$LOG" "$OUT_DIR/scout_${STAMP}.json" "$OUT_DIR/autonomy_${STAMP}.json" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

summary_path = Path(sys.argv[1])
stamp, day = sys.argv[2], sys.argv[3]
rc_scout, rc_auto = int(sys.argv[4]), int(sys.argv[5])
log_path = sys.argv[6]
scout_path = Path(sys.argv[7])
auto_path = Path(sys.argv[8])

def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e), "path": str(p)}

scout = load(scout_path)
auto = load(auto_path)

def count_intents(blob):
    if not isinstance(blob, dict):
        return None
    for k in ("n_intents", "intents"):
        if k == "n_intents" and k in blob:
            return blob[k]
        if k == "intents" and isinstance(blob.get(k), list):
            return len(blob[k])
    # nested
    for v in blob.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "symbol" in v[0]:
            return len(v)
    return None

payload = {
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "stamp": stamp,
    "day": day,
    "rc": {"scout": rc_scout, "autonomy_dry": rc_auto},
    "log": log_path,
    "scout_path": str(scout_path),
    "autonomy_path": str(auto_path),
    "n_intents_scout": count_intents(scout),
    "n_intents_autonomy": count_intents(auto),
    "trading_authority": False,
    "live_authority": False,
    "execute_paper": False,
    "note": "deterministic RTH residual — judgment still required for paper place; never live",
}
summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
# also day pointer
day_path = summary_path.parent / f"rth_ops_{day}.json"
day_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY

echo "trader_rth_ops: done"
exit 0

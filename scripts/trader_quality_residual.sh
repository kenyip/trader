#!/usr/bin/env bash
# Tight quality residual when Strategy Engine has no survivor.
# Intent: more prove cycles without dense bag thrash or MoA spam.
#
# Loop:
#   research rank (30s–few min)
#   defined-risk evolve (PCS/CCS) + MCP-native CSP/wheel (apply paper-safe hyps)
#   B3/B4 stress on newest SHIP hyps that look PCS-like (best-effort)
#   multi-symbol re-prove + dry paper loop
#
# Never live / shadow / arm / execute-paper.
set -euo pipefail

REPO="${TRADER_REPO:-/Users/jarvis/dev/trader}"
cd "$REPO"
PY="${TRADER_PYTHON:-$REPO/.venv/bin/python}"
OUT_DIR="${TRADER_QUALITY_OUT:-$REPO/.cache/platform/quality_residual}"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%S)"
LOG="$OUT_DIR/run_${STAMP}.log"
SUMMARY="$OUT_DIR/LATEST.json"

exec > >(tee -a "$LOG") 2>&1
echo "trader_quality_residual: start $STAMP"

rc_research=0
rc_evolve_dr=0
rc_evolve_csp=0
rc_stress=0
rc_multi=0
rc_paper=0

set +e
"$PY" -m trader_platform.research tick --write-report --notes quality_residual --sleeve-usd 3000
rc_research=$?
set -e

set +e
"$PY" -m trader_platform.evolve_tick --once \
  --structures put_credit_spread call_credit_spread \
  --top-symbols 8 --mutants 3 --sleeve-usd 3000 --apply
rc_evolve_dr=$?
set -e

set +e
"$PY" -m trader_platform.evolve_tick --once \
  --structures cash_secured_put wheel_assignment short_put_credit \
  --top-symbols 6 --mutants 2 --sleeve-usd 3000 --apply
rc_evolve_csp=$?
set -e

# Best-effort: stress a shortlist file if present; else skip.
SHORTLIST="$REPO/reports/bootstrap/QUALITY_SHORTLIST.json"
if [[ -f "$SHORTLIST" ]]; then
  hyps="$("$PY" - "$SHORTLIST" <<'PY'
import json, sys
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
ids = []
for row in d.get("shortlist") or []:
    hid = row.get("hyp_id") or row.get("id")
    if hid and row.get("structure") in (
        "put_credit_spread", "call_credit_spread", "iron_condor"
    ) and row.get("stress_priority", True):
        ids.append(str(hid))
print(",".join(ids[:6]))
PY
)"
  if [[ -n "${hyps:-}" ]]; then
    set +e
    "$PY" "$REPO/scripts/pcs_regime_stress.py" --hyps "$hyps" \
      --out "$OUT_DIR/regime_${STAMP}.json"
    r1=$?
    "$PY" "$REPO/scripts/pcs_cost_stress.py" --hyps "$hyps" \
      --out "$OUT_DIR/cost_${STAMP}.json"
    r2=$?
    rc_stress=$(( r1 != 0 || r2 != 0 ? 1 : 0 ))
    set -e
  fi
fi

set +e
"$PY" "$REPO/scripts/trader_multi_symbol_reprove.py" >"$OUT_DIR/multi_${STAMP}.json"
rc_multi=$?
"$PY" "$REPO/scripts/trader_paper_loop.py" >"$OUT_DIR/paper_${STAMP}.txt" 2>&1
rc_paper=$?
# Self-driving paper campaign (learn + manage + optional paper place on shortlist leaders)
rc_campaign=0
if [[ -f "$REPO/scripts/trader_paper_campaign.sh" ]]; then
  bash "$REPO/scripts/trader_paper_campaign.sh" >"$OUT_DIR/campaign_${STAMP}.txt" 2>&1
  rc_campaign=$?
fi
set -e

"$PY" - "$SUMMARY" "$STAMP" "$rc_research" "$rc_evolve_dr" "$rc_evolve_csp" "$rc_stress" "$rc_multi" "$rc_paper" "$rc_campaign" "$LOG" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
path = Path(sys.argv[1])
payload = {
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "stamp": sys.argv[2],
    "rc": {
        "research": int(sys.argv[3]),
        "evolve_defined_risk": int(sys.argv[4]),
        "evolve_csp": int(sys.argv[5]),
        "stress": int(sys.argv[6]),
        "multi_symbol": int(sys.argv[7]),
        "paper": int(sys.argv[8]),
        "paper_campaign": int(sys.argv[9]),
    },
    "log": sys.argv[10],
    "trading_authority": False,
    "live_authority": False,
    "execute_paper": False,
    "note": "quality residual — paper-safe search + paper campaign; never live/arm",
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY

echo "trader_quality_residual: done"
exit 0

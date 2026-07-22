#!/usr/bin/env bash
# Self-driving paper campaign residual — no Ken nudge required.
#
# Advances the paper funnel on shortlist leaders:
#   1) learn_tick (safe apply)
#   2) cancel smoke/plumbing residue that pollutes open_risk
#   3) scout shortlist testing/paper symbols
#   4) paper place defined-risk OPEN_* for shortlist leaders (max 1 new / run)
#   5) write durable NEXT_SEED + campaign receipt
#
# Never live / shadow / arm / agentic_live / place_* broker.
set -euo pipefail

REPO="${TRADER_REPO:-/Users/jarvis/dev/trader}"
cd "$REPO"
PY="${TRADER_PYTHON:-$REPO/.venv/bin/python}"
OUT_DIR="${TRADER_CAMPAIGN_OUT:-$REPO/.cache/platform/paper_campaign}"
SHORTLIST="${TRADER_SHORTLIST:-$REPO/reports/bootstrap/QUALITY_SHORTLIST.json}"
NEXT_SEED="${TRADER_NEXT_SEED:-$REPO/reports/bootstrap/NEXT_SEED.json}"
mkdir -p "$OUT_DIR" "$(dirname "$NEXT_SEED")"
STAMP="$(date -u +%Y%m%dT%H%M%S)"
LOG="$OUT_DIR/run_${STAMP}.log"
RECEIPT="$OUT_DIR/LATEST.json"

# Optional: TRADER_PAPER_CAMPAIGN_EXECUTE=0 to force dry-only (default 1 = paper place allowed)
EXECUTE="${TRADER_PAPER_CAMPAIGN_EXECUTE:-1}"

exec > >(tee -a "$LOG") 2>&1
echo "trader_paper_campaign: start $STAMP execute=$EXECUTE"

rc_learn=0
rc_campaign=0

set +e
"$PY" -m trader_platform.learn_tick --once --apply --json >"$OUT_DIR/learn_${STAMP}.json"
rc_learn=$?
set -e

set +e
"$PY" - "$SHORTLIST" "$NEXT_SEED" "$RECEIPT" "$STAMP" "$EXECUTE" "$OUT_DIR" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trader_platform.execution.broker_adapter import get_broker
from trader_platform.hypothesis_registry import HypothesisRegistry
from trader_platform.paper_filters import is_smoke_stub_order, is_smoke_stub_tag
from trader_platform.autonomy_loop import run_tick
from trader_platform.modes import Mode

shortlist_path = Path(sys.argv[1])
next_seed_path = Path(sys.argv[2])
receipt_path = Path(sys.argv[3])
stamp = sys.argv[4]
execute = sys.argv[5].strip() not in ("0", "false", "False", "no", "NO")
out_dir = Path(sys.argv[6])

now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_json(p: Path, default: Any):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

shortlist = load_json(shortlist_path, {})
rows = list(shortlist.get("shortlist") or [])

# Leaders eligible for paper campaign: paper_research lane, multi-leg defined-risk, stress_priority preferred
paper_structs = {
    "put_credit_spread",
    "call_credit_spread",
    "iron_condor",
    "iron_butterfly",
    "broken_wing_iron_butterfly",
}
leaders: list[dict[str, Any]] = []
for r in rows:
    st = (r.get("structure") or "").strip()
    lane = (r.get("lane") or "")
    if st not in paper_structs:
        continue
    if lane and lane not in ("paper_research", "paper", ""):
        # still allow if stress_priority and multi-leg
        if not r.get("stress_priority"):
            continue
    leaders.append(r)

# Prefer stress_priority then listed order
leaders.sort(key=lambda r: (0 if r.get("stress_priority") else 1))

reg = HypothesisRegistry()
# Ensure leaders are at least testing so scout sees them
promoted = []
for r in leaders[:4]:
    hid = r.get("hyp_id") or r.get("id")
    if not hid:
        continue
    h = reg.get(str(hid))
    if h is None:
        continue
    if h.status == "candidate":
        try:
            reg.transition(
                str(hid),
                "testing",
                evidence_link=f"paper_campaign:{stamp}:auto_testing_for_scout",
            )
            promoted.append(str(hid))
        except Exception as e:
            promoted.append(f"{hid}:err:{e}")

broker = get_broker("paper")
canceled = []
for o in list(broker.list_open_orders()):
    tag = getattr(o, "tag", "") or ""
    smoke = False
    try:
        smoke = bool(is_smoke_stub_order(o) or is_smoke_stub_tag(tag))
    except Exception:
        smoke = "smoke" in tag.lower() or "m0_stub" in tag
    plumbing = tag.startswith("plumbing_smoke")
    if smoke or plumbing:
        try:
            broker.cancel(o.order_id)
            canceled.append({"order_id": o.order_id, "symbol": o.symbol, "reason": "smoke_or_plumbing"})
        except Exception as e:
            canceled.append({"order_id": o.order_id, "error": str(e)})

open_orders = broker.list_open_orders()
# Real campaign open (ignore anything still stub-like)
real_open = []
for o in open_orders:
    tag = getattr(o, "tag", "") or ""
    if "smoke" in tag.lower() or tag.startswith("plumbing_smoke"):
        continue
    real_open.append(
        {
            "order_id": o.order_id,
            "symbol": o.symbol,
            "strategy_id": o.strategy_id,
            "max_loss_usd": o.max_loss_usd,
            "structure": getattr(o, "structure", None),
            "status": o.status,
        }
    )

port = broker.portfolio_snapshot() if hasattr(broker, "portfolio_snapshot") else None
open_risk = float(getattr(port, "open_risk", 0.0) or 0.0) if port else 0.0

# Symbols from leaders
symbols: list[str] = []
for r in leaders:
    sym = (r.get("symbol") or "").upper()
    if sym and sym not in symbols:
        symbols.append(sym)
if not symbols:
    symbols = ["BAC", "PLTR", "IWM", "KO"]

# Cap concurrent campaign risk ~500 (prefer 1–2 lots of quality leaders, not spray)
MAX_OPEN_RISK = float(os.environ.get("TRADER_PAPER_CAMPAIGN_MAX_OPEN_RISK", "500"))
MAX_NEW = int(os.environ.get("TRADER_PAPER_CAMPAIGN_MAX_NEW", "1"))
MAX_LOSS_CAP = float(os.environ.get("TRADER_PAPER_CAMPAIGN_MAX_LOSS", "250"))
MAX_CONCURRENT = int(os.environ.get("TRADER_PAPER_CAMPAIGN_MAX_CONCURRENT", "2"))

already_ids = {o["strategy_id"] for o in real_open}
actions: list[dict[str, Any]] = []
placed = []
dry_ready = []

# Always scout
scout_summary = None
try:
    # premium_scout CLI module entry
    import subprocess

    scout_path = out_dir / f"scout_{stamp}.json"
    cmd = [
        sys.executable,
        "-m",
        "trader_platform.premium_scout",
        "--symbols",
        *symbols[:10],
        "--json",
        "--max-intents",
        "8",
        "--event",
        "paper_campaign",
    ]
    proc = subprocess.run(cmd, cwd=str(Path.cwd()), capture_output=True, text=True)
    scout_raw = proc.stdout
    try:
        scout_summary = json.loads(scout_raw[scout_raw.find("{") :])
    except Exception:
        scout_summary = {"raw_tail": scout_raw[-2000:], "rc": proc.returncode, "err": proc.stderr[-1000:]}
    scout_path.write_text(json.dumps(scout_summary, indent=2)[:500000], encoding="utf-8")
except Exception as e:
    scout_summary = {"error": str(e)}

# Decide paper place: only if execute and capacity
can_place = (
    execute
    and open_risk < MAX_OPEN_RISK
    and MAX_NEW > 0
    and len(real_open) < MAX_CONCURRENT
)
new_count = 0
if can_place:
    # Prefer leader hyps not already open — one symbol attempt, one place max
    for r in leaders:
        if new_count >= MAX_NEW or len(real_open) + new_count >= MAX_CONCURRENT:
            break
        if open_risk >= MAX_OPEN_RISK:
            break
        hid = str(r.get("hyp_id") or r.get("id") or "")
        sym = str(r.get("symbol") or "").upper()
        if not hid or not sym:
            continue
        if hid in already_ids:
            actions.append({"hyp_id": hid, "action": "already_open"})
            continue
        # Skip secondary leaders on a symbol that already has a campaign open
        if any(o.get("symbol") == sym for o in real_open):
            actions.append({"hyp_id": hid, "action": "symbol_already_open", "symbol": sym})
            continue
        try:
            summary = run_tick(
                mode=Mode.PAPER,
                event="paper_campaign",
                dry_run=False,
                symbols=[sym],
                max_intents=1,
            )
        except TypeError:
            summary = run_tick(
                mode="paper",
                event="paper_campaign",
                dry_run=False,
                symbols=[sym],
                max_intents=1,
            )
        placed_this = False
        for entry in summary.get("results") or []:
            intent = entry.get("intent") or {}
            sid = intent.get("strategy_id") or ""
            action = entry.get("action")
            ml = intent.get("max_loss_usd")
            structure = intent.get("structure") or ""
            # Accept only the targeted hyp_id (scout may emit multiple DNA on one symbol)
            if sid != hid:
                actions.append({"hyp_id": hid, "action": "skip_other_hyp", "other": sid})
                continue
            if structure and structure not in paper_structs:
                actions.append({"hyp_id": hid, "action": "skip_non_defined", "structure": structure})
                continue
            if ml is not None and float(ml) > MAX_LOSS_CAP:
                actions.append({"hyp_id": hid, "action": "skip_max_loss", "max_loss_usd": ml})
                continue
            if open_risk + float(ml or 0.0) > MAX_OPEN_RISK:
                actions.append({"hyp_id": hid, "action": "skip_open_risk_cap", "open_risk": open_risk, "ml": ml})
                continue
            if action == "paper_place":
                placed.append(entry)
                new_count += 1
                placed_this = True
                already_ids.add(hid)
                open_risk += float(ml or 0.0)
                real_open.append(
                    {
                        "order_id": (entry.get("broker") or {}).get("order_id"),
                        "symbol": sym,
                        "strategy_id": hid,
                        "max_loss_usd": ml,
                        "structure": structure,
                        "status": "working",
                    }
                )
                actions.append(
                    {
                        "hyp_id": hid,
                        "action": "paper_place",
                        "order_id": (entry.get("broker") or {}).get("order_id"),
                        "max_loss_usd": ml,
                        "symbol": sym,
                    }
                )
                break
            else:
                actions.append({"hyp_id": hid, "action": action, "risk": entry.get("risk")})
        # One leader decision per run after first non-already_open attempt
        if placed_this or any(a.get("hyp_id") == hid and a.get("action") != "already_open" for a in actions):
            break
else:
    # Dry autonomy for visibility
    try:
        summary = run_tick(
            mode=Mode.PAPER,
            event="paper_campaign_dry",
            dry_run=True,
            symbols=symbols[:8],
            max_intents=5,
        )
    except TypeError:
        summary = run_tick(
            mode="paper",
            event="paper_campaign_dry",
            dry_run=True,
            symbols=symbols[:8],
            max_intents=5,
        )
    for entry in summary.get("results") or []:
        dry_ready.append(
            {
                "action": entry.get("action"),
                "intent": entry.get("intent"),
                "risk": entry.get("risk"),
            }
        )

# Recompute open after places
open_orders = broker.list_open_orders()
real_open = []
for o in open_orders:
    tag = getattr(o, "tag", "") or ""
    if "smoke" in tag.lower() or tag.startswith("plumbing_smoke"):
        continue
    real_open.append(
        {
            "order_id": o.order_id,
            "symbol": o.symbol,
            "strategy_id": o.strategy_id,
            "max_loss_usd": o.max_loss_usd,
            "structure": getattr(o, "structure", None),
            "status": o.status,
        }
    )
port = broker.portfolio_snapshot() if hasattr(broker, "portfolio_snapshot") else None
open_risk = float(getattr(port, "open_risk", 0.0) or 0.0) if port else 0.0

# Durable NEXT seed — continuum always has a concrete next without Ken
if real_open:
    next_action = "manage_open_paper_campaign"
    next_detail = {
        "open_orders": real_open,
        "hint": "RTH: mark/manage paper; learn_tick; stand-aside if no new capital-fit OPEN_*",
    }
elif leaders:
    top = leaders[0]
    next_action = "await_open_pcs_on_leader"
    next_detail = {
        "leader": top.get("hyp_id"),
        "symbol": top.get("symbol"),
        "hint": "Keep residual + rth-ops; paper place when OPEN_PCS and risk allows",
    }
else:
    next_action = "quality_search_for_leader"
    next_detail = {"hint": "Run quality residual; refresh shortlist until B3+B4 leader exists"}

next_seed = {
    "generated_at": now,
    "stamp": stamp,
    "source": "trader_paper_campaign",
    "ken_required": False,
    "ken_only_for": ["gateway_up", "LIVE_PACKET_arm", "fund_3k_at_packet"],
    "next_action": next_action,
    "detail": next_detail,
    "trading_authority": False,
    "live_authority": False,
    "paper_campaign_execute": execute,
}
next_seed_path.write_text(json.dumps(next_seed, indent=2, sort_keys=True) + "\n", encoding="utf-8")

receipt = {
    "generated_at": now,
    "stamp": stamp,
    "execute": execute,
    "promoted_to_testing": promoted,
    "canceled_residue": canceled,
    "leaders": [
        {"hyp_id": r.get("hyp_id"), "symbol": r.get("symbol"), "structure": r.get("structure")}
        for r in leaders[:6]
    ],
    "actions": actions,
    "placed": [
        {
            "strategy_id": (p.get("intent") or {}).get("strategy_id"),
            "order_id": (p.get("broker") or {}).get("order_id"),
            "symbol": (p.get("intent") or {}).get("symbol"),
            "max_loss_usd": (p.get("intent") or {}).get("max_loss_usd"),
        }
        for p in placed
    ],
    "dry_ready_n": len(dry_ready),
    "open_orders": real_open,
    "open_risk": open_risk,
    "scout_n_intents": (scout_summary or {}).get("n_intents")
    if isinstance(scout_summary, dict)
    else None,
    "next_seed_path": str(next_seed_path),
    "next_action": next_action,
    "trading_authority": False,
    "live_authority": False,
    "note": "paper campaign residual — never live/arm",
}
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(out_dir / f"receipt_{stamp}.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(receipt, indent=2, sort_keys=True))
sys.exit(0)
PY
rc_campaign=$?
set -e

echo "trader_paper_campaign: done learn_rc=$rc_learn campaign_rc=$rc_campaign"
# Always exit 0 on expected campaign outcomes; infrastructure hard-fail only if python missing earlier
exit 0

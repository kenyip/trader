# Continuous densify — pause & after-action

**Pinned:** 2026-07-15  
**Purpose:** When non-stop BUILD densify pauses, do **not** immediately launch more volume. Run this loop so the next epoch works **toward a viable strategy**, not thrash.

Related:
- Progress surface: `~/.local/state/jarvis/trader-guidance/continuous-progress-LATEST.md`
- State: `~/.local/state/jarvis/trader-guidance/continuous-densify-state.json`
- Controller: `~/.hermes/scripts/trader_continuous_densify.py`
- Charter: `docs/TRADER_RESTART_CHARTER.md`

---

## 1. What pause means

| Action | Happens? |
|---|---|
| New continuous BUILD launches | **No** (`enabled=false`) |
| RTH eval / stand-aside | Yes |
| Watchdogs / reviewer | Yes |
| Paper / shadow / live / arm | **No** (unchanged) |
| Auto re-arm densify | **No** |

Stop reasons:
- `living_candidate` — success pause; review capital-seat bar
- `epoch_burst_stop` — 3 epoch no-advances
- `novelty_stall` — last N wakes added no advance and no new closed family
- `thrash_stall` — low-quality / capability-only loops

---

## 2. After-action loop (required)

```text
pause
  → reevaluation packet (written)
  → decide: new epoch | diminishing returns | living-seat path
  → if new epoch: promote configs/search_epoch.json + re-arm densify
  → if living seat: paper/review path, densify stays off or rare revalidation only
  → if diminishing returns: stay paused; change platform assumptions or stop
```

### Step A — Freeze densify
Confirm state `enabled=false` and `stop_reason` set. Do **not** launch a fourth wake in the same exhausted burst.

### Step B — Reevaluation packet
Write or complete a search-design reassessment (see latest `docs/SEARCH_DESIGN_REASSESSMENT_*.md`).

Must include:
1. Epoch id + closed stamps/outcomes
2. What failed (edge / uncertainty / costs / density / capital fit / evidence design)
3. Families **quarantined** (no unchanged reopen)
4. **Independent open routes** (process guidance, not DNA orders)
5. Discovery bar vs capital-seat bar (unchanged hard split)
6. Decision: open new epoch **or** `DIMINISHING_RETURNS` **or** living-seat review
7. Epoch success definition (usually first `STRATEGY_ADVANCED` F0→F1 under discovery bar)

Trader still owns mechanism choice. Jarvis owns control-plane + gate integrity.

### Step C — Open next epoch (if justified)
1. Set `configs/search_epoch.json` from the next-epoch package (or promote `configs/search_epoch_next.json`).
2. Link reassessment doc path in the epoch JSON.
3. Reset densify streak semantics by new `started_stamp` (pivot/burst-stop count **only** new epoch wakes).
4. Keep closed families from orientation history.

### Step D — Re-arm continuous densify
Only after Step B+C:

```bash
# after clean main + active next epoch
python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime
p = Path.home()/'.local/state/jarvis/trader-guidance/continuous-densify-state.json'
s = json.loads(p.read_text()) if p.exists() else {}
s.update({
  "enabled": True,
  "mode": "nonstop-with-progress-gate",
  "stop_reason": None,
  "stopped_at": None,
  "rearmed_at": datetime.now().astimezone().isoformat(),
  "note": "Re-armed after written search-design reassessment + new epoch.",
})
p.write_text(json.dumps(s, indent=2) + "\n")
print("re-armed", p)
PY
```

Or ask Jarvis: “re-arm densify for epoch \<id\>”.

### Step E — Living-candidate path (if that was the stop)
1. Do **not** densify-spam discovery.
2. Check capital-seat bar (not discovery bar alone).
3. If seat clears → paper/RTH path.
4. If not → either keep as L0 labeled research or close/quarantine with reason.

---

## 3. Progress gate (what “good” looks like after re-arm)

| Quality | Keep densify? |
|---|---|
| POSITIVE (`STRATEGY_ADVANCED` / living) | Yes (or success-pause on living for seat review) |
| SEARCHING (new closed family / novelty, streak &lt; 3) | Yes |
| STALLED (burst-stop / novelty stall / thrash) | Pause again → back to Step B |

Glance:
- `~/.local/state/jarvis/trader-guidance/continuous-progress-LATEST.md`
- `reports/readiness/build-progress-LATEST.md`
- `reports/trader-wakes/LATEST.md`

---

## 4. Anti-patterns after pause

- Launching more duals “because continuous is on” without reassessment
- Reopening closed families with nearby knob retunes
- Peeking reserved holdouts after F0 fail
- Treating capability-only completion as strategy progress
- Promoting discovery survivors to capital path / paper
- Auto shadow / live / arm

---

## 5. Owner matrix

| Who | After pause |
|---|---|
| Continuous densify cron | Stays silent while `enabled=false` |
| Jarvis | Draft/verify reassessment; promote epoch; re-arm; milestone Ken |
| Trader | After re-arm, freely chooses mechanism outside quarantine |
| Ken | Optional approve new epoch direction if asked; fund/arm only later |

# Trader build coordination (anti-collision)

**Update this when a lane starts or finishes.** Keep it short.

Shared goal map: [TRADER_LOOPS.md](TRADER_LOOPS.md)

---

## Active / recent lanes (2026-07-09)

| Lane | Agent / id | Files (primary) | Status |
|------|------------|-----------------|--------|
| Capital-aware multi-symbol research + promote-top | CoS async **`deleg_5c03b11e`** / session `20260709_010532_98e5b2` | `trader_platform/research/*`, `docs/RESEARCH_LOOP.md`, `docs/RESEARCH_CRON.md`, Justfile research-* | **Landed 2026-07-09** (session ended) |
| Learn-tick v0 + loops map | CLI Jarvis (this session) | `trader_platform/learn_tick.py`, `docs/TRADER_LOOPS.md`, `docs/BUILD_COORDINATION.md`, Justfile `learn-tick`, LaunchAgents + scripts/cron_* | **Landed 2026-07-09** — card `t_ad8dbd08` |
| Desk brief review | Kanban `t_9c8c8b9e` | `docs/DESK_BRIEF.md`, `scripts/desk_brief.py` | Blocked review |
| M2 premium scout foundation | Kanban `t_387b3aef` | `premium_scout.py`, `autonomy_loop.py`, `docs/RESEARCH_LOOP_FOUNDATION.md` | Blocked review |
| Stage2 RH RO | Kanban `t_c8e95876` | RH snapshot / capital docs | Done |

---

## Merge / touch rules

1. **Research package** (`trader_platform/research/`): prefer CoS worker completion; other agents only append CLI recipes or docs pointers.
2. **Learn tick** (`learn_tick.py`): outcome → scoreboard → safe hyp transitions; import research DB read-only.
3. **hypotheses.yaml**: both promote-top and learn-tick may write — keep transitions legal; never write `live` from automation.
4. **Justfile**: append-only recipes when possible; avoid reordering CoS research block.
5. **Crons**: research + learn on **`trader` profile only**; never CoS; never agentic_live.

---

## How to signal

```bash
# Durable work
hermes kanban --board trading-strategies create --assignee trader \
  --workspace /Users/jarvis/dev/tsla-tsll-options-tracker \
  --created-by <you> \
  --body "Lane / files / gates / verify" "Short title"

# Comment when done
hermes kanban --board trading-strategies comment <task_id> "lane=… files=… verify=… next=…"
```

Update the table above in the same commit or handoff comment.

---

## Next shared milestone

**Self-learning tick v0 closed loop (paper):**

1. L1 research-tick-paper (CoS)  
2. L1 promote-top candidates (CoS)  
3. L3 learn-tick --apply (this lane)  
4. Optional L2 paper-scout manual  
5. Ken review blocked desk brief + M2  

Live arming remains a separate Ken decision.

# Trader loops + learn-promote (shared goal)

**Pinned 2026-07-09.** This is the shared map so **jarvis-coordinator**, **trader**, Kanban workers, and CLI sessions build toward the **same goal** without overstepping.

North star: [TRADER_PLATFORM_GOAL.md](TRADER_PLATFORM_GOAL.md)  
Autonomy: [AGENTIC_AUTONOMY_POLICY.md](AGENTIC_AUTONOMY_POLICY.md)  
Research cron (paper only): [RESEARCH_CRON.md](RESEARCH_CRON.md)

---

## Who owns what

| Lane | Owner | May do | Must not do |
|------|--------|--------|-------------|
| **Route / unblock** | `jarvis-coordinator` (CoS) | Park work on `trading-strategies` → assignee `trader`; summarize; gate approvals | Own RH MCP, place orders, edit strategy defaults, run learning as CoS skills |
| **Research rank + capital promote** | CoS-delegated worker / trader on board | Multi-symbol research tick; promote-top → **candidates only** | Trading cron; live arming |
| **Learn tick / hyp status** | `trader` + `learn_tick` | Evaluate outcomes; candidate↔testing↔paper; scoreboard | Auto → shadow/live; place_* |
| **Income desk** | `trader` + desk brief | PMCC + short-premium status | Orders without mandate |
| **Live sleeve** | Ken arm only | Stage1 OAuth + fund + options + `agentic.enabled` | Silent cron live |

**Last known CoS step (2026-07-09):** async worker `deleg_5c03b11e` — *capital-aware multi-symbol research pipeline: wire top-N → paper candidates*. That lane owns `trader_platform/research/*` promote/capital. **Learn-tick lives beside it**, not inside CoS.

---

## Named loops (Loopy-shaped)

Each loop: **bounded pass → check → keep/discard → stop/hand back**.

### L1 — Research tick (daily, paper)

```text
universe → score vol/premium/alpha + capital → rank → research.db → dated report
optional: promote-top → hypothesis status=candidate only
```

```bash
just research-tick-paper -- --sleeve-usd 5000
just research-promote-top -- --top 5 --sleeve-usd 5000   # optional
# or one shot:
just research-tick -- --sleeve-usd 5000 --write-report --promote --promote-top 5
```

**Cron OK** on `trader` profile (see RESEARCH_CRON.md). **Not** a trading cron.

### L2 — Paper scout tick (manual / future schedule)

```text
regime → eligible hyps → premium_scout → risk_governor → paper ledger
```

```bash
just platform-scout
just platform-paper-tick
just platform-scan          # shadow / no ledger mutate
```

**Default: do not Hermes-cron this until Ken + CoS agree.** Policy still forbids `agentic_live` cron until arming.

### L3 — Learn tick (self-improve, v0)

```text
paper ledger + autonomy audit + last research run
  → per-hypothesis verdict (SHIP|NULL|REJECT|NEEDS_MORE_DATA|…)
  → safe status transitions only (never shadow/live)
  → learn_audit.jsonl + optional RESEARCH_SCOREBOARD row
```

```bash
just learn-tick                    # dry-run evaluate
just learn-tick -- --apply         # apply candidate→testing / testing→paper
just learn-tick -- --apply --append-scoreboard
```

**Cron OK** on `trader` (weekly or daily after research). Never auto-live.

### L4 — Critic / lab week (heavy)

```text
propose knob/rule → just sweep|scenarios → scoreboard SHIP/NULL → STRATEGY.md
```

See [FREE_STRATEGY_RESEARCH_RUNBOOK.md](FREE_STRATEGY_RESEARCH_RUNBOOK.md). Not a silent cron until packaged.

### L5 — Desk brief (operating)

```text
data quality → PMCC monitor → live.py stance → action queue
```

```bash
just desk-brief
```

Review card: `t_9c8c8b9e` (blocked on Ken eyes).

---

## Learnables contract (“learn this”)

| Stage | What happens | Auto? |
|-------|----------------|-------|
| Messy idea / research rank | research.db + report | Yes (L1) |
| Paper candidate | promote-top → `candidate` | Yes (L1 optional) |
| Testing / paper evidence | learn_tick verdicts + transitions | Yes within safe graph (L3) |
| Shadow | promotion_gates + human | **No** |
| Live / agentic | Stage1 + fund + arm + allowlist | **No** |
| Skill / doctrine patch | Explicit Ken “learn this” / skillify | **No** silent skill spam |

Nulls go on `null_results` + scoreboard so we do not re-propose.

---

## Communication surfaces (so everyone knows)

| Surface | Purpose |
|---------|---------|
| **This file** | Shared loop map + ownership |
| `docs/BUILD_COORDINATION.md` | Active lane handoffs / what not to touch |
| Board `trading-strategies` | Durable work; assignee `trader`; workspace repo |
| `.cache/platform/learn_audit.jsonl` | Machine receipts for learn ticks |
| `.cache/platform/research_reports/` | Dated research receipts |
| CoS Telegram | Milestone only; details pull from artifacts |

When starting a build: **read this file + BUILD_COORDINATION.md**, comment the Kanban card with lane + files touched, avoid editing another open worker’s files.

---

## Hard forbidden (all agents)

- CoS owning broker MCP or trading skills allowlist for domain work  
- Auto-promote to **live** or **shadow** from learn/research ticks  
- Research universe collapsed to TSLA/TSLL only  
- Scheduling `autonomy_loop --mode agentic_live` before arming  
- Committing `pmcc_positions.yaml`, MCP tokens, raw secrets  

---

## History

### 2026-07-09 — Loops + learn-tick v0

Ken: fit Loopy/Learnables into trader; ticks that evaluate, learn, change hypotheses; do not overstep CoS; communicate shared goal. CoS last step `deleg_5c03b11e` capital-aware promote. Added `trader_platform/learn_tick.py`, this doc, BUILD_COORDINATION, `just learn-tick`.

## Schedule (paper only)

Hermes **trader** profile has inventory jobs `5b1b3e7803cf` / `d471a8e1d8e0`, but CoS is sole live Hermes gateway — those jobs do not fire unless a trader gateway is running.

**Primary schedule (Mac Mini LaunchAgents):**

| Job | Label | When (America/Los_Angeles) |
|-----|--------|----------------------------|
| Research tick | `com.jarvis.trader.research-tick-paper` | Mon–Fri 16:30 |
| Learn tick | `com.jarvis.trader.learn-tick` | Sun 17:00 |

Logs: `~/.local/state/jarvis/trader-cron/` and repo `.cache/platform/*_cron.log`.

# Trader Platform Goal (anti-drift pin)

> **Pinned 2026-07-09.** Future sessions must not redefine this product.
> Research-engine goal detail remains in root [GOAL.md](../GOAL.md).
> Autonomy / live-sleeve rules: [AGENTIC_AUTONOMY_POLICY.md](AGENTIC_AUTONOMY_POLICY.md).
> **Alignment / restart / clean-start vs tweak:** [TRADER_RESTART_CHARTER.md](TRADER_RESTART_CHARTER.md) — re-read before densified BUILD or doctrine changes.
> **Progress honesty:** [BUILD_PROGRESS_AND_CONFIDENCE.md](BUILD_PROGRESS_AND_CONFIDENCE.md) — ops complete ≠ strategy closer.

---

## North star

Build a **self-learning research + income engine** owned by Hermes profile `trader`:

| Layer | Freedom | Role |
|---|---|---|
| Research / hypothesis mutation | High | Discover, mutate, falsify edges |
| Backtest / walk-forward / scenarios | High | Deterministic validation harness |
| Paper / shadow | High | Simulate fills and order lifecycle |
| Live sleeve | **Autonomous** on the **isolated Agentic Robinhood account only** | No per-trade Ken approval once Stage1+`agentic_live` is armed |

**Isolated ≠ unlimited ruin.** Autonomy is always inside a deterministic risk governor: kill switch, max loss/day/position, strategy allowlist, audit log.

### Ownership

- **Coordinator** stays thin (route, summarize, unblock).
- **`trader`** owns broker MCP, strategy registry, risk envelope, execution loops.
- Seed strategies (PMCC / TSLA / TSLL short-premium) are **hypotheses**, not the ceiling.
- **Symbol freedom:** research ranks the multi-name universe; live risk allowlist is separate (and empty until armed). TSLA/TSLL are not the autonomous ceiling.
- **Strategy freedom:** full DNA (structure + entry + exit/management), not wheel-only. New structure classes are in-scope (build sim + catalog).

### Ranking doctrine (Ken pin 2026-07-10) — evidence, not plumbing

**Rank strategies by multi-name multi-structure evidence**, not by which paper path happens to be wired first.

| Rule | Meaning |
|---|---|
| **Rank keys** | Capital fit ($3k sleeve), regime stress, cost/slip falsification, multi-name multi-structure comparison |
| **Plumbing readiness** | **Parallel build debt**, never a rank key and never a reason to demote stronger DNA |
| **Incomplete OPEN path** | If CCS/IC (or any defined-risk class) lacks paper OPEN, **build the path** — do not force discovery/paper onto TSLL PCS alone |
| **XOM-style mid-slip** | Do **not** demote a stronger cost-adjusted mid-slip result solely because TSLL has `OPEN_PCS` wired |
| **Paper-first** | Research / paper / shadow only; **no** `place_*` live, agentic arm, or fund automation from ranking or wakes |

Wrong: “TSLL first because OPEN_PCS is ready.”
Right: “Rank by capital/regime/cost/falsify; wire missing paths in parallel so plumbing cannot limit discovery.”

### Better-trades doctrine (Ken pin 2026-07-10) — quality, not diversify-for-fear

**Strive for better trades.** Multi-name freedom is for **discovery**, not a capital-path quota.

| Rule | Meaning |
|---|---|
| **Capital path earns its seat** | A hyp stays on the capital / first-paper path only if it is independently a **better (or equal-quality) trade** on capital fit, regime, cost/slip, and edge quality |
| **Diversify-for-fear is lazy** | Do **not** promote or keep a name because it is “not TSLL,” “another ticker for eyes,” or a multi-name quota filler |
| **If only a TSLL diversifier** | **Remove from capital path** (park at `candidate` / research). Keep sim metrics for honest retest — re-enter capital path only when quality beats the bar without diversifier rationale |
| **Research stays multi-name** | Universe scout and evolve may still hunt non-TSLL DNA; promotion to testing/capital path requires **better-trade** evidence, not ticker count |
| **Paper-first** | Same hard gate: research / paper / shadow only; **no** live `place_*`, agentic arm, or fund automation from this pin |

Wrong: “Keep XOM CCS because we need a non-TSLL peer.”
Right: “Keep only DNA that wins (or ties) on trade quality; multi-name is a search space, not a portfolio mandate.”

### Edge stack (first principles)

1. **Regime** — trend / vol / stress classification
2. **Options structure** — skew, term, premium richness, liquidity
3. **Technical** — price/volume structure, levels
4. **Fundamental / catalysts** — earnings, product, macro, flow
5. **Emotional swings** — overreaction windows for tactical entries

Sleeves that use the stack:

- **Premium income** — sell/manage defined-risk or managed premium
- **Tactical quick in/out** — short-horizon asymmetric trades
- **Core long bias** — when regime supports; not forced always-on
- **Cash / stand-aside** — valid and preferred under bad edges

### Promotion path (non-negotiable)

```
research → paper → shadow → agentic_live
```

No auto-promote to live without an evidence record. See `trader_platform/promotion_gates.py`.

### What this is not

- Not guaranteed income
- Not unguarded market-order spam
- Not trading Ken’s main accounts without explicit separate mandate
- Not coordinator-owned broker credentials

### Current milestone

**M0–M2 (2026-07-09):** doctrine pinned; local hypothesis registry; risk governor; paper broker; autonomy loop in paper/dry-run; **research loop foundation** (`premium_scout`: regime→strategy→symbol→premium, paper-first). Package renamed `platform/` → `trader_platform/` (stdlib unshadowed). Live broker path stubbed until Stage1 OAuth + arming.

**Loops + learn-tick v0:** shared map [TRADER_LOOPS.md](TRADER_LOOPS.md) + coordination [BUILD_COORDINATION.md](BUILD_COORDINATION.md). Multi-symbol research (CoS lane) + `learn_tick` outcome→hyp status (never auto live/shadow).

**Agent-wake reframing (2026-07-09):** Trader profile SOUL + `trader-self-evolution` skill + Hermes agent crons. Ticks wake the agent free to improve itself; program recipes are optional tools. Cron-only `gateway-trader` (no Telegram).

---

## History

### 2026-07-10 — Better trades, not diversify-for-fear

Ken: if a name (e.g. XOM CCS `77766a47`) exists on the capital path **only as a TSLL diversifier**, remove it. Diversify-for-fear is lazy; strive for better trades. Complements the same-day plumbing pin: multi-name remains the research search space; capital/testing seats require independent trade quality, not ticker-count quota. Paper-first; no live/agentic/fund.

### 2026-07-10 — Rank by evidence, not plumbing

Ken rejects first-money / first-paper ordering that picks TSLL PCS solely because `OPEN_PCS` plumbing is ready. Durable pin: rank by capital/regime/cost/falsify across multi-name multi-structure DNA; treat incomplete CCS/IC paper OPEN as parallel build debt; do not demote stronger mid-slip non-TSLL DNA for wiring convenience. Paper-first; no live/agentic/fund from ranking.

### 2026-07-09 — Platform north star pinned

Ken: no per-build approval; build so it does not drift. Affirmed research→paper→shadow→live income engine. Isolated Agentic account gets autonomous limit-order freedom inside risk envelope; no per-trade Ken wait once armed. Cron/event-driven scanning allowed by design (local stubs only until Stage1).


## Stage2 progress (2026-07-09)

Completed: RH MCP read-only smoke (after-hours), risk review vs real accounts, paper→RH bridge (`PaperRhBridge` + snapshot readiness), strategy/capital plan tiers T0–T3.

**Blockers for live:** Agentic account ~$0 and no options level. Keep `agentic.enabled=false`.

Details: `docs/STAGE2_RH_READONLY_AND_CAPITAL.md`.

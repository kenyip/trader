# Trader Platform Goal (anti-drift pin)

> **Pinned 2026-07-09.** Future sessions must not redefine this product.
> Research-engine goal detail remains in root [GOAL.md](../GOAL.md).
> Autonomy / live-sleeve rules: [AGENTIC_AUTONOMY_POLICY.md](AGENTIC_AUTONOMY_POLICY.md).

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

---

## History

### 2026-07-09 — Platform north star pinned

Ken: no per-build approval; build so it does not drift. Affirmed research→paper→shadow→live income engine. Isolated Agentic account gets autonomous limit-order freedom inside risk envelope; no per-trade Ken wait once armed. Cron/event-driven scanning allowed by design (local stubs only until Stage1).


## Stage2 progress (2026-07-09)

Completed: RH MCP read-only smoke (after-hours), risk review vs real accounts, paper→RH bridge (`PaperRhBridge` + snapshot readiness), strategy/capital plan tiers T0–T3.

**Blockers for live:** Agentic account ~$0 and no options level. Keep `agentic.enabled=false`.

Details: `docs/STAGE2_RH_READONLY_AND_CAPITAL.md`.

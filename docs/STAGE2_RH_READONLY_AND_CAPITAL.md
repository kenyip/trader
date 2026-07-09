# Stage2 — RH read-only smoke, risk review, paper→RH wire, strategy/capital plan

**Status (2026-07-09):** Stage2 implemented for *read-only* path. **Do not arm `agentic_live`.**  
**Data quality:** after-hours MCP smoke (not RTH). Account numbers masked.

## Scope

| Piece | Outcome |
|-------|---------|
| RH read-only smoke | MCP `get_accounts` / portfolio / positions / quotes — **no place_*** |
| Risk review | Compared `trader_platform/risk_limits.yaml` vs real Agentic + main sleeves |
| paper→RH wire | `PaperRhBridge` + `rh_snapshot.py` + review_* payloads; place stays blocked |
| Strategy/capital plan | Funding tiers T0–T3; keep agentic.enabled=false until T1+ prerequisites |

## RH smoke findings (masked)

### Accounts visible to trader agent

1. **Agentic** (`••••8507`) — `agentic_allowed=true`, **cash**, **option_level empty**, **~$0** equity/cash/BP.  
2. **Individual / default** (`••••5223`) — `agentic_allowed=false`, **margin**, `option_level_3`, total ~**$84.8k** (equity ~$122k, options ~$2.9k, cash ~-$40k margin, BP ~$22.2k).

### Main sleeve positions (desk context only — **not** agentic execution target)

- Equities: **TSLL 7000**, CCL 100, NCLH 200, RCL 100.  
- Options (approx): TSLL 10× short Aug21 $16C; NVDA 1× short Aug21 $230C + 1× long 2028 $200C (PMCC-style); SPCX 1× short put.  
- **No TSLA cash shares** on this RH main account (TSLA share book may live elsewhere).

### Quotes at smoke (after-hours)

TSLA / NVDA / TSLL quotes successfully returned via MCP. Treat marks as **after-hours**.

## Risk review

Current `trader_platform/risk_limits.yaml` (summarized):

- `agentic.enabled: false` (soft kill) — **correct for T0**
- max notional / order ~$2,500; max contracts 5; max open risk $5,000; max daily loss $750
- instrument allowlist: TSLA, NVDA, TSLL
- kill switch file: `agentic_kill.switch`

**Verdict vs live RH state:**

| Check | Result |
|-------|--------|
| Isolation (main non-agentic) | PASS — main correctly non-agentic for this agent |
| Agentic funded | **FAIL** — $0 |
| Agentic options level | **FAIL** — empty (need option_level_2+) |
| Limits vs capital | Limits assume a funded sleeve; with $0 capital they are fine as *paper* ceilings but **live arming must stay off** |
| Daily loss $750 | Too large for T1 $2.5k seed (~30% of capital) — scale down on fund |

### Recommended limit scales (Agentic capital only)

| Agentic capital | max_notional | max_contracts | max_open_risk | max_daily_loss | max_open_orders |
|-----------------|--------------|---------------|---------------|----------------|-----------------|
| $0 (now) | keep paper defaults | 2 | 2500 | 250 | 3 |
| $2,500 T1 | $250 | 2 | $625 | $250 | 3 |
| $5,000 T2 | $500 | 2–3 | $1,250 | $500 | 3 |
| $10,000 T3 | $1,000 | 3–5 | $2,500 | $750 | ≤10 |

CLI: `just platform-rh-readiness` (or `.venv/bin/python -m trader_platform.rh_readonly_cli`).

## paper→RH wire (code)

| Component | Role |
|-----------|------|
| `trader_platform/rh_snapshot.py` | Masked snapshot schema, readiness, capital-tier helpers |
| `.cache/platform/rh_readonly_snapshot.json` | Local snapshot (**gitignored**) written after MCP smoke |
| `PaperRhBridge` | Paper ledger mutations + RH snapshot portfolio/readiness |
| `RhMcpReadAdapter` / review_* builders | Payload only; no place from bare Python |
| `RobinhoodMcpBroker` | Fail-closed place (`LiveOrdersBlocked` / NotConnected) until arming |
| `autonomy_loop` | Uses bridge by default; shadow/dry-review emit review_*; readiness blocks agentic_live when snapshot unfunded |

**Hard rule:** platform code never calls `place_*` / `cancel_*` MCP tools. Hermes trader session owns OAuth; snapshot is the offline handoff.

### Operator flow

1. Trader Hermes session: MCP read-only (`get_accounts`, portfolio, positions).  
2. Write masked snapshot → `.cache/platform/rh_readonly_snapshot.json`.  
3. `just platform-rh-readiness` → expect blockers until funded + options level.  
4. `just platform-paper-tick` / `just platform-scan` — paper/shadow only.  
5. **No** `agentic.enabled=true` until capital plan prerequisites met.

## Strategy / capital plan

### Principles

1. **Agentic sleeve is isolated capital** — never point agentic_live at the main margin book.  
2. Main book (TSLL / NVDA PMCC / cruises) stays **manual + playbook / PMCC manager**, not autonomy_loop.  
3. Agentic strategies start as **hypothesis registry** entries with explicit allowlists — not full desk automation.  
4. LEAPS / share inventory for core PMCC remains human-managed (core-vs-income sleeve split).

### Funding tiers

| Tier | Capital | Modes | Arm live? |
|------|---------|-------|-----------|
| **T0_unfunded** (current) | $0 | research / paper / shadow | **No** |
| **T1_seed** | $2,500 | + tiny live after gates | Only after options level + risk yaml retune + Ken explicit OK |
| **T2_income_lab** | $5,000 | small short-premium / 1-lot experiments | After ≥5 clean paper days + promotion evidence |
| **T3_scaled** | $10,000 | still << main account | Allowlist + kill-switch drill only |

### Prerequisites before any agentic_live

1. Fund Agentic to at least **T1**.  
2. Enable **option_level_2+** on Agentic (if options).  
3. Retune `risk_limits.yaml` to capital table above.  
4. Keep `agentic.enabled: false` until Ken flips it deliberately.  
5. Stage1 place_* wire still **NotImplemented** — separate task after paper evidence.  
6. Kill switch drill: touch `agentic_kill.switch` and confirm deny.

### Strategy allowlist (initial)

- `hyp_stand_aside` always valid.  
- Short-premium / PMCC income hyps: **paper/shadow only** until T2.  
- Instruments for agentic sleeve: prefer **TSLA/TSLL** first; NVDA only if capital and risk re-approved (main already holds NVDA PMCC).  
- Do **not** auto-manage cruise names or SPCX from agentic loop.

## What Stage2 does *not* do

- No live order placement or cancel.  
- No automatic funding or options enrollment.  
- No moving main-account positions into agentic control.  
- M2 short-premium scout wired (`trader_platform/premium_scout.py` → intents); PMCC structure scout still deferred.
- No place_* / no agentic_live arming.

## Commands

```bash
just platform-smoke
just platform-rh-readiness
just platform-paper-tick
just platform-scan          # shadow
.venv/bin/python -m trader_platform.autonomy_loop --mode paper --dry-review --once
```

## Acceptance (Stage2)

- [x] RH read-only MCP smoke completed (after-hours labeled)  
- [x] Snapshot + readiness CLI report blockers on $0 / no options  
- [x] Risk review + capital tiers documented  
- [x] Paper→RH bridge + review_* wire; place fail-closed  
- [x] `just platform-smoke` green  
- [ ] Ken funds Agentic + options level (human ops — out of band)  
- [ ] Stage1 place_* implementation (future card)

## Related

- `docs/AGENTIC_AUTONOMY_POLICY.md`  
- `docs/TRADER_PLATFORM_GOAL.md`  
- `docs/PROMOTION_GATES.md`  
- `trader_platform/risk_limits.yaml`  

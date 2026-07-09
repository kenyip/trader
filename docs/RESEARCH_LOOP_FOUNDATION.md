# Research Loop Foundation (M2) — regime → strategy → symbol → premium scout

**Status:** paper-first foundation (2026-07-09)  
**Package:** `trader_platform/` (renamed from `platform/` so stdlib `platform` is not shadowed)  
**Code:** `trader_platform/premium_scout.py`, wired into `trader_platform/autonomy_loop.py`

---

## Pipeline

```
1. REGIME    features via live.make_recommendation → data.build (regime, iv_rank, high_iv, reversal)
2. STRATEGY  hypothesis registry: premium sleeve, status in {testing, paper, shadow, live}
             (PMCC entry_logic_ref skipped in v1 scout — separate structure later)
3. SYMBOL    instruments listed on each eligible hypothesis
4. PREMIUM   live.make_recommendation / pick_entry → SELL_PUT | SELL_CALL | STAND_ASIDE
5. PAPER     autonomy_loop risk_check → paper place/replace (or shadow / dry-review)
```

**Stand-aside is success.** No intent is not a crash.

**Never places live** from the scout itself. `agentic_live` remains blocked until Stage1 OAuth + `agentic.enabled` + readiness.

---

## Commands

```bash
# Offline scout smoke (no network)
just platform-scout -- --stub

# Live scout (uses same path as just test)
just platform-scout
just platform-scout -- --symbols TSLA TSLL --json

# Paper tick with real scout → risk → paper ledger
just platform-paper-tick

# Shadow (log + review_* payloads only)
just platform-scan

# Offline paper tick (CI / no market data)
.venv/bin/python -m trader_platform.autonomy_loop --mode paper --once --stub-proposals

# Full smoke (registry + risk + paper + scout stub + Stage2 bridge)
just platform-smoke
```

---

## Intent shape

Sell intents:

- `side=sell`, `order_type=limit`
- `limit_price` = model `estimated_credit` (paper-first; live chain marks later)
- `strategy_id` = hypothesis id
- `tag` = `scout:<event>|<put|call>|K=...|dte=...|exp=...`

Audit:

- `.cache/platform/premium_scout.jsonl` (scout)
- `.cache/platform/autonomy_audit.jsonl` (tick)

---

## Explicit non-goals (this foundation)

- No `place_*` on Robinhood
- No PMCC LEAPS/short-call structure scout yet
- No auto-promotion of hypotheses
- No cron that mutates anything beyond paper ledger

---

## Package rename note

`platform/` → `trader_platform/` because the local package name collided with the Python **stdlib** `platform` module and broke `pandas`/`scipy` imports for `live.py` and related tools. Prefer:

```bash
.venv/bin/python -m trader_platform.autonomy_loop ...
.venv/bin/python -m trader_platform.premium_scout ...
.venv/bin/python -m trader_platform.hypothesis_cli ...
```

Just recipes: `just platform-*` still work (they call `trader_platform`).

---

## Related

- `docs/TRADER_PLATFORM_GOAL.md`
- `docs/AGENTIC_AUTONOMY_POLICY.md`
- `docs/STAGE2_RH_READONLY_AND_CAPITAL.md`
- `docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md`
- `docs/PROMOTION_GATES.md`

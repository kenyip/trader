# Multi-Symbol Research Loop

**Status:** paper-only capital-aware research scout (2026-07-09)  
**Package:** `trader_platform/research/`  
**Pin:** **Research universe ≠ live risk allowlist.** Multi-symbol ranking is mandatory.

---

## Doctrine

| Layer | Scope | Gate |
|-------|--------|------|
| **Research universe** | Broad liquid multi-name list (`universe.yaml`) | Ranks opportunity only; no orders |
| **Live instrument allowlist** | `risk_limits.yaml` → `instrument_allowlist` (e.g. TSLA, TSLL) | **LIVE / paper order** gate only |
| **Agentic live** | `agentic.enabled` + Stage1 OAuth + readiness | Still false / blocked |

Research ticks **must not** be limited to TSLA/TSLL. Those names are *members* of the universe, not the whole universe. Expanding live trading remains a separate, deliberate risk decision.

---

## Pipeline

```
1. UNIVERSE   trader_platform/research/universe.yaml  (indexes + mega-cap + high-beta)
2. FEATURES   data.build(symbol) → hv, iv_rank proxy, regime, ema_stack, …
3. SCORE      vol / premium / alpha proxies → composite
4. CAPITAL    spot, 100*spot, CSP BP proxy, long debit proxy, contracts @3k/5k/15k, capital_fit
5. RANK       top N by composite (optional --sleeve-usd pilot filter on tops)
6. STORE      SQLite: research_runs, symbol_scores, opportunities (+ capital columns)
7. PROMOTE    optional: top-N → hypothesis candidates (never live)
8. BACKTEST   optional hooks: engine Backtester when importable
```

Scores are **proxies**, not guaranteed alpha:

| Score | Meaning (honest) |
|-------|------------------|
| **vol** | Realized-vol level + expansion (hv_20 vs hv_60) |
| **premium** | `iv_rank` (HV-based proxy) + quiet-path-vs-vol residual — **not** live option chain IV |
| **alpha** | Trend strength + RSI edge + momentum alignment — **edge proxy**, not proven alpha |
| **composite** | `0.35*vol + 0.40*premium + 0.25*alpha` |
| **capital** | CSP BP ≈ 0.95×100×spot; long debit ≈ 2%×spot×100 — **not** broker margin |

Optional: regime → `strategy_family` hint attached to top symbols (research only).

---

## Commands

```bash
# Show research universe (must be multi-name)
just research-universe
# or
.venv/bin/python -m trader_platform.research universe

# One research tick — rank all universe symbols (+ capital table)
just research-tick
.venv/bin/python -m trader_platform.research tick --top 10

# Pilot sleeve filter + dated report
just research-tick-paper -- --sleeve-usd 5000 --top 12
just research-tick -- --sleeve-usd 3000 --write-report --promote --promote-top 5

# Wire last run top-N → paper candidates (never live)
just research-promote-top -- --top 5 --sleeve-usd 5000
just research-promote-top -- --run-backtests --dry-run

# Re-print last run tables (incl. capital)
just research-report
.venv/bin/python -m trader_platform.research report
```

SQLite DB (default): `.cache/platform/research.db`  
Dated reports: `.cache/platform/research_reports/YYYY-MM-DD_run{N}.md`  
Recurring paper-only schedule: **`docs/RESEARCH_CRON.md`** (no trading cron).

---

## Relation to premium_scout (M2)

| Module | Role |
|--------|------|
| `trader_platform/research/` | **Which symbols** look best (broad universe ranking + capital fit) |
| `trader_platform/premium_scout.py` | **Given** eligible hypotheses/instruments → sell-put/call intents for paper |

Research scout can inform which symbols to study next; it does **not** place orders.  
`premium_scout` still never places live; autonomy loop paper path remains the only mutator of the paper ledger.

Promote path writes **candidate** hypotheses only (`hyp_research_*`). No auto-promote to live.

---

## Forbidden

- Limiting the research universe to TSLA/TSLL only  
- Using `instrument_allowlist` to cap research ranking  
- `place_*`, funding, or `agentic.enabled=true` from this loop  
- Treating composite scores as guaranteed edge  
- Trading cron / agentic_live schedule  

---

## Files

```
trader_platform/research/
  universe.yaml   # configurable multi-symbol list
  universe.py
  scorer.py
  capital.py      # capital-by-price sizing + sleeve filter
  store.py        # SQLite (+ capital columns)
  loop.py
  promote.py      # top-N → hypothesis candidates (never live)
  backtest_hooks.py  # optional engine hooks
  __main__.py     # CLI: tick | report | universe | promote-top
docs/RESEARCH_LOOP.md
docs/RESEARCH_CRON.md
```

---

## Related

- `docs/RESEARCH_CRON.md` — paper-only recurring tick (no trading cron)  
- `docs/RESEARCH_LOOP_FOUNDATION.md` — regime→strategy→symbol→premium intents  
- `docs/STAGE2_RH_READONLY_AND_CAPITAL.md` — funding tiers  
- `docs/TRADER_PLATFORM_GOAL.md`  
- `docs/AGENTIC_AUTONOMY_POLICY.md`  
- `trader_platform/risk_limits.yaml` — live gate only  

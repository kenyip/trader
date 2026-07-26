# Engine prove → Hermes Trader handoff

**Generated:** 2026-07-19  
**Updated:** 2026-07-26 — progress pack tools (first-live / multi-reprove shortlist / shadow)  
**Status:** Engine plumbing proven; starter pack is **thin L0 research DNA** — Trader owns ops, not self-arm live.

## Prove results (this run)

| Gate | Result |
|---|---|
| Unit suite (Desk B spine) | **68 passed** |
| Dual-cost bootstrap re-prove | 6 candidates → **4 F2**, 2 seeds closed |
| Shortlist (symbol+DNA diversify) | **2 seats**: AMZN densify, IWM densify |
| Path stress (quick→full, DTE-aware) | **Both staged_pass=true** |
| Paper promote | Both seats **paper_eligible (F3)** |
| Watch | `PAPER_PACKET_READY` (IWM PCS on latest bar) |
| Dry paper handoff | **PAPER_INTENT_READY** (risk allowed, no mutate) |
| Plumbing smoke | **PAPER_PLACED** (forced bullish KO — ledger path only) |

### Dual-cost honesty

| Candidate | Decision | Why |
|---|---|---|
| Thesis seeds (bull_neutral 45d, iv_rich 21d) on BAC/KO | **FAMILY_CLOSED** | Negative dual-cost PnL / DD / control beat |
| AMZN densify (7 DTE, IV≥40, bull-only) | **F2** | Thin n≈9 trades — passes gates, smell remains |
| IWM densify family (14 DTE) | **F2** | Fragile train PnL; holdout stronger |

### Path stress notes

- Windows are **DTE-aware** (`long_dte + 7`, floor 21). These seats are 7/14 DTE → 21d windows.
- AMZN mostly **stand-aside** on dump/up/flat; one gap trade → profit_target.
- IWM: `huge_down→normal_down` fallbacks; vol_expansion lost ~$50 within risk (management saw profit_target / losses).

**L0 only:** black-scholes proxy marks. Not observed chains. Not live edge.

## Starter pack (Trader may paper-watch)

1. `PCS_BULL_NEUTRAL_INCOME_45D_PT50_V1__dn_d7_pt60_dl22_iv40_c8_w1_pcs_bu_0` @ **AMZN**  
2. `PCS_IV_RICH_NONCOLLAPSE_21D_PT50_V1__dn_d14_pt60_dl14_iv30_c10_w1_pcs_bu_4` @ **IWM**

Specs live under `.cache/platform/spine/discovery/…` (local). Registry seats are `paper_eligible`.

## Operator surface (Trader defaults)

```bash
just trader-status
just trader-first-live-lane               # MCP single-leg capital-fit board
just trader-multi-symbol-reprove --from-shortlist
just trader-shadow-rehearsal              # deliberate shadow (stub=PARTIAL only)
just trader-run-now progress              # one-shot progress pack + status
just trader-progress
just trader-bootstrap --candidates-only   # or full re-prove
just trader-path-stress --spec <spec.json> --symbols SYM
just trader-opportunity                   # watch + handoff (no evolve)
just trader-paper-handoff                 # dry default
just trader-paper-handoff --plumbing-smoke
just trader-promote-paper --top 5
# CPU discovery (not the primary wake): just trader-discover
```

### Dual lane (2026-07-26)

| Surface | Role |
|---|---|
| `QUALITY_SHORTLIST.json` | Research/paper multi-leg stress survivors |
| `FIRST_LIVE_LANE.json` | RH MCP placeable single-leg fit_3k seats |
| `MULTI_SYMBOL_REPROVE.json` | Pack-grade honesty (`--from-shortlist` includes AAL/BAC) |
| `.cache/platform/shadow/LATEST.json` | Deliberate shadow window |

Do **not** promote multi-leg shortlist leaders as first arm DNA while MCP place is single-leg only.

**Primary path:** StrategySpec → evaluate_proxy → living seat → path stress → watch → RiskGovernor → paper.  
**Secondary:** StrategyDNA / scout — only if spine has no seats.

## What Trader should do first

1. Orient from `docs/TRADER_BUILD.md` (only build bible).  
2. Keep starter pack healthy: opportunity loop, dry handoff, residual notes.  
3. **Do not** treat densify F2 as durable edge — densify only proven DNA; kill clones.  
4. Prefer **new thesis proposals** that re-clear dual-cost + path stress over draining cartesian bags.  
5. **Never** agentic_live without Ken arm.  
6. Paper execute only with explicit paper_eligible + RiskGovernor allow.

## Next steps — DONE (2026-07-19)

| # | Item | Status |
|---|---|---|
| 1 | Hermes SOUL / AGENTS / skill / MEMORY pin to BUILD + handoff | **Done** |
| 2 | `just trader-paper-loop` for starter seats | **Done** (ops recipe) |
| 3 | Multi-symbol re-prove densify DNA | **Done** — see below |
| 4 | Stronger quality bars | **Done** — `configs/quality_bars.json` (min 12 trades, ≥2 symbols F2, path min 3 windows) |
| 5 | Densify-winners-only policy | **Done** — BUILD + discovery policy; dense grid not default |

### Multi-symbol re-prove result (`MULTI_SYMBOL_REPROVE.json`)

| DNA | F2 symbols | Thick (≥12 holdout trades) | quality_pass |
|---|---|---|---|
| AMZN densify 7d | **AMZN only** (n=9) | none | **false** |
| IWM densify 14d | **IWM only** (n=9) | none | **false** |

**Honest conclusion:** Starter seats remain **paper plumbing pack**, not pack-grade edge. Trader should exercise paper ops and invent/re-prove **new multi-symbol DNA** rather than promote these to “edge found.”

## Trader first-week loop

```bash
# RTH / daily ops
just trader-paper-loop
just trader-opportunity

# Off-hours research (not dense marathon)
just trader-bootstrap --candidates-only
just trader-multi-symbol-reprove
just trader-path-stress --spec <survivor.json> --symbols SYM
# optional: just trader-discover   # Wave A densify only
```

## Engine health patches this prove cycle

- Paper handoff data period fallback (`3mo→1y→2y→5y`)
- Path stress DTE-aware windows + staged quick→full
- Multi-symbol re-prove + quality bars
- Hermes profile pin

---

**Bottom line for Ken:** Engine **ops-ready** for Hermes Trader. Starter pack is **thin single-name L0 densify** — use for paper residual, not edge claims. Multi-symbol quality bar correctly rejects pack-grade promotion.

# Engine prove → Hermes Trader handoff

**Generated:** 2026-07-19  
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
just trader-progress
just trader-bootstrap --candidates-only   # or full re-prove
just trader-path-stress --spec <spec.json> --symbols SYM
just trader-opportunity                   # watch + handoff (no evolve)
just trader-paper-handoff                 # dry default
just trader-paper-handoff --plumbing-smoke
just trader-promote-paper --top 5
# CPU discovery (not the primary wake): just trader-discover
```

**Primary path:** StrategySpec → evaluate_proxy → living seat → path stress → watch → RiskGovernor → paper.  
**Secondary:** StrategyDNA / scout — only if spine has no seats.

## What Trader should do first

1. Orient from `docs/TRADER_BUILD.md` (only build bible).  
2. Keep starter pack healthy: opportunity loop, dry handoff, residual notes.  
3. **Do not** treat densify F2 as durable edge — densify only proven DNA; kill clones.  
4. Prefer **new thesis proposals** that re-clear dual-cost + path stress over draining cartesian bags.  
5. **Never** agentic_live without Ken arm.  
6. Paper execute only with explicit paper_eligible + RiskGovernor allow.

## Known gaps / next steps (decide with Ken)

| Priority | Item | Why |
|---|---|---|
| P0 | Hermes SOUL/skill pin to TRADER_BUILD + this handoff | Trader alignment |
| P1 | Multi-symbol re-prove of densify DNA (not one ticker) | Reduce single-name luck |
| P1 | Thicker trade-count bar or multi-window path stress | Thin n_trades F2 |
| P2 | Auto path-stress in bootstrap report | One command prove |
| P2 | F4 observed paper residual after real manage/close | Confidence ladder |
| Later | Live arm packet | Ken only |

## Engine health patches this prove cycle

- Paper handoff data period fallback (`3mo→1y→2y→5y`) — fixed IWM dry intent after watch ready.
- Path stress DTE-aware windows.
- Staged quick→full path stress.

---

**Bottom line for Ken:** The engine runs end-to-end and can feed Trader a **paper-ready starter pack of 2 L0 densify survivors**. Ready for Trader **ops ownership**. Not ready to claim edge or go live.

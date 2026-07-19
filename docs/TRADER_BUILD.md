# Trader — Build Bible

**This is the single document to open for build and alignment.**  
Everything else in `docs/` is detail, ops runbooks, or research archive.

| | |
|---|---|
| **Status** | Living — update when doctrine or spine changes |
| **Pinned** | 2026-07-19 |
| **Audience** | Ken, Jarvis, Trader agents, implementers |
| **Repo** | `~/dev/trader` · GitHub `kenyip/trader` |

**Index of other docs:** [README.md](README.md) (this folder).

When code or agents conflict with this file: **change the code/agent**, or amend this file with a changelog entry. Do not re-introduce unbounded cartesian knob thrash as the primary edge path.

---

## 1. Dual desk (one monorepo)

| Desk | Purpose | Live money? |
|---|---|---|
| **A — Personal** | Positions, PMCC, TSLA/TSLL methods, desk brief, AI coaching | Ken’s book only; no auto-trade |
| **B — Agentic** | Find edge → prove → wait → paper → **Ken-armed** live on **$3k sleeve** | Only after explicit arm |

Same repo, separate authority. Desk B never trades Desk A’s account.

---

## 2. Why we build (edge, not vanity)

**Goal:** Find and run a durable **advantage** on a small defined-risk sleeve — not maximize backtest count, wake volume, or green tests alone.

**Edge means:** In a named **regime**, a named **thesis** produces **opportunities** that, after realistic costs and time discipline, have acceptable expectancy and tails — and the same rules still fire in paper/live (no silent zero-trade “wins”).

| Success | Not success |
|---|---|
| Thesis survives dual-cost chronological proof | 800 near-duplicate F2 clones |
| Paper proves plumbing | Paper used as the only “edge” claim |
| Stand-aside when no setup | Trading for activity |
| Live only when Ken arms | Self-arm / main-book bleed |

**Stand-aside is a valid win.**

Promotion path (non-negotiable):

```text
research → paper → shadow → agentic_live (Ken-armed)
```

---

## 3. North-star pipeline (build toward this)

Invert “grid of knobs first.” Product orientation:

```text
Market data
  → SIGNALS          named, timestamped observables
  → OPPORTUNITY      who / when / why  — or stand_aside
  → STRUCTURE        option type, exp, strikes, entry premium rule
  → MANAGEMENT       close premium / time / risk / thesis stops
  → PROVE            program sim: train → holdout, costs, gates
  → EXECUTE          RiskGovernor → paper → Ken-armed live
  → LEARN            score thesis × regime; extend catalog; densify winners only
```

| Layer | Program | Human / LLM |
|---|---|---|
| Compute signals | ✅ | Propose new features |
| Opportunity templates | ✅ rules / small models | Invent new templates |
| New thesis / mechanism | weak alone | ✅ sparse, deliberate |
| Structure + manage DNA | library + defaults | First draft |
| Cartesian 10⁵ knob search | ❌ not primary | ❌ worse |
| Dual-cost proof & ranking | ✅ only | ❌ |
| Order path | ✅ only | **Forbidden** |

**LLM proposes; programs measure and trade.**

### Layered edge (condensed)

A named structure is not a strategy. A strategy is a **falsifiable forecast** expressed through a payoff, in a regime, with risk and evidence:

1. Market / symbol set  
2. Forecast type (e.g. non-collapse, vol premium)  
3. Economic mechanism  
4. Option structure  
5. Greeks intended / dangerous  
6. Regime envelope + stand-aside  
7. Entry trigger (lag-safe)  
8. Exit / management  
9. Capital fit ($3k, ~$300 max loss / lot)  
10. Evidence / falsifier  
11. Confidence stage (F* / L*)  

Full table: [TRADER_LAYERED_EDGE_DOCTRINE.md](TRADER_LAYERED_EDGE_DOCTRINE.md).

---

## 4. Core objects (canonical vocabulary)

Use these names in code, configs, and agent prompts.

| Object | Meaning |
|---|---|
| **Signal** | Observable feature at `asof` (not a vibe) |
| **Opportunity** | Thesis + symbol + regime + evidence → trade *or* stand_aside |
| **StructurePlan** | PCS/CCS/IC/… + exp + strikes + entry premium rule + max loss |
| **ManagementPlan** | Profit take, time/risk/thesis stops (frozen **with** entry) |
| **Thesis** | Named mechanism + opportunity rules + structure/manage defaults + prove gates + score dimensions |
| **StrategySpec** | Current frozen JSON claim (implementable thesis DNA) |
| **EvaluationReport** | Dual-cost train/holdout result |
| **Living seat** | F2+ research claim in registry — **not** live authority |

Identity preference: `thesis_id + symbol + coarse DNA` over thousands of mutant suffixes.

### Opportunity → option geometry

Only after opportunity:

- **symbol** — liquidity + thesis fit + capital fit  
- **structure** — PCS / CCS / IC / …  
- **expiration** — DTE band or calendar rule  
- **strikes** — delta / %OTM / width rules  
- **entry premium** — min credit % width or $ floor  
- **manage** — % of credit, dte_stop, delta breach, regime flip  

One opportunity → **1–3** structures max (not a full grid).

---

## 5. Prove spine (what the sim actually does)

**Implementable path today** (keep; re-aim identity toward theses):

```text
StrategySpec
  → evaluate_proxy()     black-scholes proxy on daily bars
  → dual-cost train (60%) then sealed holdout (40%)
  → living registry seat if F2
  → opportunity watcher → paper handoff → RiskGovernor
```

### Dual cost (must clear **both**)

| Axis | Meaning |
|---|---|
| `slip_5pct` | 5% adverse slip on marks |
| `fixed_0p01` | $0.01 half-spread per leg |

### Gates (typical; per seed `discovery_gates`)

| Gate | Bar |
|---|---|
| min_trades | ≥ 8 |
| positive PnL | > 0 after costs |
| max_loss_usd | ≤ ~$300 |
| max_dd | ≤ ~$150 discovery |
| integrity | ledger consistent |
| control beat | optional on train |

### Funnel

```text
F0_MECHANISM → F1_TRAIN → F2_UNTOUCHED_HOLDOUT
  → F3_ROBUST_PAPER_PLAN → F4_OBSERVED_PAPER
```

| Stage | Meaning |
|---|---|
| F0 / quarantined | Train fail |
| F1 | Train pass; holdout fail or not proven |
| F2 | Holdout dual-cost pass → living research seat |
| F3+ | Paper plan / observed paper |

### Confidence ladder (live money)

| Level | Meaning | Live $? |
|---|---|---|
| L0 | Sims / research | No |
| L1 | Non-vacuous after-cost edge claims | No |
| L2 | Multi-session paper open/manage/close | No |
| L3 | Shadow propose → risk → log | No |
| L4 | Funded + **Ken arm** + 1-lot | Yes, gated |

**Proxy BS marks cannot earn L1 observed-surface claims.** Missing Schwab history does not freeze all research.

### Ranking (among F2 only)

1. Worst dual-cost **holdout** PnL (higher better)  
2. Then lower max DD  

Pass/fail is gates; ranking is soft. Clone floods ≠ many edges.

Detail: [TRADER_SPINE_ARCHITECTURE.md](TRADER_SPINE_ARCHITECTURE.md), [DISCOVERY_AND_PAPER_FASTTRACK.md](DISCOVERY_AND_PAPER_FASTTRACK.md).

---

## 6. Evaluation dimensions (extensible)

**Gates** = hard constraints. **Scores** = ranking among passers.

New ideas (human or self-learning) enter as:

1. **Name + hypothesis**  
2. **Definition** (formula, units, higher/lower better)  
3. **Gate vs score** (explicit)  
4. **Implement + prove** on dual-cost holdout / paper residual  
5. **Changelog** (§12)

### Current primary

Dual-cost PnL, n_trades, max_loss, max_dd, integrity (± control beat).

### Candidates (adopt without redesign)

| Dimension | Hypothesis | Status |
|---|---|---|
| **Premium / day** (PnL or credit capture per day held) | Prefer efficient use of sleeve time | **Hypothesis — prove** |
| Credit % of width | Richer short-vol setups | Partial entry filter |
| PnL / max_loss (R) | Normalize by risk unit | Candidate |
| Time-to-50%-credit | Faster winners free capital | Candidate |
| Stand-aside purity | Correct non-trades matter | Partial |
| Regime-conditional expectancy | Edge only in regime R | Candidate |
| Fill residual (proxy − live) | Cost realism | Later L1 |

**Premium/day draft:**

```text
premium_per_day = (entry_credit - exit_debit) / max(days_in_trade, 1)
```

May become score, manage rule, or optional gate **after** evidence — never a silent hard gate.

---

## 7. Learning & search policy

| Allowed | Forbidden without deliberate promote |
|---|---|
| Local densify of **proven** DNA (±1 step) | Full 10⁵ cartesian bag as “progress” |
| Thesis × regime scoreboard | Silent gate loosening |
| Symbol tier promote/demote on evidence | LLM-written orders |
| Coarse Wave A screen → prove → densify | Self-arm live |

**Search policy that worked operationally:** coarse bag + core symbols screen + prove on growth names + densify winners — **not** drain a 300k product.

Self-learning may **propose** signals, dimensions, or thesis kills; **promotion** into catalog/gates is deliberate.

---

## 8. Authority & safety

| Mode | Meaning |
|---|---|
| `research` | Sims / hypotheses only |
| `paper` | Local ledger (default autonomy path) |
| `shadow` | Propose + risk-check + log; no broker mutate |
| `agentic_live` | Real orders on **isolated** Agentic account only |

Hard stops:

- No live without Ken arm + risk envelope  
- No main-book trading from Desk B  
- No secrets / private positions in git  
- RiskGovernor always on for mutate paths  

Detail: [AGENTIC_AUTONOMY_POLICY.md](AGENTIC_AUTONOMY_POLICY.md), [PROMOTION_GATES.md](PROMOTION_GATES.md), [GO_LIVE_READINESS.md](GO_LIVE_READINESS.md).

---

## 9. Operator commands (Desk B)

```bash
just setup
just trader-progress              # bag + F2 + parallel workers
just trader-progress --watch
just trader-discover              # tight sim discovery (proof)
just trader-universe              # managed underlyings add/remove
just trader-promote-paper         # F2 → paper_eligible (symbol+DNA diversify)
just trader-bootstrap             # re-prove shortlist → reports/bootstrap/
just trader-bootstrap --candidates-only
just trader-paper-handoff         # dry handoff
just trader-paper-handoff --plumbing-smoke
just trader-opportunity           # watch + handoff (no evolve)
just test
```

Hermes (when gateway up):

- `trader-desk-b-loop` ~30m → discovery cron (skip if marathon live)  
- `trader-opportunity-loop` ~60m → market wait  

**Discovery** burns CPU offline. **Opportunity** waits on RTH/setup. Do not conflate them.

Desk A (personal): `just positions`, `just pmcc-manage`, `just desk-brief`, Streamlit `just run`.

---

## 10. Key paths

| Path | Role |
|---|---|
| `configs/strategy_specs/*.json` | Frozen StrategySpec seeds |
| `configs/theses/*.yaml` | Executable thesis DNA (opportunity rules + structure defaults) |
| `configs/signal_catalog.yaml` | Named observables → `data.add_features` columns |
| `configs/bootstrap_strategies.json` | Bootstrap candidate config |
| `configs/discovery_grid.json` | Wave A coarse proof grid |
| `configs/discovery_grid_dense.json` | Archived dense axes (not default) |
| `configs/discovery_universe.json` | Symbol tiers: core / growth / experimental |
| `trader_platform/research/evaluate_proxy.py` | Dual-cost prove spine |
| `trader_platform/research/opportunity.py` | Opportunity emitter + structure plans |
| `trader_platform/research/signals.py` | Signal catalog + snapshots |
| `trader_platform/research/identity.py` | Coarse DNA keys / diversify |
| `trader_platform/research/bootstrap.py` | Bootstrap re-prove tooling |
| `trader_platform/research/discovery_loop.py` | Screen / prove / densify campaign |
| `trader_platform/data/living_registry.json` | Living seats |
| `trader_platform/risk_governor.py` | Order gates |
| `reports/bootstrap/` | Bootstrap snapshots + re-prove reports |
| `.cache/platform/spine/` | Discovery state, marathon pid, reports |

---

## 11. Alignment checklist (every change)

1. Which layer? Signal / Opportunity / Structure / Manage / Prove / Execute / Learn  
2. Which thesis (or catalog-only)?  
3. New parameter — inside thesis default, or cartesian thrash?  
4. New metric — named in §6 as gate or score?  
5. Still research/paper unless Ken-armed?  
6. Deduped identity (not clone flood)?  
7. Stand-aside still first-class?  

If you cannot answer (1)–(4), it is not aligned yet.

---

## 12. Near-term build backlog (ordered)

1. ~~Pin north star / consolidate build doc~~ (this file)  
2. ~~`configs/signal_catalog.yaml` from §4-style inventory~~  
3. ~~Rephrase 1–2 seeds as **thesis** files with opportunity rules~~ (`configs/theses/`)  
4. ~~Opportunity emitter (rule-based) → structure builder → existing prove~~ (`opportunity.py`; watcher shares path)  
5. ~~Pluggable scoreboard column: **premium/day** (experimental)~~ (score on `AxisSummary`; not a gate)  
6. ~~Dedupe living seats; paper shortlist from diversified thesis winners~~ (`identity.py` coarse DNA + promote diversify)  
7. Real paper places on setup (not only plumbing smoke)  
8. Live arm packet only when Ken is ready  

**Bootstrap:** `just trader-bootstrap` re-proves candidates and writes `reports/bootstrap/LATEST.json`. Pack = dual-cost survivors, not hardcoded favorites.

### Desk B primary path (do not fork)

| Primary (build + Hermes default) | Secondary (legacy / Desk A / scout) |
|---|---|
| `StrategySpec` → `evaluate_proxy` → living seats → opportunity watch → RiskGovernor → paper | `StrategyDNA` + `hypothesis_registry` + `premium_scout` / `evolve_tick` / `learn_tick` |

Agents invent and measure on the **primary** path first. Secondary DNA is optional only when the spine has no watchable seats — never a parallel “true” edge path.

---

## 13. Changelog

| Date | Change |
|---|---|
| 2026-07-19 | **Canonical build bible** created: consolidate north star, spine, dual desk, funnel, authority, commands, extensible scores (premium/day candidate). Other docs demoted to detail/research via [README.md](README.md). |
| 2026-07-19 | Phase 0: mark Desk B **StrategySpec spine as primary** vs StrategyDNA/scout secondary; discovery unit tests aligned to Wave A API. |
| 2026-07-19 | Engine phases 1–4: `signal_catalog`, thesis files, shared opportunity emitter (watcher wired), premium/day score, coarse DNA diversify, `just trader-bootstrap`. |

---

## 14. One paragraph (for agents)

Build a dual-desk monorepo whose Agentic path turns **named signals** into **opportunities** (or stand-aside), expresses them with **frozen structure+management DNA**, **proves** them under dual-cost chronological holdout, **executes** only through RiskGovernor/paper/Ken-arm, and **learns** by scoring **theses × regimes** on an **extensible metric catalog**. Cartesian knob volume is not progress. LLMs propose; programs measure and trade. **This file is the alignment surface.**

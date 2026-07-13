# Trader BUILD Lab Environment — Dual-Model Income Research

**Pinned:** 2026-07-10 (Ken)
**Repo:** `/Users/jarvis/dev/tsla-tsll-options-tracker`
**Profile:** Hermes `trader` (gateway-trader, cron-only; CoS stays Ken-facing)
**Hard rule:** paper / research only. No live, no agentic arm, no shadow auto-promote.

---

## Mission

Give Trader **enough BUILD time** and a **two-model research partnership** so it can search, simulate, and falsify **income-oriented option strategies** — not polish one familiar DNA.

| Model | Role | Default |
|---|---|---|
| **GPT 5.6 Sol** (`openai-codex`) | **Executor** — tools, research, evolve/sims, stress, durable writes | single writer |
| **Grok 4.5** (`xai-oauth`) | **Challenger** — read-only critique, quality bar, one NEXT seed | no evolve `--apply` |

They work **together on BUILD / discovery**, not on every RTH tick.

---

## Time split (operating contract)

| Window (America/Los_Angeles) | Mode | What happens |
|---|---|---|
| **Pre-market BUILD lab** Mon–Fri ~05:15 | Dual MoA | Research → multi-structure sims → falsify → Sol challenge |
| **RTH condition eval** Mon–Fri 06:30–12:30 hourly | Single agent | Wait / stand-aside / paper open-close path only — **no free evolve** |
| **Post-close BUILD lab** Mon–Fri ~14:15 | Dual MoA | Deeper discovery after cash close |
| **Daily self-evolution** Mon–Fri 16:45 | Dual MoA | Primary income-lab wake (coverage rotation) |
| **Evening BUILD lab** Mon–Fri ~20:00 | Dual MoA | Structure-gap / time-direction bias focus |
| **Saturday lab** ~10:00 | Dual MoA | Broader coverage + sim class gaps |
| **Sunday weekly critic** 17:00 | Dual MoA | Systems + coverage critique |

RTH remains **apply / wait / manage paper risk**.
BUILD remains **search / simulate / learn**.

---

## Income research goal

**Steady income** on the **$3k Agentic sleeve**, earned by:

1. **Defined-risk preferred** (PCS / CCS / IC and future calendars/diagonals/butterflies once simmed)
2. **Time advantage** — DTE buckets, entry weekday/session, hold duration, theta harvest vs gamma risk
3. **Direction / regime bias** — bull put / bear call / neutral condor / regime stand-aside as **features**, not slogans
4. **Falsify hard** — B3 regime + B4 cost + ml/dd quality bar vs current leader
5. **Paper path next** — live-clock open/close samples only when filters pass

The sole authoritative durable BUILD goal is `configs/build_lab_free_goal.txt`; Trader SOUL owns identity, north star, risk, and the self-sufficient orientation/judgment contract. Every authorized caller uses the same **zero-input** front door. Time/market session is derived internally as context metadata; it is not caller strategy judgment. Prior NEXT is context, never an order.

Each BUILD wake is **goal-driven rather than recipe-driven**. Trader may explore any liquid symbol, strategy DNA, combination, entry/exit/management rule, regime, time, volatility, stand-aside condition, simulator, negative control, or research tool. Prior NEXT is context, not an order. Evidence validity remains non-negotiable: a flaw that can invalidate the chosen claim must be repaired, tested, or used to narrow that claim. A blocked observed-data path blocks dependent promotion claims but does not freeze unrelated valid exploration. Proxy work is allowed for discovery when labeled; it cannot earn L1 without evidence appropriate to the claim.

See `docs/INCOME_STRATEGY_COVERAGE.md` for the structure matrix and gaps.

---

## How to run the lab

```bash
cd /Users/jarvis/dev/tsla-tsll-options-tracker

# Full dual-pass income discovery lab (Sol → Grok)
just trader-build-lab

# Normal interface for humans, Jarvis/coordinator, and cron: no arguments
just trader-build-lab

# Debug/recovery overrides only (not normal routing)
just trader-build-lab --goal "diagnose a named evidence failure"
just trader-build-lab --slot replay-label --structures put_credit_spread,call_credit_spread

# Coverage report only (no MoA)
just trader-income-coverage

# Classic stress MoA on named hyps (judgment peak)
just trader-wake-moa -- --hyps id1,id2,id3
```

**Residue**

- Dual lab: `reports/trader-wakes/moa/<stamp>/` + `*-moa-exec.md` / `*-moa-merge.md`
- Coverage: `reports/readiness/income-coverage-LATEST.md`
- Wakes front door: `just trader-wakes` → `reports/trader-wakes/LATEST.md`

---

## Environment surfaces

| Surface | Role |
|---|---|
| `configs/build_lab_free_goal.txt` | Sole authoritative durable BUILD program goal |
| `scripts/trader_build_lab_moa.sh` | Zero-input dual-model orchestrator; loads canonical goal and derives context |
| `scripts/trader_income_coverage.py` | Catalog + hyp + sim coverage scoreboard |
| `scripts/trader_wake_moa.sh` | Dual-pass stress / judgment MoA |
| `docs/INCOME_STRATEGY_COVERAGE.md` | Target matrix + gaps + build order |
| `docs/TRADER_LOOPS.md` | Loop map L1–L5 |
| skill `trader-self-evolution` | Wake protocol + anti-patterns |
| Hermes crons on `trader` | BUILD densify + RTH condition-only |

---

## What is NOT ready (honest)

| Capability | Status |
|---|---|
| PCS / CCS / IC multi-leg sim + evolve | **Built** (`pcs_sim`); IC supports side-specific delta/width/regime research, with current asymmetric grid cost-rejected |
| Collared covered call | **Built / rejected this cycle** — capital-honest sub-$30 scaffold; 1,152-row management grid had zero $75 window-DD passes |
| Single-leg short premium / wheel DNA | **Built** (StrategyConfig path) |
| Calendar spreads | **Partial** — explicit front/back IV + put-skew assumptions and chronological OOS scaffold; historical option-surface inputs still absent |
| Diagonal spreads | **Partial** — defined-debit scaffold + B3/B4 + exact-DNA OOS/density and a no-lookahead dividend/short-call assignment guard; observed surfaces and historical event-provider data missing |
| Butterfly / debit / ratio spreads | **Partial** — long call butterfly, symmetric/broken-wing credit iron butterflies, bull-call/bear-put debit verticals, and a 1x2 put ratio backspread have BS scaffolds; bull-call debit has the no-lookahead dividend/assignment guard, while short-put assignment remains unmodeled; ratio cost survival did not overcome its drawdown gate |
| Explicit time-bucket research dimensions | **Partial** (multi-hyp DTE/target/stop + entry-weekday/cost grid, lagged completed-bar close-shock filters, and chronological selection/holdout falsification built; session-time slices absent) |
| Direction bias as first-class score feature | **Partial** — shared-window scoreboard plus a no-lookahead shared-position PCS/CCS/IC router and standalone controls exist; router, prior adjacent-daily close-shock/momentum/pullback/vol-compression PCS, multi-horizon trend-pullback PCS, and bearish volatility-expansion CCS families were cost/density/DD-rejected |
| Cost-model realism | **Partial** — percentage/fixed-dollar sensitivity + normalized observed bid/ask archive/current snapshot + exact PCS/CCS/IC leg/time coverage reject gate; injectable actual expiry/strike-grid boundary and date-aware archived provider are fixture-tested and fail-closed. All-expiration append-safe capture is built, but historical density remains one market date; at least three dates are required before provider-backed historical entry simulation |
| Live-clock multi-session paper open/close | **Thin** (B6 partial) |
| Live / agentic open-close | **Blocked** until fund + arm |

BUILD labs should **prefer closing these gaps** over re-polishing TSLL PCS every night.

---

## Run completion and self-evolution contract

A BUILD wake has three judgment phases plus deterministic integration:

1. **Executor:** research/build/simulate and write evidence; partial phase only.
2. **Challenger:** critique claims, tests, capital honesty, evidence semantics, freedom restrictions, and NEXT; partial phase only.
3. **Finalizer:** reconcile critique, repair claim-invalidating defects, run focused checks and the full suite, regenerate derived surfaces, and write `learning-promotion.md`.
4. **Deterministic gate:** stage the reviewed run delta, reject sensitive paths/raw-secret assignments, commit on the run branch, push it, fast-forward it into `main`, push `main`, and verify clean local `HEAD == origin/main`.

The wrapper may emit `RUN COMPLETE` only after all four close. Executor/challenger markers are phase receipts—not completion. A red test, dirty tree, untracked residue, missing learning artifact, unpushed commit, or unmerged branch leaves the run `RUN INCOMPLETE` with its branch/evidence preserved for repair.

Recovery is explicit and resumable: run `scripts/trader_build_lab_moa.sh --stamp <stamp> --resume` to rerun challenge → finalizer → integration, or `--finalizer-only` when the critique is already green. Recovery must run from the original `trader/run-<stamp>` branch recorded in `meta.json`; old pre-contract runs cannot masquerade as recoverable completed runs.

Each finalizer promotes learning by type:

- dated outcome, current readiness, and project truth → repo report/doc;
- repeatable procedure, pitfall, or stronger test method → skill;
- compact stable stance/preference/routing fact → Trader profile memory;
- repeated manual work → script/check/automation;
- stale or contradictory guidance → rewrite/remove, not append-around.

Required learning artifact: `reports/trader-wakes/moa/<stamp>/learning-promotion.md` with `VERIFICATION`, `DURABLE`, `LESSON`, and exactly one `NEXT` (or `DIMINISHING_RETURNS`). Machine receipt: `.cache/platform/completion/<stamp>.json`.

Manual/direct-main infrastructure wakes do not fabricate MoA artifacts. They must commit a tracked report under `reports/trader-wakes/` with `VERIFICATION`, `DURABLE`, `LESSON`, and exactly one non-empty `NEXT`, then run `postflight --report <path> --base-head <pre-mutation-head> --run-head <integrated-commit> --receipt .cache/platform/completion/<name>.json`. This preserves the same clean/main/origin/ancestry proof without weakening wrapper `--stamp` checks. `preflight` reports `completion: false` and cannot write a completion receipt.

Manual preflight: `just trader-run-gate preflight`. Enforcement: `scripts/trader_run_completion_gate.py` and `scripts/trader_build_lab_moa.sh`.

---

## Hard stops (all lab jobs)

- No live orders / broker login / agentic arm
- No auto status → shadow/live
- No secrets / positions YAML in git
- Challenger does not `--apply` evolve
- Capital path only after quality bar (not vanity SHIP)

---

## History

### 2026-07-12 — Zero-input self-sufficient wake contract

Established `configs/build_lab_free_goal.txt` as the sole BUILD program goal. `just trader-build-lab` and the wrapper now require no caller judgment: they load the canonical goal, derive session context internally, and direct Trader to orient from SOUL/doctrine/readiness/prior learning before choosing the highest-information loop. Prior NEXT is context, not an order. Active profile cron compatibility names converge on one zero-argument runner; explicit goal/slot/structure and recovery flags remain diagnosis/recovery only.

### 2026-07-10 — Dual-model BUILD lab environment

Ken: enable Grok 4.5 + GPT 5.6 Sol to research/sim many income strategies with time + direction bias; more BUILD time; RTH waits for apply open/close. Added this doc, coverage map, `trader_build_lab_moa.sh`, coverage script, densified crons, skill/SOUL doctrine.

### 2026-07-10 — Diagonal scaffold

Added the paper-only long-call `diagonal_spread` BS simulator with explicit short/long expiry IV assumptions, defined debit/max-loss fields, synthetic smoke, evolve dispatch, and B3/B4 dispatch. The first SMCI baseline is after-cost positive but remains research-only because entries concentrate in 2022–23 and max-loss/window DD are worse than the PCS quality leader.

### 2026-07-10 — Diagonal exact-DNA OOS gate

Added `scripts/diagonal_oos_stress.py` with chronological 60/40 exact-DNA baseline/5%-slip reruns and entry-year density. SMCI `d1017453` produced zero entries in the 2024-12-17–2026-07-10 holdout, so its older after-cost result is rejected as a capital-path edge rather than retuned through assumed IV multipliers.

### 2026-07-11 — Long call butterfly scaffold

Added a paper-only same-expiry long-call butterfly simulator with catalog/evolve/B3/B4 wiring and synthetic smoke. The first six candidates all failed non-vacuous 5% leg-slip stress despite several positive mid-mark baselines, so the proxy class remains research-only and readiness stays L0.

### 2026-07-11 — Debit vertical scaffold

Added paper-only bull-call and bear-put debit-vertical BS simulators with catalog/evolve/B3/B4 wiring, defined debit risk, and synthetic tests/smoke. Eight registered candidates all failed non-vacuous 5% leg-slip stress; several also failed regime hold or full-history SHIP. The class remains research-only and readiness stays L0.

### 2026-07-11 — Cost-aware entry-weekday lab

Added entry-weekday gating to `pcs_sim` and weekday/slippage axes to `pcs_time_bias_grid.py`. The best weekday-only mid-mark row became vacuous under 5% slip; the only dense after-cost SHIP among the top time variants had worse window DD/dense-negative counts than `b195f5fe`, so readiness remains L0.

### 2026-07-11 — Multi-hyp time lab

Added multi-hyp PCS/CCS/IC comparison to the cost-aware time grid plus exact transient variant B3+B4. A BAC PCS Friday 7-DTE row survived 5% slip densely, but its $184.55 max loss and $87.29 window max DD missed the $76.32 / $74.85 leader quality bar. It remains unregistered and readiness stays L0.

### 2026-07-11 — Credit iron-butterfly scaffold

Added a paper-only same-expiry credit iron-butterfly simulator with catalog/evolve/B3/B4 wiring and defined max loss, tests, and synthetic smoke. A focused population produced no iron-butterfly SHIP at 2y. The top SMCI and TSLL proxy candidates regime soft-held over 5y but collapsed non-vacuously at 5% leg slip, so the class remains research-only and readiness stays L0.

### 2026-07-11 — Fixed-dollar per-leg cost sensitivity

Added a uniform fixed-dollar half-spread per option leg to PCS/CCS/IC and credit iron-butterfly entry/exit marks, with a standalone comparison script and tests. Every representative structure was negative at a $0.01 half-spread per leg, including the relative PCS leader. This closes the prior fixed-cost tooling seed but does not substitute for observed quotes or create an L1 edge.

### 2026-07-11 — Fixed-dollar proxy coverage completion

Extended the same adverse fixed-dollar per-leg entry/exit model to calendar, diagonal, long butterfly, and debit-vertical proxies. Exact stress left TSLL calendar `fcc76896` positive at $0.01 per leg but increased drawdown above the leader bar; all other survivors had worse max-loss/DD. No L1 edge emerged, and observed option quotes remain the realism boundary.

### 2026-07-11 — Exact observed quote coverage gate

Added exact non-future symbol/expiry/type/strike/time joining for registered PCS/CCS/IC simulated entry and exit legs. The first leader run required 228 leg observations and matched 0 from the only 70-row snapshot, correctly rejecting calibration. This also exposed synthetic non-listed expiration dates as the next simulator realism gap; readiness remains L0.

### 2026-07-11 — Listed Friday expiry abstraction

PCS/CCS/IC entries now price and record the first Friday on or after target DTE, with the actual calendar DTE used in Black-Scholes marks. Tests cover Friday preservation and weekday roll-forward. Restress increased `b195f5fe` window max drawdown from the prior $74.85 bar to $88.39 and left 5% slip non-vacuousness absent (n13/−$13.18), so the former relative leader is rejected from the capital path; no L1 DNA remains. Actual symbol/date available-expiry and strike grids still require observed archives.

### 2026-07-11 — Actual contract-grid injection boundary

PCS/CCS/IC sims now accept a symbol/date contract-grid provider and can require it. Required mode selects only supplied expirations and right-specific strikes and fails closed on absent coverage or missing wings; tests cover both selection and rejection. The boundary is not historical data: discovery still uses labeled synthetic mode until forward archives are dense enough. New SMCI/NFLX calendar and TSLA butterfly SHIPs all failed B4, so readiness remains L0.

### 2026-07-11 — Append-safe all-expiration capture

Replaced the first-expiration overwrite capture boundary with all-expiration current-chain capture and atomic append/deduplication. Archive summaries expose distinct New York market dates and reject provider-backed historical use below three. The first TSLL run captured 600 quotes across 12 expirations but only one market date, so the lab correctly skipped evolve and remains L0 with no living quality leader.

### 2026-07-11 — Broken-wing credit iron butterfly

Added an asymmetric bullish credit iron-butterfly scaffold with enforced wider put wing, defined max loss, evolve/B3/B4/fixed-cost dispatch, and tests. SMCI/XOM baseline SHIPs were all rejected by non-vacuous 5% slip, $0.01-per-leg cost, and/or the $75 drawdown gate. No L1 leader emerged.

### 2026-07-11 — Put ratio backspread scaffold

Added a paper-only bearish 1x2 put ratio backspread with closed-form valley max loss, signed expiry payoff, structure-pure evolve, B3/B4/fixed-cost dispatch, and behavioral tests. SMCI survived both 5% percentage slip and $0.01 per-leg cost but failed regime, max-loss, and drawdown gates; BAC regime-held and survived $0.01 per leg but was negative at 5% slip and exceeded the $75 drawdown gate. No L1 leader emerged.

### 2026-07-11 — Proxy simulator event-loop correction

Independent post-run test review found that butterfly, iron-butterfly/BWIB, calendar, diagonal, debit-vertical, and put-ratio proxy loops could close and immediately re-enter on the same daily bar. They now follow the canonical one-position per-bar sequence and defer a new entry until a later bar. Put-ratio tests also verify exact three-leg half-spread cost on both entry and exit plus the no-same-bar-reentry boundary. Pre-correction metrics for affected proxies are historical only and must be restressed before tuning or promotion.

### 2026-07-11 — No-lookahead defined-risk regime router

Added a current-row-only shared-position router across PCS/CCS/IC with no close-bar re-entry, population-purity checks, exact standalone controls, two proxy cost axes, and independent ledger recomputation. The first eight-symbol default-DNA run produced no absolute-gate pass: 5% slip was sparse/vacuous and all dense baselines exceeded $75 window drawdown. The router is useful research tooling but rejected as a capital family this cycle; readiness remains L0.

### 2026-07-12 — Asymmetric condor boundary + falsification

Added transient put/call-specific delta and width controls plus a regime gate for capped-jade-shaped iron-condor research. Fixed the IC close cap to the widest non-overlapping wing rather than the sum of both wings, then ran a complete 96-row grid over BAC/TSLL/SMCI/PLTR/SOFI/F. Twenty-nine rows were positive baseline SHIPs, but none was positive under either 5% leg slip or $0.01-per-leg half-spread; 288/288 ledgers were exact and same-bar re-entry was zero. Family rejected this cycle; no leader or readiness advance.

### 2026-07-12 — Lagged close-shock PCS falsification

Added fail-closed current-row entry bounds and an explicit completed-bar signal lag to the defined-risk credit simulator. A 64-DNA, eight-symbol downside-close-shock grid found one full-sample SMCI proxy pass after both cost axes, but chronological 60/40 train selection produced PLTR/TSLL candidates and both failed untouched holdout gates (PLTR drawdown; TSLL PnL and drawdown). Family rejected this cycle; no hypothesis registration, leader, or readiness advance.

### 2026-07-12 — Bearish volatility-expansion CCS falsification

Tested one predeclared 14-DTE call-credit-spread DNA after a prior completed-bar `hv_20/hv_60 >= 1.20` state and non-positive return across BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL. Expanding 40/60/80% train gates and following holdouts used both proxy cost axes plus unconditional and compression CCS controls. Zero of 24 train folds and zero complete folds passed; minimum strategy-axis samples were 0–6 and worst per-symbol fold drawdown was $76.20–$347.91 despite one-lot max loss remaining $94.71–$237.36. All 286 persisted strategy/control/window summaries had exact ledgers, zero signal violations, and zero same-bar re-entry. Family rejected without tuning or registration; synthetic option marks/costs cannot earn L1.

### 2026-07-12 — Multi-horizon trend-pullback PCS falsification

Added fail-closed prior-bar `ret_5d`, `ret_14d`, and EMA-stack entry bounds and tested one predeclared 21-DTE PCS across BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL. Four of 24 expanding-origin train gates passed, but zero complete folds survived untouched holdouts under both proxy cost axes; all 286 persisted strategy/control/window summaries had exact ledgers with zero signal or same-bar violations. The finalizer added a local passing-holdout/failing-train negative control. This proxy family is closed without threshold tuning or registration and cannot earn L1.

## Cumulative improvement contract

The zero-input wrapper generates `orientation.json` from prior integrated `compounding.json` records before the executor chooses a loop. This is decision context, not a strategy recipe or allowlist: it carries closed families, prior novelty keys, recent loop signatures/outcomes, and a redirect signal. A closed family may be reopened only when Trader names a genuinely new evidence class or repaired capability. A prior NEXT remains advisory.

Each finalizer writes one structured `compounding.json`:

```json
{
  "schema_version": 1,
  "stamp": "YYYY-MM-DDTHHMM",
  "loop_signature": "stable family/axis/evidence-class identifier",
  "outcome": "CANDIDATE|FALSIFIED|CAPABILITY|REPAIRED|DIMINISHING_RETURNS",
  "useful_deltas": [
    {
      "kind": "candidate|falsification|capability|repair|evidence|stop_rule",
      "summary": "decision-relevant change",
      "novelty_key": "stable unique capability/evidence key",
      "artifacts": ["repo/relative/path"]
    }
  ],
  "critic_findings": [
    {
      "finding": "material finding",
      "status": "repaired|rejected",
      "rationale": "evidence-backed disposition",
      "repair_artifacts": ["required when repaired"],
      "test_artifacts": ["required when repaired"]
    }
  ],
  "closed_families": ["stable-family-id"],
  "data_dependencies": ["what genuinely needs new market data"],
  "next": "exactly one seed or DIMINISHING_RETURNS"
}
```

The validator requires every non-diminishing wake to cite at least one changed artifact and a new novelty key. Capability/repair claims require changed machinery and tests. Repaired critic findings require repair and test artifacts; rejected findings require rationale. A no-delta wake must say `DIMINISHING_RETURNS`. Two repeated loop signatures or the prior diminishing-return outcome set `redirect_required` for the next orientation; this redirects an unchanged loop but never restricts symbol or strategy freedom.

Finalizer role readiness is not a phrase in model output. Before the role starts, the wrapper snapshots hashes of `learning-promotion.md` and `compounding.json`; after a zero exit it validates that both materially changed and that the structured handoff passes the delta/finding rules. Session logs and prompt echoes are ignored. The deterministic prepare gate validates the handoff again.

Zero-input interruption recovery is fail-closed. A launch from a matching `trader/run-<stamp>` branch automatically resumes that stamp. Integration is idempotent across an already-created run commit and an already-fast-forwarded local main; divergence, dirty committed recovery state, mismatched metadata, or non-descendant history remains a blocker. No cleanup, reset, force push, or strategy choice is automated.

### 2026-07-12 — End-to-end completion and self-evolution gate

A run audit found useful research and honest falsification but also a large uncommitted working tree, duplicate monitor semantics, and completion markers that did not prove durable integration. Trader now uses an executor → challenger → finalizer workflow followed by a deterministic branch/commit/push/fast-forward-main/remote-clean gate. Each run must promote lessons to the smallest durable surface and write `learning-promotion.md`; partial phases, red tests, dirty residue, unpushed commits, or unmerged branches are explicitly `RUN INCOMPLETE`. The full test baseline was restored by making live-PMCC integration assertions validate current selected package/date semantics instead of stale hard-coded state.

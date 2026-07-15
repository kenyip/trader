# Trader Restart Charter — anti-drift alignment

**Pinned:** 2026-07-14  
**Audience:** Ken + Jarvis (control plane) + Trader (executor of strategy work)  
**Status:** Durable alignment surface. Re-read before restarting BUILD density or changing doctrine.  
**Does not replace:** `TRADER_PLATFORM_GOAL.md`, `configs/build_lab_free_goal.txt`, trader `SOUL.md`, `GO_LIVE_READINESS.md`.  
**This file answers:** what we are optimizing for, standing directives, current gap, and whether to rebuild vs reframe.

---

## 1. North star (stable)

Build a **self-learning research → paper → shadow → (Ken-armed) live income engine** on the isolated **$3,000 Agentic sleeve**, owned by Hermes profile `trader`.

Success is **not** wake volume, dual-lab count, hyp count, or green tests alone.

Success is:

1. At least one durable, paper-testable edge **after costs** at **1-lot** size on **$3k**.
2. Capital protected harder than opportunity chased.
3. Stand-aside treated as a valid win.
4. Live only after evidence + **explicit Ken arm**.

Promotion path (non-negotiable):

```text
research → paper → shadow → agentic_live
```

---

## 2. Objectives (stable)

| # | Objective |
|---|---|
| O1 | Discover edges freely across the research universe and strategy DNA. |
| O2 | Validate with claim-scoped evidence (no future leak, honest costs, train → untouched holdout). |
| O3 | Keep only capital-honest candidates on the path to paper (`fit_3k`, defined-risk preferred, max-loss budget). |
| O4 | Paper open / manage / close under live-clock conditions when filters pass. |
| O5 | Shadow, then draft a live arm packet only when A+B (and day-of C) are green. |
| O6 | Never self-arm; never trade Ken’s main book. |

Confidence ladder (see `BUILD_PROGRESS_AND_CONFIDENCE.md`):

| Level | Meaning | Live money? |
|---|---|---|
| L0 BUILD | Sims / research only | No |
| L1 sim edge | Non-vacuous after-cost + B3 density + competitive ml/dd | No |
| L2 paper B6 | Multi-session open/manage/close | No |
| L3 shadow B7 | Propose → risk → log | No |
| L4 first real $ | Funded + Ken arm + 1-lot | Yes, gated |

---

## 3. Directives (standing pins)

| Pin | Rule |
|---|---|
| **Freedom** | Any liquid symbol in `trader_platform/research/universe.yaml`; any strategy DNA. Not wheel-only, not TSLA/TSLL tunnel. |
| **Rank by evidence** | Capital fit + regime + cost/slip + multi-name multi-structure. Plumbing readiness is **not** a rank key. |
| **Better trades** | Capital seats require independent quality, not diversify-for-fear. |
| **BUILD vs RTH** | Off-hours: discovery / sim / falsify / repair. RTH: wait / filters → paper or stand-aside. No free evolve on RTH. |
| **Quality ≠ capital_fit** | `fit_3k` can still be research-only if ml/dd or B3/B4 fail the quality bar. |
| **Claim-scoped validity** | A blocked observed-option path blocks only observed / L1 claims. BS-proxy historical sims may continue when labeled. Proxy cannot earn L1. |
| **Strategy-run contract** | Each BUILD wake closes exactly one of: `STRATEGY_ADVANCED`, `FAMILY_CLOSED`, `BLOCKER_REMOVED_AND_RETESTED`, `EVIDENCE_WAIT`. Tooling alone ≠ strategy progress. |
| **Funnel** | `F0_MECHANISM` → `F1_TRAIN` → `F2_UNTOUCHED_HOLDOUT` → `F3_ROBUST_PAPER_PLAN` → `F4_OBSERVED_PAPER`. |
| **Burst control** | After **2** consecutive completed wakes without `STRATEGY_ADVANCED` → pivot mechanism / evidence class. After **3** → **stop burst** and reassess search design / data. |
| **Ownership** | Trader owns implementation and hypothesis choice. Jarvis = guidance, evidence audit, control plane. Ken = fund / arm / live. |
| **Hard stops** | No live orders, broker login, agentic arm, shadow auto-promote, spend, secrets / private positions in git. |
| **Zero-input BUILD** | Normal entry is `just trader-build-lab` with sole goal from `configs/build_lab_free_goal.txt`. Callers do not pick strategy axes. Prior NEXT is context, not an order. |

Ken research prior (**not a cage**): explore small, repeatable profits from time decay and price swings while preserving a positive long-term directional bias when regime supports it.

---

## 4. Operating surfaces (where truth lives)

| Surface | Path / command |
|---|---|
| Goal pin | `docs/TRADER_PLATFORM_GOAL.md` |
| BUILD program goal | `configs/build_lab_free_goal.txt` |
| This charter | `docs/TRADER_RESTART_CHARTER.md` |
| Identity | `~/.hermes/profiles/trader/SOUL.md` |
| Repo | `~/dev/tsla-tsll-options-tracker` |
| Wakes | `just trader-wakes` / `reports/trader-wakes/LATEST.md` |
| Readiness | `reports/readiness/LATEST.md` |
| Strategy-convergence | `scripts/trader_build_progress.py` / `reports/readiness/build-progress-LATEST.md` |
| Income coverage | `just trader-income-coverage` / `reports/readiness/income-coverage-LATEST.md` |
| BUILD entry | `just trader-build-lab` / `scripts/trader_build_lab_moa.sh` |
| Dual roles | Sol executor → Grok challenger → Sol finalizer |
| RTH | trader cron `trader-rth-eval` (`30 6-12 * * 1-5`) |
| Gateway | `ai.hermes.gateway-trader` (cron-only; no Telegram) |

Jarvis monitor preference: **milestone-only** after completed BUILD or real blocker — not raw activity feeds.

---

## 5. Snapshot vs goal (as of 2026-07-14)

### Where we are

- **Phase:** BUILD / **L0**
- **Living quality leader:** **none**
- **Capital path:** **empty**
- **Strategy advances (`BETTER` / `STRATEGY_ADVANCED`):** **0** in integrated dual history
- **Recent pattern:** many **INFORMATIVE_BUT_NOT_CLOSER** falsifications and capability repairs; funnel stuck at **F0**
- **Burst state:** `strategy_burst_stop_required` / `DIMINISHING_RETURNS` for current search burst
- **RTH:** repeated stand-aside (e.g. 14 eligible / 0 intents); preferred historical PCS reference `b195f5fe` is **not** a living leader; bear regime blocks OPEN_PCS
- **Paper open risk:** 0 (smoke stubs only)
- **Observed option archive:** 3/3 market-date plumbing floor on TSLL — **not** historical edge / L1
- **Agentic RH:** unfunded / options-level blocked; `agentic_enabled=false`
- **BUILD densify crons:** mostly **paused**; RTH eval remains active

### Platform assets worth keeping

- Dual-model BUILD + deterministic completion / clean `main` integration
- Strategy-run outcome contract + strategy-convergence scoreboard (separates ops complete from strategy closer)
- Multi-structure catalog (~21) + many simulators + absolute risk/cost gates
- Chronological train → untouched holdout / pre-registration machinery
- Multi-name universe + freedom pins + ranking / better-trades doctrine
- RTH wait / stand-aside discipline
- Claim-integrity culture (bad evidence can be superseded; e.g. 0612 VRP story repaired by 0859)
- Paper / risk governor stubs and go-live checklist structure

### What is still missing for the goal

1. A living candidate that clears non-vacuous after-cost + density + competitive ml/dd (L1)
2. A robust paper plan (F3) and observed paper sample (F4 / B6)
3. A written **search-design reassessment** after the no-advance burst
4. Funded Agentic sleeve + options level (external Ken/account gates)
5. Decision: campaign-driven BUILD only vs resume densified BUILD slots **after** reassessment

### Closed / rejected family themes (examples; not exhaustive)

Honest closes under dual-cost / chronological / absolute gates include:

- PCS mild-pullback, bullish-momentum, close-shock, vol-compression (daily-bar proxy)
- CCS vol-expansion
- Multi-horizon trend-pullback PCS
- Collar management surface / class
- Asymmetric condor class (proxy)
- Session-time 30m PCS/CCS/IC seed
- Free defined-risk dry pop + chronological pre-reg pop (train SHIPs died on holdout / absolute gates)
- Gap-recovery 21-DTE PCS family
- SPY turn-of-month first-session underlying pre-screen (failed before option stage)
- SPY VRP VIX/RV family (closed; control-density / integrity after repair)
- Narrow AAPL no-auth ex-date inventory route (partial L0 data close)

Interpretation: the lab is **good at falsifying**. It has **not** yet produced a holdout-surviving capital-honest edge under the current absolute seat bar.

---

## 6. Decision: start clean vs tweak current Trader

### Recommendation (2026-07-14)

**Do not rebuild the platform from zero.**  
**Do restart the search epoch / design on the current platform.**

Call this a **search restart**, not a full product rewrite.

| Option | Verdict |
|---|---|
| Throw away repo / profile / dual lab / gates | **No** — loses the hard-won falsification and integrity machinery that protects capital |
| Keep running densified BUILD without reassessment | **No** — violates burst-stop; more volume will mostly mint informative non-advances |
| Keep platform + directives; reframe search + intermediate funnel economics | **Yes** — best path to a viable strategy |
| Soft “clean slate” of strategy state only | **Optional** — new search epoch label, closed-family inventory, empty capital path (already empty), new charter seed |

### Why many runs did not get close (root diagnosis)

These are **process / search-design** findings, not “Trader is broken” or “gates should be deleted.”

1. **Zero funnel advances past F0.** Integrated dual history shows **0** `STRATEGY_ADVANCED`. We did not get “almost paper-ready”; we never cleared a capital-honest train→holdout survivor into a living candidate.
2. **Absolute seat bar applied early.** Gates such as dual-cost positivity + window DD ≤ ~$75 + max loss ≤ ~$300 + dense-negative limits are appropriate for a **$3k capital seat**, but they made **discovery** look like total failure even when mechanisms were only F0 probes.
3. **Capability work crowded strategy advancement.** Several wakes shipped dividend boundaries, archive densify, session-time plumbing, or pre-reg adapters. Useful, but under the current contract they count as **search information** unless the unlocked experiment advances or closes a family in-wake. The scoreboard correctly refuses to call that “closer to a trade.”
4. **Holdout killed free evolve.** Example pattern: train SHIPs exist → complete chronological dual-cost / absolute gates **0/N**. That means either no durable edge under proxy costs, or DNA/search space still wrong — not that the harness is silent.
5. **Historical “SHIP” references ≠ living leaders.** e.g. `b195f5fe` failed listed-expiry / quality restress and is historical context only. Old scoreboard SHIPs should not be treated as near-live.
6. **Burst continued after informative non-advances.** Burst-stop exists because this is expected: dense duals without mechanism redesign become expensive thrash.

### What to keep (bring forward if “starting clean”)

- Goal + freedom + better-trades + claim-scoped evidence doctrine
- Dual MoA + completion gate + clean main integration
- Strategy-convergence scoreboard (ops complete ≠ strategy closer)
- Structure catalog / sims that already exist
- Absolute **capital-seat** bar for L1 / paper eligibility
- RTH stand-aside discipline
- Closed-family quarantine list (do not re-open without new evidence class)

### What to change (search restart)

1. **Mandatory written search-design reassessment** before the next BUILD density campaign. Must name:
   - open non-quarantined economic mechanisms worth testing
   - mechanisms already closed and why
   - data classes available (historical underlying / BS proxy vs observed options)
   - one primary mechanism class for the next epoch
   - explicit predeclared falsifier
   - what would count as the first `STRATEGY_ADVANCED` (usually F0→F1 or F1→F2)
2. **Separate discovery bar from capital-seat bar.**
   - **Discovery (F0→F1/F2):** chronological integrity, labeled costs, non-vacuous n, no leakage; may use looser DD/pnl thresholds **as research signals only**.
   - **Capital seat (L1 / paper path):** keep strict absolute gates (ml/dd/cost non-vacuity/density).
   - Never promote discovery-only survivors to capital path without clearing the seat bar.
3. **Strategy-first wake charter.** Every BUILD wake must name mechanism + funnel stage + falsifier **before** tools. Capability-only final outcomes fail closed unless same-wake retest advances or closes.
4. **New search epoch label** in readiness / progress (e.g. `search_epoch: 2026-07-14-reassess`) so old no-advance streak is historical context, not a psychological mandate to keep thrashing the same burst.
5. **Resume densified BUILD only after reassessment.** Until then: RTH condition-eval remains fine; BUILD is campaign / explicit only.
6. **Jarvis role stays external.** Guidance + evidence audit + milestone monitor. Do not dictate strategy DNA as success criteria.

### When a true platform rewrite *would* be justified

Only if one of these becomes true:

- Completion / integrity machinery systematically lies and cannot be repaired
- Freedom is structurally impossible (hard-coded tunnels in code + prompts that cannot be fixed)
- Evidence contract is abandoned (proxy sold as L1, future leak tolerated)
- Ownership model collapses (Jarvis implements strategy; Trader becomes a script runner)

None of those are the current diagnosis. The current diagnosis is: **honest lab, empty edge seat, search design exhausted under the last burst.**

---

## 7. Next alignment checklist (use before any new BUILD campaign)

- [ ] Re-read this charter + `configs/build_lab_free_goal.txt` + latest readiness LATEST
- [ ] Confirm phase is still BUILD/L0 unless living candidate evidence says otherwise
- [ ] Confirm burst-stop honored (no densified dual spam without reassessment)
- [ ] Written search-design reassessment exists and names a **new** mechanism/evidence class
- [ ] First wake of the new epoch has a strategy decision charter (mechanism, funnel, falsifier, decision)
- [ ] Discovery bar vs capital-seat bar distinguished in the experiment writeup
- [ ] Closed families not reopened without new evidence class
- [ ] RTH remains stand-aside-capable; no forced paper
- [ ] No shadow / arm / live / fund automation from wakes
- [ ] After the wake: strategy-convergence says BETTER / INFORMATIVE / THRASH honestly

---

## 8. One-line control-plane answer

**We keep the Trader platform; we restart the search epoch.**  
Many runs were real work and real falsification, but they did **not** get close to a viable capital strategy. Closeness requires the first `STRATEGY_ADVANCED` into a living candidate under claim-appropriate evidence — not more duals on exhausted families.

---

## History

### 2026-07-14 — Search restart executed

Search-design reassessment completed in `docs/SEARCH_DESIGN_REASSESSMENT_2026-07-14.md`. Active epoch `2026-07-14-reassess` in `configs/search_epoch.json`. Discovery bar vs capital-seat bar codified in goal/BUILD lab/orientation. Pivot/burst-stop streak is epoch-scoped so prior no-advance history no longer freezes new strategy work.
### 2026-07-15 — Continuous densify post-pause path prepared

After three epoch no-advances (`2203`, `2302`, `2337`), continuous densify pauses for reevaluation. Playbook: `docs/CONTINUOUS_DENSIFY_POST_PAUSE.md`. Reassessment: `docs/SEARCH_DESIGN_REASSESSMENT_2026-07-15.md`. Next epoch package: `configs/search_epoch_next.json` (`2026-07-15-viable-path`). Re-arm only via `~/.hermes/scripts/trader_rearm_densify_after_reassess.py` after clean integrate — does not invent strategy DNA.

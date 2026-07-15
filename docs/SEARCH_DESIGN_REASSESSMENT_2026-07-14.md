# Search-design reassessment — 2026-07-14

**Status:** complete (unblocks a new search epoch; does **not** invent a strategy DNA)  
**Epoch:** `2026-07-14-reassess` (`configs/search_epoch.json`)  
**Charter:** `docs/TRADER_RESTART_CHARTER.md`  
**Owner of mechanism choice:** Trader (not Jarvis, not cron)

---

## 1. Why this reassessment exists

Integrated dual history showed:

- **0** `STRATEGY_ADVANCED`
- long **INFORMATIVE_BUT_NOT_CLOSER** streak
- `strategy_burst_stop_required` / last BUILD NEXT = `DIMINISHING_RETURNS`
- living leader **none**; capital path **empty**

The platform is healthy enough to keep. The **last search burst is exhausted**. Continuing densified duals without a design change would buy volume, not closeness.

---

## 2. What is closed (do not reopen unchanged)

Orientation still carries the full closed-family set. Themes already falsified under dual-cost / chronological / absolute-style probes include (non-exhaustive):

| Theme | Lesson |
|---|---|
| Daily-bar PCS signal families (mild-pullback, momentum, close-shock, vol-compression, multi-horizon pullback) | Train/full-sample glimmers die on untouched holdout or DD gates |
| CCS vol-expansion daily-bar | Same class of cost/DD failure |
| Collar class / management grid | Window DD dominates; not a seat |
| Asymmetric condor proxy class | Cost axes not capital-honest |
| Session-time 30m PCS/CCS/IC seed | Capability useful; edge not holdout-surviving |
| Free defined-risk dry pop + chronological pre-reg pop36 | Many train SHIPs → 0 complete absolute holdouts |
| Gap-recovery 21-DTE PCS | Family closed |
| SPY turn-of-month first-session underlying pre-screen | Failed before option stage |
| SPY VRP VIX/RV family | Closed after claim-integrity repair; control density insufficient |
| Narrow AAPL no-auth ex-date inventory | Data route partial L0 only |

Reopen only with a **named new evidence class** (new data geometry, new control design, new economic mechanism — not retune of the same signature).

---

## 3. What remains open (process guidance, not an allowlist)

Trader still chooses freely. These are **open research classes**, not orders:

1. **Time-decay income + regime stand-aside** outside already-closed daily signal families — management/exit or DTE/hold edges where entry is deliberately simple and falsifiable.
2. **Underlying pre-screen → conditional defined-risk** with proper control density and non-overlapping episodes (do not revive closed TOM/VRP signatures without a new design).
3. **Structure classes not yet holdout-closed as a capital family** (e.g. calendar/diagonal/debit with honest data bounds) — discovery bar first, seat bar second.
4. **Portfolio / stand-aside policy as edge** — when not-to-trade is the main EV driver, test it as a mechanism with placebos, not as after-the-fact narration.
5. **Simulator/capability unlock** only when the same wake retests a dependent strategy decision to advance or close.

Available routes (claim-scoped):

- Historical underlying + BS-proxy option marks: **executable** for discovery/falsify; **cannot earn L1**
- Observed historical option replay: **not** broad-edge ready; 3-date archive is plumbing only
- RTH: condition-eval / paper when filters fire; stand-aside success

---

## 4. Discovery bar vs capital-seat bar (hard process fix)

Previous burst often applied **capital-seat absolute gates** as the only pass/fail for early funnel work. That is honest for L1 seats but **starves F0→F1 learning**.

| Bar | Use for | May pass with | Cannot grant |
|---|---|---|---|
| **Discovery bar** | F0→F1, F1→F2 signals | Labeled proxy costs, looser risk thresholds, non-vacuous n, chronology, predeclared falsifier | L1, capital path, paper seat |
| **Capital-seat bar** | L1 / paper eligibility | Dual-cost non-vacuous edge, B3 density, max loss ≤$300, window DD ≤$75, dense-neg ≤5, defined-risk preferred | Live/shadow without Ken |

**STRATEGY_ADVANCED at F0→F1** may use the discovery bar when claim scope is labeled L0 discovery.  
**L1 / capital path / paper path** still requires the capital-seat bar and cannot be proxy-only.

Machine config: `configs/search_epoch.json` → `discovery_bar` / `capital_seat_bar`.

---

## 5. Epoch operating rules

1. Every BUILD wake opens with a strategy decision charter (mechanism, scope, funnel stage, falsifier, decision).
2. Close exactly one strategy outcome; capability-only final outcomes fail closed unless same-wake retest advances or closes.
3. Closed families stay closed without a new evidence class.
4. Pivot after 2 no-advance wakes **inside this epoch**; burst-stop after 3 **inside this epoch**.
5. Prior epoch `DIMINISHING_RETURNS` does not freeze the new epoch after this reassessment.
6. RTH remains wait/filters → paper or stand-aside; no free evolve on RTH.
7. Jarvis monitors milestones and evidence; does not dictate DNA.

Epoch success (first milestone): **one `STRATEGY_ADVANCED`** into a living candidate (typically F0→F1).

---

## 6. Blockers cleared by this packet

| Blocker | Action |
|---|---|
| Burst-stop forever on pre-epoch streak | Streak/pivot/stop now scoped to `started_stamp` of active search epoch |
| Seat bar = only discovery metric | Discovery vs capital-seat bars codified |
| No written reassessment | This document |
| Dense BUILD while exhausted | Epoch restarts search; densify may resume modestly after code lands |
| Archive density as global freeze | Already invalid; reiterated |

Still external (not cleared here): Agentic funding, options level, Ken arm.

---

## 7. Immediate next action for Trader

Run zero-input:

```bash
cd /Users/jarvis/dev/tsla-tsll-options-tracker
just trader-build-lab
```

Orient on this reassessment + `configs/search_epoch.json` + `orientation.json`, then choose **one** open mechanism class **outside** closed families. Prefer a loop that can honestly produce F0→F1 under the discovery bar, or a decisive family close with a new signature.

Do not reopen SPY VRP, TOM, gap-recovery, or closed daily PCS signal families without a new evidence class.

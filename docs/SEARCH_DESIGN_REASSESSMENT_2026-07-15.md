# Search-design reassessment — 2026-07-15

**Status:** ready (activates next epoch package; does **not** invent Trader DNA)  
**Supersedes active densify for epoch:** `2026-07-14-reassess` after three consecutive no-advances  
**Next epoch id:** `2026-07-15-viable-path` (`configs/search_epoch_next.json`)  
**Charter:** `docs/TRADER_RESTART_CHARTER.md`  
**Post-pause playbook:** `docs/CONTINUOUS_DENSIFY_POST_PAUSE.md`  
**Owner of mechanism choice:** Trader

---

## 1. Why this reassessment exists

Active epoch `2026-07-14-reassess` produced **three** integrated/accepted closes and **0** `STRATEGY_ADVANCED`:

| Stamp | Outcome | Closed family / axis | Dominant failure (train / F0) |
|---|---|---|---|
| `2026-07-14T2203` | `FAMILY_CLOSED` | `pcs-monday-45dte-exit21-vs-exit5-train-proxy` | Dual-cost train expectancy fail; calendar-stop contrast sparse |
| `2026-07-14T2302` | `FAMILY_CLOSED` | `MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT` | Absolute low-HV drift positive; **paired excess negative** vs high-HV control |
| `2026-07-14T2337` | `FAMILY_CLOSED` | `MONTHLY_CROSS_SECTION_12_1_MOMENTUM_FORWARD_DRIFT` | Point excess positive; **bootstrap LB90 uncertainty gate failed** |

Living candidates: **none**. Capital path: **empty**. Funnel: still **F0**.

Process was healthy (honest closes, holdouts unspent, quarantine seeds). Strategy closeness was not. Burst-stop is correct: **more volume in the same design is the wrong next step**.

---

## 2. What the three closes teach (design, not DNA)

1. **PCS management micro-variants** on multi-name Monday 45-DTE DNA can fail dual-cost train hard; sparse stop-contrast must not be over-interpreted as pure theta timing proof.
2. **Cross-section underlying selectors** (low-HV and 12−1 momentum on a fixed present-day panel) can show positive absolute drift while **incremental edge vs control / uncertainty bounds** fail — absolute drift alone is not a discovery advance.
3. **Harness capability** (paired controls, bootstrap LB, train-only gates) is working; the miss is economic edge under predeclared falsifiers, not missing tests.
4. **Ken priors remain valid research preferences**, not results: TSLA/TSLL swing + long-term bullish bias + small repeatable theta/swing profits are allowed hypothesis classes. They were not proven by this epoch.

---

## 3. Quarantine (do not reopen unchanged)

Carry full orientation closed-family history. **Additionally mark this epoch’s exact closes:**

- `pcs-monday-45dte-exit21-vs-exit5-train-proxy` and nearby stop-nudge / symbol-cherry-pick of the same DNA
- `MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT` and nearby low-HV rank retunes / high-HV inversion on the same panel design
- `MONTHLY_CROSS_SECTION_12_1_MOMENTUM_FORWARD_DRIFT` and nearby 252/21/top-three retunes of the same momentum panel design

Also still closed from prior reassessment: daily-bar PCS signal families, CCS vol-expansion daily, collar grids, asymmetric condor proxy class, session-time 30m short-premium seeds, gap-recovery 21-DTE PCS, SPY TOM first-session pre-screen, SPY VRP VIX/RV family (unless a **named new evidence class** is declared).

Hard bans until a new evidence class is named:
- No holdout peek on failed F0 reserved blueprints (incl. 2337’s 27)
- No option pricing to “rescue” a failed underlying selector
- No fourth wake inside `2026-07-14-reassess`

---

## 4. Open routes for the next epoch (guidance, not orders)

Trader chooses freely. Prefer **independent** economic mechanisms that can clear **discovery bar** first, then capital-seat bar later.

### A. Defined-risk income with simple entry + explicit regime stand-aside
- Entry deliberately dumb/simple; edge claimed in **when to stand aside** and/or **management**, not in a closed daily signal family.
- Falsify stand-aside with placebos, not narrative.

### B. High-beta / TSLA–TSLL swing + theta (preferred exploration class, not mandate)
- Ken prior: swings + long-term positive bias; $3k one-lot defined-risk is a natural fit for **TSLL options** or carefully sized TSLA structures.
- Still multi-name free; still no plumbing-rank TSLL tunnel.
- Avoid reopening the exact Monday 45-DTE early-exit DNA above without a new mechanism (e.g. different structure class, different economic claim, different evidence geometry).

### C. Structure classes not yet holdout-closed as capital families
- Calendar / diagonal / debit / defined-risk verticals with honest data bounds.
- Discovery bar first (proxy OK if labeled); seat bar never proxy-only.

### D. Portfolio / inventory / cadence policy as the edge
- Frequency caps, correlation caps, “one risk unit” rules tested as mechanisms with controls.

### E. Capability unlock only if same-wake retest
- No capability-only finals. Repair must end in `STRATEGY_ADVANCED` or `FAMILY_CLOSED` for a dependent experiment.

### Explicitly lower priority next
- Another pure cross-section **underlying-only** selector on the same fixed survivorship-convenience panel without a new panel construction / out-of-sample name set / different horizon economics.
- More dual-cost PCS stop micro-variants of the closed Monday 45-DTE family.

---

## 5. Discovery bar vs capital-seat bar (unchanged)

| Bar | Use | May pass with | Cannot grant |
|---|---|---|---|
| **Discovery** | F0→F1 / F1→F2 signals | Labeled proxy, looser risk, non-vacuous n, chronology, predeclared falsifier | L1, capital path, paper seat |
| **Capital-seat** | L1 / paper path | Dual-cost non-vacuous edge, B3 density, max loss ≤$300, window DD ≤$75, dense-neg ≤5, defined-risk preferred | Live/shadow without Ken |

**Epoch success:** first valid `STRATEGY_ADVANCED` moving a named candidate **F0→F1** under discovery bar.  
Capital seat remains a later, stricter gate.

---

## 6. Operating rules for next densify burst

1. Continuous densify may re-arm only after this packet is active and `configs/search_epoch.json` points at the new epoch.
2. Every wake: strategy charter + one of `STRATEGY_ADVANCED` | `FAMILY_CLOSED` | `BLOCKER_REMOVED_AND_RETESTED` | `EVIDENCE_WAIT`.
3. Pivot at 2 epoch no-advances; burst-stop at 3 → return here, do not densify through it.
4. Ken soft prior (hypothesis class only): explore small repeatable profits from **time decay + price swings** with **positive long-term directional bias**, especially on liquid high-beta names including **TSLA/TSLL**, without forcing a single recipe.
5. Hard stops unchanged: no live, broker login, arm, shadow auto-promote, secrets in git.

---

## 7. Decision

**Open next epoch `2026-07-15-viable-path`.**  
Not `DIMINISHING_RETURNS` for the whole program — the first restart epoch exhausted three independent F0 axes cleanly; that is a design checkpoint, not platform death.

**Do not invent the next DNA here.** Trader picks one highest-information loop outside quarantine after re-arm.

---

## 8. Activation checklist

- [ ] `2026-07-14T2337` fully integrated (`RUN COMPLETE` + completion receipt) if not already
- [ ] Promote `configs/search_epoch_next.json` → `configs/search_epoch.json` (or rewrite active epoch with same fields)
- [ ] Link this doc from charter / readiness banner
- [ ] Re-arm continuous densify (`enabled=true`, clear `stop_reason`)
- [ ] Confirm first post-rearm wake orientation shows new epoch id + closed families + discovery/seat bars

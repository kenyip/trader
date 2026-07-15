# MOA BUILD challenger critique — 2026-07-15T1515

ROLE: Grok 4.5 challenger (read-only judgment)
PHASE: BUILD / L0 discovery
SLEEVE_USD: 3000
PAPER_ONLY: true
NO EVOLVE --apply / NO broker / NO arm / NO commit / NO RUN COMPLETE

## Overall judgment

**PASS WITH NITS**

Accept overall `BLOCKER_REMOVED_AND_RETESTED` with retest `STRATEGY_ADVANCED`, funnel `F0_MECHANISM → F1_TRAIN` only, claim bar **discovery / L0**, for candidate `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` / family `TIME_SERIES_20D_BREAKOUT_CONTINUATION`.

Do **not** accept any L1, capital seat, registry, paper eligibility, option after-cost, mispricing, or readiness promotion. Living leader remains **none**. Capital path remains **empty**.

## Rubric

| # | Item | Verdict | One line |
|---|---|---|---|
| 1 | Strategy charter | **PASS** | Mechanism, family, F0→F1, predeclared falsifier, and single closed outcome are explicit in charter + closeout + payload. |
| 2 | Strategy vs operations | **PASS** | New matching/lab capability is not claimed as strategy progress alone; same-wake retest produced advance-or-close residue. |
| 3 | Goal progress | **PASS WITH NITS** | New epoch + new mechanism + honest F1 train signal improves the discovery path; concentration keeps the edge fragile and non-paper. |
| 4 | Creativity / independence | **PASS** | Required reassessment first, then a within-symbol breakout event study outside closed selector/OPEX/PCS tunnels; pivot honored. |
| 5 | Claim validity | **PASS WITH NITS** | Only train discovery prerequisites used; option/holdout unread; survivorship panel labeled; do not let concentration get laundered into robustness. |
| 6 | Evidence / test quality | **PASS WITH NITS** | Canonical JSON + audit + 7/7 focused tests verified; useful leakage/bootstrap/zero-support/holdout-boundary checks; full-suite claim not re-run here. |
| 7 | Falsification | **PASS** | Six frozen train gates predeclared and applied; post-gate diagnostics honestly narrow rather than reverse the gate. |
| 8 | Capital honesty | **PASS** | No seat/leader; structural `capital_fit_usd=max_loss_usd=100`, `max_lots=1`; option package unpriced. |
| 9 | Research freedom | **PASS** | Burst-stop repaired by reassessment, not archive freeze or allowlist; unrelated routes not frozen. |
| 10 | ONE NEXT | **PASS** | Keep `BREAKOUT_UNTOUCHED_HOLDOUT_ONCE`; no option pricing unless holdout advances; no live/shadow. |

Score: **10/10 items accepted**; material claim stays **narrow F1/L0**.

## Independent verification performed

Read/verified:

- `reports/trader-wakes/moa/2026-07-15T1515/meta.json`
- `reports/trader-wakes/moa/2026-07-15T1515/executor-closeout.md`
- `reports/trader-wakes/moa/2026-07-15T1515/strategy-decision-charter.md`
- `reports/trader-wakes/2026-07-15T1515-moa-exec.md`
- `docs/SEARCH_DESIGN_REASSESSMENT_2026-07-15T1515.md`
- `configs/search_epoch.json` → epoch `2026-07-15-time-series-breakout-payoff`, `started_stamp=2026-07-15T1515`, `reassessment_complete=true`
- `docs/TRADER_LAYERED_EDGE_DOCTRINE.md`, `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`
- `reports/readiness/LATEST.md`, `reports/readiness/income-coverage-LATEST.md`
- Canonical evidence `.cache/platform/breakout_continuation_train_2026-07-15T1515.json`
- Audit `.cache/platform/breakout_continuation_train_2026-07-15T1515_audit.json`
- Rerun `.cache/platform/breakout_continuation_train_2026-07-15T1515_rerun.json`
- Lab + tests: `scripts/breakout_continuation_train_lab.py`, `tests/test_breakout_continuation_train_lab.py`

Independent checks:

1. Recomputed train means from persisted pairs: n=168; treated +1.6318%; control +0.0785%; excess +1.5533%; pos freq 52.98%. Matches closeout.
2. All six `gate_checks` true; `integrity_violations=[]`; holdout `outcome_metrics_read=false`, `simulation_run=false`, no holdout pairs payload; `pricing_calls=0`.
3. Cache-backed rerun: zero substantive diffs after excluding `generated_at` (within 1e-12 float noise on excess/LB).
4. Chronology: control always prior; treated entry strictly after signal; entry/exit windows non-overlapping under lab integrity. Cases where next `treated_signal_date == prior treated_exit_date` are allowed because occupied windows are **entry→exit**, not signal→exit; not an integrity failure.
5. Focused suite re-run: `.venv/bin/python -m unittest tests.test_breakout_continuation_train_lab -v` → **7/7 OK**.
6. Capital fields: 100 / 100 / max_lots=1; `registration_eligible=false`; `f2_or_l1_claim=false`.
7. Population validity correctly marks `survivorship_bias=true`, `bias_free=false`, `generalization_allowed=false`.

Not independently re-run by challenger: full `311/311` suite, platform smoke, coverage generator. Finalizer must re-verify those.

## What is accepted

### A. Burst-stop repair is real, not counter-reset theater

Prior active epoch closed three no-advance wakes and required reassessment. This wake:

- wrote `docs/SEARCH_DESIGN_REASSESSMENT_2026-07-15T1515.md`
- started new epoch `2026-07-15-time-series-breakout-payoff` in `configs/search_epoch.json`
- kept prior closed families quarantined
- then exercised one frozen new-mechanism experiment in the same wake

That is the correct `BLOCKER_REMOVED_AND_RETESTED` pattern.

### B. Layered Edge Stack is complete enough for F0→F1 discovery

Stack fields present: market/panel, `direction_up`, mechanism, conditional bull-call debit, intended/dangerous Greeks, regime/entry/exit/stand-aside, capital fit, falsifier, F1/L0 confidence. Option structure monetizes the stated directional forecast **conditionally**; not priced this wake, which matches the claim boundary.

### C. Predeclared discovery gate actually fired and passed

Canonical train:

- 281 matched blueprints → train 168 / holdout 113 unread
- all 8 symbols present; min floors 80 pairs / 6 symbols cleared
- treated mean after labeled 20 bps > 0
- paired excess mean > 0
- one-sided 90% five-pair-block bootstrap LB90 ≈ +0.2947% > 0
- integrity empty

Under the **discovery bar**, this is enough for `STRATEGY_ADVANCED` F0→F1/L0 only.

### D. Search information is real

Durable machinery: lagged breakout/trend features, prior-only same-symbol matching without replacement, non-overlapping entry/exit windows, chronological split, unread holdout boundary, labeled underlying sensitivity, circular block bootstrap gate, strict JSON nulls on zero support, CLI, and focused behavioral/boundary/negative-control tests (selection leakage via outcome shock, bootstrap reject path, zero support, nonfinite fail-closed, stack/holdout unread).

### E. Capital / authority honesty

No living leader, empty capital path, no B-check claim, no registry write, no paper/shadow/arm/live. Structural $100 width bound is correctly **not** treated as observed paid debit or stressed path loss.

## Nits (finalizer must preserve / tighten; none overturn the F1 discovery claim)

### N1 — Concentration is material; keep F1 claim pooled and fragile

Audit evidence is not optional color:

- MSFT / NVDA per-symbol paired means negative
- leave-TSLA-out LB90 negative (−0.1719%)
- train tertile 1 mean/LB90 negative; only middle tertile has positive LB90

Accept the **predeclared pooled** gate pass, but finalizer language must keep:

- not universal-by-symbol
- not temporally uniform
- not TSLA-independent
- not holdout-validated
- not option-payoff-validated

Do **not** invent a post-hoc concentration hard gate on already-inspected train rows. Do require the holdout wake to **report** symbol concentration, leave-one-symbol sensitivity, and chronological tertiles as mandatory diagnostics beside the frozen pooled gate.

### N2 — Fixed-horizon underlying evidence ≠ planned managed option path

Train measures a fixed 10-session next-session entry return. Planned later management (50% max-value harvest, invalidation below pre-breakout high, 14-DTE package) was **not** simulated. Keep wording as fixed-horizon directional pre-screen. Do not imply managed-path expectancy.

### N3 — 10-session outcome vs 14-DTE option is approximate alignment

Horizon mismatch is acceptable at F1 only if labeled: underlying 10-session continuation is a pre-screen for a later 14-DTE debit expression, not proof the option package harvests that drift after theta/vega/spread.

### N4 — Symmetric 20 bps does not stress paired excess

Executor already notes paired excess is invariant to symmetric round-trip sensitivity. Do not over-claim “cost robustness.” It is a labeled absolute-level sensitivity, not a differential friction or option-fill model.

### N5 — Test gaps are minor, not claim-invalidating

Focused suite is useful and green. Missing nice-to-haves for finalizer/tests (not required to reject F1):

- explicit negative control that `min_train_symbols=6` fails when breadth is thin (production path does pass `min_symbols=6`)
- explicit boundary that holdout outcomes cannot appear under JSON serialization already partly covered
- optional regression asserting leave-one-symbol diagnostics remain non-gating on train

### N6 — Full-suite / smoke / coverage claims are executor-attested only here

Challenger verified focused 7/7 and artifact arithmetic. Finalizer must re-run focused + full suite + smoke + handoff surfaces before integration.

### N7 — Readiness NEXT is already correct

`reports/readiness/LATEST.md` top block already records new epoch, narrow F1, empty capital path, and `BREAKOUT_UNTOUCHED_HOLDOUT_ONCE`. **No readiness NEXT patch required** unless finalizer changes the decision.

## Rejected overclaims (if anyone tries them later)

- Any L1 / capital seat / paper eligibility from this train file
- Any option mispricing, BS proxy edge, or fill realism
- Any “multi-name diversifier seat” because eight symbols appear
- Any generalization beyond the fixed present-day mega-cap/high-beta panel
- Any reopening of quarantined prior-epoch families because a new epoch started
- Any DIMINISHING_RETURNS freeze of unrelated historical routes

## Strategy outcome disposition for finalizer

| Field | Challenger disposition |
|---|---|
| Overall outcome | `BLOCKER_REMOVED_AND_RETESTED` |
| Retest decision | `STRATEGY_ADVANCED` |
| Funnel | `F0_MECHANISM → F1_TRAIN` |
| Strategy advancement | **true** (named candidate only; L0 discovery) |
| Registration / seat | **false** |
| Living leader | **none** |
| New-epoch no-advance streak if accepted | **0** |
| Pivot / burst-stop | false / false |

## ONE NEXT seed (challenger)

`BREAKOUT_UNTOUCHED_HOLDOUT_ONCE`

Build a fail-closed holdout validator that:

1. Reconstructs the exact frozen 281 blueprints under unchanged panel/signal/match/horizon/cost geometry.
2. Selects the reserved final 113 without retuning.
3. Reads those outcomes **exactly once**.
4. Closes F1→F2 as advance-or-`FAMILY_CLOSED` under a **predeclared pooled** after-cost / excess / bootstrap gate (same family geometry; no knob search).
5. Mandatorily reports temporal tertiles, per-symbol means, and leave-one-symbol pooled LB diagnostics (reporting only; do not invent a second inspected-train gate).
6. Prices **no** options unless holdout advances.
7. Changes no signal, match bounds, panel, horizon, or cost label.
8. No registry, seat, paper, shadow, arm, or live.

## Phase boundary

Challenger phase is partial. Finalizer must reconcile nits, re-verify, promote learning, and prepare integration. Deterministic commit/push/merge/origin equality/clean tree/completion receipt remain **not done**.

MOA_CHALL_DONE

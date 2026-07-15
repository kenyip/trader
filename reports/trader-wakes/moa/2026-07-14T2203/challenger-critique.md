# MOA BUILD challenger critique — 2026-07-14T2203 (Grok 4.5)

PHASE: BUILD / research only
SLEEVE_USD: 3000
ROLE: Grok 4.5 challenger (read-only judgment)
PAPER_ONLY: true
NO_EVOLVE_APPLY: true
NO_BROKER_ARM_LIVE: true

## FINAL JUDGMENT

**PASS with nits.** Accept executor outcome `FAMILY_CLOSED`, strategy advancement false, `F0_MECHANISM -> F0_MECHANISM` for closed family `pcs-monday-45dte-exit21-vs-exit5-train-proxy`.

Canonical evidence verified:
- `reports/trader-wakes/moa/2026-07-14T2203/pcs-early-exit-train.json`
- Challenger-recomputed executor SHA-256 `831c007eb7b07cc6c0bdc67a87f45cb69237c869067a72450ec99f591edb8587`; finalizer later accepted nit 3, repaired operating/theoretical-lot labels, and regenerated the canonical artifact at SHA-256 `39113fe2aa6fa071a09902470fad3e39a30cf765a2dfdf32e1d42986a9c6446e` with substantive strategy metrics unchanged.
- Charter: `strategy-charter.md` + executor closeout
- Lab: `scripts/pcs_early_exit_train_lab.py`
- Tests: `tests/test_pcs_early_exit_train_lab.py` (challenger re-ran 4/4 OK)

Independent metric audit (train only; holdout untouched as claimed):

| Symbol | 5% n / PnL / DD | Fixed n / PnL / DD | Dual+ | Worst>ctrl | Cand cal-stops |
|---|---:|---:|---|---|---:|
| BAC | 42 / −154.92 / 147.97 | 41 / −156.50 / 150.27 | no | yes | 2 |
| F | 33 / −148.72 / 166.60 | 26 / −229.10 / 199.90 | no | no (identical) | 0 |
| SOFI | 32 / −85.95 / 103.09 | 29 / −111.35 / 120.82 | no | no (identical) | 0 |
| PLTR | 41 / −156.76 / 227.85 | 42 / −87.69 / 195.20 | no | no | 2 |
| TSLL | 22 / −125.71 / 157.37 | 22 / −36.30 / 129.35 | no | no | 2 |
| SMCI | 31 / −195.45 / 265.64 | 36 / −106.02 / 166.06 | no | no | 2 |
| AMD | 28 / −750.97 / 730.03 | 37 / −150.68 / 266.47 | no | no | 8 |
| AAPL | 37 / −470.44 / 425.24 | 41 / +128.60 / 159.55 | no | no | 1 |

- `n_discovery_pass=0`; `selected_candidate_id=None`; `pooled_qualifying_worst_axis_pnl=0` (empty-set, not affirmative edge).
- Every 5% axis non-vacuous and negative (`−750.97..−85.95`); fixed axis negative on 7/8; AAPL fixed +128.60 fails dual-cost with 5% −470.44.
- Integrity true and same-bar reentries 0 on inspected axes; chronology_ok true; population pure; ranking complete; registry writes false.
- One-lot max loss `$85.76..$235.43` fits sleeve/`$300` gate; capital fit does not rescue negative expectancy.
- Living leader remains **none**; no L1/capital-seat/paper/shadow/arm/live claim.

## Rubric (PASS/FAIL + one line)

1. **Strategy charter — PASS.** Mechanism, fixed Monday 45-DTE/exit21 vs exit5 scope, F0→F0, predeclared dual-cost+control falsifier, and exact `FAMILY_CLOSED` are explicit.
2. **Strategy vs operations — PASS.** Lab/tests/diagnostics are search information; outcome is experiment-closed `FAMILY_CLOSED`, not tooling-as-progress.
3. **Goal progress — PASS.** Honest F0 close of one new open time-management family improves search by quarantine; first post-reassessment epoch wake without thrash.
4. **Creativity / independence — PASS.** Autonomous simple-entry time-decay management axis from open reassessment routes; not TSLL monomania or prior NEXT order; pivot not required (epoch streak was 0).
5. **Claim validity — PASS.** Prerequisites match experiment; BS proxy/L0 labeled; holdout not spent; discovery bar used without seat claim.
6. **Evidence / test quality — PASS with nit.** Real artifact + lab + 4 behavioral/boundary/negative-control unit tests; executor-cited focused 36/full 268 not re-executed by challenger (finalizer must re-verify).
7. **Falsification — PASS.** Predeclared dual-cost positive + control outperformance + integrity + max-loss gates fail closed; dominant failure is cost-adjusted expectancy.
8. **Capital honesty — PASS.** No living leader/seat; defined-risk one-lot bounds reported; all candidate DDs also exceed `$75` capital-seat bar (secondary).
9. **Research freedom — PASS.** No freeze from archive blockage; historical-proxy route used correctly; quarantine is family-specific not global stop.
10. **ONE NEXT — PASS with tighten.** Accept lagged monthly cross-sectional low-HV underlying pre-screen as new evidence class; keep option marks gated on underlying advance.

## Accepted claims

1. `FAMILY_CLOSED` at F0 for the exact fixed-DNA family is justified and reproducible from the JSON.
2. Search information (train-only causal-management lab + control-fail-closed gate + stop diagnostics) is real and secondary.
3. Untouched final-40% holdout was not used for ranking or decision.
4. Epoch accounting: if integrated, no-advance streak becomes 1; pivot/burst-stop remain false.
5. NEXT seed is a materially different cross-sectional evidence class, not a nearby PCS stop nudge.

## Nits (non-blocking; finalizer should reconcile in prose/surfaces)

1. **Sparse mechanism contrast (record honestly).** Candidate calendar-stop exits total 17 across 16 symbol/cost rows (mostly AMD=8); F and SOFI are path-identical to the 5-DTE control on both axes. Profit-target and regime-flip dominate exits; avg hold is usually ~7–13 days, so dte_stop=21 rarely binds. Dominant failure wording should be: cost-adjusted expectancy under PT/regime-dominated Monday 45-DTE PCS management, with only sparse early-calendar-stop contrast — not a pure early-theta vs late-gamma isolation. Executor already notes other exits usually fire first; keep that as primary, not a footnote.

2. **Quarantine scope.** Close `pcs-monday-45dte-exit21-vs-exit5-train-proxy` and nearby stop nudges / symbol cherry-picks of this DNA. Do **not** freeze all Monday PCS or all 45-DTE management forever without a new evidence class.

3. **`max_lots` labeling.** Axis rows from `summarize_result` still show `max_lots=3` while top-level `_capital_fields` forces operating `max_lots=1`. Prefer explicit operating vs theoretical capacity labels on any living summary (optional code polish, not claim-invalidating).

4. **Verification ownership.** Challenger re-ran only the new 4 lab tests OK. Finalizer must re-run focused + full suite and any substantive reproduction before integration.

5. **NEXT anti-leakage constraints (accept, tighten).** Monthly cross-sectional low-HV screen must use only **prior completed** 60-session HV known before the rank month, same-date top-quartile controls, chronological train then untouched holdout on **underlying** forward returns first, and option marks only if the underlying mechanism advances. No reopening closed families; no paper/shadow/arm/live.

## Rejected / not present overclaims

- No STRATEGY_ADVANCED, L1, capital seat, B-check advance, registry mutation, or paper/shadow/live authority.
- No claim that observed option surfaces were required or that archive density freezes research.
- No stale `b195f5fe` seat resurrection.

## Freedom / thrash audit

Symbol/strategy freedom intact. Loop is distinct from closed gap-recovery, TOM, VRP, daily signal PCS families, and BAC Friday 7-DTE. Not thrash: new fixed DNA + causal control + train-only discovery bar under active epoch `2026-07-14-reassess`.

## Disposition for finalizer

- Accept `FAMILY_CLOSED` / no strategy advance.
- Reconcile nits 1–5 in durable surfaces (wake/merge/readiness/compounding closed-family text).
- Re-verify tests; promote learning; prepare integration. Do **not** retune DNA or spend holdout to rescue.
- Keep ONE NEXT as cross-sectional low-HV pre-screen with constraints above.

Challenger phase only. No commit, push, merge, evolve `--apply`, broker, arm, or `RUN COMPLETE`.

MOA_CHALL_DONE

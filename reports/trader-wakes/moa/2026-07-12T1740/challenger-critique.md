# MOA BUILD challenger critique — 2026-07-12T1740

WAKE: 2026-07-12T1750 PDT (Sunday; market closed)
PHASE: BUILD
SLEEVE_USD: 3000
PAPER_ONLY: true
ROLE: Grok 4.5 challenger (read-only judgment); partial phase only

## Scope reviewed

- `reports/trader-wakes/moa/2026-07-12T1740/meta.json`
- `reports/trader-wakes/moa/2026-07-12T1740/executor-closeout.md`
- `reports/trader-wakes/moa/2026-07-12T1740/orientation.json`
- `reports/trader-wakes/2026-07-12T1740-moa-exec.md`
- `reports/trader-wakes/LATEST.md`
- `reports/readiness/LATEST.md`
- `reports/readiness/income-coverage-LATEST.md`
- `.cache/platform/pcs_trend_pullback_rolling_origin_lab_2026-07-12T1740.json`
- `scripts/pcs_trend_pullback_rolling_origin_lab.py`
- `tests/test_pcs_trend_pullback_rolling_origin_lab.py`
- `trader_platform/research/pcs_sim.py` (`entry_filters_pass` ret_5d/ret_14d/ema_stack + fail-closed nonnumeric)
- Doctrine: `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`, skill `trader-self-evolution`
- Prior context: 1700 DIMINISHING_RETURNS, 1735 historical-route unblock, closed adjacent-daily PCS/CCS signal families

Independent checks: focused sibling suite 36/36 OK; full unittest discovery 137/137 OK; JSON walk recomputed decision, train/complete fold counts, capital ranges, PLTR holdout DD/PnL, integrity run-summary count 286/286, signal/reentry zeros.

## Chosen loop (executor)

Predeclared multi-horizon trend-pullback PCS: prior completed-bar `ret_5d <= 0`, `ret_14d >= 3%`, bullish EMA stack (`ema_stack >= 1/3`), 21-DTE defined-risk put credit spread. Eight symbols × expanding 40/60/80% rolling-origin train gates + untouched holdouts; dual proxy costs (5% leg slip + $0.01/leg half-spread); unconditional + bearish multi-horizon mirror controls; absolute gates with no living leader.

Decision claimed: `REJECT_MULTI_HORIZON_TREND_PULLBACK_PCS`.

Supersession of prior NEXT: Sunday cannot add a distinct RTH archive date; 1700 archive-weighted stop was invalidated by 1735 route inventory; multi-horizon is a new evidence class vs closed adjacent-daily families. Accepted.

## Independent metric verification

| Claim | Executor | Independent | Match |
|---|---|---|---|
| Decision | REJECT_MULTI_HORIZON_TREND_PULLBACK_PCS | same | yes |
| Completions / errors | 8/8, 0 errors | same | yes |
| Train gates / complete folds / all-fold | 4/24, 0/24, 0/8 | same (BAC f2, SOFI f1/f2, PLTR f1 train-only) | yes |
| Integrity | 286/286 exact; signal0; reentry0 | 286 run summaries with `integrity`+`n_trades` all true; signal/reentry sums 0 | yes |
| Capital fit range | $75.30–$225.80 | same | yes |
| Worst one-lot max_loss | $227.19 | AMD holdout slip_5pct $227.19; all ≤$300 | yes |
| PLTR train-pass holdout | slip −$208.97 / DD $214.28; fixed −$39.62 / DD $118.96 | same | yes |
| Other train-pass holdout fails | BAC n=5 NEEDS_MORE_DATA; SOFI f1 n=9 NULL; SOFI f2 slip −$1.16 | same | yes |
| Living leader / L1 / registry | none / no seat / no mutation | readiness L0; coverage no leader; claim_scope proxy L0 | yes |
| Suite | focused 36/36; full 137/137; smoke green | reconfirm 36/36 and 137/137 | yes |

Conjunctive train-before-holdout is live: zero complete folds despite four train gates. No holdout-shopping or threshold retune after reject.

## Rubric

1. **Goal progress — PASS.** Material honest falsification of a new multi-horizon signal class plus reusable fail-closed `ret_5d`/`ret_14d`/`ema_stack` machinery. No L1 advance; family-close and capability delta are valid free-goal progress. Improves the map of what does not work under dual proxy costs.

2. **Creativity and independence — PASS.** Not TSLL-PCS monomania and not a retune of closed mild-pullback / close-shock / momentum / vol-compression DNA. Multi-horizon (5d pullback inside 14d/EMA trend) is a named new evidence class. Prior DIMINISHING_RETURNS / archive NEXT correctly treated as context and superseded with executable Sunday rationale.

3. **Claim validity — PASS.** Prerequisites match the experiment: lagged completed-bar signals, listed-Friday/rounded-strike BS marks labeled, dual proxy costs, absolute gates with empty leader. No promotion, registration, paper/shadow/live, or observed-cost claim. JSON `claim_scope` is explicit and correct.

4. **Evidence and test quality — PASS (minor nits).** Real lab path, real tools, independent JSON verification, full suite green. Behavioral tests cover lag, multi-axis mirror disjointness, fail-closed bad inputs, and unconditional filter removal. Shared `_fold_pass` / cost axes from prior rolling-origin labs are reused and empirically confirmed by the four train-only failures. Nit: this module does not locally re-assert the train-fail/holdout-pass negative control that sibling vol-compression/pullback tests carry. Not claim-invalidating because the shared helper already enforces the conjunctive gate.

5. **Falsification — PASS.** Clear predeclared falsifier; 0/24 complete folds; train gates independent; no grid/threshold/DTE/management tuning after partial train survival; negative controls persisted; family closed this cycle without registration.

6. **Capital honesty — PASS.** No living quality leader; absolute gates used (ml≤$300, DD≤$75, dense-neg≤5, dual-cost positive SHIP). Structure `put_credit_spread`; capital_fit/max_loss/max_lots stated; worst observed one-lot max loss $227.19 ≤$300; operational posture 1 lot. Engine `max_lots=3` is sleeve-capacity math, not a multi-lot seat — executor labeled this correctly. Rejected family is not a candidate.

7. **Research freedom — PASS.** Blocked one-date archive did not freeze unrelated historical-proxy exploration. Orientation redirect after 1700 stop was honored with a new class, not thrash on the same adjacent-daily signature. No removable prompt restriction observed. Anti-thrash note: another pure daily-bar multi-feature PCS signal retune without new machinery would now be thrash; this wake itself remains justified.

8. **ONE highest-information NEXT — PASS (tightened).** Executor pivot to dividend/ex-date + early-assignment risk boundary for short-call diagonal/debit sims is higher-information than another PCS signal filter or Sunday archive append. Matches explicit coverage gaps and orientation’s executable `simulator_capability_work` route. Keep proxy L0; fail closed when event data absent; do not reopen closed signal families; RTH archive 1→2/3 remains parallel orientation-only when a distinct NY market date exists.

## Verdict

**OVERALL: PASS 8/8**

Accept executor decision and family close. No claim-invalidating defect requiring rewrite of the rejection.

### Accepted findings (finalizer should carry)

1. Close family / novelty keys: `pcs-multi-horizon-trend-pullback-daily-bar` and `pcs-multi-horizon-trend-pullback-rolling-origin-8x3-reject`. Do not reopen on the same synthetic marks/costs or threshold polish.
2. Keep living leader empty; readiness formal B checks unchanged; L0 BUILD.
3. Do not promote, register, or seat any result from this lab.
4. Optional non-blocking harden: local train-fail/holdout-pass negative-control test on `tests/test_pcs_trend_pullback_rolling_origin_lab.py` (parity with vol-compression/pullback siblings); ensure orientation/compounding `closed_families` includes the new key after integration.
5. Promote reusable lesson: multi-horizon 5d/14d/EMA trend-pullback PCS produced train-only survival and zero dual-cost rolling-origin holdouts — threshold tuning is thrash; capability boundary for dividends/assignment is the higher-leverage next route.
6. Skill note (optional, small): add the multi-horizon reject + fail-closed nonnumeric configured-feature pitfall to `trader-self-evolution` if not already covered by generic entry-filter guidance.

### Rejected / not accepted as defects

- “Four train gates means almost-edge; retune thresholds” — thrash; predeclared falsifier and zero complete folds correctly stop.
- “Must execute archive NEXT on Sunday” — not executable without a distinct NY RTH date; supersede was correct after 1735 route repair.
- “Integrity 334 nested fields vs 286 claim” — 286 is the established run-summary convention (`integrity` + `n_trades`); all 286 true; nested window fields also exact.
- “Missing local train-fail test invalidates REJECT” — shared `_fold_pass` already conjunctive; optional harden only.

## Capital path / promotion

- Living quality leader: none
- L1 hyps: none
- This family: research-only reject; no candidate/testing/paper status change
- Hard stops held: no evolve `--apply` by challenger; no broker/live/shadow/arm

## Partial phase contract

Challenger writes critique + merge seed + merge wake report + LATEST/INDEX only. No commit, push, merge, or `RUN COMPLETE`. Finalizer repairs accepted optional nits, reconfirms verification, promotes learning, and prepares deterministic integration.

MOA_CHALL_DONE

# MOA BUILD challenger critique — 2026-07-12T1636

WAKE: 2026-07-12T1646 PDT (Sunday; market closed)
PHASE: BUILD
SLEEVE_USD: 3000
PAPER_ONLY: true
ROLE: Grok 4.5 challenger (read-only judgment); partial phase only

## Scope reviewed

- `reports/trader-wakes/moa/2026-07-12T1636/meta.json`
- `reports/trader-wakes/moa/2026-07-12T1636/executor-closeout.md`
- `reports/trader-wakes/moa/2026-07-12T1636/orientation.json`
- `reports/trader-wakes/2026-07-12T1636-moa-exec.md`
- `reports/trader-wakes/LATEST.md`
- `reports/readiness/LATEST.md`
- `reports/readiness/income-coverage-LATEST.md`
- `.cache/platform/ccs_vol_expansion_rolling_origin_lab_2026-07-12T1636.json`
- `scripts/ccs_vol_expansion_rolling_origin_lab.py`
- `tests/test_ccs_vol_expansion_rolling_origin_lab.py`
- Prior sibling: `.cache/platform/pcs_vol_compression_rolling_origin_lab_2026-07-12T1616.json`
- Archive density: `.cache/platform/option_quote_archive_density_2026-07-11T2031.json` (TSLL 1/3 market dates; `provider_backtest_eligible=false`)

Independent checks: full-suite unittest 126/126 OK; focused new-module tests 3/3 OK; JSON walk recomputed decision, fold counts, integrity, and per-symbol min_n / worst DD / worst max_loss.

## Chosen loop (executor)

Predeclared direction-aligned **bearish volatility-expansion CCS**: prior completed-bar `hv_20/hv_60 >= 1.20` and `ret_1d <= 0`, 14-DTE $1-wide defined-risk call credit spread, eight symbols × expanding 40/60/80% rolling-origin train gates + untouched holdouts, dual proxy costs, unconditional + compression CCS controls.

Decision claimed: `REJECT_VOL_EXPANSION_CCS_ROLLING_ORIGIN`.

## Independent metric verification

| Claim | Executor | Independent | Match |
|---|---|---|---|
| Decision | REJECT_VOL_EXPANSION_CCS_ROLLING_ORIGIN | same | yes |
| Completions / errors | 8/8, 0 errors | same | yes |
| Train gates / complete folds / all-fold | 0/24, 0/24, 0/8 | same | yes |
| Integrity | 286/286 exact; signal0; reentry0 | 286 summaries with integrity+n_trades+pnl+max_loss all true; violations 0; reentries 0 | yes |
| Min strategy-axis n by symbol | 0–6 | BAC6 F4 SOFI3 PLTR1 TSLL2 SMCI2 AMD0 AAPL3 | yes |
| Worst fold-axis DD by symbol | $76.20–$347.91 | TSLL 76.20 … AAPL 347.91 | yes |
| Worst one-lot max_loss by symbol | $94.71–$237.36 | BAC 94.71 … AAPL 237.36; all ≤300 | yes |
| Living leader / L1 / registry | none / no seat / no mutation | readiness L0; archive still 1/3 | yes |
| Suite | focused 31/31; full 126/126 | full reconfirm 126/126; new module 3/3 | yes |

Conjunctive train-before-holdout is live in evidence: BAC fold0 holdout both axes positive (slip +$25.34 / fixed +$38.97) while train both axes negative → `train_gate_pass=false` and `fold_gate_pass=false`. No holdout rescue path.

## Rubric

1. **Goal progress — PASS.** Material honest falsification of the natural complementary family (bearish expansion CCS after compression PCS). Adds a reusable harness + doctrine/coverage residue. Does not advance L1; stand-aside / family-close is valid progress under the free goal.
2. **Creativity and independence — PASS.** Not a familiar-recipe tunnel into TSLL PCS or a retune of closed compression DNA. Structure flipped to CCS; state flipped to expansion + non-positive return; prior RTH-archive NEXT correctly treated as context and superseded on Sunday with explicit non-executability reason.
3. **Claim validity — PASS.** Prerequisites match the experiment: lagged completed-bar HV/return, synthetic Friday/rounded-strike BS marks labeled, dual proxy costs, absolute gates with no living leader. No promotion, no L1, no observed-cost claim. Claim scope in JSON is explicit and correct.
4. **Evidence and test quality — PASS (minor nits).** Real lab path + real tools. Behavioral tests cover lag/disjoint expansion vs compression, unconditional signal removal, and CCS population purity. Shared `_fold_pass` / HV fail-closed machinery from prior wakes is reused and empirically confirmed. Nit: this module does not locally re-assert the train-fail/holdout-pass negative control or nonnumeric HV fail-close (those live in sibling PCS labs / pcs_sim). Not claim-invalidating because the shared helper and BAC counterexample already enforce the conjunctive gate.
5. **Falsification — PASS.** Clear predeclared falsifier; 0/24 train gates stops before holdout shopping; no threshold/DTE/management tuning; family closed this cycle; negative controls persisted (unconditional + compression CCS).
6. **Capital honesty — PASS.** No living quality leader; absolute gates used; structure `call_credit_spread`; capital_fit/max_loss/max_lots fields present; worst observed one-lot max loss ≤$237.36 ≤$300; default 1-lot posture stated. Note: sim capital rows report `max_lots=3` as sleeve-capacity math, not a seat or multi-lot claim — executor labeled this correctly.
7. **Research freedom — PASS.** Blocked archive density (1/3) did not freeze unrelated valid exploration. Sunday BUILD chose a non-archive loop with a new evidence/structure combination. No removable prompt restriction observed. Anti-thrash: another pure daily-bar HV-ratio sibling without a new evidence class would now be thrash — this wake itself is still justified.
8. **ONE highest-information NEXT — PASS.** Distinct-RTH all-expiration TSLL archive append 1→2/3; no provider-backed historical sim / observed-cost calibration / L1 before 3/3; no live/shadow/arm. Correct priority now that the complementary synthetic HV family is closed.

## Verdict

**OVERALL: PASS 8/8**

Accept executor decision and family close. No claim-invalidating defect requiring rewrite of the rejection.

### Accepted findings (finalizer should carry)

1. Close family key: `ccs-vol-expansion-daily-bar` / novelty `ccs-realized-vol-expansion-rolling-origin-8x3-reject` (do not reopen on same synthetic marks/costs).
2. Keep living leader empty; readiness B checks unchanged; L0 BUILD.
3. Do not promote, register, or seat any result from this lab.
4. Optional non-blocking harden (same class as 1616 finalizer polish, not required to uphold REJECT): local train-fail/holdout-pass negative-control test on this module; ensure orientation/compounding closed_families includes the new key after integration.
5. Minor doctrine nit (non-blocking): `docs/BUILD_LAB_ENVIRONMENT.md` direction-bias cell now emphasizes router + this CCS reject and under-mentions the four prior PCS signal rejects; income-coverage gap text is more complete. Prefer aligning BUILD doc language without inventing new claims.

### Rejected / not accepted as defects

- “Sparse samples mean inconclusive, not reject” — falsifier requires min trades and train gates; sparse/zero train axes correctly fail closed.
- “Should have tuned ratio/DTE after 0/24” — thrash; executor stop rule is correct.
- “Must execute archive NEXT on Sunday” — not executable without a distinct NY RTH market date; supersede was correct.

## Capital path / promotion

None. No shadow/live. No arm packet. Paper/research only.

## Phase status

Partial challenger critique only. No evolve `--apply`, no broker, no commit/push/merge, no RUN COMPLETE.

MOA_CHALL_DONE

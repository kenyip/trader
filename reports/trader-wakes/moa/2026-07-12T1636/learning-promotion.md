# MOA BUILD learning promotion — 2026-07-12T1636

## VERIFICATION

- Exact lab rerun: `.venv/bin/python scripts/ccs_vol_expansion_rolling_origin_lab.py --out .cache/platform/ccs_vol_expansion_rolling_origin_lab_2026-07-12T1636.json` → `REJECT_VOL_EXPANSION_CCS_ROLLING_ORIGIN`; 8 completed symbols, 24 folds, 0 train-gate passes, 0 complete-fold passes, 0 errors.
- Independent artifact reduction: 286/286 persisted strategy/control/window summaries had `integrity=true`; aggregate `signal_violations=0` and `same_bar_reentries=0`; minimum strategy-axis trade counts were BAC6/F4/SOFI3/PLTR1/TSLL2/SMCI2/AMD0/AAPL3; worst fold-axis drawdown was BAC $175.57, F $81.31, SOFI $86.44, PLTR $311.68, TSLL $76.20, SMCI $140.58, AMD $222.90, AAPL $347.91; worst one-lot max loss was $94.71–$237.36.
- Focused behavioral/boundary/negative-control/regression suite: `.venv/bin/python -m unittest tests.test_ccs_vol_expansion_rolling_origin_lab tests.test_pcs_vol_compression_rolling_origin_lab tests.test_pcs_pullback_rolling_origin_lab tests.test_pcs_momentum_walkforward_lab tests.test_pcs_expiry_grid tests.test_pcs_direction_scoreboard` → 32 tests, OK. Finalizer strengthened the new CCS file from three to four tests with an explicit passing-holdout/failing-train fold-gate negative control.
- Full regression: `.venv/bin/python -m unittest discover -s tests` → 127 tests, OK.
- Compile: `.venv/bin/python -m py_compile scripts/ccs_vol_expansion_rolling_origin_lab.py tests/test_ccs_vol_expansion_rolling_origin_lab.py scripts/trader_income_coverage.py` → exit 0.
- Derived coverage regeneration: `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-12T1636` → 20 structures, 245 hypotheses, 67 evolve artifacts, no living quality leader; dated and LATEST coverage files agree.
- Structured handoff: `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-12T1636 --base-head b101f799e9405b21f28287eb87aa07f47fbe0326` → `ok=true`, `role_ready=true`, outcome `FALSIFIED`, 1 useful delta, 4 closed critic findings, and novelty key `ccs-realized-vol-expansion-rolling-origin-8x3-reject`.
- Consistency/whitespace: `cmp` proved the dated merge equals wake `LATEST.md` and dated income coverage equals coverage `LATEST.md`; `python -m json.tool` accepted `compounding.json`; `git diff --check b101f799e9405b21f28287eb87aa07f47fbe0326` → exit 0.
- Complete base-diff audit: tracked changes plus `git ls-files --others --exclude-standard` contain 21 intended text paths (7 tracked modifications, 14 untracked run artifacts). The completion-gate path/secret patterns found zero sensitive paths, zero binary files, and zero raw-secret markers or assignments. The run-created duplicate unstamped coverage surface `income-coverage-2026-07-12T1643.md` was removed; the deterministic 1636 dated surface remains.
- Accepted challenger findings: PASS 8/8, the rejection decision and cited aggregates match the exact rerun, the family remains unregistered and closed, living leader remains empty, readiness stays BUILD/L0, and synthetic option marks/costs cannot earn L1.
- Repaired challenger findings: added the local train-fail/holdout-pass negative control; aligned BUILD and generated coverage language so close-shock, momentum, pullback, and volatility-compression PCS history is not hidden behind the new CCS result; added `ccs-vol-expansion-daily-bar` to the structured closed-family handoff.
- Rejected findings with evidence: sparse samples are a predeclared fail-closed gate rather than an inconclusive pass; threshold/DTE/management tuning after 0/24 train gates would be same-evidence thrash; Sunday cannot create a distinct New York RTH archive date, so the archive NEXT was correctly superseded for this wake and retained for the next valid date.
- Integration remains pending the deterministic wrapper gate. This finalizer did not commit, push, merge, switch branches, or claim RUN COMPLETE.

## DURABLE

- Project truth and dated evidence: `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`, `reports/trader-wakes/2026-07-12T1636-moa-exec.md`, `reports/trader-wakes/2026-07-12T1636-moa-merge.md`, `reports/trader-wakes/LATEST.md`, `reports/trader-wakes/INDEX.md`, and `reports/readiness/LATEST.md` agree that `ccs-vol-expansion-daily-bar` is closed, the capital path is empty, archive density remains 1/3, and readiness remains BUILD/L0.
- Reusable machinery and tests: `scripts/ccs_vol_expansion_rolling_origin_lab.py` and `tests/test_ccs_vol_expansion_rolling_origin_lab.py` preserve structure-pure CCS dispatch, lagged/disjoint volatility controls, train-before-holdout gating, dual proxy costs, and the local negative control.
- Generated truth: `scripts/trader_income_coverage.py`, `reports/readiness/income-coverage-2026-07-12T1636.md`, and `reports/readiness/income-coverage-LATEST.md` now name the prior PCS signal families and the CCS expansion rejection consistently.
- No skill update: the reusable prior-bar realized-volatility parsing, disjoint controls, and train∧holdout negative-control procedure was already promoted by the 1616 finalizer into `trader-self-evolution`; this wake applies that procedure to CCS and adds dated strategy evidence rather than a new general pitfall.
- No profile-memory update: this is dated research evidence, not a stable Ken preference, environment fact, or cross-session routing rule.

## LESSON

Future Trader can test a direction-aligned CCS complement without confusing a bearish structure change for independent edge: prior-bar realized-volatility expansion plus non-positive return still failed every rolling-origin train gate under both proxy cost axes. The correct durable outcome is to close the CCS daily-bar expansion family on current synthetic evidence, preserve train-before-holdout fail-close locally, and wait for a genuinely new evidence class rather than tune threshold, DTE, or management against the same marks.

## NEXT

On the next distinct New York RTH market date, append one all-expiration TSLL option observation snapshot and verify archive density advances from 1/3 to 2/3 without duplicating identical rows. Do not run provider-backed historical simulation, observed-cost calibration, evolve-on-observed-grid, or L1 claims before 3/3 dates (`provider_backtest_eligible=true`).

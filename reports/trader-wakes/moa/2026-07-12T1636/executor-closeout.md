# MOA BUILD executor closeout — 2026-07-12T1636

WAKE: 2026-07-12T1636 PDT (Sunday; market closed)
PHASE: BUILD
SLEEVE_USD: 3000
PAPER_ONLY: true
ROLE: GPT 5.6 Sol executor; partial phase only

## Chosen closed loop

Test one predeclared, direction-aligned bearish volatility-expansion call-credit-spread family with rolling-origin train gates and untouched holdouts. This is a new CCS structure/signal combination rather than reopening the closed volatility-compression PCS family. The prior archive NEXT was not executable on Sunday; it remains the next data-dependent seed.

Hypothesis: a prior completed-bar `hv_20/hv_60 >= 1.20` state plus non-positive return identifies bearish expansion states where one 14-DTE, $1-wide defined-risk CCS earns positive after-cost income.

Falsifier: no symbol passes every expanding 40/60/80% train gate and following holdout under both 5% adverse leg slip and $0.01-per-leg half-spread, with at least eight trades per axis, positive SHIP, one-lot max loss <=$300, drawdown <=$75, dense-negative windows <=5, and exact ledger/signal integrity.

## What changed

- Added `scripts/ccs_vol_expansion_rolling_origin_lab.py` with one fixed DNA, unconditional CCS and volatility-compression CCS controls, train-before-holdout gating, two proxy cost axes, capital fields, and explicit synthetic/observed provenance.
- Added `tests/test_ccs_vol_expansion_rolling_origin_lab.py` covering lag/disjoint controls, signal removal, and call-credit-spread dispatch/population purity.
- Ran the exact eight-symbol experiment to `.cache/platform/ccs_vol_expansion_rolling_origin_lab_2026-07-12T1636.json`.
- Updated BUILD and coverage doctrine plus the generated coverage gap source. No registry mutation, hypothesis registration, status promotion, paper order, broker session, shadow action, arm, or live action.

## Evidence and decision

Decision: `REJECT_VOL_EXPANSION_CCS_ROLLING_ORIGIN`.

- Population: BAC, F, SOFI, PLTR, TSLL, SMCI, AMD, AAPL; 8/8 completed, 0 errors.
- Rolling-origin gates: 0/24 train gates passed; 0/24 complete folds passed; 0/8 symbols passed all folds.
- Minimum strategy-axis sample count by symbol: BAC 6, F 4, SOFI 3, PLTR 1, TSLL 2, SMCI 2, AMD 0, AAPL 3.
- Worst fold-axis drawdown by symbol: BAC $175.57, F $81.31, SOFI $86.44, PLTR $311.68, TSLL $76.20, SMCI $140.58, AMD $222.90, AAPL $347.91.
- Worst one-lot max loss by symbol: BAC $94.71, F $94.93, SOFI $94.82, PLTR $231.77, TSLL $94.82, SMCI $223.43, AMD $233.00, AAPL $237.36.
- Integrity: 286/286 strategy/control/window summaries exact; signal violations 0; same-bar re-entry 0.
- Structure: call credit spread. `capital_fit_usd` is per result and <=$3,000 by gate; worst observed one-lot `max_loss_usd` $237.36; `max_lots` is per result, but default posture remains 1 lot.
- Living quality leader: none. Absolute gates used. No result can earn L1 because option marks, listed-Friday strike grids, and costs remain synthetic proxies.

The family is closed this cycle without threshold, DTE, or management tuning. Capital path and readiness B checks remain unchanged at L0 BUILD.

## Validity critique

- Leakage/lookahead: volatility ratio and return are consumed from the prior completed bar via `entry_signal_lag_bars=1`.
- Selection: one predeclared DNA; no grid, no holdout-driven selection, and train gate is conjunctive with holdout.
- Costs/fills: both percentage and fixed-dollar adverse proxy axes are required; neither is represented as observed spread evidence.
- Contract availability: synthetic Friday expirations and rounded strikes only; archive-backed provider remains blocked at one of three market dates.
- Population/ranking: structure-pure CCS, all eight names completed, and no stale leader comparison was used.
- Path realism: one-position-per-bar and independent ledger recomputation are exact; B6 live-clock paper evidence remains absent.
- Freedom audit: symbol universe and strategy catalog remained open; the loop used a non-PCS directional family and imposed only evidence/capital gates.

## Verification

- `.venv/bin/python -m py_compile scripts/ccs_vol_expansion_rolling_origin_lab.py tests/test_ccs_vol_expansion_rolling_origin_lab.py` — pass.
- Initial focused command named two nonexistent test modules and failed after 12 real tests passed; corrected module discovery rather than normalizing the error.
- `.venv/bin/python -m unittest tests.test_ccs_vol_expansion_rolling_origin_lab tests.test_pcs_vol_compression_rolling_origin_lab tests.test_pcs_pullback_rolling_origin_lab tests.test_pcs_momentum_walkforward_lab tests.test_pcs_expiry_grid tests.test_pcs_direction_scoreboard` — 31/31 OK.
- `.venv/bin/python -m unittest discover -s tests` — 126/126 OK.
- Exact lab — 8/8 complete, decision REJECT, 0 errors.
- `.venv/bin/python scripts/trader_income_coverage.py --write` — refreshed 20 structures / 245 hypotheses / 67 evolve artifacts; no living leader.
- Final `py_compile` and `git diff --check` passed; 20 changed/untracked text files scanned with zero credential/private-key pattern hits. Dirty/uncommitted state is intentional for the challenger/finalizer and means this phase is not complete.

## Durable lesson

A direction-aligned CCS did not rescue the daily-bar realized-volatility signal class: expansion plus non-positive return failed every train gate before holdout judgment, mostly on sparse samples, negative after-cost PnL, or drawdown. Do not tune this family on the same synthetic option evidence.

## ONE NEXT SEED

On the next distinct New York RTH market date, append one all-expiration TSLL option observation snapshot and verify archive density advances from 1/3 to 2/3 without duplicating identical rows; do not run provider-backed historical simulation, observed-cost calibration, or L1 claims before 3/3.

## Phase status

Executor residue is ready for Grok challenge. This phase is not RUN COMPLETE and did not commit, push, merge, or invoke deterministic postflight.

MOA_EXEC_DONE

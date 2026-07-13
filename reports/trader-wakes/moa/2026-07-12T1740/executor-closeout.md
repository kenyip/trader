# MoA executor closeout — 2026-07-12T1740

ROLE: GPT 5.6 Sol executor / only writer
PHASE: BUILD / L0
SLEEVE_USD: 3000
PAPER_ONLY: true
PARTIAL_PHASE: true
OUTCOME: FALSIFIED + CAPABILITY

## Choice

One highest-information loop: open a distinct multi-horizon signal boundary instead of repeating the closed adjacent-daily close-shock, momentum, mild-pullback, or volatility families. Prior archive-focused NEXT was superseded because Sunday cannot add a distinct RTH observation date while historical-underlying proxy research remains executable.

Hypothesis: a prior completed bar with `ret_5d <= 0`, `ret_14d >= 3%`, and bullish EMA stack improves 21-DTE defined-risk PCS income after both proxy cost axes.

Falsifier: no symbol passes every expanding rolling-origin fold with an independent train gate, untouched holdout positive SHIP on 5% leg slip and $0.01-per-leg half-spread, one-lot max loss <= $300, holdout/window drawdown <= $75, dense-negative windows <= 5, and exact ledger/signal/no-reentry integrity.

## Result

- Decision: `REJECT_MULTI_HORIZON_TREND_PULLBACK_PCS`.
- Population: BAC, F, SOFI, PLTR, TSLL, SMCI, AMD, AAPL; 8/8 completed, zero errors.
- Rolling origin: 24 folds total; four train gates passed (BAC fold 2, SOFI folds 1/2, PLTR fold 1), but zero complete folds passed untouched holdout.
- The train-pass holdouts failed on density/verdict (BAC n=5; SOFI fold 1 n=9 but NULL), cost/PnL (SOFI fold 2 slip -$1.16), or PnL/drawdown (PLTR fixed -$39.62/DD $118.96; slip -$208.97/DD $214.28).
- Integrity: 286/286 strategy/control/window summaries exact; zero signal violations; zero same-bar reentries.
- Trade shape: 21-DTE put credit spread, defined risk. Across persisted train/holdout cost axes, `capital_fit_usd` $75.30-$225.80, worst observed one-lot `max_loss_usd` $227.19, engine `max_lots=3`; capital posture remains 1 lot. The family is rejected, not a candidate or seat.
- Evidence: `.cache/platform/pcs_trend_pullback_rolling_origin_lab_2026-07-12T1740.json`.

## Capability / validity

- `pcs_sim.entry_filters_pass` now supports fail-closed lagged `ret_5d`, `ret_14d`, and `ema_stack` bounds.
- The experiment found and repaired a generic boundary: configured nonnumeric entry features previously raised `ValueError`; they now reject the entry.
- Selection was predeclared with no grid or holdout-driven tuning. Controls are same-DTE unconditional PCS and a disjoint bearish multi-horizon mirror PCS.
- Historical underlying bars are observed; option marks, listed-Friday/rounded strikes, and both cost axes are proxies. This result is L0 discovery/falsification only and cannot earn L1.
- No living leader exists; absolute risk/evidence gates were used. No hypothesis registration, status transition, readiness B change, paper order, shadow action, broker session, arm, or live action occurred.

## Freedom audit

Symbol freedom remained eight-name and strategy freedom remained open; orientation closed only unchanged evidence families, not symbols or catalog structures. The chosen loop named a genuinely new multi-horizon evidence class.

## Verification

- TDD red: new test initially failed because the lab module did not exist.
- Focused behavioral/boundary/negative/regression suite: 36/36 green.
- `python -m trader_platform.smoke_test`: green, including live fail-closed gate.
- Full unittest discovery: 137/137 green.
- `git diff --check`: green.
- Coverage refreshed: 20 structures / 245 hypotheses / 67 evolve artifacts; no quality leader.
- Initial deterministic preflight reported the expected orchestrator-created orientation/coverage residue; this executor did not discard, stash, or hide it.

## Durable

- Machinery: `trader_platform/research/pcs_sim.py`, `scripts/pcs_trend_pullback_rolling_origin_lab.py`.
- Boundary tests: `tests/test_pcs_trend_pullback_rolling_origin_lab.py`.
- Project truth: `docs/INCOME_STRATEGY_COVERAGE.md` and refreshed income coverage reports.
- Reusable lesson is currently embodied in generic fail-closed code/tests; skill promotion is deferred to finalizer/challenger review to avoid premature duplication.

## Readiness

BUILD/L0 unchanged. No living leader or capital seat. Formal B checks did not change, so `reports/readiness/LATEST.md` was not rewritten in this partial phase.

## NEXT

Build a no-lookahead dividend/ex-date and early-assignment risk boundary for short-call diagonal/debit simulators, with deterministic behavioral/negative tests before any strategy retuning; keep proxy claims L0 and reject dependent results when required event data is absent.

MOA_EXEC_DONE

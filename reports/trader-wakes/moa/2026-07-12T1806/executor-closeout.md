# MOA BUILD executor closeout — 2026-07-12T1806

WAKE: 2026-07-12T1814 PDT (Sunday; market closed)
PHASE: BUILD / L0
SLEEVE: $3,000
ROLE: GPT 5.6 Sol executor (only writer)
PAPER_ONLY: true
OUTCOME: CAPABILITY

## Choice

Built one strategy-free realism boundary for short-call structures rather than repeating a closed daily-bar signal family or attempting the one-date TSLL archive on a weekend. Prior NEXT was useful and executable: diagonal and bull-call debit simulators had no dividend/ex-date or early-assignment handling, while `orientation.json` confirms simulator capability work remains open and `redirect_required=false`.

Hypothesis: an announcement-time-aware dividend event provider plus an ITM-short-call extrinsic-value guard can close diagonal and bull-call debit positions before an ex-date without allowing later announcements to alter earlier bars.

Falsifiers:
- an event with `known_at` after the simulated bar changes that bar;
- required missing provider or date coverage fails open;
- a known dividend that dominates remaining short-call extrinsic leaves the position open;
- dividend logic contaminates the bear-put path.

## Durable delta

- Added `trader_platform/research/corporate_action_risk.py` with typed dividend events, explicit `known_at`, visible-event filtering, and conservative short-call assignment assessment.
- Injected optional/required dividend-event providers into `diagonal_sim` and bull-call `debit_vertical_sim`; required provider/coverage fails closed, assignment-risk exits precede normal profit/loss/DTE exits, and result metrics label corporate-action mode and exit count.
- Kept bear-put debit behavior explicit as `not_applicable_put`; short-put/non-dividend assignment remains unmodeled rather than implied complete.
- Added behavioral/boundary/negative controls in `tests/test_corporate_action_risk.py`: future-announcement non-leakage, provider/coverage/malformed-record fail-close, realized assignment-risk exits in both short-call simulators, and bear-put isolation.
- Updated BUILD and income-coverage doctrine plus the generated coverage surface. No strategy DNA, hypothesis registry, B-check, capital seat, paper ledger, shadow, arm, or live mutation.

## Evidence validity / capital

This is simulator machinery, not strategy edge evidence. The exercised paths use deterministic synthetic bars and Black-Scholes option marks; no observed option surface or historical announcement-time corporate-action provider was supplied. Therefore no B3/B4, L1, candidate, or readiness claim follows.

No living leader exists. Any future trade-shaped diagonal or debit candidate must still state `capital_fit_usd`, one-lot `max_loss_usd`, `max_lots`, structure, dual after-cost evidence, regime windows, and drawdown quality. This executor created no such candidate.

## Verification

- Focused behavioral/boundary/negative-control/regression: `.venv/bin/python -m unittest tests.test_corporate_action_risk tests.test_debit_vertical_sim tests.test_diagonal_oos_stress tests.test_defined_risk_fixed_cost -v` → 13/13 pass.
- Platform smoke: `.venv/bin/python -m trader_platform.smoke_test` → `platform smoke OK`, including agentic-live blocked.
- Full suite: `.venv/bin/python -m unittest discover -s tests` → 143/143 pass.
- Diff hygiene: `git diff --check` → pass.
- Coverage refresh: `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-12T1806` → 20 structures / 245 hypotheses / 67 evolve artifacts; no quality leader.
- An initial broader-test command named nonexistent module `tests.test_defined_risk_fixed_cost_stress` and failed only at unittest import. It was corrected to the real `tests.test_defined_risk_fixed_cost`; the corrected focused suite and full suite are green.

## Freedom audit

Symbol and strategy search remained open; this wake chose cross-simulator capability because it repairs a claim-relevant realism gap without reopening closed proxy families, forcing TSLA/TSLL, or treating plumbing as an edge.

## Readiness

BUILD/L0 unchanged. Formal B checks unchanged. Historical event-provider data, observed option surfaces, non-dividend assignment, B6, B7, funding/options level, and Ken arm remain unresolved. No live/broker/login/order action occurred.

## ONE NEXT SEED

Inventory no-paid historical corporate-action sources for both ex-date and announcement-time provenance; implement an archived `DividendEventProvider` only if `known_at` can be represented honestly, otherwise write a fail-closed data decision packet and keep required-mode diagonal/bull-call simulations blocked rather than backfilling announcement dates from ex-dates.

## Phase status

Executor phase only. Challenger critique, finalizer repair/learning promotion, deterministic commit/integration/push/postflight, and RUN COMPLETE determination remain pending. Do not commit, push, merge, or claim completion here.

MOA_EXEC_DONE

# MOA BUILD executor closeout — 2026-07-13T0515

WAKE: recovery completed 2026-07-13 13:30 PDT
PHASE: BUILD / L0
SLEEVE: $3,000
ROLE: GPT 5.6 Sol recovery executor; only writer; Grok challenger/finalizer/integration pending
OUTCOME: CAPABILITY_ADDED / EXACT_SESSION_TIME_PROXY_SEED_FALSIFIED
PAPER_ONLY: true

## ORIENTATION / CHOICE

The recovery continued the existing `2026-07-13T0515` branch and residue only. It accepted the prior seed because the original executor had already built the new completed-30-minute session-time machinery and had one concrete claim-invalidating timezone failure left. No closed daily-bar or double-diagonal family was reopened. Living leader remains none; BUILD/L0 and the empty capital path remain unchanged.

Hypothesis: for at least one of BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL and one defined-risk PCS/CCS/IC structure, a train-selected open/midday/late entry bucket remains positive, non-vacuous, capital-fit, and bounded on untouched chronological holdout under both 5% adverse leg slip and $0.01 half-spread-per-leg costs.

Falsifier: reject this exact proxy cycle unless both train and holdout independently pass with n>=3, PnL>0, one-lot max loss <=$300, max and window DD <=$75, dense-negative windows <=5, exact ledger, and zero same-bar or same-date/session-bucket reentries.

## DID

- Added `intraday_session_data.py`: New York RTH filtering, open/midday/late buckets, finite OHLCV fail-closed handling, and regime/IV features joined only from the prior completed market date.
- Extended `pcs_sim.py` so `entry_signal_lag_bars` applies to every entry feature, optional session buckets fail closed on invalid values, and a date/session bucket is consumed by either an entry or exit.
- Repaired calendar-DTE marking for timezone-aware intraday timestamps by subtracting local calendar dates rather than tz-naive and tz-aware timestamps. Listed-Friday expiration and calendar-DTE semantics remain unchanged.
- Added a reproducible 8-symbol × 3-structure chronological train-selection/untouched-holdout dual-cost lab and focused behavioral, boundary, and negative-control tests.
- Reran the exact lab and copied the immutable evidence into this MoA directory.
- Refreshed the deterministic 0515 income-coverage copy while restoring the concurrently newer `income-coverage-LATEST.md` unchanged.
- Registered, promoted, placed, armed, or accessed nothing.

## EXACT EVIDENCE / JUDGMENT

Evidence:
- `.cache/platform/pcs_session_time_chronological_lab_2026-07-13T0515.json`
- `reports/trader-wakes/moa/2026-07-13T0515/pcs-session-time-chronological-lab.json`

Result:
- Decision: `REJECT_SESSION_TIME_PROXY_THIS_CYCLE`.
- Population complete: 8/8 symbols, 3/3 structures, 24/24 rows; errors 0.
- Each symbol had 273 completed 30-minute bars over 21 market dates, split chronologically into 12 train and 9 holdout dates (2026-06-11 through 2026-07-13 ET).
- Six rows passed both train cost axes; zero passed the complete conjunctive train+holdout gate.
- Maximum absolute ledger delta across evaluated axes: `1.4210854715202004e-14`.
- Same-bar reentries: 0. Same-date/session-bucket reentries: 0 after the exit-consumes-bucket repair.
- Maximum reported one-lot axis loss: `$224.61`, inside the `$300` hard gate; every trade-shaped row is a defined-risk `put_credit_spread`, `call_credit_spread`, or `iron_condor`, with `capital_fit_usd`/`max_loss_usd` in each axis and `max_lots` reported. Operating posture remains 1 lot.

Decisive holdout examples:
- BAC late PCS: train fixed/5% `+$37.03/+$49.79`; holdout fixed `-$19.44` and 5% `+$11.24` — dual-cost conjunction fails.
- F open CCS: train fixed/5% `+$17.14/+$23.43`; holdout fixed `-$5.31` and 5% `+$4.49` — fails.
- F late IC: train fixed/5% `+$26.97/+$36.93`; holdout `-$38.74/-$14.83` — fails.
- SOFI late PCS: train fixed/5% `+$28.11/+$17.31`; holdout `-$15.81/-$5.68` — fails.
- SOFI late IC: fixed holdout `+$16.34`, but 5% holdout `-$8.45` — fails.
- F midday PCS holdout had only one trade on each cost axis and was negative, so it also fails density and PnL.

Judgment: the exact 21-market-date, 7-DTE, one-point-wide synthetic listed-Friday/rounded-strike Black-Scholes session-time seed is falsified for this cycle. The machinery is useful, but this is underlying-only proxy evidence and cannot earn L1, support observed fills, or justify registration/paper/shadow/live action.

## CLAIM CRITIQUE / BOUNDARIES

- No lookahead: entry regime/IV fields are prior-completed-session values; entry evaluation uses a one-completed-bar lag; holdout is evaluated only after a train bucket passes.
- Calendar semantics: timezone metadata is discarded only after extracting each timestamp's represented local calendar date; expiration selection and remaining DTE stay calendar-day based.
- Costs: 5% adverse leg slip and fixed `$0.01` half-spread per leg are proxy stress axes, not observed bid/ask fills.
- Availability: listed Friday and rounded strikes are synthetic; no historical observed option surface or contract-availability proof is claimed.
- Density: only 21 market dates and nine holdout dates were available. The rejection is exact-seed/cycle scoped, not a universal rejection of session-time PCS/CCS/IC.
- Population/ranking: all 24 requested rows completed with no errors; no mixed strategy families or registry leaders were inserted.
- Capital: defined-risk only, one-lot worst reported axis loss `$224.61`, operating posture 1 lot, sleeve `$3,000`; no capital seat was created.

## VERIFICATION

- Timezone/calendar-DTE regression: `tests.test_pcs_expiry_grid.PcsExpiryGridTest.test_timezone_aware_intraday_marks_use_calendar_dte` → 1/1 OK.
- Focused no-reentry + timezone controls → 2/2 OK.
- Focused behavioral/boundary/negative-control/regression suite: `tests.test_intraday_session_data tests.test_pcs_session_time_chronological_lab tests.test_pcs_expiry_grid` → 22/22 OK.
- Exact lab rerun → 24 completed / 6 train passes / 0 all-axis passes / 0 errors.
- Platform smoke → `platform smoke OK`; `agentic_live` remained blocked at the Stage1 Robinhood OAuth gate.
- Full discovery → 192/192 OK.
- `py_compile`, `git diff --check` → OK.
- Coverage → 21 structures / 245 hypotheses / 67 evolve artifacts / no leader.

## FREEDOM AUDIT

The experiment used the predeclared broad eight-symbol PCS/CCS/IC route because new session-time machinery could change evidence. It imposed no symbol or strategy allowlist, did not reopen closed daily-bar families, and did not convert the proxy result into a capital candidate.

## DURABLE / LESSON

Future Trader now has a runnable completed-30-minute chronological session-time lab with prior-session features, dual costs, complete population accounting, exact ledger checks, and robust timezone/calendar-DTE and no-reentry boundaries. An exit must consume its date/session bucket; tracking entry buckets alone silently permits later same-bucket reentry when the position was opened on an earlier date.

The concurrent 06:30–12:31 RTH wake files and monitor/readiness updates were preserved and are not executor evidence. Their newer `LATEST` surfaces were not overwritten or claimed.

## ONE NEXT SEED

Build an append-safe, provenance-recorded 30-minute underlying archive for the same universe until at least 60 distinct completed market dates are available, then rerun this locked chronological PCS/CCS/IC specification once as a genuinely denser evidence class; do not retune on the nine-date holdout, register, promote, paper, shadow, arm, or live.

## PHASE STATUS

Executor partial phase only. No commit, push, merge, branch switch, postflight, or RUN COMPLETE claim. Grok challenger must critique; finalizer must repair and rerun gates; deterministic wrapper integration remains authoritative.

MOA_EXEC_DONE

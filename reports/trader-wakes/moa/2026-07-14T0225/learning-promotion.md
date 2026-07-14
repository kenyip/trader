## VERIFICATION

Strategy charter/outcome: tested exactly one mutation-free SPY first-completed-session turn-of-month mechanism over the next five sessions, with tenth-session placebo, deterministic weekday-matched session-12-to-17 complement, and chronological 60% train / 40% untouched holdout. Conditional option DNA was one-lot 21-DTE approximately 0.20-delta $1-wide PCS with 50% profit, 2x-credit loss, and mandatory five-session exits, but the predeclared falsifier required every underlying paired-control gate to pass before any pricing. Outcome is `BLOCKER_REMOVED_AND_RETESTED`; retest decision is `FAMILY_CLOSED`; strategy advancement is false; funnel remains `F0_MECHANISM -> F0_MECHANISM`.

Canonical strict-JSON artifact `reports/trader-wakes/moa/2026-07-14T0225/spy-tom-event-study.json` (SHA-256 `fb81bf035093ce0db07c3e4fcf43bba292d1e8f8bf272ac52b8c5b6416842e9c`) contains 126 months, 75 train and 51 untouched-holdout events. Event-minus-complement mean is `-0.0007316349154277522` train and `-0.0023542854031338863` holdout; bootstrap LB90 is negative versus placebo and complement in both partitions; holdout event drawdown frequency at or below -2% is `0.3333333333333333` versus complement `0.2549019607843137`. Population repair retains November 2018 with complement fields serialized as JSON `null`. The underlying gate failed, so `pricing_calls=0`, option status is `NOT_RUN_UNDERLYING_GATE_FAILED`, candidate_pass and registration_eligible are false, and no option PnL was simulated. Structural one-lot bound is `capital_fit_usd=100`, `one_lot_max_loss_usd=100`, `max_lots=1`; this is not an observed fill or seat.

Commands and exact results:

- `.venv/bin/python -m unittest tests.test_spy_turn_of_month_event_study -v` -> `Ran 6 tests in 0.075s`, `OK`. Behavior, population-purity boundary, train-pass/holdout-fail negative control, fail-closed pricing, same-bar volatility shock, and strict-JSON missingness are covered.
- `.venv/bin/python -m unittest discover -s tests` -> `Ran 248 tests in 9.936s`, `OK`.
- `.venv/bin/python -m py_compile scripts/spy_turn_of_month_event_study.py tests/test_spy_turn_of_month_event_study.py` -> exit 0, no output.
- `just platform-smoke` -> `platform smoke OK`; PCS multi-leg risk/ledger/intent path green; `agentic_live` blocked at Stage1 OAuth as required.
- Exact repaired rerun command -> `REJECT_SPY_TOM_CALENDAR_FLOW_FAMILY`, `FAMILY_CLOSED`, underlying_gate_pass false, `NOT_RUN_UNDERLYING_GATE_FAILED`, candidate_pass false, and the same seven failure reasons. Independent assertions confirmed all underlying/option metrics unchanged from executor evidence, strict JSON, 126 months, 75/51 split, November 2018 null complement, and `pricing_calls=0`.
- `.venv/bin/python scripts/trader_income_coverage.py --write` -> 21 structures / 246 hypotheses (`paper:1`, `testing:14`, `candidate:230`, `rejected:1`) / 70 evolve artifacts / no living leader; wrote `income-coverage-LATEST.md` and `income-coverage-2026-07-14T0339.md`; stale pre-regeneration 0225 snapshot removed.
- Schema-v2 handoff validation -> PENDING_FINAL_GATE.
- Non-mutating temporary-index completion `prepare` plus staged secret/path and diff checks -> PENDING_FINAL_GATE.
- Integration is pending the deterministic wrapper gate; no real-index staging, commit, push, merge, branch switch, broker action, paper order, shadow/live promotion, or arm occurred in finalization.

## DURABLE

Challenger reconciliation:

- F1 ACCEPT: preserved `BLOCKER_REMOVED_AND_RETESTED` with retest `FAMILY_CLOSED`, `strategy_advancement.advanced=false`, and F0 to F0. The canonical strategy artifact itself remains `FAMILY_CLOSED`; no advancement is implied.
- F2 ACCEPT: closed `spy-turn-of-month-first-session-5day-pcs-21dte-020delta-1wide-dualcost-60-40-v1`; unchanged and nearby day/DTE/width/symbol/threshold mutants are quarantined.
- F3 ACCEPT/REPAIRED: completed executor-closeout, top-level moa-exec, schema-v2 compounding, this learning artifact, and final surfaces; `hyp_spy_turn_of_month_pcs_21d_020d_1w` now links to tracked canonical JSON rather than ignored cache evidence.
- F4 ACCEPT/REPAIRED: focused verification expanded from challenger 4/4 to final 6/6, and full 248/248 plus compile, smoke, exact artifact, and deterministic handoff checks were required.
- F5 ACCEPT/REPAIRED: `scripts/spy_turn_of_month_event_study.py` shifts its 30-session volatility estimate one completed bar; `tests/test_spy_turn_of_month_event_study.py` proves a same-entry-bar shock cannot alter the entry value and verifies the first-valid boundary.
- F6 ACCEPT/REPAIRED: final merge, LATEST, INDEX, readiness, and regenerated coverage agree on family close, 246 hypotheses with one rejected audit, no leader, and the reassessment NEXT.
- F7 ACCEPT: merged NEXT bans TOM mutants and nearby options-filter volume under the search-burst stop.
- Finalizer finding REPAIRED: unavailable complement values previously emitted Python `NaN`; canonical evidence now normalizes to strict JSON `null`, writes with `allow_nan=False`, and has a direct November 2018 test. Exact rerun preserved the strategy decision.

Dated project truth is durable in the canonical JSON, rejected hypothesis audit, executor/merge/LATEST/INDEX, readiness, regenerated income coverage, `compounding.json`, and this report. Reusable procedure was promoted to profile skill `trader-self-evolution`: audit checked-in dormant branches even when outcome gating keeps them uncalled; lag entry features to completed data, test same-bar-shock/first-valid boundaries, require strict JSON null missingness, and rerun the unchanged dependent experiment. Profile memory was intentionally not changed because this is procedure plus dated outcome, not a stable Ken preference or routing fact. Superseded ignored event JSON and stale 0225 coverage snapshot were removed only after tracked canonical evidence and regenerated coverage existed.

## LESSON

Future Trader can now falsify a calendar-flow story without mistaking raw positive drift for a specific edge: the event must beat deterministic placebo and weekday-matched complement controls robustly in both train and untouched holdout, and a dead underlying gate must prevent option-proxy rescue. Future Trader also treats dormant reusable code as evidence-bearing machinery: outcome gating does not excuse a same-bar feature, and Python-readable `NaN` is not durable strict JSON. The repairs did not rescue this strategy; they made the unchanged family close population-pure, chronology-safe, portable, and auditable.

## NEXT

`SEARCH_DESIGN_REASSESSMENT_AFTER_TOM_CLOSE`: inventory remaining open, non-quarantined economic mechanisms and select exactly one materially distinct mechanism whose first discriminating test uses outcome-independent underlying labels, deterministic placebo/complement controls, and chronological train-to-untouched-holdout evaluation before option pricing. If no materially novel mechanism can be stated from executable evidence, stop and redesign the search/data plan rather than buy familiar PCS volume. Do not reopen TOM day/DTE/width/symbol mutants or nearby options-filter volume; remain BUILD/L0 with no paper/shadow/arm/live/broker/funding action.

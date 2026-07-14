# MOA BUILD challenger critique — 2026-07-14T0225

ROLE: Grok 4.5 challenger / read-only judgment
PHASE: BUILD / L0 adjusted-underlying + conditional BS proxy (not reached)
SLEEVE_USD: 3000
INTEGRATION: partial critique phase only — no commit, push, merge, broker, shadow/live, arm, or evolve --apply

## Read set

- `docs/BUILD_LAB_ENVIRONMENT.md`
- `docs/INCOME_STRATEGY_COVERAGE.md`
- skill `trader-self-evolution`
- `reports/trader-wakes/moa/2026-07-14T0225/meta.json`
- `reports/trader-wakes/moa/2026-07-14T0225/orientation.json`
- `reports/trader-wakes/moa/2026-07-14T0225/executor-closeout.md` (charter only; still says pending)
- `reports/trader-wakes/moa/2026-07-14T0225/executor-session.log` (terminal summary + tool residue)
- `reports/readiness/income-coverage-LATEST.md` / `income-coverage-2026-07-14T0225.md`
- `reports/readiness/LATEST.md` (top NEXT still 0053 evidence pivot)
- `.cache/platform/spy_tom_event_study_2026-07-14T0225.json`
- `.cache/platform/spy_tom_adjusted_20160101_20260714.csv` (via provenance)
- `scripts/spy_turn_of_month_event_study.py`
- `tests/test_spy_turn_of_month_event_study.py`
- `trader_platform/data/hypotheses.yaml` tail (`hyp_spy_turn_of_month_pcs_21d_020d_1w`)

Read-only / inspect actions: Python artifact recompute, unittest focused suite (4/4 OK). No registry mutation, no evolve --apply, no broker.

## Overall judgment

PASS / ACCEPT WITH FINALIZER REPAIRS (executor phase incomplete).

The wake chose the authorized search-design pivot after a 16-wake no-advance streak and closed one genuinely new calendar-flow mechanism with leakage-safe, outcome-independent underlying gates. The exact first-session SPY turn-of-month 5-session effect failed chronological train and untouched-holdout paired controls; conditional option pricing correctly did not run (`pricing_calls=0`). That is honest `FAMILY_CLOSED` strategy information, not a paper-testable candidate and not closer to a living edge.

Strategy advancement: false. Funnel stays `F0_MECHANISM -> F0_MECHANISM`. Living leader remains none. Capital path remains empty. No L1, paper, shadow, arm, broker, or live claim is supported.

Executor hit the tool-call ceiling before required residue (final closeout, moa-exec.md, LATEST/INDEX, full suite, compounding handoff). Finalizer must complete operational closeout without reopening the closed family or overstating progress.

## Rubric

1. Strategy charter: PASS — economic mechanism (BOM allocation/payroll flow → 5-session bullish SPY drift), candidate `SPY_TOM_PCS_21D_020D_1W`, funnel target F2 only if underlying gates pass, predeclared dual-control falsifier, mutation ban, and exact close boundary are explicit in executor-closeout charter.
2. Strategy vs operations: PASS — event-study tooling is search machinery; the strategy decision is the underlying fail-closed family close. Mid-wake population-purity repair (Nov-2018 complement-impossible month retained) plus retest is claim-relevant, not capability-only theater.
3. Goal progress: PASS — no candidate advanced, but a new mechanism class was decisively falsified with discriminating evidence and the option stack was not allowed to launder a failed underlying effect. Informative-but-not-closer; no-advance streak continues (17 once this run integrates).
4. Creativity and independence: PASS — SPY calendar-flow event study is materially distinct from closed technical-state, gap-recovery, session-time, free-pop, and vol-filter families; prior NEXT was accepted with independent orientation under `strategy_pivot_required` / `strategy_burst_stop_required`, not habit tunneling into TSLA/TSLL PCS.
5. Claim validity: PASS — claims limited to adjusted SPY underlying event evidence; option stage status `NOT_RUN_UNDERLYING_GATE_FAILED`; BUILD/L0; registration_eligible false; no L1. Observed-option archive blockage was not used to freeze this independent historical route.
6. Evidence and test quality: PASS-WITH-NITS — real artifact + focused tests exist and metrics recompute; full suite / moa-exec / final closeout missing because of executor ceiling. Focused tests cover calendar labeling/disjointness, post-close MAE, complement-unavailable retention, conjunctive train∧holdout gates, and fail-closed option stage + capital DNA bounds.
7. Falsification: PASS — train and holdout both `gate_pass=false`; dominant failure is lack of specificity vs weekday-matched complement (mean excess already negative) plus non-robust bootstrap excess vs placebo; quarantine stated; no mutation rescue.
8. Capital honesty: PASS — no seat; structural one-lot $1-wide PCS bound `capital_fit_usd=100`, `one_lot_max_loss_usd=100`, `max_lots=1` labeled as structural upper bound before credit / not observed fill; leader remains none; former `b195f5fe` not resurrected.
9. Research freedom: PASS — free symbol/strategy lane used for a new mechanism; blocked observed-option path correctly treated as irrelevant until underlying survived. No red-lane action.
10. ONE highest-information NEXT seed: PASS — see merged seed; no live/shadow promotion; do not reopen TOM day/DTE/width/symbol mutants.

## Artifact checks (independent)

Canonical JSON: `.cache/platform/spy_tom_event_study_2026-07-14T0225.json`

- SHA-256: `3ff867f453d1bf87777a55075b97beab1037074336b04ad4f918d41e8fa2ad98`
- Adjusted data SHA-256: `f15bfd1830d86085bb9159ffb4bd0ccbb1f6b7f92254b9852314b1a0b23d35e7` (2645 rows, 2016-01-04 → 2026-07-13, yfinance auto_adjust=true)
- Decision: `REJECT_SPY_TOM_CALENDAR_FLOW_FAMILY`
- strategy_outcome: `FAMILY_CLOSED`
- candidate_pass: false; registration_eligible: false
- Funnel: `F0_MECHANISM -> F0_MECHANISM`
- Monthly population: 126 unique sorted months (2016-01 … 2026-06); only 2018-11 lacks weekday-matched complement (retained with `complement_available=false`)
- Train (75 events, 2016-01…2022-03): event mean +0.520%, median +0.629%, positive freq 68%; excess vs placebo mean +0.424% but bootstrap LB90 −0.142%; excess vs complement mean −0.073%, bootstrap LB90 −0.655%; gate_pass false
- Holdout (51 events, 2022-04…2026-06): event mean +0.169%, median +0.398%; excess vs placebo mean +0.267% but bootstrap LB90 −0.198%; excess vs complement mean −0.235%, bootstrap LB90 −0.843%; holdout ≥2% drawdown 33.3% vs complement 25.5% (matched-event 33.3%); gate_pass false
- option_stage: `pricing_calls=0`, status `NOT_RUN_UNDERLYING_GATE_FAILED`
- Independent recompute of partition means/excess matches artifact

Focused verification re-run by challenger:

- `.venv/bin/python -m unittest tests.test_spy_turn_of_month_event_study -v` → **4/4 OK**

## Findings for finalizer

F1 — ACCEPT strategy close; ALIGN outcome label.
- Disposition: treat the wake as a decisive family close of the SPY first-session TOM 5-session calendar-flow mechanism. Preferred schema-v2: `outcome=BLOCKER_REMOVED_AND_RETESTED` with `retest_decision=FAMILY_CLOSED` because the Nov-2018 silent month-drop was claim-invalidating population purity and was repaired then retested in-wake (same pattern as 0053). Accept bare `FAMILY_CLOSED` only if compounding cannot carry retest_decision, but do not claim STRATEGY_ADVANCED.
- advanced=false; funnel F0→F0; decision key `REJECT_SPY_TOM_CALENDAR_FLOW_FAMILY`.

F2 — ACCEPT exact family quarantine.
- Closed-family / novelty keys to record (use both for search):
  - `spy-first-session-tom-5session-v1` (notes quarantine_key)
  - `spy-turn-of-month-first-session-5day-pcs-21dte-020delta-1wide-dualcost-60-40-v1` (artifact hypothesis_id)
  - long novelty: `spy-tom-calendar-flow-first-session-5s-underlying-placebo10-weekday-complement12-17-60-40-reject-v1`
- Unchanged reruns and nearby mutants (other BOM day, other hold length, other index ETF, width/DTE knobs, “last session of month” without a new mechanism statement) are thrash.

F3 — REQUIRED residue completion (executor incomplete).
- Finalize `executor-closeout.md` (still says pending).
- Write `reports/trader-wakes/2026-07-14T0225-moa-exec.md`.
- Write schema-v2 `compounding.json` + `learning-promotion.md`.
- Update LATEST/INDEX (challenger writes merge surfaces below; finalizer owns exec/learning/verification completion).
- Fix hyp `evidence_links` pointing at missing moa-exec.md; keep status `rejected` / null_results; do not promote.
- Align quarantine_key strings between hyp notes and artifact hypothesis_id in one durable place.

F4 — REQUIRED verification completion.
- Re-run focused suite; run full unittest discovery + platform-smoke + compile of new modules.
- Do not weaken gates or retune DNA to force a pass.

F5 — GUARD: dormant option-stage vol lookahead.
- `_option_feature_frame` builds `iv_proxy` from a same-bar-inclusive rolling return. Option stage did not run this wake, so it does not invalidate the FAMILY_CLOSED claim. If any future mechanism reuses this path, lag completed-bar IV (min_periods + shift) before pricing; add a boundary test.

F6 — READINESS NEXT patch.
- Current readiness top NEXT still describes the 0053 evidence pivot that this wake already executed. Patch ONE NEXT to the merged seed below; leave B-checks, living leader none, BUILD/L0, capital path empty.

F7 — NEXT after 17 no-advance.
- Do not buy more TOM/options-filter volume. Prefer a search-design reassessment that names one remaining open economic-mechanism class with an outcome-independent underlying pre-screen, or stop the burst if no such class can be stated with a discriminating falsifier.

## Non-findings / no repair requested

- No live, broker, shadow, arm, funding, or paper-order action in cited residue.
- No L1 / capital-seat / living-leader claim.
- Option pricing did not rescue a failed underlying effect.
- Adjusted SPY provenance is labeled; claim scope correctly excludes L1.
- Complementary control construction and post-close MAE (lows after entry close) are sound for the underlying claim.
- Registering a `rejected` hyp with null_results is audit-appropriate once evidence_links resolve; not a promotion.

## Challenger verdict

`PASS_ACCEPTED_FOR_FINALIZER`

Finalizer repairs incomplete executor residue, preserves the family close, runs full verification, promotes learning, and hands off to the deterministic gate. This challenger phase remains partial by design — not RUN COMPLETE.

# MOA BUILD executor closeout — 2026-07-15T1515

PHASE: BUILD / L0 discovery
SLEEVE_USD: 3000
ROLE: GPT 5.6 Sol executor; only writer
SESSION: postclose
PAPER_ONLY: true
OUTCOME: `BLOCKER_REMOVED_AND_RETESTED`
RETEST DECISION: `STRATEGY_ADVANCED`
STRATEGY ADVANCEMENT: true; `F0_MECHANISM -> F1_TRAIN` only

## Strategy decision charter

- Economic edge mechanism: gradual information diffusion and trend-following demand may create ten-session continuation after a completed close at least 2% above the prior completed 20-session high while above a fully warmed prior-completed SMA100.
- Candidate/family: `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` / `TIME_SERIES_20D_BREAKOUT_CONTINUATION`; fixed AAPL/MSFT/NVDA/AMZN/META/GOOGL/AMD/TSLA panel; next-session entry; ten-session outcome; earlier same-symbol near-high controls matched prior-only and without replacement on 20-session return, HV20, and calendar distance; pair windows non-overlapping per symbol.
- Funnel before: `F0_MECHANISM`.
- Exact wake decision: `BLOCKER_REMOVED_AND_RETESTED`. The blocker was the prior epoch's mandatory three-wake no-advance burst stop. The repair was an explicit search-design reassessment and new epoch plus a materially different within-symbol event-study capability. The same wake then exercised the frozen strategy test.
- Predeclared falsifier: on the chronological first 60% of frozen matched pairs, fewer than 80 pairs or 6 represented symbols; non-positive treated mean after labeled 20-bps underlying round-trip sensitivity; non-positive paired excess; non-positive one-sided 90% circular five-pair-block bootstrap lower bound; or any chronology, overlap, reuse, or match-bound violation.
- Claim boundary: a pass advances only F0→F1 / L0 underlying discovery. It cannot establish option mispricing, option after-cost edge, L1, a capital seat, paper eligibility, or real-account readiness.

Charter: `reports/trader-wakes/moa/2026-07-15T1515/strategy-decision-charter.md`.
Reassessment: `docs/SEARCH_DESIGN_REASSESSMENT_2026-07-15T1515.md`.
Active epoch: `2026-07-15-time-series-breakout-payoff`, started by this wake.

## Closed decision

The repair succeeded and the retest advanced the named candidate to `F1_TRAIN/L0` under the predeclared pooled discovery gate.

Canonical evidence: `.cache/platform/breakout_continuation_train_2026-07-15T1515.json`.

- Common adjusted-close panel: 2,646 complete inner-joined rows, 2016-01-04 through 2026-07-14; yfinance `auto_adjust=True`; no forward fill; per-symbol paths and SHA-256 values embedded.
- Outcome-independent matched population: 281 blueprints.
- Train inspected: 168 pairs across all eight symbols.
- Untouched reserve: 113 blueprints, first treated signal 2022-03-24, last treated exit 2026-06-12; `outcome_metrics_read=false`, `simulation_run=false`.
- Treated mean after labeled 20-bps underlying round-trip sensitivity: +1.6318%.
- Earlier same-symbol control mean after the same sensitivity: +0.0785%.
- Paired excess mean: +1.5533%; median +0.7212%; positive frequency 52.98%.
- One-sided 90% circular five-pair-block bootstrap lower bound: +0.2947% from 10,000 samples.
- Pair counts by symbol: AAPL 24, AMD 27, AMZN 18, GOOGL 18, META 14, MSFT 18, NVDA 25, TSLA 24.
- All six frozen train checks passed; `integrity_violations=[]`.
- Option stage did not run: `pricing_calls=0`, option-mark provenance `null`.

There is no living readiness leader and no capital seat. This F1 train signal is compared against the absolute discovery gates only; historical candidates are context, not seats.

## Layered Edge Stack

- Market/underlying: fixed present-day liquid panel AAPL, MSFT, NVDA, AMZN, META, GOOGL, AMD, TSLA. Population rows are internally complete, but the panel is explicitly survivorship/listing biased and cannot support broad generalization.
- Forecast type: `direction_up` over ten sessions.
- Economic mechanism: gradual information diffusion plus trend-following demand after an unusually strong completed-bar breakout in an established uptrend.
- Option structure: conditional one-lot 14-DTE $1-wide bull-call debit spread; not priced or simulated in this wake.
- Intended Greeks: positive delta and bounded positive gamma.
- Dangerous Greeks: theta decay if continuation stalls, long-vega exposure, pin/liquidity/assignment risk, and option-fill friction not represented by adjusted-close outcomes.
- Regime envelope: signal close above fully warmed prior-completed SMA100 and at least 2% above the prior completed 20-session high.
- Entry trigger: next session after the completed-bar signal.
- Exit/management to test later: 50% of maximum spread value profit harvest, thesis invalidation if close returns below the pre-breakout 20-session high, hard ten-session time stop, no same-bar re-entry.
- Risk/capital: `capital_fit_usd=100`; one-lot `max_loss_usd=100` structural width bound before closing friction; `max_lots=1`; one correlated breakout risk unit across the sleeve.
- Evidence/falsifier: passed the frozen pooled train gate above; untouched holdout and option-payoff evidence remain absent.
- Confidence stage: `F1_TRAIN/L0`.
- Stand aside: no qualifying completed-bar breakout, weak trend, failed holdout, or future option package loss/cost outside the one-lot bound.

## Evidence challenge and claim narrowing

Post-gate concentration diagnostics are stored at `.cache/platform/breakout_continuation_train_2026-07-15T1515_audit.json`; they are diagnostics, not a retroactive gate.

- Per-symbol paired means were negative for MSFT (-0.2971%) and NVDA (-0.5915%), while TSLA (+4.5906%) and AAPL (+2.5895%) were strongest. Therefore the F1 claim is pooled-panel, not universal by symbol.
- Leave-one-symbol-out pooled means stayed positive in all eight exclusions, but the bootstrap lower bound became negative when TSLA was excluded (-0.1719%). The pooled train signal is not independent of TSLA contribution.
- Chronological train tertile 1 had mean -0.2966% / LB90 -2.3267%; tertile 2 +2.9733% / +1.1346%; tertile 3 +1.9832% / -0.3475%. The signal is not temporally uniform.
- Prior-only controls reduce same-symbol identity confounding but do not eliminate time-varying macro-regime confounding. The holdout must retain the exact frozen population and report temporal/symbol concentration before any option test.
- The 20-bps label is an underlying-return sensitivity, not option execution cost. Paired excess is unchanged by symmetric sensitivity; no option after-cost claim exists.
- A second cache-backed run reproduced 168/113 and the same decision; all substantive values matched within 1e-12 after excluding `generated_at`. CSV round-trip created only sub-1e-12 float representation differences.

These caveats prevent overclaim but do not override the predeclared pooled F0→F1 discovery gate after inspection.

## Search information versus strategy progress

Search information:

- The prior three-wake burst stop was repaired by a written reassessment and a new epoch, rather than ignored or counter-reset inside the exhausted epoch.
- New deterministic machinery provides lagged breakout/trend features, prior-only same-symbol matched controls, no-reuse/non-overlap checks, strict chronology, labeled underlying cost sensitivity, circular block-bootstrap gating, unread-holdout payloads, zero-support strict-null handling, and direct CLI execution.
- Seven focused behavioral/boundary/negative-control tests and adjacent event-study regressions cover selection leakage, positive gates, bootstrap rejection, malformed data, vacuous support, strict JSON, capital/stack labels, and holdout/option boundaries.

Strategy progress:

- `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` advances from F0 to F1 under L0 discovery only.
- It is not registered, seated, priced, paper-promoted, or made readiness/live eligible.
- The new epoch no-advance streak is 0. The prior epoch's three-wake close remains historical and its families remain quarantined.

Freedom audit: Trader superseded the prior burst-stop NEXT only by completing the required reassessment first, then autonomously chose a materially different within-symbol breakout-continuation mechanism; no caller axis, structure allowlist, stale leader, TSLA habit, or observed-option blockage dictated the choice.

## Readiness / authority

- Phase remains BUILD/L0.
- Living leader remains none; capital path remains empty.
- Formal B checks are unchanged; F1 underlying discovery is not a B-check pass.
- No hypothesis registry write, L1, capital seat, paper order, shadow transition, funding, broker session, arm, or live action.
- `reports/readiness/LATEST.md` is updated only to record the new epoch and narrow F1 train signal while preserving all authority gates.

## Verification

- Focused suite: `.venv/bin/python -m unittest tests.test_breakout_continuation_train_lab -v` -> 7/7 `OK`.
- Focused plus adjacent regressions: breakout + low-HV + TSLL tracking + monthly OPEX -> 28/28 `OK`.
- Changed-file compile -> exit 0.
- Exact experiment -> retest decision `STRATEGY_ADVANCED`; train 168; holdout 113 unread; option pricing 0.
- Cache-backed substantive reproduction -> no differences beyond absolute/relative tolerance 1e-12 after excluding `generated_at`.
- Full suite: `.venv/bin/python -m unittest discover -s tests` -> 311/311 `OK`.
- Platform smoke: `platform smoke OK`; `agentic_live` remained blocked.
- Coverage refresh: 21 catalog structures / 246 hypotheses / 70 evolve artifacts; living leader none; wrote `reports/readiness/income-coverage-2026-07-15T1532.md` and LATEST.
- Final diff, secret-residue, and partial-phase status checks are recorded in the companion executor wake report.

## Exactly one next seed

`BREAKOUT_UNTOUCHED_HOLDOUT_ONCE`: build a fail-closed validator that reconstructs the exact frozen 281 blueprints, selects the reserved final 113 without retuning, reads those outcomes exactly once, and closes `F2_UNTOUCHED_HOLDOUT` as advance-or-family-close under a predeclared pooled after-cost/excess/bootstrap gate while reporting temporal tertiles and symbol concentration. Do not price options unless that untouched holdout advances; do not alter the signal, match bounds, panel, horizon, or cost label.

## Phase boundary

Executor evidence is partial. Grok 4.5 challenge, GPT 5.6 Sol finalization, deterministic staging/commit/integration/push, origin/main equality, clean-tree proof, and the completion receipt remain required. No commit, push, merge, broker action, or `RUN COMPLETE` claim occurred.

MOA_EXEC_DONE

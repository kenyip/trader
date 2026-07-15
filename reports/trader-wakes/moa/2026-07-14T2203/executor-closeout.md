# MOA BUILD executor closeout — 2026-07-14T2203

PHASE: BUILD / research only
SLEEVE_USD: 3000
ROLE: GPT 5.6 Sol executor; only writer; challenger/finalizer/integration pending
PAPER_ONLY: true

## Strategy decision charter

ECONOMIC EDGE MECHANISM: In bullish/neutral regimes, a one-lot 45-DTE put-credit spread entered only on Monday may harvest the favorable early theta segment while avoiding late-cycle gamma/tail exposure when closed at 21 DTE. The causal control is the identical spread held to a 5-DTE calendar stop.

CANDIDATE/FAMILY SCOPE: Fixed-DNA 45-DTE / approximately 0.20-delta / `$1`-wide Monday PCS with 21-DTE stop across BAC, F, SOFI, PLTR, TSLL, SMCI, AMD, and AAPL; one train-ranked survivor only. This is distinct from the closed BAC Friday 7-DTE path and closed daily signal-entry families.

FUNNEL: `F0_MECHANISM -> F0_MECHANISM`.

PREDECLARED FALSIFIER: Close if no symbol's chronological first 60% has at least eight trades on both labeled proxy-cost axes, positive PnL on both, exact ledger/no-same-bar integrity, one-lot max loss <=`$300`, and early-exit worst-axis PnL strictly above the otherwise-identical 5-DTE-stop control; qualifying pooled worst-axis PnL also had to be positive. Otherwise the top train row would advance to L0/proxy `F1_TRAIN`. The final 40% stayed untouched.

EXACT OUTCOME: `FAMILY_CLOSED`.
STRATEGY ADVANCEMENT: false.

## Why this loop

The active `2026-07-14-reassess` epoch supersedes the prior-epoch burst stop; orientation had zero completed epoch wakes and no pivot/stop signal. The reassessment explicitly left simple-entry time-decay management mechanisms open. This bounded train-only comparison used existing PCS machinery, did not reopen a closed family, and could either produce the epoch's first discovery-bar F1 candidate or close one genuinely new timing mechanism without spending the untouched holdout.

## Closed outcome

Executor evidence SHA-256 was `831c007eb7b07cc6c0bdc67a87f45cb69237c869067a72450ec99f591edb8587`. Finalizer regenerated `reports/trader-wakes/moa/2026-07-14T2203/pcs-early-exit-train.json` after the accepted operating/theoretical-lot label repair; canonical SHA-256 is `39113fe2aa6fa071a09902470fad3e39a30cf765a2dfdf32e1d42986a9c6446e`, with strategy metrics and `FAMILY_CLOSED` unchanged.

- Eight of eight symbols completed; errors `0`; population pure; ranking complete; registry writes `false`.
- Every 5% adverse-leg-slip train row was non-vacuous but negative: `n=22..42`, PnL `-$750.97..-$85.95`, max DD `$103.09..$730.03`.
- Fixed `$0.01` half-spread-per-leg rows were `n=22..42`; seven of eight were negative. AAPL alone was positive at `+$128.60`, but its 5% axis was `-$470.44`, so it failed the dual-cost discovery bar.
- Only one symbol had early-exit worst-axis PnL strictly above the control, and that worst axis was still negative. `n_discovery_pass=0`; pooled qualifying PnL is therefore `0` by empty set, not evidence.
- Candidate calendar-stop exits occurred 17 times across the 16 symbol/cost rows versus one control calendar-stop exit. The 21-DTE mechanism was exercised, but profit-target, regime-flip, and delta exits usually occurred first; it did not create positive after-cost expectancy.
- Exact ledger/signal/no-same-bar integrity was true for all 32 candidate/control cost rows. Train/holdout boundaries are strictly chronological; no holdout simulation or metric was used.
- Structure: `put_credit_spread`; observed one-lot `capital_fit_usd` and `max_loss_usd` range `$85.76..$235.43`; operating `max_lots=1`. Every row fits the `$3,000` sleeve and the `$300` one-lot loss cap, but capital fit does not rescue negative expectancy.
- Dominant failure mechanism: cost-adjusted expectancy, not funding. The 5% axis was negative on all eight names, fixed cost was negative on seven, and all candidate DD values exceeded the `$75` capital-seat bar. The claim closes at F0 before any untouched holdout, L1, or paper claim.

Closed family ID: `pcs-monday-45dte-exit21-vs-exit5-train-proxy`. Unchanged reruns, nearby stop nudges, and symbol cherry-picking are quarantined.

## Search information, separate from strategy advancement

1. Added `scripts/pcs_early_exit_train_lab.py`: fixed candidate/control DNA, chronological 60/40 partitioning, train-only rank, dual labeled proxy costs, one-lot risk fields, strict JSON, and no registry mutation.
2. Added `tests/test_pcs_early_exit_train_lab.py` with behavioral and boundary checks for candidate/control purity, dual-cost/non-vacuity/integrity/capital/control gates, train-only ranking, and persisted proof that the calendar stop was exercised.
3. After the first run, added management diagnostics (`avg_days_held`, exit reasons, stop-exit counts) and exact-reran the unchanged experiment. During final evidence critique, strengthened the gate to fail closed when either control cost row is not OK, non-vacuous, or exact; its negative controls failed before implementation and passed after it.
4. Exact-ran the dependent experiment again after that gate repair. Decision remained `FAMILY_CLOSED`, and a second full run was substantively identical after excluding only `generated_at`.

No strategy advanced. Tooling and green tests are search information only.

## Evidence validity audit

- Leakage/lookahead: entry uses no custom outcome feature; only Monday and the simulator's contemporaneous regime/IV state. Candidate selection and ranking read the chronological first 60% only. Final 40% boundaries are recorded but not simulated.
- Control purity: candidate and control configs differ only at `dte_stop` (`21` versus `5`); same symbol, entry weekday, DTE, delta, width, credit floor, exits, costs, and train partition.
- Cost/fill semantics: 5% adverse leg slip and fixed `$0.01` per-leg half-spread are labeled Black-Scholes sensitivities, not observed fills. They can support L0 falsification only.
- Contract availability: listed-Friday/rounded-strike synthetic mode; no broad observed historical option surface. Proxy result cannot earn L1.
- Density/population/ranking: all eight fixed outcome-rank-free names completed; each axis was non-vacuous; no holdout or symbol cherry-pick; ranking complete.
- Path/risk: exact ledgers, no same-bar re-entry, max loss reported from observed train trades. All candidate DDs exceed `$75`, but that capital-seat failure is secondary to the discovery-bar dual-cost PnL failure.
- Stale leader/labels: living leader remains none; historical `b195f5fe` is not a seat. No hypothesis status or readiness label changed.

## Verification

- Focused behavioral/boundary/negative-control/regression suite: 36 tests in 0.539s — `OK` (`test_pcs_early_exit_train_lab`, expiry grid, time-bias, momentum walk-forward, gap-recovery).
- New focused test file: 4/4 — `OK`; RED was observed before each new lab capability was implemented.
- Changed-file compile: exit 0.
- Exact experiment reproduction: `SUBSTANTIVE_REPRODUCTION_OK` after excluding only `generated_at`; asserts 8/8, 0 passes, chronology, max loss, all-slip-negative, and exercised calendar stop.
- Platform smoke: `platform smoke OK`; live remained blocked.
- Full suite: 268 tests in 12.845s — `OK`.
- Coverage refresh: `.venv/bin/python scripts/trader_income_coverage.py --write`; 21 structures / 246 hypotheses / 70 evolve artifacts / no quality leader.

## Readiness and authority

BUILD/L0 remains unchanged. No living candidate or quality leader exists. B1-B7 did not advance; B6 remains thin. Registry stays 246 total (`paper=1`, `testing=14`, `candidate=230`, `rejected=1`). No paper order, shadow/live promotion, broker login, funding, spend, arm, or main-account action occurred.

If accepted and integrated, this is epoch wake 1 without advancement; epoch no-advance streak becomes 1, so neither pivot nor burst-stop is yet required.

## Freedom audit

Symbol and strategy freedom remained intact. Trader autonomously selected a materially distinct open time-management mechanism; no caller slot, prior NEXT, TSLA/TSLL preference, plumbing, or allowlist dictated the loop.

## Search information vs strategy advancement

SEARCH INFORMATION: one new fixed-DNA early-theta/gamma-avoidance mechanism was decisively falsified on train before spending holdout; a reusable train-only causal-management comparator and its negative controls now exist.

STRATEGY ADVANCEMENT: none; `F0_MECHANISM -> F0_MECHANISM`; no F1/F2/F3/F4 movement.

## Next seed

Build and run one lagged monthly cross-sectional low-realized-volatility pre-screen over a fixed liquid universe: rank only on prior completed 60-session HV, compare bottom-quartile forward returns with same-date top-quartile controls, use chronological train then untouched holdout, and reach option marks only if the underlying mechanism advances. This is a new cross-sectional evidence class, not another PCS entry/exit-stop nudge.

Executor phase only. Do not commit, push, merge, or claim RUN COMPLETE. Challenger/finalizer/deterministic integration remain pending.

MOA_EXEC_DONE

# Strategy decision charter — 2026-07-15T1606

PHASE: BUILD / L0 discovery
SLEEVE_USD: 3000
ROLE: GPT 5.6 Sol executor; only writer
SESSION: postclose

## One chosen loop

Open the reserved untouched holdout exactly once for the already-frozen `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` candidate. Reconstruct the exact 281 outcome-independent blueprints from the unchanged data/config, prove the first 168 identities reproduce the prior train population and the final 113 remain the reserved partition, evaluate only those 113 under the unchanged pooled discovery gate, report predeclared concentration diagnostics as non-gating context, and close the family as either `STRATEGY_ADVANCED` F1→F2 or `FAMILY_CLOSED` F1→F1.

This follows the active epoch success definition and is higher-information than a new search: the train signal already advanced to F1, the one-shot holdout is now the only claim-appropriate test, and retuning or opening a different family would waste the reserved evidence.

## Layered Edge Stack

- Candidate ID: `MULTINAME_BREAKOUT_BULL_CALL_14D_V1`.
- Structure family: conditional `bull_call_debit_spread` expression; options remain unpriced unless the underlying holdout first advances.
- Market / underlying: frozen AAPL, MSFT, NVDA, AMZN, META, GOOGL, AMD, TSLA adjusted-close panel, requested 2016-01-01 through end-exclusive 2026-07-15. The panel is liquid but fixed-present-day and explicitly survivorship/listing biased.
- Forecast type: `direction_up` over ten sessions.
- Economic mechanism: gradual information diffusion and trend-following demand may cause a completed close at least 2% above the prior completed 20-session high, while above a fully warmed prior-completed SMA100, to continue upward over the next ten sessions relative to earlier same-symbol near-high non-breakout controls.
- Option structure: if F2 survives, a future one-lot 14-DTE $1-wide bull-call debit spread is the bounded positive-delta expression. This wake does not claim option mispricing, payoff capture, fills, or cost survival.
- Intended Greek exposure: positive delta and bounded positive gamma.
- Dangerous unintended Greek/execution exposure: theta decay if continuation stalls, long vega, pin/liquidity/assignment risk, and multi-leg bid/ask friction; none is measured by this underlying-only test.
- Regime envelope: completed-bar breakout in a positive fully warmed SMA100 trend. Weak/nonpositive trend, no breakout, failed holdout, or future package risk/cost outside the one-lot bound requires stand-aside.
- Entry trigger: next session after the completed close is at least 1.02 times the prior completed 20-session high and above the prior completed SMA100.
- Exit / management: measured evidence is only the fixed ten-session underlying exit. A future option plan may test 50% of maximum spread value, invalidation below the pre-breakout 20-session high, and a hard ten-session stop; those managed exits are not simulated here.
- Risk / capital fit: `capital_fit_usd=100`, structural one-lot `max_loss_usd=100` before closing friction, `max_lots=1`, and at most one correlated breakout risk unit across the sleeve. These are structural future bounds, not an observed paid debit or L1 evidence.
- Portfolio overlap: no concurrent same-cluster breakout positions; one global breakout risk unit.
- Mispricing claim: none. The wake tests only underlying directional continuation.
- Evidence before: pooled train 168/281 blueprints, all eight symbols, +1.5533% paired excess and +0.2947% one-sided LB90 under the labeled symmetric 20-bps absolute-level underlying sensitivity; final 113 reserved and outcome-unread; option pricing calls zero.
- Confidence before: `F1_TRAIN/L0`; discovery bar only; no living leader or capital seat.
- Stand-aside: no qualifying lag-safe breakout, failed exact-population reproduction, any chronology/reuse/overlap/match-bound violation, any pooled holdout gate failure, or later option loss/cost outside the bound.

## Predeclared one-shot holdout falsifier

The exact family closes without option pricing if any of the following occurs on the chronological final 40% / 113 frozen blueprints: fewer than 80 pairs; fewer than six represented symbols; non-positive treated mean after the same labeled symmetric 20-bps underlying absolute-level sensitivity; non-positive paired excess mean; non-positive one-sided 90% circular five-pair-block bootstrap lower bound; failure to reproduce the frozen data/config/281-blueprint population and first-168 train identities; or any chronology, control-reuse, window-overlap, match-bound, nonfinite, or strict-JSON violation.

Per-symbol treated/control/paired means and counts, leave-one-symbol-out pooled bootstrap bounds, and chronological-tertile paired means/bootstrap bounds are mandatory reporting-only concentration diagnostics. They do not alter the frozen pooled gate after inspection.

## Exact decision this wake closes

- `STRATEGY_ADVANCED` only if the unchanged pooled holdout gate passes: advance `F1_TRAIN → F2_UNTOUCHED_HOLDOUT`, still L0 and still without option/L1/capital/paper authority.
- Otherwise `FAMILY_CLOSED`: remain at F1 historical context, record the dominant holdout failure, quarantine the exact 20-session breakout / 10-session continuation / frozen-panel / prior-only matched-control geometry, and price no options.

No registry mutation, capital seat, paper order, shadow transition, broker session, arm, or live action is authorized.

## Finalizer disposition

The frozen decision stands: `STRATEGY_ADVANCED` from `F1_TRAIN` to `F2_UNTOUCHED_HOLDOUT/L0` on the unchanged pooled gate. Finalization split funnel progress from authority (`funnel_claim_f2=true`, `l1_claim=false`), retained weak symbol/time slices as mandatory non-gating scope limits, and froze the next option stage to the original 168 development rows with the opened 113 usable only as non-retunable secondary stress. The immutable one-shot cache was not rewritten; its durable summary supersedes the legacy overloaded claim field. Integration remains pending the deterministic wrapper gate.

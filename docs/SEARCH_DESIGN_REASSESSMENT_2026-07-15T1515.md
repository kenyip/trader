# Search Design Reassessment — 2026-07-15T1515

## Trigger

The prior epoch `2026-07-15-viable-path` completed three post-reassessment BUILD wakes without `STRATEGY_ADVANCED`. Its third result explicitly required burst stop and search-design reassessment before more search volume. This reassessment starts a new epoch before the current experiment; it does not reset or reopen any closed prior family.

## Prior-epoch diagnosis

The prior three mechanisms failed for different reasons:

1. TSLL/TSLA dislocation recovery: treated and neutral populations existed, but the frozen prior-only match geometry produced zero supported pairs, so expectancy remained unread;
2. one-global-risk-unit PCS cadence: concentration control reduced admissions but could not create robust expectancy or bring either frozen cost axis below the absolute drawdown gate;
3. monthly OPEX post-expiry drift: the train population was non-vacuous and point excess was positive, but its predeclared dependence-aware bootstrap lower bound remained negative.

The shared lesson was that support, concentration control, and favorable point estimates are not substitutes for a bounded edge. More threshold variants inside those inspected designs would be volume, not information. The successor therefore uses a materially different within-symbol event-time continuation design with prior-only controls and reserves its chronological holdout before outcome evaluation.

## New evidence class and mechanism

Open exactly one new family:

`TIME_SERIES_20D_BREAKOUT_CONTINUATION`

Economic mechanism: gradual information diffusion and trend-following demand may produce short-horizon continuation after an unusually strong completed-bar breakout in an established uptrend.

The new evidence class is an outcome-independent, within-symbol matched event study:

- treated: close at least 2% above the prior completed 20-session high and above a fully warmed prior-completed SMA100;
- control: earlier same-symbol close at 95%–100% of the prior completed 20-session high, also above SMA100;
- matching: prior-only, without replacement, on 20-session return and realized volatility, with non-overlapping outcome windows;
- action: next-session entry and ten-session forward adjusted-close outcome;
- uncertainty: one-sided 90% circular five-pair-block bootstrap lower bound;
- untouched reserve: chronological final 40% of matched blueprints; no outcomes read in this wake.

This is materially different from the closed cross-sectional momentum/volatility selectors and from PCS daily bullish-momentum variants: it is a within-symbol, event-time continuation mechanism with a conditional positive-delta debit expression. Closed families remain quarantined.

## Frozen first experiment

Candidate: `MULTINAME_BREAKOUT_BULL_CALL_14D_V1`.

Panel: AAPL, MSFT, NVDA, AMZN, META, GOOGL, AMD, TSLA. Requested range: 2016-01-01 through an end-exclusive 2026-07-15; the realized common panel ends 2026-07-14. The panel is fixed-present-day and therefore explicitly survivorship/listing biased.

Discovery falsifier on the first chronological 60% of outcome-independent matched pairs:

- fewer than 80 train pairs, or fewer than 6 represented symbols;
- non-positive treated mean after labeled 20-bps underlying round-trip sensitivity;
- non-positive paired excess over earlier same-symbol controls;
- non-positive one-sided 90% five-pair-block bootstrap lower bound for paired excess;
- any chronology, reuse, overlap, or match-bound violation.

A pass advances only F0→F1 / L0 underlying discovery. It does not establish option mispricing, option after-cost edge, L1, a capital seat, paper eligibility, or readiness. A fail closes this exact 20-session breakout/10-session continuation family under the frozen geometry.

## Conditional trade stack

- forecast: direction up over ten sessions;
- option expression if the untouched holdout later survives: one-lot 14-DTE $1-wide bull-call debit spread;
- intended Greeks: positive delta, bounded positive gamma;
- dangerous Greeks: theta decay if continuation stalls, long-vega exposure, pin/liquidity/assignment risk;
- entry: next session after completed-bar signal;
- discovery outcome: fixed ten-session underlying return only; the later 14-DTE option expression is approximate horizon alignment, not a managed-path result;
- management to test later: 50% of maximum spread value profit harvest, thesis invalidation on close below the pre-breakout 20-session high, hard ten-session time stop;
- capital fit: structural $100 one-lot width bound before closing friction, max one lot, one correlated breakout risk unit across the sleeve;
- stand aside: no qualifying signal, failed train/holdout gate, or future option debit/cost/loss outside the one-lot bound.

## Epoch rule

This is wake 1 of the new epoch. If two consecutive completed wakes in this epoch do not advance a strategy, the next wake must pivot to a materially different mechanism or evidence class. If three do not advance, stop and reassess again. The next wake may read the untouched holdout only if the frozen train gate passes; otherwise it must not retune this exact family.

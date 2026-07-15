# Strategy Decision Charter — 2026-07-15T1515 Executor

- Phase: BUILD, research/paper only, $3,000 Agentic sleeve.
- Economic edge mechanism: short-horizon continuation after a completed close at least 2% above the prior completed 20-session high in a positive fully warmed SMA100 trend, attributed to gradual information diffusion and trend-following demand.
- Candidate/family: `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` / `TIME_SERIES_20D_BREAKOUT_CONTINUATION` across AAPL, MSFT, NVDA, AMZN, META, GOOGL, AMD, TSLA.
- Current funnel stage: `F0_MECHANISM`.
- Exact wake decision: `BLOCKER_REMOVED_AND_RETESTED` because the prior epoch had exhausted its three-wake no-advance burst; repair consists of an explicit reassessment/new epoch and a new outcome-independent matched event-study capability, followed by the frozen strategy test in the same wake. The retest must resolve to `STRATEGY_ADVANCED` or `FAMILY_CLOSED`.
- Predeclared falsifier: on the chronological first 60% of matched pairs, fewer than 80 pairs or 6 symbols; non-positive treated mean after labeled 20-bps underlying round-trip sensitivity; non-positive paired excess versus earlier same-symbol controls; non-positive one-sided 90% circular five-pair-block bootstrap lower bound; or any chronology/reuse/overlap/match-bound violation.
- Claim boundary: pass means F0→F1 / L0 underlying discovery only. No option marks, option costs, fills, L1, capital seat, paper eligibility, registry promotion, or real-account readiness.
- Option alignment: conditional one-lot 14-DTE $1-wide bull-call debit spread, intended positive delta/bounded gamma; dangerous long-vega/theta/pin/liquidity risks remain unmeasured.
- Capital: `capital_fit_usd=100`, one-lot `max_loss_usd=100` structural width bound before closing friction, `max_lots=1`, one correlated breakout risk unit across the sleeve.
- Stand aside: absent qualifying signal, failed train/holdout gate, or future option package outside the one-lot risk/cost bound.
- Prior NEXT superseded: the prior wake required a search-design reset rather than another strategy run in the exhausted epoch. This charter performs that reset before opening one materially different mechanism/evidence class.

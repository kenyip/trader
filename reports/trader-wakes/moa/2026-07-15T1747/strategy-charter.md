# Strategy decision charter — 2026-07-15T1747 executor

PHASE: BUILD / L0 discovery only
SLEEVE_USD: 3000
DECISION TO CLOSE: advance `POST_SHOCK_RANGE_COMPRESSION_IRON_BUTTERFLY_21D_V1` from `F0_MECHANISM` to `F1_TRAIN`, or close the exact family at F0.

## Why this loop

The latest current full-universe research rank (`research.db` run 36, generated after the cash close) places AAPL, AMD, META, GOOGL, NVDA, and AVGO among the highest-ranked neutral/high-premium liquid names. Prior NEXT is accepted only in mechanism class: test a non-monotonic theta-led payoff rather than reopen the closed bull-call expression. This loop does not reopen the generic iron-butterfly proxy search unchanged: it names a new event-conditioned economic mechanism and a prior-only same-symbol matched-control evidence class. Closed daily PCS/CCS, asymmetric-condor, generic butterfly-cost, and breakout bull-call families remain quarantined.

## Layered Edge Stack

- candidate_id: `POST_SHOCK_RANGE_COMPRESSION_IRON_BUTTERFLY_21D_V1`
- structure_family: conditional symmetric credit iron butterfly (not yet option-priced)
- market / underlying: frozen ordered panel AAPL, AMD, META, GOOGL, NVDA, AVGO; chosen before outcomes from current run-36 neutral/high-premium rank and liquidity, not from future event outcomes.
- forecast_type: `range_bound`
- economic mechanism: a completed large one-session move inside an otherwise neutral medium-term price location, while short realized volatility is elevated versus long realized volatility, may reflect temporary liquidity/attention pressure. After the shock, liquidity normalization and volatility mean reversion may produce a tighter five-session close path and higher terminal pin probability than prior same-symbol high-volatility neutral controls without the shock.
- option structure: future one-lot 21-DTE symmetric credit iron butterfly, exact `$2` wings, structurally defined maximum loss no more than `$200` before credit and closing friction. No option pricing is run unless the underlying mechanism first clears F0→F1.
- intended Greeks: positive theta and short vega while spot remains near the body; limited short gamma inside defined wings.
- dangerous unintended Greeks: short gamma/path risk after a shock, vega expansion rather than crush, pin/assignment risk, and four-leg spread friction.
- regime envelope: only a prior-completed-bar absolute one-day return at least 2%, `hv20/hv60 >= 1.20`, price within ±5% of a fully warmed prior SMA20, and no scheduled-event data claim. Stand aside outside that envelope, in missing/nonfinite history, when exact option package risk exceeds the one-lot bound, or if discovery fails.
- entry trigger: next session after the completed signal; no same-bar entry.
- measured exit / outcome: fixed five completed sessions for the underlying pre-screen. Future option management, not tested here: 40% credit harvest, 70% of defined-loss cut, or 5-DTE stop, with expiration precedence and no same-bar reentry.
- capital_fit_usd: `$200` structural one-lot width bound before entry credit/closing friction; discovery label only.
- one-lot max_loss_usd: `$200` structural bound before closing friction; future executable package must report the larger of structural and stressed path loss.
- max_lots: `1`
- portfolio overlap: one global open risk unit across this correlated mega-cap/semi panel; no same-cluster concurrent entries.
- evidence stage: `F0_MECHANISM`; bar claimed: `discovery`; option marks/costs/fills: not run.
- population/control design: chronological 60/40 blueprint split; first 60% only is inspected. Each treated shock is matched without replacement to an earlier same-symbol high-volatility neutral no-shock control, using only signal-time 20-session return, `hv20/hv60`, SMA20 distance, and calendar distance; control and treated forward windows cannot overlap.
- predeclared falsifier: close the exact family at F0 if the chronological train partition has fewer than 60 pairs or fewer than 5 represented symbols; if treated mean five-session close-path range is not lower than control; if treated terminal pin rate within ±3% is not higher than control by at least 5 percentage points; if mean paired range compression (`control_range - treated_range`) is non-positive; if its one-sided 90% five-pair circular-block-bootstrap lower bound is non-positive; or if any chronology, overlap, control-reuse, signal, or match-integrity check fails.
- stand-aside rule: any failed trigger, failed discovery gate, unavailable/four-leg package, one-lot risk above `$300`, observed friction not supportable, or correlated unit already open means no trade.
- confidence / authority: F0/L0 before test. Even an advance grants F1/L0 research only—no L1, registry promotion, paper seat, shadow, arm, broker, or live action.

## Freedom audit

Free symbol/strategy search remained intact. Current rank selected a six-name neutral/high-premium panel; the mechanism—not existing paper plumbing—selected the structure. No TSLA/TSLL tunnel, diversify-for-fear seat, or live path was used.

# MoA executor closeout — 2026-07-15T1747

PARTIAL PHASE: executor only. Challenger/finalizer/integration are still required. No commit, merge, push, or RUN COMPLETE claim is made here.

## Strategy decision charter

- exact decision: advance `POST_SHOCK_RANGE_COMPRESSION_IRON_BUTTERFLY_21D_V1` from `F0_MECHANISM` to `F1_TRAIN`, or close the exact family at F0.
- economic mechanism: temporary liquidity/attention pressure after a completed large one-session move may normalize. When `hv20/hv60 >= 1.20` but close remains within ±5% of its prior completed SMA20, the following five-session close path may be tighter and more likely to finish near entry than a prior same-symbol high-volatility neutral no-shock control.
- market / underlying: frozen ordered AAPL, AMD, META, GOOGL, NVDA, AVGO panel. These were chosen from current `research.db` run 36 neutral/high-premium/liquidity ranks before this experiment's train outcomes. The historical study is nevertheless a fixed present-day survivor panel and is explicitly not point-in-time universe selection.
- forecast type: `range_bound`.
- option structure: future one-lot 21-DTE symmetric credit iron butterfly with exact `$2` wings; no option pricing was allowed before the underlying F0 gate.
- intended Greeks: positive theta, short vega, bounded short gamma.
- dangerous Greeks/exposures: renewed short-gamma path expansion after the shock, vega expansion, four-leg friction, pin/assignment risk, and unavailable exact expirations/strikes.
- regime: completed-bar absolute one-day return `>=2%`, `hv20/hv60 >=1.20`, close within ±5% of prior SMA20; otherwise stand aside.
- entry: next session only; no same-bar use.
- measured exit: fixed five-session underlying close-path range and terminal ±3% pin. Future option management remains untested context only: 40% credit harvest, 70% defined-loss cut, or 5-DTE stop with expiration precedence and no same-bar re-entry.
- risk/capital: `capital_fit_usd=$200`, one-lot `max_loss_usd=$200`, `max_lots=1`; structural width ceiling before entry credit/closing friction, not a simulated or observed loss. One global correlated risk unit across the panel.
- evidence stage before: `F0_MECHANISM/L0`.
- controls: earlier same-symbol high-HV neutral no-shock observations, matched without replacement on 20-session return, `hv20/hv60`, SMA20 distance, and calendar distance. Control and treated outcome windows are non-overlapping; only the chronological first 60% of frozen blueprints is inspected.
- predeclared falsifier: close at F0 if train has `<60` pairs or `<5` symbols; treated mean five-session close-path range is not lower than control; treated terminal ±3% pin-rate edge is `<5` percentage points; paired `control_range - treated_range` mean or one-sided 90% five-pair circular-block-bootstrap lower bound is non-positive; or any chronology/overlap/reuse/signal/match check fails.
- stand-aside: any missing trigger, failed gate, exact-package unavailability, risk above `$300`, unsupported four-leg friction, scheduled-event uncertainty, or existing correlated open unit.
- authority even if passed: F1/L0 research only; no L1, registry, capital seat, paper, shadow, funding, broker, arm, or live authority.

The full pre-action charter is preserved at `reports/trader-wakes/moa/2026-07-15T1747/strategy-charter.md`.

## Closed strategy outcome — `FAMILY_CLOSED`

Claim artifact: `reports/trader-wakes/moa/2026-07-15T1747/post-shock-range-compression-train.json`

- exact family: `POST_SHOCK_RANGE_COMPRESSION_MATCHED_CONTROL`
- funnel: `F0_MECHANISM -> F0_MECHANISM`
- matched blueprints: 102; train 61; untouched holdout 41.
- breadth: all six symbols; train pair counts AAPL 10, AMD 4, AVGO 13, GOOGL 16, META 14, NVDA 4.
- treated mean five-session close-path range: `5.018873756%`.
- control mean close-path range: `4.644141213%`.
- paired range-compression mean (`control - treated`): `-0.374732544%`.
- one-sided 90% five-pair block-bootstrap lower bound: `-1.012686052%`.
- treated and control ±3% pin rates were equal; pin-rate edge `0.0` percentage points.
- density and breadth passed; all four economic gates failed; integrity violations `[]`.
- all three chronological train tertiles had negative paired compression (`-0.6233%`, `-0.2786%`, `-0.2296%`). AAPL alone was positive on only 10 post-hoc rows; no symbol carve-out is advanced or retested.
- holdout dates `2022-01-05..2026-07-09` remain outcome-unread and option pricing calls remain zero.

Dominant failure mechanism: the post-shock cohort expanded rather than compressed over the five-session close path, with no incremental terminal pin edge. The gross underlying mechanism fails before four-leg costs, option marks, or management can help. The exact pooled panel/trigger/control/horizon family is quarantined from unchanged reruns. This does not claim that every shock definition, symbol-specific model, or iron-butterfly mechanism is universally impossible; reopening requires a genuinely new mechanism/evidence class, not threshold mining or the post-hoc AAPL slice.

## Evidence validity critique

- chronology/leakage: signals use completed bars; entry is next session; controls are prior only; train/holdout split occurs on frozen blueprints; tests show altering a selected treated outcome does not alter that selection. Integrity counters are zero.
- provenance: six yfinance `auto_adjust=True` close caches each contain 2,647 common rows from `2016-01-04` through `2026-07-15`, inner-joined without forward fill. Exact source hashes are in the JSON.
- reproducibility repair: the shared adjusted-history loader previously wrote a cache but let a first run continue from downloader floats, producing sub-ulp differences versus a hash-identical cache replay. It now reads the persisted cache back before evaluation; an exact-series regression was added. Canonical and replay payloads are byte-value identical after removing only `generated_at`; the strategy decision remained `FAMILY_CLOSED` before and after repair.
- population: the current full-universe rank was complete for its run, but the fixed current survivor panel creates selection/listing bias over historical train. Therefore the close is scoped to this exact panel/family; there is no population-wide generalization claim.
- path realism: adjusted daily closes omit intraday excursions and understate absolute short-gamma path risk. Because even the close-only gross mechanism fails, this omission cannot rescue the planned short-gamma expression; it narrows rather than inflates the close.
- option/cost/contract boundary: no observed or proxy option marks, implied-volatility crush, four-leg fills, listed-expiry availability, assignment, or option management were measured. No after-cost option edge, L1, or paper claim is made. Structural `$200` width is a planning ceiling only.
- uncertainty/concentration: pooled uncertainty bound is negative and every chronological tertile is negative. Sparse AMD/NVDA and positive AAPL development slices are retained as limitations, not promoted post hoc.
- living leader: none exists in current readiness. This F0 mechanism was judged only against its predeclared absolute discovery gate and cannot receive a capital seat.

## Search information versus strategy progress

Search information:

1. Added an outcome-independent, prior-only matched post-shock range-compression lab with untouched holdout semantics and strict JSON output.
2. Added behavioral, boundary, negative-control, breadth, strict-null, holdout-secrecy, capital-stack, and CLI tests.
3. Removed shared cache-first-run provenance nondeterminism and proved exact persisted-series reuse.
4. Refreshed income coverage: 21 structures, 246 hypotheses, 70 evolve artifacts, no living leader.

Strategy progress:

- exactly one outcome: `FAMILY_CLOSED`.
- no strategy advanced; no current phase, B check, readiness authority, registry status, or capital path changed.
- active reassessed-epoch no-advance streak becomes one if the finalizer accepts this wake; no two-wake pivot or three-wake burst stop is yet triggered.

## Verification executed

- TDD red: new suite initially failed import because implementation did not exist.
- new behavioral/boundary/negative-control suite: 8/8 OK.
- focused/adjacent suite: post-shock, breakout-continuation, iron-butterfly, coverage — 20/20 OK.
- cache provenance + post-shock suite after repair — 15/15 OK.
- final full suite after the cache repair and report writes — 339/339 OK.
- Python compile for all changed Python/test surfaces — OK.
- final `git diff --check` — OK.
- exact canonical-cache replay — same payload after removing only `generated_at`; family-close metrics and decision unchanged.

The finalizer must rerun the full suite and deterministic completion/integration gates after challenger repairs; this executor phase intentionally does not commit or push.

## Readiness / safety

BUILD/L0 only. `reports/readiness/LATEST.md` was not changed because phase and B checks did not change. No live order, broker login/session, shadow promotion, agentic arm, paid data, secret, private position, or main-account action occurred.

Freedom audit: symbol/strategy search stayed free; the current rank and a new range-compression mechanism selected a non-monotonic theta structure. Closed families were not reopened unchanged, TSLA/TSLL were not privileged, and no diversify-for-fear capital seat was created.

## Exactly one next seed

Finalizer supersession: the executor-proposed calendar seed below is retained as role history only. Challenger/finalizer rejected it as too near closed TOM/OPEX/monthly-ranking families; the one living seed is `POST_EARNINGS_INFO_RESOLUTION_DRIFT_F0` in `merged-next-seed.md`, `learning-promotion.md`, the final merge, LATEST, INDEX, and readiness.

`MONTH_END_FLOW_POSITIVE_DRIFT_PCS_F0`: predeclare a train-only, matched same-symbol/weekday study of last-three-trading-days institutional/rebalancing flow versus ordinary calendar controls across a fixed liquid panel; test five-session positive drift before any `$2`-wide PCS pricing, preserve an untouched holdout, and close at F0 unless breadth, paired drift, block-bootstrap uncertainty, and downside-tail gates all pass.

MOA_EXEC_DONE

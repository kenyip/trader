# Trader readiness — LATEST

Updated: 2026-07-16T0546 RUN COMPLETE (`317384d`); integrated/pushed/postflight-complete on `main == origin/main`
Phase: **BUILD**
Authority: **research / paper-safe only; no broker, shadow, arm, or live authority**
Integration: complete; wrapper postflight receipt confirms clean pushed main

## Current strategy decision

`FAMILY_CLOSED`, `F0_MECHANISM -> F0_MECHANISM`, for exact `BROAD_INDEX_OVERNIGHT_ABSORPTION_BULL_CALL_21D_V1` / `BROAD_INDEX_OVERNIGHT_SELL_INTRADAY_ABSORPTION_FORWARD_UPDRIFT`. Strategy advancement is false.

The predecessor three-no-advance epoch remained completed. A mandatory reassessment opened successor epoch `REPEATED_EXPOSURE_SPECIFICITY_DISCOVERY_V1` before this experiment. This accepted close is successor decision one: `strategy_pivot_required=false`, `strategy_burst_stop_required=false`.

## Exact evidence

Canonical artifact: `reports/trader-wakes/moa/2026-07-16T0546/broad-index-overnight-absorption-train.json`

- Current finalizer-regenerated raw SHA-256: `29d0c6199c96ed9c91290467c748e34c5c7cd4bdced243abb84dfde93fe51b73`.
- Normalized SHA-256 excluding only `generated_at`: `85ce2277b587135cd7394e0cce0b6e90cc5ce82e6c7f8067241042cb60a3b4a5`; persisted-cache replay is exactly equal on the normalized payload.
- Source panel: adjusted `SPY, QQQ, IWM, DIA`, 4,832 rows each, 2007-05-01 through 2026-07-15; source hashes are in the artifact.
- Frozen unique signal dates: 168; train cutoff 2019-11-14.
- Train eligible/matched rows: 144/139; prior same-symbol control support 96.5278%.
- Same-date clustered train episodes: 97 across 12 years and all four ETFs.
- Event/control mean after 10 bps: **-0.048879% / +0.017988%**.
- Paired event-minus-control mean/median: **-0.066867% / -0.124070%**.
- Circular five-episode-block paired LB90: **-0.623971%**.
- Event positive frequency: **57.7320%**.
- Event-return worst-decile mean after 10 bps: **-5.724566%**; paired-excess worst-decile diagnostic: **-6.831920%**.
- Control distance median/max: **268 / 735 sessions**.
- Integrity violations: **0**.
- Passed gates: 48 clustered episodes, ten years, three symbols, 80% control support, 55% event hits, zero integrity violations.
- Failed gates: positive event mean, positive paired mean, positive block LB90, event-return worst-decile >=-5%.
- Holdout: 105 matched identities on 68 signal dates, 2020-01-06 through 2026-06-29, identity SHA `8d427bb57ee199bc6fa2f1abefbd920df184650ac0a0bd1356f2e0a2c228b193`; outcomes unread, simulation false, option pricing zero.

Dominant failure: density and hit rate were not enough. Absolute event expectancy, paired specificity, dependence-aware uncertainty, and event tail all failed.

Exact-family quarantine: no overnight/intraday threshold nudge, horizon change, sign inversion, same-date unclustered rerun, post-hoc 3+-symbol breadth filter, or option-wrapper substitution. Reopening requires a genuinely new predeclared risk-transfer mechanism or evidence class.

## Dependence / breadth / control boundaries

Same-date clustering correctly reduces synchronous pseudo-replication, but it does not establish 97 independent episodes.

- **28/96** consecutive episode gaps are at most seven calendar days, so five-session windows can retain shared calendar exposure.
- Episode breadth is mostly sequential: **67×1, 20×2, 8×3, 2×4** represented ETFs.
- Prior-control distance is **268/735 sessions** median/max, so local specificity is weak despite 96.5% support.
- The five-episode circular block is a dependence sensitivity, not proof of independence.

These limits weaken any salvage argument. They do not reverse an already-negative event/paired result and do not authorize outcome-driven filtering.

## Layered Edge Stack / capital truth

Measured F0 forecast: bullish direction from next completed close through the fifth subsequent completed close after the frozen overnight-sell/intraday-absorption state.

Future expression only: one-lot 18–24 DTE $2-wide bull-call debit spread.

- `capital_fit_usd=200`
- frictionless planning `max_loss_usd=200` width ceiling before debit, closing friction, assignment/exercise, or management-path validation
- `max_lots=1`; one broad-index directional risk unit across correlated ETF signals
- intended: positive delta, limited positive gamma/vega, defined debit
- dangerous: negative theta, volatility crush, gap loss, capped upside, correlation, debit/closing friction, assignment/exercise
- future management only: +50% spread value, -50% debit, five-session time stop or trend invalidation; no roll/averaging
- stand aside: under-warmed/nonfinite data, regime mismatch, absent prior control, future option illiquidity, debit above $200, overlapping broad-index risk, or source/chronology/integrity ambiguity

The five-session underlying result is not an 18–24 DTE option-path result. No historical contract, IV, strike, listed expiry, debit, fill, theta/vega path, management, assignment, or exercise was measured. The planning expression grants no F1, L1, paper plan, or capital seat.

## Funnel / leaders / seats

| item | current |
|---|---:|
| living strategy candidates | 0 |
| F1 survivors | 0 |
| F2 untouched-holdout survivors | 0 |
| F3 robust paper plans | 0 |
| F4 observed paper candidates | 0 |
| L1 capital-seat candidates | 0 |
| quality leaders | 0 |
| capital seats | 0 |

No stale historical leader is living. Absolute frozen discovery gates governed this F0 decision.

## Readiness checks

| Check | State | Evidence / gap |
|---|---|---|
| B1 — deterministic research evidence | BUILD improvement only | Current-code strict JSON, source hashes, normalized replay equality, clustered train, and sealed holdout are green; the strategy fails the complete discovery conjunction. |
| B2 — strategy hypothesis quality | NOT READY | Exact family closed; no F1 survivor. |
| B3 — regime/path stress | NOT RUN for candidate | Inapplicable after F0 close. |
| B4 — cost/parameter stress | NOT RUN for candidate | Underlying 10-bps sensitivity only; no option proxy or observed marks. |
| B5 — auditability / controls | BUILD improvement only | Prior-only controls, global-date partitioning, same-date clustering, residual-gap/breadth diagnostics, strict holdout seal, and tests are durable; near-date dependence, remote controls, and fixed-panel survivorship remain explicit limits. |
| B6 — paper execution realism | NOT READY | No option path, packet, or observed paper fills. |
| B7 — shadow | BLOCKED | Ken-only authorization; no qualifying candidate. |
| B8 — agentic live | BLOCKED | Ken-only arming; prohibited. |

No B3/B4/B6+ state or phase advanced. No registry mutation or paper intent occurred.

## Verification

Finalizer-owned results:

- Focused behavior/boundary/positive/negative-control suite: **9/9**, `OK`.
- New lab + compounding/completion/coverage/progress adjacent suite: **65/65**, `OK`.
- Full required suite `.venv/bin/python -m unittest discover -s tests`: **433/433**, `OK`.
- Deterministic persisted-cache replay: normalized payload equality true; current normalized SHA `85ce2277…`.
- Strict JSON, source/holdout hashes, outcome `FAMILY_CLOSED`, and option-pricing count zero verified.
- Income coverage: **21 structures / 246 hypotheses / 70 evolve artifacts / no quality leader**.

Deterministic secret/path/diff/staging and integration checks passed under the wrapper postflight receipt.

## Active search-epoch implication

`configs/search_epoch.json` preserves completed predecessor `POST_REASSESSMENT_INDEPENDENT_DEFINED_RISK_DISCOVERY_V1` (0335/0408/0454, three no-advances) and records active successor `REPEATED_EXPOSURE_SPECIFICITY_DISCOVERY_V1`:

1. 2026-07-16T0546 broad-index overnight absorption — no advance / family close.

Successor `counted_no_advance_decisions=1`, `strategy_pivot_required=false`, `strategy_burst_stop_required=false`.

## ONE NEXT

`YIELD_CURVE_STEEPENING_REGIONAL_BANK_FORWARD_UPDRIFT_PREFLIGHT`: before any train outcome access, validate that a completed point-in-time steepening measure built from fixed Treasury-duration proxies can honestly support a regional-bank lending-margin mechanism without composition, futures-roll, credit-beta, or construction confounds. If proxy semantics fail, stop pre-outcome without inspecting KRE returns. Only if they pass, freeze a train-only KRE or predeclared regional-bank panel with chronology, density, prior same-regime controls, sealed holdout, labeled underlying cost, and one-lot defined-risk bull-call planning fields, then advance-or-close under frozen gates. No overnight-absorption salvage, holdout reads, L1, seat, paper, shadow, arm, broker, funding, or live claims.

Finalizer status: `MOA_FINALIZE_READY`; integration remains pending the deterministic wrapper gate.

## RTH opportunity reconfirm

Updated: 2026-07-16T1230 mid-session RTH.

| Check | State | Evidence |
|---|---|---|
| C — live condition / paper opportunity | STAND_ASIDE (reconfirm) | Scout 14/0/14; autonomy 0 proposals; PCS b195f5fe+ bear_dte=0; real open_risk=0; same class as 0630 open + 1030/1130 mid. Session-day freshness pass (SMCI/AMD intraday mark drift only). No new densify (archive already 3/3 RTH). No B6 advance. |


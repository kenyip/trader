# Agentic go-live readiness — LATEST

As-of: 2026-07-16T0408 RUN COMPLETE (`df5a9e5`); integrated/pushed/postflight-complete on `main == origin/main`
Phase: BUILD
Status: NOT READY
Authority: research-only; no broker session, funding, shadow promotion, arming, or live orders
Integration: complete; wrapper postflight receipt confirms clean pushed main

## Current strategy-convergence state

- Living candidates: **0**
- Furthest living funnel stage: **none**
- L1 sim-edge candidates: **0**
- Quality leader: **none**; the former TSLL PCS proxy reference remains disqualified
- Capital seats: **0**
- Active successor search epoch: `POST_REASSESSMENT_INDEPENDENT_DEFINED_RISK_DISCOVERY_V1`, formally registered at `2026-07-16T0335`; the prior FOMC epoch remains completed historical context.
- Consecutive no-strategy-advance decisions in the active epoch: **2** (`0335`, `0408`).
- `strategy_pivot_required=true`; `strategy_burst_stop_required=false`. The next wake must use a materially different mechanism/evidence class and cannot retune this wake's credit or overnight screens.

## Accepted strategy decision

`CREDIT_RISK_OFF_SPY_BEAR_PUT_21D_V1` / `HIGH_YIELD_CREDIT_DIVERGENCE_FORWARD_DOWNSIDE` is **FAMILY_CLOSED at F0**. Strategy advancement is false.

Frozen train-only evidence from the run-local canonical factory claim JSON:

- exact-date adjusted SPY/HYG/IEF panel: **4,832** sessions, 2007-05-01 through 2026-07-15; source CSVs hash-cited; no forward fill;
- train eligible/matched: 42/41 across ten signal years; prior-control support 97.6190%;
- signed bearish event mean after 10 bps: **-0.909825%**;
- signed bearish prior-control mean after 10 bps: **-0.201659%**;
- signed paired excess: **-0.708167%**;
- circular three-pair-block LB90: **-1.360006%**;
- signed positive frequency: **29.2683%**;
- signed worst-decile mean: **-4.015427%**;
- failed gates: event expectancy, paired specificity, uncertainty lower bound, and positive frequency;
- passed-but-nonrescuing gates: n36 density, eight-year floor, 80% support, -5% tail floor, and zero integrity violations;
- prior-control distance diagnostic: median **153** sessions, maximum **680** sessions. This is a long-lookback generalization limit, not a post-hoc invitation to widen or retune matching;
- untouched holdout: 28 matched identities, SHA `83fc5c0fe69de6801d440970c53edc8c098d09bd3edf0cdbe7728a41707c1c23`; outcomes unread, simulation false, option pricing zero.

The signed forecast is wrong in train: SPY rose after the trigger and the bearish result was worse than matched prior same-regime controls. A bear-put wrapper cannot rescue the F0 anti-edge.

Conditional future geometry was planning-only: one-lot 18–24 DTE $2-wide SPY bear-put debit spread, `capital_fit_usd=200`, frictionless planning `max_loss_usd=200` before debit slippage/closing friction, `max_lots=1`. No historical option contract, debit, IV, fill, path, assignment, management, L1, or capital-seat claim exists.

## Secondary factory screen — no advancement

`OVERNIGHT_SELL_INTRADAY_RECOVERY_SPY_BULL_CALL_21D_V1` / `OVERNIGHT_INTRADAY_DISAGREEMENT_FORWARD_UPDRIFT` remains F0/L0 search information only:

- train eligible/matched 34/32, support 94.1176%, ten signal years;
- signed event mean +0.511192%, paired excess +0.739330%, positive frequency 71.875%, worst-decile -4.699177%;
- required density failed at n32 <36 and paired LB90 failed at -0.200722% <=0;
- prior-control distance diagnostic: median **155.5** sessions and maximum **723** sessions (direct recomputation from the 32 persisted pair rows; the challenger prose median 165 was not reproducible);
- holdout 24 matched identities, SHA `40113d833d3e6d360a7230015a5dfffdd3f53a3267ad3d569ea41089874492c8`; outcomes unread, simulation false, option pricing zero.

Positive point centers are diagnostic only. Do not open the holdout, retune thresholds, claim F1/L1/paper eligibility, or turn the secondary screen into a second family-close outcome.

## Readiness checks

| Check | Status | Current evidence / blocker |
|---|---|---|
| B0 Policy/config safety | PASS for BUILD | Research-only; no broker, order, funding, shadow, arm, or live action. |
| B1 Data integrity | BUILD-PASS / live-NOT-READY | Exact persisted source hashes, lagged signals, prior-only controls, sealed holdouts, deterministic replay, bounded ULP CSV validation, and exact failed-gate machine labels are green. Observed historical option surfaces remain unavailable. |
| B2 Risk checks | PARTIAL | $3k sleeve, one-lot cap, and frictionless planning debit bounds are explicit; no candidate earned a capital seat and actual option debit/path loss is unmeasured. |
| B3 Backtest density | NOT READY | Primary mechanism is closed at F0; secondary fails frozen n36. No living strategy has dense after-cost L1 evidence. |
| B4 Stress/tails | NOT READY | Primary expectancy/specificity/uncertainty fail; secondary uncertainty fails. No surviving priced option path exists. |
| B5 Logging/audit | BUILD-PASS | Charter, canonical claim, executor/challenger/finalizer judgments, schema-v2 compounding, learning promotion, epoch record, source hashes, sealed identities, and finalizer-owned replay/tests are durable; deterministic integration is complete. |
| B6 Paper path | NOT READY | No capital-fit living candidate or paper intent exists. |
| B7 Shadow path | NOT READY | No propose->risk_check->log window exists. |
| B8 Arming/funding | HARD STOP | Ken mandate, funding, explicit arm, and accepted live packet are absent. |

## Data and claim boundaries

- Features end at a completed session; entry is next close and exit is the fifth subsequent close.
- Signals are non-overlapping. Controls are deterministic, prior-only, no-reuse, base-regime matched, non-trigger at the control feature date, and fully realized before each signal.
- No later control-path pattern label is used to select controls.
- Control matching can reach 680/723 sessions; that weakens local comparability/generalization but does not salvage either failed frozen decision.
- The present-day ETF panel and evolving HYG/IEF composition limit generalization; these are not point-in-time credit spreads.
- The 10-bps hurdle is underlying sensitivity, not option spread/fill friction.
- Both chronological holdouts remain identity-only and outcome unread; zero option pricing occurred.
- Finalizer-regenerated claim raw SHA is `2eb3e4c7ebf502de0ac533edcf8a986eb95253189a46922f6f3b7bb75b13f14c`; replay-normalized SHA is `a4fd731d931185297648b7bde28350c9b17022cf8062b9fc06fa0e76762d30b3`. The challenger independently verified the pre-wording-repair SHA `31278399…`; economic rows and decisions are unchanged.
- Proxy underlying evidence can close exact F0 mechanisms but cannot earn L1 or paper authority.

## Closed-family quarantine

Add both stable IDs:

- `CREDIT_RISK_OFF_SPY_BEAR_PUT_21D_V1`
- `HIGH_YIELD_CREDIT_DIVERGENCE_FORWARD_DOWNSIDE`

Quarantine scope: SPY above SMA100, ten-session HYG-minus-IEF <=-1.5 percentage points, SPY five-session return <=0, next-close entry, five-session hold, nearby threshold nudges, and option-wrapper substitutions on the same panel. Reopening requires a materially different credit-state construction/economic horizon justified before outcomes, point-in-time credit-spread evidence, or another independent evidence class.

Do not retune or open the sealed holdout for `OVERNIGHT_SELL_INTRADAY_RECOVERY_SPY_BULL_CALL_21D_V1`. Existing sector-leader, Beige Book, FOMC, and earlier compounding quarantines remain in force.

## Verification

- Focused behavioral/boundary/positive/negative/leakage plus shared OHLCV/FOMC and schema-v2/epoch regressions: `Ran 47 tests in 9.389s`, `OK`.
- Mandated full suite `.venv/bin/python -m unittest discover -s tests`: `Ran 416 tests in 26.777s`, `OK`.
- Strict compile plus `just test`: exit 0; TSLA and TSLL both `STAND ASIDE`; no broker action.
- Exact-cache replay: substantive equality true after excluding only `generated_at`; common panel 4,832; normalized SHA above; control-distance diagnostics reproduced.
- Income coverage regenerated at `2026-07-16T0420`: 21 structures / 246 hypotheses / 70 evolve artifacts / no quality leader; dated and LATEST surfaces byte-identical.
- Schema-v2 handoff and isolated temporary-index deterministic prepare gate are finalizer-owned pre-integration checks; exact results are recorded in `learning-promotion.md` before handoff.

## NEXT

NEXT: `SEC_FORM4_CLUSTERED_INSIDER_BUYING_DIRECTION_F0` — pivot to official point-in-time corporate-information evidence. Before outcome access freeze a fixed liquid panel, Form 4 open-market transaction-code/direct-indirect ownership/amendment/issuer/timestamp rules, cluster threshold, prior-only same-symbol no-reuse controls with distance diagnostics, signed five- or ten-session horizon, and a complete one-lot 18–24 DTE $2-wide call-debit Layered Edge Stack (`capital_fit_usd=200`, planning `max_loss_usd=200` before debit/closing friction, `max_lots=1`). Exercise exactly one named F0→F1 `STRATEGY_ADVANCED` or `FAMILY_CLOSED` decision in the same wake; capability-only EDGAR scaffolding fails closed. Do not inspect this wake's sealed holdouts or retune its credit/overnight screens.

# Trader wake — 2026-07-16T0408 — MOA FINALIZER

Phase: BUILD / L0 underlying discovery
Role: GPT 5.6 Sol finalizer / single writer
Status: **RUN COMPLETE**
Integration: complete; deterministic wrapper integrated/pushed/postflight-verified as `df5a9e50341cb7e3da5f3c1cc7b34047a27a44af`

## Strategy charter and final outcome

The frozen charter exercised `TRAIN_ONLY_DEFINED_RISK_CANDIDATE_FACTORY_V1` on two independent mechanisms and required exactly one claim-bearing decision. The factory is search machinery, not strategy progress.

Accepted outcome: `FAMILY_CLOSED`, `F0_MECHANISM -> F0_MECHANISM`, strategy advancement false, for `CREDIT_RISK_OFF_SPY_BEAR_PUT_21D_V1` / `HIGH_YIELD_CREDIT_DIVERGENCE_FORWARD_DOWNSIDE`.

Economic mechanism: high-yield credit may reprice deteriorating risk appetite before large-cap equities; the exact test asked whether ten-session HYG-minus-IEF weakness inside a still-positive SPY trend leads five-session SPY downside.

Future conditional structure only: one-lot 18–24 DTE $2-wide SPY bear-put debit spread, `capital_fit_usd=200`, frictionless planning `max_loss_usd=200` before debit/closing friction, `max_lots=1`. No option pricing, L1, capital seat, registry, paper, shadow, broker, funding, arm, or live authority exists.

Canonical claim: the run-local canonical factory claim JSON.

- Finalizer raw SHA `2eb3e4c7ebf502de0ac533edcf8a986eb95253189a46922f6f3b7bb75b13f14c`; normalized replay SHA `a4fd731d931185297648b7bde28350c9b17022cf8062b9fc06fa0e76762d30b3`; exact-cache payload equality true after excluding only `generated_at`.
- Exact-date SPY/HYG/IEF panel: **4,832** rows, 2007-05-01 through 2026-07-15.
- Primary train eligible/matched 42/41 across ten years; support 97.6190%.
- Signed event **-0.909825%**, signed prior control **-0.201659%**, paired excess **-0.708167%**, circular three-pair LB90 **-1.360006%**, hit **29.2683%**, worst decile **-4.015427%**.
- Four gates fail: signed event expectancy, paired specificity, uncertainty lower bound, and positive frequency. Density, year count, support, tail floor, and integrity pass but cannot rescue the anti-edge.
- Primary control distance median/max: **153 / 680 sessions**; long lookback is a generalization diagnostic, not a salvage path.
- Primary holdout 28 identities (`83fc5c0f…`) remains outcome-unread; simulation false; option pricing zero.

Dominant failure: the exact trigger predicts the wrong five-session sign and has negative specificity versus prior same-regime controls. A bearish option wrapper would monetize the inverse of the observed train result.

## Independent secondary search information

`OVERNIGHT_SELL_INTRADAY_RECOVERY_SPY_BULL_CALL_21D_V1` / `OVERNIGHT_INTRADAY_DISAGREEMENT_FORWARD_UPDRIFT` remains F0/L0 search information only.

- Train 32/34 matched; support 94.1176%; ten years.
- Event +0.511192%, paired +0.739330%, hit 71.875%, but n32<36 and LB90 -0.200722% fail.
- Control distance median/max is **155.5 / 723 sessions** from direct recomputation of persisted rows; challenger prose median 165 is not reproducible.
- Holdout 24 identities (`40113d83…`) remains unread; option pricing zero.

No F1, second family-close claim, holdout opening, threshold retune, or capital authority is granted.

## Challenger reconciliation

Accepted all substantive judgments: exact primary family close, false advancement, secondary search-only status, sealed holdouts/no-option boundary, dual-ID quarantine, ULP validator repair, zero candidates/leaders/seats, and the Form 4 pivot with same-wake anti-theater discipline.

Closed the nits:

- wrote schema-version-2 `compounding.json` with four unique useful deltas, both closed IDs, complete critic dispositions, data dependencies, and exactly one NEXT;
- registered `POST_REASSESSMENT_INDEPENDENT_DEFINED_RISK_DISCOVERY_V1` at `2026-07-16T0335`, preserving the FOMC epoch as completed context; the 0335 and 0408 no-advance decisions now set streak2 / pivot true / burst false;
- normalized living panel prose to 4,832;
- repaired the factory's machine dominant-failure text to name only the actual failed gates and added a negative-control test;
- promoted primary/secondary control-distance diagnostics without widening or retuning matching;
- independently reran focused/shared/schema and full unittest verification;
- reviewed the complete base diff and untracked set; ignored session logs/preflight stderr remain excluded, while all intended evidence/config/doc/report/code/test paths remain visible.

No economic challenger finding was rejected. The only rejected numeric assertion is secondary control median 165; direct persisted-row recomputation is 155.5.

## Verification

- Focused behavioral/boundary/positive/negative/leakage plus shared OHLCV/FOMC and compounding/epoch suite: `Ran 47 tests in 9.389s`, `OK`.
- Mandated full suite `.venv/bin/python -m unittest discover -s tests`: `Ran 416 tests in 26.777s`, `OK`.
- Strict compile plus `just test`: exit 0; TSLA and TSLL both `STAND ASIDE`; no broker action.
- Exact-cache replay: `SUBSTANTIVE_REPLAY_EQUAL=true`; panel 4,832; raw/normalized hashes above; distance diagnostics reproduced.
- Income coverage regenerated at stamp 0420: 21 structures / 246 hypotheses / 70 evolve artifacts / no leader; dated and LATEST files byte-identical.
- Schema-v2 validate-handoff and isolated temporary-index deterministic prepare gate: finalizer-owned and green; exact machine results are in `reports/trader-wakes/moa/2026-07-16T0408/learning-promotion.md`.

## Durable learning and readiness

New durable capability: future Trader can compare multiple predeclared F0 mechanisms under one completed-session, prior-control, train-only, sealed-holdout contract without counting the factory as strategy progress. Machine failure prose now cannot imply failures in gates that passed.

Economic lesson: the exact HYG-minus-IEF risk-off geometry is a strong five-session bearish anti-edge in train. The overnight/intraday screen has favorable point centers but insufficient density and dependence-aware uncertainty. Long prior-control distances limit local comparability for both and must be reported, not tuned away.

Readiness remains BUILD / NOT READY with zero living candidates, quality leaders, or capital seats. No B3/B4/B6+ gate advanced.

## ONE NEXT

`SEC_FORM4_CLUSTERED_INSIDER_BUYING_DIRECTION_F0`: pivot to official point-in-time corporate-information evidence. Before outcomes freeze a fixed liquid panel, Form 4 open-market transaction-code/direct-indirect ownership/amendment/issuer/timestamp rules, cluster threshold, prior-only same-symbol no-reuse controls with distance diagnostics, signed five- or ten-session horizon, and a complete one-lot 18–24 DTE $2-wide call-debit Layered Edge Stack (`capital_fit_usd=200`, planning `max_loss_usd=200` before debit/closing friction, `max_lots=1`). Exercise exactly one named F0→F1 `STRATEGY_ADVANCED` or `FAMILY_CLOSED` decision in the same wake; capability-only EDGAR scaffolding fails closed. Do not inspect this wake's sealed holdouts or retune its credit/overnight screens.

RUN COMPLETE

Verification path: `reports/trader-wakes/moa/2026-07-16T0408/learning-promotion.md`
Learning path: `reports/trader-wakes/moa/2026-07-16T0408/compounding.json`

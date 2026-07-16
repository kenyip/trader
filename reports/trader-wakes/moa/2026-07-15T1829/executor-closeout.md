# MoA BUILD executor closeout — 2026-07-15T1829

STATUS: EXECUTOR DONE — partial executor phase; finalizer surface owns current completion state
PHASE: BUILD / L0 research only
ROLE: GPT 5.6 Sol executor / only writer
SLEEVE: $3,000 Agentic research sleeve
SESSION: off-hours; cash market closed

## Strategy decision charter (predeclared)

ECONOMIC EDGE MECHANISM: Quarterly earnings resolve a concentrated information uncertainty set. Analyst and investor underreaction may cause the signed first completed post-announcement move to continue over the following five completed sessions relative to prior same-symbol non-event sessions with similar pre-entry trend and realized-volatility state.

CANDIDATE / FAMILY SCOPE: `POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT_CALL_DEBIT_21D_V1` / `POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT` on a frozen present-day liquid operating-company panel selected from current research run 36 before outcomes: AAPL, AMD, SMCI, TSLA, META, GOOGL, ARM, NVDA. TSLL is excluded because it has no issuer earnings event. The panel is a present-day survivor/liquidity screen, not an unbiased historical universe.

CURRENT FUNNEL: `F0_MECHANISM`.

FORECAST TYPE: signed direction continuation after an earnings information event. Primary outcome is paired excess five-session signed return, where each event's direction is the sign of the first completed post-announcement session. Secondary outcome is same-direction hit-rate excess versus controls.

OPTION STRUCTURE: future conditional 21-DTE $2-wide call debit spread after positive first-session reactions and 21-DTE $2-wide put debit spread after negative reactions. The underlying F0 test runs before option pricing. Structural planning bound: `capital_fit_usd=200`, one-lot `max_loss_usd=200` before closing friction, `max_lots=1`; portfolio overlap rule is one global earnings-risk unit and no overlapping event windows.

GREEKS: intended bounded signed delta and convexity; dangerous unintended exposures are long vega into post-event IV crush, long gamma/theta decay, gap risk, sparse multi-leg liquidity, and event-timing errors.

REGIME ENVELOPE: only issuer earnings events with an explicit announcement timestamp/session label and a first completed post-announcement session; stand aside on missing/ambiguous timing, absent price history, overlapping windows, non-finite features, or an event move below the predeclared absolute threshold. No broad-market or non-event entry.

ENTRY TRIGGER: after an issuer earnings announcement whose timing is point-in-time explicit, observe the first fully completed regular session after the announcement; enter at the next regular-session open in the sign of that completed reaction. No same-session signal/entry.

EXIT / MANAGEMENT: primary underlying research horizon is five completed sessions after entry; future option expression would use a 50% profit harvest, close on a completed-session reversal through the post-event signal-session opposite extreme, hard five-session time stop, no roll, and no close-bar re-entry.

EVIDENCE PLAN: first 60% of chronological matched blueprints only. Each event is matched without replacement to an earlier same-symbol non-event session using only pre-entry trend, realized-volatility, and absolute reaction magnitude geometry; control and event outcome windows must not overlap. Final 40% stays outcome-unread. Current option marks are absent; any result is discovery/L0 only.

PREDECLARED FALSIFIER: close at F0 if the data provider cannot supply point-in-time explicit announcement timing for a non-vacuous sample; train has fewer than 40 matched pairs or fewer than 6 symbols; paired five-session signed excess mean is non-positive; one-sided 90% five-pair circular-block-bootstrap lower bound is non-positive; same-direction hit-rate excess is below 5 percentage points; or any chronology, overlap, source-hash, population, strict-JSON, or outcome-unread integrity check fails.

EXACT DECISION THIS WAKE WILL CLOSE: `STRATEGY_ADVANCED` from F0 to F1 only if every discovery gate passes; otherwise `FAMILY_CLOSED`. If the event source lacks point-in-time explicit timing, the closed decision is `EVIDENCE_WAIT` only when no honest independent event-timestamp route can be exercised in this wake.

STAND-ASIDE RULE: no trade-shaped candidate, registry promotion, paper intent, L1/capital seat, shadow, arm, broker, or live action unless the underlying mechanism first advances and later clears claim-appropriate option, cost, path-risk, and live-clock evidence.

## Orientation and freedom audit

- Active epoch `2026-07-15-time-series-breakout-payoff` is completed; its prior success does not authorize reuse of opened holdout evidence.
- Two consecutive epoch-scoped no-advance closes require a materially different mechanism/evidence class. This earnings-event / signed-continuation design is materially different from the closed breakout option expression and post-shock range-compression family.
- Current living quality leader: none; capital path empty; capital-seat bar remains max loss <=$300, window DD <=$75, dual-cost non-vacuity, dense B3, and claim-appropriate option evidence.
- Current research run 36 ranks TSLL/AAPL/MU/AMD/SMCI/TSLA/META/GOOGL/ARM/NVDA; panel choice uses liquid operating companies with issuer events rather than forcing TSLL or a familiar structure.
- Closed families remain quarantined. Prior NEXT is accepted because it satisfies the mandatory pivot and offers a new point-in-time event evidence class; it is not followed merely because it was written.
- Freedom audit: symbol and strategy freedom were preserved; the chosen loop follows the highest-information materially different evidence route, not a caller slot, plumbing path, or diversification quota.

## Outcome

STRATEGY OUTCOME: `FAMILY_CLOSED`
DECISION: `CLOSE_POST_EARNINGS_INFORMATION_DRIFT_TRAIN_FAMILY`
CLOSED FAMILY / QUARANTINE KEY: `POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT`
FUNNEL: remains `F0_MECHANISM`; no F1, L1, capital-seat, registry, paper, shadow, arm, broker, or live authority.

The predeclared discovery gates were exercised on the first 60% of the chronological matched population. The persisted strict-JSON claim artifact is `.cache/platform/post_earnings_information_drift_train_2026-07-15T1829.json` (SHA-256 `a5b256ee4cd47473fcfa799074efb48de1faabcff9f4f018448acba372212f46`). It contains 298 retrospective timestamped issuer events, 126 matched non-overlapping blueprints, 75 train pairs across seven symbols, and 51 outcome-unread holdout blueprints spanning 2022-05-04 through 2026-05-13.

Train evidence decisively falsified the stated mechanism:

- event signed five-session mean: `-0.0048312306693351955`
- matched-control signed five-session mean: `-0.0018400686017785396`
- paired event-minus-control mean: `-0.0029911620675566564`
- paired median: `0.007205961204603817`
- paired positive frequency: `0.5333333333333333`
- one-sided 90% five-pair circular-block-bootstrap lower bound: `-0.016153603629205513`
- event continuation hit rate: `0.4533333333333333`
- control continuation hit rate: `0.4666666666666667`
- hit-rate edge: `-0.013333333333333364`
- integrity violations: `[]`

Density and breadth passed, but the event mean exceeded neither zero nor control, the paired mean and bootstrap lower bound were non-positive, and the hit-rate edge missed the predeclared +5 percentage-point gate. The dominant failure is therefore not data scarcity: broad high-attention issuer earnings reactions did not exhibit average signed five-session continuation versus prior same-symbol, same-sign, non-event reaction controls. The positive median/positive-frequency alongside a negative mean indicates adverse-tail asymmetry, which makes the unconditional mechanism especially unsuitable for a one-lot debit-spread income thesis. The outcome-unread holdout remains sealed because train already failed.

## Search information vs strategy progress

SEARCH INFORMATION: added a reusable timestamp-aware earnings event study with explicit BMO/AMC session mapping, ambiguous-timing stand-aside, source-cache hashes, same-symbol prior controls, event-window exclusion, without-replacement/non-overlap checks, chronological 60/40 partitioning, block-bootstrap gate, strict JSON, complete Layered Edge Stack labels, and structural one-lot risk fields. Added `lxml>=5.0` because `yfinance.get_earnings_dates` requires an HTML parser.

STRATEGY PROGRESS: none. The named family was closed at F0. This capability work is not counted as advancement; it was exercised in-wake to a strategy decision.

## Validity critique

- Leakage/lookahead: event and control outcomes begin after completed signal sessions; controls precede their events and are selected without replacement from pre-event data. A negative control proves changing a selected event's forward exit value does not change that pair. The current retrospective event timestamps are not a point-in-time vendor archive, so the claim is limited to post-announcement mechanism discovery, never pre-event scheduling alpha.
- Timing: explicit BMO events map to the same completed session; AMC events map to the next completed session. Ambiguous regular-session timestamps stand aside. Two in-range TSLA rows (`2020-04-29T12:00:00-04:00`, `2021-10-20T15:00:00-04:00`) were excluded rather than guessed.
- Provenance: all eight adjusted-price and eight event-cache paths exist and match the SHA-256 values embedded in the claim artifact. Prices are split/dividend adjusted closes; earnings timestamps are current retrospective Yahoo Finance downloads.
- Population: the frozen current-rank operating-company panel is complete but has explicit survivorship/listing bias. ARM had no train pair because its shorter listing history falls in the sealed holdout era; the seven-symbol train breadth still exceeded the gate.
- Costs/path realism: no option marks, IV, bid/ask, multi-leg fills, open-price execution, or after-cost PnL were used. The $200 one-lot bound is only the structural maximum debit of a future $2-wide vertical. Proxy-only L0 evidence cannot earn L1.
- Ranking/leader: there is no living capital-path leader, so no competitive promotion comparison exists. The absolute discovery falsifier closed the family.

## Verification snapshot

- Focused behavior/boundary/negative-control suite: `8` tests passed.
- Related low-HV, post-shock, and income-coverage regression suites: `16` tests passed.
- Claim artifact reloaded as strict JSON; chronology and numeric finiteness independently checked; 75/75 train rows passed, source-hash verification returned `all_ok True`.
- Full suite: `.venv/bin/python -m unittest discover -s tests -q` → `Ran 347 tests in 18.072s`, `OK`.
- Coverage refresh: `.venv/bin/python scripts/trader_income_coverage.py --write` refreshed `reports/readiness/income-coverage-LATEST.md` and wrote `reports/readiness/income-coverage-2026-07-15T1845.md`; catalog 21, registry 246, capital leader none.
- Executor phase remains partial by contract: no commit, merge, push, readiness promotion, or `RUN COMPLETE` claim.

## Durable lesson and next seed

DURABLE LESSON: unconditional post-earnings signed continuation on this frozen high-attention panel is not an income edge; its average and hit-rate edge are worse than matched non-event reactions despite a positive median, exposing adverse-tail asymmetry. Do not reopen `POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT` by threshold or symbol churn. Reopening requires a genuinely new economic mechanism and evidence class, such as predeclared fundamental surprise/estimate-revision interaction with point-in-time data, not the same signed-reaction continuation test.

NEXT SEED (exactly one): `BURST_STOP_SEARCH_DESIGN_REASSESSMENT` — this is the third consecutive completed post-advance strategy wake without `STRATEGY_ADVANCED`; stop search volume and diagnose whether current matched-control discovery gates are selecting high-attention families with positive medians but adverse-tail means, then predeclare one materially different mechanism/data class before another strategy experiment.

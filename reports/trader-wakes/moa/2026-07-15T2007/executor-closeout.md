# MOA executor closeout — 2026-07-15T2007

WAKE: 2026-07-15T2007
PHASE: BUILD / L0 research only
ROLE: GPT 5.6 Sol executor / only writer
SESSION: off-hours PDT; adjusted-close sources end 2026-07-14
SLEEVE: $3,000
EXECUTOR STATUS: partial MOA phase complete; challenger/finalizer/integration pending; no `RUN COMPLETE` claim

## Strategy decision charter

ECONOMIC EDGE MECHANISM: downside risk is persistent and heterogeneous across broad and sector ETFs because sector cyclicality, concentration, and risk-transfer demand differ. Inside a lag-safe broad-market uptrend, the single lowest prior downside-semivariance ETF should have lower next-ten-session 5% close-barrier hazard and a milder worst-decile close path than the single highest-semivariance control.

CANDIDATE / FAMILY: `LOW_DOWNSIDE_SEMIVARIANCE_ETF_PCS_21D_V1` / `noncollapse|cross_section_low_downside_semivariance_60d|liquid_etfs_spy_qqq_iwm_xlf_xle_xlk_xli_xlv|spy_sma100_uptrend_positive60d|10session_close_barrier5pct|pcs21d2wide_planned`.

CURRENT FUNNEL: `F0_MECHANISM`.

EXACT WAKE DECISION: `FAMILY_CLOSED`. The exact semivariance-specific non-collapse family remains at `F0_MECHANISM`; holdout and option pricing remain sealed.

PREDECLARED FALSIFIER: close if train has fewer than 60 rank dates/episodes or fewer than six represented symbols on either selected side; low-rank 5% close-barrier breach exceeds 10%; high-minus-low edge is below 5 percentage points; one-sided 90% multi-symbol date-block-bootstrap lower bound is non-positive; the low-rank worst-decile close path is no milder than the high-rank control; downside-semivariance edge is no stronger than the same-date plain-HV diagnostic; or chronology, overlap, source hash, population purity, finite values, strict JSON, unread holdout, or integrity fails. Mean terminal return after a labeled 20-bps underlying sensitivity is diagnostic only.

DECISION CLOSED: the train passed absolute hazard, relative edge, date-block uncertainty, tail, breadth, density, and integrity gates but failed the frozen mechanism-specificity gate. Plain total HV separated the same tail endpoint more strongly, so the semivariance-specific economic claim is not identified.

## Complete Layered Edge Stack

- market / underlying: fixed present-day `SPY, QQQ, IWM, XLF, XLE, XLK, XLI, XLV` panel; broad/sector ETFs reduce single-name earnings concentration but do not remove survivorship, listing-history, composition-change, or current-universe bias
- forecast type: `non_collapse`
- economic mechanism: persistent cross-sectional left-tail heterogeneity from sector cyclicality, concentration, and risk-transfer demand
- option structure: future conditional one-lot PCS on the selected lowest-semivariance ETF; nearest listed 18–24 DTE expiry; sell one 0.18–0.25 delta put and buy one same-expiry put exactly `$2` lower; require at least `$0.30` credit, positive bids, and two-leg NBBO width at most `$0.20`; no pricing at F0
- intended Greeks: positive delta, positive theta, short vega, bounded short gamma
- dangerous Greeks / risks: ETF correlation spike, gap through the long wing, volatility/skew expansion, sector composition drift, early assignment/dividend, and two-leg liquidity
- regime envelope: completed SPY close above its fully warmed prior-completed SMA100 and positive completed 60-session SPY return
- entry trigger: rank eight ETFs after a completed close using 60 completed daily log returns; downside semivariance is 252 times mean squared negative return with non-negative returns set to zero; enter next session in the single lowest-ranked ETF; one global non-overlapping ten-session episode at a time
- exit / management: future PCS plan is 50% credit harvest, close after underlying closes 5% below entry, or hard ten-session time stop; F0 measures fixed ten-session close paths only
- risk / capital fit: `capital_fit_usd=$200`; one-lot structural `max_loss_usd=$200` before credit/closing friction; `max_lots=1`; one global correlated bullish risk unit and no simultaneous ETF positions
- evidence / falsifier: chronological 60% train / outcome-unread 40% holdout; direct 5% close barrier and worst-decile endpoints; high-semivariance control; same-date plain-HV specificity diagnostic; complete-rank-date circular block bootstrap; frozen conjunctive gates above
- confidence stage: exact family closed at F0; no F1/F2/F3/F4/L1/capital-seat claim
- stand-aside: no entry when SPY trend/momentum gates fail, rank inputs are incomplete/nonfinite, later quote/capital filters fail, or another correlated bullish unit is open
- mispricing claim: none; no IV, skew, credit, fill, or option-cost edge was tested

Full pre-outcome charter: `reports/trader-wakes/moa/2026-07-15T2007/strategy-charter.md`.

## Strategy experiment

Evidence: `reports/trader-wakes/moa/2026-07-15T2007/downside-semivariance-etf-train.json`

Provenance and chronology:

- split/dividend-adjusted yfinance daily closes, persisted and SHA-256 hashed by the existing loader
- requested 2010-01-01 through end-exclusive 2026-07-15; common panel 2010-01-04 through 2026-07-14, 4,156 rows per source
- train: 178 globally non-overlapping rank dates from 2010-08-02 through 2019-10-29
- untouched holdout: 119 blueprints with rank dates 2019-11-13 through 2026-06-16 and exits through 2026-07-02; identity SHA-256 `72a6d18430031f03421d27a2680f53d42f099357a5c6685b1b3db2ce1a7dcd5d`; outcomes unread and option simulation not run
- selected-side breadth: all eight ETFs appeared on the low side; seven appeared on the high side; integrity violations `[]`; pricing calls `0`

Train metrics:

- low/high semivariance 5% close-barrier breach rates: `0.0449438202247191 / 0.11235955056179775`
- high-minus-low semivariance breach edge: `0.06741573033707865`
- one-sided 90% complete-rank-date block-bootstrap lower bound: `0.03932584269662921`
- low/high semivariance worst-decile mean minimum close returns: `-0.04917175883244284 / -0.08064732070759122`
- low-rank mean terminal return after labeled 20-bps underlying sensitivity: `0.0045952882915832535`
- same-date plain-HV high-minus-low breach edge: `0.07865168539325842`
- semivariance-minus-plain-HV specificity margin: `-0.011235955056179775`
- semivariance and plain-HV selected the same low symbol on `134/178` rank dates and the same high symbol on `141/178` rank dates

Passing gates: minimum rank-date density, low/high symbol breadth, absolute low-rank breach at or below 10%, relative edge at or above 5pp, positive date-block lower bound, milder low-rank tail, and zero integrity violations.

Failing gate: `semivariance_edge_exceeds_plain_hv` only. The proposed left-tail second-moment selector did not improve tail-hazard separation over the simpler total-volatility rank; it overlapped that rank heavily. Positive absolute hazard quality and relative separation cannot establish the stated semivariance-specific mechanism.

Dominant failure mechanism: mechanism non-specificity. The observed non-collapse separation is better attributed to a broader low-total-volatility ranking until independent evidence says otherwise. This exact downside-semivariance family is quarantined from threshold/lookback/panel retuning. No holdout or option stage was spent.

## Evidence challenge and claim boundaries

- Chronology: all features end at the completed rank close and entry begins next session; outcome windows are globally non-overlapping.
- Dependence: uncertainty resamples complete rank-date rows in circular five-rank-date blocks, preserving low/high symbol outcomes within each date. It is date-blocked, but the fixed ETF panel and overlapping fund holdings still limit generalization.
- Determinism: a current-code cache replay was substantively identical after excluding only `generated_at`; all eight source hashes and holdout identity matched.
- Population: fixed present-day ETF basket, not a point-in-time investable population. High ranks were concentrated in XLE (`107/178`); low ranks were concentrated in SPY (`83/178`) and XLV (`60/178`). Breadth passed but concentration narrows the claim.
- Path fidelity: 5% barrier uses daily closes only and can miss worse intraday lows. It is not an option mark, executable stop, or managed PCS PnL.
- Costs: 20 bps is an underlying-return sensitivity diagnostic, not option costs. It is non-gating for the primary tail claim.
- Option availability / fills: untested; no expiration, strike, credit, NBBO, assignment, or fill evidence exists.
- Holdout: selection identity was frozen and hashed, but no holdout outcomes were read.
- Strictness: evidence writes strict JSON with `allow_nan=False`; finite and fixed-population boundaries fail closed.

These limits cannot rescue the closed family and prevent any F1/L1/paper interpretation.

## Search information versus strategy advancement

SEARCH INFORMATION: yes. The wake added a reusable lag-safe ETF downside-semivariance/direct-barrier lab, complete-rank-date bootstrap, same-date total-HV specificity comparator, sealed-holdout identity, strict capital/Greek/authority labels, and four decision-critical negative/boundary controls. It produced a decisive 178-date train disposition.

STRATEGY ADVANCEMENT: no. The exact family is `FAMILY_CLOSED` at F0. No candidate moved to F1/F2/F3/F4/L1, a capital seat, registry promotion, paper intent, shadow, arm, broker, or live action. The current living leader remains none; absolute capital-seat gates were not invoked.

## Validation

- TDD red states observed for missing module, unimplemented evaluator, and unimplemented payload before implementation
- focused behavioral/boundary/negative-control/integrity suite: `Ran 7 tests in 0.137s — OK`
- Python compile and CLI-help smoke: exit `0`
- actual 10,000-sample train experiment: exit `0`; `FAMILY_CLOSED`; train `178`; holdout `119` unread; pricing `0`
- deterministic current-code replay excluding only `generated_at`: `True`; eight source hashes and holdout identity all equal
- required full suite: `Ran 363 tests in 18.099s — OK`
- income coverage refreshed: 21 structures / 246 hypotheses / 70 evolve artifacts / no living leader
- readiness phase/B checks unchanged; `reports/readiness/LATEST.md` intentionally not rewritten

## Freedom audit

Freedom preserved: the executor independently validated the prior NEXT because it changed population, forecast mechanism, endpoint hierarchy, and dependence treatment; it searched a liquid multi-ETF panel rather than defaulting to TSLA/TSLL, added no instrument/strategy allowlist, and let mechanism-specific evidence—not PCS enthusiasm—close the family.

## Durable learning

A low downside-semivariance ETF rank can satisfy an absolute 5% close-barrier ceiling, relative hazard edge, uncertainty lower bound, and tail-severity gate yet still fail as an economic mechanism when plain total volatility separates the same endpoint more strongly. Mechanism-specificity must remain conjunctive; otherwise a fancier left-tail feature merely relabels the low-volatility effect.

## Exactly one next seed

`LOW_TOTAL_HV_ETF_BARRIER_EXTERNAL_TRAIN_F0`: treat the current 2010–2019 plain-HV comparator as inspected development evidence only, not an advance. Before reading new outcomes, freeze a complete low-total-HV ETF non-collapse stack on an independent pre-2010 development interval (or another genuinely independent population if historical coverage fails), retaining the direct 5% close-barrier, worst-decile, date-block, absolute <=10%, `$2` PCS structural bound, and one-global-unit rules. Keep the current `72a6d184…` 2019–2026 holdout sealed. Do not reopen the semivariance or 14-name low-HV mean-return families; if no independent sample exists, return `EVIDENCE_WAIT` rather than reuse inspected rows.

## Partial-phase boundary

No commit, push, merge, deterministic integration, or `RUN COMPLETE` claim was made. Challenger and finalizer must critique the mechanism-specificity comparator, dependence label, fixed-ETF concentration, close-only barrier, holdout seal, code/tests, exact family quarantine, and one NEXT before integration.

MOA_EXEC_DONE

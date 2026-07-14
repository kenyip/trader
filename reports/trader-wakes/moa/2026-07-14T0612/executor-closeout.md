# MOA BUILD executor closeout — 2026-07-14T0612

PHASE: BUILD / research only / L0 inspected-development mechanism study
SLEEVE_USD: 3000
STATUS: executor partial complete; challenger and finalizer pending
OUTCOME: `FAMILY_CLOSED`; `F0_MECHANISM -> F0_MECHANISM`; strategy advancement false

## Strategy decision charter

- ECONOMIC MECHANISM: when same-close observed VIX is at least 1.25 times fully warmed 20-session SPY realized volatility while SPY closes above SMA200, implied volatility should overstate subsequent 21-session realized volatility often enough to support a small bullish defined-risk put-credit-spread income trade.
- CANDIDATE/FAMILY SCOPE: candidate `SPY_VRP_PCS_VIX_RV_21D_V1` within canonical family `SPY_VRP_VIX_RV_21D`; SPY only; positive-trend signal; same-close VIX/RV20 >=1.25; suppress the next 21 sessions after each treated episode; downstream fixed one-lot 21-DTE approximately 0.20-delta $1-wide PCS, 50% credit target, 2x-credit stop, and mandatory DTE<=1 exit. All 2016–2026 observations are inspected development data, not an untouched holdout.
- FUNNEL: `F0_MECHANISM -> F0_MECHANISM`. Option pricing was allowed only after every assessment and pooled mechanism gate passed.
- PREDECLARED FALSIFIER: close the tested family if any of the three expanding-origin assessment windows has fewer than 10 non-overlapping treated episodes, treated mean under 1 vol point, treated positive frequency under 60%, fewer than 8 outcome-independent matched controls, or matched treated-minus-control mean <=0; also close if pooled density/integrity fails or the circular-block-bootstrap one-sided 95% lower bound is <=0. No threshold, DTE, delta, width, symbol, or management mutation was allowed in-wake.
- EXACT DECISION: `FAMILY_CLOSED`. The high-VIX/RV positive-trend selector did not add stable conditional edge over its matched positive-trend low-ratio controls. No hypothesis was registered.

## Closed outcome

Final canonical strict JSON after the executor's label-only rerun: `reports/trader-wakes/moa/2026-07-14T0612/spy-vrp-pcs-study.json` (SHA-256 `4a22bec0e15e3d71b1163e6528790e951044d27169a5567b0c4c38dc6bdf68fd`). Metrics, gates, and decision are unchanged from the first executor artifact; only generated time and the precise matched-selector failure wording changed. The run used 10,000 circular-block bootstrap samples, 53 non-overlapping treated episodes, and 35 matched controls. Integrity reported zero warmup, episode-overlap, outcome-window, control-duplicate, control-overlap, threshold, or tolerance violations.

Raw treated VIX-minus-forward-RV was positive on 86.79% of episodes with a 3.9484-vol-point pooled mean and 1.1085-vol-point lower bound. That does not validate the selector. The 2020–2021 matched difference was -1.6221 vol points, failing the frozen per-assessment gate; 2022–2023 and 2024–2026 were +1.4107 and +2.6220. The pooled matched mean was +1.0633, but its one-sided 95% lower bound was -2.5507, failing the frozen pooled gate. Dominant failure: a broad volatility premium exists in these inspected rows, but the 1.25 ratio plus trend rule does not show stable incremental selection value across regimes.

The mechanism failure forced option status `NOT_RUN_MECHANISM_GATE_FAILED`, `pricing_calls=0`, candidate_pass=false, and registration_eligible=false. The stated `capital_fit_usd=100`, `one_lot_max_loss_usd=100`, and `max_lots=1` are only the structural upper bound for a $1-wide spread and not an observed fill, modeled PnL result, capital seat, or readiness claim.

## Evidence critique

- SPY adjusted closes and observed VIX are real historical series, but every row is inspected development evidence. There is no untouched F2 partition and no L1 claim.
- Signals use same-close features and only subsequent returns for the outcome. Controls are chosen without outcome values, within fixed VIX/trend tolerances, without replacement, and with non-overlapping forward windows.
- The COVID transition produces extreme treated and control outcomes. Circular three-episode blocks preserve local episode order, but 35 pairs and three coarse assessment windows still leave wide uncertainty and residual matching confounding.
- Positive raw premium is not equivalent to tradable conditional alpha. The matched instability is claim-invalidating, so downstream Black-Scholes PCS pricing, costs, path gates, and paper intent were correctly skipped.
- Quarantine the exact ratio/trend/21-session family and nearby threshold/timing mutants. Reopening requires a genuinely new mechanism or evidence design, not tuning this failed selector.

## Search information (not strategy advancement)

Added the reusable study `scripts/spy_vrp_pcs_study.py` and thirteen behavior/boundary tests in `tests/test_spy_vrp_pcs_study.py`. Full verification also exposed and repaired an unrelated PMCC desk `bid_credit=None` formatting crash with a deterministic regression, relaxed a market-state-dependent preferred-candidate assertion to finite candidate-surface invariants, and repaired the income-coverage generator so TSLL archive density is derived rather than hard-coded. Coverage now states 3/3 dates, newest-date expiration breadth 13 after the separate mid-session recapture, and explicitly labels the three-date floor as plumbing only.

Executor-time verification was later superseded by the challenger's red positive fixture. Finalizer repaired only the synthetic calendar spacing, retained the matched-negative-control half, and reran focused VRP 13/13, PMCC desk 7/7, coverage 1/1, full discovery 262/262, `just platform-smoke`, and compile checks green. Readiness phase and B-checks did not change. No paper, shadow, arm, broker, funding, or live action occurred. Freedom audit: SPY/VRP was selected as a distinct economic-mechanism route; no symbol or structure allowlist constrained the choice.

## NEXT

`POST_VRP_SEARCH_DESIGN_REASSESSMENT`: stop the no-advance experiment burst and audit the remaining reset shortlist for material mechanism/evidence novelty. Authorize at most one future candidate only if its entry feature, outcome-independent control/placebo, chronology, and pre-option falsifier are distinct from the quarantined TOM and VIX/RV selectors; otherwise emit `DIMINISHING_RETURNS` rather than run more familiar PCS volume. Remain BUILD/L0 with no paper/shadow/arm/live action.

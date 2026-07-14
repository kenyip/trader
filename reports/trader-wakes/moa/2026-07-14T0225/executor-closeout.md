# MOA BUILD executor closeout — 2026-07-14T0225

PHASE: BUILD / research only / L0 adjusted-underlying event study
SLEEVE_USD: 3000
STATUS: executor residue closed by finalizer; deterministic integration pending

## Strategy decision charter

- ECONOMIC MECHANISM: predictable beginning-of-month retirement, payroll, and institutional allocation flows create a short bullish SPY drift over the next five completed trading sessions.
- CANDIDATE/FAMILY SCOPE: exact candidate `SPY_TOM_PCS_21D_020D_1W`; SPY only; first completed trading session of each month; five-session hold; conditional downstream one-lot 21-DTE approximately 0.20-delta $1-wide put credit spread with 50% credit target, 2x-credit loss exit, and mandatory five-session exit.
- FUNNEL: `F0_MECHANISM -> F0_MECHANISM`; advancement required both adjusted-underlying partitions and the conditional option stage to pass.
- PREDECLARED FALSIFIER: close `spy-turn-of-month-first-session-5day-pcs-21dte-020delta-1wide-dualcost-60-40-v1` if the outcome-independent underlying event fails any chronological train or untouched-holdout gate versus either the tenth-session placebo or deterministic weekday-matched session-12-to-17 complement; option pricing must not run after underlying failure. If underlying gates pass, close the family unless the exact PCS passes train and holdout dual-cost, density, capital, drawdown, dense-negative-window, and integrity gates. No mutation or alternate symbol/day/DTE/width is allowed.
- EXACT DECISION: `BLOCKER_REMOVED_AND_RETESTED` with retest decision `FAMILY_CLOSED`; strategy advancement false.

## Closed outcome

Canonical strict-JSON evidence: `reports/trader-wakes/moa/2026-07-14T0225/spy-tom-event-study.json` (SHA-256 `fb81bf035093ce0db07c3e4fcf43bba292d1e8f8bf272ac52b8c5b6416842e9c`). The population-purity repair retains the complete November 2018 month even though its deterministic weekday complement is calendar-impossible. The unchanged experiment has 126 months, 75 chronological train events, and 51 untouched-holdout events. Event-minus-complement means are `-0.0007316349154277522` train and `-0.0023542854031338863` holdout; bootstrap 90% lower bounds are negative versus placebo and complement in both partitions. Holdout event drawdown frequency at or below -2% is `0.3333333333333333` versus complement `0.2549019607843137`.

The underlying gate failed, so `pricing_calls=0`, option status is `NOT_RUN_UNDERLYING_GATE_FAILED`, candidate_pass and registration_eligible are false, and no option PnL claim exists. Structural one-lot bound is `capital_fit_usd=100`, `one_lot_max_loss_usd=100`, `max_lots=1`; it is not an observed fill or capital seat. The rejected hypothesis is audited as `hyp_spy_turn_of_month_pcs_21d_020d_1w` and linked to the tracked evidence.

## Finalizer reconciliation

- Accepted the challenger’s no-advance classification, exact-family quarantine, merged reassessment NEXT, readiness correction, and burst-stop guard.
- Repaired the dormant option branch so its 30-session volatility proxy is shifted to use prior completed bars only; a same-bar shock boundary test now proves the lag.
- Repaired evidence serialization so the unavailable November 2018 complement is JSON `null`, never non-standard `NaN`; strict `allow_nan=False` generation is tested.
- Exact rerun after both repairs preserved all decision metrics and `pricing_calls=0`.

No living leader, B-check, paper seat/order, shadow state, agentic arm, broker session, funding, or live authority changed. Symbol/strategy freedom remained open; this calendar-flow route was chosen as a distinct evidence class rather than TSLA/TSLL or options-filter habit.

## NEXT

`SEARCH_DESIGN_REASSESSMENT_AFTER_TOM_CLOSE`: inventory remaining open, non-quarantined economic mechanisms and select exactly one outcome-independent underlying pre-screen with placebo/complement controls and chronological train-to-untouched-holdout evaluation before option pricing; if no materially novel mechanism can be stated, stop and redesign rather than buy familiar PCS volume. Do not reopen TOM day/DTE/width/symbol mutants or nearby options-filter volume; remain BUILD/L0 with no paper/shadow/arm/live action.

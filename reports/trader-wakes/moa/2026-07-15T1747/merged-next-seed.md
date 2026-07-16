# Merged NEXT seed — 2026-07-15T1747 (challenger)

ONE seed only. Prior executor month-end calendar-flow seed is superseded (too near closed TOM / OPEX / month-end ranking families). Post-shock range-compression family stays quarantined.

## NEXT

`POST_EARNINGS_INFO_RESOLUTION_DRIFT_F0`

Predeclare a train-only, outcome-independent event study on a **fixed liquid multi-name panel** chosen from the current full-universe research rank **before** train outcomes:

Economic mechanism (new vs this wake and vs closed calendar TOM/OPEX):
- A scheduled earnings announcement resolves information asymmetry. After the first **completed** post-announcement session is known, temporary attention/liquidity and inventory effects may leave a short residual drift and/or tighter path than same-symbol ordinary non-event weekday controls — **or** may not. This is information-resolution, not pure month-end rebalancing and not the failed post-shock range-compression claim.

Design gates (freeze before looking at train outcomes):
1. Use only announcement timing that could be known without future leakage (prior completed event calendar / known schedule; no same-bar use of unreleased prints). Prefer symbols with durable event history; fail closed when event provenance is missing.
2. Entry = next session after the first completed post-event bar (or a predeclared equivalent lag that avoids using the announcement bar’s full close as both signal and price without lag — state the exact rule).
3. Measured underlying outcome only at F0: predeclare one primary (e.g. five-session signed drift **or** path range + terminal pin — pick one primary and one secondary before run). Do **not** price options until the underlying gate passes.
4. Controls: prior-only same-symbol matched non-event observations (weekday and/or 20d return + HV covariates), without replacement, non-overlapping outcome windows, chronological first 60% train only; final 40% holdout outcome-unread.
5. Predeclared falsifier examples (set exact thresholds in the charter before run): non-vacuous train pair/symbol floors; paired treated-minus-control mean on the primary metric; one-sided 90% block-bootstrap lower bound; integrity/chronology/reuse checks; optional downside-tail gate if the planned later structure is long-biased credit/debit.
6. If underlying F0 fails → `FAMILY_CLOSED` and quarantine the exact event/control/horizon family. No subset salvage, no threshold mining, no reopening closed `POST_SHOCK_RANGE_COMPRESSION_MATCHED_CONTROL`, TOM, OPEX, or monthly 12-1 momentum families.
7. If underlying F0 passes → only then freeze a capital-fit one-lot defined-risk expression (prefer bull put / put credit or a long-biased debit vertical aligned to the signed drift sign) with `capital_fit_usd`, one-lot `max_loss_usd` ≤$300 planning bound, `max_lots=1`, dual multi-leg costs, and still L0 discovery only — no L1/seat/paper force.

Stand-aside / authority:
- Missing event provenance, failed gate, unavailable package, correlated unit open, or risk above sleeve bounds → no trade.
- Discovery bar only. No registry auto-promote, paper force, shadow, arm, broker, or live action.

Why this seed:
- Material mechanism pivot after accepted post-shock `FAMILY_CLOSED` (and no-advance streak → 2).
- Avoids calendar-seasonality thrash (TOM/OPEX/month-end).
- Keeps preferred income path available (defined-risk premium or directional debit) **after** an honest underlying pre-screen.
- Reuses proven matched-control + holdout-secrecy lab patterns without reopening quarantines.

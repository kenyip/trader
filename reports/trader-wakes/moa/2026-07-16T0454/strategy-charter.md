# Strategy decision charter — 2026-07-16T0454

PHASE: BUILD / L0 discovery only
SLEEVE: $3,000
ROLE: GPT 5.6 Sol executor / only writer
MARKET SESSION: premarket, 2026-07-16 PDT

## Chosen closed loop

Test one materially different, official point-in-time corporate-information mechanism: whether clustered, direct, open-market common-share purchases by multiple officers/directors, disclosed on SEC Form 4, predict ten-session issuer upside beyond prior same-symbol controls. This supersedes any unchanged market-price, scheduled-macro, cross-sectional, credit, or daily PCS retune because the active epoch is at two no-advance decisions and requires a genuinely different mechanism/evidence class.

## Decision contract

- Economic mechanism: officers/directors who spend their own capital on open-market common shares may possess issuer-specific valuation or operating information not yet fully incorporated in price. Two distinct qualified owners disclosing purchases within 20 calendar days should carry more information than one isolated purchase; delayed diffusion may support a ten-session bullish drift after the cluster becomes public.
- Candidate: `SEC_FORM4_CLUSTERED_INSIDER_BUYING_CALL_21D_V1`.
- Family: `SEC_FORM4_CLUSTERED_OPEN_MARKET_BUYING_FORWARD_UPDRIFT`.
- Funnel: `F0_MECHANISM -> F1_TRAIN` only if every frozen discovery gate passes; otherwise `F0_MECHANISM -> F0_MECHANISM` and `FAMILY_CLOSED`.
- Exact decision this wake closes: `STRATEGY_ADVANCED` or `FAMILY_CLOSED` for the named candidate/family. Capability-only SEC scaffolding is not an acceptable outcome.
- Claim authority: L0 underlying discovery only. No historical option pricing, L1, capital seat, registry promotion, paper intent, shadow, broker, funding, arm, or live authority.

## Frozen evidence geometry

- Official source: SEC Insider Transactions Data Sets quarterly Form 3/4/5 archives. Source ZIP hashes and archive labels must be persisted.
- Fixed present-day research panel, frozen before outcome evaluation: `AAPL, MSFT, NVDA, AMZN, META/FB, GOOGL, AMD, NFLX, TSLA, COIN, PLTR, SMCI, AVGO, MU, JPM, XOM, BAC, F, SOFI, AAL, PFE, SNAP, CCL`.
- Qualified filing/transaction: original Form 4 only; non-derivative transaction code `P`; acquired `A`; direct ownership `D`; officer or director reporting owner; common-equity security title; finite positive shares and price; transaction value at least $10,000; filing date from transaction date 0–5 calendar days; amendments, derivatives, indirect ownership, ten-percent-owner-only rows, missing issuer mapping, and ambiguous rows fail closed.
- Cluster: at least two distinct qualified reporting-owner CIKs in one issuer within 20 calendar days and aggregate qualified purchase value at least $100,000. Signal date is the filing date on which the threshold first becomes knowable; overlapping 20-day signals are suppressed.
- Entry/exit: first completed trading-session close strictly after the public filing signal; exit at the tenth subsequent session close. Underlying round-trip hurdle is 10 bps. No option marks are called at F0.
- Specificity control: one deterministic, prior-only, same-symbol, no-reuse, non-event control with the same broad-market SMA100 state and nearest prior 20-session issuer return, absolute return distance no more than five percentage points. Its ten-session outcome must be fully realized before the event filing date. Persist median/max session distance and unmatched reasons.
- Chronology: sort matched blueprints by signal date; assess only the first 60%; keep the final 40% identity-only and outcome-unread.

## Predeclared discovery falsifier

The family closes at F0 unless train has all of:

1. at least 24 matched event/control pairs;
2. signals across at least six calendar years and six distinct symbols;
3. at least 70% control support;
4. signed event mean after 10 bps greater than +0.25%;
5. paired event-minus-control mean greater than +0.20%;
6. one-sided 90% circular three-pair-block bootstrap lower bound greater than zero;
7. positive-return frequency at least 55%;
8. signed event-return worst-decile mean after the 10-bps hurdle no worse than -8%;
9. zero source, chronology, control-reuse, future-control, overlap, or holdout-read integrity violations.

No gate may be relaxed after seeing outcomes. A passing point estimate with a non-positive dependence-aware lower bound is a close, not an advance.

## Complete Layered Edge Stack

- Market/underlying: fixed liquid US single-name panel above; current-symbol survivorship and filing-time ticker changes are explicit L0 limitations.
- Forecast type: issuer-specific bullish directional drift for ten sessions after public clustered insider buying.
- Economic mechanism: insider own-capital information/valuation signal plus gradual public assimilation.
- Option structure: future conditional one-lot 18–24 DTE $2-wide bull-call debit spread; long call near 0.55 delta, short call $2 higher. The F0 test evaluates underlying direction only.
- Intended Greeks: positive delta, limited positive gamma/vega, capped debit risk, less capital than shares.
- Dangerous Greeks/exposures: negative theta, volatility crush, weak upside participation after debit, gap risk, assignment/exercise and closing-friction boundaries not measured at F0.
- Regime envelope: public, timely, direct open-market officer/director buying; liquid common equity; no ambiguous amendment/derivative/indirect transaction. Broad-market regime is matched in controls rather than post-hoc filtered. Stand aside in missing-source, stale/late filing, ambiguous issuer/security, or option-liquidity states.
- Entry trigger: the first public filing date that makes the frozen two-owner/$100k/20-day cluster knowable; option entry would be no earlier than the next completed trading session.
- Exit/management: future option plan closes at +50% spread value, -50% of paid debit, or the tenth session, whichever comes first; no averaging, rolling, or same-bar re-entry. F0 measures the fixed ten-session underlying horizon only.
- Risk/capital fit: `capital_fit_usd=200`; planning frictionless structural `max_loss_usd=200` before debit/closing friction; `max_lots=1`; one risk unit; no concurrent same-symbol position; portfolio overlap must remain within the sleeve's 25–30% open-risk aim. Actual debit/path loss is unmeasured and cannot earn a capital seat.
- Evidence/falsifier: official SEC source + frozen train-only controls and gates above; holdout sealed; no option marks.
- Confidence: `F0_MECHANISM`, `L0 BUILD` before the run; at most `F1_TRAIN`, still `L0`, after a full discovery-gate pass.
- Stand-aside: no qualified cluster, ambiguous SEC row, missing point-in-time source coverage, control support failure, bearish/illiquid future option setup, debit above $200, spread width/quote quality failure, or any risk-governor conflict.

## Freedom audit

Symbol and strategy freedom remain intact: this wake chooses an official corporate-information evidence class and a defined-risk bullish debit expression because it is materially independent of the active epoch's closed market-price/macro/credit families, not because NEXT is an order.

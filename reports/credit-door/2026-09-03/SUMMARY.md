# Agentic sleeve — next credit door (analysis only)

As-of **2026-09-03**. No live orders. Multi-leg send is rejected on this sleeve; 1-leg LIMIT only.

## Crown

**CROWN: null.** No survivor beat MRK on sendable ROC while staying fillable under $855.

MRK MEASURED remains the paper credit champion: +$27.08 n=15. Live MRK Oct-16 140/135 is a *new* strike (allowed) but is not crowned unless MODEL ROC clears that bar.

## Live book (do not add a second cash-fail lot)

- Agentic ••••8507: cash $854.90, BP $784.86, account $984.9.
- Occupant: OKE Oct-16 2026 100/105 bull-call debit, net 1.40 (long 100C @2.25, short 105C @0.85).
- Working GTC BTC on the short 105C at 0.70 (agentic, confirmed, unfilled) — left untouched.
- Free BP today cannot fund an ~$880 second lot (MPC 340/330 class). Coexist requires lock ≤ live BP.

## DNA

- Defined risk only. BUY the long wing first so a missed short leaves a long option, not a naked short.
- Credit/width ≥ 10%; |Δ| ≤ 0.30; IVR ≥ 20; combined half-spread ≤ 40% of credit; earnings outside the hold; lock ≤ $855.
- Discard list honored (TRGP, refiners, INTU/HUM, CAT/DE, DG/JNJ/MRK unless new strike/expiry, MCD CCS, V, PFE, XOM CCS, banks, REGN/AMGN, LNG, stale Aug-26 LOW/TGT/BMY).

## Candidates

| Name | Struct | Expiry | Strikes | Credit | Lock | Δ | DNA | MODEL avg (n) | ROC |
|---|---|---|---|---:|---:|---:|---|---:|---:|
| KO | put_credit_spread | 2026-10-16 | 85.0/80.0 | 0.58 | $442.0 | 0.2244 | PASS |  |  |
| KO | put_credit_spread | 2026-10-16 | 85.0/82.5 | 0.39 | $211.0 | 0.2244 | PASS |  |  |
| T | put_credit_spread | 2026-10-16 | 25.0/23.0 | 0.3 | $170.0 | 0.2765 | PASS |  |  |
| T | put_credit_spread | 2026-10-16 | 25.0/22.0 | 0.34 | $266.0 | 0.2765 | PASS |  |  |
| MO | put_credit_spread | 2026-10-16 | 65.0/62.5 | 0.28 | $222.0 | 0.1793 | PASS |  |  |
| MO | put_credit_spread | 2026-10-16 | 67.5/60.0 | 1.14 | $636.0 | 0.3111 | delta_hot |  |  |
| CVS | put_credit_spread | 2026-10-16 | 92.5/85.0 | 1.01 | $649.0 | 0.2567 | PASS |  |  |
| CVS | put_credit_spread | 2026-10-16 | 92.5/80.0 | 1.31 | $1119.0 | 0.2567 | lock_over_cash |  |  |
| INTC | put_credit_spread | 2026-10-16 | 80.0/75.0 | 1.04 | $396.0 | 0.2205 | PASS |  |  |
| MRK | put_credit_spread | 2026-10-16 | 140.0/135.0 | 0.74 | $426.0 | 0.2005 | PASS |  |  |
| MRK | put_credit_spread | 2026-10-16 | 145.0/135.0 | 2.04 | $796.0 | 0.3053 | delta_hot |  |  |
| KO | call_credit_spread | 2026-10-16 | 92.5/97.5 | 0.68 | $432.0 | 0.291 | PASS |  |  |
| WMT | call_credit_spread | 2026-10-16 | 115.0/120.0 | 0.79 | $421.0 | 0.2739 | PASS |  |  |
| WMT | call_credit_spread | 2026-10-16 | 115.0/125.0 | 1.1 | $890.0 | 0.2739 | lock_over_cash |  |  |
| MPC | put_credit_spread | 2026-10-16 | 340.0/330.0 | 0.3 | $970.0 | 0.18 | discard_prior_hunt,width_skinny,spread_vs_premium,lock_over_cash |  |  |
| SLB | put_credit_spread | 2026-10-16 | 55.0/50.0 | 0.5 | $450.0 | 0.22 | earnings_inside_hold |  |  |

## Labels

- **MODEL** = `pcs_sim.run_pcs_backtest` Black-Scholes daily marks (this engine). Not fills.
- **MEASURED** = prior-cell paper/live NBBO result. MRK +$27.08 n=15 is MEASURED.
- n is printed on every average.

## Scale ticket

Think in 1-lot defined max loss, then add lots only after Ken wires. Today's sleeve sizes to $855 post-OKE-flat, ~$785 while OKE is on.

## Authority

Analysis only. No `place_option_order`. No arm. No main-account use.


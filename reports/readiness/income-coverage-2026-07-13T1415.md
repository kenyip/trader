# Income strategy coverage — 2026-07-13T1415

Source: `scripts/trader_income_coverage.py` · doctrine: `docs/INCOME_STRATEGY_COVERAGE.md`

- Catalog structures: **21**
- Hypotheses: **245** ({'paper': 1, 'testing': 14, 'candidate': 230})
- Evolve sim artifacts: **67** under `.cache/platform/evolve_backtests/`
- Quality leader hint: `none; former reference hyp_dna_tsll_put_credit_spread_b195f5fe failed listed-expiry restress quality bar`

## Catalog × registry

| structure | engine | side_policy | n_hyps | statuses |
|---|---|---|---:|---|
| `bear_put_debit_spread` | debit_vertical_sim | bearish_not_bullish | 5 | {'candidate': 5} |
| `broken_wing_iron_butterfly` | iron_butterfly_sim | bullish_not_bearish_credit | 5 | {'candidate': 5} |
| `bull_call_debit_spread` | debit_vertical_sim | bullish_not_bearish | 9 | {'candidate': 9} |
| `butterfly_spread` | butterfly_sim | neutral_to_bullish_pin | 15 | {'candidate': 15} |
| `calendar_spread` | calendar_sim | time_decay_neutral_to_bullish | 17 | {'candidate': 17} |
| `call_credit_spread` | pcs_sim | prefer_call | 9 | {'candidate': 9} |
| `cash_secured_put` | single_leg | prefer_put | 18 | {'candidate': 18} |
| `collared_covered_call` | collar_sim | bullish_income_collar | 0 | — |
| `diagonal_spread` | diagonal_sim | bullish_time_decay | 7 | {'candidate': 7} |
| `double_diagonal_spread` | double_diagonal_sim | neutral_high_iv_time_decay | 0 | — |
| `iron_butterfly` | iron_butterfly_sim | neutral_pin_credit | 7 | {'candidate': 7} |
| `iron_condor` | pcs_sim | range_bound | 6 | {'candidate': 6} |
| `long_dte_conservative` | single_leg | regime_directed | 5 | {'candidate': 5} |
| `put_credit_spread` | pcs_sim | prefer_put | 25 | {'testing': 3, 'candidate': 22} |
| `put_ratio_backspread` | put_ratio_backspread_sim | bearish_convexity | 8 | {'candidate': 8} |
| `regime_short_premium` | single_leg | regime_directed | 14 | {'testing': 1, 'candidate': 13} |
| `roll_defend` | single_leg | regime_directed | 15 | {'testing': 1, 'candidate': 14} |
| `short_call_credit` | single_leg | prefer_call | 11 | {'candidate': 11} |
| `short_dte_aggressive` | single_leg | regime_directed | 14 | {'testing': 2, 'candidate': 12} |
| `short_put_credit` | single_leg | prefer_put | 16 | {'candidate': 15, 'testing': 1} |
| `wheel_assignment` | single_leg | prefer_put | 30 | {'candidate': 28, 'testing': 2} |

## Gaps (BUILD targets)

- calendar_spread — explicit front/back IV + put-skew assumptions and chronological OOS built; observed historical option-surface inputs missing
- double_diagonal_spread — same-strike/inward protective four-leg BS daily-bar scaffold with American intrinsic floors, signed four-leg percentage/fixed-dollar costs, observed-path loss capital sizing, enforced one-lot operating cap with theoretical capacity separately labeled, and a reproducible eight-symbol chronological reject-unless lab built; 0/8 symbols passed both train/holdout cost axes, no hypothesis was registered, and observed option surfaces/assignment calibration remain missing
- diagonal_spread — BS defined-debit scaffold + B3/B4 + exact-DNA OOS/density plus announcement-time dividend/short-call assignment boundary built; AAPL has bounded 40/40 issuer corroboration for announcement date/amount/common-stock identity from 2016-07-26 through 2026-04-30, while the independent explicit-ex-date inventory covered only the latest 20/40 target events and closed that narrow route at partial L0; ambiguous/unsupported symbols fail closed and observed option surfaces remain missing
- convex/ratio family — long call, symmetric/broken-wing credit iron butterflies, and a 1x2 put ratio backspread have B3/B4/fixed-cost dispatch; ratio cost survivors still fail absolute DD/risk gates, and observed surfaces/assignment remain missing
- debit_vertical — bull-call and bear-put BS defined-debit scaffold + evolve/B3/B4 built; bull-call can use the archived Nasdaq declaration-date provider on supported eventful listings with bounded AAPL issuer corroboration for announcement date/amount/common-stock identity only, while the explicit-ex-date inventory was incomplete at 20/40 and observed surfaces plus short-put assignment remain missing
- collared_covered_call — capital-honest scaffold plus 1,152-row DTE/delta/management grid built; 258 rows were positive on both proxy cost axes but zero met the $75 window-DD gate, so the family is rejected this cycle; dividends/assignment unmodeled and no proxy SHIP registered
- time-bucket scoreboard — multi-hyp DTE/profit-target/DTE-stop + entry-weekday/cost grid plus a completed-30-minute open/midday/late PCS/CCS/IC chronological dual-cost lab are built; append-safe 30-minute and daily-feature archives produced 60 usable dates from 60 raw dates (36 train / 24 holdout), but the locked 8-symbol rerun still rejected at L0 with only 1/24 train dual-cost passes and 0/24 complete train+holdout passes
- direction/volatility-bias lab — shared-window scoreboard + no-lookahead shared-position PCS/CCS/IC router built; asymmetric capped-jade IC, daily close-shock/momentum/pullback/vol-compression PCS, multi-horizon trend-pullback PCS, and bearish volatility-expansion CCS families failed complete proxy gates, so they remain rejected pending a genuinely new edge or observed-data density
- cost realism — exact PCS/CCS/IC leg/time join + reject gate, Friday abstraction, archive-backed date-aware expiry/strike-grid provider, and all-expiration atomic append capture built; density gate fails closed below three market dates, and the current TSLL archive covers 2/3 dates, so provider-backed historical simulation and observed-cost calibration remain blocked

## BUILD lab recipe

1. Dual MoA: `just trader-build-lab`
2. Rotate under-covered structures / time / direction axes
3. Falsify new SHIP with B3+B4 + ml/dd quality bar
4. RTH: wait for filters → paper open/close only

Paper/research only. No live.

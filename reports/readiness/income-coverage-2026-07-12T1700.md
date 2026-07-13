# Income strategy coverage — 2026-07-12T1700

Source: `scripts/trader_income_coverage.py` · doctrine: `docs/INCOME_STRATEGY_COVERAGE.md`

- Catalog structures: **20**
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
- diagonal_spread — BS defined-debit scaffold + B3/B4 + exact-DNA OOS/density built; observed option surfaces and assignment realism missing
- convex/ratio family — long call, symmetric/broken-wing credit iron butterflies, and a 1x2 put ratio backspread have B3/B4/fixed-cost dispatch; ratio cost survivors still fail absolute DD/risk gates, and observed surfaces/assignment remain missing
- debit_vertical — bull-call and bear-put BS defined-debit scaffold + evolve/B3/B4 built; observed option surfaces, dividends, and assignment missing
- collared_covered_call — capital-honest scaffold plus 1,152-row DTE/delta/management grid built; 258 rows were positive on both proxy cost axes but zero met the $75 window-DD gate, so the family is rejected this cycle; dividends/assignment unmodeled and no proxy SHIP registered
- time-bucket scoreboard — multi-hyp DTE/profit-target/DTE-stop + entry-weekday/cost grid, lagged completed-bar close-shock filters, and chronological selection/holdout falsification built; session-time slices missing
- direction/volatility-bias lab — shared-window scoreboard + no-lookahead shared-position PCS/CCS/IC router built; asymmetric capped-jade IC, close-shock/momentum/pullback/vol-compression PCS families, and a bearish volatility-expansion CCS family failed complete proxy gates, so they remain rejected pending a genuinely new edge or observed-data density
- cost realism — exact PCS/CCS/IC leg/time join + reject gate, Friday abstraction, archive-backed date-aware expiry/strike-grid provider, and all-expiration atomic append capture built; density gate fails closed below three market dates, and the current archive still covers only one, so provider-backed historical simulation and observed-cost calibration remain blocked

## BUILD lab recipe

1. Dual MoA: `just trader-build-lab`
2. Rotate under-covered structures / time / direction axes
3. Falsify new SHIP with B3+B4 + ml/dd quality bar
4. RTH: wait for filters → paper open/close only

Paper/research only. No live.

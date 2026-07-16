# Strategy decision charter — 2026-07-15T2007

WAKE: 2026-07-15 20:07 PDT
PHASE: BUILD / L0 research only
SLEEVE: $3,000
CHOSEN LOOP: test one materially distinct cross-sectional downside-semivariance ETF non-collapse mechanism under the active tail-hazard epoch. This accepts the prior NEXT because it changes the population, mechanism, endpoint hierarchy, and dependence design rather than retuning the closed recent-downshock or low-HV mean-return families.

## Decision charter

ECONOMIC EDGE MECHANISM: Downside risk is persistent and heterogeneous across broad/sector ETFs because sector cyclicality, concentration, and risk-transfer demand create stable differences in left-tail exposure. Inside a lag-safe broad-market uptrend, the contemporaneous lowest downside-semivariance ETFs should have a lower next-ten-session 5% close-barrier hazard and milder worst-decile close path than the highest downside-semivariance ETFs. This is a non-collapse forecast, not a mean-return or plain-volatility forecast.

CANDIDATE / FAMILY: `LOW_DOWNSIDE_SEMIVARIANCE_ETF_PCS_21D_V1` / `noncollapse|cross_section_low_downside_semivariance_60d|liquid_etfs_spy_qqq_iwm_xlf_xle_xlk_xli_xlv|spy_sma100_uptrend_positive60d|10session_close_barrier5pct|pcs21d2wide_planned`.

CURRENT FUNNEL: `F0_MECHANISM`.

EXACT WAKE DECISION: `STRATEGY_ADVANCED` from `F0_MECHANISM` to `F1_TRAIN` only if every frozen train discovery gate passes; otherwise `FAMILY_CLOSED` for this exact mechanism. Holdout and option pricing remain sealed unless F1 is earned.

PREDECLARED FALSIFIER: close the exact family if the chronological train has fewer than 60 cross-sectional rank dates / low-rank episodes / high-rank control episodes, fewer than 6 represented symbols across either selected side, low-rank 5% close-barrier breach rate above 10%, high-minus-low breach edge below 5 percentage points, a non-positive one-sided 90% multi-symbol date-block-bootstrap lower bound, low-rank worst-decile minimum close return no milder than high-rank control, downside-semivariance breach edge no stronger than the same-date plain-HV rank diagnostic, or any chronology, overlap, source-hash, population-purity, finite-value, strict-JSON, unread-holdout, or integrity failure. Mean terminal return after a labeled 20-bps underlying sensitivity is diagnostic only and cannot rescue or kill the primary tail claim.

## Complete Layered Edge Stack

- market / underlying: fixed liquid ETF panel `SPY, QQQ, IWM, XLF, XLE, XLK, XLI, XLV`; broad and sector ETFs reduce single-name earnings/event concentration but do not remove survivorship, listing-history, composition-change, or present-day-universe bias
- forecast type: `non_collapse`
- economic mechanism: persistent cross-sectional left-tail heterogeneity from sector cyclicality/concentration and risk-transfer demand; lowest prior downside semivariance should identify less fragile bullish exposure within a broad uptrend
- option structure: future conditional one-lot put credit spread on the selected lowest-semivariance ETF, nearest listed 18–24 DTE expiry; sell one 0.18–0.25 delta put and buy one same-expiry put exactly `$2` lower; require at least `$0.30` credit, positive bids, and two-leg NBBO width at most `$0.20`; no pricing at F0
- intended Greeks: positive delta, positive theta, short vega, bounded short gamma
- dangerous Greeks / risks: cross-ETF correlation spike, gap through the long wing, volatility/skew expansion, sector composition drift, early assignment/dividend, and two-leg liquidity
- regime envelope: completed SPY close above its fully warmed prior-completed SMA100 and positive completed 60-session SPY return; invalid in a broad-market downtrend or on any data/integrity failure
- entry trigger: rank the eight ETFs after a completed signal close using the prior 60 completed daily log returns; downside semivariance is the mean squared negative log return with non-negative returns contributing zero; enter next session in the single lowest-ranked ETF, with one global non-overlapping ten-session episode at a time
- exit / management: future option plan is 50% credit harvest, close after the underlying closes 5% below entry, or hard ten-session time stop; the F0 test measures fixed ten-session close paths only
- risk / capital fit: `capital_fit_usd=$200`; one-lot structural `max_loss_usd=$200` before credit and closing friction; `max_lots=1`; one global correlated bullish risk unit and no simultaneous ETF positions in an eventual paper plan
- evidence / falsifier: chronological 60% train / outcome-unread 40% holdout; direct barrier and worst-decile endpoints; high-semivariance control; same-date plain-HV specificity diagnostic; multi-symbol date-block bootstrap; frozen gates above
- confidence stage: F0 / L0 discovery only before execution
- stand-aside: no entry when SPY is below the lag-safe SMA100, SPY 60-session return is non-positive, group ranking is incomplete/nonfinite, quote/capital constraints later fail, or another bullish risk unit is open
- mispricing claim: none; no IV, skew, credit, fill, or option-cost edge is claimed at F0

## Frozen design

Data are split/dividend-adjusted daily closes requested from `2010-01-01` through end-exclusive `2026-07-15`, persisted and SHA-256 hashed by the existing adjusted-history loader. Signals consume completed closes only; entry is next session. Rank dates are greedily selected in the valid regime and globally separated so ten-session outcome windows do not overlap. The low/high selections are the single minimum/maximum ranks across eight ETFs; ties break by symbol. The final chronological 40% of frozen rank-date blueprints remains outcome-unread.

The primary endpoints are the low-rank absolute 5% close-barrier breach rate, high-minus-low breach-rate edge, date-blocked uncertainty, and worst-decile minimum close return. The same-date 60-session annualized total-HV minimum/maximum rank is a mechanism-specificity diagnostic: downside-semivariance must produce a strictly stronger barrier edge. Mean terminal return after 20 bps is diagnostic only. Daily-close barriers can miss intraday lows and do not represent option marks, executable stops, or managed PCS PnL.

No L1, capital seat, registry promotion, paper force, shadow, arm, broker, or live authority can result from this executor phase.

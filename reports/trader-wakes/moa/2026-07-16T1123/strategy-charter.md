# Strategy decision charter — 2026-07-16T1123

WAKE: 2026-07-16T1123 PDT (RTH metadata; BUILD/L0 executor phase)
PHASE: BUILD / research only
SLEEVE_USD: 3000
CHOSE: official 2s10s bull-steepening → regional-bank relative updrift train-only discovery

## Why this loop

The active epoch has one counted no-advance and no pivot/burst-stop. The living leader and capital path are empty. The prior NEXT proposed validating a fixed-duration Treasury-ETF proxy before looking at KRE outcomes. I supersede only the proxy construction, not the economic question: the U.S. Treasury daily par-yield curve provides direct point-in-time 2-year and 10-year par-yield observations and avoids Treasury-ETF composition, duration drift, roll, distribution, and credit/beta contamination. The official Treasury CSV route was reachable before charter freeze. This is a materially different repeated-exposure mechanism from the closed broad-index overnight-absorption family.

No KRE or XLF forward outcome was inspected before this charter. Exposure thresholds, chronology, controls, partition, gates, and option-planning boundaries below are frozen first.

## Decision

Test exact candidate `OFFICIAL_2S10S_BULL_STEEPENING_KRE_BULL_CALL_21D_V1` / family `OFFICIAL_YIELD_CURVE_BULL_STEEPENING_REGIONAL_BANK_RELATIVE_UPDRIFT` from `F0_MECHANISM`.

Close exactly one strategy decision:

- `STRATEGY_ADVANCED` only if the frozen train-only discovery conjunction passes, moving the named candidate `F0_MECHANISM -> F1_TRAIN`; otherwise
- `FAMILY_CLOSED` at `F0_MECHANISM -> F0_MECHANISM`, recording the dominant failure and quarantining the exact geometry without threshold/horizon/sign/option-wrapper salvage.

This is discovery authority only. Even an F1 pass grants no L1, capital seat, paper status, registry mutation, shadow, arm, broker, funding, or live authority. Holdout outcomes and option prices remain unread.

## Layered Edge Stack

```yaml
candidate_id: OFFICIAL_2S10S_BULL_STEEPENING_KRE_BULL_CALL_21D_V1
family_id: OFFICIAL_YIELD_CURVE_BULL_STEEPENING_REGIONAL_BANK_RELATIVE_UPDRIFT
structure_family: bull_call_debit_spread
forecast_type: direction_up_with_same_date_sector_specificity
underlying_universe: KRE primary; XLF same-date broad-financial specificity control; official U.S. Treasury 2-year and 10-year par yields as exposure source
market_reason: KRE is a liquid regional-bank basket with listed options; XLF removes broad-financial beta from the specificity claim; direct Treasury yields measure the curve without ETF-duration proxy contamination.
economic_mechanism: A completed bull steepening in the 2s10s Treasury curve can lower short funding pressure relative to longer asset yields. If equity investors underreact to that repeated net-interest-margin tailwind, regional banks should rise and outperform broad financials over the next ten completed sessions.
regime_hypothesis: Only a bull steepening inside positive KRE and SPY long trends. Stand aside during under-warmed/nonfinite data, absent direct Treasury observations, negative KRE/SPY trend, or overlapping exposure windows.
entry_trigger: On completed date t, 2s10s=(10Y-2Y); its 20-observation change is at least +0.20 percentage points, the 2Y 20-observation change is at most -0.10 percentage points, KRE close>SMA100, and SPY close>SMA100. Select only the first trigger after false and enforce non-overlap. Enter at the next completed KRE/XLF close; no same-day entry.
exit_rule: Measure the tenth subsequent completed close. The future option plan uses a ten-session time stop.
management_rule: Future option plan only: harvest at +50% spread value, cut at -50% debit, exit by ten sessions, or exit on a predeclared curve/trend invalidation; no roll, averaging, or overlapping regional-bank risk units.
greek_exposures:
  intended: positive delta, bounded positive gamma, limited positive vega, defined debit
  dangerous_unintended: negative theta, volatility crush, capped upside, gap loss, regional-bank correlation/concentration, wide debit/closing spreads, assignment/exercise friction
capital_fit:
  sleeve_usd: 3000
  capital_fit_usd: 200
  one_lot_max_loss_usd: 200
  max_loss_semantics: frictionless planning $2 width ceiling before actual debit, closing friction, assignment/exercise, or management-path validation
  max_lots: 1
  portfolio_overlap_rule: one regional-bank directional risk unit; no concurrent correlated KRE/bank-sector directional packet
mispricing_claim: delayed regional-bank equity repricing to a directly observed bull-steepening funding/lending spread tailwind, conditional on positive trend
predeclared_falsifier: close unless every frozen train-only gate below passes with zero integrity violations
confidence_stage: F0_MECHANISM
bar_claimed: discovery_L0_only
stand_aside_rule: no direct official curve data; stale/nonfinite values; insufficient 20-observation warmup; trigger not met; KRE or SPY at/below SMA100; overlapping signal window; future option debit >$200; missing listed/liquid legs; wide/zero markets; portfolio overlap; chronology/source ambiguity
```

## Frozen evidence design

Source and provenance:

- Curve: official U.S. Treasury daily par-yield CSV, exact `2 Yr` and `10 Yr` fields, fetched year-by-year and persisted/replayed with source hashes.
- Market: adjusted daily KRE, XLF, and SPY OHLCV through the repository's persisted-cache loader; evaluate the reread persisted representation.
- Join: exact common completed market date; no forward fill across missing Treasury dates.
- Timing: curve and trend features through completed date `t`; entry is the next common completed market close; exit is the tenth subsequent common completed market close.

Population and partition:

- Signal threshold: `spread_10y_minus_2y.change(20) >= +0.20pp` AND `2y.change(20) <= -0.10pp` AND KRE/SPY close above fully warmed SMA100.
- Episodes: rising edge only; after selection, suppress every trigger whose entry/exit overlaps a prior selected ten-session episode.
- Global chronological partition: first 60% of frozen eligible signal dates are train; final 40% are identity-only sealed holdout.
- Same-date control: XLF ten-session return on every event date.
- Cost label: subtract 10 bps once from KRE and XLF underlying forward returns; no option costs or marks.
- Inference: circular five-episode block-bootstrap sensitivity on KRE-minus-XLF paired excess; report near-date gaps and train-year distribution. It is not proof of independence.

Train-only discovery conjunction:

1. at least 24 non-overlapping train episodes;
2. at least 10 train signal years;
3. KRE mean ten-session return after 10 bps > 0;
4. KRE-minus-XLF paired mean > 0;
5. circular five-episode-block paired LB90 > 0;
6. KRE positive-return frequency after cost >= 55%;
7. KRE-minus-XLF positive frequency >= 52%;
8. KRE event-return worst-decile mean after cost >= -7%;
9. zero source, feature-lag, entry-lag, overlap, partition, holdout-read, option-pricing, nonfinite, or strict-JSON violations.

Holdout identities are frozen and hashed, but holdout KRE/XLF forward outcomes are not read. `option_pricing_calls=0` and `option_path_measured=false` are mandatory.

## Predeclared validity challenges

- Direct Treasury yields remove ETF proxy roll/composition confounds, but the economic mechanism is still imperfect: deposit beta, loan repricing, hedges, securities duration, credit losses, and macro-growth expectations can dominate. That is why same-date XLF specificity and uncertainty/tail gates are conjunctive.
- Present-day ETF composition creates survivorship scope; any pass is limited to the historical behavior of the current KRE/XLF instruments, not constituent-level bank fundamentals.
- Daily Treasury observations are treated as completed-date features and acted on only at the next close; same-session trading is prohibited.
- The ten-session underlying forecast is not an 18–28 DTE option-path result. The bull-call expression is planning context only until a later frozen payoff validation.
- A favorable point estimate cannot advance without the dependence-aware lower bound, frequency, density, and tail gates.

Freedom audit: Trader remained free on symbol/structure and chose a materially new official-yield repeated-exposure mechanism; prior NEXT informed the question but its inferior ETF-proxy construction was not treated as an order.

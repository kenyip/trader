# Option quote data boundary

Updated: 2026-07-12

Purpose: replace assumed percentage/fixed-dollar option costs with archived bid/ask observations before any L1 claim.

## Executable adapter

`trader_platform/research/option_quote_observations.py` defines a normalized CSV boundary for timestamped option bid/ask rows and computes per-leg half-spreads. `scripts/option_quote_observations.py` can validate archived CSVs or capture all currently available yfinance expirations. Capture appends atomically by default and deduplicates identical rows; `--overwrite` is explicit.

The adapter requires timezone-aware observation timestamps, expiration, type, strike, bid, ask, source, and an explicit `is_observed` flag. Synthetic fixtures are rejected by default and cannot calibrate execution costs.

## No-paid-data inventory

| Source/path | Current bid/ask | Historical bid/ask | Decision |
|---|---:|---:|---|
| Installed `yfinance` 1.5.1 (`Ticker.options`, `Ticker.option_chain`) | Yes, current snapshot when Yahoo serves it | No historical chain method exposed | Use only to start forward archival; never backfill B3/B4 |
| User-supplied normalized CSV archive | Yes | Yes, only for timestamps actually archived | Supported by adapter; provenance must remain attached |
| Existing OHLCV/Black-Scholes proxy sims | No | No | Sensitivity research only, not observed execution evidence |
| Broker APIs | Potentially | Provider-dependent | Out of scope: no broker login in BUILD lab |
| Paid option-data vendors | Provider-dependent | Usually | Blocked without Ken approval; do not enable/spend |

Web inventory was unavailable in this wake because Hermes web search was not configured. The executable local finding is narrower and verified: installed yfinance 1.5.1 exposes only `_download_options`, `_options2df`, `option_chain`, and `options`; it does not expose a historical option-chain API.

## Smoke and forward capture

```bash
.venv/bin/python -m unittest tests.test_option_quote_observations
.venv/bin/python scripts/option_quote_observations.py \
  --input tests/fixtures/option_quote_observations.csv \
  --allow-synthetic-fixture

# Forward-only all-expiration observed archive; no broker login:
.venv/bin/python scripts/option_quote_observations.py \
  --snapshot TSLL \
  --out .cache/platform/option_quotes/TSLL_archive.csv \
  --summary-out .cache/platform/option_quote_archive_density.json
```

The fixture is marked `is_observed=false`. A successful fixture smoke proves schema/validation only. Archive summaries fail closed for provider-backed historical simulation until they contain at least three distinct New York market dates. The first all-expiration TSLL capture contains 600 observed rows across 12 expirations but only 2026-07-11, so it is still ineligible.

## Exact strategy-leg coverage gate

`scripts/observed_quote_coverage.py` reruns a registered PCS/CCS/IC DNA, expands every simulated entry and exit into exact option legs, and performs a non-future as-of join on symbol, expiration, option type, strike, and event time. Quotes older than the configured maximum age are rejected. Calibration is eligible only when every entry and exit leg is matched to an observed row.

The first executable check used `hyp_dna_tsll_put_credit_spread_b195f5fe`, its 57 five-year simulated trades, and the single 70-row TSLL snapshot. It required 228 entry/exit leg observations and matched **0**, so `.cache/platform/observed_quote_coverage_lab_2026-07-11T1800.json` returns `REJECT_INSUFFICIENT_COVERAGE`. This is the intended gate: one current cross-section cannot calibrate historical execution.

```bash
.venv/bin/python scripts/observed_quote_coverage.py \
  --hyp hyp_dna_tsll_put_credit_spread_b195f5fe \
  --quotes '.cache/platform/option_quotes/*.csv' \
  --out .cache/platform/observed_quote_coverage_lab.json
```

## Exact blocker

There is no verified no-paid historical bid/ask backfill in the installed stack. Exact PCS/CCS/IC leg/time joining, all-expiration append-safe capture, a three-market-date density floor, and an insufficient-coverage reject gate now exist, but the forward archive has no matched historical entries or exits. Until enough observations exist across regimes and exits, proxy B3/B4 cannot become observed-cost evidence and readiness remains L0.


## Corrected evidence/data model (2026-07-12)

The platform has independent evidence routes; option-archive density is not a global BUILD gate.

| Route | Inputs actually present | Valid use now | Forbidden inference |
|---|---|---|---|
| Historical underlying replay | Cached yfinance OHLCV across the broad universe (1y/2y/5y/10y where present), with lagged features/regimes | Search, rolling-origin train/holdout, regime and management falsification, negative controls | Does not observe listed option marks, spreads, fills, assignment, or contract availability |
| Option proxy simulation | The same real historical underlying bars plus `iv_proxy`, listed-Friday/rounded-strike assumptions, and Black-Scholes leg marks | L0 discovery and relative sensitivity across any strategy DNA supported by a simulator | Cannot earn L1 or be described as observed-option after-cost edge |
| Historical option replay | Timestamped historical bid/ask surfaces joined to exact entry/exit legs without future quotes | Not available in the installed/local dataset | No edge, cost-calibration, or readiness claim from current data |
| Forward option capture | Current yfinance chains archived append-only | Validate capture/dedup/date/contract-grid/join plumbing; begin cost calibration as density grows | Three dates do not establish a historical strategy edge and do not earn L1 |
| Synthetic market generator | Regime-aware bootstrap/perturbation of historical underlying paths | Stress and model-training augmentation | Neither observed underlying replay nor observed option evidence |

Current code paths using real historical **underlying** bars with proxy **option** marks are `pcs_sim` (PCS/CCS/IC), calendar, diagonal, long butterfly, debit vertical, credit iron butterfly, put-ratio backspread, collar, and the regime router over PCS entries. Single-leg `StrategyConfig` backtests also use historical underlying bars with Black-Scholes marks. The separate `simulator/market_generator.py` path block-bootstraps and perturbs historical underlying bars and is synthetic stress, not historical replay.

`trader_platform/research/evidence_policy.py` provides a fail-closed L1 provenance policy, and the proxy direction scoreboard applies it; readiness/promotion callers must use computed coverage rather than self-asserted metadata. Proxy or unknown option marks cannot earn L1. Observed marks still require more than the three-date plumbing floor, complete observed entry/exit leg joins, and an explicit demonstration that historical coverage is sufficient for the edge claim.

Zero-input orientation records these independent routes in `orientation.json.research_routes`. Observed-option/archive blockage alone cannot justify `DIMINISHING_RETURNS` while historical-underlying/proxy discovery or simulator capability work remains informative. Honest information-exhaustion stops remain valid after open routes are assessed for material novelty.

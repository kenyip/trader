# Historical option data — provider decision packet

Updated: 2026-07-12
Decision owner: Ken
Trader action now: no purchase, credential, account, terms acceptance, broker access, or provider integration.

## Local/no-credential assessment

- The repository contains broad cached historical underlying OHLCV, not historical option surfaces.
- `.cache/platform/option_quotes/TSLL_archive.csv` is one forward snapshot: 600 rows, 12 expirations, one observation timestamp/market date. It has no historical entry/exit coverage.
- Cached PMCC TSLA/NVDA parquet files are current-chain cross-sections with expirations, not timestamped historical surfaces.
- Installed yfinance 1.5.1 exposes current `Ticker.options` / `Ticker.option_chain`; it exposes no historical option-chain method.
- The normalized CSV adapter can consume a lawful user-supplied archive, but no such broad historical archive exists locally.
- No installed adapter for Cboe DataShop, OptionMetrics, ORATS, Polygon, ThetaData, Tradier, or another historical option-surface vendor exists. Broker APIs are excluded by policy.

Conclusion: there is no verified free, local, no-credential source in this environment that supplies broad timestamped historical bid/ask surfaces with expirations, rights, strikes, and enough entry/exit dates to test strategy edge. Public/current chains can support forward capture only. Real historical surfaces therefore require an external data decision unless Ken supplies an already licensed export.

## Minimum data product needed

- Historical NBBO or defensible end-of-day bid/ask (not last-only) for a multi-symbol universe
- Observation timestamp, underlying, expiration, call/put, strike, bid, ask; contract identifier preferred
- Corporate-action/symbol normalization and listed-contract history
- Enough years/regimes and entry/exit dates for rolling-origin tests; three dates are explicitly insufficient
- Export/API terms permitting local research storage, reproducible tests, and derived aggregate evidence
- Cost, rate limit, retention, redistribution, and cancellation terms known before integration

## Options for Ken

1. `DECLINE / FORWARD_ONLY` (default): spend $0; continue broad historical-underlying + proxy-option discovery at L0, while forward archives accumulate. No L1 from proxy evidence.
2. `SUPPLY_LICENSED_EXPORT`: Ken provides a legally usable historical option dataset already owned. Trader builds a read-only normalized adapter and coverage audit; no provider login required.
3. `APPROVE_VENDOR_EVALUATION_ONLY`: authorize a separate comparison of named vendors, coverage, terms, and exact price—still no purchase, credentials, or terms acceptance.
4. `APPROVE_PROVIDER_AND_BUDGET`: later specify provider, account owner, symbols/years, budget ceiling, and terms approval. This must be an explicit mandate before any integration requiring credentials or spend.

Recommendation: keep `FORWARD_ONLY` while proxy discovery remains productive. If a proxy family survives rigorous rolling-origin/regime/cost sensitivity and becomes worth observed validation, request `APPROVE_VENDOR_EVALUATION_ONLY` for a targeted multi-symbol sample before buying broad coverage.

Rollback: provider work remains a separate adapter behind the existing normalized observation boundary. Removing the adapter/config must leave proxy BUILD research and forward archives unchanged.

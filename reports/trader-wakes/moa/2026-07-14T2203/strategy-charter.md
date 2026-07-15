# Strategy decision charter — 2026-07-14T2203 executor

- **Economic mechanism:** In bullish/neutral regimes, 45-DTE one-lot put-credit spreads entered only on Mondays should realize the favorable early theta segment while avoiding the late-cycle gamma/tail zone when closed at 21 DTE; this should improve after-cost path quality versus the identical spread held to 5 DTE.
- **Candidate/family scope:** Fixed-DNA 45-DTE/21-DTE-stop Monday PCS population across BAC, F, SOFI, PLTR, TSLL, SMCI, AMD, and AAPL; one train-ranked named survivor only. This is materially distinct from the closed BAC Friday 7-DTE management path and closed daily signal-entry families.
- **Current funnel stage:** `F0_MECHANISM`.
- **Target stage:** decision on `F1_TRAIN`. The final 40% of every symbol remains untouched in this executor phase.
- **Predeclared falsifier:** `FAMILY_CLOSED` if no symbol's chronological 60% train partition has at least eight trades on each labeled proxy cost axis, positive PnL on both axes, exact ledger/no-same-bar integrity, one-lot max loss <= `$300`, and an early-exit worst-axis PnL strictly better than the identical 5-DTE-stop control; additionally, pooled early-exit worst-axis PnL across qualifying rows must be positive. Otherwise the predeclared top train row becomes one L0/proxy `F1_TRAIN` candidate under `STRATEGY_ADVANCED`.
- **Decision to close:** exactly one of `STRATEGY_ADVANCED` or `FAMILY_CLOSED`.
- **Claim boundary:** historical underlying bars plus listed-Friday/rounded-strike Black-Scholes proxy option marks; labeled 5% adverse leg slip and fixed `$0.01` half-spread per leg; L0 discovery only. Proxy evidence cannot earn L1, a capital seat, or paper authority.
- **Capital shape:** `put_credit_spread`; one-lot defined risk; `capital_fit_usd` and one-lot `max_loss_usd` reported from the run; operating `max_lots=1`.
- **Safety:** research/paper only; no registry mutation, broker, shadow, arm, or live action.

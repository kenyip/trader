# Strategy decision charter — 2026-07-14T0053

PHASE: BUILD / L0 Black-Scholes proxy
SLEEVE_USD: 3000
ROLE: GPT 5.6 Sol executor; only writer; partial MoA phase

ECONOMIC MECHANISM: A sharp overnight downside gap that is fully reclaimed during the same completed session while price remains above a lagged EMA60 may identify transient panic absorption inside an intact longer-term uptrend. Selling a defined-risk 21-DTE put credit spread only on the following bar attempts to harvest elevated downside premium and time decay after confirmation, rather than buying the gap or selling premium during the information shock.

CANDIDATE/FAMILY SCOPE: One predeclared lagged gap-recovery 21-DTE put-credit-spread family across a fixed, outcome-rank-free multi-symbol universe sample. Signal day: open <= 99% of the previous completed close, close >= signal-day open, and close > lagged EMA60. Entry: next completed daily bar only. Controls: no-signal/unconditional PCS plus a complementary failed-recovery or broken-trend control using the same structure and accounting.

FUNNEL BEFORE: F0_MECHANISM
TARGET FUNNEL AFTER: F2_UNTOUCHED_HOLDOUT only if a named exact DNA passes both chronological train and untouched holdout gates; otherwise F0_MECHANISM with the family closed for unchanged reruns.

PREDECLARED FALSIFIER: FAMILY_CLOSED if no named exact DNA passes conjunctive train and untouched-holdout gates with non-vacuous positive 5% adverse leg-slip and fixed-$0.01-per-leg PnL, one-lot max_loss_usd <= 300, window max drawdown <= 75 on both cost axes, dense-negative windows <= 5, exact ledger reconciliation, strict signal lag, no same-bar re-entry, and complete population/ranking evidence. Any claim-invalidating integrity defect blocks the result until repaired and rerun in this wake.

EXACT DECISION THIS WAKE WILL CLOSE: STRATEGY_ADVANCED if at least one named candidate moves F0_MECHANISM -> F2_UNTOUCHED_HOLDOUT under the predeclared conjunction; otherwise FAMILY_CLOSED with the dominant failure mechanism and unchanged-rerun quarantine recorded.

WHY THIS LOOP: orientation reports 15 consecutive no-advance wakes and requires burst stop/reassessment. Jarvis independently authorizes one bounded schema-v2 re-entry after reassessment. This event-driven overnight-gap absorption mechanism is materially different from the closed adjacent-close momentum/pullback, realized-volatility, session-time, symmetric double-diagonal, and generic free-population mechanisms. It supersedes an unchanged random-cap/structure-volume rerun; no successor burst is authorized regardless of outcome.

AUTHORITY: Research/paper only. Proxy evidence cannot earn L1. No registry mutation, paper order, shadow/live promotion, broker login, arm, funding, or live action.

# Merged NEXT SEED — 2026-07-13T0026

**Source:** executor NEXT + Grok challenger PASS 8/8 (light tighten only; no supersede).

## ONE NEXT

Build one no-lookahead completed-30-minute-bar session-time evidence route for defined-risk PCS/CCS/IC across a liquid multi-symbol universe (default: BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL).

Requirements:
- Entry buckets: open / midday / late, using only completed 30-minute bars.
- Regime / signal features: prior-completed bars only (no same-bucket lookahead).
- Cost axes: exact multi-leg 5% adverse percentage slip **and** $0.01 half-spread per leg.
- Design: chronological train selection → untouched holdout (or equivalent predeclared holdout), exact ledger recomputation, no same-bar / same-bucket reentry.
- Absolute reject-unless gates: one-lot max_loss ≤ $300, window max DD ≤ $75, non-vacuous density/min trades, positive after-cost PnL on claimed axes, dense-negative windows ≤ 5.
- Keep L0. Register nothing on first pass. No paper / shadow / arm / live.

Do **not**:
- Reopen the rejected double-diagonal 14/60 proxy seed or expand its IV/DTE grid first.
- Reopen closed daily-bar PCS/CCS signal families, collar, asymmetric IC, BAC Fri7 management, or AAPL no-auth ex-date inventory.
- Treat the one-date TSLL observed archive as a global freeze; archive append is parallel-only when a distinct NY RTH date exists (1→2/3), and three dates remain plumbing/calibration only.

## Why this NEXT

Coverage still lists session-time slices as the open time-axis gap after weekday/DTE grids and lagged daily signal rejects. Double-diagonal capability is now present and this exact proxy config is closed for the cycle; the highest-information remaining BUILD loop is the missing intraday session-time evidence class on mature defined-risk engines.

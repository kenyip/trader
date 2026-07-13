# Merged NEXT seed — 2026-07-13T0515

## ONE NEXT (BUILD / L0)

Promote an **append-safe, provenance-recorded raw 30-minute underlying archive** for the same eight-symbol universe (BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL), retaining full yfinance-available history with download/as-of metadata. Expand **usable** session-feature market dates toward that raw history **without lookahead** (justify or relax feature-readiness/`min_daily_history` burn that currently collapses ~60 raw dates → ~21 usable). Then **rerun once** the locked chronological PCS/CCS/IC open/midday/late dual-cost train→holdout specification (same DNA/gates; no holdout retune).

Reject again unless both train and untouched holdout independently pass 5% leg slip **and** $0.01 half-spread-per-leg with n≥3, PnL>0, one-lot max loss ≤$300, max/window DD ≤$75, dense-negative windows ≤5, exact ledger, and zero same-bar / same-date-session-bucket reentries. Keep L0. Do **not** register, promote, paper, shadow, arm, or live. Do **not** reopen closed daily-bar families or the rejected double-diagonal seed.

## Why this supersedes the executor wording (same intent)

- Executor correctly forbids DNA retune and demands denser evidence before retest.
- Independent check: raw stamp CSVs already have **60** market dates; usable session frames only **21** after default feature readiness. Waiting for “60 new dates” is thrash-adjacent; unlocking usable density from retained raw history is the new evidence class.
- Append-safe archive remains required so future wakes do not depend on ephemeral yfinance retention alone.

## Explicit non-goals

- No observed-option provider hist / L1 from this path
- No registry mutation on first denser pass
- No same-holdout knob search
- No live / shadow / agentic arm

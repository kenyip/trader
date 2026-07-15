# Merged NEXT seed — 2026-07-15T1606 (challenger)

## ONE NEXT

`BREAKOUT_F2_OPTION_PAYOFF_FREEZE`

Freeze **one** exact claim-aligned option specification for `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` and dual-cost falsify it under L0 proxy rules. No L1, capital seat, paper place, shadow, arm, or live.

## Freeze scope (development-only)

- **DNA source rows:** original **168** train/development blueprints only.
- **Structure:** one-lot 14-DTE `$1`-wide **bull call debit** vertical (defined risk).
- **Entry:** next session after completed lag-safe breakout (close ≥1.02 × prior completed 20-session high and above prior completed SMA100).
- **Management (must match F2 horizon evidence):**
  - harvest at ~50% of maximum spread value;
  - invalidate if close returns below the pre-breakout 20-session high;
  - **hard 10-session time stop** (primary claim-aligned exit; do not treat full 14-session hold-to-expiry as the F2 outcome);
  - no same-bar reentry.
- **Costs:** explicit adverse multi-leg **fixed-dollar** and **percentage** axes.
- **Capital fields:** `capital_fit_usd` / one-lot `max_loss_usd` / `max_lots=1`; structural bound before closing friction remains labeled until observed debit exists.
- **Listing realism:** fail closed when strike/expiry unavailable in the sim grid; no invented fills.

## Decision gates (reject-unless)

Primary metrics are **absolute after-cost option PnL and path risk**, not underlying paired excess / control underperformance.

On the **168 development** partition (primary):

1. Non-vacuous trades under **both** cost axes.
2. Positive after-cost total PnL on **both** cost axes.
3. One-lot max loss ≤ `$300`.
4. Window max DD ≤ `$75`.
5. Density / integrity: no same-bar reentry; chronology intact; strict JSON.
6. Keep claim **L0 proxy**; `pricing` may use BS/proxy marks but **cannot earn L1 or a capital seat**.

On the **opened 113** holdout pairs (secondary stress only):

- May rerun the **already frozen** DNA as labeled inspected stress.
- **Must not** be called a new untouched option holdout.
- **Must not** be used to retune strikes/DTE/management after seeing results.
- Report pass/fail transparently; a development pass with catastrophic secondary stress is a paper-plan / F3 warning, not an automatic L1.

## Mandatory diagnostics (do not mutate freeze after peek)

- Per-symbol and chronological concentration of option results.
- Do not claim universal 8-name option edge from pooled underlying F2.
- AMZN/META underlying weakness and 2022–23 tertile flat absolute treated path remain context that option results must respect.

## Explicit non-goals

- No registry promotion to capital path / L1.
- No paper/shadow/arm/live.
- No retune of the frozen underlying breakout geometry (lookback, 1.02 ratio, SMA100, match bounds, 60/40 split).
- No reopening quarantined families as a substitute for this freeze.

## Success / failure outcomes for the next wake

- `STRATEGY_ADVANCED` only if a named option DNA moves F2→F3 (robust paper plan) with claim-appropriate dual-cost evidence and honest L0 proxy labels — still no seat.
- `FAMILY_CLOSED` if the frozen option expression fails reject-unless gates on development data (record dominant failure: cost, DD, vacuity, listing, etc.).
- `BLOCKER_REMOVED_AND_RETESTED` only if a claim-invalidating sim/cost defect is repaired and the option experiment is re-run same wake.
- Do not stop the broader program solely because observed historical option archives are thin; this freeze uses proxy/listed-expiry abstraction with honest labels.

## Context (not orders)

- Prior epoch `2026-07-15-time-series-breakout-payoff` is **completed** at F2/L0 underlying.
- Canonical holdout: `.cache/platform/breakout_continuation_holdout_2026-07-15T1606.json` SHA `dd30bee3…`.
- Living leader: none. Capital path: empty.

# ONE NEXT SEED — 2026-07-14T2203 (challenger merge)

Build and run **one** lagged monthly cross-sectional low-realized-volatility pre-screen over a fixed liquid multi-name universe.

## Mechanism under test

Names with relatively low completed realized volatility may exhibit more stable near-term path quality than same-date high-HV peers (carry / reduced jump risk), measurable first as an **underlying** forward-return effect before any option overlay.

## Required design (non-negotiable)

1. Rank only on **prior completed 60-session HV** known before the rank month (no same-month / same-bar leakage).
2. Compare bottom-quartile forward returns vs **same-date top-quartile** controls (and/or middle-quartile complement if stated pre-declaration).
3. Chronological **train then untouched holdout** on the underlying mechanism first.
4. Reach option marks **only if** the underlying pre-screen advances under its predeclared falsifier.
5. Close exactly one strategy outcome: `STRATEGY_ADVANCED` | `FAMILY_CLOSED` | `BLOCKER_REMOVED_AND_RETESTED` | `EVIDENCE_WAIT`.
6. Keep claim L0 / research-only until capital-seat bar could apply; proxy option marks still cannot earn L1 alone.

## Explicit non-goals

- Not another PCS entry/exit-stop nudge or retune of `pcs-monday-45dte-exit21-vs-exit5-train-proxy`.
- Do not reopen closed families (gap-recovery, TOM, VRP, daily signal PCS/CCS, collar, session-time seed, free defined-risk pop36, etc.) without a genuinely new evidence class.
- No registry write on first pass unless predeclared gates pass and claim scope allows.
- No paper / shadow / arm / live / broker / spend.

## Context (not orders)

- Active epoch `2026-07-14-reassess`; after this wake integrates, epoch no-advance streak = 1 (pivot/stop still false).
- Living leader: none. Capital path: empty. Phase: BUILD.
- Prior NEXT was context; this seed is the highest-information independent cross-sectional evidence class after the Monday early-exit family closed.

If the pre-screen cannot be stated with leakage-safe features and a falsifier before option pricing, stop and redesign rather than buy familiar PCS volume.

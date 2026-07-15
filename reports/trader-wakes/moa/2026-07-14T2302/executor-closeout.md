# MOA executor closeout — 2026-07-14T2302

PARTIAL PHASE — executor only; not RUN COMPLETE.

## Strategy decision charter (predeclared before experiment execution)

- Economic edge mechanism: within a fixed liquid-equity cross-section, the lowest prior completed 60-session realized-volatility names should retain a steadier positive 21-session forward drift than the contemporaneous highest-volatility names. If supported, the selector could later condition a one-lot, $1-wide put credit spread so directional drift and time decay work together.
- Candidate/family scope: `CROSS_SECTION_LOW_HV_PCS_21D_V1`; monthly bottom-three versus top-three prior-HV ranks across fixed present-day liquid equities AAPL, MSFT, NVDA, AMZN, META, GOOGL, AMD, NFLX, TSLA, AVGO, MU, JPM, XOM, BAC; non-overlapping 21-session episodes; chronological first 60% only.
- Current evidence-funnel stage: `F0_MECHANISM`.
- Predeclared falsifier: on the chronological first 60% of eligible non-overlapping monthly episodes, fewer than 24 episodes, non-positive low-HV mean return, non-positive low-minus-high mean return, or a non-positive one-sided 90% circular-block-bootstrap lower bound closes this exact family. Any chronology, overlap, population-completeness, or strict-serialization violation also fails the gate.
- Exact decision this wake will close: `STRATEGY_ADVANCED` to `F1_TRAIN` if every frozen train gate passes; otherwise `FAMILY_CLOSED`. The untouched final 40% will not be simulated or read in this executor phase.
- Trade shape / capital context: planned structure is a defined-risk put credit spread, one future $1-wide lot; `capital_fit_usd=100`, one-lot `max_loss_usd=100` structural upper bound before credit/friction, `max_lots=1`. No option pricing, trade, L1, capital-seat, or paper claim is made at F0.

Choice rationale: the active epoch required a material pivot after two no-advance wakes. This selector is a distinct cross-sectional direction/risk mechanism, uses the valid historical-underlying route, and does not reopen any closed time-event/VRP/PCS-entry family. It follows the prior NEXT because current orientation independently supports it, not because NEXT is an order.

## Outcome

`FAMILY_CLOSED`; `F0_MECHANISM -> F0_MECHANISM`; strategy advancement false.

The frozen chronological train partition contained 43 eligible non-overlapping monthly episodes. The bottom-three low-HV basket had positive absolute mean forward drift (`+0.028044839681`), but the same-date top-three high-HV control averaged `+0.055349242755`. Paired low-minus-high excess was `-0.027304403074` (median `-0.037595516809`; positive frequency `0.348837209302`), and the one-sided 90% circular-block-bootstrap lower bound was `-0.041618164833` with 10,000 samples, block length 3, and seed 20260714. Density, chronology, disjoint-group, and absolute-drift checks passed; the frozen incremental-mean and bootstrap gates failed.

The dominant failure is therefore missing incremental selector edge versus the same-date high-HV control, not missing absolute low-HV drift. The untouched final 40% remains 30 reserved blueprints with `outcome_metrics_read=false` and `simulation_run=false`. Option pricing did not run (`pricing_calls=0`). The planned one-lot `$1`-wide PCS remains only structural context: `capital_fit_usd=max_loss_usd=100`, `max_lots=1`; no trade loss, L1, capital seat, registration, paper, shadow, arm, broker, or live claim exists.

Close and quarantine `MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT` plus nearby unchanged HV-lookback, k-of-14, and 21-session knobs on this fixed present-day 14-name panel. The observed high-HV outperformance is not a free inverted strategy; any such thesis requires a new predeclared mechanism and falsifier.

Canonical evidence: `reports/trader-wakes/moa/2026-07-14T2302/low-hv-cross-section-train.json` (finalizer-regenerated SHA-256 `9ab27b71c7fb2a0ed4cc0c0a41426ae709ba5cc7b0cf449058ecceca2f5187f2`).

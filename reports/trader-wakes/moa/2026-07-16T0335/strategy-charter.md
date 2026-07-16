# Strategy decision charter — 2026-07-16T0335

WAKE: 2026-07-16T0335
PHASE: BUILD / L0 underlying discovery
SLEEVE: $3,000 Agentic research sleeve
MARKET SESSION: premarket, derived at 2026-07-16 03:35 PDT; no RTH paper action

## Decision

ECONOMIC MECHANISM: Monthly institutional and benchmark allocation changes are implemented over multiple sessions rather than instantaneously. A liquid US sector ETF that is already the three-month relative-strength leader, remains in an absolute uptrend, and is separated materially from the cross-sectional median may therefore continue to outperform its same-date sector peers over the next trading month.

CANDIDATE / FAMILY: `MONTHLY_SECTOR_LEADER_CONTINUATION_BULL_CALL_35D_V1` / `SECTOR_ALLOCATION_RELATIVE_STRENGTH_CONTINUATION`. The frozen panel is the nine original Select Sector SPDRs (`XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`). This is a materially new evidence class for the quarantined fixed-stock monthly 12-1 momentum family: a sector-allocation panel with a shorter 63-session formation horizon, same-date nonleader specificity control, and roughly 1999-forward history. It is not a threshold retune on the prior 14-stock panel.

FUNNEL: `F0_MECHANISM -> F1_TRAIN` only if every frozen discovery gate passes; otherwise `F0_MECHANISM -> F0_MECHANISM` and the exact sector-allocation family closes.

PREDECLARED OUTCOME: exactly one of `STRATEGY_ADVANCED` or `FAMILY_CLOSED`.

PREDECLARED FALSIFIER: On the chronological first 60% of frozen eligible monthly signals, close the exact family if any of these holds: fewer than 60 non-overlapping train signals; fewer than 10 signal years; any chronology, month-end, next-session-entry, overlap, population, adjusted-data, holdout, non-finite, option-pricing, or strict-JSON integrity violation; leader mean 20-session return after a 10-bps round-trip hurdle at or below 0.50%; leader positive frequency below 55%; mean same-date paired excess versus the equal-weight nonleader basket below 0.30%; paired-excess circular date-block bootstrap LB90 at or below zero; leader worst-decile return below -8%; or the equal-weight nonleader basket is not weaker than the leader. Geometry and thresholds are frozen before train outcome evaluation. The sealed final 40% is identity-only and outcome-unread.

EXACT DECISION THIS WAKE WILL CLOSE: whether this named sector-allocation continuation mechanism advances from F0 to F1 under the discovery bar or is quarantined unchanged as `FAMILY_CLOSED`. No option pricing, holdout outcome read, registry insertion, L1, capital seat, paper force, shadow, arm, broker, or live action.

## Layered Edge Stack

- Market / underlying: the dynamically selected leader from the frozen nine original Select Sector SPDR ETFs. Every panel member is a liquid US equity sector ETF; the fixed historical panel avoids letting late-listed `XLC`/`XLRE` truncate the discovery sample.
- Forecast type: absolute upward drift and cross-sectional outperformance over the next 20 completed sessions.
- Economic mechanism: slow institutional/benchmark sector reallocation and performance-chasing flows may persist for several weeks after a sector has established intermediate-term leadership.
- Signal schedule: only the final completed trading session of each calendar month. All ranking and regime inputs use data through that completed close.
- Entry trigger: rank the frozen panel by split/dividend-adjusted 63-session return. The leader must have positive 63-session return, close above its completed 126-session SMA, and exceed the panel median 63-session return by at least 5 percentage points. Enter conceptually at the next completed regular-session close; otherwise stand aside for that month.
- Exit / management: underlying discovery exits after 20 completed sessions. A later option-stage charter would freeze +50%/-50% debit exits, a five-DTE guard, trend invalidation, liquidity, assignment, and no-roll rules separately.
- Specificity control: the equal-weight 20-session return of the eight same-date nonleader sector ETFs, with the same 10-bps round-trip hurdle applied per leg. Rank selection is frozen from pre-entry fields; peer outcomes cannot affect leader selection.
- Partition: chronological 60% train / sealed 40% holdout across frozen eligible monthly signal blueprints. Holdout identities and source hashes may be serialized; holdout leader or peer returns remain unread.
- Option structure: conditional future one-lot 30–45 DTE $2-wide bull call debit spread on the selected leader only after underlying advancement and a separate option-stage charter. Zero option marks in this wake.
- Intended Greeks: positive delta, positive gamma, and bounded negative theta.
- Dangerous Greeks / exposures: negative theta if continuation stalls; IV contraction after a momentum burst; capped upside; gap loss; sector concentration; short-call assignment and expiration handling; dynamic-underlying operational complexity.
- Regime envelope: selected leader has positive completed 63-session return and completed close above SMA126; cross-sectional separation is at least 5 percentage points. No broad-index regime filter is added because it would obscure whether the sector-relative mechanism itself carries information.
- Capital fit: `sleeve_usd=3000`; future structural `capital_fit_usd=200`; width-bound one-lot `max_loss_usd=200` before debit slippage/closing friction; `max_lots=1`; no concurrent Agentic position in the chosen sector ETF or broad-index positive-delta unit. These are planning bounds, not observed debit or L1 evidence.
- Evidence / falsifier: adjusted daily ETF closes, exact month-end schedule, deterministic split, train-only 10-bps hurdle, same-date nonleader control, date-block uncertainty, density, absolute and relative gates, chronology, population purity, source hashes, and sealed holdout. Underlying-only discovery cannot earn L1.
- Confidence: before run `F0_MECHANISM / L0`; after run either `F1_TRAIN / L0` or closed at F0.
- Stand-aside rule: incomplete/non-finite panel; insufficient warmup; signal not the final completed month session; leader return non-positive; leader below SMA126; leader-minus-median spread below 5%; missing next-session entry or full 20-session path; overlap; failed train gate; any holdout outcome read; future quoted debit/max loss above $200; poor option liquidity; major earnings-style idiosyncratic event cannot apply to diversified sector ETFs, but scheduled macro overlap would be limited to one global risk unit.

## Freedom / anti-thrash judgment

The accepted two-close scheduled-macro pivot reassessment is closed by pivoting away rather than opening CPI: current BLS access remains blocked and another information-resolution event study would repeat a recently exhausted evidence class. The broad candidate-factory seed is context, not an order; a single frozen sector-allocation experiment is smaller and more decision-efficient than another unconstrained batch. It supplies the materially new panel construction explicitly allowed by the closed monthly fixed-stock momentum quarantine. Freedom remains intact: symbol, structure, and mechanism were selected from current evidence rather than a TSLA/TSLL or strategy allowlist.

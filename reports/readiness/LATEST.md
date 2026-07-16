# Trader readiness — LATEST

Updated: 2026-07-16T1123 finalizer ready; deterministic integration pending
Phase: **BUILD**
Authority: **research / paper-safe only; no broker, shadow, arm, or live authority**
Integration: **pending wrapper commit/push/fast-forward/postflight**; no RUN COMPLETE

## Current strategy decision

`FAMILY_CLOSED`, `F0_MECHANISM -> F0_MECHANISM`, for exact `OFFICIAL_2S10S_BULL_STEEPENING_KRE_BULL_CALL_21D_V1` / `OFFICIAL_YIELD_CURVE_BULL_STEEPENING_REGIONAL_BANK_RELATIVE_UPDRIFT`. Strategy advancement is false.

The executor replaced the prior fixed-duration Treasury-ETF proxy before outcome access with direct official U.S. Treasury daily par-yield `2 Yr` and `10 Yr` observations. The exact event geometry is too sparse and calendar-concentrated for a durable one-lot income mechanism. No holdout outcome or option path was opened.

## Exact evidence

Canonical artifact: `reports/trader-wakes/moa/2026-07-16T1123/yield-curve-regional-bank-train.json`

- Current finalizer raw SHA-256: `676e674fe5be6a6ea01b366a141bdca2c8e6ac6b60fc6fbf4f0fd299f9a06116`.
- Normalized SHA-256 excluding only `generated_at`: `36c96f9d238edaca0fbd4b36e601123556e4f93c755f16fb5898aa20aee3f6d8`; persisted-cache replay is substantively equal.
- Official curve rows: 5,137; exact common completed KRE/XLF/SPY rows: 5,009 from 2006-06-22 through 2026-07-15.
- Frozen signals: 7 total from 2009-11-09 through 2025-08-27.
- Train: 4 episodes across 2 signal years; `2009:1 / 2024:3`; maximum calendar concentration 75%.
- Sealed holdout: 3 identities, identity SHA `2805d49db7459e63024a5c86a61a10ca295c18315ad3f580fafc196e751e475a`; outcomes unread, simulation false, option pricing zero.
- KRE mean after the labeled 10-bps round-trip sensitivity: **+4.890755%**.
- XLF mean after 10 bps: **+2.642830%**.
- Paired KRE-minus-XLF mean: **+2.247924%**.
- KRE positive frequency: 100%; paired positive frequency: 75%; KRE event-return worst-decile mean: +4.278067%.
- Integrity violations: 0.
- Failed gates: n4<24; 2 years<10; five-episode uncertainty cannot be non-vacuous at n4.

Dominant failure: `insufficient_nonoverlapping_episode_density`.

The favorable four-row center is diagnostic only. Three of four train episodes occur in 2024, so calendar concentration reinforces the density/year failure rather than offering a subset to promote. No threshold, horizon, sign, trend, control, unclustered, holdout, or option-wrapper salvage is permitted. Reopening requires a genuinely new evidence class and pre-outcome charter.

The executor/challenger hashes `f8e20be6…` / `7435db0c…` are pre-finalizer phase receipts. Finalizer regenerated the same decision after adding machine-readable year concentration, duplicate-source-date fail-close, and exact 10-bps round-trip cost semantics.

## Layered Edge Stack / capital truth

Measured F0 forecast: bullish KRE direction and KRE-over-XLF specificity from next completed close through the tenth subsequent completed close after a direct official 2s10s bull steepening, with KRE and SPY above fully warmed SMA100.

Future expression only: one-lot KRE 18–28 DTE $2-wide bull-call debit spread.

- `capital_fit_usd=200`
- frictionless planning `max_loss_usd=200` before actual debit, closing friction, assignment/exercise, or management-path validation
- `max_lots=1`; one correlated regional-bank directional risk unit
- intended: positive delta, bounded positive gamma, limited positive vega, defined debit
- dangerous: negative theta, volatility crush, gap/concentration, capped upside, wide debit/closing spreads, assignment/exercise
- future management only: +50% spread value, -50% debit, ten-session time stop or predeclared curve/trend invalidation; no roll/averaging
- stand aside: absent/stale/nonfinite direct yields, missing exact common date, under-warmed trend, overlap, debit >$200, illiquid/unlisted legs, wide/zero market, portfolio overlap, or source/chronology ambiguity

The ten-session underlying result is not an 18–28 DTE option-path result. No historical contract, IV, strike, listed expiry, debit, fill, theta/vega path, management, assignment, exercise, B3, B4, or B6 was measured. Planning fields grant no F1, L1, paper plan, or capital seat.

## Funnel / leaders / seats

| item | current |
|---|---:|
| living strategy candidates | 0 |
| F1 survivors | 0 |
| F2 untouched-holdout survivors | 0 |
| F3 robust paper plans | 0 |
| F4 observed paper candidates | 0 |
| L1 capital-seat candidates | 0 |
| quality leaders | 0 |
| capital seats | 0 |

No stale historical leader is living. Absolute frozen discovery gates govern this F0 close.

## Readiness checks

| Check | State | Evidence / gap |
|---|---|---|
| B1 — deterministic research evidence | BUILD improvement only | Persisted official-source hashes, exact-date/no-forward-fill joins, current-code replay equality, strict JSON, sealed holdout, and duplicate-date fail-close are green; strategy discovery conjunction fails. |
| B2 — strategy hypothesis quality | NOT READY | Exact family closed; no F1 survivor. |
| B3 — regime/path stress | NOT RUN for candidate | Inapplicable after F0 close. |
| B4 — cost/parameter stress | NOT RUN for candidate | One 10-bps round-trip underlying sensitivity only; no option proxy or observed marks. |
| B5 — auditability / controls | BUILD improvement only | Direct tenors, persisted-byte replay, chronology, non-overlap, XLF specificity, year concentration, non-vacuous uncertainty, strict holdout seal, and tests are durable; current ETF composition and omitted bank fundamentals remain explicit limits. |
| B6 — paper execution realism | NOT READY | No option path, packet, or observed paper fills. |
| B7 — shadow | BLOCKED | Ken-only authorization; no qualifying candidate. |
| B8 — agentic live | BLOCKED | Ken-only arming; prohibited. |

No B3/B4/B6+ state or phase advanced. No registry mutation or paper intent occurred.

## Verification

Finalizer-owned results:

- Focused behavior/boundary/positive/negative suite: **12/12**, `OK` in 0.044s.
- Adjacent lab + compounding/completion/coverage/progress suite: **68/68**, `OK` in 9.751s.
- Full required suite `.venv/bin/python -m unittest discover -s tests`: **445/445**, `OK` in 29.377s.
- `py_compile`: `OK`.
- Deterministic persisted-cache replay: substantive payload equality true; normalized SHA `36c96f9d…`.
- Strict JSON, source/holdout hashes, outcome `FAMILY_CLOSED`, and option-pricing count zero verified.
- Income coverage: **21 structures / 246 hypotheses / 70 evolve artifacts / no quality leader**.
- TSLL observed archive: 3/3 RTH dates and 13 expirations/date; plumbing floor only, not historical edge or L1.

Deterministic secret/path/diff/staging checks and integration remain pending the wrapper gate.

## Active search-epoch implication

`configs/search_epoch.json` preserves completed predecessor `POST_REASSESSMENT_INDEPENDENT_DEFINED_RISK_DISCOVERY_V1` and records active successor `REPEATED_EXPOSURE_SPECIFICITY_DISCOVERY_V1`:

1. 2026-07-16T0546 broad-index overnight absorption — no advance / family close.
2. 2026-07-16T1123 official 2s10s regional-bank updrift — no advance / family close.

Successor `counted_no_advance_decisions=2`, `strategy_pivot_required=true`, `strategy_burst_stop_required=false`. The next strategy wake must pivot mechanism/evidence class. A third no-advance must stop the burst and reassess search design/data.

## RTH opportunity state

Concurrent 2026-07-16T1530 late-session condition state remains valid and orthogonal:

| Check | State | Evidence |
|---|---|---|
| C — live condition / paper opportunity | STAND_ASIDE (success) | Session-day freshness pass (2026-07-16T1530); scout 14/0/14; autonomy 0 proposals; real paper open risk 0; no capital-fit OPEN_PCS/CCS/IC; no B6 advance. Same bearish TSLL/TSLA/SMCI class as open→14:30. Historical RTH report remains reports-only pending this BUILD integration. |

## ONE NEXT

`MULTI_ISSUER_DIVIDEND_INCREASE_FORWARD_UPDRIFT_F0`: pivot to a materially different issuer cash-flow-confidence mechanism. Before outcomes, freeze a point-in-time regular cash-dividend increase definition from declaration-date and amount records; exclude specials, unchanged amounts, cuts, preferred/ambiguous securities, missing `known_at`, nonpositive amounts, and chronology conflicts; predeclare a fixed liquid multi-issuer panel with same-date sector controls, next-close ten-session forecast, labeled underlying cost, global chronological train/sealed identity holdout, and density/year/issuer-breadth, specificity, dependence-aware uncertainty, hit-rate, tail, and integrity gates. Existing dividend provenance and assignment-guard tooling is infrastructure, not edge evidence. Close exactly one `STRATEGY_ADVANCED` F0→F1 or `FAMILY_CLOSED` decision in-wake. Future one-lot defined-risk expression must have `capital_fit_usd` and `max_loss_usd <= 300`, `max_lots=1`. No yield-curve salvage, holdout reads, L1, seat, paper, shadow, arm, broker, funding, or live authority.

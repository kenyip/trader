# MoA executor closeout — 2026-07-16T1123

> Finalizer note: hashes and verification below are truthful executor-phase receipts. Finalizer regeneration added duplicate-date fail-close, exact 10-bps round-trip cost labeling, and machine calendar concentration; current raw/normalized hashes are `676e674f…` / `36c96f9d…`. Strategy metrics and `FAMILY_CLOSED` did not change; living truth is `2026-07-16T1123-moa-merge.md`.

EXECUTOR: GPT 5.6 Sol
PHASE: BUILD / research-only L0
AUTHORITY: executor partial only; challenger/finalizer and deterministic integration still pending
SLEEVE: $3,000
OUTCOME: `FAMILY_CLOSED`
FUNNEL: `F0_MECHANISM -> F0_MECHANISM`
STRATEGY_ADVANCEMENT: false

## Strategy decision charter

Economic edge mechanism: a completed bull steepening in the official U.S. Treasury 2s10s daily par-yield curve may reduce short funding pressure relative to longer asset yields. If regional-bank equities underreact to that repeated net-interest-margin tailwind, KRE should rise and outperform broad financials over the next ten completed sessions.

Candidate / family:

- candidate: `OFFICIAL_2S10S_BULL_STEEPENING_KRE_BULL_CALL_21D_V1`
- family: `OFFICIAL_YIELD_CURVE_BULL_STEEPENING_REGIONAL_BANK_RELATIVE_UPDRIFT`
- starting stage: `F0_MECHANISM`
- exact close: `FAMILY_CLOSED`, `F0_MECHANISM -> F0_MECHANISM`

Why this loop: the active successor epoch entered with one counted no-advance, no mandatory pivot, no burst stop, no living leader, and no capital seat. The prior NEXT's economic question remained informative, but its fixed-duration Treasury-ETF proxy was not an order. The executor replaced that confounded proxy with direct official U.S. Treasury `2 Yr` and `10 Yr` daily par-yield observations before any KRE/XLF forward-outcome read. This is materially different from the already-closed broad-index overnight-absorption mechanism.

Full pre-outcome charter: `reports/trader-wakes/moa/2026-07-16T1123/strategy-charter.md`.

### Layered Edge Stack

- Market / underlying: KRE primary; XLF same-date broad-financial specificity control; SPY trend filter; official Treasury 2-year and 10-year par yields as exposure source.
- Forecast type: direction up with same-date sector specificity over ten completed sessions.
- Economic mechanism: bull-steepening funding/lending spread tailwind with delayed regional-bank equity repricing.
- Option structure: future-only 18–28 DTE KRE $2-wide bull-call debit spread.
- Intended Greeks: positive delta, bounded positive gamma, limited positive vega, defined debit.
- Dangerous Greeks / risks: negative theta, volatility crush, capped upside, gap loss, regional-bank correlation/concentration, wide debit/closing spreads, assignment/exercise friction.
- Regime envelope: direct curve observation plus KRE and SPY above fully warmed SMA100; exact common completed dates only.
- Entry: on completed date `t`, 20-observation 2s10s change >= +0.20 percentage points, 2-year yield change <= -0.10 percentage points, KRE/SPY trend positive, rising edge only; enter next completed close.
- Exit / management: measured underlying exit is tenth subsequent completed close. Future option plan only: +50% spread value, -50% debit, ten-session time stop or predeclared curve/trend invalidation; no averaging, roll, or overlapping regional-bank risk unit.
- Capital fit: `capital_fit_usd=200`, frictionless planning one-lot `max_loss_usd=200`, `max_lots=1`; one correlated regional-bank directional risk unit. Actual debit, listed legs, closing friction, assignment/exercise, and managed option path were not measured.
- Evidence / falsifier: first 60% chronological train only; final 40% identity-only holdout; same-date XLF control; 10 bps subtracted from both underlying returns; every frozen density, center, specificity, block-LB, hit-rate, tail, and integrity gate must pass.
- Confidence: L0 / `F0_MECHANISM` only.
- Stand aside: absent/stale/nonfinite direct curve; missing exact common date; under-warmed data; KRE/SPY at or below SMA100; overlapping exposure; future debit >$200; missing or illiquid listed legs; wide/zero markets; portfolio overlap; source/chronology ambiguity.

## Frozen train-only design

- Official source: U.S. Treasury Daily Treasury Par Yield Curve Rates, exact `2 Yr` and `10 Yr` CSV fields, 2006–2026, persisted and hashed year by year.
- Market source: persisted/reread yfinance `auto_adjust=True` OHLCV for KRE, XLF, SPY; request ended exclusively at 2026-07-16, so the last completed bar was 2026-07-15.
- Join: exact common dates only; no curve forward fill. One 2010 row missing both direct tenors was dropped and counted rather than imputed.
- Signal geometry: 20-observation direct 2s10s change >= +0.20pp and 2-year change <= -0.10pp, KRE/SPY > SMA100, rising edge, non-overlapping ten-session windows, next-close entry.
- Partition: globally chronological 60% train / 40% sealed identity holdout.
- Frozen discovery conjunction: train n>=24; >=10 signal years; KRE mean after 10 bps >0; KRE-minus-XLF mean >0; non-vacuous circular five-episode block LB90 >0; KRE hit>=55%; relative hit>=52%; KRE event-return worst-decile mean>=-7%; zero integrity violations.
- Option pricing calls: 0.

## Claim-bearing result

Canonical artifact: `reports/trader-wakes/moa/2026-07-16T1123/yield-curve-regional-bank-train.json`

- Source curve rows: 5,137; exact common completed rows: 5,009 from 2006-06-22 through 2026-07-15.
- Frozen signals: 7 total from 2009-11-09 through 2025-08-27.
- Train: 4 episodes across only 2 signal years.
- Sealed holdout: 3 identities; outcomes unread; simulation false; option pricing 0; identity SHA `2805d49d…`.
- KRE mean ten-session return after 10 bps: +4.890755%.
- XLF mean after 10 bps: +2.642830%.
- KRE-minus-XLF paired mean: +2.247924%.
- Four-row circular block diagnostic: +2.247924%, but the five-episode uncertainty gate is explicitly non-vacuous only at n>=5 and therefore fails.
- KRE positive frequency after cost: 100%.
- KRE-minus-XLF positive frequency: 75%.
- KRE event-return worst-decile mean after 10 bps: +4.278067%.
- Integrity violations: 0.

Failed frozen gates:

1. train episodes 4 < 24;
2. train years 2 < 10;
3. five-episode block uncertainty is non-vacuous only at n>=5.

Dominant failure: `insufficient_nonoverlapping_episode_density`.

Decision: `FAMILY_CLOSED`. The exact threshold/horizon/trend/control geometry does not generate enough independent train opportunities to support a durable one-lot income mechanism. Four favorable train outcomes are diagnostic only and cannot rescue density, calendar breadth, or uncertainty. The three holdout outcomes remain sealed.

Quarantine: no threshold nudge, horizon change, sign inversion, trend-filter removal, unclustered rerun, holdout read, or bull-call wrapper substitution. Reopening requires a genuinely new evidence class and a new pre-outcome charter.

## Claim-validity challenge and repairs

- Repaired a direct-source boundary discovered on real data: one 2010 Treasury row lacked both selected tenors. The parser now drops/counts only missing direct-tenor dates and never forward-fills; malformed dates, duplicates, nonpositive values, and nonfinite retained rows fail closed.
- Added a persisted-input boundary test proving the loader hashes/parses bytes reread from disk rather than an in-memory response.
- Repaired a vacuous uncertainty label: four episodes cannot pass a five-episode block gate even when its degenerate diagnostic LB equals the mean.
- Corrected the charter's source label from “constant-maturity” to the actual official Treasury daily par-yield semantics. Thresholds, population, outcomes, and decision were not changed.
- Daily curve availability is not a full bank-profit model. Deposit betas, loan repricing, securities duration, hedges, credit losses, composition, and macro-growth expectations remain unmodeled.
- Present-day KRE/XLF ETF membership and adjusted-close history limit generalization; no constituent-level or option-contract claim is made.
- Exact-date joining and next-close entry prevent same-day outcome leakage; no forward fill was used.
- Favorable n=4 center/hit/tail diagnostics are not treated as an edge because population density and uncertainty are vacuous.
- The measured ten-session underlying result is not an 18–28 DTE option-path result. No contract availability, strike, expiry, IV, debit, theta/vega path, management fill, assignment, exercise, option costs, B3, B4, or B6 was measured.

## Search information vs strategy progress

Search information gained:

- A reusable official Treasury par-yield persisted-cache adapter with source hashes, no-imputation boundary, direct 2s10s features, strict replay, and tests.
- The exact bull-steepening KRE geometry is sparse: seven signals in about twenty years, only four train observations across two train years.
- Train-only returns were favorable but non-claim-bearing because density and uncertainty failed.

Strategy progress:

- none; no F1 survivor, no L1 seat, no paper path, no registry mutation, no quality leader.
- `FAMILY_CLOSED` is the sole strategy outcome.

## Verification

- Focused behavioral/boundary/positive/negative suite: 10/10 `OK`.
- Full required suite: `.venv/bin/python -m unittest discover -s tests` -> 443/443 `OK`.
- `py_compile`: new script and tests `OK`.
- Artifact invariants: strict JSON, holdout seal, option-pricing zero, false capital seat, and exact counts `OK`.
- Persisted-cache replay: normalized payload equality true; normalized SHA-256 `7435db0cd92c1749b898e38b7b10b1bf6bf795d336caa050b360c5cb6a6e1c71`.
- Canonical artifact raw SHA-256 `f8e20be6f1c00d923b4d0c044af6099a8c82f2e0009260ab78e0b796e4611ca1`.
- Income coverage refreshed: 21 structures / 246 hypotheses / 70 evolve artifacts / no quality leader.

## Readiness / epoch implication

- Phase stays BUILD; authority stays research/paper-safe only.
- B1/B5 capability improved, but B2 remains NOT READY and B3/B4/B6 were not run for this closed candidate.
- Capital path remains empty: 0 F1/F2/F3/F4, 0 L1 candidates, 0 leaders, 0 seats.
- If accepted by challenger/finalizer, this is successor-epoch decision two with no strategy advance, so the next BUILD strategy wake must pivot to a materially different economic mechanism or evidence class. Burst-stop remains false until a third completed successor no-advance.
- Concurrent RTH state remains STAND_ASIDE: 14 eligible / 0 intents / 14 stand-asides, 0 real paper open risk, no B6 advance.

## Freedom audit

Trader remained free on symbols and structures. The prior NEXT informed the economic question but did not dictate proxy construction; direct official yields replaced the ETF proxy. The result was closed rather than promoted despite attractive four-row diagnostics.

## Durable lesson

Direct source semantics and a positive tiny sample are not enough. A repeated-exposure income mechanism must first produce a non-vacuous opportunity population before uncertainty, option wrappers, or favorable anecdotes deserve authority.

## Exactly one next seed

`MULTI_ISSUER_DIVIDEND_INCREASE_FORWARD_UPDRIFT_F0`: pivot to a materially different corporate cash-flow-confidence mechanism. Before outcomes, freeze a point-in-time regular-dividend increase definition from archived declaration-date/amount records, exclude specials/unchanged/cuts/ambiguous issuer events, predeclare a multi-issuer train-only next-close ten-session updrift test against same-date sector controls, seal holdout identities, and close-or-advance under density/specificity/uncertainty/tail gates. Future expression may be a one-lot <=$300 bull-call debit spread only after the underlying mechanism passes. No yield-curve threshold salvage, holdout reads, L1, seat, paper, shadow, arm, broker, funding, or live authority.

## Executor integration state

PARTIAL PHASE ONLY. No commit, push, merge, or RUN COMPLETE claim. Grok challenger and GPT finalizer must critique/repair this residue, update epoch state as accepted, and run the deterministic completion/integration gate.

`MOA_EXEC_DONE`

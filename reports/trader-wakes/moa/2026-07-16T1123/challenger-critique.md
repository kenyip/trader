# MoA challenger critique — 2026-07-16T1123

> Finalizer note: hashes below are truthful challenger-time receipts. Finalizer regeneration added duplicate-date fail-close, exact 10-bps round-trip cost labeling, and machine calendar concentration; current raw/normalized hashes are `676e674f…` / `36c96f9d…`. Grok's PASS WITH NITS and accepted `FAMILY_CLOSED` decision are unchanged; every nit is reconciled in `learning-promotion.md`.

CHALLENGER: Grok 4.5 (xai-oauth)
PHASE: BUILD / research-only L0 — **partial critique only**
AUTHORITY: read-only judgment; no evolve --apply; no broker; no arm; no commit/push/merge/RUN COMPLETE
SLEEVE: $3,000
DISPOSITION: **PASS WITH NITS**

## Executive judgment

Accept the executor's sole strategy outcome:

- `FAMILY_CLOSED`
- `F0_MECHANISM -> F0_MECHANISM`
- strategy advancement: **false**
- candidate: `OFFICIAL_2S10S_BULL_STEEPENING_KRE_BULL_CALL_21D_V1`
- family: `OFFICIAL_YIELD_CURVE_BULL_STEEPENING_REGIONAL_BANK_RELATIVE_UPDRIFT`
- dominant failure: `insufficient_nonoverlapping_episode_density`

Independent read-only checks match the claim-bearing artifact. Favorable n=4 train centers are diagnostic only and correctly do not rescue density, calendar breadth, or non-vacuous uncertainty. Holdout remains sealed. No L1, capital seat, paper, shadow, arm, broker, funding, or live claim is present or accepted.

## Independent evidence checks (read-only)

Canonical artifact: `reports/trader-wakes/moa/2026-07-16T1123/yield-curve-regional-bank-train.json`

| Check | Result |
|---|---|
| Raw SHA-256 | `f8e20be6f1c00d923b4d0c044af6099a8c82f2e0009260ab78e0b796e4611ca1` — **matches** executor claim |
| Normalized SHA-256 (drop only `generated_at`) | `7435db0cd92c1749b898e38b7b10b1bf6bf795d336caa050b360c5cb6a6e1c71` — **matches** |
| `strategy_decision.outcome` | `FAMILY_CLOSED` |
| Funnel | `F0_MECHANISM` → `F0_MECHANISM` |
| `gate_pass` | `false` |
| Train episodes / years | 4 / 2 |
| Holdout identities | 3; `outcome_metrics_read=false`; `option_pricing_calls=0` |
| Holdout identity SHA | `2805d49db7459e63024a5c86a61a10ca295c18315ad3f580fafc196e751e475a` |
| Failed gates | `at_least_min_train_episodes`, `at_least_min_train_years`, `kre_minus_xlf_five_episode_block_lb90_positive` |
| Living capital leader | `null` |
| Capital seat / paper / shadow-live flags | all false |
| Option path measured | false; pricing calls 0 |

Train gate detail (from artifact):

- positive KRE mean after 10 bps: true (~+4.89%)
- positive KRE−XLF mean: true (~+2.25%)
- KRE hit / paired hit / worst-decile: true / true / true
- n≥24, years≥10, non-vacuous five-episode LB: **false / false / false**

Population: 7 total frozen events (2009-11-09 … 2025-08-27); train 4 (one 2009, three 2024); holdout 3 sealed. Exact density failure is decisive.

Scripts/tests present on the run branch (uncommitted; finalizer owns integration):

- `scripts/yield_curve_regional_bank_train_lab.py`
- `tests/test_yield_curve_regional_bank_train_lab.py`

Full suite `443/443` and focused `10/10` remain **executor-claimed**. Challenger did not re-execute the suite; finalizer must re-verify before integration.

## Rubric

1. Strategy charter — **PASS**  
   Pre-outcome charter (`strategy-charter.md`) names economic mechanism, candidate/family IDs, F0 stage, predeclared falsifier, and exactly one close path (`STRATEGY_ADVANCED` F0→F1 or `FAMILY_CLOSED` F0→F0). Layered Edge Stack fields are complete for a planning bull-call expression. Closeout matches the charter.

2. Strategy vs operations — **PASS**  
   Treasury adapter + tests are search information / capability residue, not the strategy outcome. Outcome is honest `FAMILY_CLOSED`, not capability-only theater. Not a `BLOCKER_REMOVED_AND_RETESTED` claim (none needed for the decision).

3. Goal progress — **PASS**  
   Highest-information result for this loop: the exact official-2s10s → KRE relative-updrift geometry is too sparse for a durable one-lot income mechanism (7 events / ~20y; train 4 across 2 years). That is discriminating falsification, not thrash. No false seat. Chance of a paper-testable edge improves by closing a non-viable axis rather than polishing it.

4. Creativity and independence — **PASS WITH NIT**  
   Prior NEXT's economic question retained; ETF Treasury proxy correctly superseded by official daily par-yield `2 Yr`/`10 Yr` before outcome access — good independence. Mechanism differs from closed overnight-absorption and Form4/credit families.  
   **Nit:** successor epoch will reach **two consecutive no-advances** if this close is accepted → next wake **must pivot** (already reflected in executor NEXT). The dividend-increase seed is a different issuer cash-flow mechanism and satisfies pivot-required, but it still templates as direction-up → future bull-call debit. Allowed by epoch freedom; not a fail. Prefer the pivot remain mechanism-first, not another identical density-screen recipe with only the event label swapped.

5. Claim validity — **PASS**  
   Only prerequisites relevant to F0 train-only discovery were used. Missing-tenor drop without forward fill, next-close entry, exact common dates, sealed holdout, and no option marks keep the claim inside its scope. Attractive centers not promoted. Source label correction (par-yield vs constant-maturity prose) did not change geometry/outcomes.

6. Evidence and test quality — **PASS WITH NIT**  
   Real artifact, hashed sources, strict JSON, labeled costs (10 bps underlying), population purity (rising-edge, non-overlap), and correct observed-vs-proxy semantics (underlying only; option path unmeasured). Non-vacuous block gate correctly fails at n<5 even when the degenerate LB equals the mean.  
   **Nit:** finalizer must re-run focused + full suite and confirm negative/boundary tests still fail closed after any critique repairs. Challenger verified SHA/invariants only.

7. Falsification — **PASS**  
   Clear predeclared gates; three explicit failures; dominant failure named; quarantine forbids threshold/horizon/sign/trend/control/option-wrapper salvage and holdout reads. Reopening requires a new evidence class + new pre-outcome charter.

8. Capital honesty — **PASS**  
   No living quality leader; empty capital path; planning `capital_fit_usd=200`, frictionless width `max_loss_usd=200`, `max_lots=1`; semantics label that actual debit/closing friction/assignment are unmeasured. No B3/B4/B6 run claimed for a closed F0 family. No stale leader resurrected.

9. Research freedom — **PASS**  
   Free symbol/structure retained. Observed-option archive thinness did not freeze this independent historical-underlying route. Prior NEXT was context, not order. No unnecessary red-lane or prompt freeze.

10. ONE highest-information NEXT — **PASS WITH NIT**  
    Accept executor seed with challenger tightening (below). No live/shadow promotion language.  
    **Nit:** readiness `reports/readiness/LATEST.md` still shows integrated 0546 decision + `YIELD_CURVE_…_PREFLIGHT` NEXT. That NEXT is now **executed and closed**. Patch readiness ONE NEXT only in this phase; finalizer regenerates full readiness/epoch surfaces.

## Findings (ordered)

### Accept as-is (no repair required for claim validity)

A1. Exact `FAMILY_CLOSED` / false advancement / density-dominant failure.  
A2. Holdout seal, option-pricing zero, no capital seat.  
A3. Official Treasury par-yield supersede of ETF proxy was justified and pre-outcome.  
A4. Quarantine text is sufficiently strict.  
A5. Layered Edge Stack is complete enough for F0 planning; measured 10-session underlying horizon vs 18–28 DTE option plan is explicitly non-identity.

### Nits for finalizer (non-invalidating)

N1. **Epoch counters:** on acceptance, successor `REPEATED_EXPOSURE_SPECIFICITY_DISCOVERY_V1` becomes `counted_no_advance_decisions=2`, `strategy_pivot_required=true`, `strategy_burst_stop_required=false`. Update `configs/search_epoch.json` + orientation-facing readiness in finalizer, not by salvage of this family.  
N2. **Train clustering prose:** three of four train episodes sit in 2024 (plus one 2009). Year-gate already fails; finalizer should ensure durable surfaces state that calendar concentration as part of density failure, not a separate salvage path.  
N3. **Verification ownership:** re-run focused lab tests + full `unittest discover -s tests`; do not inherit 443/443 from executor prose alone.  
N4. **Dividend NEXT thrash guard:** existing dividend archive / issuer-crosscheck / assignment-guard machinery is provenance tooling for diagonals/debit verticals — **not** an F0 updrift edge. Next wake must freeze a **new** increase definition + multi-issuer train gates before outcomes; do not re-label assignment-guard corroboration as strategy advancement.  
N5. **Income-lane awareness (non-blocking):** preferred BUILD income lanes (PCS theta, defined-risk diagonals, debit swings with full stack) remain open. After a second epoch no-advance, a third no-advance triggers burst-stop. If dividend density also fails early, prefer a true mechanism/evidence-class change or search-design reassessment over another sparse event→bull-call F0 clone.  
N6. **Readiness/index surfaces:** LATEST wake already mirrors executor; INDEX needs challenger merge prepend; readiness strategy body still 0546 until finalizer regenerates — only NEXT patched here.

### Rejected / not claimed

R1. Any `STRATEGY_ADVANCED` or F1 survivor — **not claimed; not accepted**.  
R2. Any L1 / quality leader / capital seat from +4.9% KRE mean — **rejected if implied**.  
R3. Threshold salvage or holdout peek — **quarantined**.  
R4. Capability-only completion — **not the closeout form used**.

## Capital / readiness truth (accepted)

| item | state |
|---|---:|
| living strategy candidates | 0 |
| F1 / F2 / F3 / F4 | 0 |
| L1 / quality leaders / seats | 0 |
| phase | BUILD |
| authority | research / paper-safe only |

B3/B4/B6 not required after F0 family close. B1/B5 improved only as capability residue.

## Freedom audit

No removable restriction found that froze a better valid experiment. Direct official yields improved the prior NEXT rather than narrowing freedom.

## Exactly one merged NEXT seed

See `merged-next-seed.md`. Summary:

`MULTI_ISSUER_DIVIDEND_INCREASE_FORWARD_UPDRIFT_F0` — pivot (epoch no-advance #2) to a **materially different** issuer cash-flow-confidence mechanism. Pre-outcome freeze only. No yield-curve salvage.

## Partial phase boundary

- No commit, push, merge, or RUN COMPLETE by challenger.  
- Sol finalizer: reconcile nits, re-verify, promote learning, prepare deterministic integration.  
- Concurrent RTH STAND_ASIDE (14/0/14, open risk 0) remains orthogonal condition state.

`MOA_CHALL_DONE`

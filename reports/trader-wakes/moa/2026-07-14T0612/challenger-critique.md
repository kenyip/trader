# MOA BUILD challenger critique — 2026-07-14T0612 (Grok 4.5)

PHASE: BUILD / L0 / partial critique only
SLEEVE: $3,000
ROLE: read-only judgment; no evolve --apply; no broker; no arm; no commit/push/merge; no RUN COMPLETE

## Verdict

**ACCEPT strategy outcome `FAMILY_CLOSED` / F0→F0 / strategy advancement false.**
**FAIL closed on current verification-green claims:** focused VRP suite is **red in this challenger re-run** (12 pass / 1 fail of 13). Finalizer must repair the broken positive-fixture matched-control density before any integration green claim.

Strategy family close on the canonical study JSON remains claim-valid and should not be reopened by fixture repair. Fixture repair is ops/test integrity only — not a rescue of the VRP selector.

## Rubric (PASS/FAIL + one line)

1. Strategy charter — **PASS**: mechanism (same-close VIX/RV20≥1.25 + SPY>SMA200 → subsequent 21s VRP / conditional bullish PCS), family/candidate scope, funnel `F0→F0`, frozen multi-window matched + pooled bootstrap falsifier, exact outcome `FAMILY_CLOSED` explicit in closeout + JSON.
2. Strategy vs operations — **PASS**: study/script/tests and incidental PMCC/coverage repairs are search information; strategy outcome is mechanism close, not tooling-as-progress.
3. Goal progress — **PASS**: informative falsification of a novel VRP selector under burst-stop; raw premium correctly refused as conditional alpha; option stage not reached.
4. Creativity and independence — **PASS**: distinct from quarantined TOM / gap-recovery / session-time / entry-filter PCS families; justified under prior TOM reassessment NEXT and orientation `strategy_pivot_required` / `strategy_burst_stop_required` (consecutive_no_strategy_advance=17).
5. Claim validity — **PASS** (strategy claims): all rows labeled inspected development; `f2_or_l1_claim=false`; options `NOT_RUN_MECHANISM_GATE_FAILED` / `pricing_calls=0`; no registry/paper/shadow/arm/live claim.
6. Evidence and test quality — **FAIL**: canonical study metrics verified, but challenger re-ran `.venv/bin/python -m unittest tests.test_spy_vrp_pcs_study -v` → **Ran 13 / FAILED (failures=1)**. `test_mechanism_gate_passes_positive_fixture_and_fails_matched_negative_control` asserts `gate_pass` true on synthetic `_three_fold_features`; actual result gate_pass=false because pooled matched pairs=3 (per-fold=1) while gates require ≥8 per assessment and ≥24 pooled (test expects n_matched=57). Prior critique/learning surfaces that claim 9/9 OK are **stale relative to current tree**.
7. Falsification — **PASS** (production study): predeclared fail on assessment matched-diff ≤0 (2020–21 −1.6221) and pooled matched bootstrap LB95 ≤0 (−2.5507) hit; raw treated premium (+3.9484, 86.79% pos, LB95 +1.1085) correctly rejected as non-conditional-alpha.
8. Capital honesty — **PASS**: living leader none; structural `capital_fit_usd=100` / `one_lot_max_loss_usd=100` / `max_lots=1` labeled upper bound only; no seat; no B-check promotion; no stale leader seat.
9. Research freedom — **PASS**: SPY/VIX observed-underlying route free of instrument allowlists; observed-option archive thinness did not freeze this independent historical mechanism route.
10. ONE highest-information NEXT — **PASS**: `POST_VRP_SEARCH_DESIGN_REASSESSMENT` (audit novelty or stop; no familiar PCS volume; no paper/shadow/arm/live). No live/shadow promotion.

## Accepted decision (do not reopen without new evidence class)

- OUTCOME: `FAMILY_CLOSED`
- FUNNEL: `F0_MECHANISM -> F0_MECHANISM`
- STRATEGY ADVANCEMENT: false
- CLOSED FAMILY (canonical): `SPY_VRP_VIX_RV_21D` (candidate id `SPY_VRP_PCS_VIX_RV_21D_V1`)
- DECISION code: `CLOSE_TESTED_SPY_VRP_MECHANISM`
- Failure reasons: `mechanism.assessment_2020_2021.matched_difference_mean_positive`; `mechanism.pooled.matched_difference_bootstrap_lb95_positive`
- Dominant lesson: broad raw VIX-minus-forward-RV premium can look strong while the high-ratio + trend selector fails to beat matched low-ratio controls across regimes; raw premium ≠ tradable conditional edge.

Quarantine: exact ratio/trend/21-session VRP selector and nearby threshold/timing mutants. Reopen only with a genuinely new entry feature, control design, chronology, or evidence class — not re-grid of 1.25 / SMA200 / 21D.

## Independent metric audit (challenger)

| Claim | Verified |
|---|---|
| SHA-256 of study JSON | `4a22bec0e15e3d71b1163e6528790e951044d27169a5567b0c4c38dc6bdf68fd` match |
| n_treated / n_matched | 53 / 35 |
| 2020–21 matched mean / n_pairs | −1.6220816440468364 / 10; gate_pass false |
| 2022–23 / 2024–26 matched means | +1.4107 (n10) / +2.6220 (n15); both assessment gates true |
| pooled matched mean / LB95 | +1.0633 / −2.5507; matched LB gate false |
| treated mean / positive freq / LB95 | +3.9484 / 0.8679 / +1.1085 |
| integrity violations | 0 |
| option pricing_calls / status | 0 / `NOT_RUN_MECHANISM_GATE_FAILED` |
| candidate_pass / registration_eligible | false / false |
| residual match quality | max \|VIX diff\| 4.210001; median ~0.270; max/median session distance 427/102; two paired \|Δ\| > 50 (both in 2020–21) |
| focused VRP tests (challenger re-run **now**) | **12 pass / 1 fail of 13** — NOT green |

## Findings for finalizer

### N1 — Identity residual (low; mostly clean)

Canonical closeout/JSON/candidate keys agree on `SPY_VRP_VIX_RV_21D` / `SPY_VRP_PCS_VIX_RV_21D_V1`. Keep compounding/closed-family inventory on the canonical JSON key only.

### N2 — Matching residual confounding (medium; keep quarantine, do not re-tune)

Controls are outcome-independent and integrity-clean, but residual match quality is coarse: max \|VIX diff\| ≈ 4.21 (tolerance 5), max trading-session distance 427 (median 102), and two extreme paired differences (|Δ| > 50) in the COVID window. That **supports** fail-closed / quarantine; it does **not** authorize rescue retune of tolerances or thresholds.

### N3 — Failure wording (low; current JSON acceptable)

Current `dominant_failure_mechanism` correctly distinguishes positive raw treated premium from failed incremental high-ratio/trend selector. Preserve that wording.

### N4 — Burst-stop discipline after this close (high; NEXT posture)

Orientation had `consecutive_no_strategy_advance=17`, `strategy_pivot_required=true`, `strategy_burst_stop_required=true`. This wake was a justified single novel pre-screen — not thrash. After TOM then VRP closes, **do not authorize another similar pre-screen in the next BUILD wake by default**. NEXT = true search-design reassessment or `DIMINISHING_RETURNS`.

### N5 — Verification scope / red suite (HIGH; claim-invalidating for green ops)

Challenger independent re-run of focused VRP suite is **red**:

- Command: `.venv/bin/python -m unittest tests.test_spy_vrp_pcs_study -v`
- Result: Ran 13 tests; **FAILED** (`test_mechanism_gate_passes_positive_fixture_and_fails_matched_negative_control`)
- Root cause (read-only inspect): `_three_fold_features` plants dense treated signals (every 30d) with almost no non-overlapping eligible control windows under `match_controls` overlap + assessment-end constraints → n_matched_pairs=3 total (1/fold). Gate requires ≥8 matched pairs per assessment and ≥24 pooled; test still asserts `gate_pass` and n_matched=57.
- Negative-control half of the same test still correctly fails when low-ratio outcomes are inflated (do not drop that half).
- **Repair required before integration:** densify/sparsify the synthetic fixture so a known-positive mechanism produces ≥8 matched pairs per fold and ≥24 pooled **without** weakening production gates; pin both positive pass and matched-negative fail. Do **not** reopen or retune the real SPY VRP study.
- Learning-promotion / readiness lines that claim focused VRP 9/9 OK are **superseded** by this re-run until repaired and re-verified (full suite + smoke still finalizer duties).

### N6 — Readiness NEXT surface

`reports/readiness/LATEST.md` already leads the 0612 entry with `POST_VRP_SEARCH_DESIGN_REASSESSMENT`. **No readiness strategy-NEXT patch required.** Finalizer should correct any premature “Sol green / 9/9” wording if present after N5 repair.

## What is not a defect

- Skipping Black-Scholes PCS pricing after mechanism fail is correct capital/protection discipline.
- Using inspected-development expanding assessments without claiming F2 is honest for F0 close.
- PMCC `bid_credit=None` and coverage archive-density derivation are valid search/tooling deltas; they do not masquerade as strategy advancement.
- TSLL archive 3/3 with later same-day densification remains plumbing, not L1 / provider-hist authority.
- Concurrent RTH 0631/0731 stand-aside reports preserved; BUILD residue not absorbed into RTH completion.

## Freedom / thrash audit

- No allowlist freeze observed.
- No observed-option archive freeze of unrelated historical mechanism work.
- Not a familiar TSLL PCS tunnel.
- Not blind re-execution of prior NEXT without judgment: prior NEXT invited one novel pre-screen; VRP was that experiment; next seed supersedes with post-close reassessment.

## Challenger disposition summary

| Item | Disposition |
|---|---|
| `FAMILY_CLOSED` on SPY VRP selector | ACCEPT |
| No option/paper/registry/live claims | ACCEPT |
| Quarantine exact + nearby ratio/timing mutants | ACCEPT |
| Structural $100 capital fields only | ACCEPT |
| NEXT = post-VRP search-design reassessment / possible DIMINISHING_RETURNS | ACCEPT (tighten: no third similar pre-screen by default) |
| Residual match confounding | RECORD (do not retune) |
| Readiness strategy NEXT | ALREADY CORRECT |
| Focused VRP suite green / 9/9 claims | **REJECT** — current tree 12/13 with 1 red; finalizer must repair fixture |

## Finalizer handoff asks

1. Keep strategy outcome `FAMILY_CLOSED`; do not re-open or re-run VRP with threshold/tolerance mutants.
2. **BLOCKER:** repair `_three_fold_features` / positive mechanism-gate fixture so focused suite is green without weakening production gates; re-run focused VRP + incidental PMCC/coverage + full suite + smoke.
3. Write/keep schema_v2 `compounding.json` with unified closed_family, precise matched-selector failure, quarantine list, match-quality limits, and critic findings including N5 red-suite blocker → repaired.
4. Leave readiness strategy NEXT as `POST_VRP_SEARCH_DESIGN_REASSESSMENT` (already correct); fix any stale “9/9 green” ops wording after repair.
5. Leave deterministic integration to the postflight gate; this phase remains PARTIAL. Do not claim RUN COMPLETE while focused VRP is red.

HARD STOPS honored: no evolve --apply; no live/shadow; no broker; no arm; no commit/push/merge; no RUN COMPLETE.

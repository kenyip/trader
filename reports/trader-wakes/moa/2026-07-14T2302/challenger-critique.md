# MOA challenger critique — 2026-07-14T2302 (Grok 4.5)

PHASE: BUILD / L0. Sleeve USD 3000. PARTIAL critique phase only.
Roles: read-only judgment. No evolve --apply, no broker, no arm, no commit/push/merge, no RUN COMPLETE.

## Executive disposition

**PASS WITH NITS** on strategy substance.

Accept executor decision `FAMILY_CLOSED` for exact family `MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT` / candidate `CROSS_SECTION_LOW_HV_PCS_21D_V1` at `F0_MECHANISM → F0_MECHANISM`. Independent re-run from cache reproduces train gate failure, zero integrity violations, untouched holdout, and `pricing_calls=0`. Strategy advancement is false. This is useful search information, not a capital seat.

Do **not** accept the provisional `executor-closeout.md` body as the final claim surface (still ends in `PENDING EXECUTOR EXPERIMENT`). Canonical evidence is the train JSON + lab code/tests. Finalizer must reconcile closeout/exec report residue.

## Canonical evidence (challenger-inspected pre-finalizer version)

| Item | Path / value |
|---|---|
| Artifact | `reports/trader-wakes/moa/2026-07-14T2302/low-hv-cross-section-train.json` |
| SHA-256 at challenge time | `32494794cf49d3d460357616ffbe48a8ad8feb09b5dcdcb7b394d2265f45186e` |
| Lab | `scripts/low_hv_cross_section_train_lab.py` |
| Tests | `tests/test_low_hv_cross_section_train_lab.py` |
| Outcome | `FAMILY_CLOSED` / `CLOSE_FIXED_LOW_HV_CROSS_SECTION_TRAIN_FAMILY` |
| Funnel | `F0_MECHANISM` → `F0_MECHANISM` |
| Closed family | `MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT` |
| Train n | 43 (≥24) |
| Low-HV mean | +0.0280448 |
| High-HV mean | +0.0553492 |
| Paired excess mean | −0.0273044 |
| Excess median | −0.0375955 |
| Positive excess freq | 0.3488 |
| Bootstrap LB90 (10k, block=3, seed 20260714) | −0.0416182 |
| Gate pass | false (`positive_paired_excess_mean` and `paired_excess_bootstrap_lb90_positive` false; density/integrity/low-HV mean true) |
| Holdout | 30 blueprints reserved; `outcome_metrics_read=false`, `simulation_run=false` |
| Option stage | `NOT_RUN_TRAIN_GATE_FAILED`, `pricing_calls=0` |
| Capital context | structural `capital_fit_usd=max_loss_usd=100`, `max_lots=1` (not simulated trade loss) |
| Living leader / seat | none / none |
| Focused tests (challenger re-run) | 6/6 OK |
| Independent re-run | same decision and same substantive gate numbers (float noise only) |

Finalizer reconciliation note: the accepted failure-label repair and a fresh `generated_at` regenerated the canonical JSON at SHA-256 `9ab27b71c7fb2a0ed4cc0c0a41426ae709ba5cc7b0cf449058ecceca2f5187f2`; an independent finalizer rerun reproduced every substantive field after excluding only `generated_at`. Final living surfaces and exact verification are in `learning-promotion.md`.

## Rubric

### 1. Strategy charter — PASS (nit: incomplete closeout file)
Economic mechanism, family scope, F0 stage, predeclared falsifier, and binary advance-or-close decision are explicit in the provisional closeout header and fully in the JSON. One closed outcome: `FAMILY_CLOSED`.
Nit: `executor-closeout.md` still says `PENDING EXECUTOR EXPERIMENT` after the experiment finished; finalizer must replace that with the realized metrics/decision.

### 2. Strategy vs operations — PASS
New harness + tests are capability, but the wake exercised the dependent train-only experiment to an advance-or-close decision in-session. Not capability-only theater. Search information and strategy outcome are separable: harness is durable; advancement is false.

### 3. Goal progress — PASS
Honest F0 falsification of a new cross-sectional risk-selector improves the chance of later paper-testable edge by removing a non-working pre-screen and blocking premature option-stage work. No false advance. Stand-aside/close is valid progress.

### 4. Creativity and independence — PASS
Follows prior 2203 NEXT as context (lagged monthly low-HV cross-section), not as blind order, and is a material pivot away from closed PCS-stop / VRP / TOM / entry-filter families. Fixed 14-name liquid universe + bottom-3 vs top-3 is a new loop signature vs prior single-name filter stacks. No familiar TSLL PCS tunnel.

### 5. Claim validity — PASS (nits)
Prerequisites match the experiment: historical adjusted closes only; discovery bar / L0; train before holdout; no option marks; survivorship/listing bias labeled; generalization disallowed.
Nits for finalizer wording:
- Dominant-failure text should not imply low-HV absolute drift failed. **Low-HV mean was positive**; the family fails **incremental edge** (low-minus-high mean and bootstrap LB).
- Bottom-3 of 14 is ~bottom 21%, not literally “bottom-quartile” from the prior NEXT wording — acceptable because the wake predeclared `quantile_count_each_side=3`, but labels must stay consistent.
- Do not treat post-hoc “high-HV outperformed” as a free inverted edge without a new predeclared economic mechanism and falsifier.

### 6. Evidence and test quality — PASS (nits)
Real code, real multi-name panel (2,645 common rows 2016-01-04→2026-07-13), non-overlapping monthly episodes, lagged HV (`feature_max_date == rank_date < entry_date`), disjoint groups, strict JSON, cache provenance + trailing unsettled-NaN discard. Challenger re-ran focused tests 6/6 and reproduced gate failure.
Nits:
- Add a **negative-control** unit test that asserts `FAMILY_CLOSED` / `gate_pass=false` when low-HV mean is positive but paired excess is non-positive (current suite covers the advance path more strongly than the reject path).
- `moa-exec.md` missing; closeout stale; executor self-marked `MOA_EXEC_INCOMPLETE` after iteration budget — finalizer must complete report surfaces.
- Independent re-run float noise at 1e-16 is fine; do not overclaim byte-identical full payload without excluding `generated_at` and provenance shape differences from helper call path.

### 7. Falsification — PASS
Predeclared density + positive low-HV mean + positive paired excess + positive bootstrap LB90. Density and absolute low-HV drift passed; **incremental-edge gates failed decisively** (excess mean −2.73%, LB90 −4.16%, only ~35% positive excess episodes). Quarantine exact family and nearby unchanged knobs.

### 8. Capital honesty — PASS
No living leader, no L1/seat, no after-cost option claim. Planned one-lot $1-wide PCS structural bound $100 only. No shadow/live promotion language in the decision path.

### 9. Research freedom — PASS
Did not freeze research on observed-option archive density. Used valid historical-underlying route. No unnecessary allowlist tunnel.

### 10. ONE NEXT seed — PASS WITH CORRECTION
Executor NEXT over-states **three-wake burst stop**. Orientation entering this wake: epoch no-advance streak = 1; pivot/burst false. After this accepted close: **streak = 2 → strategy_pivot_required = true**; **burst_stop remains false until three** completed epoch wakes without `STRATEGY_ADVANCED`.
Corrected ONE NEXT: see `merged-next-seed.md`.

## Integrity audit (challenger)

| Check | Result |
|---|---|
| Chronology rank < entry < exit | hold (code + tests) |
| Feature uses completed HV only | hold (`min_periods=hv_lookback`; shock-on-entry does not change ranks) |
| Non-overlapping episodes | hold |
| Holdout unread | hold |
| Option pricing absent | hold |
| Population purity / ranking complete within fixed panel | hold |
| Survivorship / present-day listing bias | labeled; generalization false |
| Registry mutation | none observed |
| Broker / live / arm | none |

## Accepted findings for finalizer

1. **Accept** `FAMILY_CLOSED` / F0→F0 / no strategy advancement.
2. **Rewrite** `executor-closeout.md` Outcome section with realized metrics; remove PENDING.
3. **Write** `reports/trader-wakes/2026-07-14T2302-moa-exec.md` (or equivalent finalizer-owned exec residue) so stamp surfaces are complete.
4. **Tighten** dominant-failure wording to relative-edge failure (not absolute low-HV drift failure).
5. **Add** reject-path negative-control unit test; re-run focused + full suite.
6. **Quarantine scope**: exact family + nearby knobs on the same fixed present-day 14-name panel (HV lookback, k-of-14, 21-session non-overlapping monthly episodes). Not a ban on all cross-sectional research forever.
7. **Streak policy**: after integration, epoch no-advance = 2 → next strategy wake must **pivot** mechanism/evidence class; do not run volume on inverted high-HV or retuned low-HV without a new predeclared mechanism. Burst-stop only if a third consecutive no-advance completes.
8. **Do not** register, paper, shadow, arm, or claim L1.

## Rejected / not required

- Reopening the family by flipping to high-HV long after seeing train outcomes.
- Holdout peek “just to learn.”
- Option-stage BS pricing after failed underlying gate.
- Capital-seat or living-leader language.
- Global `DIMINISHING_RETURNS` freeze of all BUILD (observed archive remains parallel-only; other open routes still exist, but **pivot** is mandatory).

## Challenger verification performed

- Read doctrine, orientation, prior 2203 merge, readiness, coverage.
- Parsed and audited train JSON metrics/gates/holdout/option stage.
- Read lab + tests; re-ran `tests.test_low_hv_cross_section_train_lab` → 6/6 OK.
- Independent `run_lab_from_panel` from `.cache/platform/low_hv_cross_section` → same decision and substantive train metrics.
- No evolve --apply; no broker; no commit.

## Overall

**PASS WITH NITS.** Strategy close is sound. Residue completion and streak language are finalizer work. ONE NEXT is pivot-required search design / new mechanism selection — not high-HV inversion and not premature three-wake burst stop.

MOA_CHALL_PARTIAL

# Learning promotion — 2026-07-14T2302

Strategy charter: within the fixed present-day 14-name liquid-equity panel, the monthly bottom-three names by prior completed 60-session realized volatility were expected to retain steadier positive 21-session forward drift than the same-date top-three control; only a surviving underlying selector could later condition a one-lot `$1`-wide put credit spread. Scope was train-only L0 underlying discovery, non-overlapping episodes, chronological first 60%, `F0_MECHANISM -> F0_MECHANISM`, structural `capital_fit_usd=max_loss_usd=100`, and `max_lots=1`.

Outcome: `FAMILY_CLOSED`; strategy advancement false. Train n=43. Low-HV absolute mean was positive (`+0.028044839681`), but high-HV mean was `+0.055349242755`; paired excess mean was `-0.027304403074`, median `-0.037595516809`, positive frequency `0.348837209302`, and one-sided 90% circular-block-bootstrap lower bound `-0.041618164833`. Density, chronology, disjoint groups, strict serialization, and absolute low-HV drift passed; incremental mean and bootstrap gates failed. The final 40% remains 30 unread blueprints, option pricing did not run, and no L1/capital-seat/registry/paper/shadow/arm/live claim exists.

## VERIFICATION

- `.venv/bin/python -m unittest -v tests.test_low_hv_cross_section_train_lab` -> `Ran 7 tests in 0.055s`, `OK`. Behavioral/boundary coverage includes lagged completed-HV ranking, entry-bar shock invariance, disjoint controls, chronology/non-overlap, positive advance fixture, positive-absolute-drift/non-positive-excess reject path, untouched-holdout serialization, cache reuse, trailing-only unsettled-NaN handling, and complete common-date population assembly.
- `.venv/bin/python -m py_compile scripts/low_hv_cross_section_train_lab.py tests/test_low_hv_cross_section_train_lab.py` -> exit `0`.
- `.venv/bin/python scripts/low_hv_cross_section_train_lab.py --out reports/trader-wakes/moa/2026-07-14T2302/low-hv-cross-section-train.json` -> exit `0`; `FAMILY_CLOSED`, train n43, paired excess `-0.027304403074314778`, bootstrap LB90 `-0.04161816483305848`, holdout n30 unread, `pricing_calls=0`.
- Independent unchanged-source rerun to `/tmp/low-hv-cross-section-train-finalizer.json` and full substantive comparison excluding only `generated_at` -> `SUBSTANTIVE_REPRODUCTION_OK`; canonical SHA-256 `9ab27b71c7fb2a0ed4cc0c0a41426ae709ba5cc7b0cf449058ecceca2f5187f2`.
- `.venv/bin/python scripts/trader_income_coverage.py --stamp 2026-07-14T2302` plus dated/LATEST `cmp` -> exit `0`, `COVERAGE_SURFACES_IDENTICAL`; 21 structures, 246 hypotheses, 70 evolve artifacts, living leader none.
- `just platform-smoke` -> exit `0`, `platform smoke OK`; `agentic_live` remained blocked at the Stage1 OAuth gate.
- `.venv/bin/python -m unittest discover -s tests` -> `Ran 276 tests in 12.706s`, `OK`.
- `git diff --check` -> exit `0`.
- `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-14T2302 --base-head f8245d4969059a1f755d1dddda193e774e2f1cb8` -> exit `0`; `ok=true`, `role_ready=true`, schema 2 `FAMILY_CLOSED`, strategy advancement false, four useful deltas, six critic findings closed.
- Temporary-index deterministic prepare (`GIT_INDEX_FILE=<temp>`; `git read-tree HEAD`; `git add -A`; `.venv/bin/python scripts/trader_run_completion_gate.py prepare --repo . --stamp 2026-07-14T2302 --base-head f8245d4969059a1f755d1dddda193e774e2f1cb8 --run-branch trader/run-2026-07-14T2302`) -> exit `0`; `ok=true`, `mode=prepare`, 19 intended files, sensitive-path/raw-secret/diff/handoff guards green. The temporary index was removed and the real index remained unstaged.

## DURABLE

All material challenger findings were accepted and reconciled:

1. `FAMILY_CLOSED`, F0→F0, and no strategy advancement were accepted; final living reports and schema-v2 handoff carry the same decision.
2. The stale `PENDING EXECUTOR EXPERIMENT` ending was replaced in `executor-closeout.md` with realized metrics, capital/authority boundaries, and the exact close.
3. Missing `reports/trader-wakes/2026-07-14T2302-moa-exec.md` was written as finalizer-reconciled executor evidence rather than pretending the executor completed its report surface.
4. Dominant-failure wording was tightened everywhere: positive absolute low-HV drift passed, while incremental low-minus-high edge and its bootstrap lower bound failed.
5. `tests/test_low_hv_cross_section_train_lab.py` now has the requested reject-path negative control: positive low-HV absolute drift plus non-positive paired excess produces `gate_pass=false` and `FAMILY_CLOSED`. The machinery's failure label in `scripts/low_hv_cross_section_train_lab.py` is asserted by that test.
6. Quarantine is limited to `MONTHLY_CROSS_SECTION_LOW_HV_FORWARD_DRIFT` and nearby unchanged HV-lookback, k-of-14, and 21-session knobs on the same fixed present-day panel. The post-hoc high-HV winner is not promoted as a free inversion.
7. Active-epoch streak language is corrected: after 2203 and this accepted close, no-advance is 2, so `strategy_pivot_required=true`; `strategy_burst_stop_required=false` until a third consecutive no-advance close.
8. Registration, holdout inspection, option pricing, capital-seat language, paper, shadow, arm, broker, and live actions remain rejected/not required. A global BUILD freeze is also rejected; the next wake must pivot rather than stop all open routes.

The dated outcome/current truth is promoted through the canonical JSON, executor closeout/report, final merge/LATEST, INDEX, readiness, deterministic coverage surface, and schema-v2 compounding handoff. The profile-local `trader-self-evolution` skill now records the reusable pitfall: positive absolute selector drift does not establish incremental edge; paired-gate failures require an explicit reject-path test, accurate failure wording, bounded quarantine, and no post-hoc inversion. Profile memory is unchanged because this is dated project evidence and reusable procedure, not a stable Ken preference or routing fact.

Integration is pending the deterministic wrapper gate. The finalizer did not stage the real Git index, commit, push, merge, switch branches, edit `.gitignore`, place an order, or claim `RUN COMPLETE`.

## LESSON

Future Trader can evaluate a lagged monthly cross-sectional selector without spending holdout or option-model effort, and can distinguish broad positive market drift from genuine incremental selector value. A positive absolute basket return is insufficient when the same-date control is stronger: the mechanism must pass its paired excess and uncertainty gates. The reusable harness now proves both advance and reject paths, preserves an unread holdout, labels survivorship/listing limits, and blocks post-hoc inversion from masquerading as a predeclared edge.

## NEXT

`STRATEGY_PIVOT_REQUIRED` after two consecutive active-epoch no-advance closes: before another strategy-volume wake, inventory and execute exactly one materially different open economic mechanism or evidence class outside quarantined families. Predeclare the mechanism, use a population that is not merely fixed present-day survivorship convenience where feasible (otherwise label non-generalizing L0), freeze the train falsifier, and inspect untouched holdout only after train survival. Do not retune HV lookback/k-of-14/21-session knobs, invert the observed high-HV result, or price options before underlying advancement. No paper/shadow/arm/live.

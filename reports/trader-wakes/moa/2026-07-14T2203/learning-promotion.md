# Learning promotion — 2026-07-14T2203

Strategy charter: in bullish or neutral regimes, one-lot Monday-entered 45-DTE approximately 0.20-delta `$1`-wide put credit spreads may harvest front-loaded theta while a 21-DTE calendar exit avoids late-cycle gamma/tail exposure relative to the otherwise-identical 5-DTE-stop control. Scope was the fixed outcome-rank-free population BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL, train-only Black-Scholes proxy marks, `F0_MECHANISM -> F0_MECHANISM`, `capital_fit_usd=max_loss_usd=$85.76..$235.43`, and operating `max_lots=1`.

Outcome: `FAMILY_CLOSED`; strategy advancement false. Eight of eight names completed, zero passed both train cost axes, all 5% adverse-leg-slip rows were negative (`-$750.97..-$85.95`), fixed `$0.01` rows were negative on seven of eight, and AAPL's fixed-cost `+$128.60` paired with 5% `-$470.44`. The final 40% holdout stayed untouched. The honest dominant failure is cost-adjusted expectancy under profit-target/regime-flip-dominated Monday 45-DTE PCS management with sparse calendar-stop contrast: 17 candidate stop exits across 16 symbol/cost rows, including path-identical F and SOFI controls. This is not pure early-theta/late-gamma isolation.

## VERIFICATION

- `.venv/bin/python -m unittest -v tests.test_pcs_early_exit_train_lab tests.test_pcs_expiry_grid tests.test_pcs_time_bias_grid tests.test_pcs_momentum_walkforward_lab tests.test_pcs_gap_recovery_chronological_lab` -> `Ran 37 tests in 0.556s`, `OK`. This covers candidate/control purity, weekday and listed-expiry boundaries, no-same-bucket/no-same-bar behavior, lagged features, dual-cost gates, invalid/vacuous/inexact control negative cases, train-only ranking, calendar-stop diagnostics, and operating/theoretical lot labels.
- `.venv/bin/python -m unittest tests.test_pcs_early_exit_train_lab -v` -> `Ran 5 tests in 0.000s`, `OK`.
- `.venv/bin/python -m py_compile scripts/pcs_early_exit_train_lab.py tests/test_pcs_early_exit_train_lab.py` -> `PY_COMPILE_RC=0`.
- `.venv/bin/python scripts/pcs_early_exit_train_lab.py --out reports/trader-wakes/moa/2026-07-14T2203/pcs-early-exit-train.json` -> exit `0`; `FAMILY_CLOSED`, 8 completed, 0 discovery passes, no errors.
- Independent exact rerun to `/tmp/pcs-early-exit-train-finalizer.json` plus comparison excluding only `generated_at` -> `SUBSTANTIVE_REPRODUCTION_OK`, `rows=8 axes=32 candidate_calendar_stops=17`, `REPRODUCTION_RC=0`; canonical SHA-256 `39113fe2aa6fa071a09902470fad3e39a30cf765a2dfdf32e1d42986a9c6446e`.
- `.venv/bin/python scripts/trader_income_coverage.py --stamp 2026-07-14T2203` plus dated/LATEST byte comparison -> `COVERAGE_RC=0`, `COVERAGE_SURFACES_CMP_RC=0`; 21 structures, 246 hypotheses, 70 evolve artifacts, living leader none.
- `just platform-smoke` -> `PLATFORM_SMOKE_RC=0`, `platform smoke OK`; `agentic_live` remained blocked at the Stage1 OAuth gate.
- `.venv/bin/python -m unittest discover -s tests` -> `Ran 269 tests in 12.811s`, `OK`, `FULL_SUITE_RC=0`.

## DURABLE

All five challenger findings were accepted and reconciled:

1. Sparse mechanism contrast: accepted. Living surfaces now lead with cost-adjusted expectancy under profit-target/regime-dominated management and explicitly state 17 candidate stop exits plus path-identical F/SOFI controls; they reject pure early-vs-late gamma isolation.
2. Quarantine scope: accepted. Only `pcs-monday-45dte-exit21-vs-exit5-train-proxy` and nearby stop nudges/symbol cherry-picks of the same DNA are closed. New Monday or 45-DTE mechanisms remain admissible only with a genuinely different mechanism or evidence class.
3. Lot labels: accepted and repaired in `scripts/pcs_early_exit_train_lab.py` and `tests/test_pcs_early_exit_train_lab.py`. Axis rows retain shared-summarizer capacity as `theoretical_max_lots=3` but now state `operating_max_lots=1` and `max_lots=1`; top-level rows state `capital_fit_usd`, `max_loss_usd`, `one_lot_max_loss_usd`, and the one-lot operating cap. The canonical experiment was regenerated and reproduced without changing the strategy decision.
4. Verification ownership: accepted. Finalizer reran focused behavioral/boundary/negative-control/regression checks, compile, the exact dependent experiment and reproduction, coverage, smoke, and the full 269-test suite rather than inheriting challenger self-report.
5. NEXT anti-leakage: accepted. The sole seed uses prior completed 60-session HV known before each rank month, same-date top-quartile controls, chronological underlying train then untouched holdout, and option marks only after underlying advancement.

Dated truth is promoted through the canonical JSON, final merge/LATEST, INDEX, readiness, regenerated coverage, and schema-v2 compounding handoff. The profile-local `trader-self-evolution` skill was patched to preserve theoretical sleeve capacity only under `theoretical_max_lots` while requiring explicit `operating_max_lots=1` / `max_lots=1`, one-lot `capital_fit_usd`/`max_loss_usd`, and a regression test. Profile memory is unchanged because this is dated project evidence and a reusable procedure, not a stable Ken preference or routing fact.

Integration is pending the deterministic wrapper gate. The finalizer did not stage the real index, commit, push, merge, switch branches, edit `.gitignore`, place orders, or claim `RUN COMPLETE`.

## LESSON

Future Trader can run a fixed-DNA train-only causal-management comparison without spending holdout, but it must measure whether the management difference actually binds before interpreting mechanism causality. Here only sparse calendar-stop exits separated candidate from control, while ordinary profit-target/regime exits dominated; negative dual-cost expectancy closes this exact DNA but does not prove that every Monday or 45-DTE PCS management hypothesis lacks edge. Living capital labels must also distinguish an engine's theoretical sleeve capacity from the experiment's one-lot operating authority; ambiguous `max_lots` fields are a readiness defect even when the strategy outcome is unchanged.

## NEXT

Build and run one lagged monthly cross-sectional low-realized-volatility underlying pre-screen over a fixed liquid multi-name universe: rank only on prior completed 60-session HV known before each rank month, compare bottom-quartile forward returns with same-date top-quartile controls, use chronological train then untouched holdout on the underlying mechanism, and reach option marks only if that mechanism advances under a predeclared falsifier; do not retune the closed PCS stop family or take paper/shadow/arm/live action.

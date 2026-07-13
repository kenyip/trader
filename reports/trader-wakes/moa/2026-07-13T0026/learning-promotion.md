# Learning promotion — 2026-07-13T0026

## VERIFICATION

- `.venv/bin/python -m unittest tests.test_double_diagonal_sim tests.test_double_diagonal_chronological_lab -v` → `Ran 9 tests in 0.044s` / `OK`. Coverage includes structure purity, exact four-leg percentage/fixed costs, candidate-budget fail-close, no-close-bar reentry, American intrinsic-floor/signed-liquidation behavior, realized loss beyond structural debit, operating `max_lots=1` versus separately labeled 2–3-lot theoretical capacity, the unchanged `$300` boundary, exact capital/ledger fields, and passing-holdout/failing-train rejection.
- `.venv/bin/python -m unittest tests.test_trader_completion_contract.TraderCompletionContractSurfaceTest.test_integrate_only_recovery_mode_is_parseable -v` → `Ran 1 test in 0.019s` / `OK`; context-only execution emitted `mode=integrate-only` and the explicit recovery stamp without entering finalization or integration.
- `.venv/bin/python -m trader_platform.smoke_test` → `platform smoke OK`; registry/paper/shadow dry paths remained healthy and `agentic_live` remained blocked at the Stage1 Robinhood OAuth gate.
- `.venv/bin/python -m unittest discover -s tests` → `Ran 181 tests in 6.831s` / `OK`.
- `.venv/bin/python scripts/double_diagonal_chronological_lab.py --stamp 2026-07-13T0026 --out .cache/platform/double_diagonal_chronological_lab_2026-07-13T0026.json` → `REJECT_DOUBLE_DIAGONAL_PROXY_THIS_CYCLE`, `n_completed=8`, `n_all_axes_pass=0`, `errors=[]`.
- Independent artifact summary → maximum absolute train/holdout ledger delta `1.1368683772161603e-13`, same-bar reentries `0`, maximum holdout-window DD `249.33746426821205`; updated representative metrics are recorded in `reports/trader-wakes/2026-07-13T0026-moa-merge.md`.
- `.venv/bin/python scripts/trader_income_coverage.py --stamp 2026-07-13T0026` → regenerated dated and current coverage at `21` structures / `245` hypotheses / `67` evolve artifacts / no living leader.
- Changed-Python compile → clean for simulator, catalog/evolve wiring, chronological runner, coverage generator, and both new test modules.
- Pointer equality checks → wake `LATEST.md` byte-equals the finalized merge report; income-coverage `LATEST` byte-equals the dated `2026-07-13T0026` report.
- `scripts/trader_build_compounding.py validate-handoff ...` → `ok=true`, `outcome=FALSIFIED`, `useful_delta_count=5`, `critic_findings_closed=5`, `role_ready=true`.
- Complete alternate-index audit of 29 current changed paths → 18 added / 11 modified; no sensitive/private paths, generated session/prompt/cache debris, symlinks, binary patches, private-key/provider-token patterns, dangerous eval/exec, pickle load, or `shell=True`; both derived pointer pairs exact.
- `scripts/trader_run_completion_gate.py prepare ...` under a temporary alternate index → `ok=true`, `mode=prepare`, base/branch matched, `staged_files=29`. The real index remained untouched and ordinary status was rechecked with `GIT_INDEX_FILE` unset.
- Independent read-only diff reviewer was dispatched against the complete base diff; its verdict is incorporated before readiness is emitted.
- Integration is pending the deterministic wrapper gate. This finalizer did not commit, push, merge, switch branches, access broker/private-position/secret state, cross paper/live gates, or claim RUN COMPLETE.

Critique dispositions:

- **F1 accepted and repaired.** `scripts/double_diagonal_chronological_lab.py` makes the exact 60/40 eight-symbol dual-cost reject reproducible without relying on executor session prose. It does not reopen, retune, or register the rejected seed.
- **F2 accepted and repaired.** `complete_evidence_gate` is conjunctive across train, untouched holdout, and window/integrity gates. `test_complete_gate_rejects_passing_holdout_when_train_failed` proves a favorable holdout cannot fail-open through a failed train.
- **F3 rejected as an outstanding current-run repair.** Same-close daily-bar semantics remain explicitly promotion-blocking and all evidence stays L0; no candidate, L1, paper, or universal-family claim depends on them. The sole NEXT supplies prior-completed 30-minute evidence rather than hiding a TODO behind this rejection.
- **F4 rejected as a defect.** Catalog and reports say symmetric double-calendar/inside-wing diagonal, and every outcome is scoped to the exact 14/60 neutral/high-IV seed/configuration/cycle. No universal time-spread closure is claimed.
- **Finalizer independent findings accepted and repaired.** A European BS back-leg mark could fall below American intrinsic while zero-clipped package liquidation hid closing friction, and generic `capital_fit_pcs` capacity could report 2–3 lots despite the executor's conservative one-lot posture. Protective legs now retain intrinsic value, package liquidation remains signed, capital reports `max(structural entry debit, observed stressed path loss)`, operating `max_lots` is capped at one, and `theoretical_max_lots` retains capacity math under an explicit non-operating label. Tests force deep-ITM front-expiry marks, a realized path loss greater than structural debit, and the one-lot/theoretical-capacity separation without weakening `$300`.

## DURABLE

- Reusable simulator and dispatch: `trader_platform/research/double_diagonal_sim.py`, `trader_platform/strategy_dna.py`, and `trader_platform/evolve_tick.py` provide a structure-pure same/inward four-leg L0 path with exact adverse leg-cost accounting and honest capital labels.
- Reproducible evidence: `scripts/double_diagonal_chronological_lab.py` and `tests/test_double_diagonal_chronological_lab.py` preserve the exact chronological reject design and conjunctive-gate negative control.
- Boundary tests: `tests/test_double_diagonal_sim.py` preserves structure purity, cost arithmetic, debit-budget rejection, no same-bar reentry, American intrinsic floor, signed closing friction, structural-versus-observed loss behavior, and the enforced one-lot operating cap versus separately labeled theoretical capacity.
- Recovery capability: `scripts/trader_build_lab_moa.sh --integrate-only --stamp <stamp>` now reaches the already-existing integration-only recovery branch through explicit CLI parsing; `tests/test_trader_completion_contract.py` proves the parser boundary in context-only mode without running any integration side effect.
- Project truth/history: `docs/BUILD_LAB_ENVIRONMENT.md` and `docs/INCOME_STRATEGY_COVERAGE.md` record the capital boundary and exact-seed rejection; dated/current readiness, coverage, executor/challenger amendments, merge, LATEST, and INDEX surfaces agree on BUILD/L0, 0/8, no leader, and no promotion.
- Skill: profile skill `trader-self-evolution` now records the reusable debit-proxy rule: intrinsic-floor American protection, retain signed liquidation costs, distinguish structural debit from observed stressed path loss, and keep proxy costs L0.
- Memory: no update. This is reusable procedure and dated repository truth, not a stable user preference or routing fact.
- Integration remains pending the deterministic wrapper gate.

## LESSON

Future Trader can now build and rerun a same/inward double-diagonal proxy without laundering closing friction through a zero floor, calling paid debit an unconditional live max loss, or presenting generic 2–3-lot capacity math as the operating posture. American protective legs need an intrinsic floor even when the proxy pricer is European; package liquidation must stay signed under explicit costs; capital evidence should carry both the frictionless structural bound and observed stressed path loss; and operating `max_lots=1` must remain distinct from `theoretical_max_lots`. A chronological reject is promotion-safe only when train, untouched holdout, and window/integrity gates are conjunctive and a passing-holdout/failing-train negative control proves that ordering. The exact 14/60 neutral/high-IV seed is closed for this cycle at L0, while unrelated symbols, strategies, and future prior-completed session-time evidence remain open.

## NEXT

Build one no-lookahead completed-30-minute-bar session-time evidence route for defined-risk PCS/CCS/IC across BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL. Use prior-completed features only; compare open/midday/late buckets; select on chronological train and evaluate once on untouched holdout; apply 5% adverse leg slip and `$0.01` half-spread per leg; require positive non-vacuous holdouts, one-lot `max_loss_usd <= $300`, window max DD `<= $75`, dense-negative windows `<= 5`, exact ledger, and no same-bar/same-bucket reentry. Keep L0, register nothing first pass, and do not reopen the rejected double-diagonal seed or closed daily-bar families.

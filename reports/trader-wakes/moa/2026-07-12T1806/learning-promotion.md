# Learning promotion — 2026-07-12T1806

## VERIFICATION

- `.venv/bin/python -m unittest tests.test_corporate_action_risk tests.test_debit_vertical_sim tests.test_diagonal_oos_stress tests.test_defined_risk_fixed_cost -v` → `Ran 16 tests in 0.171s` / `OK`.
- `.venv/bin/python -m trader_platform.smoke_test` → `platform smoke OK`; agentic live remained blocked by the Stage1 OAuth gate.
- `.venv/bin/python -m unittest discover -s tests` → `Ran 146 tests in 6.731s` / `OK`.
- `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-12T1806` → 20 catalog structures / 245 hypotheses / 67 evolve artifacts; no quality leader; dated and LATEST coverage files regenerated.
- Final diff/secret/path hygiene and `git diff --check` are finalizer gates still to be recorded before handoff.

Critique dispositions:

- Accepted and repaired catalog honesty lag: `STRUCTURE_CATALOG` now places `early_assignment_risk` first for diagonal and bull-call exits and records provider/`known_at`/non-dividend limitations. Test: `test_catalog_exposes_provider_dependent_assignment_guard`.
- Accepted and repaired thin simulator threshold coverage: both simulators now have an integration negative control proving a below-extrinsic dividend does not force assignment exit. Test: `test_below_extrinsic_dividend_does_not_force_sim_exit`.
- Accepted and repaired exit-precedence coverage: both simulators prove assignment risk wins when the profit-target predicate is simultaneously true. Test: `test_assignment_exit_precedes_profit_target_in_both_sims`.
- Accepted the NEXT-scope caution and rejected it as a machinery defect: `merged-next-seed.md` already says a zero-input wake may supersede an empty/slow provider inventory with a higher-information open route. No broader discovery restriction was introduced.

## DURABLE

- Current project truth: `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`, generated income coverage, readiness, and wake surfaces state that the guard is opt-in/provider-dependent L0 machinery, not observed edge evidence.
- Reusable machinery: `trader_platform/research/corporate_action_risk.py`, `trader_platform/research/diagonal_sim.py`, `trader_platform/research/debit_vertical_sim.py`, and `trader_platform/strategy_dna.py` encode announcement-time visibility, required-mode fail-close, assignment precedence, and honest catalog limits.
- Reusable tests: `tests/test_corporate_action_risk.py` covers future-announcement non-leakage, provider/coverage/malformed fail-close, at-risk exits, below-threshold continuation, assignment precedence, catalog honesty, and bear-put isolation.
- Skill promotion: profile skill `trader-self-evolution` now records that required corporate-action coverage uses `None` for missing coverage and `[]` for explicit covered/no-event data, that `known_at` must not be fabricated from ex-date, and that precedence/below-threshold controls are required.
- Memory: no update. This is a reusable procedure/pitfall, not a stable user preference or routing fact; skill + repo truth are the correct durable surfaces.
- Integration is pending the deterministic wrapper gate; this finalizer did not commit, push, merge, switch branches, or claim RUN COMPLETE.

## LESSON

Future Trader can inject an announcement-time-aware dividend stream into diagonal and bull-call debit simulations, fail closed when required historical coverage is absent, distinguish explicit no-event coverage from missing coverage, close a dividend-dominant ITM short call before ordinary management, and verify that harmless below-extrinsic dividends do not trigger the guard. The capability remains L0 until an honest historical provider supplies both ex-date and `known_at`; synthetic bars and Black-Scholes marks do not create an edge, candidate, or capital seat.

## NEXT

Inventory no-paid historical corporate-action sources that supply both ex-date and honest announcement-time provenance (`known_at`). Implement an archived `DividendEventProvider` only if that provenance can be represented without fabricating announcement dates from ex-dates; otherwise write a fail-closed data decision packet and keep required-mode diagonal/bull-call simulations blocked. A later zero-input wake may supersede this seed after a hard data block if another open route is higher-information.

# Learning promotion — MOA BUILD 2026-07-13T0515

## VERIFICATION

- Focused behavioral/boundary/negative-control/regression command: `.venv/bin/python -m unittest tests.test_intraday_session_data tests.test_pcs_session_time_chronological_lab tests.test_pcs_expiry_grid tests.test_trader_income_coverage -v` → `Ran 23 tests` / `OK`.
- Full suite: `.venv/bin/python -m unittest discover -s tests` → `Ran 193 tests in 7.424s` / `OK`.
- Platform smoke: `.venv/bin/python -m trader_platform.smoke_test` → `platform smoke OK`; `agentic_live` remained blocked at the Robinhood Stage1 OAuth gate.
- Compile/diff hygiene: `.venv/bin/python -m py_compile trader_platform/research/intraday_session_data.py trader_platform/research/pcs_sim.py scripts/pcs_session_time_chronological_lab.py scripts/trader_income_coverage.py tests/test_intraday_session_data.py tests/test_pcs_session_time_chronological_lab.py tests/test_trader_income_coverage.py` and `git diff --check 8edd2b907d9efd3d668e1ee3e274c269bdf77df9` → exit 0.
- Immutable evidence parse: `REJECT_SESSION_TIME_PROXY_THIS_CYCLE`; 24/24 complete; six train dual-cost passes; zero complete train+holdout passes; errors 0; max one-lot axis loss `$224.61`; max absolute ledger delta `1.4210854715202004e-14`; 21 usable market dates and nine holdout dates.
- Coverage regeneration: `.venv/bin/python scripts/trader_income_coverage.py --stamp 2026-07-13T0515` → 21 structures / 245 hypotheses / 67 evolve artifacts / no living leader; generated coverage now says completed-30-minute session-time is built-but-rejected rather than missing.
- Structured handoff: `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-13T0515 --base-head 8edd2b907d9efd3d668e1ee3e274c269bdf77df9` → `ok: true`, `outcome: FALSIFIED`, four useful deltas, five critic findings closed.
- Deterministic pre-integration gate over an isolated temporary Git index: `trader_run_completion_gate.py prepare` → `ok: true`, branch `trader/run-2026-07-13T0515`, base `8edd2b907d9efd3d668e1ee3e274c269bdf77df9`, `staged_files: 46`; the real index was not modified.
- Integration is pending the deterministic wrapper gate. This finalizer did not stage the real index, commit, push, merge, switch branches, or claim RUN COMPLETE.

Accepted/rejected challenger findings:
- F1 accepted and repaired: `scripts/trader_income_coverage.py` and both coverage doctrines now describe the built 30-minute session route, its exact 0/24 rejection, and thin usable-date boundary; `tests/test_trader_income_coverage.py` prevents the stale “session-time slices missing” regression.
- F2 accepted and repaired in routing: raw 30-minute history already spans about 60 dates while prior-session feature readiness leaves 21 usable dates. `merged-next-seed.md`, readiness, and wake surfaces now target append-safe raw retention plus no-lookahead usable-feature density, not an idle wait for 60 new dates.
- F3 rejected as a required simulator mutation: the exact artifact reports theoretical helper capacity in `max_lots`, but every structure/axis and closeout explicitly fixes the operating posture at one lot; zero rows passed and no seat, registration, paper intent, or readiness promotion exists. Changing immutable evidence labels after the run would add no decision value. A future rerun may split operating and theoretical labels before execution.
- F4 accepted as a limitation but rejected as claim-invalidating for this cycle: a nine-date holdout yields only one window, so dense-negative/window evidence is weak; the rejection is independently decisive on dual-cost holdout PnL/trade density. Reports now forbid treating sparse windows as affirmative evidence, and NEXT requires denser usable history before one locked rerun.
- F5 accepted and repaired on current surfaces: every concurrent RTH reference now calls `b195f5fe` historical and states no living leader; coverage’s tested leader hint remains `none; former reference …`.

## DURABLE

- Machinery: `trader_platform/research/intraday_session_data.py`, `trader_platform/research/pcs_sim.py`, `scripts/pcs_session_time_chronological_lab.py`, and `scripts/trader_income_coverage.py`.
- Behavioral/boundary/negative controls: `tests/test_intraday_session_data.py`, `tests/test_pcs_session_time_chronological_lab.py`, `tests/test_pcs_expiry_grid.py`, and `tests/test_trader_income_coverage.py`.
- Immutable run evidence: `reports/trader-wakes/moa/2026-07-13T0515/pcs-session-time-chronological-lab.json` plus executor/challenger reports.
- Current project truth: `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`, `reports/readiness/LATEST.md`, and regenerated `reports/readiness/income-coverage-2026-07-13T0515.md` / `income-coverage-LATEST.md`.
- Reusable procedure/pitfalls are already present in the loaded `trader-self-evolution` skill: timezone-aware intraday DTE uses represented local calendar dates; exits consume the date/session bucket; raw-date density and usable feature-date density are distinct. No further skill patch was made because it would duplicate current guidance.
- Profile memory unchanged: this run produced dated project evidence and reusable procedures, not a stable user preference or routing fact.

## LESSON

Future Trader can run and falsify a completed-30-minute, prior-session-feature, chronological PCS/CCS/IC session-time hypothesis without same-bar or same-date/session-bucket reentry and without timezone-aware calendar-DTE crashes. It also knows that a nominal 60-day intraday download is not a 60-date usable feature sample: warmup reduced this cycle to 21 usable dates and a nine-date holdout, so sparse window metrics cannot support an affirmative edge claim. The exact seed is rejected at L0; the capability remains reusable, the living leader remains none, and the capital path remains empty.

## NEXT

Promote an append-safe, provenance-recorded raw 30-minute underlying archive for BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL; retain the full yfinance-available history with download/as-of metadata; expand usable prior-session feature dates toward retained raw history without lookahead; then rerun exactly once the locked PCS/CCS/IC open/midday/late chronological dual-cost train→holdout specification with unchanged DNA/gates and no holdout retune. Reject again unless train and untouched holdout independently pass both 5% adverse leg slip and `$0.01` half-spread-per-leg with n≥3, positive PnL, one-lot max loss≤`$300`, max/window DD≤`$75`, dense-negative windows≤5, exact ledger, and zero same-bar/session-bucket reentries. Keep L0; do not register, promote, paper, shadow, arm, or live.

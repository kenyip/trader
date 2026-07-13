# Learning promotion — MOA BUILD 2026-07-13T1415

## VERIFICATION

- Focused behavioral/boundary/negative-control/regression command: `.venv/bin/python -m unittest tests.test_intraday_session_data tests.test_pcs_session_time_chronological_lab tests.test_pcs_expiry_grid tests.test_trader_income_coverage -v` → `Ran 31 tests in 0.593s` / `OK`.
- Full suite: `.venv/bin/python -m unittest discover -s tests` → `Ran 201 tests in 7.415s` / `OK`.
- Platform smoke: `just platform-smoke` → `platform smoke OK`; the PCS max-loss risk/ledger/intent path passed and `agentic_live` remained blocked at the Robinhood Stage1 OAuth gate.
- Compile/diff hygiene: `.venv/bin/python -m py_compile trader_platform/research/intraday_session_data.py scripts/pcs_session_time_chronological_lab.py scripts/trader_income_coverage.py tests/test_intraday_session_data.py tests/test_pcs_session_time_chronological_lab.py tests/test_trader_income_coverage.py` and `git diff --check` → exit 0.
- Immutable evidence recomputation: `REJECT_SESSION_TIME_PROXY_THIS_CYCLE`; 24/24 complete; errors 0; 1/24 train dual-cost pass; 0/24 complete train+holdout passes; every symbol 780 usable bars / 60 raw=usable dates / 36 train / 24 untouched holdout / zero feature-date violations; maximum one-lot axis loss `$223.36`; maximum absolute ledger delta `5.684341886080802e-14`; zero same-bar and same-date/session-bucket reentries.
- Sole train survivor check: AAPL late `put_credit_spread`; untouched holdout fixed `$0.01` axis n=2 / `+$6.858454559174554`, 5% leg-slip axis n=2 / `-$10.538313351563206`; both fail density and the 5% axis also fails positive PnL.
- Deterministic coverage regeneration: `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-13T1415` → 21 structures / 245 hypotheses / 67 evolve artifacts / no living leader; run-stamped and LATEST outputs are byte-identical. Redundant 1429/1437/1443 intermediate snapshots were removed.
- Structured handoff: `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-13T1415 --base-head 06701f338eecce287cb62e66894b9b8fe2853b3f` → `ok: true`, `outcome: FALSIFIED`, three useful deltas, six critic findings closed.
- Deterministic pre-integration gate over an isolated temporary Git index: `trader_run_completion_gate.py prepare` → `ok: true`, branch `trader/run-2026-07-13T1415`, base `06701f338eecce287cb62e66894b9b8fe2853b3f`, `staged_files: 25`; the real index remained untouched (`0` staged paths) and `GIT_INDEX_FILE` was unset afterward.
- Integration is pending the deterministic wrapper gate. This finalizer did not stage the real index, commit, push, merge, switch branches, or claim RUN COMPLETE.

Challenger reconciliation:
- F1 rejected as a required post-run evidence rewrite: artifact `max_lots=3` is explicitly labeled generic/theoretical sleeve capacity while the operating posture is one lot. No row passed, no seat or intent exists, and maximum one-lot loss is `$223.36`; rewriting immutable results would not change the rejection. Future positive-capital outputs should split operating and theoretical fields before execution.
- F2 accepted as a scope limitation but rejected as claim-invalidating: this production artifact is honestly a first capture (`new_rows=780`, `replaced_rows=0`) and makes no multi-capture operational claim. Repeat append/overlap/replacement behavior is independently exercised by unit tests, including provenance journal growth and mixed-DST round trips.
- F3 accepted and repaired: canonical coverage was regenerated at the run stamp and only `income-coverage-2026-07-13T1415.md` plus `income-coverage-LATEST.md` remain; deterministic stamp regeneration and the coverage regression test preserve claim-current wording.
- F4 accepted as a cosmetic interpretation risk but rejected as claim-invalidating: zero-trade rows report the simulator’s explicit theoretical 1-point-width loss estimate (`$75`), not an observed loss. Their `n_trades=0` forces `gate_pass=false`, so they cannot rescue selection or support an empirical-risk claim.
- F5 closed by finalizer re-execution: focused 31/31, platform smoke, and full 201/201 are independently green; no executor-only verification was inherited.
- F6 accepted and closed on final surfaces: the executor audit handoff remains historically correct for its partial phase, while merge, LATEST, readiness, compounding, and this report use the merged post-run BUILD seed and leave the densified session-time family closed.

## DURABLE

- Reusable machinery: `trader_platform/research/intraday_session_data.py` now retains append/deduplicated 30-minute and daily OHLCV archives with capture journals; `scripts/pcs_session_time_chronological_lab.py` reports raw archive density separately from usable no-lookahead feature density. CSV and metadata replacement are atomic individually; no two-file transaction claim is made.
- Behavioral/boundary/negative controls: `tests/test_intraday_session_data.py`, `tests/test_pcs_session_time_chronological_lab.py`, `tests/test_pcs_expiry_grid.py`, and `tests/test_trader_income_coverage.py` cover overlap replacement, malformed/nonfinite/source-mismatch fail-close behavior, New York DST round trips, prior-session warmup, chronological selection, failed-train/pass-holdout rejection, calendar DTE, no reentry, and stale coverage wording.
- Dated immutable evidence: `reports/trader-wakes/moa/2026-07-13T1415/pcs-session-time-archive-rerun.json`, executor closeout, challenger critique, and this final handoff.
- Current project truth: `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`, `reports/readiness/LATEST.md`, and deterministic run-stamped/LATEST income coverage.
- Reusable pitfall promoted to the loaded `trader-self-evolution` skill: distinguish raw archive dates, usable prior-session feature dates, and first-capture versus exercised append behavior; a denser underlying archive does not reopen an exact family that still fails locked dual-cost train→holdout gates.
- Profile memory unchanged: this is dated project truth and reusable procedure, not a stable user preference or routing fact.

## LESSON

Future Trader can retain yfinance 30-minute and daily underlying history append-safely, preserve capture provenance, round-trip New York offsets across DST, and warm every retained intraday market date only from a completed prior session. The locked 8-symbol × 3-structure session-time proxy family became materially denser (21→60 usable dates) yet weakened from six train survivors to one and still produced zero complete train→untouched-holdout dual-cost passes. Densification fixed the evidence bottleneck but did not reveal an edge; that exact family is closed for this cycle. First-write production journals prove provenance, while repeated overlap semantics are test evidence until a later real capture exercises them. BUILD/L0, no living leader, and the empty capital path remain honest.

## NEXT

Run one free defined-risk multi-structure discovery across top research symbols using PCS/CCS/IC plus at most one already-simmed under-covered catalog structure, then apply exact B3+B4 and fixed-`$0.01`-per-leg falsification to every SHIP against non-vacuous dual-cost positive PnL, one-lot `max_loss_usd <= $300`, window max DD `<= $75`, and dense-negative windows `<= 5`; register nothing unless the complete gates pass, keep L0/proxy labels, and do not reopen closed families or paper/shadow/arm/live.

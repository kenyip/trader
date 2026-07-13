# Learning promotion — 2026-07-12T2237

## VERIFICATION

- `.venv/bin/python -m unittest tests.test_dividend_event_crosscheck tests.test_dividend_event_archive tests.test_corporate_action_risk tests.test_debit_vertical_sim tests.test_diagonal_oos_stress tests.test_defined_risk_fixed_cost -v` → `Ran 36 tests in 0.175s` / `OK`; this includes parser behavior, source/path and issuer-chronology boundaries, amount/missing/duplicate/identity failures, provider fail-close behavior, assignment precedence, and the new equal-record/ex-date non-substitution control.
- `.venv/bin/python scripts/dividend_event_crosscheck.py --nasdaq-archive .cache/platform/dividend_events/AAPL_nasdaq.json --out .cache/platform/dividend_event_crosscheck_2026-07-12T2237.json` → `partial_issuer_corroboration`; coverage `2016-07-26` through `2026-04-30`, archive/issuer `40/40`, matched `40`, conflicts `0`, unmatched archive `0`, unmatched issuer `0`, earlier archive events `13`, qualified `known_at`/`amount_per_share`/`security_identity`, unqualified `ex_date`.
- `.venv/bin/python -m trader_platform.smoke_test` → `platform smoke OK`; `agentic_live` remained blocked at the Stage1 Robinhood OAuth gate.
- `.venv/bin/python -m unittest discover -s tests` → `Ran 166 tests in 6.809s` / `OK`.
- `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-12T2237 --json` → 20 catalog structures / 245 hypotheses / 67 evolve artifacts / no quality leader; dated and LATEST coverage regenerated.
- `.venv/bin/python -m py_compile trader_platform/research/dividend_event_crosscheck.py scripts/dividend_event_crosscheck.py tests/test_dividend_event_crosscheck.py scripts/trader_income_coverage.py` plus `git diff --check 75d34da711f498173e84ec779a367154cde1b898` → `OK` / no output.
- Completion-artifact/report consistency check → `run_artifacts=ok latest_equals_merge=True`.
- Completion-gate-equivalent scan across all 23 modified/untracked paths → sensitive paths `[]`, secret findings `[]`, binary paths `[]`; added/full untracked text also has zero hardcoded-secret, shell-injection, `eval`/`exec`, pickle, or formatted-SQL matches. No `.cache`, private positions, credentials, tokens, raw secrets, or generated binary debris enters the handoff.
- `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-12T2237 --base-head 75d34da711f498173e84ec779a367154cde1b898` → `ok=true`, `role_ready=true`, outcome `CAPABILITY`, one useful delta / one new novelty key / five critic findings closed.
- Integration remains pending the deterministic wrapper gate.

Critique dispositions:

- Accepted the security-identity scope nit and rejected any whole-provider security-class interpretation. `security_identity` is qualified only for the 40 matched releases whose issuer text explicitly says Apple common stock; the 13 older archive rows and any unmatched/noncanonical source remain outside the claim.
- Accepted the intersection-completeness nit and rejected any whole-provider completeness interpretation. The exact 40/40 result proves concordance only inside the Apple-sitemap span; dual silent omission remains theoretically possible and is now explicit durable guidance.
- Accepted and repaired the optional record-date substitution control. `tests/test_dividend_event_crosscheck.py` now proves that even when the issuer `record_date` equals the archive `ex_date`, the result still qualifies only announcement date, amount, and matched-release security identity while `ex_date` remains unqualified.
- Rejected stale readiness as a remaining defect after finalization: the 2237 readiness top, machine-readable NEXT, and phase decision are updated to this finalizer outcome and the completed 1835 seed is marked superseded.
- Rejected the challenger’s full-suite re-gate as outstanding: the finalizer ran the focused 36-test suite, platform smoke, live exact cross-check, and full 166-test suite successfully.

## DURABLE

- Project truth: `docs/DIVIDEND_EVENT_DATA_BOUNDARY.md`, `docs/BUILD_LAB_ENVIRONMENT.md`, and `docs/INCOME_STRATEGY_COVERAGE.md` preserve field- and interval-bounded AAPL issuer corroboration and explicit non-claims for ex-date, pre-window rows, split-adjusted economics, observed option surfaces, assignment calibration, and L1.
- Reusable machinery: `trader_platform/research/dividend_event_crosscheck.py` and `scripts/dividend_event_crosscheck.py` provide canonical Apple Newsroom parsing, exact bounded Nasdaq comparison, fail-closed conflict handling, and atomic live evidence output.
- Reusable tests: `tests/test_dividend_event_crosscheck.py` covers issuer wording, canonical sitemap/URL identity, exact match, amount/missing/duplicate/forged-source failures, invalid issuer chronology, and explicit record-date/ex-date non-substitution.
- Derived truth: `reports/readiness/income-coverage-2026-07-12T2237.md`, `reports/readiness/income-coverage-LATEST.md`, `reports/readiness/LATEST.md`, `reports/trader-wakes/LATEST.md`, and `reports/trader-wakes/INDEX.md` agree on BUILD/L0, no living leader, 20/245/67 coverage, and the one merged NEXT.
- Skill: profile skill `trader-self-evolution` now records that primary-source corroboration is field- and interval-specific, intersection completeness is not whole-provider completeness, and issuer record date must never be substituted for ex-date even when values coincide.
- Memory: no update. This is reusable procedure/data-provenance knowledge rather than a stable user preference or routing fact.
- Integration is pending the deterministic wrapper gate; this finalizer did not commit, push, merge, switch branches, or claim RUN COMPLETE.

## LESSON

Future Trader can independently normalize canonical Apple results releases and compare them to the AAPL Nasdaq archive without broadening evidence semantics. It now knows and tests that a perfect bounded match supports only explicitly observed fields inside the exact overlap: publication/announcement date, nominal amount, and matched-release common-stock wording. Neither coincident issuer record dates, a 40/40 intersection, nor a hardcoded normalized identity licenses historical `ex_date`, whole-provider completeness, pre-2016 coverage, split-adjusted assignment economics, observed-option realism, L1, or a capital seat.

## NEXT

Inventory one no-paid source that explicitly labels historical AAPL ex-dividend dates for the same 40-event interval (2016-07-26 through 2026-04-30). Corroborate only if the independent source names `ex_date` or an equivalent field; never substitute issuer record date or Nasdaq reuse. If no source survives a short fail-closed inventory, close this provenance route at bounded partial L0 and redirect to an open historical-underlying or simulator-capability loop that can advance an L1 paper-testable decision rule. Do not reopen closed daily-bar proxy families or promote, paper, shadow, arm, or live.

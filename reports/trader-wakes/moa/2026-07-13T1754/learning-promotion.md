# Learning promotion — 2026-07-13T1754

## VERIFICATION

- `.venv/bin/python -m unittest tests.test_evolve_chronological_pre_registration tests.test_evolve_pre_registration_stress -q` → `Ran 20 tests in 0.004s`, `OK`.
- `.venv/bin/python scripts/evolve_chronological_pre_registration.py --period 5y --top-symbols 8 --mutants 2 --max-population 36 --seed 1754 --train-fraction 0.60 --out reports/trader-wakes/moa/2026-07-13T1754/evolve-chronological-pre-registration.json` → exit 0; 36/36 sampled DNA evaluated; 17 train SHIPs; complete chronological proxy gate 0/17; registration eligible 0; errors empty; `REJECT_ALL_TRAIN_SELECTED_DNA_ON_CONJUNCTIVE_HOLDOUT_GATES` unchanged. Eligible structures 11; evaluated 10; `put_credit_spread` count 0.
- `.venv/bin/python -m py_compile scripts/evolve_chronological_pre_registration.py scripts/evolve_pre_registration_stress.py scripts/pcs_cost_stress.py scripts/pcs_regime_stress.py tests/test_evolve_chronological_pre_registration.py tests/test_evolve_pre_registration_stress.py` → exit 0, OK.
- `just platform-smoke` → exit 0, `platform smoke OK`; `agentic_live` blocked because Robinhood MCP is not connected (Stage1 OAuth gate).
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q` → `Ran 221 tests in 7.527s`, `OK`.
- `.venv/bin/python scripts/trader_income_coverage.py --stamp 2026-07-13T1754 --write` → 21 catalog structures / 245 hypotheses / 70 evolve artifacts / quality leader none; dated and LATEST outputs byte-identical.
- Final diff, secret-sensitive path scan, `git diff --check`, compounding validation, and temporary-index deterministic `prepare` result are recorded below after the non-mutating handoff check. Integration is pending the deterministic wrapper gate.

Critique dispositions:

- ACCEPTED: chronological adapter capability and 0/17 exact-cycle falsification.
- REPAIRED: capped population coverage labeling now distinguishes 11 eligible structures from 10 evaluated structures, records zero-inclusive counts, and has a boundary test where an omitted eligible structure coexists with sampled-cap ranking completeness.
- REPAIRED: redundant T2012 coverage debris removed; only run-stamped T1754 plus byte-identical LATEST remain.
- REJECTED AS REQUIRED DEFECT: optional `fixed_cost.summary`; exact `by_half_spread`, unrounded gates, and quality fields already carry every decision metric.
- REPAIRED: novelty key and closed-family identifier written to `compounding.json`; the next orientation will ingest them. The pre-run `orientation.json` is intentionally not rewritten after the fact.
- ACCEPTED: no registration, no promotion, and no soft/vacuous near-miss treated as edge.

## DURABLE

- Repo machinery: `scripts/evolve_chronological_pre_registration.py`, `scripts/evolve_pre_registration_stress.py`, `scripts/pcs_cost_stress.py`, `scripts/pcs_regime_stress.py`.
- Tests: `tests/test_evolve_chronological_pre_registration.py`, `tests/test_evolve_pre_registration_stress.py`.
- Dated project truth/evidence: `reports/trader-wakes/moa/2026-07-13T1754/evolve-chronological-pre-registration.json`, top-level merge/LATEST/readiness/coverage surfaces, and this learning record.
- Compounding: `reports/trader-wakes/moa/2026-07-13T1754/compounding.json` closes `free-definedrisk_chronological-prereg-seed-1754-pop36-train60-cycle` and records unique novelty keys.
- Skill: `trader-self-evolution` now carries the reusable capped-random-population coverage-labeling pitfall and boundary-test procedure.
- Profile memory: no update. This is dated project evidence and a reusable procedure, not a stable user preference or routing fact; repo reports plus the skill are the correct durable surfaces.
- Superseded guidance: broad “11 structures searched” wording is replaced in final surfaces by explicit eligible/evaluated semantics; the original executor/challenger receipts remain historical role evidence.

## LESSON

Future Trader can run fixed-seed, train-only free defined-risk selection followed by exact-DNA untouched-holdout absolute gates without granting registration authority, and its hard gates no longer fail open at rounded precision boundaries. It also knows that a random population cap can entirely omit an eligible strategy family: `ranking_complete` means every sampled row was evaluated, not that every eligible structure was represented. Balanced-family claims now require explicit zero-inclusive coverage evidence or stratified sampling.

## NEXT

Implement and run one predeclared lagged gap-recovery 21-DTE put-credit-spread class on a fixed, outcome-rank-free multi-symbol set: the prior completed day must open at least 1% below its previous close, recover to close at or above that open, and close above its lagged 60-day EMA; entry is allowed only on the following bar. Use one fixed DNA, complementary/no-signal controls, chronological 60/40 train selection to one untouched holdout evaluation, non-vacuous 5% and fixed-$0.01-per-leg costs, one-lot `max_loss_usd <= 300`, window max DD `<= 75`, dense-negative windows `<= 5`, and train AND holdout conjunction. Register nothing first pass; keep Black-Scholes proxy/L0 labels; do not paper, shadow, arm, or live.

Integration is pending the deterministic wrapper gate. This finalizer has not staged the real index, committed, pushed, merged, switched branches, or claimed RUN COMPLETE.

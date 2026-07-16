# Learning promotion — 2026-07-15T2007

## VERIFICATION

- Focused behavioral, boundary, negative-control, and integrity suite:
  - command: `.venv/bin/python -m unittest tests.test_downside_semivariance_etf_barrier_train_lab -v`
  - exact result: `Ran 7 tests in 0.137s — OK`.
  - coverage includes completed-bar ranking, next-session entry, global non-overlap, outcome-invariant first blueprint, absolute-hazard negative control, same-date plain-HV specificity failure, specificity-only dominant-failure wording, fixed-population rejection, overlap rejection, sealed holdout identity, capital/Greek/authority labels, close-only boundary, and strict JSON.
- Focused finalizer-adjacent suite:
  - command: `.venv/bin/python -m unittest tests.test_downside_semivariance_etf_barrier_train_lab tests.test_trader_build_compounding tests.test_trader_completion_contract tests.test_trader_run_completion_gate -v`
  - exact result: `Ran 57 tests in 7.523s — OK`.
- Required full suite:
  - command: `.venv/bin/python -m unittest discover -s tests`
  - exact result: `Ran 363 tests in 18.244s — OK`.
- Compilation and CLI smoke:
  - command: `.venv/bin/python -m py_compile scripts/downside_semivariance_etf_barrier_train_lab.py tests/test_downside_semivariance_etf_barrier_train_lab.py && .venv/bin/python scripts/downside_semivariance_etf_barrier_train_lab.py --help >/dev/null`
  - exact result: exit `0`, no output.
- Current-code claim replay:
  - command: `.venv/bin/python scripts/downside_semivariance_etf_barrier_train_lab.py --out <temporary-json>` followed by strict-JSON substantive comparison excluding only `generated_at`.
  - exact result: exit `0`; `FAMILY_CLOSED`; train `178`; low/high breach `0.0449438202247191 / 0.11235955056179775`; semivariance edge `0.06741573033707865`; LB90 `0.03932584269662921`; plain-HV edge `0.07865168539325842`; failed gates exactly `semivariance_edge_exceeds_plain_hv`; tracked and replay payloads substantively equal; normalized SHA-256 `2f1dc94161b361b1725f92d91eb63b32dc0686d87a7f52bf582a24e123cf48a2`; all eight source hashes and holdout identity equal.
- Derived coverage:
  - command: `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-15T2007 && cmp -s reports/readiness/income-coverage-2026-07-15T2007.md reports/readiness/income-coverage-LATEST.md`
  - exact result: exit `0`; `21` structures / `246` hypotheses / `70` evolve artifacts / no living leader; dated and LATEST byte-identical; stale run-created `2020` dated copy removed.
- Schema-v2 handoff and disposable-index completion prepare:
  - commands: `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-15T2007 --base-head 8ce5335601133a23d5377c9df6707d125a43a6da`; then temporary-index `git read-tree HEAD`, `git add -A`, `git diff --cached --check`, and `.venv/bin/python scripts/trader_run_completion_gate.py prepare --repo . --stamp 2026-07-15T2007 --base-head 8ce5335601133a23d5377c9df6707d125a43a6da --run-branch trader/run-2026-07-15T2007`.
  - exact result: handoff `ok=true`, `role_ready=true`, schema `2`, outcome `FAMILY_CLOSED`, strategy_advanced `false`, four useful deltas, six critic findings closed; diff check clean; prepare `ok=true`, mode `prepare`, branch `trader/run-2026-07-15T2007`, staged files `20`.
- Complete diff/security audit: all 20 intended paths reviewed from base `8ce5335`; no private positions, credentials, tokens, raw secrets, auth/session logs, cache payloads, or unintended generated debris. Run-created stale coverage copy `2026-07-15T2020` was removed; executor/challenger evidence and strict-JSON claim were preserved.

Integration is pending the deterministic wrapper gate. This finalizer has not committed, pushed, merged, switched branches, or claimed `RUN COMPLETE`.

## DURABLE

Strategy charter and outcome:
- Economic mechanism: persistent cross-sectional left-tail heterogeneity should make the lowest prior downside-semivariance ETF less likely than the highest-ranked control to breach a 5% ten-session close barrier inside a lag-safe SPY uptrend.
- Candidate/family: `LOW_DOWNSIDE_SEMIVARIANCE_ETF_PCS_21D_V1` / `noncollapse|cross_section_low_downside_semivariance_60d|liquid_etfs_spy_qqq_iwm_xlf_xle_xlk_xli_xlv|spy_sma100_uptrend_positive60d|10session_close_barrier5pct|pcs21d2wide_planned`.
- Planned expression only: one-lot nearest listed 18–24 DTE `$2`-wide PCS, short 0.18–0.25 delta put, at least `$0.30` credit, positive bids, two-leg NBBO width at most `$0.20`; `capital_fit_usd=$200`, structural one-lot `max_loss_usd=$200` before credit/closing friction, `max_lots=1`, one global bullish risk unit.
- Outcome: `FAMILY_CLOSED` at `F0_MECHANISM -> F0_MECHANISM`; strategy advancement false. Train passed absolute hazard, relative edge, date-block uncertainty, tail, breadth, density, and integrity but failed the frozen mechanism-specificity gate only because plain HV separated the same endpoint more strongly.
- Evidence: train `178`; low/high breach `4.4944% / 11.2360%`; semivariance edge `+6.7416pp`; LB90 `+3.9326pp`; low/high worst-decile minimum close return `-4.9172% / -8.0647%`; plain-HV edge `+7.8652pp`; same low/high rank overlap `134/178` and `141/178`; holdout `119` with rank dates 2019-11-13 through 2026-06-16 and exits through 2026-07-02 remains unread under identity `72a6d18430031f03421d27a2680f53d42f099357a5c6685b1b3db2ce1a7dcd5d`; pricing calls `0`.
- Authority: fixed present-day ETF panel, split/dividend-adjusted daily-close L0 evidence only. Severe low-rank SPY/XLV and high-rank XLE concentration, fund overlap, composition drift, close-only barriers, and absent option costs/fills prevent generalization, F1/F2/L1, capital-seat, registry, paper, shadow, arm, broker, or live claims.

Accepted challenger findings and repairs:
- Accepted `PASS WITH NITS` and the exact `FAMILY_CLOSED` disposition.
- Repaired the claim-bearing dominant failure from a misleading full-stack failure to mechanism non-specificity only; current code and the focused test require that every other gate passed and reject the word `absolute` on this sole-failure path.
- Tightened holdout dates so rank-date identity and later exit coverage are not conflated.
- Rewrote readiness for stamp 2007 rather than leaving a NEXT-only patch on the 1912 decision.
- Adopted the challenger merge seed and recorded active-epoch consecutive no-advance `2`, `strategy_pivot_required=true`, and the third-no-advance burst-stop rule.
- Preserved semivariance/lookback/barrier/panel quarantine, recent-downshock and low-HV mean-return quarantines, and the sealed `72a6d184…` holdout.

Rejected claims:
- Rejected executor NEXT `LOW_TOTAL_HV_ETF_BARRIER_EXTERNAL_TRAIN_F0` as the durable seed; it remains the inspected direct-tail rank lane and would violate the two-no-advance pivot rule.
- Rejected any implication that absolute hazard success nearly earned F1; mechanism specificity was conjunctive and failed.
- Rejected using severe fixed-panel concentration as a broad ETF-selection or capital claim.
- Rejected any capital-path, paper-force, registry, shadow, arm, broker, or live reading.
- No material challenger strategy judgment was rejected; `critic_findings` uses `rejected` only for the invalid/stale state or promotion implication that final surfaces now disprove.

Promotion routing:
- Dated outcome/current truth: claim JSON, executor/challenger/finalizer reports, readiness, coverage, LATEST, INDEX, this learning record, and schema-v2 compounding handoff.
- Reusable machinery/tests: `scripts/downside_semivariance_etf_barrier_train_lab.py` and `tests/test_downside_semivariance_etf_barrier_train_lab.py`.
- Skill: patched `trader-self-evolution` with the reusable mechanism-specificity rule: a specialized tail selector must beat a simpler same-date risk rank; sole-failure labels and negative controls must remain exact; after the second no-advance, pivot rather than laundering the inspected comparator.
- Memory: no addition. Dated metrics, family closure, and epoch streak belong in repo evidence; the stable autonomy, capital, proxy-evidence, and anti-thrash stances already exist.

## LESSON

Future Trader now knows that a downside-semivariance ETF selector can pass absolute close-barrier quality, relative separation, dependence-aware uncertainty, tail severity, breadth, and chronology while still failing to identify its stated mechanism. If a simpler same-date total-HV rank separates the endpoint more strongly, the specialized feature is a relabeling candidate, not an F1 advance.

Future Trader can now audit that boundary in code and evidence: preserve the exact failed-gate list, emit specificity-only dominant-failure prose when appropriate, test that isolated path, distinguish holdout rank dates from later exits, keep the sealed holdout and option stage unspent, and force a materially different mechanism/evidence pivot after the second active-epoch no-advance.

## NEXT

`SPY_INDEX_THETA_CARRY_PCS_21D_DUAL_COST_F0`: freeze a regime-only SPY one-lot 18–24 DTE `$2`-wide PCS (short 0.18–0.25 delta, minimum `$0.30` credit, positive bids, two-leg NBBO width `≤$0.20` when quotes exist, 50% harvest, 5% underlying-close invalidation, hard approximately ten-session stop), `capital_fit_usd=$200`, structural `max_loss_usd=$200` before credit/friction, `max_lots=1`; evaluate chronological train then untouched holdout proxy option path PnL under both 5% adverse leg slip and `$0.01`-per-leg half-spread with non-vacuous trade, max-loss, window-DD, chronology, and integrity gates. No cross-sectional HV/semivariance rank, no use of holdout `72a6d184…`, and no L1, registry, paper force, shadow, arm, broker, or live action from proxy evidence.

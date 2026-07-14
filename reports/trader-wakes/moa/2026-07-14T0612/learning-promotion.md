## VERIFICATION

Strategy charter/outcome: tested candidate `SPY_VRP_PCS_VIX_RV_21D_V1` within canonical family `SPY_VRP_VIX_RV_21D`. The mechanism was same-close observed VIX / fully warmed SPY RV20 at least 1.25 while SPY closed above fully warmed SMA200, with non-overlapping subsequent 21-session outcomes and outcome-independent positive-trend low-ratio controls. The frozen falsifier required every assessment and pooled matched-control gate to pass before any option marks. Outcome is `FAMILY_CLOSED`; strategy advancement is false; funnel remains `F0_MECHANISM -> F0_MECHANISM`.

Canonical strict JSON `reports/trader-wakes/moa/2026-07-14T0612/spy-vrp-pcs-study.json` has SHA-256 `4a22bec0e15e3d71b1163e6528790e951044d27169a5567b0c4c38dc6bdf68fd`. It contains 53 non-overlapping treated episodes, 35 matched controls, and 10,000 circular-block bootstrap samples. Raw treated VIX-minus-forward-RV mean is `3.948384961161123` vol points, positive frequency `0.8679245283018868`, and treated LB95 `1.1085384403209784`; those values do not prove conditional alpha. The 2020-2021 matched mean is `-1.6220816440468364`; pooled matched mean is `1.0633423571201617` but matched LB95 is `-2.5506969930277643`. Both frozen incremental-selector gates failed. Integrity violations are zero, `pricing_calls=0`, option status is `NOT_RUN_MECHANISM_GATE_FAILED`, candidate_pass and registration_eligible are false. Structural `capital_fit_usd=100`, `one_lot_max_loss_usd=100`, and `max_lots=1` are a $1-wide upper bound only, not an observed fill, modeled PnL, or capital seat.

Commands and exact results:

- `.venv/bin/python -m unittest tests.test_spy_vrp_pcs_study -v` -> `Ran 13 tests in 2.268s`, `OK`. The repaired positive fixture now yields 57 treated / 57 matched pairs across three folds and passes unchanged production density gates; its outcome-perturbed matched negative control still fails.
- `.venv/bin/python -m unittest tests.test_pmcc_desk -v` -> `Ran 7 tests in 7.236s`, `OK`; includes `bid_credit=None` fallback, valid zero-bid preservation, and live-surface invariants.
- `.venv/bin/python -m unittest tests.test_trader_income_coverage -v` -> `Ran 1 test in 0.690s`, `OK`; deterministic three-date/two-expiration fixture proves derived density, explicit breadth, thin labeling, and plumbing-only authority.
- `.venv/bin/python -m py_compile scripts/spy_vrp_pcs_study.py tests/test_spy_vrp_pcs_study.py pmcc/desk.py tests/test_pmcc_desk.py scripts/trader_income_coverage.py tests/test_trader_income_coverage.py` -> exit 0, no output (`compile OK`).
- `.venv/bin/python -m unittest discover -s tests` -> `Ran 262 tests in 12.290s`, `OK`.
- `just platform-smoke` -> exit 0, `platform smoke OK`; PCS multi-leg risk/ledger/intent, Stage2/readiness, evolve ship bar, calendar/diagonal sims, capital fit, and learn-tick checks were green; `agentic_live` remained blocked at Stage1 OAuth as required.
- Matching limitation audit from canonical JSON -> max absolute VIX difference `4.210000991821289`, max/median trading-session distance `427/102`, two paired differences with absolute value above 50. This supports fail-closed quarantine; no tolerance or threshold was retuned.
- Schema-v2 `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-14T0612 --base-head 4cb52f44e126877c736fc086b65afdc9965518ec` -> `ok=true`, `outcome=FAMILY_CLOSED`, `strategy_advanced=false`, 4 useful deltas, 6 critic findings closed.
- Non-mutating isolated-index `.venv/bin/python scripts/trader_run_completion_gate.py prepare ...` -> `ok=true`, `mode=prepare`, 26 staged files in the temporary index; `git diff --cached --check`, sensitive-path, and raw-secret gates were green. The real index remained empty and `GIT_INDEX_FILE` was unset afterward.
- No real-index staging, commit, push, merge, branch switch, `.gitignore` edit, broker login, paper order, shadow/live promotion, funding, or arm occurred in finalization.

## DURABLE

Challenger reconciliation:

- N1 ACCEPT/NO REPAIR NEEDED: candidate `SPY_VRP_PCS_VIX_RV_21D_V1` and canonical closed family `SPY_VRP_VIX_RV_21D` already agree across JSON and reports; no duplicate identity was introduced.
- N2 ACCEPT/RECORDED: matching is outcome-independent and integrity-clean but coarse. Max VIX difference `4.210001`, max/median session distance `427/102`, and two >50-vol-point paired differences reinforce quarantine and a stronger future control-design requirement; they do not authorize rescue retuning.
- N3 ACCEPT/NO REPAIR NEEDED: canonical failure wording already distinguishes positive raw treated VRP from failed incremental selector value.
- N4 ACCEPT: burst-stop is enforced. `POST_VRP_SEARCH_DESIGN_REASSESSMENT` is the only NEXT; a third similar pre-screen and familiar PCS volume are blocked by default.
- N5 ACCEPT/REPAIRED: the synthetic positive fixture now leaves sufficient disjoint calendar space for production matching. Focused VRP is 13/13 green without weakening the >=8-per-assessment or >=24-pooled gates; the matched negative-control half remains intact. The real SPY family close was not reopened or retuned.
- N6 ACCEPT/NO STRATEGY PATCH NEEDED: readiness already had the correct post-VRP NEXT; only stale ops-green wording was corrected.

Dated project truth is durable in the canonical study JSON, executor/final merge/LATEST/INDEX, readiness, regenerated coverage, schema-v2 compounding handoff, and this learning report. Reusable machinery and regressions are `scripts/spy_vrp_pcs_study.py`, `tests/test_spy_vrp_pcs_study.py`, `pmcc/desk.py`, `tests/test_pmcc_desk.py`, `scripts/trader_income_coverage.py`, and `tests/test_trader_income_coverage.py`. Profile skill `trader-self-evolution` already contains the reusable matched-control lesson: report covariate/time-distance/extreme-pair quality, fail closed on unstable paired evidence, and do not retune an inspected family. No additional skill patch is warranted. Profile memory remains unchanged because this is procedure plus dated project truth, not a stable Ken preference or routing fact. Superseded 9/9 and 258/258 current-run claims are rewritten on current surfaces rather than stacked as contradictory green claims.

## LESSON

Future Trader can distinguish a broad raw volatility-risk premium from incremental selector value: a positive treated VIX-minus-forward-RV distribution is not enough when a high-ratio/trend rule cannot beat outcome-independent matched controls stably across assessments and on a paired lower bound. Matching without outcome leakage can still be too coarse, so future studies must report covariate and time-distance tails and extreme pairs before treating a pooled mean as specific edge. A positive synthetic test must itself satisfy production density and non-overlap semantics; expected counts are not proof. Future Trader also preserves semantic boundaries in incidental systems: `None` may mean a missing quote while zero is a valid quote, and current archive density must be derived and deterministically tested rather than hard-coded. These repairs did not rescue the strategy; they made the family close precise, reproducible, and harder to reopen by accident.

## NEXT

`POST_VRP_SEARCH_DESIGN_REASSESSMENT`: stop the no-advance burst and inventory remaining reset routes for a materially distinct economic mechanism, stronger outcome-independent control/placebo design with explicit residual-match limits, chronology capable of train and untouched holdout before option marks, and a frozen pre-option falsifier. Authorize at most one later candidate only if all four are written before simulation or pricing; otherwise emit `DIMINISHING_RETURNS` rather than run familiar multi-name PCS volume. Keep BUILD/L0 with no paper/shadow/arm/broker/live action.

Integration is pending the deterministic wrapper gate.

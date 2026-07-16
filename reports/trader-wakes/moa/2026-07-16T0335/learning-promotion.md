# Learning promotion — MoA 2026-07-16T0335

## VERIFICATION

Strategy charter/outcome:

- Frozen charter: `reports/trader-wakes/moa/2026-07-16T0335/strategy-charter.md`.
- Exact scope: `MONTHLY_SECTOR_LEADER_CONTINUATION_BULL_CALL_35D_V1` / `SECTOR_ALLOCATION_RELATIVE_STRENGTH_CONTINUATION`.
- Economic mechanism: slow monthly institutional/benchmark sector reallocation may sustain an established 63-session sector ETF leader for another trading month.
- Frozen structure boundary: future conditional one-lot 30-45 DTE $2-wide bull-call debit spread only, `capital_fit_usd=200`, planning structural `max_loss_usd=200` before debit slippage/closing friction, `max_lots=1`; no option pricing occurred.
- Outcome: `FAMILY_CLOSED` at machine funnel stage `F0_MECHANISM -> F0_MECHANISM`. The 102-signal/17-year train population produced leader mean -0.130819% after the 10-bps underlying hurdle versus +0.732793% for the same-date nonleader basket, paired excess -0.863612%, circular three-signal-date LB90 -1.455459%, leader positive frequency 48.0392%, and worst-decile return -9.375157%. Six frozen gates failed. The 69-signal holdout remains identity-sealed/outcome-unread; simulation false; observed and proxy option marks false.

Commands and exact finalizer results:

- `.venv/bin/python -m unittest tests.test_monthly_sector_leader_train_lab tests.test_sector_breadth_thrust_train_lab tests.test_low_hv_cross_section_train_lab tests.test_trader_build_compounding -v` -> `Ran 50 tests in 5.323s`, `OK`. This covered the new behavioral/boundary/positive/negative/leakage suite plus adjacent sector/cross-section and schema-v2 compounding regressions.
- `.venv/bin/python -m unittest discover -s tests` -> `Ran 409 tests in 22.349s`, `OK`.
- `.venv/bin/python -m py_compile scripts/monthly_sector_leader_train_lab.py tests/test_monthly_sector_leader_train_lab.py && just test` -> exit 0; the existing research smoke returned `STAND ASIDE` for both TSLA and TSLL and performed no broker action.
- Exact-cache replay via `scripts/monthly_sector_leader_train_lab.py --cache-dir .cache/platform/monthly_sector_leader` -> canonical raw SHA-256 `7ac37abc182c67dbf56bfaa572f13fc126200a79de6a9a6aef175a21b73886ba`; canonical and replay normalized SHA-256 `f9e1363da6ec54939f8eb9246095315bb68f7261ab728369ad4341c7f269d64d`; payload equality true after excluding only `generated_at`; `FAMILY_CLOSED`, train gate false, holdout outcomes unread, holdout simulation false, observed/proxy option marks false.
- `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-16T0335 --base-head 6b51aec5f37b8b17f718a99c181066a8a70adddd` -> `ok=true`, `role_ready=true`, `outcome=FAMILY_CLOSED`, `strategy_advanced=false`, three useful deltas, seven critic findings closed.
- Deterministic pre-integration check used an isolated temporary Git index (`git read-tree HEAD`; `git add -A`; no real-index mutation) and ran `.venv/bin/python scripts/trader_run_completion_gate.py prepare --repo . --stamp 2026-07-16T0335 --base-head 6b51aec5f37b8b17f718a99c181066a8a70adddd --run-branch trader/run-2026-07-16T0335` -> `ok=true`, `mode=prepare`, `staged_files=20`; sensitive-path/raw-secret scan and cached `diff --check` passed. Follow-up proved `GIT_INDEX_FILE_unset=true` and `real_index_unchanged=true`.
- Complete base-diff inventory contains exactly 20 intended nonignored paths: run role/evidence/handoff reports, living readiness/wake/coverage surfaces, one lab, and one test module. No private position file, credentials, token, cache, binary, unrelated source, or `.gitignore` change is present. The stale run-created `income-coverage-2026-07-16T0335.md` duplicate was removed; deterministic regeneration at stamp `2026-07-16T0349` matches `income-coverage-LATEST.md` byte-for-byte.

Challenger reconciliation:

- Accepted: exact `FAMILY_CLOSED` at F0; strategy advancement false; quarantine both canonical IDs and nearby same-panel retunes; preserve the unread holdout/no-option boundary; leave living candidates, leaders, and capital seats at zero; retain the candidate-factory NEXT with same-wake exercise discipline.
- Completed process/report nits: wrote schema-version-2 `compounding.json`; registered both family aliases; used `F0_MECHANISM -> F0_MECHANISM` as the machine funnel while retaining historical executor `F0_MECHANISM_CLOSED` only as readable shorthand; independently reran focused/adjacent/full verification; kept XLE/XLU concentration diagnostic-only; strengthened NEXT to require at least two independent predeclared mechanisms and exactly one exercised strategy decision.
- No challenger finding required machinery repair. Each finding is machine-recorded as `rejected` only in the narrow sense that it was not a broken-code finding; every substantive obligation was accepted and closed through verification or living report/handoff reconciliation. Exact rationales are in `compounding.json`.
- No challenger claim was rejected on economic substance.

Integration is pending the deterministic wrapper gate. The finalizer has not committed, pushed, merged, switched branches, edited `.gitignore`, or claimed `RUN COMPLETE`.

## DURABLE

Repo files updated:

- `scripts/monthly_sector_leader_train_lab.py` and `tests/test_monthly_sector_leader_train_lab.py`: reusable train-only monthly sector-leader decision lab with fixed-panel validation, exact completed-month-end/next-close chronology, non-overlap enforcement, same-date peer specificity control, sealed chronological holdout, strict JSON, and behavioral/boundary/negative controls.
- `reports/trader-wakes/moa/2026-07-16T0335/monthly-sector-leader-train.json`, `strategy-charter.md`, `executor-closeout.md`, `challenger-critique.md`, `merged-next-seed.md`, `compounding.json`, and this file: dated charter, canonical claim, role judgments, machine outcome, critic disposition, and learning history.
- `reports/trader-wakes/2026-07-16T0335-moa-exec.md`, `reports/trader-wakes/2026-07-16T0335-moa-merge.md`, `reports/trader-wakes/LATEST.md`, `reports/trader-wakes/INDEX.md`, `reports/readiness/LATEST.md`, and refreshed income coverage: living project truth and the sole next-wake seed.

Promotion routing:

- No skill patch: the reusable methodology is now executable code plus targeted tests, while the existing `trader-self-evolution` skill already requires same-date outcome-independent controls, sealed holdouts, strict JSON, full verification, and schema-v2 strategy decisions. Adding a second prose recipe would duplicate rather than improve the durable procedure.
- No profile-memory addition: this dated family outcome and quarantine belong in versioned compounding/readiness history. The profile memory is near capacity and should not duplicate project truth that orientation reads directly.
- No doctrine rewrite: no stable policy changed. The existing distinction between search information, strategy advancement, L0 discovery, and capital-seat authority correctly governed this wake.

No threshold, formation horizon, separation, SMA, hold, top-two, rank-weight, or option-wrapper retune was promoted. No holdout read, option mark, registry mutation, paper intent, shadow promotion, arm, broker session, funding, or live authority was created.

## LESSON

Future Trader can now:

- test dynamic monthly sector leadership on a long-history fixed nine-original-sector ETF panel without truncating the sample to late-listed XLC/XLRE;
- freeze month-end identities on completed data, enter only at the next completed close, prevent overlapping 20-session outcomes, and compare the selected leader against an outcome-independent same-date eight-peer basket;
- preserve a chronological holdout as identity-only evidence and prove future-price perturbations cannot alter the first frozen identity or train payload;
- separate conditional one-lot defined-risk planning geometry from any priced option, L1, capital-seat, or paper claim;
- close a strongly wrong-signed mechanism at F0 without spending the sealed holdout or attempting a bullish option wrapper to rescue negative underlying specificity;
- carry both stable candidate/family IDs into compounding and orientation while keeping a completed search epoch's no-advance counter bounded through its prior `completed_stamp`.

Economic lesson: established intermediate-term sector leadership did not continue in the frozen train sample. The selected leader lost 0.130819% on average after the underlying hurdle while contemporaneous nonleaders gained 0.732793%, and the dependence-aware lower bound was materially negative. Nearby same-panel rank/hold/trend polish is not a higher-information path.

## NEXT

`TRAIN_ONLY_DEFINED_RISK_CANDIDATE_FACTORY_V1`: predeclare at least two genuinely independent, non-quarantined economic mechanisms, each with a complete Layered Edge Stack and frozen specificity control before outcome access; exercise the cheap train-only factory in the same wake and close exactly one named survivor as `STRATEGY_ADVANCED` F0->F1 or one named mechanism as `FAMILY_CLOSED`. The factory itself is not strategy progress. Do not retune `SECTOR_ALLOCATION_RELATIVE_STRENGTH_CONTINUATION` / `MONTHLY_SECTOR_LEADER_CONTINUATION_BULL_CALL_35D_V1`, open this stamp's sealed holdout, or claim L1, capital seat, paper, shadow, arm, broker, funding, or live authority from scaffolding.

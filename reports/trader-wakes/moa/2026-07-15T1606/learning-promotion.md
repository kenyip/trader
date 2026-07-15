# Learning promotion — 2026-07-15T1606 finalizer

## VERIFICATION

- `.venv/bin/python -m unittest -v tests.test_breakout_continuation_holdout_lab tests.test_breakout_continuation_train_lab tests.test_low_hv_cross_section_train_lab tests.test_tsll_tracking_dislocation_train_lab tests.test_monthly_opex_post_expiry_train_lab` → 36 tests in 1.576s, `OK`. This covered holdout behavior, changed-prefix and source-tamper rejection, strict authority labels, downstream option constraints, concentration reporting, absolute-return negative controls, chronology, and adjacent regression families.
- `.venv/bin/python -m unittest discover -s tests` → 319 tests in 15.104s, `OK`.
- `.venv/bin/python -m py_compile scripts/breakout_continuation_holdout_lab.py tests/test_breakout_continuation_holdout_lab.py && git diff --check` → exit 0 with no output.
- `just platform-smoke` → exit 0, `platform smoke OK`; agentic_live remained blocked at the Stage1 OAuth gate.
- `.venv/bin/python scripts/trader_income_coverage.py --stamp 2026-07-15T1606 --write` → exit 0; regenerated dated and LATEST coverage at 21 catalog structures / 246 hypotheses / 70 evolve artifacts / living leader none.
- Canonical consistency Python check → `SUMMARY_EPOCH_CANONICAL_CONSISTENCY_OK sha=dd30bee303b7e08dc5932f1bbd69177dcf26c63141b0b09a7aabd7a2baf40e7d bytes=94859`; the exact epoch paired-excess and LB90 values equal the durable summary, F2=true, L1=false, and the ten-session option boundary is present.
- Final handoff validation, report-consistency validation, final secret/debris scan, and final `git diff --check` are run after these role artifacts are written and are recorded in the finalizer closeout/LATEST surface.

## DURABLE

Strategy charter and outcome:

- `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` advanced exactly `F1_TRAIN → F2_UNTOUCHED_HOLDOUT/L0`. The frozen 113-pair holdout retained eight-symbol breadth and passed all six unchanged pooled discovery checks: treated `+2.2298%`, control `-1.4955%`, paired excess `+3.7254%`, LB90 `+1.8624%`, and zero integrity violations.
- This is pooled-panel underlying directional evidence only. `pricing_calls=0`; no option payoff, L1, capital seat, paper, shadow, arm, broker, or live authority exists. The claim is not universal by symbol or uniform over time: META paired excess was negative, AMZN/META treated means were negative, MSFT support was thin, and the earliest chronological tertile had negative treated mean/LB90.
- The immutable canonical evidence remains `.cache/platform/breakout_continuation_holdout_2026-07-15T1606.json` with SHA-256 `dd30bee303b7e08dc5932f1bbd69177dcf26c63141b0b09a7aabd7a2baf40e7d` and 94,859 bytes. Its tracked strict-JSON summary is `reports/trader-wakes/moa/2026-07-15T1606/breakout-holdout-summary.json`.

Accepted challenger findings and repairs:

- N1 accepted and repaired: future runner payloads split `funnel_claim_f2` from `l1_claim`, remove inherited `f2_or_l1_claim`, and keep authority fail-closed. The immutable cache bytes/SHA were preserved; the durable summary explicitly supersedes its legacy overloaded field.
- N2 accepted and repaired: the downstream option stage now names `absolute_after_cost_option_pnl_and_path_risk` as primary and forbids underlying paired excess from rescuing absolute option failure.
- N3 accepted and repaired: the frozen downstream constraints require the original 168 development rows, a hard ten-session primary stop, non-primary hold-to-expiry, dual adverse multi-leg cost axes, listed-expiry/strike availability with fail-close, no retuning from the opened 113, and symbol/time concentration.
- N4 accepted as a project-truth cleanup, not a decision change: `configs/search_epoch.json` now pins paired excess `0.03725361396111984` and LB90 `0.018623657692392246` exactly to the canonical summary.
- N5 accepted and closed by the 36-test focused/adjacent run plus the 319-test full suite.
- N6 accepted: strategy advancement is attributed only to the frozen experiment; validator/claim repairs are separately recorded as repair/search-information deltas.

Rejected challenger interpretations, with evidence:

- Rejected retroactively failing the frozen pooled F2 gate because some diagnostic slices are weak. Those slices were predeclared non-gating context; mutating the gate after inspection would be post-hoc. Their weakness instead narrows scope and constrains the option stage.
- Rejected any inference that F2 implies L1 or capital readiness: split claim fields, the independent authority block, readiness, and tests all keep L1 false.
- Rejected relabeling the opened 113 rows as a new untouched option holdout. `configs/search_epoch.json`, the durable summary, and `merged-next-seed.md` make them inspected secondary stress only.

Promotion surfaces:

- Repo project truth: `configs/search_epoch.json`, `breakout-holdout-summary.json`, `strategy-decision-charter.md`, `reports/readiness/LATEST.md`, the finalizer merge/LATEST wake reports, and `reports/trader-wakes/INDEX.md`.
- Reusable machinery/tests: `scripts/breakout_continuation_holdout_lab.py` and `tests/test_breakout_continuation_holdout_lab.py`.
- Reusable procedure: profile-local `trader-self-evolution` was patched with the split-funnel/authority-label pitfall, immutable one-shot supersession rule, and required assertions.
- Profile memory: no update. The new material is a reusable procedure plus dated project evidence, not a stable Ken preference/routing fact; memory is already near its compact limit.

Integration is pending the deterministic wrapper gate. The finalizer did not commit, push, merge, switch branches, or claim `RUN COMPLETE`.

## LESSON

Future Trader can now open a frozen strategy-level holdout with source/population/overwrite controls, keep immutable evidence bytes intact, and still repair a misleading claim label on durable surfaces. Funnel advancement and evidence authority must be separate booleans: an F2/L0 underlying pass may be real strategy progress while L1 remains false. After such a pass, option DNA must freeze on development data, optimize absolute after-cost option PnL and path risk over the measured ten-session horizon, fail closed on unavailable listings, and treat the opened underlying holdout only as non-retunable secondary stress.

## NEXT

`BREAKOUT_F2_OPTION_PAYOFF_FREEZE`: freeze one exact listed-expiry/strike/debit/management 14-DTE `$1`-wide bull-call specification on only the original 168 development rows; require non-vacuous positive absolute after-cost option PnL under adverse fixed-dollar and percentage multi-leg costs, one-lot max loss ≤`$300`, window max DD ≤`$75`, listing availability, symbol/time concentration, a hard ten-session primary stop, and no same-bar reentry; use the opened 113 only as labeled secondary stress without retuning; keep evidence L0/no L1 and require fresh live-clock paper before F4.

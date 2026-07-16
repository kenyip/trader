# Learning promotion — 2026-07-15T1747

## VERIFICATION

- Focused behavioral, boundary, negative-control, provenance, and adjacent strategy suite:
  - command: `.venv/bin/python -m unittest -v tests.test_post_shock_range_compression_train_lab tests.test_low_hv_cross_section_train_lab tests.test_breakout_continuation_train_lab tests.test_iron_butterfly_sim tests.test_trader_income_coverage`
  - exact result: `Ran 27 tests in 1.591s — OK`.
  - coverage includes prior-only matching, next-session chronology, outcome-independent selection, non-overlapping windows, holdout secrecy, non-vacuous breadth, positive-point/non-positive-bootstrap rejection, strict JSON nulls, nonfinite fail-close, the explicit five-session-versus-21-DTE horizon boundary, exact first-download/cache replay identity, planned iron-butterfly structural bounds, and derived coverage state.
- Required full suite:
  - command: `.venv/bin/python -m unittest discover -s tests`
  - exact result: `Ran 339 tests in 16.445s — OK`.
- Changed Python/test compilation:
  - command: `.venv/bin/python -m py_compile scripts/post_shock_range_compression_train_lab.py scripts/low_hv_cross_section_train_lab.py tests/test_post_shock_range_compression_train_lab.py tests/test_low_hv_cross_section_train_lab.py`
  - exact result: exit `0` with no output.
- Current-code claim replay:
  - command: `.venv/bin/python scripts/post_shock_range_compression_train_lab.py --out .cache/platform/post_shock_range_compression_finalizer_replay.json`
  - exact result: exit `0`; `FAMILY_CLOSED`; train `61` pairs across `6` symbols; paired compression `-0.0037473254364201393`; one-sided LB90 `-0.010126860517532412`; pin-rate edge `0.0`; integrity `[]`; pricing calls `0`.
  - canonical versus replay comparison after removing only `generated_at`: `normalized_payload_equal True`; both normalized SHA-256 values are `f81e987152792a3b2bc270e35e946b97eb388a7f1c0c6e87365455378fb2d2`.
  - independent chronological train-tertile means: `[-0.006232627697476424, -0.0027855774666764527, -0.0022963213494557578]`; all are negative.
- Derived coverage regeneration:
  - command: `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-15T1747`
  - exact result: exit `0`; wrote dated plus LATEST surfaces with `21` catalog structures, `246` hypotheses, `70` evolve artifacts, and no living quality leader. The redundant run-created `2026-07-15T1802` snapshot was removed; `2026-07-15T1747` is canonical for this wake.
- Handoff/completion contract and final audit:
  - command: `.venv/bin/python -m unittest -v tests.test_trader_build_compounding tests.test_trader_run_completion_gate`
  - exact result: `Ran 38 tests in 6.210s — OK`.
  - command: `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-15T1747 --base-head 955c194194ee263ff7329c2f952486dd2f48b7dd`
  - exact result: exit `0`; schema `2`; outcome `FAMILY_CLOSED`; strategy advanced `false`; `3` useful deltas; `4` critic findings closed; `role_ready=true`.
  - temporary-index command: `git read-tree HEAD`; `git add -A`; `scripts/trader_run_completion_gate.py prepare --stamp 2026-07-15T1747 --base-head 955c194194ee263ff7329c2f952486dd2f48b7dd --run-branch trader/run-2026-07-15T1747`; then delete the temporary index and verify the real index.
  - exact result: exit `0`; `staged_files=22`; complete staged diff across `22` paths; private-key/GitHub/API-secret/AWS-key hits `0`; sensitive paths `[]`; session-log/prompt/preflight debris `[]`; private-position paths `false`; real index remained clean.
  - `git diff --check` exited `0` with no output.

Integration is pending the deterministic wrapper gate. This finalizer does not commit, push, merge, switch branches, or claim `RUN COMPLETE`.

## DURABLE

Strategy charter and outcome:
- Charter: `reports/trader-wakes/moa/2026-07-15T1747/strategy-charter.md`.
- Candidate/family: `POST_SHOCK_RANGE_COMPRESSION_IRON_BUTTERFLY_21D_V1` / `POST_SHOCK_RANGE_COMPRESSION_MATCHED_CONTROL`.
- Economic mechanism: a completed large move with elevated short-versus-long realized volatility but price still near prior SMA20 might be temporary liquidity/attention pressure followed by five-session range compression and improved terminal pin versus prior same-symbol high-HV neutral no-shock controls.
- Planned structure only: future one-lot 21-DTE symmetric `$2`-wing credit iron butterfly; positive theta/short vega intent, bounded short gamma, with renewed expansion, vega, pin/assignment, and four-leg friction risks. `capital_fit_usd=$200`, one-lot `max_loss_usd=$200`, `max_lots=1` are structural planning bounds before entry credit and closing friction—not observed or simulated loss.
- Outcome: `FAMILY_CLOSED`, `F0_MECHANISM -> F0_MECHANISM`. Train density and breadth passed at `61` pairs/all six symbols, but treated range was `5.018873756%` versus control `4.644141213%`; paired compression was `-0.374732544%`; LB90 was `-1.012686052%`; pin-rate edge was `0`; every train tertile was negative. The final 41 blueprints remain outcome-unread and option pricing calls remain zero.
- Scope: quarantine the exact frozen panel/trigger/control/horizon family. This is not a universal claim about every shock definition or iron butterfly. No AAPL n=10 post-hoc salvage, threshold mining, L1, leader, capital seat, registry promotion, paper force, shadow, arm, broker, or live authority.

Accepted challenger findings and repairs:
- Accepted the `FAMILY_CLOSED` decision and all claim boundaries. The finalizer independently replayed the artifact exactly and retained fixed present-day panel survivorship/listing bias, close-only path understatement, high-HV plus `|1d|<=0.5%` control semantics, sparse AMD/NVDA n=4 limitations, and zero option/cost/fill evidence.
- Accepted the horizon-alignment nit. Living prose and payload state that a five-session underlying range/pin pre-screen does not measure 21-DTE theta/vega capture; the complete-stack test now asserts that label.
- Accepted the shared cache provenance repair. `scripts/low_hv_cross_section_train_lab.py` rereads the persisted CSV on the first download, and `tests/test_low_hv_cross_section_train_lab.py` uses `np.nextafter` plus `check_exact=True` to prove first-run/replay identity.
- Accepted the full-suite condition and reran focused plus all `339` tests after final code/test repairs.
- Accepted the stale-readiness/NEXT finding. Living wake/readiness surfaces now use the merged `POST_EARNINGS_INFO_RESOLUTION_DRIFT_F0` seed and record consecutive no-strategy-advance `2`, requiring a mechanism pivot on next orientation.

Rejected findings/claims:
- Rejected the executor's `MONTH_END_FLOW_POSITIVE_DRIFT_PCS_F0` as the living NEXT because it is too near closed turn-of-month, monthly OPEX, and monthly ranking families.
- Rejected any inference that AAPL's positive post-hoc n=10 slice supports a candidate or reopening; no symbol-level gate was predeclared and every chronological pooled tertile was negative.
- No challenger critique finding itself was rejected; its strategy verdict, labeling limits, and merged NEXT were accepted.

Promotion routing:
- Dated outcome/current project truth: claim JSON, this learning record, schema-v2 `compounding.json`, final merge/LATEST/INDEX/readiness surfaces, charter, and canonical income coverage.
- Reusable machinery/tests: `scripts/post_shock_range_compression_train_lab.py`, `tests/test_post_shock_range_compression_train_lab.py`, `scripts/low_hv_cross_section_train_lab.py`, and `tests/test_low_hv_cross_section_train_lab.py`.
- Reusable procedure/pitfall: profile skill `trader-self-evolution` records that hash-cited first-download evidence must consume the persisted representation before evaluation, with exact first-run/replay regression coverage.
- Memory: no addition. The autonomy, proxy-evidence, and completion stances are already durable; dated mechanism metrics and run state belong in repo evidence, not profile memory.

## LESSON

Future Trader now knows that this exact post-shock/high-HV/near-SMA20 cohort expanded rather than compressed over the following five-session close path versus matched prior high-HV neutral controls, with no incremental terminal pin edge. The gross underlying mechanism fails before a short-gamma, four-leg iron butterfly can help; option costs or management were correctly never invoked, and the unread holdout remains unspent.

Future Trader can also produce hash-cited adjusted-history evidence deterministically on both the first download and later cache replay. Persisting a CSV is not enough if the first evaluation still consumes downloader floats: the evaluator must reread the persisted representation, and an exact-series regression must detect sub-ulp drift.

## NEXT

POST_EARNINGS_INFO_RESOLUTION_DRIFT_F0: predeclare a train-only, outcome-independent event study on a fixed liquid multi-name panel selected from the current full-universe rank before train outcomes. Use point-in-time announcement timing that was knowable without future leakage; enter only after the first completed post-announcement session under an exact lag rule; choose one primary underlying outcome and one secondary before running; match prior-only same-symbol non-event controls without replacement with non-overlapping windows; inspect only the chronological first 60% and keep the final 40% outcome-unread. Close at F0 unless non-vacuous pair/symbol floors, positive paired primary effect, one-sided 90% block-bootstrap lower bound, and all chronology/integrity gates pass. Do not reopen post-shock range compression, TOM, OPEX, monthly 12-1 momentum, or the breakout bull-call expression. Only after an underlying F0 pass may a one-lot defined-risk expression be frozen with capital_fit_usd, max_loss_usd <=$300, max_lots=1, and dual multi-leg costs; discovery remains L0 with no registry, paper force, shadow, arm, broker, or live action.

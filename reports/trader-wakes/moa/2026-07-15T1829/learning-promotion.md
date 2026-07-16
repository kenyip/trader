# Learning promotion — 2026-07-15T1829

## VERIFICATION

- Focused behavioral, boundary, negative-control, provenance, and adjacent-strategy suite:
  - command: `.venv/bin/python -m unittest -v tests.test_post_earnings_information_drift_train_lab tests.test_low_hv_cross_section_train_lab tests.test_post_shock_range_compression_train_lab tests.test_trader_income_coverage`
  - exact result: `Ran 26 tests in 2.576s — OK`.
  - coverage includes explicit BMO/AMC mapping, ambiguous timing stand-aside, prior-only non-event controls, outcome-invariant selection, without-replacement/non-overlap integrity, dense-positive and positive-point/non-positive-bound gates, nonfinite fail-close, strict-null zero-control support, unread holdout, retrospective-not-PIT authority, serialized match geometry/extreme-pair diagnostics, shared adjusted-history replay, adjacent matched-control semantics, and derived coverage state.
- Required full suite:
  - final command: `unset GIT_INDEX_FILE; .venv/bin/python -m unittest discover -s tests`
  - exact final result after all code/evidence/report changes: `Ran 349 tests in 17.891s — OK`.
  - disclosed recovery: the first post-surface rerun inherited a removed temporary index path because Hermes terminal preserves exported environment state and returned `Ran 349 tests in 15.583s — FAILED (errors=11)`; all errors were fixture `git commit` setup failures. `unset GIT_INDEX_FILE` restored the ordinary index, and the unchanged suite passed. The loaded `trader-self-evolution` skill already documents this exact temporary-index pitfall, so no duplicate skill patch was added.
- Changed Python/test compilation:
  - command: `.venv/bin/python -m py_compile scripts/post_earnings_information_drift_train_lab.py tests/test_post_earnings_information_drift_train_lab.py`
  - exact result: exit `0` with no output.
- Current-code claim replay:
  - commands: run `scripts/post_earnings_information_drift_train_lab.py` once to the tracked claim and once to a cache replay, then compare strict-JSON payloads after removing only `generated_at`.
  - exact result: both exits `0`; substantive equality `True`; normalized SHA-256 both `68454675f609da13816fa55f0a577027516b25d511bd5869baa200f8f62f7441`; tracked raw SHA-256 `df7e80547438e6c7577e82c13de42c6419e61ad2fbfdf489431ac501e0d802c5`.
  - reproduced decision: `FAMILY_CLOSED`; train `75` pairs / `7` symbols; event mean `-0.0048312306693351955`; control mean `-0.0018400686017785396`; paired mean `-0.0029911620675566564`; LB90 `-0.016153603629205513`; hit edge `-0.013333333333333364`; integrity `[]`; holdout `51` unread; pricing calls `0`.
  - match diagnostics: max/median calendar distance `420/70` sessions; reaction gap `0.014535216821615071/0.005119322162228213`; ret20 gap `0.09867362859333861/0.03244327657868151`; hv20 gap `0.19649267782103053/0.030509601706523032`; absolute paired-excess >=10% count `15/75`. These are diagnostic-only, not post-hoc pass/fail gates.
  - all `75/75` train rows had finite outcome and match-geometry fields; all embedded price/event cache hashes reverified separately before final handoff.
- Derived coverage regeneration:
  - command: `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-15T1829`
  - exact result: exit `0`; dated and LATEST surfaces are byte-identical; `21` catalog structures, `246` hypotheses, `70` evolve artifacts, and no living quality leader. Redundant run-created `2026-07-15T1845` snapshot removed.
- Handoff/completion contract:
  - schema: `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-15T1829 --base-head 6e833902fbd81127f8b88a18208166cad188b15d` -> `ok=true`, schema `2`, outcome `FAMILY_CLOSED`, `4` useful deltas, `7` critic findings closed.
  - focused gate regressions: `.venv/bin/python -m unittest -v tests.test_trader_build_compounding tests.test_trader_run_completion_gate` -> `Ran 38 tests in 6.212s — OK`.
  - temporary-index prepare: `.venv/bin/python scripts/trader_run_completion_gate.py prepare --stamp 2026-07-15T1829 --base-head 6e833902fbd81127f8b88a18208166cad188b15d --run-branch trader/run-2026-07-15T1829` -> `ok=true`, branch exact, `20` staged files. The real index was never staged.
  - claim provenance: `16/16` embedded source cache hashes verified; train gate false, holdout unread, pricing zero, strict JSON loaded.
  - complete staged diff review: `20` intended paths / `272936` patch bytes; `git diff --cached --check` empty; no `.cache`, temp, log, private-position, credential, token, secret, private-key, or unexpected executable-mode path; four JSON files parse strictly; secret-pattern scan counts all zero. Historical executor/challenger/meta/orientation/exit files are preserved evidence, not debris.
  - final ordinary-index status and a final prepare rerun are verified after this record is staged in a disposable index.

Integration is pending the deterministic wrapper gate. This finalizer has not committed, pushed, merged, switched branches, or claimed `RUN COMPLETE`.

## DURABLE

Strategy charter and outcome:
- Economic mechanism: quarterly earnings may resolve concentrated uncertainty slowly enough that the signed first completed post-announcement move continues for five sessions relative to prior same-symbol, same-sign, non-event reactions.
- Candidate/family: `POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT_CALL_DEBIT_21D_V1` / `POST_EARNINGS_INFORMATION_RESOLUTION_DRIFT` on frozen AAPL, AMD, SMCI, TSLA, META, GOOGL, ARM, NVDA.
- Planned expression only: conditional one-lot 21-DTE `$2`-wide call debit after a positive reaction or put debit after a negative reaction; intended bounded signed delta/convexity, with dangerous post-event IV crush, theta/gamma, gap, and two-leg liquidity exposures. `capital_fit_usd=$200`, one-lot `max_loss_usd=$200` before closing friction, `max_lots=1`, one global earnings-risk unit.
- Outcome: exact `FAMILY_CLOSED`, `F0_MECHANISM -> F0_MECHANISM`. Density/breadth/integrity passed, but absolute event expectancy, event-versus-control mean, paired mean, uncertainty lower bound, and hit-rate edge failed. Positive median/frequency hid adverse tails; the final 51 blueprints remain outcome-unread.
- Authority: retrospective Yahoo timestamps support post-announcement session alignment only, not historical known-at/pre-event scheduling alpha. No next-open execution, option marks, IV crush, costs, fills, managed PnL, L1, capital seat, registry, paper, shadow, arm, broker, or live authority.

Accepted challenger findings and repairs:
- Accepted `PASS WITH NITS` and the exact family close; no strategy verdict was reopened.
- Accepted the retrospective-versus-PIT boundary and made it explicit in the tracked claim, readiness, final reports, and regression assertions.
- Accepted the missing match-geometry/extreme-tail diagnostics. The lab now serializes per-pair calendar/reaction/ret20/hv20 gaps plus max/median summaries and a diagnostic-only >=10% extreme-pair count. The current sample has `15/75` extremes and a 420-session maximum control distance; that weakens causal precision but cannot rescue a family whose absolute event mean, paired mean, lower bound, and hit edge all fail.
- Accepted the optional zero-control-support negative control. The empty path now fails before bootstrap, uses strict JSON `null`, and cannot pass vacuously.
- Accepted sparse SMCI and survivor/listing bias as scope limits and rejected subset salvage.
- Accepted the readiness repair: phase remains BUILD, capital path and B checks remain unchanged, no-advance streak is `3`, `strategy_burst_stop_required=true`, and living NEXT is the burst-stop reassessment.
- Accepted the wording correction: this is the third consecutive completed post-advance strategy wake without `STRATEGY_ADVANCED`, not the third completed epoch wake; the breakout epoch itself completed with F2 advancement at 1606.

Rejected claims:
- Rejected threshold/symbol churn, median-positive mining, holdout peeking, or sparse-subset salvage for this exact family.
- Rejected any pre-event scheduling/known-at claim from current retrospective timestamps.
- Rejected capability/tests as strategy advancement; they are search information accompanying a decisive F0 close.
- Rejected any capital-seat comparison against a living leader because none exists.
- No material challenger judgment was rejected; its nits were accepted and repaired or used to narrow labels.

Promotion routing:
- Dated outcome/current project truth: tracked strict-JSON claim, executor/challenger/finalizer reports, readiness, LATEST, INDEX, this learning record, and schema-v2 compounding handoff.
- Reusable machinery/tests: `scripts/post_earnings_information_drift_train_lab.py`, `tests/test_post_earnings_information_drift_train_lab.py`, and direct dependency `lxml>=5.0` in `requirements.txt`.
- Skill: no patch required. `trader-self-evolution` already contains the durable matched-control pitfalls to report maximum covariate/time distance and extreme-pair counts, fail closed on zero support with strict nulls, and avoid salvaging positive point/median evidence when dependence-aware gates fail. This wake brought the new lab into compliance rather than adding duplicate guidance.
- Memory: no addition. The stable autonomy, evidence-authority, and completion stances already exist; dated mechanism metrics and streak state belong in repository evidence.

## LESSON

Future Trader now knows that unconditional post-earnings signed five-session continuation on this frozen high-attention panel is not a durable income mechanism: the event path itself averaged negative signed continuation, it underperformed prior matched non-event reactions, its uncertainty bound and hit edge were negative, and a positive median concealed 15 large absolute paired outcomes. Do not spend the sealed holdout or tune the reaction threshold/panel to rescue it.

Future Trader can now make matched-event evidence auditable at the row and population levels: persist calendar/covariate match geometry, label extreme-pair diagnostics as non-gating unless predeclared, and fail before return/bootstrap estimation when frozen matching has zero support. Retrospective timestamp precision is adequate for post-announcement alignment but never substitutes for point-in-time known-at provenance.

## NEXT

BURST_STOP_SEARCH_DESIGN_REASSESSMENT: stop strategy-experiment volume. Diagnose the 1648 breakout-expression dual-cost/path close, 1747 post-shock compression close, and 1829 post-earnings continuation close; test whether current matched-control discovery is surfacing positive-median/adverse-tail families unsuitable for one-lot defined-risk income; inventory independent non-quarantined evidence classes; then open at most one successor epoch/charter with a complete Layered Edge Stack and predeclared falsifier before another strategy experiment. Do not rerun or threshold/panel-churn the closed post-earnings, post-shock, breakout-expression, TOM, OPEX, or monthly-ranking families. No registry, paper force, shadow, arm, broker, or live action.

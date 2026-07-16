# Learning promotion — 2026-07-16T1123

## VERIFICATION

Finalizer-owned commands and exact results:

- `.venv/bin/python -m unittest -v tests.test_yield_curve_regional_bank_train_lab` → **12 tests**, `OK` in 0.044s. Coverage includes direct-tenor parsing, missing-tenor no-forward-fill, duplicate-date fail-close before drop, persisted-byte replay, completed-bar lag/future invariance, positive conjunction, non-vacuous five-episode uncertainty, unstable-center rejection, event-tail-versus-relative-tail negative control, calendar concentration, cost-label semantics, capital-planning-only option boundaries, and identity-only holdout sealing.
- `.venv/bin/python -m unittest tests.test_yield_curve_regional_bank_train_lab tests.test_trader_build_compounding tests.test_trader_run_completion_gate tests.test_trader_income_coverage tests.test_trader_build_progress` → **68 tests**, `OK` in 9.751s.
- `.venv/bin/python -m unittest discover -s tests` → **445 tests**, `OK` in 29.377s.
- `.venv/bin/python -m py_compile scripts/yield_curve_regional_bank_train_lab.py tests/test_yield_curve_regional_bank_train_lab.py` → `OK`.
- Current-code persisted-cache replay to `/tmp/yield-curve-regional-bank-finalizer-replay.json` → `substantive_replay_equal=true` after dropping only `generated_at`; normalized SHA-256 `36c96f9d238edaca0fbd4b36e601123556e4f93c755f16fb5898aa20aee3f6d8`; strict-JSON round-trip true; holdout outcome metrics unread; option pricing calls 0.
- Independent aggregation of the four serialized train episodes reproduced KRE mean after 10 bps `0.048907549555746443`, XLF mean `0.026428304576612743`, paired KRE-minus-XLF mean `0.0224792449791337`, year counts `2009:1 / 2024:3`, and maximum calendar concentration `0.75`.
- `shasum -a 256 reports/trader-wakes/moa/2026-07-16T1123/yield-curve-regional-bank-train.json` → current finalizer raw SHA-256 `676e674fe5be6a6ea01b366a141bdca2c8e6ac6b60fc6fbf4f0fd299f9a06116`.
- `.venv/bin/python scripts/trader_income_coverage.py --write --stamp 2026-07-16T1123 --json` → 21 catalog structures, 246 hypotheses, 70 evolve artifacts, no quality leader; TSLL archive 3/3 RTH dates, 13 expirations on each retained market date, plumbing gate eligible only.
- `.venv/bin/python scripts/trader_build_compounding.py validate-handoff --repo . --stamp 2026-07-16T1123 --base-head fc73411a46409c698384feb44b70cc3fb2f39c35` and disposable-index completion `prepare` are final audit gates; their exact green results are recorded below after all derived surfaces are written.

The executor/challenger raw/normalized hashes `f8e20be6…` / `7435db0c…` remain truthful pre-finalizer phase receipts. Finalizer regeneration superseded those bytes only by adding source/date/cost claim boundaries; the economic metrics, failed gates, holdout seal, and `FAMILY_CLOSED` decision did not change.

## DURABLE

Strategy charter and accepted outcome:

- Economic mechanism: a completed official Treasury 2s10s bull steepening might improve regional-bank funding/lending economics and create delayed KRE updrift and KRE-over-XLF specificity over ten completed sessions.
- Exact candidate/family: `OFFICIAL_2S10S_BULL_STEEPENING_KRE_BULL_CALL_21D_V1` / `OFFICIAL_YIELD_CURVE_BULL_STEEPENING_REGIONAL_BANK_RELATIVE_UPDRIFT`.
- Frozen decision: advance `F0_MECHANISM -> F1_TRAIN` only if every density, year-breadth, absolute-center, specificity, non-vacuous uncertainty, hit-rate, event-tail, and integrity gate passed; otherwise close at F0 without holdout outcomes or option pricing.
- Accepted result: `FAMILY_CLOSED`, `F0_MECHANISM -> F0_MECHANISM`, strategy advancement false. Seven total events yielded four train episodes across only two years, with `2009:1 / 2024:3`; 75% calendar concentration strengthens the density failure. Favorable KRE `+4.890755%` and paired `+2.247924%` means remain diagnostic only because n≥24, ≥10 years, and the non-vacuous five-episode LB gate failed. Three holdout identities remain unread and option pricing is zero.
- Future option context only: one-lot KRE 18–28 DTE $2-wide bull-call debit spread, `capital_fit_usd=200`, frictionless planning `max_loss_usd=200`, `max_lots=1`. Actual debit, listed legs, closing friction, assignment/exercise, theta/vega path, and management were not measured; no F1/L1/seat/paper/shadow/live authority exists.

Challenger reconciliation:

1. **N1 accepted as finalization state; rejected as an executor claim defect.** `configs/search_epoch.json`, `docs/SEARCH_EPOCH_2026-07-16T0546.md`, readiness, wake, and handoff surfaces now record successor no-advance 2, `strategy_pivot_required=true`, and burst-stop false.
2. **N2 accepted and repaired.** The runner and canonical artifact now serialize `train_signal_year_counts={2009:1, 2024:3}` and `train_calendar_concentration_max_fraction=0.75`; a focused test locks the boundary. Living prose treats concentration as part of insufficient density, not a salvage route.
3. **N3 accepted as finalizer ownership; rejected as a code defect.** Finalizer independently ran 12 focused, 68 adjacent, and 445 full tests plus compile, replay, strict-JSON, hash, and independent aggregation checks.
4. **N4 accepted as the sole NEXT boundary; rejected as a missing-NEXT defect.** Existing dividend archive, issuer-crosscheck, and assignment-guard machinery remains provenance infrastructure—not updrift evidence. A new multi-issuer increase definition and gates must be frozen before outcomes.
5. **N5 accepted as forward stop state; rejected as a current defect.** A third successor no-advance is explicitly burst-stop/reassessment, not permission for another sparse event-to-bull-call clone.
6. **N6 accepted as finalizer regeneration work; rejected as a challenger-phase defect.** Readiness, merge, LATEST, INDEX, epoch, coverage, and compounding surfaces now agree on the accepted 1123 close and sole dividend-increase pivot.

Finalizer independent findings:

- **Repaired:** duplicate Treasury source dates could become hidden if one duplicate row had a missing tenor because uniqueness was checked after dropping missing rows. Uniqueness now fails closed before the drop; a negative test covers one complete plus one missing duplicate.
- **Repaired:** artifact geometry said cost “each leg” while the model subtracts one 10-bps sensitivity from each underlying return series. One shared constant now drives evaluation and the claim key is `underlying_round_trip_cost_bps=10.0`; a semantic boundary test prevents relabel drift.
- Neither repair changed source hashes, event identities, train returns, failed gates, or outcome.

Durable surfaces:

- Machinery/tests: `scripts/yield_curve_regional_bank_train_lab.py`; `tests/test_yield_curve_regional_bank_train_lab.py`.
- Claim/charter/handoff: `reports/trader-wakes/moa/2026-07-16T1123/yield-curve-regional-bank-train.json`, `strategy-charter.md`, `executor-closeout.md`, `challenger-critique.md`, `merged-next-seed.md`, `compounding.json`, and this file.
- Project truth: `configs/search_epoch.json`, `docs/SEARCH_EPOCH_2026-07-16T0546.md`, `reports/readiness/LATEST.md`, `reports/trader-wakes/2026-07-16T1123-moa-exec.md`, `reports/trader-wakes/2026-07-16T1123-moa-merge.md`, `reports/trader-wakes/LATEST.md`, and `reports/trader-wakes/INDEX.md`.
- Derived coverage: `reports/readiness/income-coverage-2026-07-16T1123.md` and `income-coverage-LATEST.md` agree on 21/246/70/no leader and 3/3 RTH archive plumbing density.
- Concurrent RTH truth preserved: `reports/trader-wakes/2026-07-16T1430-rth.md` remains a historical reports-only STAND_ASIDE receipt with 14/0/14, zero real paper risk, and no B6 advance.
- Skill promotion: active-profile `trader-self-evolution` now records the reusable tiny-event-population pitfall: persist year counts/calendar concentration and require non-vacuous density, breadth, and uncertainty before an option wrapper or holdout read.
- Profile memory: no update. This wake produced project truth and a reusable procedure/test lesson, not a compact stable preference or routing fact.

Integration is pending the deterministic wrapper gate. The finalizer does not commit, push, merge, switch branches, or claim `RUN COMPLETE`.

## LESSON

Future Trader can now distinguish a direct, point-in-time macro source from an economically usable repeated-income exposure. Official source semantics and favorable tiny-sample centers are not enough: the exact opportunity population must be non-vacuous across episodes and calendar years before uncertainty, holdout access, or an option wrapper has authority. Calendar concentration is machine evidence, not just prose. Source adapters must also reject duplicate dates before cleaning can hide them, and cost labels must describe the exact modeled deduction. The official-2s10s regional-bank geometry is closed rather than tuned.

## NEXT

`MULTI_ISSUER_DIVIDEND_INCREASE_FORWARD_UPDRIFT_F0`: pivot to a materially different issuer cash-flow-confidence mechanism. Before outcomes, freeze a point-in-time regular cash-dividend increase definition from declaration-date and amount records; exclude specials, unchanged amounts, cuts, preferred/ambiguous securities, missing `known_at`, nonpositive amounts, and chronology conflicts; predeclare a fixed liquid multi-issuer panel with same-date sector controls, next-close ten-session forecast, labeled underlying cost, global chronological train/sealed identity holdout, and density/year/issuer-breadth, specificity, dependence-aware uncertainty, hit-rate, tail, and integrity gates. Existing dividend provenance and assignment-guard tooling is infrastructure, not edge evidence. Close exactly one `STRATEGY_ADVANCED` F0→F1 or `FAMILY_CLOSED` decision in-wake. Future one-lot defined-risk expression must have `capital_fit_usd` and `max_loss_usd <= 300`, `max_lots=1`. No yield-curve salvage, holdout reads, L1, seat, paper, shadow, arm, broker, funding, or live authority.

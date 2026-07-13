# MOA BUILD challenger critique — 2026-07-12T1806

WAKE: 2026-07-12T1825 PDT (Sunday; market closed)
PHASE: BUILD / L0
SLEEVE: $3,000
ROLE: Grok 4.5 challenger (read-only judgment)
PAPER_ONLY: true
OUTCOME: CAPABILITY accepted with minor nits

## Rubric

| # | Criterion | Verdict | One line |
|---|---|---|---|
| 1 | Goal progress | **PASS** | Closes a claim-relevant short-call assignment realism gap on open simulator-capability route; no edge claim, but better future paper honesty. |
| 2 | Creativity / independence | **PASS** | Justified prior-NEXT capability; weekend archive skipped; not closed-family thrash or TSLA/TSLL monomania. |
| 3 | Claim validity | **PASS** | Machinery-only claim; default remains disabled; required mode fails closed; no L1/B3/B4/capital mutation. |
| 4 | Evidence and test quality | **PASS** | Real code + independent re-run: focused 13/13, smoke green, full 143/143; tests are behavioral/boundary/negative, not pure mirrors. |
| 5 | Falsification | **PASS** | Predeclared falsifiers exercised (lookahead leak, fail-open required data, at-risk non-exit, bear-put contamination); none fired. |
| 6 | Capital honesty | **PASS** | No living leader, no seat, no hyp/paper/shadow/live change; capital fields still required for any future candidate. |
| 7 | Research freedom | **PASS** | Archive 1/3 did not freeze capability work; symbol/strategy catalog remain open. |
| 8 | ONE NEXT seed; no live/shadow | **PASS** | Honest known_at provider inventory or fail-closed data packet; no promotion language. |

**Overall: PASS (8/8)** — minor non-blocking nits for finalizer optional polish.

## What the executor chose

Orientation (`reports/trader-wakes/moa/2026-07-12T1806/orientation.json`): weekend context; `redirect_required=false`; executable routes = historical proxy discovery + simulator capability; observed option replay blocked at 1/3 market dates; prior 1740 NEXT named the no-lookahead dividend/early-assignment boundary.

Executor closed that named capability loop: `corporate_action_risk.py` + injection into `diagonal_sim` and bull-call `debit_vertical_sim`, with doctrine/coverage honesty updates. No strategy DNA, hyp registry, stress JSON, paper ledger, or readiness promotion.

## Claim audit (challenged against live files)

### Accepted claims

1. **Announcement-time visibility** — `visible_dividend_events` drops `known_at > as_of`. Independent unit path: pre-announcement `no_known_dividend_before_expiry`; post-announcement can be `early_assignment_risk`. Test: `test_future_announcement_cannot_leak_into_earlier_bar`.

2. **Required fail-closed** — diagonal missing provider → `required dividend event provider missing`; bull-call provider returning `None` under required → `coverage missing`. Test: `test_required_provider_missing_or_uncovered_fails_closed`.

3. **Malformed fail-closed** — non-finite dividend amount → `invalid dividend event data`. Test: `test_malformed_dividend_data_fails_closed`.

4. **Realized assignment-risk exits in both short-call sims** — extreme known dividend produces `early_assignment_risk_exits > 0` and exit-reason counts on diagonal + bull-call. Test: `test_known_dividend_closes_at_risk_short_calls_in_both_sims`.

5. **Bear-put isolation** — required flag does not block put path; metrics label `not_applicable_put`. Test: `test_bear_put_vertical_does_not_require_dividend_events`.

6. **Default remains off** — `require_dividend_events=False` and no provider → `corporate_action_mode=disabled`. Existing proxy diagonal/debit history is not silently restressed under a new assignment model. Capital note strings updated to “provider-dependent,” not “fully modeled.”

7. **No edge / no capital path** — coverage still 20 structures / 245 hyps / 67 evolve artifacts; quality leader none. No living leader seat language.

### Independent verification (challenger re-ran)

```text
.venv/bin/python -m unittest tests.test_corporate_action_risk \
  tests.test_debit_vertical_sim tests.test_diagonal_oos_stress \
  tests.test_defined_risk_fixed_cost -v
→ Ran 13 tests … OK

.venv/bin/python -m trader_platform.smoke_test
→ platform smoke OK; agentic_live blocked

.venv/bin/python -m unittest discover -s tests
→ Ran 143 tests in 6.701s … OK
```

Executor’s earlier typo (`tests.test_defined_risk_fixed_cost_stress`) is acknowledged and corrected; current green evidence is the real module path.

### Semantics / scope (honest limits — accepted)

- Guard is **conservative research rule** (ITM short call + known dividend ≥ ratio × extrinsic), not a probability/early-exercise solver.
- Marks remain Black-Scholes / synthetic bars; fixture machinery only.
- Empty event list under optional/required-with-provider means “no known dividend,” not “missing coverage.” `None` is the coverage-missing sentinel. Correct, but callers must not confuse them.
- Visibility window is `as_of < ex_date ≤ through`; on/after ex-date the dividend is no longer “upcoming,” so risk must fire on prior bars. Conservative pre-ex path is intended.
- Collar / calendar / other short-call surfaces remain unmodeled for this boundary (collar DNA still lists `dividends_unmodeled` / `early_assignment_unmodeled`). Executor scoped to diagonal + bull-call as named by prior NEXT — acceptable; do not overclaim catalog-wide assignment realism.

## Nits (non-blocking; finalizer optional)

1. **Catalog honesty lag** — `STRUCTURE_CATALOG` diagonal / bull_call exit ladders do not yet list `early_assignment_risk` or provider-dependent limitations. Doctrine/coverage docs were updated; catalog descriptions still read as pure BS scaffold. Prefer a one-line DNA note or exit-ladder mention so evolve readers do not miss the opt-in guard.

2. **Sim-path threshold coverage is thin** — unit assessor correctly returns OTM / below-threshold reasons; sim integration only proves an extreme $100 dividend forces exit. Not claim-invalidating. Optional: one bull-call/diagonal row with ITM + dividend below extrinsic that continues under normal management.

3. **Assignment precedes profit/loss by code order** — good, but no dedicated test that when both PT and assignment would fire, reason is `early_assignment_risk`. Optional behavioral assert.

4. **NEXT scope** — inventory of honest `known_at` sources is the right completion for *this* family. Do not let it freeze unrelated open historical-proxy discovery if inventory is empty/slow; zero-input wakes may supersede with a different highest-info loop after writing the fail-closed packet.

None of these reverse PASS.

## Freedom / thrash audit

- Prior closed families (close-shock, momentum, pullback, vol-compression, multi-horizon trend-pullback, CCS vol-expansion, collar, asymmetric IC, BAC Fri7 management) were **not** reopened.
- One-date TSLL archive was **not** treated as platform stop.
- No evolve `--apply`, no hyp registration, no B-check mutation, no live/broker path.
- Choice matches orientation: simulator capability is executable and was the prior NEXT’s named class.

## Capital / readiness

- Phase: **BUILD / L0** unchanged.
- Living quality leader: **none**.
- Formal B checks: unchanged.
- Any future diagonal/bull-call candidate still needs structure, `capital_fit_usd`, 1-lot `max_loss_usd`, `max_lots`, non-vacuous dual-cost evidence, regime windows, and competitive DD — plus honest corporate-action provenance if claims depend on required mode.

## Disposition for finalizer

- **Accept** capability delta as useful durable learning.
- **Do not** invent edge, restress old proxy SHIP as newly L1-eligible, or promote statuses.
- Optional: DNA catalog honesty + one extra threshold/precedence test.
- Promote: dated outcome → wake/readiness; reusable pitfall → skill if finalizer judges worth it (“required dividend coverage is `None`, not empty list; known_at is mandatory for honesty”).
- Preserve ONE NEXT: provider inventory or fail-closed data packet.

## Phase status

Challenger phase only. Finalizer repair/verification/learning promotion, deterministic commit/integration/push/postflight, and RUN COMPLETE remain pending. Challenger did not commit, push, merge, evolve `--apply`, broker, arm, or claim completion.

MOA_CHALL_DONE

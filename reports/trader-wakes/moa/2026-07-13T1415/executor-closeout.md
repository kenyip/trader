# MOA BUILD executor closeout — 2026-07-13T1415

WAKE: recovery completed 2026-07-13 14:39 PDT
PHASE: BUILD / L0
SLEEVE: $3,000
ROLE: GPT 5.6 Sol recovery executor; only writer; Grok challenger/finalizer/integration pending
OUTCOME: CAPABILITY_ADDED / LOCKED_DENSIFIED_SESSION_TIME_PROXY_RERUN_FALSIFIED
PAPER_ONLY: true

## ORIENTATION / CHOICE

Recovery continued only the existing `2026-07-13T1415` dirty run branch after the first executor exhausted its tool budget. The scoped loop was already fixed: append-safe provenance-recorded 30-minute archives plus archived daily warmup, followed by exactly one locked PCS/CCS/IC open/midday/late train→untouched-holdout rerun. No new hypothesis, symbol, structure, DNA, gate, or holdout tuning was introduced. BUILD/L0, the empty capital path, and no-living-leader truth remain unchanged.

Hypothesis under test: for at least one of BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL and one defined-risk PCS/CCS/IC structure, a bucket selected only on chronological train remains positive, non-vacuous, sleeve-fit, and bounded on untouched holdout under both 5% adverse leg slip and $0.01 half-spread-per-leg costs after usable prior-session feature history is expanded to the retained 60-date intraday history.

Falsifier: reject unless train and untouched holdout independently pass both cost axes with n>=3, PnL>0, one-lot max loss <=$300, maximum/window DD <=$75, dense-negative windows <=5, exact ledger, and zero same-bar or same-date/session-bucket reentries.

## DID

- Preserved and directly reviewed the first executor's implementation and evidence instead of trusting its incomplete summary.
- Added stable append/deduplicate OHLCV archives with capture journals recording source, request period, capture time, downloaded/new/replaced rows, archive row/date density, and archive bounds.
- Added archived one-year daily history as warmup for regime/IV features; every intraday feature date remains strictly earlier than its market date.
- Added mixed-DST archive round-trip behavior and fail-closed invalid/nonfinite capture and metadata-source mismatch boundaries.
- Updated the locked lab to report raw archive density separately from usable feature density and to retain capture provenance.
- Preserved the already completed exactly-once locked 8-symbol × 3-structure rerun; did not rerun it during recovery.
- Reconciled coverage/doctrine and current wake/readiness surfaces to the stronger rejection.
- Registered, promoted, paper-traded, shadowed, armed, broker-accessed, committed, pushed, merged, or postflighted nothing.

## EXACT EVIDENCE / JUDGMENT

Primary immutable evidence: `reports/trader-wakes/moa/2026-07-13T1415/pcs-session-time-archive-rerun.json`.

- Decision: `REJECT_SESSION_TIME_PROXY_THIS_CYCLE`.
- Population complete: 8/8 symbols × 3/3 structures = 24/24 rows; errors 0.
- Every symbol: 780 usable 30-minute bars over 60 raw/usable market dates; 36 train dates and 24 untouched holdout dates; feature-date violations 0.
- Train dual-cost passes: 1/24. Complete train+holdout passes: 0/24.
- Sole train survivor: AAPL late `put_credit_spread`.
- Its untouched holdout had only two trades per axis: fixed `$0.01` PnL `+$6.858454559174554`; 5% slip PnL `-$10.538313351563206`. Both fail minimum density, and 5% also fails positive PnL.
- Maximum reported one-lot axis loss/capital fit: `$223.36`; observed range `$68.05`–`$223.36`, inside the `$300` hard gate.
- Every axis reports structure, `capital_fit_usd`, `max_loss_usd`, and generic `max_lots=3`; research operating posture remains exactly 1 lot and no capital seat exists.
- Maximum absolute ledger delta: `5.684341886080802e-14`.
- Same-bar reentries: 0. Same-date/session-bucket reentries: 0.

Judgment: the locked densified session-time proxy seed is falsified for this cycle more strongly than the 21-date run. Daily warmup increased usable dates without adding same-day features, but did not produce a complete train+holdout dual-cost pass. This does not universally reject session timing; it rejects this exact synthetic 7-DTE/rounded-strike/listed-Friday PCS/CCS/IC specification and cannot support L1, registration, paper, shadow, or live action.

## CLAIM CRITIQUE / BOUNDARIES

- Lookahead: direct artifact inspection records zero feature-date violations; tests establish prior-daily warmup features satisfy `feature_market_date < market_date`. Bucket selection reads train only; holdout executes only for train survivors.
- Data semantics: underlying bars and daily warmup are yfinance observations, but option marks, listed-Friday availability, and rounded strikes are Black-Scholes proxies. Appendability improves retained underlying history, not option-fill realism.
- Costs: 5% leg slip and fixed `$0.01` half-spread per leg are sensitivities, not observed historical bid/ask fills.
- Density: 60 dates is materially denser than 21, but the sole holdout evaluation contains two trades per axis and is non-affirmative. Rejection is independently decisive on minimum density and the negative 5% PnL.
- Population purity: all and only the requested PCS/CCS/IC rows completed; registry counts and statuses did not change.
- Capital: all evaluated structures are defined risk and fit the sleeve at one lot, but capital fit alone is not a seat. No living leader exists.
- Archive atomicity: each CSV and metadata write is atomic individually; no claim is made that both files commit as one cross-file transaction. Source/symbol/interval mismatches fail before mutation.
- Generated residue: deterministic 1415 preflight coverage and intermediate 1429 coverage were retained as auditable run-created snapshots; 1437/LATEST contains the claim-current coverage. No private position, auth, token, credential, raw archive, or cache file was added to the intended tracked diff.

## DIRECT VERIFICATION

Recovery reran, rather than inherited, all claim-relevant checks:

- Focused behavioral/boundary/negative-control/regression suite:
  `.venv/bin/python -m unittest tests.test_intraday_session_data tests.test_pcs_session_time_chronological_lab tests.test_pcs_expiry_grid tests.test_trader_income_coverage -v`
  → 31/31 OK.
- Platform smoke: `just platform-smoke` → `platform smoke OK`; `agentic_live` remained blocked at the Robinhood Stage1 OAuth gate.
- Full suite: `.venv/bin/python -m unittest discover -s tests -v` → 201/201 OK.
- Python syntax: `py_compile` over all changed Python and test modules → exit 0.
- Diff hygiene: `git diff --check` → exit 0.
- Direct JSON recomputation: 24 completed / 0 errors / 1 train pass / 0 complete passes; raw=usable=60 dates, 36/24 split, zero feature violations, max loss `$223.36`, ledger `5.684341886080802e-14`, and zero reentries.
- Coverage: 21 structures / 245 hypotheses / 67 evolve artifacts / no living leader.
- Complete tracked and untracked residue review found no sensitive-path or secret-content match. The raw executor session log is expected MoA audit evidence, not strategy evidence.

## DURABLE / LESSON

Future Trader can retain yfinance 30-minute and daily OHLCV history append-safely, distinguish downloaded/overlap/archive/usable density, and warm early intraday dates only from completed prior daily sessions. More usable underlying dates did not rescue this locked family; rerunning or retuning it without a materially different evidence class would be thrash.

## ONE NEXT SEED

Grok challenger audits this exact `2026-07-13T1415` executor residue and rejection for provenance integrity, leakage, cross-file archive failure modes, cost/proxy overclaim, sparse survivor holdout, generated debris, and no-living-leader consistency; no strategy rerun or DNA change before that critique.

## PHASE STATUS

Executor partial phase only. No commit, push, merge, registration, promotion, paper, shadow, arm, broker, live action, postflight, or RUN COMPLETE claim. Challenger, finalizer, and deterministic integration remain pending.

MOA_EXEC_DONE

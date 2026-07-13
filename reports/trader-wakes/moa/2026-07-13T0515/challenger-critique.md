# MOA BUILD challenger critique — 2026-07-13T0515

WAKE: 2026-07-13 ~13:40 PDT (Monday; BUILD recovery / post-RTH)
PHASE: BUILD / L0
SLEEVE: $3,000
ROLE: Grok 4.5 challenger (read-only judgment)
SCOPE: Critique executor only. No evolve --apply, no broker, no arm, no commit/push/merge, no RUN COMPLETE.

## Verdict

**PASS 8/8** — accept executor outcome: session-time capability added + exact predeclared 30-minute PCS/CCS/IC chronological dual-cost proxy seed **rejected this cycle**; no capital seat; no registration; L0 / empty capital path unchanged.

NEXT is **accepted in spirit and refined in mechanism**: denser evidence is required before any retest, but the highest-information densify path is **not** “wait until 60 brand-new market dates exist.” Raw yfinance 30m already spans **60** calendar market dates; feature readiness currently burns most of them down to **21** usable dates.

## What was challenged

Primary claims under review:
- Recovery completed a no-lookahead completed-30-minute open/midday/late PCS/CCS/IC chronological train→holdout dual-cost lab on BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL.
- Timezone-aware calendar-DTE and exit-consumes-session-bucket repairs are claim-relevant integrity fixes, not vanity.
- Exact seed decision is `REJECT_SESSION_TIME_PROXY_THIS_CYCLE` (24/24 complete; 6 train dual-cost passes; 0 all-axes passes).
- No leader / no L1 / no hyp registration / paper-only.
- ONE NEXT remains open and non-thrash.

Evidence inspected:
- `reports/trader-wakes/moa/2026-07-13T0515/meta.json`
- `reports/trader-wakes/moa/2026-07-13T0515/executor-closeout.md`
- `reports/trader-wakes/moa/2026-07-13T0515/orientation.json`
- `reports/trader-wakes/moa/2026-07-13T0515/pcs-session-time-chronological-lab.json`
- `reports/trader-wakes/2026-07-13T0515-moa-exec.md`
- concurrent RTH `reports/trader-wakes/LATEST.md` (context only; not executor evidence)
- `reports/readiness/LATEST.md`
- `reports/readiness/income-coverage-LATEST.md` (still hardcodes session-time missing)
- `.cache/platform/pcs_session_time_chronological_lab_2026-07-13T0515.json`
- `.cache/platform/intraday_underlying/2026-07-13T0515/*_60d_30m.csv`
- `trader_platform/research/intraday_session_data.py`
- `trader_platform/research/pcs_sim.py` (session buckets + exit consumes bucket)
- `scripts/pcs_session_time_chronological_lab.py`
- `tests/test_intraday_session_data.py`, `tests/test_pcs_session_time_chronological_lab.py`, `tests/test_pcs_expiry_grid.py`
- doctrine: skill `trader-self-evolution`, `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`

Independent checks (read-only):
- Lab JSON decision/population MATCH executor: `REJECT_SESSION_TIME_PROXY_THIS_CYCLE`, n_completed=24, n_train_gate_pass=6, n_all_axes_pass=0, errors=[].
- Train-pass holdout metrics re-match closeout examples exactly (BAC late PCS fixed holdout −19.44 / 5% +11.24; F open CCS fixed −5.31 / 5% +4.49; F late IC −38.74/−14.83; SOFI late PCS −15.81/−5.68; SOFI late IC fixed +16.34 / 5% −8.45; F midday PCS holdout n=1 both axes).
- Max reported axis `max_loss_usd` across all rows = **$224.61** (≤ $300). Same-bar reentries 0; same-session-bucket reentries 0; max abs ledger delta on train late BAC fixed is ~7e-15 class (JSON reports 0.0 on holdout axes).
- Raw BAC 30m CSV: **780 rows / 60 market dates** (2026-04-16 → 2026-07-13). After `build_session_frame` default `min_daily_history=20`: **273 bars / 21 market dates**. With `min_daily_history=5`: **51** market dates. Density bottleneck is feature readiness, not missing raw history.
- Focused unittest re-run this critique: `tests.test_intraday_session_data tests.test_pcs_session_time_chronological_lab tests.test_pcs_expiry_grid` → **22/22 OK**.
- Branch `trader/run-2026-07-13T0515`; executor residue uncommitted (expected partial phase). Concurrent RTH stamps dirty the tree and are out of executor scope.

## Rubric

| # | Criterion | Grade | One line |
|---|---|---|---|
| 1 | Goal progress | **PASS** | New completed-30m session-time machinery + honest dual-cost chronological reject closes a real time-axis gap without inventing edge. |
| 2 | Creativity / independence | **PASS** | Prior 0026 NEXT continued for unfinished claim-invalidating TZ work; new evidence class (session buckets), not closed daily-bar or TSLL-PCS tunnel. |
| 3 | Claim validity | **PASS** | L0 proxy/synthetic Friday-strike scope explicit; seed/cycle reject only; no L1, registration, paper, shadow, arm, or live claim. |
| 4 | Evidence / test quality | **PASS** | Real code+lab JSON+tests; metrics independently match; behavioral/boundary/negative-control coverage present (lag, TZ calendar-DTE, no-reentry, train∧holdout NC). |
| 5 | Falsification | **PASS** | Predeclared dual-cost train+holdout + absolute ml/DD/density gates; 0/24 complete passes; no DNA retune after fail. |
| 6 | Capital honesty | **PASS** | Living leader remains **none**; defined-risk only; max axis loss $224.61; no seat; operating 1-lot posture stated despite reported capacity 3. |
| 7 | Research freedom | **PASS** | Option-archive 2/3 did not freeze independent historical 30m proxy work; no new allowlist; closed daily-bar families left closed. |
| 8 | ONE NEXT / no live-shadow | **PASS** | Single densify-then-rerun NEXT kept; mechanism refined so densify uses available raw history + archive provenance rather than idle wait / retune. |

## Strengths

1. **Correct loop choice under recovery:** finish claim-invalidating timezone/calendar-DTE crash on already-chosen session-time experiment rather than reopen double-diagonal or daily-bar rejects.
2. **Integrity repairs that matter:** calendar-DTE from local dates (not naive-vs-aware subtraction); exit consumes date/session bucket so early-close cannot re-enter same bucket later that day.
3. **Conjunctive falsifier:** six train dual-cost survivors all fail untouched holdout dual-cost or density; no soft “preferred under cost” seat language.
4. **Proxy hygiene:** claim_scope, validity, and prose correctly bar observed fills, contract availability proof, and L1.
5. **Population purity:** only predeclared 8×3 rows; ranking complete; no registry mutation.
6. **Freedom audit holds:** independent historical/capability route used while observed option hist remains blocked — doctrine-correct.

## Findings (none claim-invalidating for the reject)

### F1 — Finalizer should patch stale coverage gap text (actionable hygiene)
`scripts/trader_income_coverage.py` still emits:
`time-bucket scoreboard … session-time slices missing`
despite built `intraday_session_data` + session-bucket PCS path + chronological lab + this-cycle reject.
Patch the hard-coded gap, regenerate coverage, and align `docs/INCOME_STRATEGY_COVERAGE.md` time-axis line. **Do not count this as new strategy edge.**

### F2 — NEXT refinement: density bottleneck is usable feature dates, not absent raw bars (actionable)
Executor NEXT (“archive until ≥60 market dates, then rerun once”) is directionally right on **append-safe provenance** and **no retune**, but understates current data:
- stamp-dir raw CSVs already hold **60** market dates;
- default feature pipeline yields only **21** usable dates;
- holdout therefore has only **9** dates and typically **1** window under `window_market_dates=10`, so dense-neg/window gates are weak (reject still stands on dual-cost PnL).

Merged NEXT (see `merged-next-seed.md`): promote append-safe provenance-recorded raw 30m archive; expand **usable** session dates toward available raw history without lookahead (justify/relax feature warmup or separate raw retention from feature readiness); then **one** locked rerun of the exact PCS/CCS/IC chronological dual-cost spec. Do not retune DNA on the thin holdout; do not register/promote/paper/shadow/arm/live.

### F3 — Soft capital label: reported `max_lots=3` vs operating 1-lot
`capital_fit_pcs` caps generic capacity at 3 via open-risk budget math. Every axis reports `max_lots=3` while prose says operating posture 1 lot. Optional finalizer alignment with double-diagonal lesson (`max_lots` operating vs `theoretical_max_lots`) if cheap; **not** a seat risk this cycle because nothing was promoted and ml stays ≤$224.61.

### F4 — Soft: window stress nearly vacuous on 9-date holdout
With `window_market_dates=10` and 9 holdout dates, `n_windows` is 1 for evaluated holdouts. Dense-negative≤5 cannot meaningfully fire. Rejection remains valid via dual-cost PnL/density-of-trades. On denser rerun, keep windows informative or document the floor.

### F5 — Soft: concurrent RTH “quality PCS b195f5fe” language
RTH readiness still narrates `b195f5fe` as quality PCS while capital path / living leader are empty and listed-expiry restress previously removed it from L1. Executor did not worsen this. Finalizer/readiness hygiene: keep “historical reference only / no living leader” wording when touching readiness NEXT.

## Capital / leader board

- Living quality leader: **none**
- Capital path: **empty**
- This seed: research/proxy only; max axis loss $224.61; structures PCS/CCS/IC defined-risk
- `b195f5fe`: historical context only, not a seat
- Absolute gates used: ml≤$300, DD/window DD≤$75, dual-cost train∧holdout, min n≥3, dense-neg≤5 (window weak this cycle)

## Disposition for finalizer

| Item | Disposition |
|---|---|
| Exact seed reject `REJECT_SESSION_TIME_PROXY_THIS_CYCLE` | **ACCEPT** |
| Session-time machinery + TZ/bucket integrity repairs | **ACCEPT** |
| No registration / no paper / no shadow / no arm / no live | **ACCEPT** |
| Coverage gap “session-time missing” | **REPAIR** (F1) |
| Executor NEXT wording | **REFINE** to merged densify-usable-history seed (F2) |
| max_lots / window vacuity | **OPTIONAL** soft repair if cheap (F3/F4) |
| Full suite / learning-promotion / integration | Finalizer + deterministic gate only |

## Phase status

Challenger partial phase only. No commit, push, merge, branch switch, postflight, or RUN COMPLETE claim.

MOA_CHALL_DONE

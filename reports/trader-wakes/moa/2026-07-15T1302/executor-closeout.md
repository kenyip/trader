# MOA BUILD executor closeout — 2026-07-15T1302

PHASE: BUILD / L0 discovery
SLEEVE_USD: 3000
ROLE: GPT 5.6 Sol executor; only writer
SESSION: postclose
PAPER_ONLY: true
OUTCOME: `FAMILY_CLOSED`
STRATEGY ADVANCEMENT: false; `F0_MECHANISM -> F0_MECHANISM`

## Strategy decision charter

- Economic mechanism: overlapping bullish/neutral put-credit-spread signals create hidden concentration; admitting at most one open one-lot position globally with an outcome-free symbol priority should preserve per-trade expectancy while reducing marked portfolio drawdown.
- Candidate/family: candidate `ONE_RISK_UNIT_CADENCE_PCS_V1` in canonical family `ONE_RISK_UNIT_CADENCE_POLICY_F0`; `PORTFOLIO_CADENCE_CONCENTRATION_CONTROL` is the class tag. Frozen symbols are `AAPL, AMD, BAC, F, PLTR, SMCI, SOFI, TSLL`; structure is one-lot 14-DTE, $2-wide put credit spread; entry features are lagged one completed bar; only `bull` and `neutral` regimes enter; ordinary simulator management remains unchanged. The uncapped stream and capped stream use the same independently generated trades within each cost axis. Same-day ties use fixed outcome-free priority; the prior risk unit's exit date is consumed.
- Funnel: `F0_MECHANISM`; target was only `F0_MECHANISM -> F1_TRAIN`. The first 60% of a common panel was train; 282 later rows were reserved without option simulation or outcome metrics.
- Predeclared falsifier: close unless both 5% adverse-price and fixed-$0.01-per-leg axes independently have at least 20 admitted trades, positive capped after-cost PnL, marked maximum drawdown at most $75, one-lot max loss at most $300, one risk unit and no cluster overlap, positive uncapped expectancy, capped expectancy retention at least 75%, at least 25% marked-drawdown reduction, exact ledger reconciliation, and complete integrity.
- Exact decision: `FAMILY_CLOSED`.

The original pre-action charter is `reports/trader-wakes/moa/2026-07-15T1302/strategy-charter.md`.

## Executor judgment

The one-global-risk-unit cadence reduced concentration and drawdown, but it did not make the frozen signal stream economically or capital-path valid on train.

| cost axis | raw / admitted / rejected | uncapped PnL / marked DD | capped PnL / marked DD | expectancy retention | DD reduction | decision |
|---|---:|---:|---:|---:|---:|---|
| 5% adverse price | 39 / 31 / 8 | -$313.11 / $484.50 | -$165.80 / $330.51 | unavailable; uncapped expectancy negative | 31.78% | fail |
| fixed $0.01 per leg | 181 / 81 / 100 | +$846.24 / $596.54 | +$646.77 / $288.63 | 170.79% | 51.62% | fail |

The 5% axis fails the economic premise: capped total PnL is negative, capped average trade is -$5.35, and uncapped expectancy is also negative. Both axes fail the capital-seat drawdown boundary by wide margins: capped marked drawdown is $330.51 and $288.63 versus the predeclared $75 maximum. The fixed-cost axis shows that the outcome-free cadence can improve the path while preserving expectancy, but the residual drawdown is still 3.85 times the absolute budget. Cost-axis disagreement is material, not a near-pass.

Dominant failure mechanism: one-position admission reduces simultaneous exposure but cannot repair cost-fragile negative expectancy or the tail path of the underlying signal family. Do not rescue this result by inspecting the reserved holdout, changing symbol priority, relaxing the $75 drawdown boundary, or rerunning the same signal DNA with nearby risk-unit counts.

Canonical evidence:
- `reports/trader-wakes/moa/2026-07-15T1302/one-risk-unit-cadence.json`
- Finalizer-regenerated SHA-256: `1cc2585ec09c70e06acd6b40af22f4e84b1a007c3c0f5934fbb4ccd03d1bad18`; strategy metrics are unchanged, while canonical candidate/class labels and invocation semantics are now explicit.
- Lab: `scripts/one_risk_unit_cadence_lab.py`
- Tests: `tests/test_one_risk_unit_cadence_lab.py`

## Evidence validity and critique

- Chronology: each symbol uses `entry_signal_lag_bars=1`; all first entries occur after the symbol's first train row. The policy consumes an accepted trade's exit date, so a later signal may enter only on a later market date.
- Partition: 705 common rows, 423 train rows from 2023-09-21 through 2025-05-29, and 282 reserved rows from 2025-05-30 through 2026-07-15. `holdout_option_pricing_calls=0`, `holdout_trade_rows_written=0`, `holdout_metrics=null`, and `holdout_outcomes_read=false`.
- Costs: 5% is an adverse proxy-price sensitivity and fixed $0.01 is per option leg; neither is an observed historical fill model. Both are labeled Black-Scholes/listed-Friday L0 proxies.
- Path: drawdown is close-to-close daily marked equity, including open trades, with zero as the initial peak. Terminal marked equity exactly reconciles to realized trade PnL on both streams and axes.
- Population: the configured eight-symbol population completed with no simulation errors. Effective signal density is uneven: the 5% axis has signals only on AMD, PLTR, SMCI, and TSLL; the fixed axis has none on F or SOFI and only two on BAC. Results therefore do not generalize to a balanced cross-sectional portfolio.
- Policy purity: admission reads entry date, exit date, fixed symbol priority, and cluster only; changing PnL cannot change accepted keys. The global one-risk-unit rule makes the cluster cap redundant, so this result closes the one-global-unit policy only; it is not evidence against a correlation-only cap that permits multiple non-correlated positions.
- Contract realism: expirations are listed-Friday abstractions and strikes/marks are Black-Scholes proxies over historical underlying features. Observed contract availability, bid/ask fills, assignment/dividends, liquidity, and intraday excursions are not claimed.
- Reproduction: the lab refreshes if stale and then re-reads the persisted cache snapshot. A second independent invocation matched the complete substantive JSON after excluding only `generated_at`.
- Living comparison: readiness has no living quality leader and the capital path is empty. This close creates neither.

## Search information versus strategy progress

Search information: Trader added a deterministic reusable portfolio-cadence lab that generates fixed PCS signals, applies outcome-free one-risk-unit admission, builds daily marked portfolio curves, enforces strict train/holdout separation, records source hashes and explicit capital labels, and tests tie, exit-date, outcome-independence, ledger, and negative-stream boundaries. The dependent strategy experiment ran and closed in the same wake.

Strategy progress: none. Canonical family `ONE_RISK_UNIT_CADENCE_POLICY_F0` remains at F0 and its exact candidate `ONE_RISK_UNIT_CADENCE_PCS_V1` one-global-unit/fixed-priority PCS implementation is quarantined from unchanged reruns. Reopening requires a materially different policy mechanism, such as a genuine correlation-only allocator with multiple permissible non-correlated units, and a newly predeclared experiment.

## Capital / readiness / authority

- Structure: one-lot defined-risk `put_credit_spread`, 14 DTE, $2 width.
- `capital_fit_usd=204.593614387283`.
- One-lot `max_loss_usd=204.593614387283` worst observed structural proxy bound.
- `max_lots=1` operating cap.
- No L1, capital seat, B-check, registry, paper, shadow, funding, broker, arm, or live transition.
- `reports/readiness/LATEST.md` is intentionally unchanged because phase and B checks did not change. Living leader remains none; capital path remains empty.
- If accepted, active-epoch no-advance streak becomes 2, so the next BUILD wake must pivot to a materially different economic mechanism/evidence class.

Freedom audit: Trader accepted the prior NEXT only after independently verifying it was the highest-information open route and narrowed it to a claim-valid one-global-risk-unit test; neither the caller, an allowlist, a stale leader, nor TSLL familiarity selected the outcome.

## Verification

- Focused behavioral/boundary/negative-control plus PCS cost/lag regression: `.venv/bin/python -m unittest -v tests.test_one_risk_unit_cadence_lab tests.test_pcs_expiry_grid tests.test_defined_risk_fixed_cost` -> 25/25 `OK` after the source-materialization repair.
- Changed-file compile: `.venv/bin/python -m compileall -q scripts/one_risk_unit_cadence_lab.py tests/test_one_risk_unit_cadence_lab.py` -> exit 0.
- Exact dependent experiment: `FAMILY_CLOSED`; integrity complete; 16 train backtest invocations (=2 axes × 8 symbols), zero holdout backtest invocations/rows/metrics.
- Independent unchanged-source reproduction: complete substantive payload equality after excluding only `generated_at`.
- Final post-repair full suite: `.venv/bin/python -m unittest discover -s tests -v` -> 294/294 `OK`.
- Platform smoke: `platform smoke OK`; `agentic_live` remained blocked.
- Coverage refresh: 21 catalog structures / 246 hypotheses / 70 evolve artifacts / living leader none; `reports/readiness/income-coverage-2026-07-15T1314.md` written.

## One next seed

`MONTHLY_OPEX_POST_EXPIRY_DRIFT_F0`: next zero-input BUILD wake must pivot away from cadence and closed daily-selector DNA. Predeclare a train-only third-Friday monthly-OPEX event study on liquid broad indexes, using next-session entry, a fixed short hold, and same-month non-OPEX-Friday controls chosen without outcomes; require non-vacuous positive after-cost drift, positive paired excess, and a positive uncertainty lower bound before any defined-debit option pricing or holdout read. Reserve holdout; keep L0; no paper/shadow/arm/live.

## Phase boundary

Executor evidence is partial. Grok 4.5 challenge, GPT 5.6 Sol finalization, deterministic staging/commit/integration/push, remote equality, and the completion receipt remain required. No commit, push, merge, branch switch, broker action, or `RUN COMPLETE` claim occurred.

MOA_EXEC_DONE

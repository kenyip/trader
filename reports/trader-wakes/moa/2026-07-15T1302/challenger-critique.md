# MOA challenger critique — 2026-07-15T1302 (Grok 4.5)

PHASE: BUILD / L0. Sleeve USD 3000. PARTIAL critique phase only.
Roles: read-only judgment. No evolve --apply, no broker, no arm, no commit/push/merge, no RUN COMPLETE.

## Executive disposition

**PASS WITH NITS** on strategy substance.

Accept executor decision `FAMILY_CLOSED` for exact family `ONE_RISK_UNIT_CADENCE_POLICY_F0` (implementation label `ONE_RISK_UNIT_CADENCE_PCS_V1` / portfolio class `PORTFOLIO_CADENCE_CONCENTRATION_CONTROL`) at `F0_MECHANISM → F0_MECHANISM`. Strategy advancement: **false**. Search information: **yes**.

Independent checks (this challenger session):
- Canonical evidence: `reports/trader-wakes/moa/2026-07-15T1302/one-risk-unit-cadence.json`
- Live SHA-256: `76206f14b58ae6a00b658acd7ce7cc4053c7856b50be67eddced329bad0339ea` (matches executor)
- `decision=FAMILY_CLOSED`; `strategy_advanced=false`; funnel `F0_MECHANISM → F0_MECHANISM`
- Config seed: `long_dte=14`, `spread_width=2.0`, catalog PCS `config_seed` + `entry_signal_lag_bars=1` (not 21-DTE)
- Partition: 705 common rows; train 423 (`2023-09-21`–`2025-05-29`); holdout blueprints 282 unread (`holdout_option_pricing_calls=0`, `holdout_trade_rows_written=0`, `holdout_metrics=null`, `holdout_outcomes_read=false`)
- Cost axes:
  - `pct_5`: raw 39 / admitted 31; uncapped PnL `-$313.11` / marked DD `$484.50`; capped PnL `-$165.80` / DD `$330.51`; expectancy retention null (uncapped expectancy negative); DD reduction 31.78%; **fail**
  - `fixed_001`: raw 181 / admitted 81; uncapped `+$846.24` / DD `$596.54`; capped `+$646.77` / DD `$288.63`; expectancy retention 170.79%; DD reduction 51.62%; **fail** on `$75` DD only among economic gates
- Dominant failure string: `pct_5:after_cost_positive,pct_5:marked_dd_le_75,pct_5:positive_uncapped_expectancy,pct_5:expectancy_retention_ge_75pct,fixed_001:marked_dd_le_75`
- Capital labels: one-lot defined-risk PCS; `capital_fit_usd=max_loss_usd=204.593614387283`; `max_lots=1`
- Integrity: lag boundaries ok; population complete; priority outcome-free; `train_option_pricing_calls=16` (= 2 axes × 8 symbols sim invocations, not per-trade marks)
- Focused lab tests re-run: **5/5 OK** (`tests/test_one_risk_unit_cadence_lab.py`) — fixed-priority tie, exit-date consume, outcome-independence, negative-stream fail-close, marked-ledger reconcile
- Active epoch: `2026-07-15-viable-path` (`started_stamp=2026-07-15T0024`); prior integrated epoch no-advance = 1 (`TSLL_TSLA_5D_TRACKING_SHORTFALL_REBOUND`); accepting this close → active-epoch no-advance **2** → **strategy_pivot_required**
- Living leader / capital path: none / empty
- Executor-claimed full suite 294/294 and coverage refresh **not** re-run here; finalizer must re-verify independently

## Canonical evidence (challenger-inspected)

| Item | Path / value |
|---|---|
| Artifact | `reports/trader-wakes/moa/2026-07-15T1302/one-risk-unit-cadence.json` |
| SHA-256 | `76206f14b58ae6a00b658acd7ce7cc4053c7856b50be67eddced329bad0339ea` |
| Lab | `scripts/one_risk_unit_cadence_lab.py` |
| Tests | `tests/test_one_risk_unit_cadence_lab.py` |
| Charter | `reports/trader-wakes/moa/2026-07-15T1302/strategy-charter.md` |
| Outcome | `FAMILY_CLOSED` |
| Funnel | `F0_MECHANISM` → `F0_MECHANISM` |
| Closed family (canonical) | `ONE_RISK_UNIT_CADENCE_POLICY_F0` |
| DNA | catalog PCS seed, **14-DTE** / $2 width / lag=1 / bull+neutral only via seed; fixed 8 symbols |
| Holdout | unread; no option sim |
| Evidence level | `L0_DISCOVERY_BS_PROXY` |
| Living leader / seat | none / none |
| Challenger re-run tests | 5/5 OK |
| Executor-claimed full suite | 294/294 (finalizer re-verify) |

## Rubric

### 1. Strategy charter — PASS
Economic mechanism (global one-open risk unit reduces correlated PCS concentration without destroying after-cost expectancy), candidate/family scope, F0 train-only target, predeclared dual-cost multi-gate falsifier, and exact advance-or-close decision are explicit in charter + JSON + closeout. One closed outcome: `FAMILY_CLOSED`.

### 2. Strategy vs operations — PASS
New portfolio-cadence lab + tests are capability, but the dependent frozen experiment ran to an advance-or-close decision in the same wake. Capability is correctly labeled search information, not strategy advancement. Not capability-only theater; not a fake `BLOCKER_REMOVED_AND_RETESTED` without retest.

### 3. Goal progress — PASS
Honest F0 close of a novel portfolio-policy mechanism improves later paper odds by rejecting “just cap concurrency” as a rescue for a cost-fragile / high-path-DD PCS stream. Discriminating evidence: cadence can cut DD and even raise per-trade expectancy on fixed-$0.01, yet residual DD remains ~3.8× the absolute budget and 5% remains expectancy-negative. No false advance. Stand-aside/close is capital-first correct.

### 4. Creativity and independence — PASS
Prior NEXT `ONE_RISK_UNIT_CADENCE_POLICY_F0` was executed with justification (open route after tracking-shortfall close; novel evidence class vs closed daily selectors / cross-section / VRP / TOM / session-time). Not a familiar single-name TSLL PCS retune. Explicitly does **not** claim against a correlation-only multi-unit allocator (global one-unit makes cluster cap redundant) — scope honesty is good. After accept, epoch no-advance = 2 forces pivot; executor’s OPEX seed respects that.

### 5. Claim validity — PASS WITH NITS
Prerequisites match the experiment: historical underlying + Black-Scholes/listed-Friday proxies; dual labeled cost sensitivities; train before holdout; no observed fills, L1, registry, paper, shadow, arm. Capital shape stated. Population imbalance (5%: only AMD/PLTR/SMCI/TSLL fire; fixed: F/SOFI zero, BAC two) is disclosed and correctly blocks balanced-portfolio generalization.

**Nits (non-blocking; finalizer must repair residue):**
- **DTE mislabel:** charter + JSON + catalog seed are **14-DTE**; executor closeout / `2026-07-15T1302-moa-exec.md` / current LATEST prose say **21-DTE**. Repair all living residual surfaces to 14-DTE. Do not invent a 21-DTE claim.
- **Name drift:** canonicalize family `ONE_RISK_UNIT_CADENCE_POLICY_F0`; optional candidate `ONE_RISK_UNIT_CADENCE_PCS_V1`; treat `PORTFOLIO_CADENCE_CONCENTRATION_CONTROL` as class tag only.
- **pricing_calls semantics:** `16` = axis×symbol backtest invocations. Keep that label; do not imply only 16 option marks.

Discovery-bar note: the predeclared `$75` marked-DD gate is the capital-seat absolute used as an F0 policy gate. Discovery bar would allow looser risk thresholds for pure F0→F1 signal claims, but **5% after-cost PnL and uncapped expectancy already fail** independently of the DD gate, so `FAMILY_CLOSED` remains forced under any honest discovery economic premise for this dual-axis design. Do not reopen by relaxing only the DD bound.

### 6. Evidence and test quality — PASS WITH NITS
Real tools/sims with cited paths; SHA verified; holdout unread verified; dual axes evaluated; integrity and ledger gates present. Focused tests cover the right policy boundaries (priority, exit consume, outcome-independence, negative stream, ledger).

Nits:
- Tests do not yet assert dual-axis conjunction (both axes must pass) or an explicit unread-holdout / no-holdout-pricing lab boundary at the payload level. Prefer adding these as cheap negative controls in finalizer if cheap; not claim-invalidating.
- Do not overclaim full-suite 294/294 without independent finalizer re-run.
- Signal density imbalance is reported but not regression-tested as a population-purity warning flag; optional.

### 7. Falsification — PASS
Predeclared multi-gate falsifier fires clearly. Dominant failure is correctly **cost-fragile negative expectancy (5%) plus residual path DD on both axes**, not integrity or lag. Quarantine exact one-global-unit / fixed-priority PCS implementation and nearby risk-unit-count / priority / budget relaxations. Correct ban on holdout peek. Explicit reservation of a **correlation-only multi-unit** allocator as untested and reopenable only as a new predeclared mechanism — accept that boundary.

### 8. Capital honesty — PASS
No living leader, no B-check, no L1/seat. One-lot defined-risk labels present and fit `$300` max-loss gate (`~$204.59`). Marked portfolio DD far above `$75` even when capped. No shadow/live/arm language. Readiness correctly left unchanged by executor for phase/B checks.

### 9. Research freedom — PASS
Did not freeze on observed-option archive density. Used independent historical-proxy portfolio route. Did not reopen quarantined families. No unnecessary allowlist tunnel. Cluster-only multi-unit left open rather than falsely closed.

### 10. ONE highest-information NEXT — PASS (with tight merge)
Executor seed `MONTHLY_OPEX_POST_EXPIRY_DRIFT_F0` is a valid pivot after no-advance 2: calendar event / index-session mechanism, not cadence retune and not reopening closed monthly **cross-section** HV/momentum or SPY **TOM first-session** families. Merged seed below tightens quarantine boundaries and requires underlying train gates before any option pricing.

## Material findings for finalizer

**Accept**
1. `FAMILY_CLOSED` F0→F0; no strategy advancement.
2. Exact one-global-unit / fixed-priority catalog-PCS cadence quarantined from unchanged reruns.
3. Search information: reusable portfolio admission + marked equity + train/holdout + dual-cost lab.
4. Capital path empty; leader none; L0 proxy only.
5. Active-epoch no-advance becomes **2**; pivot required next wake.
6. Merged NEXT: `MONTHLY_OPEX_POST_EXPIRY_DRIFT_F0` (refined).

**Repair before integration**
1. Replace every **21-DTE** claim for this family with **14-DTE** (exec report, LATEST residual, INDEX residual, any compounding prose).
2. Canonical family/candidate naming as above.
3. Independently re-run focused lab tests + full suite; do not reuse executor counts alone.
4. On integration, set readiness next strategy action to merged OPEX seed; active-epoch streak **2**; `strategy_pivot_required=true`; burst-stop false.
5. Optional but preferred: dual-axis conjunction + holdout-unread payload tests.

**Reject**
- Reopening via holdout inspection, priority retune, multi-unit count nearby knobs, or DD-gate-only relaxation.
- Claiming capital-seat / L1 from fixed-cost expectancy retention or DD reduction alone.
- Treating cluster-cap multi-unit as already falsified.
- Claiming balanced 8-name portfolio edge from imbalanced signal density.

## Disposition line

`PASS WITH NITS` — accept `FAMILY_CLOSED` for `ONE_RISK_UNIT_CADENCE_POLICY_F0` (14-DTE catalog PCS, one global risk unit); repair DTE/name residue; pivot NEXT to monthly OPEX event study.

PARTIAL phase only. Finalizer owns verification, learning promotion, staging, and integration.

MOA_CHALL_DONE

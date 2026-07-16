# BUILD strategy-convergence scoreboard — 2026-07-16T0057

Primary question: **are the new runs better toward a living strategy?**
Uses the machine-enforced strategy-run outcome contract (`compounding.json` schema v2;
legacy schema v1 remains readable). Operational wake completion and research-process
scores are **not** strategy closeness. See `docs/BUILD_PROGRESS_AND_CONFIDENCE.md`.

## Strategy-convergence scorecard

- Search epoch: **TSLL_OBSERVED_TERM_CARRY_DIAGONAL_V1** (status `completed`, started_stamp `2026-07-15T2152`)
- Stamps scored: **12** (complete **10**)
- Strategy advances (BETTER): **1** · rate **10%** of complete
- INFORMATIVE_BUT_NOT_CLOSER: **9** · INVALID_THRASH: **2**
- Living candidates: **0** (none)
- Furthest living funnel stage: **—**
- Consecutive no-advance streak (**configured epoch**): **3**
- Historical no-advance streak (all integrated, context only): **9**
- Pivot/stop state: **strategy_burst_stop_required** (pivot≥2=True, burst-stop≥3=True)

### Per-run strategy verdicts

| stamp | verdict | advanced | outcome | funnel | scope | process_score* |
|---|---|---:|---|---|---|---:|
| `2026-07-15T1515` | **INVALID_THRASH** | no | BLOCKER_REMOVED_AND_RETESTED | F0_MECHANISM→F1_TRAIN | MULTINAME_BREAKOUT_BULL_CALL_14D_V1 /… | 0 |
| `2026-07-15T1606` | **BETTER** | yes | STRATEGY_ADVANCED | F1_TRAIN→F2_UNTOUCHED_HOLDOUT | MULTINAME_BREAKOUT_BULL_CALL_14D_V1 /… | 5 |
| `2026-07-15T1648` | **INFORMATIVE_BUT_NOT_CLOSER** | no | FAMILY_CLOSED | F2_UNTOUCHED_HOLDOUT→F2_UNTOUCHED_HOLDOUT | MULTINAME_BREAKOUT_BULL_CALL_14D_V1 o… | 3 |
| `2026-07-15T1747` | **INFORMATIVE_BUT_NOT_CLOSER** | no | FAMILY_CLOSED | F0_MECHANISM→F0_MECHANISM | POST_SHOCK_RANGE_COMPRESSION_IRON_BUT… | 3 |
| `2026-07-15T1829` | **INFORMATIVE_BUT_NOT_CLOSER** | no | FAMILY_CLOSED | F0_MECHANISM→F0_MECHANISM | POST_EARNINGS_INFORMATION_RESOLUTION_… | 3 |
| `2026-07-15T1912` | **INFORMATIVE_BUT_NOT_CLOSER** | no | BLOCKER_REMOVED_AND_RETESTED | F0_MECHANISM→F0_MECHANISM | MULTINAME_NO_RECENT_DOWNSHOCK_PCS_21D… | 4 |
| `2026-07-15T2007` | **INFORMATIVE_BUT_NOT_CLOSER** | no | FAMILY_CLOSED | F0_MECHANISM→F0_MECHANISM | LOW_DOWNSIDE_SEMIVARIANCE_ETF_PCS_21D… | 3 |
| `2026-07-15T2045` | **INFORMATIVE_BUT_NOT_CLOSER** | no | BLOCKER_REMOVED_AND_RETESTED | F0_MECHANISM→F0_MECHANISM | Exact SPY_INDEX_THETA_CARRY_PCS_21D_V… | 4 |
| `2026-07-15T2152` | **INFORMATIVE_BUT_NOT_CLOSER** | no | EVIDENCE_WAIT | F0_MECHANISM→F0_MECHANISM | Exact TSLL_OBSERVED_TERM_CARRY_DIAGON… | 2 |
| `2026-07-15T2254` | **INFORMATIVE_BUT_NOT_CLOSER** | no | FAMILY_CLOSED | F0_MECHANISM→F0_MECHANISM | Exact BROAD_SECTOR_BREADTH_THRUST_SPY… | 3 |
| `2026-07-15T2344` | **INFORMATIVE_BUT_NOT_CLOSER** | no | FAMILY_CLOSED | F0_MECHANISM→F0_MECHANISM | Exact CROSS_SECTION_RESIDUAL_REVERSAL… | 3 |
| `2026-07-16T0029` | **INVALID_THRASH** | no | BLOCKER_REMOVED_AND_RETESTED | F2_UNTOUCHED_HOLDOUT→F2_UNTOUCHED_HOLDOUT | Exact MULTINAME_BREAKOUT_BULL_CALL_14… | 0 |

Verdict definitions:

- **BETTER** — independently declared/valid strategy funnel advancement
  (`STRATEGY_ADVANCED`, advancing retest, or legacy `CANDIDATE`).
- **INFORMATIVE_BUT_NOT_CLOSER** — valid family closure, evidence wait, non-advancing
  retest, or legacy informative non-advance (capability/repair/falsify). Search
  information only — **not closer to a living strategy seat**.
- **INVALID_THRASH** — incomplete, contract-invalid, or forbidden loop repetition
  without new novelty.

## Secondary context (research-process / capability — not strategy closeness)

- Avg research-process score (complete): **3.30 / 5**
- High process-score runs (≥4): **3** · Low (≤2): **1**
- These counts measure tooling, falsification density, and operational residue.
  A window of **4+ capability runs with strategy_no_advance is still zero strategy advance.**

| stamp | process_score | progress_types | exits | models |
|---|---:|---|---|---|
| `2026-07-15T1515` | 0 | failed_or_incomplete | None/None | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T1606` | 5 | delta_candidate, delta_repair, delta_stop_rule, strategy_advanced | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T1648` | 3 | delta_capability, delta_falsification, delta_repair, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T1747` | 3 | delta_capability, delta_falsification, delta_repair, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T1829` | 3 | delta_capability, delta_falsification, delta_repair, delta_stop_rule, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T1912` | 4 | delta_capability, delta_falsification, delta_repair, delta_stop_rule, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T2007` | 3 | delta_capability, delta_falsification, delta_repair, delta_stop_rule, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T2045` | 4 | delta_capability, delta_falsification, delta_repair, delta_stop_rule, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T2152` | 2 | delta_evidence, delta_repair, delta_stop_rule, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T2254` | 3 | delta_capability, delta_falsification, delta_stop_rule, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-15T2344` | 3 | delta_capability, delta_falsification, delta_stop_rule, strategy_no_advance | 0/0 | gpt-5.6-sol→grok-4.5 |
| `2026-07-16T0029` | 0 | failed_or_incomplete | 0/0 | gpt-5.6-sol→grok-4.5 |

## Real-trade confidence (manual ladder)

- **L0 BUILD** — current unless L1 evidence appears
- **L1 sim edge** — non-vacuous after-cost + B3 density + competitive ml/dd
- **L2 paper B6** — multi-session open/manage/close
- **L3 shadow B7** — propose→risk→log window
- **L4 first real $** — Ken fund + arm + 1-lot only

Strategy-convergence leads; process plumbing is secondary. **L0 for live money**
until a BETTER advance survives L1 gates + B6.

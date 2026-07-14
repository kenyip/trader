# BUILD progress + real-trade confidence

**Audience:** Ken monitor / Jarvis support. Trader still owns free exploration.
**Updated:** 2026-07-14

## What one dual-lab run is *for*

One BUILD MoA (Sol executor → Grok challenger) should close **exactly one strategy-run outcome**
under the machine-enforced contract (`compounding.json` schema v2):

| Outcome | Strategy-convergence meaning |
|---|---|
| **STRATEGY_ADVANCED** | Named candidate moved ≥1 funnel stage with claim-appropriate evidence → **BETTER** |
| **FAMILY_CLOSED** | Mechanism decisively falsified; unchanged reruns quarantined → **INFORMATIVE_BUT_NOT_CLOSER** |
| **BLOCKER_REMOVED_AND_RETESTED** | Repair + in-wake retest to advance **or** close → **BETTER** only if retest advanced |
| **EVIDENCE_WAIT** | Next discriminating test truly blocked on unavailable evidence → **INFORMATIVE_BUT_NOT_CLOSER** |

Capability/tooling/tests/clean integration alone are **search information**, not strategy progress.
Legacy schema v1 outcomes remain readable history (`CANDIDATE` = advance; `CAPABILITY` /
`REPAIRED` / `FALSIFIED` / `DIMINISHING_RETURNS` = non-advance).

Funnel: `F0_MECHANISM` → `F1_TRAIN` → `F2_UNTOUCHED_HOLDOUT` → `F3_ROBUST_PAPER_PLAN` → `F4_OBSERVED_PAPER`.

## Primary scoreboard: strategy-convergence

Command: `.venv/bin/python scripts/trader_build_progress.py [--limit N] [--write]`

Leads with the answer to **"are the new runs better?"**:

| Field | Meaning |
|---|---|
| **Strategy advances (BETTER)** | Count/rate of independently declared valid funnel advancements |
| **INFORMATIVE_BUT_NOT_CLOSER** | Valid family closure / evidence wait / non-advancing retest / legacy informative non-advance |
| **INVALID_THRASH** | Incomplete, contract-invalid, or forbidden loop repetition without new novelty |
| **Living candidates** | Advanced scopes not later closed |
| **Furthest living funnel stage** | Max stage among living candidates |
| **Consecutive no-advance streak** | Integrated history streak without STRATEGY_ADVANCED / legacy CANDIDATE |
| **Pivot/stop state** | `none` / `strategy_pivot_required` (≥2) / `strategy_burst_stop_required` (≥3) |

Per-run verdicts:

| Verdict | Requires |
|---|---|
| **BETTER** | `strategy_advanced(...)` true from the compounding contract |
| **INFORMATIVE_BUT_NOT_CLOSER** | Valid non-advancing strategy outcome (see table above) |
| **INVALID_THRASH** | Incomplete dual, missing/invalid handoff, or same `loop_signature` with no new novelty |

**Rule:** a board full of capability/repair process scores with every row `strategy_no_advance`
is **zero strategy advance**, not "high-value progress toward a trade."

## Secondary context: research-process / capability score (0–5)

Kept only as **clearly labeled secondary context**. It measures tooling, falsification density,
and operational residue — **never strategy closeness**.

| Score | Research-process meaning (not strategy) |
|---:|---|
| 0 | Failed / incomplete |
| 1 | Re-stated known facts / stop only |
| 2 | Thin sims / evidence wait residue |
| 3 | Closed falsify loop or thin tool improvement |
| 4 | Material capability/repair or full quality retest without stage advance |
| 5 | Strategy advance **or** advancing retest (also BETTER) |

Historical P0–P4 prose labels (sim class / axis scoreboard / quality falsify / discovery yield)
remain useful for pre-compounding stamps only.

## Confidence ladder for real trades (Ken gate)

Real trades need **Ken arm** even when trader is “happy.” Trader happiness ≠ permission.

### L0 — BUILD only (current)
- Sims + research; paper ledger optional
- Confidence for **live**: **none**

### L1 — Research confidence (sim edge)
All required:

1. Defined-risk DNA with **non-vacuous** after-cost result (5% slip n≥ few trades, not soft-null / zero-trade “hold”)
2. B3 regime soft-hold with **non-sparse** trade density
3. Window max_dd / 1-lot ml competitive with or better than quality leader
4. At least **one** structure class fully exercised (PCS is closest)
5. Challenger PASS on the readiness claim (not just “more hyps”)

→ Confidence: **sim-only**. Still **no real money.** Requires a BETTER funnel advance that survives these gates — not wake volume.

### L2 — Paper trading confidence (B6)
On top of L1:

1. Multi-session live-clock paper: open → manage → close (or stand-aside with reasons) across **≥10 RTH sessions** or **≥5 completed round-trips**
2. Realized paper PnL / max DD within risk limits for $3k sleeve
3. Kill switch + risk governor exercised once in paper

### L3 — Shadow confidence (B7)
On top of L2: shadow propose→risk→log window with no silent failures / no authority creep.

### L4 — First real-trade confidence (tiny)
Funded account + explicit Ken arm + 1-lot only + written kill criteria.

### What we will *not* use as confidence
- Dual-lab count, hyp count, or SHIP count alone
- Research-process / capability score ≥4 with zero BETTER advances
- Soft `cost_hold=true` with losses or zero trades
- Single full-history SHIP without B3+B4
- “Sim exists” without after-cost survival
- Challenger 8/8 on a *research* wake (grades the loop, not live readiness)
- Operational `RUN COMPLETE` without strategy-run advancement

## Monitor checklist (Jarvis after each dual)

1. Stamp / exits / models / complete?
2. **Strategy verdict** BETTER / INFORMATIVE_BUT_NOT_CLOSER / INVALID_THRASH
3. Living candidates + furthest funnel + no-advance streak / pivot-stop
4. Did any DNA approach L1? (Y/N + why) — only relevant after BETTER
5. Secondary research-process residue (capability/repair) — labeled, not lead
6. B6/B7/funding still blocked?
7. Trader NEXT seed (support only — don’t override unless live-gate)

## Commands

```bash
.venv/bin/python scripts/trader_build_progress.py --limit 8
.venv/bin/python scripts/trader_build_progress.py --write
.venv/bin/python scripts/trader_build_monitor.py --write
just trader-income-coverage
just trader-build-lab   # zero-input BUILD; Trader chooses the loop
# after runs:
ls reports/trader-wakes/moa/
cat reports/readiness/build-progress-LATEST.md | head -80
```

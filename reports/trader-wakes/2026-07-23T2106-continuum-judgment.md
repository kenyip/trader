# WAKE — 2026-07-23T2106 continuum judgment / coach

WAKE: 2026-07-23 ~21:06 PDT / ~00:06 ET Jul 24 (evening coach)  
PHASE: PAPER  
SLEEVE: 3000 plan · cash≈500 · live_armed=false  
CHOSE: **Fix EDGE thrash that survived prior coach** — campaign still 300s on cadence; selector burning B3/B4 on NFLX CCS score-twins  
OUTCOME: search-system improvement (not STRATEGY_ADVANCED / not pack-grade)

## Orient

- EDGE: worker ON (~21h, cycles≈470+, hb fresh); evolve/stress green
- Latest cycles: walls 370–690s; campaign cadence hits still **rc=124 TIMEOUT 300s** with run log stuck at `start` (learn_tick before fast path)
- Stress batch truth: TSLL/CCL/NFLX CCS vanity correctly rejected (NULL@0 / B3 dens / B4 −508); shortlist leaders stable dens0 **AAL + BAC** SHIP@5%
- Thrash: NFLX CCS **32 fails / 0 ok in 6h**; clone groups e.g. (n=2,pnl=46.2)×13 hyp_ids; selector still queued twin score 475.65 n=46 pairs
- ROBOT: paper **3/3** sessions · open=2 BAC+PLTR · risk=$359.18 · NEXT manage_open_paper_campaign
- ARM: WAIT Ken only · no pack-grade · first-live CSP still oversized (NFLX)
- hyp yaml briefly 0-byte mid-write under worker (recovered ~20MB) — known thrash; no git restore

## Thrash detector

- Leaders not re-stressed (TTL skip AAL/BAC) ✓
- Residual thrash #1: **learn_tick under full book** → QC campaign 300s timeout despite scout skip
- Residual thrash #2: **metric-twin / cooled-family requeue** (NFLX CCS clones)

## DID

1. **`trader_paper_campaign.sh` — skip learn_tick when book full**
   - Cheap ledger peek before learn; `book_full_manage_skip_learn`
   - Smoke under live 2/2 book: **~0.06s** wall, manage_only, scout_skipped (was 300s TIMEOUT / ~14s with learn)

2. **`trader_select_stress_hyps.py` — twin dedupe + family cool-down**
   - Collapse evolve fingerprint `(symbol, structure, round(score,1), n_trades)`
   - Cool symbol×structure after ≥2 fails / 0 capital_path_ok in 6h
   - Live select: skip NFLX CCS cooled; queue **TSLL CCS** faee5878; leaders TTL-skipped

3. **Tests**
   - metric twin dedupe + family cool unit tests
   - book-full skip-learn predicate
   - **14 passed** (`test_stress_rotation` + `test_quality_cycle_cadence`)

4. Skill pitfalls updated (learn hang + NFLX twin cool)

## Evidence

- `.cache/platform/quality_residual/campaign_20260724T034933.log` TIMEOUT 300s
- `.cache/platform/paper_campaign/run_*` start-only vs manage skip-learn
- `reports/bootstrap/STRESS_ROTATION.json` NFLX CCS 6h fail streak
- pytest: 14 passed

## Paper (post-close; no force manage)

| Order | Sym | ml | Action |
|---|---|---:|---|
| paper_2f78815a0614 | BAC PCS | 162.64 | **HOLD** (book full; overnight) |
| paper_c80aaa1cab46 | PLTR PCS | 196.54 | **HOLD** (manage path; prior elevated notes stand) |
| New | — | — | **STAND_ASIDE** (2/2) |

No live / shadow / arm.

## DURABLE

- Repo: campaign skip-learn + selector twin/cool + tests
- Skill: two new pitfalls
- Memory: none

## VERIFICATION

- `pytest tests/test_stress_rotation.py tests/test_quality_cycle_cadence.py` → **14 passed**
- `bash scripts/trader_paper_campaign.sh` → 0.06s, skip learn, manage_only
- `trader_select_stress_hyps.py --json` → cooled NFLX; TSLL CCS selected

## INTEGRATION

- Selective commit: scripts/tests/wake/NEXT/readiness — **not** hypotheses.yaml thrash / worker caches

## LESSON

Future Trader: full-book campaign must not touch hyp registry (no learn). Stress queue must not re-burn cooled families or score-identical hyp_id clones — fingerprint + fail-streak cool before B3/B4.

## NEXT SEED

`manage_open_paper_campaign` (ken_required=false) — HOLD open paper; worker continues EDGE with cooler selector; no Ken.

## GATES

none

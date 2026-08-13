# WAKE — 2026-08-12T2100 continuum judgment / coach

WAKE: 2026-08-12 ~21:00 PDT / 2026-08-13 00:00 ET  
PHASE: **SHADOW** ops + PAPER manage + EDGE coach  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
ECONOMIC MECHANISM: time-decay defined-risk multi-leg income (paper research) + MCP single-leg first-live lane  
CANDIDATE/FAMILY SCOPE: post-unlock CCS vanity burn (F/CCL/SNAP/TSLL CCS) vs CCL PCS survivor  
FUNNEL: F2 residual (B3/B4 rotation) — not new F0  
PREDECLARED FALSIFIER: create-sat unlock + living&lt;12 reopen keeps minting 4h all-fail CCS while a better family (CCL PCS) already SHIP@5%  
OUTCOME: **BLOCKER_REMOVED_AND_RETESTED**  
STRATEGY ADVANCEMENT: false (no new capital_path leader; F IC dens0 still leads)  
SEARCH INFORMATION: true — unlock worked (CCL PCS 11/12 ok) then became CCS vanity license; 4h exhaust re-arms hot-streak  
NO-ADVANCE STREAK: n/a (coach ops; no F0 BUILD streak)  
CHOSE: **stop post-reopen CCS vanity burn** — `family_reopen_sample_exhausted` — not densify, not ARM

## Orient

- Status: Phase SHADOW · NEAR_PACKET · EDGE OK pack-grade shortlist_dna_multi · ROBOT paper=ok shadow=PASS · ARM blocked
- Worker ON · cycle 21815 · all rc=0 · registry≈5.3MB · edge_search=OK · hb fresh
- Latest cycle created+stressed `hyp_dna_f_call_credit_spread_dd11c0ae` — B4 fragile@5% pnl−379 (already NULL at 2% slip)
- NEXT prior: `manage_open_paper_campaign` · 1 open BAC PCS `paper_b5422618e55d` ml=$79.32
- Research leaders: F IC dens0; AAL/BAC PCS; first-live SNAP CSP fit_3k
- After-hours: no paper ladder force-close

## Diagnosis (highest leverage)

| Signal | Finding |
|---|---|
| Unlock 15:15 | create-sat floor 12 reopened preferred CCS/IC mint |
| 55 stresses since 22:00Z | F/CCL/SNAP/TSLL CCS + CCL IC mostly B4 kill |
| Hidden survivor | **CCL PCS 11/12 capital_path_ok** (SHIP@5%, dens0–2) — correctly not leading F IC dd22 |
| Latest create | F CCS `dd11c0ae` mid-mark SHIP 139 n=47 → 2% slip already NULL |
| Why still minting | living 7–12 &lt; `streak_min_living=12` skipped hot-streak even after a fresh 4h fail burst |

Unlock did its job (found CCL PCS). Leaving the reopen latch stuck on is the waste.

## DID

1. Added `family_reopen_sample_exhausted` (≥4 fails & 0 oks in 4h)
2. `family_challenge_toxic` living-floor skip now falls through to hot-streak when the 4h sample is exhausted
3. Leftover 8h-old streaks still reopen (prune/sat leftover ≠ tonight's burst)
4. Isolated IC unsat test (live-ledger IC/PFE hope was dated after the burn)
5. Tests: **44 passed** (`test_stress_rotation` + `test_evolve_toxic_family_registry`)
6. Live verify: F CCS + TSLL CCS exhaust+toxic; CCL PCS open (5 oks / 4h); F IC leaders not toxic
7. Selector n=0 (queue drained + newly toxic CCS skipped) — unsat now SNAP/TSLL PCS + XOM/INTC CCS
8. Paper: leave BAC manage residual (after-hours; no ladder fire)

### Live family flags (coach_20260813T2100)

| family | live | 4h | exhaust | toxic | note |
|---|---|---|---|---|---|
| F CCS | 11 | 4f/0ok | yes | yes | stop mint |
| TSLL CCS | 12 | 5f/0ok | yes | yes | stop mint |
| SNAP/CCL CCS | 12 | 2–3f | no | yes via living≥12 hot | stop mint |
| CCL PCS | 12 | 1f/5ok | no | no | keep |
| F IC | 12 | 1f/0ok | no | no | leaders hold |

## EVIDENCE

- `trader_platform/stress_family_policy.py` (`family_reopen_sample_exhausted`)
- `tests/test_stress_rotation.py` (`test_family_reopen_sample_exhausted_rearms_hot_streak`)
- `tests/test_evolve_toxic_family_registry.py` (isolated IC eligibility)
- `.cache/platform/quality_residual/cost_20260813T035534.json` (F CCS 2% already NULL)
- `.cache/platform/quality_residual/evolve_dr_20260813T035534.log` (created dd11c0ae)
- skill `references/quality-acceleration.md` fingerprint

## DURABLE

- Thin/moderate living reopen is for **leftover** 24h streaks after prune/sat, not a standing CCS vanity license.
- After unlock, read the **4h** fail burst before declaring EDGE healthy. 11/12 CCL PCS oks can hide inside a 55-row CCS spray.

## VERIFICATION

- `pytest tests/test_stress_rotation.py tests/test_evolve_toxic_family_registry.py` → **44 passed**
- selector n=0 · skipped_family_toxic includes CCL/SNAP/TSLL CCS + SNAP/NFLX IC
- live F CCS exhaust=1 toxic=1 · CCL PCS toxic=0
- live_armed=false · ken_required=false

## INTEGRATION

- Selective commit: policy + tests + wake/INDEX/LATEST + NEXT_SEED + readiness + skill ref — **no** hypotheses.yaml thrash

## LESSON

- Future coach: if last wake unlocked creates and tonight's cycle log is `created: *ccs*` + B4 large_loss@5%, check `family_reopen_sample_exhausted` before raising sat floors again.

## NEXT SEED

manage_open_paper_campaign · ken_required=false · BAC HOLD residual · worker uses 4h exhaust (no restart required if cycles subprocess) · no densify · ARM Ken only

## GATES

none · ARM still Ken LIVE_PACKET only

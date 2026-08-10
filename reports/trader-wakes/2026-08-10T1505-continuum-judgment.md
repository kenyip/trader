# WAKE — 2026-08-10T1505 continuum judgment / coach

WAKE: 2026-08-10 ~15:00–15:10 PDT / 22:00–22:10 UTC  
PHASE: **SHADOW** (ops) + EDGE search repair  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
ECONOMIC MECHANISM: continuum must mint **new** unstressed multi-leg DNA for B3/B4; update-only evolve under a near-fully-stressed registry is fake-green empty queue  
CANDIDATE/FAMILY SCOPE: `apply_results` max_create budget; unsat AAPL PCS + IWM CCS challenge; F IC shortlist leaders  
FUNNEL: F2 search health → B4 kill of vanity unsat SHIP (no new F3 seat)  
PREDECLARED FALSIFIER: free updates must not block creates; new unsat SHIP still dies B4 if dens/slip worse than F IC leaders  
OUTCOME: **BLOCKER_REMOVED_AND_RETESTED**  
STRATEGY ADVANCEMENT: false (no capital-path leader beats F IC dens0 / SHIP@5% / dd~25)  
SEARCH INFORMATION: true — empty stress queue root cause fixed; AAPL PCS + IWM CCS B4 REJECT  
NO-ADVANCE STREAK: none (ops/search repair)  
CHOSE: **max_create update-starvation fix + unsat create→B3/B4** (not densify, not paper spray)

## Orient

- Status: EDGE OK · ROBOT paper 2 open AAL+BAC PCS risk~$120 · shadow PASS · ARM blocked  
- Worker ON cycles~20.6k green wall~126s; `shortlist_hyps=""`; stress_queue_empty every cycle  
- Multi-leg registry ~512 PCS/CCS/IC rows; **only toxic NFLX IC unstressed** after worker stressed AAL IC d37 (dens9 secondary)  
- DR cycles `updated:` high-score already-registered DNA (ARM CCS / AAL IC) with **zero creates** → selector n=0 while edge_search=OK  
- Shortlist leaders: F IC dens0 SHIP@5% dd~25 (best risk profile); AAL/BAC PCS secondary; first-live SNAP CSP fit_3k  
- NEXT was `manage_open_paper_campaign` · post-close coach parallel EDGE repair  

## DID

1. Diagnosed thrash: green cycles + empty stress queue = almost all multi-leg already in `STRESS_ROTATION`; evolve `--apply` counted **updates toward max_create**, so top re-sims exhausted budget before unsaturated creates  
2. Patched `trader_platform/evolve_tick.apply_results`: `max_create` counts **new hyp rows only**; evidence updates free  
3. Test `test_apply_existing_updates_do_not_consume_max_create_budget` + suite `tests/test_evolve_toxic_family_registry.py` (+ vanity/stress_rotation) → **41 passed**  
4. Hardened `_symbol_of` in `trader_select_stress_hyps` to read `dna.symbols[]`  
5. Stopped quality_worker; forced unsat DR evolve → created `hyp_dna_aapl_put_credit_spread_2c8840e6` + `hyp_dna_iwm_call_credit_spread_13d60e0c`  
6. B3/B4 coach: both **B3 hold** vanity full-history SHIP; both **B4 REJECT** (AAPL −$994@5%; IWM −$1440@5%) — correctly not capital_path  
7. Ingest rotation + refresh shortlist (F IC leaders hold); `just trader-first-live-lane`  
8. Restarted quality_worker; status EDGE OK / ROBOT paper 2 open  

## EVIDENCE

- Code: `trader_platform/evolve_tick.py` (max_create = creates only)  
- Test: `tests/test_evolve_toxic_family_registry.py::test_apply_existing_updates_do_not_consume_max_create_budget`  
- Evolve logs: `.cache/platform/quality_residual/evolve_dr_coach_20260810T1506.log` + `…1508.log`  
- Regime/cost: `.cache/platform/quality_residual/regime_coach_20260810T1509.json` + `cost_coach_20260810T1509.json`  
- Boards: `QUALITY_SHORTLIST.json` tops F IC; `STRESS_ROTATION.json` AAPL/IWM capital_path_ok=false  
- pytest: 41 passed (toxic + vanity + stress_rotation)  

## DURABLE

- Repo: free-update max_create semantics + regression test + selector symbols[] parse  
- Skill: pitfall row — green empty stress queue under update-only evolve  
- Lesson: when multi-leg registry is mostly stressed, **create budget must ignore re-sim updates** or EDGE looks SEARCHING while B3/B4 starves  

## VERIFICATION

- 41 tests passed  
- Selector after creates: n=2 (AAPL PCS + IWM CCS) then B4 reject ingested  
- Shortlist still F IC dens0 leaders (no worse dens/dd promotion)  
- Worker restarted edge_search=OK registry≈2.9MB  
- No live/broker/arm/shadow promote  

## INTEGRATION

- Selective commit: evolve_tick + select script + tests + hyp yaml (new DNA) + shortlist/stress/first-live boards + wake/NEXT/readiness  
- Leave worker cycle caches unstaged  

## LESSON

Future Trader: diagnose empty `shortlist_hyps` with unstressed multi-leg count + last evolve `created:` vs `updated:`. If updates dominate and unstressed≈0–2 toxic-only, patch/verify **max_create does not charge updates**, then force unsat DR create→B3/B4 before calling EDGE healthy.

## NEXT SEED

`manage_open_paper_campaign` · ken_required=false · open AAL PCS + BAC PCS (risk~$120) · next RTH re-mark ladder · EDGE worker continues with free-update create budget (expect non-empty stress when unsat SHIPs mint)

## GATES

none (Ken only for LIVE_PACKET / $3k / arm)

# WAKE — 2026-08-06T2105 continuum judgment / coach

WAKE: 2026-08-06 ~21:01–21:10 PDT / 2026-08-07 04:01–04:10 UTC  
PHASE: **SHADOW** (ops: PAPER manage residual; coach EDGE data-path repair)  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
CHOSE: **Unblock EDGE — fix corrupt VIX cache killing all build/stress/evolve/research**  
OUTCOME: `BLOCKER_REMOVED_AND_RETESTED` (search infrastructure; retest evolve+B3/B4+research+first-live)  
STRATEGY ADVANCEMENT: false (AAL dens1 leaders hold; no tighter risk profile displaced them)  
SEARCH INFORMATION: true — “healthy worker + stress rc=1” was VIX parse death, not empty edge  
NO-ADVANCE STREAK: n/a (coach ops)

## Orient

- Status pre-fix: Phase SHADOW · search SEARCHING; EDGE WIP; first-live **eligible=0**; paper 2/2 AAL+BAC; shadow PASS; worker ON cycles~17.5k hb fresh registry≈4.2MB
- Cycle LATEST: wall~27–59s, shortlist_hyps stuck AAL×2, **regime_stress rc=1 / cost_stress rc=1 / research rc=2 / evolve all NULL build failed**
- Root log: `pandas.errors.ParserError: Expected 2 fields in line 281, saw 3` via `data.load_vix` → `.cache/VIX_10y.csv`
- Glued row evidence: `2017-09-13,10.202017-09-14,10.4399995803833`
- Selector: leaders outside TTL → re-queued forever; every B3/B4 burn failed in ~4s; evolve created nothing
- FIRST_LIVE_LANE stale 2026-08-05 with spot=0.0 → n_eligible=0
- Jarvis guidance (2026-07-15 burst-stop BUILD): critic context only — not an order for this continuum coach

## Decision charter

- ECONOMIC MECHANISM: n/a — restore feature/sim data path so next cycles can find/falsify DNA
- CANDIDATE/FAMILY SCOPE: VIX cache integrity + post-fix coach DR on F/CCL/KO/IWM/BAC/SNAP/PFE/TSLL
- FUNNEL: search infrastructure (+ incidental B3/B4 closes on AAL IC / IWM CCS; IWM PCS dens5 secondary)
- PREDECLARED FALSIFIER: after VIX repair, stress/research/evolve exit 0; AAL dens1 still beat dens5 vanity; first-live not stuck eligible=0 solely from spot=0
- Decision: delete+refetch VIX → harden load_vix → tests → re-stress leaders → first-live refresh → coach evolve+B3/B4

## DID

1. Diagnosed cycle/stress/evolve/research logs → single VIX tokenize failure (pitfall already documented)
2. Removed corrupt `.cache/VIX_10y.csv`; `load_vix` refetch → len=2514 through 2026-08-06; `build('AAL','5y')` → 973 rows
3. Hardened `data.load_vix`: catch ParserError/EmptyDataError/ValueError/IndexError/OSError on cache read, unlink, refetch; empty series if network fails
4. Added `tests/test_load_vix_corrupt_cache.py` — **2 passed**
5. Re-proved leaders B3/B4:
   - AAL PCS `5fa0eac8`: hold dens1 dd31 SHIP@5% pnl~60
   - BAC PCS `c7d09885`: hold dens0 dd42 SHIP@5% pnl~173
   - Ingest + shortlist refresh; TTL skip works on fresh capital_path_ok
6. Stressed unstressed AAL IC `b82d92ea` → **B4 fragile** capital_path reject (dens10 / NULL@-147)
7. `just trader-first-live-lane` → **n_eligible=1** leader AAL `wheel_assignment` dna_4afc n=29 fit_3k csp_bp≈$1523 (was 0)
8. Coach DR `--symbols F CCL KO IWM BAC SNAP PFE TSLL --ship-only --max-create 2`:
   - created `hyp_dna_iwm_put_credit_spread_57fcf3b0` (full-history vanity SHIP)
   - updated `hyp_dna_iwm_call_credit_spread_b697ee8b`
9. B3/B4 IWM:
   - PCS: dens5 dd186 SHIP@5% — capital_path_ok but **does not outrank** AAL dens1 on shortlist (correct quality bar)
   - CCS: B4 REJECT@-1431 capital_path reject
10. Worker left ON (no stop needed); research tick green multi_symbol_universe; status EDGE=PASS pack-grade shortlist_dna_multi; first-live seat restored

## EVIDENCE

- Code: `data.py` `load_vix`; `tests/test_load_vix_corrupt_cache.py`
- Stress: `.cache/platform/quality_residual/regime_coach_20260807T040310.json` + `040355` + `040450` / matching `cost_coach_*`
- Ledger/shortlist/first-live/shortlist_dna_multi: `reports/bootstrap/STRESS_ROTATION.json`, `QUALITY_SHORTLIST.json`, `FIRST_LIVE_LANE.json`, `SHORTLIST_DNA_MULTI.json`
- pytest: 2 passed
- Status post: EDGE PASS · ROBOT PASS · ARM BLOCKED; first-live AAL wheel; paper 2/2

## DURABLE

- Repo: load_vix harden + tests + bootstrap boards + wake/NEXT/readiness
- Lesson: green quality cycles with **stress/evolve rc≠0 and identical shortlist_hyps** → inspect VIX/feature build first, not thrash densify or re-prune a healthy ~4MB registry
- Skill pitfall already covers VIX glued-row; code now self-heals on next read
- IWM dens5 capital_path secondary ≠ pack leader (AAL dens1/dd31 holds)

## VERIFICATION

- pytest `tests/test_load_vix_corrupt_cache.py`: 2 passed
- pcs_regime_stress / pcs_cost_stress coach stamps: rc=0
- research tick coach: rc=0 n_scored=30
- evolve_tick coach: rc=0 created IWM PCS
- first-live: n_eligible=1
- No live/place_*/arm; paper ledger untouched this coach tick

## INTEGRATION

- Selective commit: data.py, tests, bootstrap boards, wake/INDEX/LATEST, NEXT_SEED, readiness; hyp yaml only if intentional coach creates cleanly staged — never foreign WIP absorb
- See git log after push

## LESSON

Future Trader: when every symbol fails `Error tokenizing data … Expected 2 fields` through `load_vix`, **delete/refetch VIX_*** and keep the ParserError self-heal path — do not treat empty SHIP tables as diminishing returns.

## NEXT SEED

`manage_open_paper_campaign` (ken_required=false) — mark/manage AAL+BAC paper on next RTH; worker EDGE continues with live VIX. Prefer new unstressed multi-leg B3/B4 over re-burning TTL-fresh AAL leaders.

## GATES

none (Ken only for LIVE_PACKET / $3k / arm)

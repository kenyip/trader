# WAKE — 2026-07-27T2106 continuum judgment / coach

WAKE: 2026-07-27 ~21:06 PDT continuum-judgment (21:00 slot)  
PHASE: PAPER  
SLEEVE: 3000 plan · cash≈500 · live_armed=false  
CHOSE: **Improve search system** — close capital_path_ok leak for NULL@tiny-positive slip (soft cost_hold false edge)  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED  
STRATEGY ADVANCEMENT: false (gate repair + ledger rescore; no new DNA stage move)  
SEARCH INFORMATION: 80/445 capital_path_ok rows were non-SHIP@5% (NULL@tiny+); flipped_off=80 → ok=365 all SHIP; TSLL CCS 8297191d demoted  
NO-ADVANCE STREAK: n/a (coach search-system wake)  
ECONOMIC MECHANISM: defined-risk credit edge must survive 5% slip as SHIP, not soft cost_hold with vanished/near-zero edge  
CANDIDATE/FAMILY SCOPE: stress-rotation capital_path policy (all multi-leg B3/B4 ledger rows)  
FUNNEL: F2 stress honesty (ledger gate)  
PREDECLARED FALSIFIER: capital_path_ok requires b4_slip5_verdict==SHIP; NULL/NEEDS/missing fail closed  

## Orient

- Worker ON · pid 73002 · cycle_n≈819 · hb fresh · wall~11–12m (evolve_csp+DR ~300s each; shortlist_dna_multi ~90s; campaign 0.07s book-full)
- Book full 2/2 BAC+PLTR PCS · open_risk $359 · sessions 5/3 · HOLD path
- EDGE pack-grade via shortlist_dna_multi (AAL PCS multi_ok BAC+XOM; BAC PCS multi_ok AAL/TSLL/XOM; AAL CCS multi_ok)
- FIRST-LIVE: SNAP CSP fit_3k n=107
- Shadow PARTIAL stub-only (2026-07-26) — ROBOT blocker unchanged this wake
- Selector after fix: n=0 (AAL leaders TTL-skipped; toxic NFLX/PLTR/SMCI CCS; empty queue beats thrash)
- Last cycle stressed TSLL PCS+CCS — PCS B4 fail; CCS admitted capital_path on NULL@$4.14 dens=4 dd=174 (**leak**)

## DID

1. `just trader-status` — EDGE OK / ROBOT paper ok + shadow partial / ARM wait
2. Mined cycle_LATEST 819 + STRESS_ROTATION + selector + SHORTLIST_DNA_MULTI
3. **capital_path_decision**: require `b4_slip5_verdict == SHIP` (NULL@tiny+, NEEDS, missing fail closed)
4. Tests: NULL@4.14 TSLL-shape + missing verdict + ingest rank (NFLX NULL no longer capital-path)
5. `--rescore-only --refresh-shortlist` → flipped_off=80, ok=365 all SHIP; shortlist top remains AAL dens1 SHIP + BAC dens0 SHIP
6. NEXT_SEED → non-stub shadow rehearsal residual (ROBOT) while manage paper continues

## Evidence

- `scripts/trader_ingest_stress_rotation.py` (SHIP@5% hard gate)
- `tests/test_stress_rotation.py`
- `reports/bootstrap/STRESS_ROTATION.json` (rescore)
- `reports/bootstrap/QUALITY_SHORTLIST.json`
- `.cache/platform/quality_worker/cycle_LATEST.json` (TSLL thrash context)

## VERIFICATION

```
.venv/bin/python -m pytest tests/test_stress_rotation.py -q
# 12 passed
.venv/bin/python scripts/trader_ingest_stress_rotation.py --rescore-only --refresh-shortlist
# rescore n=2549 ok=365 flipped_off=80
```

## DURABLE

- Repo: capital_path requires SHIP@5%; ledger purged soft NULL@positive; shortlist pure SHIP multi-leg
- Skill: pitfall NULL@tiny+ capital_path leak closed
- Memory: none

## LESSON

Soft `cost_hold=true` + `slip5_verdict=NULL` with tiny positive pnl (~$1–$10) was still `capital_path_ok`. That inflated ok counts (80 rows) and let thrash DNA (e.g. TSLL CCS dens4) look like survivors after B4. Comments already said “require SHIP@5%” for NEEDS only — enforce for **all** non-SHIP verdicts. Empty stress queue after purge is success (no B3/B4 burn), not “no edge.”

## NEXT SEED

`shadow_rehearsal_non_stub_then_manage_paper` · ken_required=false  
(Paper book full → HOLD/manage; search continues via worker; empty stress queue OK until new unstressed SHIP score>0 on non-toxic families.)

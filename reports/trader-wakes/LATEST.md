# WAKE — 2026-08-07T2100 continuum judgment / coach (Fri evening)

WAKE: 2026-08-07 ~21:00–21:10 PDT / 2026-08-08 ~00:00–00:10 UTC  
PHASE: **SHADOW** (ops) + **BUILD** coach (search system)  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
CHOSE: **Unblock first-live CSP board + family-scoped unsat inject**  
OUTCOME: **BLOCKER_REMOVED_AND_RETESTED** (first-live seats restored; open multi-leg families retest B4 reject)  
STRATEGY ADVANCEMENT: false for multi-leg capital_path (INTC IC + IWM CCS B4 fragile); **true for first-live funnel** (MCP seats named)  
SEARCH INFORMATION: true — CSP collateral≠$300 bar; sibling thrash hid INTC IC; MU/TSLA cold zero-trade  
NO-ADVANCE STREAK: multi-leg capital_path no new ok (ops separate)

## Orient

- EDGE: PASS / SEARCHING — pack-grade shortlist_dna_multi; research CCL IC dens0 leaders; worker ON edge_search=OK registry≈5.9MB cycles~18.5k  
- ROBOT: paper open=1 AAL PCS `paper_537129ebd52d` risk=$40.3 sessions 13/3; shadow PASS  
- ARM: WAIT (Ken LIVE_PACKET only)  
- NEXT was: manage_open_paper_campaign (RTH closed; HOLD residual overnight)  
- Pathology: `FIRST_LIVE n_eligible=0` forever (SNAP CSP ml≈500>300); stress queue empty (leaders TTL); unsat → MU/TSLA zero_trades; DR create starved on open preferred families  

## Decision charter

- ECONOMIC MECHANISM: MCP first-arm needs CSP/wheel seats that fit sleeve collateral; multi-leg EDGE needs sibling-safe family inject when preferred PCS is toxic  
- CANDIDATE/FAMILY SCOPE: first-live CSP ranker; unsat families AAL IC / IWM CCS / INTC IC  
- FUNNEL: ARM-path board F3 naming + multi-leg create→B3/B4  
- PREDECLARED FALSIFIER: first-live n_eligible>0 with SNAP-class leader; unsat fams include open INTC IC; forced DR DNA B3/B4 decides capital_path  

## Root cause

1. `rank_first_live_seats` applied the **$300 defined-risk bar** using CSP **collateral fallback** (spot×100). SNAP@~$5 → ml≈500 always near-miss; board empty despite doctrine SNAP/TSLL CSP first-arm.  
2. `unsaturated_discovery_families` skipped open **INTC IC** because **symbol-level** fail mass from toxic INTC PCS ≥ thrash min.  
3. MU on preferred cold + TSLA not mega-demoted → DR residual burned zero_trades while tier-0 preferred multi-leg was hot/toxic/saturated.  

## DID

1. `just trader-status` — EDGE/ROBOT OK; ARM wait; open=1 AAL; worker healthy; stress n=0  
2. **Code**  
   - `first_live_lane.py`: CSP/wheel gate = fit_3k + csp_bp≤sleeve; $300 bar only on explicit path max_loss / long debit; `fits_test_cash_500` (±5%)  
   - `stress_family_policy.py`: family-scoped thrash for family inject; MU off preferred; MU+TSLA mega-demote  
   - tests: first-live CSP board + sibling IC inject (25 passed)  
3. `just trader-first-live-lane` → **n_eligible=1143**, leader **SNAP CSP** bp≈506 fit_3k test_cash≈true; shortlist SNAP/AAL/TSLL/SOFI/SMCI  
4. Force DR AAL/IWM/INTC → created `hyp_dna_intc_iron_condor_665d6c9a`, updated IWM CCS `b697ee8b`  
5. B3+B4 coach: both **B4 fragile REJECT@5%** → capital_path_ok=false (ingest ledger)  
6. No paper close/live/arm; **no hyp yaml commit**  

## EVIDENCE

- `reports/bootstrap/FIRST_LIVE_LANE.json` — SNAP CSP leader  
- `.cache/platform/quality_residual/regime_coach_20260808T040902.json` + `cost_coach_20260808T040902.json`  
- `reports/bootstrap/STRESS_ROTATION.json` — INTC IC + IWM CCS reject rows  
- pytest: `tests/test_first_live_lane.py` + `tests/test_evolve_toxic_family_registry.py` → **25 passed**  

## DURABLE

| Surface | Change |
|---|---|
| `trader_platform/first_live_lane.py` | CSP collateral vs path-loss bar split |
| `trader_platform/stress_family_policy.py` | family thrash + MU/TSLA demote |
| tests | CSP board + sibling IC |
| skill `references/quality-acceleration.md` | 2026-08-08T2100 pitfall |
| bootstrap | FIRST_LIVE_LANE + STRESS_ROTATION + shortlist refresh |

## VERIFICATION

- pytest first_live + toxic family → **25 passed**  
- first-live leader SNAP CSP; n_eligible>0  
- unsat fams include AAL IC tier0 + IWM/INTC opens (not MU/TSLA-only)  
- INTC IC + IWM CCS capital_path_ok=false (B4)  
- No live/place_*/arm  

## INTEGRATION

- commit `c90568d` on `main` pushed to `origin/main`
- clean of intended paths; left unstaged: worker `hypotheses.yaml` thrash + residual multi/paper_loop caches
- verification: pytest 25 passed (first_live + toxic family)  

## LESSON

Future Trader: **never gate CSP first-live on $300 using full collateral** — that empties the MCP arm path. Family inject thrash must be **per structure**, not whole-symbol, or the last open twin dies.  

## NEXT SEED

`manage_open_paper_campaign` — HOLD open AAL PCS overnight; next RTH dual-PT re-mark. Worker continues with fixed first-live + unsat. Optional: CSP evolve bias SNAP/TSLL fit_3k; do not thrash densify. ken_required=false.  

## GATES

none (Ken only: gateway / LIVE_PACKET arm / $3k at packet)

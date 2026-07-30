# WAKE — 2026-07-30T0908 continuum judgment / coach

WAKE: 2026-07-30 ~09:00–09:10 PDT / 12:00–12:10 ET  
PHASE: PAPER  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
CHOSE: **Unstick empty B3/B4 queue** — evolve was sampling research tops only; all multi-leg registry DNA already stressed → selector n=0 forever  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED (search system) + FAMILY_CLOSED-ish on forced IWM create set (B4 not SHIP@5%)  
STRATEGY ADVANCEMENT: false (no new capital_path multi-leg leader)  
SEARCH INFORMATION: true — root cause fixed; shortlist de-monocultured; IWM PCS vanity SHIP falsified at B4  
NO-ADVANCE STREAK: n/a (coach ops; EDGE pack-grade already OK via shortlist_dna_multi)

## Orient

- EDGE: pack-grade shortlist_dna_multi quality_pass; research leader AAL PCS `5fa0eac8`; first-live **F CSP** fit_3k n=99; worker ON cycles≈4477 hb fresh; registry ~4.5MB
- ROBOT: paper open **2/2** AAL CCS + BAC PCS risk=$264.24 · sessions 7/3; shadow PARTIAL
- NEXT: `manage_open_paper_campaign` (RTH owns marks; coach does not re-mark)
- Session: RTH midday Thu 2026-07-30; continuum coach slot
- Cycle LATEST: wall~35s, **shortlist_hyps empty**, stress_queue_empty ledger-only refresh, evolve_csp ok / DR alternate skip, registry 4.68MB

### Thrash detector (mandatory)

| Signal | Observation |
|---|---|
| shortlist_hyps empty many cycles | YES — selector n=0 |
| Leaders TTL-skipped | AAL PCS `5fa0eac8` + `5c55c29f` (48h capital_path_ok) |
| Multi-leg unstressed in registry | **0 / 466** — every ML hyp already in STRESS_ROTATION (3054 ledger ids) |
| DR evolve SHIP without create | NFLX/PLTR/SOFI CCS SHIP logs; toxic/saturated blocks create |
| Research tops | TSLL NFLX SMCI PLTR XOM SOFI BAC AAL — **no** SNAP/CCL/PFE/KO/IWM |
| Saturated | AAL PCS ok≈280, BAC PCS≈87, AAL CCS≈28, TSLL CCS≈59 |
| Toxic | NFLX/PLTR/SOFI CCS, F multi-leg, XOM PCS, … |

**Verdict:** green cycles + empty stress queue ≠ progress. Search starved of *creatable* multi-leg DNA outside AAL/BAC monoculture.

## Decision charter

- ECONOMIC MECHANISM: improve search routing so unsaturated multi-leg families get sim→create→B3/B4 bandwidth  
- CANDIDATE/FAMILY SCOPE: system fix (evolve symbol mix + shortlist diversity); retest via forced IWM/SNAP/CCL DR  
- FUNNEL: F1 discovery plumbing (not capital-path advance)  
- PREDECLARED FALSIFIER: after fix, selector must find unstressed multi-leg OR shortlist must show ≥3 symbols; forced IWM SHIP must still clear SHIP@5% for capital_path  
- Decision: ship code fix + shortlist cap; IWM B4 fail = honest reject (not capital path)

## DID

1. Diagnosed selector n=0: all 466 multi-leg registry rows already stressed; evolve tops never inject unsaturated names  
2. **`unsaturated_discovery_symbols`** in `stress_family_policy.py` — prefer proven-unsaturated (PFE/SNAP/TSLL…) over cold mega-caps; skip toxic+saturated  
3. **`evolve_tick`**: default `--unsat-extra 4` appends discovery symbols; `--symbols` force list for coach/recovery  
4. **Shortlist** `max_per_symbol` 3→2 so AAL+BAC cannot fill all 6 multi-leg seats  
5. Forced DR apply on SNAP CCL PFE KO IWM TSLL → created 4× IWM multi-leg SHIP (SNAP/CCL/PFE zero-trade on this pop)  
6. B3+B4 + ingest on IWM quartet — **none capital_path_ok** (B4 NULL/~0 or NEEDS@5% not SHIP)  
7. Shortlist refresh → **AAL×2, BAC×2, F PCS, CCL PCS** + first-live MCP tier  
8. Post-fix selector: n=1 residual unstressed (`hyp_dna_amd_put_credit_spread_677da0bb`) — queue unstuck  
9. Tests: 25 passed (`test_evolve_toxic_family_registry` + `test_stress_rotation`)

## Evidence

- evolve force log: `.cache/platform/quality_residual/evolve_dr_coach_20260730T1200.log`  
  - created: `hyp_dna_iwm_put_credit_spread_{b651a30d,94abf5bb,9f68914e}`, `hyp_dna_iwm_call_credit_spread_2a0c6bd5`  
- B3/B4: `.cache/platform/quality_residual/regime_20260730T1206.json`, `cost_20260730T1206.json`  
- ingest source=`coach`; IWM rejects: slip5 NULL/~0 or NEEDS_MORE_DATA (not SHIP@5%)  
- shortlist top_ids: AAL, AAL, BAC, BAC, F, CCL  
- code: `trader_platform/stress_family_policy.py`, `trader_platform/evolve_tick.py`, `scripts/trader_ingest_stress_rotation.py`  
- tests: `tests/test_evolve_toxic_family_registry.py`

## IWM stress snapshot (falsified for capital path)

| hyp | dens | dd | slip5 | capital_path |
|---|---:|---:|---|---|
| iwm PCS b651a30d | (see regime) | high | NULL~0 | false |
| iwm PCS 94abf5bb | | | NULL~0 | false |
| iwm PCS 9f68914e | dens3 | dd~174 | NEEDS +186 | false (not SHIP@5%) |
| iwm CCS 2a0c6bd5 | dens5 | dd~240 | NULL~0 | false |

Full-history SHIP $ on IWM does **not** outrank AAL/BAC risk profile; edge dies under 5% slip.

## VERIFICATION

```text
pytest tests/test_evolve_toxic_family_registry.py tests/test_stress_rotation.py → 25 passed
unsaturated_discovery_symbols(limit=8) → ['PFE','SNAP','PLTR','TSLL',…]
forced evolve --symbols SNAP CCL PFE KO IWM TSLL → 4 IWM creates
pcs_regime_stress + pcs_cost_stress + ingest --refresh-shortlist → shortlist F+CCL seats
select_stress_hyps → n≥1 (was 0)
```

## DURABLE

- Repo: unsaturated evolve inject + shortlist ≤2/symbol (this commit)  
- Skill: empty stress queue + green cycles + research tops without SNAP/CCL/PFE ⇒ check multi-leg unstressed count before calling continuum healthy  
- Memory: none (session-local)  
- hyp yaml: IWM creates on disk; **not** committed (worker thrash surface)

## INTEGRATION

- Selective commit: code/tests/shortlist/ledger/wake only; leave `hypotheses.yaml` unstaged  
- ken_required=false

## LESSON

Future Trader: when every multi-leg hyp is already in STRESS_ROTATION, **B3/B4 cannot invent novelty** — evolve must create on non-toxic non-saturated symbols. Research composite tops are necessary but not sufficient; default unsat inject closes the starvation loop. Shortlist caps per symbol must leave room for secondary capital_path symbols (F/CCL) or status will look like AAL/BAC forever.

## NEXT SEED

`manage_open_paper_campaign` (RTH) + worker continues with unsat inject; residual stress may pick AMD/IWM-class fresh DNA. No Ken.

## GATES

none

# WAKE — 2026-07-30T1509 continuum judgment / coach

WAKE: 2026-07-30 ~15:01–15:10 PDT / 18:01–18:10 ET  
PHASE: PAPER → **SHADOW** (ROBOT shadow PASS this wake)  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
CHOSE: **Improve unsat inject thrash + force unsaturated DR → B3/B4 + refresh first-live/shadow**  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED (search routing) + FAMILY_CLOSED-ish on MU/IWM forced set (B4 NULL~0)  
STRATEGY ADVANCEMENT: false (no new multi-leg capital_path leader tighter than AAL/BAC/F/CCL)  
SEARCH INFORMATION: true — recent-fail thrash demotion; SNAP CCS capital_path dens4 noted; MU/IWM vanity SHIP falsified  
NO-ADVANCE STREAK: n/a (coach ops; EDGE pack-grade already OK)

## Orient

- EDGE: pack-grade `shortlist_dna_multi` quality_pass; research leader AAL PCS `5fa0eac8`; worker ON cycles≈5034 hb fresh; registry ~5.94MB near 6MB cap
- ROBOT was: paper 2/2 AAL CCS + BAC PCS risk=$264 · sessions 7/3; shadow **PARTIAL**
- NEXT: `manage_open_paper_campaign` (RTH owns marks; market closed — coach does not re-mark)
- Cycle LATEST: wall~43s, **shortlist_hyps empty**, stress_queue_empty, evolve_csp ok / DR alternate, leaders TTL-skipped AAL PCS pair
- Jarvis guidance (2026-07-15 burst-stop): **not** an order for continuum quality coach

### Thrash detector

| Signal | Observation |
|---|---|
| shortlist_hyps empty | YES — selector n=0 (leaders TTL + 0 unstressed SHIP left) |
| Immediate create→stress | SNAP CCS `aa606248` capital_path_ok dens=4 dd≈51 SHIP@5% — not shortlist seat (dens_bucket) |
| Recent 6h B3/B4 | ARM/AAPL/AMD/AMZN/COIN/PFE CCS fails dominate; F/SNAP CCS some oks |
| Unsat inject before fix | F/SNAP/PFE good; still admitted cold thrash paths via sibling structs |
| Registry | ~5.94MB / 6MB max — DR alternate skip half cycles |

**Verdict:** empty queue after healthy create+stress ≠ starve. Remaining waste = unsat inject recycling mega-cap fail thrash.

## Decision charter

- ECONOMIC MECHANISM: route evolve inject away from recent pure-fail symbols so B3/B4 budget hits F/SNAP/CCL/KO-class DNA  
- CANDIDATE/FAMILY SCOPE: system fix + forced MU/IWM/KO DR retest  
- FUNNEL: F1 discovery plumbing / F2 stress reject  
- PREDECLARED FALSIFIER: MU/IWM SHIP must clear SHIP@5% for capital_path; unsat list must drop AMD-style thrash  
- Decision: ship thrash demotion; MU/IWM B4 NULL~0 = honest reject

## DID

1. Diagnosed selector n=0: unstressed multi-leg SHIP count=0 after cycles stress every create; SNAP CCS just capital_path dens4  
2. **`unsaturated_discovery_symbols`**: score recent fails/oks across **all** ML structs; skip cold names with ≥6 recent fails & 0 recent/lifetime capital_path_ok (AMD sibling-struct disguise fix)  
3. Forced DR `--symbols KO DIA MU IWM CCL F SNAP PFE` → created MU PCS ×2, updated IWM PCS  
4. B3+B4+ingest coach source — **all capital_path_ok=false** (B4 slip5 NULL/~0)  
5. Second KO/DIA/SOFI/NIO force — KO SHIP score≤0 not registered (ship-only gate)  
6. `just trader-first-live-lane` refresh → leader **AAL short_put_credit** n=77 fit_3k (was F CSP overnight board)  
7. Shortlist refresh → multi-leg AAL×2 BAC×2 F PCS CCL PCS + MCP AAL/TSLL/SOFI  
8. **`just trader-shadow-rehearsal --symbols SNAP F TSLL AAL` → PASS** sessions=3 non-stub  
9. Tests: 26 passed (`test_evolve_toxic_family_registry` + `test_stress_rotation`)

## Evidence

- evolve: `.cache/platform/quality_residual/evolve_dr_coach_20260730T220615.log`  
  - created: `hyp_dna_mu_put_credit_spread_e2a8a3d7`, `hyp_dna_mu_put_credit_spread_39aa914f`  
  - updated: `hyp_dna_iwm_put_credit_spread_94abf5bb`  
- B3/B4: `regime_20260730T2207.json`, `cost_20260730T2207.json`  
- SNAP CCS capital_path (prior cycle): `hyp_dna_snap_call_credit_spread_aa606248` dens4 dd51.25 slip+$18.66  
- unsat after fix: `['F','SNAP','PLTR','PFE','ARM',…]` — F/SNAP first  
- shadow: `.cache/platform/shadow/LATEST.json` status=PASS session_days=3  
- code: `trader_platform/stress_family_policy.py`, `tests/test_evolve_toxic_family_registry.py`

## MU/IWM stress (falsified capital path)

| hyp | dens | dd | slip5 | capital_path |
|---|---:|---:|---|---|
| MU PCS e2a8a3d7 | high | high | NULL~0 | false |
| MU PCS 39aa914f | 6 | 373 | NULL~0 | false |
| IWM PCS 94abf5bb | 7 | 202 | NULL~0 | false |

Full-history SHIP $ on MU/IWM dies under 5% slip — same lesson as morning IWM set.

## VERIFICATION

```text
pytest tests/test_evolve_toxic_family_registry.py tests/test_stress_rotation.py → 26 passed
unsaturated_discovery_symbols(limit=10) → F, SNAP first; AMD thrash test green
pcs_regime_stress + pcs_cost_stress + ingest → MU/IWM reject
just trader-first-live-lane → AAL short_put leader
just trader-shadow-rehearsal --symbols SNAP F TSLL AAL → PASS
just trader-status → Phase SHADOW · ROBOT OK · ready≈85%
```

## DURABLE

- Repo: unsat recent-fail thrash demotion + test (this commit)  
- Skill: at 100k char cap — lesson recorded here; do not expand SKILL.md without split  
- hyp yaml MU creates on disk; **not** committed (worker thrash surface)  
- Shadow PASS is ops evidence only — still no LIVE_PACKET / arm

## INTEGRATION

- Selective commit: code/tests/bootstrap boards/wake/shadow report; leave `hypotheses.yaml` unstaged  
- ken_required=false

## LESSON

Future Trader: (1) empty stress queue after create→stress is often **healthy drain**, not starvation — inspect `last_ingest` + capital_path dens before unsat surgery. (2) Unsat inject must count recent fails on toxic structs too or mega-cap thrash hides behind a cold sibling structure. (3) MU/IWM vanity SHIP keeps failing SHIP@5% — do not promote dens≥6 NULL~0 over AAL/BAC dens0–1. (4) Shadow multi-session non-stub is the ROBOT gate — deliberate `trader-shadow-rehearsal` closes PARTIAL.

## NEXT SEED

`manage_open_paper_campaign` on open AAL CCS + BAC PCS (next RTH marks). Worker continues with thrash-aware unsat inject. Residual: registry prune off-hours if bytes stay ≥6MB (stop worker first). No Ken for residual; ARM only on LIVE_PACKET.

## GATES

none (Ken only for LIVE_PACKET / $3k / arm)

# WAKE — 2026-07-22T2103 continuum judgment / coach

WAKE: 2026-07-22 ~21:00–21:05 PDT (evening continuum coach)  
PHASE: PAPER + BUILD search  
SLEEVE: 3000 plan · Agentic cash≈500 · agentic.enabled=false  
ECONOMIC MECHANISM: improve stress→shortlist ranking so B3/B4 cycles stress SHIP@5% leaders + positive-score fresh multi-leg, not soft-loss / NULL-DD vanity  
CANDIDATE/FAMILY SCOPE: stress-rotation ledger / QUALITY_SHORTLIST / stress selector (search system)  
FUNNEL: F3 paper sample ongoing (session_days=1/3) — no TOP_HYP  
PREDECLARED FALSIFIER: if soft_loss@5% or NULL@tighter-DD still outranks SHIP@5% dens=1 after rescore → gate bug  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED (gates + rank + selector fixed; ledger rescored; shortlist/selector verified)  
STRATEGY ADVANCEMENT: false (search-system improvement; no pack-grade TOP_HYP)  
SEARCH INFORMATION: flipped_off=13 soft-loss capital_path; n_ok 126→114; leaders BAC SHIP + CCL CCS SHIP; negative-score unstressed no longer selected  
NO-ADVANCE STREAK: n/a (coach/search tooling)  
CHOSE: Harden capital-path soft-loss reject + rank slip-verdict before DD + skip score≤0 unstressed (worker healthy; paper manage residual already set)

## DID

1. Oriented: `just trader-status` — PAPER_PROGRESS ~66% / HOT_SEARCH ~93%; quality_worker=ON cycles=259 hb fresh; handoff=NO_QUALIFIED_STRATEGY; paper BAC+PLTR working open_risk=$359.18; NEXT=manage_open_paper_campaign
2. Thrash check: cycle mix leaders+fresh OK (not stuck on fixed BAC/PLTR only). Integrity issues remained:
   - **NFLX CCS 5141ccf8** stress_priority #2 with NULL@5% because rank used **dd before slip verdict** (dd 58.98 beat BAC SHIP dd 68.2)
   - **BAC f50469ab** and 12 peers still capital_path_ok with **soft_loss@5% / slip5_pnl&lt;0**
   - Selector pulled **negative composite “SHIP”** (TSLL −146 / SMCI −120) into B3/B4 burn slots
3. Latest cycle 20260723T035127 outcomes: fresh PLTR/BAC/SMCI/TSLL largely B3/B4 rejects; CCL/NFLX leaders re-confirmed — good rotation, bad leader quality for next stress_priority
4. Fixed:
   - `capital_path_decision`: reject **any slip5_pnl &lt; 0** (soft_loss / fragile) regardless of cost_hold / NEEDS_MORE_DATA
   - Rank: dense_neg → **slip verdict (SHIP&lt;NEEDS&lt;NULL)** → max_dd → slip pnl → full pnl
   - Selector registry path: **skip known score ≤ 0** (evolve-log path already did)
5. Rescore: **n=510, flipped_off=13, capital_path_ok=114**; shortlist top all **SHIP@5%**: BAC PCS 3954107b → CCL CCS ee09043e → BAC/AAL SHIPs; NFLX NULL + soft-loss BAC demoted off multi-leg top6
6. Selector after refresh: BAC+CCL SHIP leaders + unstressed **positive** NFLX/PLTR/AAL/SNAP (no neg-score burn)
7. Paper: leave **HOLD** by order_id (post-close; concurrent full); no campaign mutate from coach
8. Tests: `tests/test_stress_rotation.py` **4 passed**

## DECISION

| Item | Action | Why |
|---|---|---|
| Soft-loss slip5_pnl&lt;0 | **capital_path reject** | cost_hold alone ≠ edge under slip |
| Rank verdict before DD | **SHIP@5% leads** dens-equal peers | NULL@tighter-DD was stealing stress_priority |
| Known score≤0 unstressed | **skip B3/B4 select** | Vanity positive_sim + DD penalty |
| Open BAC+PLTR paper | **HOLD** residual | B6 multi-session; book full |
| New paper | **STAND_ASIDE** while 2/2 | Campaign guards |
| Live/shadow/arm | none | Ken-only |

## EVIDENCE

- `scripts/trader_ingest_stress_rotation.py` (soft-loss gate, rank_key)
- `scripts/trader_select_stress_hyps.py` (score≤0 skip)
- `tests/test_stress_rotation.py` (soft-loss, rank SHIP&gt;NULL tighter DD, neg score select)
- `reports/bootstrap/STRESS_ROTATION.json` last_rescore flipped_off=13 n_ok=114
- `reports/bootstrap/QUALITY_SHORTLIST.json` generated_at 2026-07-23T04:03:14Z top BAC/CCL SHIP
- `.cache/platform/quality_worker/cycle_LATEST.json` stamp 20260723T035127 ok
- `just trader-status` ~21:00 PDT

## DURABLE

- Repo: ingest + selector + tests + shortlist + rotation ledger + wake + NEXT_SEED + readiness
- Skill: trader-self-evolution pitfall + quality-acceleration ranking rows
- No hyp yaml commit (worker thrash surface)

## VERIFICATION

```text
.venv/bin/python -m pytest tests/test_stress_rotation.py -q  → 4 passed
.venv/bin/python scripts/trader_ingest_stress_rotation.py --rescore-only --refresh-shortlist --source continuum_judgment_20260722T2100
  → flipped_off=13 n_ok=114 top=BAC_SHIP,CCL_SHIP,BAC,AAL…
.venv/bin/python scripts/trader_select_stress_hyps.py --json
  → leaders BAC+CCL + unstressed pos NFLX/PLTR/AAL/SNAP
```

## INTEGRATION

Selective commit on main: scripts/tests/bootstrap shortlist+ledger+NEXT_SEED+wake+readiness.  
Leave `hypotheses.yaml` and worker cache dirt unstaged.

## LESSON

`cost_hold=true` with **soft_loss@5% (neg slip pnl)** still polluted capital_path. Ranking **max_dd before slip verdict** let NULL@positive with slightly tighter DD own stress_priority #2 and waste re-stress regression slots that should stay on SHIP@5% DNA. Dry evolve **SHIP tag + negative composite** must not enter multi-leg B3/B4 selection.

## NEXT SEED

`manage_open_paper_campaign` — HOLD BAC+PLTR through B6 sessions; worker stresses BAC/CCL SHIP leaders + positive-score fresh multi-leg. ken_required=false.

## GATES

none (Ken-only: gateway_up | LIVE_PACKET_arm | fund_3k_at_packet)

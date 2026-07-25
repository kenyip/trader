# WAKE — 2026-07-24T2106 continuum judgment / coach

WAKE: 2026-07-24 ~21:06 PDT / 00:06 ET Sat (weekend post-close)  
PHASE: PAPER  
SLEEVE: 3000 plan · cash≈500 · live_armed=false  
CHOSE: **Improve search system** — toxic-family 0-challenge + non-cooled-first fill + dens_bucket shortlist rank  
OUTCOME: search-system repair (not STRATEGY_ADVANCED; no pack-grade)  
STRATEGY ADVANCEMENT: false  
SEARCH INFORMATION: empty stress queue beats PLTR/NFLX CCS B3/B4 burn; shortlist re-led by AAL dens1 tight-DD + F + BAC  

## Orient

- EDGE: worker ON (pid 73002 · hb_age~0 · cycle_n≈395–396) all rc=0; wall~436s; book_full campaign skip
- Thrash: selector **n=2 only toxic challenges** (NFLX CCS + PLTR CCS) while leaders TTL-skipped; recent 6h PLTR CCS fail=50 / NFLX CCS fail=43 / 0 ok; last cycle 0/4 capital_path (soft NULL@~0 dominant)
- Shortlist was BAC dens0 monoculture + TSLL/CCL; elite dens0 SHIP@5 almost all BAC; AAL dens1 dd≈34 never surfaced (raw dens rank)
- ROBOT: paper 3/3 · open=2 BAC+PLTR · risk=$359 · weekend HOLD (NEXT manage) — Mon RTH owns marks
- ARM: WAIT Ken · no pack-grade · no live/shadow/arm
- Jarvis guidance (2026-07-15 burst-stop) critic context only; continuum quality ops continue

## DID

1. **`trader_select_stress_hyps`**:
   - `_family_challenge_toxic`: recent fails≥8 & 0 ok **or** lifetime fails≥20 & 0 ok → **0 challenge slots**
   - Fill **non-cooled first**; cooled challenges only after
   - Rank fresh with **prior capital_path_ok family** before vanity score
   - CLI: `--toxic-fail-min` / `--lifetime-fail-min`
2. **`trader_ingest_stress_rotation` shortlist rank**: dens_bucket ties dens 0–1 so tight-DD dens1 can beat loose dens0; raw dens micro-tie after DD
3. Tests: toxic zero-challenge + dens_bucket AAL leader + prior suite — **14 passed**
4. Live: `--rescore-only --refresh-shortlist` → shortlist leaders **AAL PCS dens1 dd34** ×3 + BAC dens0 + **F PCS dens1**; selector **n=0** with `skipped_family_toxic` NFLX/PLTR (honest empty queue)
5. Paper: open BAC `paper_2f78815a0614` + PLTR `paper_c80aaa1cab46` — no mid-close; weekend gap watch Mon RTH

## Pre → post

| Surface | Before | After |
|---|---|---|
| Stress queue | n=2 NFLX+PLTR CCS challenges only | n=0; toxic skipped (empty > burn) |
| Shortlist multi leaders | BAC dens0 ×3 + TSLL + CCL | **AAL dens1 tight-DD ×3** + BAC dens0 ×2 + **F dens1** |
| Toxic families | 1 challenge/cycle forever | hard-blocked until oks appear / window clears |

## Evidence

- Selector live: `skipped_family_toxic` = nflx_bf109ec0, pltr_1efcc394/887e5ead/efe4c374; `n=0`
- Shortlist: `reports/bootstrap/QUALITY_SHORTLIST.json` top AAL `32c7191f` / `a337c5ac` / `972ca6be`
- Ledger: `reports/bootstrap/STRESS_ROTATION.json` n_ledger≈1902 · capital_path_ok=283
- Last cycle ingest: SMCI/NFLX/PLTR CCS + PLTR PCS all capital_path_ok=false (soft NULL / B3 fail / NEEDS)
- Tests: `pytest tests/test_stress_rotation.py tests/test_evolve_vanity_ship_registry.py -q` → **14 passed**
- Paper: BAC+PLTR working · risk $359.18 · sessions 3/3

## DURABLE

- Repo: selector toxic + non-cooled-first + prior rank; shortlist dens_bucket; tests; shortlist/ledger refresh; this wake
- Skill: pitfall — cool 1-challenge still burns toxic families every cycle → escalate to 0-challenge; dens0 vanity can hide dens1 tight-DD
- No hyp yaml commit (worker owns)

## VERIFICATION

- 14 passed stress_rotation + evolve_vanity
- Shortlist risk leaders AAL dd34; toxic not in stress csv
- No live/arm/shadow

## INTEGRATION

- See commit on main (selective: scripts/tests/shortlist/ledger/wake/NEXT — not hypotheses.yaml)

## LESSON

Future Trader: **cool ≠ enough** when a family has dozens of recent fails and zero capital_path_ok — hard-block challenges. Prefer empty B3/B4 queue over guaranteed soft-NULL burns. Rank shortlist so dens1 + much tighter window DD can lead over dens0 loose-DD clones.

## NEXT SEED

`manage_open_paper_campaign` (ken_required=false) — weekend HOLD open BAC+PLTR; Mon RTH mark/manage. Worker continues evolve; stress skips toxic until non-toxic unstressed SHIP appears (prefer AAL/F/BAC/TSLL/CCL families with prior oks).

## GATES

none (Ken only for LIVE_PACKET / $3k / arm)

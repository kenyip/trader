# WAKE — 2026-08-14T0900 continuum judgment / coach

WAKE: 2026-08-14 ~09:00 PDT / 12:00 ET / 16:00 UTC  
PHASE: **SHADOW** ops + PAPER manage + EDGE coach  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
ECONOMIC MECHANISM: time-decay defined-risk multi-leg income (paper research) + MCP single-leg first-live lane  
CANDIDATE/FAMILY SCOPE: paper book integrity under Ken-frozen EDGE (pack-grade INTC IC spray)  
FUNNEL: F4_OBSERVED_PAPER manage + ROBOT book-law (not new F0)  
PREDECLARED FALSIFIER: spine `--execute-paper` can still mint a second same-symbol working order after `PaperBroker.place_limit` book guards  
OUTCOME: **BLOCKER_REMOVED_AND_RETESTED**  
STRATEGY ADVANCEMENT: false (no new capital_path leader; F IC dens0 still leads research; first-live still SNAP CSP)  
SEARCH INFORMATION: true — Ken latch still honored; 2-min pack-grade handoff sprayed 3 identical INTC ICs after a false BAC `pt40`/`spot_intrinsic` close  
NO-ADVANCE STREAK: n/a (coach ops; no F0 BUILD streak)  
CHOSE: **stop same-symbol paper spray + commit PaperBroker book guards** — honor Ken freeze; do not prune; do not absorb pack_grade WIP

## Orient

- Status: Phase SHADOW · IN_PROGRESS · search EDGE_FROZEN_KEN (35%) · ROBOT paper=ok shadow=PASS · ARM blocked
- Worker ON · cycle_n=23193 · hb_age≈0.01h · all phase rc=0 · wall~37s · registry 6,000,873 · EDGE Ken-frozen (evolve + prove skipped; research + paper only)
- Ken latch: `~/.local/state/jarvis/trader-guidance/edge-search-freeze.json` (`skip_evolve=true`, unfreeze=explicit Ken only)
- NEXT prior: `manage_open_paper_campaign` · campaign-thinned 16:00Z then rewritten with 3 INTC working
- Research leaders: F IC dens0; AAL/BAC PCS; first-live SNAP CSP fit_3k (n=109, bp≈$494)
- Last RTH 11:31 ET: HOLD BAC `paper_b5422618e55d` mid +10.18 / adv +8.68 vs PT 12.98
- Concurrent dirty tree (pack_grade / campaign.sh / promote / paper_handoff / opportunity_watcher / trader_paper_mark.py) left unstaged
- Jarvis 2026-07-15 BUILD burst-stop — critic only; not this coach loop

## Diagnosis (highest leverage)

| Signal | Finding |
|---|---|
| 2100 coach | Ken-frozen tight cycle already skips prove wave; wall~37s healthy |
| EDGE | still `ken_first_close_freeze_edge_search` — do not prune 6.0MB |
| Ledger 15:55Z | BAC closed `pt40` + `spot_intrinsic` (not DNA dual-PT; mid was still under $12.98) |
| 15:55–16:03Z | spine INTC IC place every ~2 min; two instant `pt40` closes then 3 working clones |
| Campaign | `placed=[]` / book_full manage — not the sprayer |
| Handoff 16:05Z | 4th place blocked only by RiskGovernor `open_order_count 3 >= 3` / risk 566+189>750 |
| Root | `PaperBroker.place_limit` had no one-open-per-symbol / max_concurrent=2 |

Worker is healthy. EDGE is intentionally frozen. Highest leverage is ROBOT book law, not another EDGE digest.

## DID

1. Added `trader_platform/execution/paper_book_guards.py` (one-open-per-symbol + max_concurrent=2; smoke stubs exempt)
2. Hooked `PaperBroker.place_limit` so campaign, handoff, and pack-grade execute share the same book law
3. Tests: `tests/test_paper_book_guards.py` (same-symbol refuse, concurrent cap, smoke exempt)
4. Canceled spray extras `paper_546143354976` + `paper_ea3350fe1422` (`same_symbol_spray`); kept oldest `paper_b5b969c4a65f`
5. In-wake retest: same-symbol INTC probe `ok=false` / `one_open_per_symbol INTC`
6. Skill `references/quality-acceleration.md`: pack-grade spray fingerprint + fix
7. No evolve / no prune / no live / no arm / no hyp yaml / no pack_grade absorb
8. Remaining INTC IC HOLD — spot~103, short put 87.5 / short call 122.5 both deep OTM; DNA manage is next RTH's job
9. BAC stays closed (false `pt40`); do not reopen

## EVIDENCE

- `.cache/platform/paper_ledger.json` events 15:55–16:03Z (BAC close + INTC spray)
- `.cache/platform/coach_20260814T1200_cancel.json` (before 3 → after 1; probe refused)
- `.cache/platform/spine/paper_handoff_LATEST.json` (16:05Z risk deny on 4th)
- `trader_platform/execution/paper_book_guards.py`
- `tests/test_paper_book_guards.py`

## DURABLE

- Paper book law belongs in `PaperBroker.place_limit`, not only `trader_paper_campaign.sh`.
- `spot_intrinsic` remaining credit is not DNA dual-PT. Do not close a deep-OTM credit because underlying vs short-put intrinsic looks like 40% captured.
- Ken first-close freeze still outranks 6.0MB; do not prune-to-unfreeze.

## VERIFICATION

- `pytest tests/test_paper_book_guards.py tests/test_risk_governor.py` → **10 passed**
- live cancel extras ok; working=1 (`paper_b5b969c4a65f`)
- live same-symbol probe → `paper_book_guard: one_open_per_symbol INTC already working`
- `just trader-status` still `search EDGE_FROZEN_KEN` · do-not-prune warning
- live_armed=false · ken_required=false
- `trader_platform.smoke_test` failed later at shadow `rh_review` (pre-existing / unrelated to place guards; paper lifecycle asserts in that file still passed)

## INTEGRATION

Selective commit: paper_book_guards + place_limit hook + tests + wake/INDEX/LATEST + NEXT_SEED + readiness. Concurrent pack_grade / campaign.sh / promote / paper_handoff / opportunity_watcher / trader_paper_mark.py WIP left unstaged. No hypotheses.yaml.

## LESSON

Future coach: if paper book jumps from 1 BAC to N identical spine seats while campaign `placed=[]`, check watcher/handoff `--execute-paper` and `PaperBroker` book guards — not quality_cycle. EDGE stays Ken-frozen until explicit Ken unfreeze.

## NEXT SEED

`manage_open_paper_campaign` · ken_required=false · HOLD INTC IC `paper_b5b969c4a65f` (ml~$188.72; short 87.5p/122.5c) until next RTH DNA ladder · extras canceled · EDGE stays Ken-frozen · no densify · ARM Ken only

## GATES

none · ARM still Ken LIVE_PACKET only · EDGE unfreeze Ken only

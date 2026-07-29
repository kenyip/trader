# WAKE — 2026-07-29T0904 continuum judgment / coach

WAKE: 2026-07-29 ~09:00–09:05 PDT  
PHASE: PAPER  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
CHOSE: **Improve search system** — hot fail-streak toxic + shortlist risk-profile twin skip  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED (search thrash gate; not strategy funnel stage)  
STRATEGY ADVANCEMENT: false  
SEARCH INFORMATION: Empty stress queue was healthy most cycles; waste was evolve minting AAL CCS full-history SHIP that dies B4 soft NULL@5%. Lifetime ok-rate ~22% never tripped classic toxic.  
NO-ADVANCE STREAK: n/a (coach / ops)

## Orient

- EDGE: pack-grade shortlist_dna_multi quality_pass; research leader AAL PCS `89f8b695`; first-live SNAP CSP fit_3k (n=107 bp≈$429)
- ROBOT: paper open=2 risk=$264.24 · sessions 6/3; shadow PARTIAL
- Worker ON (cycles~2443; hb fresh; yaml ~4.7MB under 6MB cap)
- Selector **n=0** most recent cycles (35/40 empty) — leaders TTL-skipped; empty trusted (no leader re-burn)
- Intermittent stress = fresh evolve creates only (e.g. `hyp_dna_aal_call_credit_spread_4d35f70c` → B3 hold, B4 NULL slip−$60 → capital_path_ok=false)
- 24h family burns: AAL CCS 27 fail / 6 ok; SOFI CCS / PLTR PCS also hot-fail; AAL PCS still productive (68 ok)
- Shortlist had exact AAL PCS dens/dd/pnl twins occupying seats
- Jarvis 2026-07-15 BUILD burst-stop guidance — superseded by PAPER continuum; not binding on coach residual
- NEXT: `manage_open_paper_campaign` (book 2/2) — RTH owns marks; coach did not re-mark this tick

## Decision charter

- ECONOMIC MECHANISM: n/a — search-system efficiency (stop doomed family mint/stress)
- CANDIDATE/FAMILY SCOPE: AAL×call_credit_spread hot streak; shortlist multi-leg twins
- FUNNEL: ops / EDGE tooling (not F-stage candidate move)
- PREDECLARED FALSIFIER: if last 8 stresses of a family have ≥6 capital_path fails and ≤1 ok (24h), create+queue must hard-block; identical dens/dd/pnl shortlist twins must collapse to one seat
- Decision: **ship hot-streak toxic + twin skip; restart worker; keep paper manage NEXT**

## DID

1. `just trader-status` — EDGE OK / ROBOT paper 2 open / shadow PARTIAL / worker ON
2. Mined cycle_LATEST + selector + STRESS_ROTATION: empty queue OK; AAL CCS clone thrash diagnosed
3. Extended `stress_family_policy.family_challenge_toxic` with `family_hot_fail_streak_toxic` (lookback 8 / fail_min 6 / max_ok 1 / 24h)
4. Shortlist refresh skips identical dens/dd/pnl/slip risk-profile twins
5. Tests: evolve hot-streak create skip + policy unit + shortlist twin — **19 passed**
6. Live: AAL CCS / SOFI CCS / PLTR PCS streak-toxic=True; AAL PCS / BAC PCS healthy
7. `--rescore-only --refresh-shortlist` — twin `e1f69a5d` dropped from leaders; stress_priority → `89f8b695` + `4ae7fe1b`
8. Restarted quality_worker (new pid) so evolve apply loads patched policy
9. No live/arm/shadow promote; no hyp yaml commit

## Evidence

- policy: `trader_platform/stress_family_policy.py`
- shortlist: `scripts/trader_ingest_stress_rotation.py` + `reports/bootstrap/QUALITY_SHORTLIST.json`
- tests: `tests/test_evolve_toxic_family_registry.py`, `tests/test_stress_rotation.py`
- cycle sample: `.cache/platform/quality_worker/cycle_LATEST.json` (4d35 AAL CCS stress then empty)
- ledger sample: `hyp_dna_aal_call_credit_spread_4d35f70c` capital_path_ok=false B4 soft_loss −60.13

## VERIFICATION

```text
.venv/bin/python -m pytest tests/test_evolve_toxic_family_registry.py tests/test_stress_rotation.py -q
→ 19 passed
Live family_challenge_toxic(AAL, call_credit_spread)=True
Worker restarted; shortlist_hyps empty on post-restart cycle
```

## DURABLE

- Repo: hot fail-streak toxic shared by selector + evolve create gate; shortlist profile-twin skip
- Skill `trader-self-evolution` pitfalls updated (AAL CCS streak thrash; shortlist twins)
- No doctrine rewrite beyond honesty string on shortlist

## INTEGRATION

- Selective commit: policy + ingest + tests + shortlist + wake/INDEX/LATEST + NEXT_SEED
- Leave `hypotheses.yaml` / worker tmp / multi reprove thrash unstaged unless already clean

## LESSON

- Lifetime ok-rate toxic misses **hot clone thrash**: historic oks keep the family “healthy” while the newest create→B4 path is almost all soft fails. Streak gate stops max_create waste so non-streak families can fill the queue.
- Empty stress queue with TTL-fresh leaders is success, not a missing fallback.
- Paper book 2/2 remains manage residual; coach improves EDGE muscle in parallel.

## NEXT SEED

`manage_open_paper_campaign` · ken_required=false — RTH: re-mark AAL CCS + BAC PCS; CLOSE only on DNA ladder; STAND_ASIDE new while 2/2. Worker continues with hot-streak toxic (no new AAL CCS mint while streak hot). Shadow still PARTIAL — next non-RTH progress pack may add non-stub shadow day.

## GATES

none (Ken only: gateway / LIVE_PACKET arm / $3k at packet)

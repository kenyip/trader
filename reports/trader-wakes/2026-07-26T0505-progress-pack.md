# WAKE — 2026-07-26 progress pack (first-live + multi-reprove + shadow)

WAKE: 2026-07-26 ~05:05 UTC (off-hours continuum / Ken Grok session)  
PHASE: PAPER  
SLEEVE: 3000 plan · cash≈500 · live_armed=false  
CHOSE: **Ship dual-lane progress tools** so next Trader wakes run the go-live funnel faster without re-deriving  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED (tooling + status surface + handoff; not STRATEGY_ADVANCED)  
STRATEGY ADVANCEMENT: false  
SEARCH INFORMATION: first-live ranker, shortlist-aware multi-reprove, deliberate shadow path

## Orient

- EDGE: quality_worker ON; research shortlist multi-leg AAL/BAC PCS; multi-symbol quality_pass=0
- ROBOT: paper BAC+PLTR open; shadow incomplete (no deliberate window)
- ARM: WAIT Ken
- Gap: multi-leg research leaders ≠ MCP placeable first-live; multi-reprove ignored shortlist symbols; shadow no recipe

## DID

1. **First-live lane** — `trader_platform/first_live_lane.py` + `just trader-first-live-lane`  
   - Ranks single-leg SHIP/NEEDS from evolve_sim + research spot BP  
   - Writes `reports/bootstrap/FIRST_LIVE_LANE.json`  
   - Status FIRST-LIVE SEATS (leader class: SNAP/F/AAL/TSLL fit_3k; NFLX/PLTR near-miss oversized)
2. **Multi-symbol re-prove** — `--from-shortlist` prepends QUALITY_SHORTLIST symbols (AAL/BAC/…)  
   - Ran: book includes AAL/BAC; still n_quality_pass=0 (honest)
3. **Shadow rehearsal** — `just trader-shadow-rehearsal`  
   - History + LATEST; stub=PARTIAL only; PASS needs multi-session **non-stub**
4. **Status + run-now** — dual boards; `just trader-run-now progress`
5. **Trader knowledge** — skill/MEMORY/SOUL/docs pin so next coach/RTH uses tools without rediscovery
6. Tests: first-live, shadow, multi-shortlist, go-live, bootstrap — **20 passed**

## Evidence

- Code: `trader_platform/first_live_lane.py`, `scripts/trader_{first_live_lane,shadow_rehearsal}.py`, bootstrap multi pack, go_live_status, Justfile, run_now
- Artifacts: `FIRST_LIVE_LANE.json`, `MULTI_SYMBOL_REPROVE.json` (from-shortlist), `.cache/platform/shadow/LATEST.json`
- Hermes: `~/.hermes/profiles/trader/skills/trading/trader-self-evolution/`, MEMORY, SOUL

## DURABLE

- Repo: progress tools + status dual-lane + docs/TRADER_AGENT_PROFILE
- Skill/memory: orient + coach + anti-patterns for first-live / multi-reprove / shadow honesty
- No hyp yaml commit (worker owns)

## VERIFICATION

```text
.venv/bin/python -m pytest tests/test_first_live_lane.py tests/test_shadow_rehearsal.py \
  tests/test_multi_symbol_shortlist_book.py tests/test_go_live_status_simple.py \
  tests/test_bootstrap.py -q
# 20 passed
```

## INTEGRATION

- Selective commit of code/tests/docs/wake/seed/first-live report — not hypotheses.yaml / stress thrash

## LESSON

Future Trader: **do not** re-derive first-live from multi-leg shortlist or invent shadow PASS from stub/audit. Use progress pack recipes every coach/off-hours wake when funnel is stuck.

## NEXT SEED

RTH: `manage_open_paper_campaign` (BAC+PLTR). Off-hours/coach: refresh first-live + multi-reprove `--from-shortlist` + non-stub shadow ticks toward multi-session PASS. Prefer closes when DNA rules fire. No Ken for residual.

## GATES

none (Ken only for LIVE_PACKET / $3k / arm)

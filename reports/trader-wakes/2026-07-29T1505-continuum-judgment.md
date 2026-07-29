# WAKE — 2026-07-29T1505 continuum judgment / coach

WAKE: 2026-07-29 ~15:01–15:06 PDT  
PHASE: PAPER  
SLEEVE: 3000 plan · test cash≈500 · live_armed=false  
CHOSE: **Unblock EDGE search** — off-hours registry prune (bloat skipped both evolves) + harden prune to force open-paper DNA  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED (search muscle; not strategy funnel stage)  
STRATEGY ADVANCEMENT: false (new AAL PCS stress survivor is secondary dens2 clone — not leader move)  
SEARCH INFORMATION: Worker cycles green but `registry_bloat_skip_evolve` at 6,001,614b > 6MB — zero DNA mint for many cycles; stress queue empty (TTL leaders) so EDGE was spinning research+multi only.  
NO-ADVANCE STREAK: n/a (coach / ops)

## Orient

- EDGE: pack-grade shortlist_dna_multi quality_pass; research leader AAL PCS `5fa0eac8`; first-live SNAP CSP fit_3k n=107 bp≈$429
- ROBOT: paper open=2 risk=$264.24 · sessions 6/3; shadow PARTIAL (1 non-stub session day)
- Worker ON before coach: cycles~3018; wall ~18s; **both evolves skipped** `registry_bloat_skip_evolve`
- Selector n=0 (leaders TTL-fresh `5fa0eac8`/`89f8b695`; SOFI CCS toxic skip) — empty queue healthy but **no new fuel without evolve**
- Shortlist: AAL PCS dens1×3 + BAC PCS dens0×3 + MCP first-live tier (ghost registry ids normal)
- Paper overnight: AAL CCS `5a213de0` + BAC PCS `c7d09885` still working; after-close manage not this loop
- Prior coach 09:04: hot-streak toxic + twin skip — still good; bloat is the new blocker
- Jarvis 2026-07-15 BUILD burst-stop — critic context only; not binding on PAPER continuum

## Decision charter

- ECONOMIC MECHANISM: n/a — restore evolve mint path so B3/B4 rotation can see fresh multi-leg DNA
- CANDIDATE/FAMILY SCOPE: registry size gate + prune keep-set integrity (open paper + shortlist)
- FUNNEL: ops / EDGE tooling
- PREDECLARED FALSIFIER: after stop→prune→start, next cycle must run ≥1 evolve lane (not bloat-skip) and must keep open-paper hyp ids; optional create→B3/B4 must complete without yaml snap-back to ≥6MB
- Decision: **prune max_keep=400; force open-paper strategy_ids; report first-live ghosts; restart worker; retest**

## DID

1. `just trader-status` — EDGE OK / ROBOT paper 2 open / shadow PARTIAL / worker ON; NEXT manage_open_paper_campaign
2. Mined cycle_LATEST: evolve_dr+csp **skipped** registry 6,001,614b; shortlist_hyps empty; stress_queue_empty ledger-only refresh
3. Dry-run prune → 1466→400 keep shortlist+paper seeds
4. `just trader-quality-worker stop` + orphan pkill (clean)
5. `scripts/trader_prune_hyp_registry.py --max-keep 400` → **6.00MB→1.83MB**, n=1466→400; backup `.cache/platform/registry_prune/hypotheses.yaml.bak_20260729T220245`
6. Verified open paper DNA kept (`5a213de0`, `c7d09885`); multi-leg shortlist kept; FIRST_LIVE ids are **ghosts** (never in registry / bak) — lane is sim-derived, not hyp rows
7. Hardened prune: `_paper_open_strategy_ids()` force tier-0; ghost first-live counters; late-bound ledger path (monkeypatch-safe)
8. Tests: `tests/test_prune_hyp_registry.py` — **2 passed**
9. Worker restart pid=97630; cycle `20260729T220441`:
   - evolve_dr **ran** 7.97s (registry 1.83MB); CSP alternate skip intentional
   - created `hyp_dna_aal_put_credit_spread_e4ad3be2`
   - B3 hold SHIP n=94 pnl~$202 dd~$34 ml~$40; B4 **SHIP@5%** pnl~$58.94 → `capital_path_ok=true`
   - dens_neg=2 → correctly **below** dens1 AAL / dens0 BAC leaders (not vanity promote)
   - NFLX CCS full-history SHIP score~144 **not** registered (toxic/ship gates) — good
10. No live/arm/shadow promote; no densify bag; paper ledger untouched

## Evidence

- prune receipt: n_before=1466 n_after=400 bytes 6001614→1831566; later dry-run `n_paper_open_forced=2` `n_first_live_ghosts=12`
- cycle: `.cache/platform/quality_worker/cycle_LATEST.json` (post `20260729T220441`+)
- evolve: `.cache/platform/quality_residual/evolve_dr_20260729T220441.log`
- stress: `regime_20260729T220441.json` + `cost_20260729T220441.json`
- rotation: `reports/bootstrap/STRESS_ROTATION.json` → `e4ad3be2` capital_path_ok
- code: `scripts/trader_prune_hyp_registry.py` + `tests/test_prune_hyp_registry.py`

## VERIFICATION

```text
just trader-quality-worker stop → stopped
.venv/bin/python scripts/trader_prune_hyp_registry.py --max-keep 400 --json
  → ok n=1466→400 bytes 6.0MB→1.83MB
.venv/bin/python -m pytest tests/test_prune_hyp_registry.py -q → 2 passed
just trader-quality-worker start → pid 97630
cycle 20260729T220441 evolve_defined_risk skipped=false sec≈8 rc=0
  (not registry_bloat_skip_evolve)
e4ad3be2 B4 SHIP@5% capital_path_ok=true dens=2
wc -c hypotheses.yaml → ~1.84MB (stable, no snap-back)
```

## DURABLE

- Repo: prune force-keeps **open paper ledger** strategy_ids; reports first-live **ghost** count (sim DNA ≠ registry rows)
- Registry deliberately capped ~400 / ~1.8MB so evolve stays under 6MB gate
- Skill pitfall: bloat skip looks like healthy empty stress queue — measure evolve skipped reason + registry_bytes
- No doctrine north-star rewrite

## INTEGRATION

- Selective commit: prune script + tests + pruned hypotheses.yaml + shortlist/rotation/wake/INDEX/LATEST + NEXT_SEED
- Leave worker tmp / unrelated dirt unstaged

## LESSON

- Green cycles with wall~18s and empty stress queue can still mean **EDGE is dead** if both evolves bloat-skip. Coach must read `phases.evolve_*.reason`, not only rc=0 / shortlist_hyps empty.
- FIRST_LIVE_LANE hyp_ids are often unregistered sim DNA — prune must not treat ghost sample as forced keep, and must **always** force open paper ledger ids so overnight prune cannot brick manage.
- Fresh AAL PCS clone with dens2 SHIP@5% is useful rotation fuel, not an automatic shortlist leader displace (dens_bucket + DD rank still holds).

## NEXT SEED

`manage_open_paper_campaign` · ken_required=false — next RTH: re-mark AAL CCS + BAC PCS; CLOSE only on DNA ladder (profit_target dual-gate / delta_breach / defined_loss); STAND_ASIDE new while 2/2. Worker continues with evolve unblocked. Optional off-hours: non-stub shadow day 2/2 (`just trader-shadow-rehearsal`) when not thrashing paper manage. Do **not** recreate densify bag.

## GATES

none (Ken only: gateway / LIVE_PACKET arm / $3k at packet)

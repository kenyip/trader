# WAKE — 2026-07-28T1439 continuum judgment / coach

WAKE: 2026-07-28 ~14:39 PDT  
PHASE: PAPER  
SLEEVE: 3000 plan · cash≈500 · live_armed=false  
CHOSE: **Repair stress-selection thrash** — low-ok-rate toxic + ghost-hyp B3/B4 abort + leader TTL 48h  
OUTCOME: BLOCKER_REMOVED_AND_RETESTED (search system; not strategy funnel advance)  
STRATEGY ADVANCEMENT: false  
SEARCH INFORMATION: NFLX CCS lifetime ~585f/4ok was never toxic under zero-ok rule → burned every cycle; ghost XOM hyp_id aborted whole B3/B4 batches for ~11 cycles; AAL leaders past 24h TTL monopolized slots  
NO-ADVANCE STREAK: n/a (coach ops)

## Orient

- EDGE: pack-grade via shortlist_dna_multi; research AAL PCS leaders; first-live SNAP CSP fit_3k
- ROBOT: paper **flat** after RTH BAC profit_target + PLTR delta_breach (5/3 sessions); shadow PARTIAL stub-only
- Worker ON (pid live, cycle in flight) but **unhealthy muscle**: cycle_n≈885 wall~1890s; evolve_dr/csp rc=124; campaign rc=124; regime/cost rc=1
- Heartbeat shortlist repeatedly: AAL×2 + NFLX CCS + ghost XOM PCS
- hyp yaml ~44.7MB thrash (worker) — not committed
- Jarvis guidance 2026-07-15 BUILD burst-stop — superseded by PAPER continuum coach

## Decision charter

- ECONOMIC MECHANISM: n/a — selector/search throughput repair
- CANDIDATE/FAMILY SCOPE: stress rotation toxic policy + pcs_* ghost resilience
- FUNNEL: search ops (not F0–F4 strategy)
- PREDECLARED FALSIFIER: NFLX CCS must classify toxic under live ledger; ghost hyp must not force batch rc=1; tests green
- Decision: ship policy + soft-skip + TTL; empty stress queue beats toxic burn

## DID

1. `just trader-status` — EDGE OK / ROBOT paper ok open=0 / shadow PARTIAL / ARM wait
2. Diagnosed cycle_LATEST: stress hyps include missing `hyp_dna_xom_put_credit_spread_54c72849` → pcs_regime/cost **missing hyp → rc=1** (whole batch)
3. STRESS_ROTATION family stats: NFLX CCS **585 fail / 4 ok** not toxic under zero-ok; PLTR/SMCI already toxic; AAL/BAC healthy
4. Patched `trader_platform/stress_family_policy.py`: `_hopeless_fail_ok` — toxic when fails≥floor **and** ok-rate ≤ `max_ok_rate` (default 0.05)
5. Patched `scripts/trader_select_stress_hyps.py`: delegate toxic to shared policy; ghost hyp filter; leader TTL default **48h**; `skipped_missing_hyps`
6. Patched `pcs_regime_stress.py` / `pcs_cost_stress.py`: soft-skip missing hyps; fail only if none living
7. Patched `trader_quality_cycle.py` + `configs/quality_worker.env`: `TRADER_QC_LEADER_TTL_HOURS=48`, `TRADER_QC_TOXIC_MAX_OK_RATE=0.05`
8. Tests: low-ok-rate toxic, ghost drop, evolve toxic timestamps fixed
9. Live check: NFLX/XOM/PLTR/SMCI toxic=True; AAL/BAC toxic=False; AAL leaders fresh@48h
10. No live/arm/shadow promote; no hyp yaml commit

## Evidence

- cycle: `.cache/platform/quality_worker/cycle_LATEST.json` stamp 20260728T203647
- stress fail logs: `quality_residual/regime_stress_*.log` / `cost_stress_*.log` (“missing hyps”)
- ledger: `reports/bootstrap/STRESS_ROTATION.json`
- code: `stress_family_policy.py`, `trader_select_stress_hyps.py`, `pcs_*_stress.py`, `trader_quality_cycle.py`, `quality_worker.env`
- tests: `tests/test_stress_rotation.py` (+2), `tests/test_evolve_toxic_family_registry.py`

## VERIFICATION

```
.venv/bin/python -m pytest \
  tests/test_stress_rotation.py::test_family_challenge_toxic_blocks_zero_challenge \
  tests/test_stress_rotation.py::test_family_challenge_toxic_low_ok_rate_blocks_legacy_flukes \
  tests/test_stress_rotation.py::test_select_drops_ghost_hyp_ids_missing_from_registry \
  tests/test_evolve_toxic_family_registry.py \
  tests/test_quality_cycle_cadence.py -q
→ 12 passed
```

Live toxic: NFLX CCS True; AAL PCS False.

## DURABLE

- Skill pitfall row: low-ok-rate toxic + ghost filter + 48h leader TTL
- Env knobs for next worker cycles (restart/ensure picks up env on next cycle start — worker sources env each cycle if script does)

## LESSON

Zero-ok toxic is insufficient when ledger keeps a handful of legacy soft capital_path_ok. One ghost hyp_id must never abort multi-hyp B3/B4. Prefer empty stress queue over NFLX CCS vanity burn.

## NEXT SEED

`just trader-shadow-rehearsal` non-stub multi-session (ROBOT blocker) after next quality cycle confirms stress rc≠1 / NFLX absent from shortlist_hyps; RTH scout capital-fit OPEN_* on empty book. ken_required=false.

## GATES

none (no Ken)

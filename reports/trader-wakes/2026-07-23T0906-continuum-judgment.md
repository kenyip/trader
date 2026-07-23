# WAKE — 2026-07-23T0906 continuum judgment / coach

WAKE: 2026-07-23 ~09:06 PDT / ~12:06 ET (RTH)  
PHASE: PAPER  
SLEEVE: 3000 plan · cash≈500 · live_armed=false  
CHOSE: **fix shortlist rank falsy-zero bug + free B3/B4 budget from fresh leaders**  
OUTCOME: search-system improvement (not strategy advancement)

## Orient
- EDGE: worker ON (bash pid 2700 + quality_cycle child); hb cycle_n≈88 / status cycles≈367; **no pack-grade**
- ROBOT: paper **2/3** sessions · open=2 · risk=$359.18
- ARM: WAIT Ken only
- Market ~12:02 ET: SPY 737.86 (−1.3%) · QQQ 691.62 (−1.9%) · IWM 291.36 (−0.8%) · AAL 13.54 (−8.5%) · BAC 60.90 (−1.2%) · PLTR 121.82 (−2.2%)
- Ledger: **1108→1114** stressed hyps · **232→234** capital_path_ok — rotation not stuck on identical artifact sizes
- Latest cycle 155435: rejected NFLX CCS 3723bb92 (B3 dens15), CCL CCS 4012c84f (NULL@0); BAC PCS a498f56b capital_path (NULL@+31 slip)

## Paper mark (secondary; NEXT was manage)

| Order | Sym | Strikes | Spot | vs short | Legs mark | MTM≈ | ml | Action |
|---|---|---|---:|---:|---|---:|---:|---|
| paper_2f78815a0614 | BAC PCS | 60/58p Aug7 | 60.90 | **+$0.90 OTM** | short 0.74 / long 0.28 → debit 0.46 vs cr 0.374 | **−$8.6** (~5% ml) | 162.64 | **HOLD** |
| paper_c80aaa1cab46 | PLTR PCS | 122.5/120p Aug7 | 121.82 | **−$0.68 ITM** | short synth avg(122p 7.75,123p 8.30)=8.025 / long 6.78 → debit 1.245 vs cr 0.535 | **−$71** (~36% ml) | 196.54 | **HOLD_elevated** |

PLTR improved vs 11:31 (−$79 / −$1.67 ITM). Still defined-risk; long OTM; no force-close. **STAND_ASIDE** new (book 2/2).

## Coach loop — highest leverage

### Bug (claim-invalidating ranking)
`refresh_shortlist_from_ledger` used `int(e.get("dense_neg_ge3") or 99)`.  
**Python falsy-zero:** dens=0 → ranked as dens=**99**. True dens=0 leaders (AAL PCS 972ca6be dd=35.38 SHIP@309; BAC PCS 5575695d dd=63.09) sat at rank ~177 while dens=1 AAL CCS 5a213de0 led the shortlist.

### Fix
1. **`trader_ingest_stress_rotation.py`**: None-safe rank_key (dens/dd/slip/pnl).
2. **`trader_select_stress_hyps.py`**: skip shortlist leaders with fresh `capital_path_ok` within **24h TTL**; `min_fresh_trades=6` when n known (kill n=1 CCS waste).
3. Tests: dens0>dens1 rank; leader TTL skip.
4. Rescore + refresh shortlist → tops now dens=0 risk profile.

### After refresh
| Pri | Hyp | dens | max_dd | slip |
|---|---|---:|---:|---|
| #1 | AAL PCS `972ca6be` | 0 | 35.38 | SHIP@309 |
| #2 | BAC PCS `5575695d` | 0 | 63.09 | SHIP@201 |

Selector with 24h TTL: **skips** both leaders → stress budget on unstressed NFLX/CCL/PLTR multi-leg (n≥6).

## Durable
- Repo: rank None-safe + leader TTL + min trades + tests + shortlist refresh
- Skill: dens=0 falsy rank is a known pitfall (promote below)
- Not densify; no hyp yaml commit; no live/shadow/arm

## Verification
```
.venv/bin/python -m pytest tests/test_stress_rotation.py -q  # 6 passed
.venv/bin/python scripts/trader_ingest_stress_rotation.py --rescore-only --refresh-shortlist
.venv/bin/python scripts/trader_select_stress_hyps.py --json  # skips dens0 leaders within TTL
```

## NEXT SEED
manage_open_paper_campaign — HOLD BAC; HOLD_elevated PLTR (~36% ml, short mild ITM); STAND_ASIDE new while 2/2; worker uses corrected shortlist dens0 leaders + unstressed stress fill; 2/3→3/3 sessions. ken_required=false

## GATES
none (Ken only: gateway / LIVE_PACKET arm / $3k at packet)

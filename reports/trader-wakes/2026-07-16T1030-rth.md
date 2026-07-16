# RTH EVAL — 2026-07-16T1030 (mid-session reconfirm ~10:30 ET)

WAKE: 2026-07-16 ~07:30 PT / 10:30 ET (RTH mid-session)
PHASE: BUILD/L0 (readiness); paper-condition path only
SLEEVE: $3,000
CHOSE: RTH condition reconfirm — freshness → multi-symbol scout → capital judgment → stand-aside or paper OPEN_* only
OUTCOME: STAND_ASIDE (success). No paper place. No evolve. Same condition class as open `2026-07-16T0630` and full-day 2026-07-15.

## Strategy / capital context (not a discovery wake)

- Living quality leader: **none**
- Capital path: **empty** (0 F1/F2/F3/F4; 0 L1 seats)
- B6: still waiting non-bear capital-fit OPEN_PCS (or other defined-risk capital-fit intent)
- Overnight BUILD context (not executed here): successor epoch decision-1 close; ONE NEXT BUILD seed `YIELD_CURVE_STEEPENING_REGIONAL_BANK_FORWARD_UPDRIFT_PREFLIGHT`
- Authority: research/paper only; agentic_live blocked; no shadow/live/arm/broker
- Checkout: clean `main` at start of this RTH; reports integrated after closeout

## Orient

| Item | State |
|---|---|
| Session | Thu 2026-07-16 RTH mid (~10:30 ET) |
| Prior LATEST | `2026-07-16T0630-rth` open STAND_ASIDE 14/0/14 |
| Prior RTH class | 2026-07-15 all-day + 2026-07-16 open — STAND_ASIDE under bearish TSLL/TSLA/SMCI |
| Readiness | BUILD/L0; capital path empty; living leader none; integrated `317384d` / later main HEAD |
| Eligible hyps | 14 scout candidates (`testing`/`paper`); 230 candidate parked (not scout-eligible) |
| Real paper open risk | **0** (only `m0_stub:smoke_test` working order on TSLA — ignored) |

Jarvis guidance remains critic context (older burst-stop note; successor epoch already opened overnight). RTH does not open BUILD strategy volume.

## Freshness gate

| Symbol | Engine date | Engine spot | Live (YF) | Drift | Regime / note |
|---|---|---|---|---|---|
| TSLL | 2026-07-16 | 11.87 | ~12.21 | ~+2.88% | bearish; intraday bounce, not multi-day freeze |
| TSLA | 2026-07-16 | 388.27 | ~393.97 | ~+1.47% | bearish |
| SMCI | 2026-07-16 | 26.54 | ~25.82 | ~−2.70% | bearish |
| PLTR | 2026-07-16 | 131.97 | ~131.73 | ~−0.18% | neutral |
| XOM | 2026-07-16 | 145.73 | ~145.73 | ~0% | neutral; thin premium engine |
| AMD | 2026-07-16 | 511.27 | ~511.27 | ~0% | neutral; engine SELL_PUT but **no eligible hyp** this tick |
| BAC | 2026-07-16 | 61.63 | ~61.63 | ~0% | neutral; thin |
| SOFI | 2026-07-16 | 17.81 | ~17.81 | ~0% | neutral; thin |

**Verdict:** Freshness **pass** — session-day engine bars for all scout symbols. Intraday TSLL/TSLA/SMCI drifts are open-session moves, not stale multi-day cache. Do not re-judge opportunity on frozen prior-week bars.

## Condition scan

```text
.venv/bin/python -m trader_platform.premium_scout --symbols TSLL TSLA XOM AMD SMCI PLTR BAC SOFI --json --max-intents 5 --event rth_eval
→ n_candidates=14, n_intents=0, n_stand_asides=14, n_skipped=0

.venv/bin/python -m trader_platform.autonomy_loop --mode paper --once --dry-run --symbols TSLL TSLA XOM AMD SMCI PLTR BAC SOFI --json --event rth_eval --max-intents 5
→ n_proposals=0; agentic_enabled=false; readiness_blockers remain (agentic ~$0 capital + no options level)
```

Eligible hyp mix:

- TSLL×10 **bearish** (incl. PCS refs `b195f5fe`, `0514c2af`, `fd407d4f`)
- TSLA×1 bearish; SMCI×2 bearish; PLTR×1 **neutral**
- Reason buckets: filtered ~7 / PCS bear_aside ~3 / bear_dte=0 ~2 / premium_thin ~2

Historical PCS reference `hyp_dna_tsll_put_credit_spread_b195f5fe` (and `0514c2af`, `fd407d4f`): honest **STAND_ASIDE** — `PCS: bearish regime — stand aside (bear_dte=0; capital-fit put credit not probed)`.

**Parked (not scout-silent = no edge):** stressed `candidate` DNA (e.g. XOM CCS, AMD IC, others) remain ineligible for RTH scout by design. AMD bare engine `SELL_PUT` is undefined-risk / no eligible hyp — not a paper probe.

## Capital judgment

| Signal | Decision |
|---|---|
| OPEN_PCS / OPEN_CCS / OPEN_IC capital-fit 1-lot | **None fired** |
| PCS b195f5fe / testing PCS DNA | Bear STAND_ASIDE (`bear_dte=0`) — success |
| Naked short premium / thin credit / wheel / short_dte | STAND_ASIDE (thin/filter/bear) — would capital-reject undefined max_loss if naked intent fired |
| Real open paper risk | 0 — nothing to manage/close |

**Decision: STAND_ASIDE.** No paper place. Mid-session reconfirm of open-session class under still-bearish TSLL/TSLA/SMCI. Stand-aside is success.

## Parallel data (optional, not evolve)

Append-safe TSLL all-expiration quote snapshot at ~10:31 ET:

- Archive rows now **2698** observed
- **`n_market_dates=3`** RTH: `2026-07-13`, `2026-07-14`, `2026-07-16` (non-RTH `2026-07-11` excluded)
- `expirations_by_market_date`: **13** expirations on each of the three RTH dates (not LEAPS-only open thin print)
- **`provider_backtest_eligible=true`** (3/3 floor met)

This advances archive density plumbing only. It does **not** create a capital-fit intent, does not authorize provider-backed hist sim on this RTH tick, and does not change STAND_ASIDE. BUILD may later use the density for observed-path work under separate doctrine gates.

## Evidence

- Scout JSON: `/tmp/rth_scout_2026-07-16T1030.json` + audit `.cache/platform/premium_scout.jsonl`
- Autonomy dry-run: `/tmp/rth_autonomy_2026-07-16T1030.json` + `.cache/platform/autonomy_audit.jsonl`
- Freshness: `/tmp/rth_freshness_2026-07-16T1030.json`
- Quote density: `.cache/platform/option_quote_archive_density_2026-07-16T1030.json`
- Paper ledger: `.cache/platform/paper_ledger.json` (stub smoke only)
- Cache eval: `.cache/platform/rth_eval_2026-07-16.json`

## DURABLE / learning

- Mid-session 2026-07-16 matches open RTH and prior day stand-aside class: eligible DNA under **bearish TSLL/TSLA/SMCI**; capital path remains empty until non-bear defined-risk filters pass.
- Optional densify at mid-session filled weeklies (13 expirations) and crossed 3/3 RTH market dates — useful for later BUILD observed-path, not a paper signal today.
- No skill/doctrine patch required (behavior matches RTH checklist).
- No promotion of hyps; no evolve; no B-check phase advance.

## VERIFICATION

- Freshness multi-symbol engine vs yfinance: pass (session day; intraday drift only)
- `premium_scout` 14/0/14: pass
- `autonomy_loop` dry-run 0 proposals: pass
- Real open_risk (non-smoke): 0
- Quote snapshot summary: `provider_backtest_eligible=true`, n_market_dates=3, 13 exps/date

## INTEGRATION

- Commit `287accd` on `main` → pushed `origin/main`; `HEAD == origin/main`; clean tree after push
- No broker / arm / shadow / live / evolve `--apply`
- Caches under `.cache/` remain untracked

## LESSON

Future RTH: when mid-session matches open class with zero open risk and zero capital-fit intents, short reconfirm + optional archive densify on a new NY date is the correct closed loop — do not thrash evolve.

## NEXT SEED

**RTH / B6:** wait for non-bear capital-fit defined-risk intent (OPEN_PCS/OPEN_CCS/OPEN_IC 1-lot) or manage real open paper risk if any appears; stand-aside remains success.

**BUILD context (not this wake):** `YIELD_CURVE_STEEPENING_REGIONAL_BANK_FORWARD_UPDRIFT_PREFLIGHT` after overnight MoA integrate.

## GATES

none (research/paper only; no approval packet)

# Trader cron layout (post engine-prove)

**Pinned:** 2026-07-19 (autonomous continuum)  
**Profile:** Hermes `trader` only (`~/.hermes/profiles/trader/cron/`)  
**Doctrine:** `docs/TRADER_BUILD.md` · handoff `reports/bootstrap/ENGINE_PROVE_HANDOFF.md`  
**Autonomous tick:** `scripts/trader_autonomous_tick.sh` / `just trader-autonomous-tick`

## Intent

Wake volume is **not** progress. Cron exists so Trader **keeps working the go-live funnel without Ken** — as long as the trader gateway is up:

1. **RTH condition / paper plumbing** — stand-aside or dry paper path on living/paper_eligible seats  
2. **Off-hours BUILD quality** — Strategy Engine handoff → MoA only when `NEXT_SURVIVOR`  
3. **Quality residual when no survivor** — research rank + defined-risk evolve + CSP/wheel evolve + B3/B4 on shortlist + multi-symbol re-prove + dry paper (`scripts/trader_quality_residual.sh`)  
4. **Never** continuous dense bag drain, live orders, self-arm, or `--execute-paper` from cron

**Acceleration pin (2026-07-20 Ken):** tighter quality loops toward proven strategies — hourly continuum + full residual, **not** 5m densify thrash.

Ken’s ongoing job is **not** to prompt every wake. Ken’s job is: keep gateway alive; fund $3k only at LIVE_PACKET; arm only when a LIVE_PACKET is drafted.

**Anti-bottleneck pin (2026-07-21):** residual NEXT actions must run without Ken chat. Durable seed: `reports/bootstrap/NEXT_SEED.json`.

**Tight-loop pin (2026-07-21 night):** programmatic search runs as a **non-stop quality worker** (parallel cycles), not only hourly cron. LLM wakes **coach** the worker results and own RTH opportunity/management — they do not replace the worker.

## Architecture (two layers)

```text
┌─────────────────────────────────────────────────────────┐
│  PROGRAMMATIC (no LLM) — tight / parallel               │
│  trader_quality_worker  (non-stop cycles, ~20s gap)     │
│    cycle: research → evolve DR → evolve CSP             │
│         → parallel(regime, cost, multi)                 │
│         → paper_loop → paper_campaign                   │
│  supervisor cron */10 ensure worker alive               │
│  NEVER densify bag drain · NEVER live/arm               │
└─────────────────────────────────────────────────────────┘
                         │ receipts + NEXT_SEED
                         ▼
┌─────────────────────────────────────────────────────────┐
│  LLM AGENT wakes — full Trader smarts                    │
│  RTH eval :30 — regime, opportunity, paper manage       │
│  continuum-judgment 21:00 (+ optional midday coach)     │
│    read worker heartbeat + go-live funnel + shortlist   │
│    improve DNA/tools/shortlist; never wait for Ken      │
│  MoA only if engine NEXT_SURVIVOR                       │
└─────────────────────────────────────────────────────────┘
```

## How autonomy works (single flight)

```text
cron / just trader-autonomous-tick
  → if build_lab.lock live: skip
  → route_batch + strategy engine handoff
  → if NEXT_SURVIVOR: zero-input BUILD MoA
  → if NO_QUALIFIED:
       if quality worker alive → defer (worker owns tight loop)
       else → one parallel quality_cycle
  → never live / shadow / arm
```

Receipts:
- `.cache/platform/quality_worker/HEARTBEAT.json` — tight loop pulse  
- `.cache/platform/autonomous/tick_LATEST.json` — hourly handoff  
- `.cache/platform/paper_campaign/LATEST.json` + `reports/bootstrap/NEXT_SEED.json`  
- `just trader-status` — go-live funnel

## Active set

| Job | Schedule (America/Los_Angeles) | Mode | Purpose |
|---|---|---|---|
| **`trader-quality-worker`** | `*/10 * * * *` ensure | script | Keep **non-stop** parallel quality cycles alive |
| `trader-rth-eval` | `30 6-12 * * 1-5` | agent + skill | RTH judgment: opportunity + paper manage |
| `trader-rth-ops` | `35 6-12 * * 1-5` | script | Scout + dry autonomy (no agent import) |
| `trader-paper-ops` | `5 6-12 * * 1-5` | script | Dry paper-loop + paper campaign |
| `trader-paper-campaign` | `20 6-13 * * 1-5` | script | learn + shortlist paper place/manage |
| `trader-autonomous-tick` | `15 * * * *` | script | Engine handoff; MoA or defer-to-worker |
| `trader-continuum-judgment` | `0 9,15,21 * * 1-5` | agent + skill | Coach worker results; improve search |
| `trader-build-lab-*` | named slots | script → tick | MoA path when survivor |

Single-flight lock means overlapping ticks **skip**, they do not stack MoA processes.

## Explicitly removed / paused

| Job | Action | Why |
|---|---|---|
| `trader-continuous-densify` (`every 5m`) | **Removed** | Thrash; bag drain as progress |
| Overnight BUILD 23/02/04 | **Paused** | Covered by 2h autonomous tick |
| Weekend pm/eve + Sunday am | **Paused** | Keep one Sat + one Sun named slot |
| Midday BUILD | **Paused** | RTH = paper/condition only |
| Legacy daily/weekly agent | **Paused** | Superseded |

Do **not** recreate the 5m densify cron. Autonomy is the 2h tick + sparse named slots, not nonstop launch spam.

## What still needs Ken

| Need | Why |
|---|---|
| Trader Hermes gateway running | Cron only fires with gateway up |
| Explicit LIVE_PACKET arm | Real money only |
| $3k transfer at packet | Not earlier |

**Does not need Ken:** residual NEXT, paper campaign, quality residual, shortlist stress, learn_tick, rth-ops, continuum judgment, commits on green lane.

## Operator checks

```bash
just trader-autonomous-tick     # one continuum cycle now
cat .cache/platform/autonomous/tick_LATEST.json
just trader-paper-loop
just trader-progress
# Hermes trader session: list crons — expect autonomous-tick every 2h; no every-5m densify
```

## Relationship to go-live plan

```text
autonomous tick + BUILD slots  → Phase 1 pack-grade edge (when engine yields survivors)
RTH paper-ops / rth-eval       → Phase 2 paper plumbing
(no cron)                      → Phase 4 Ken arm / live
```

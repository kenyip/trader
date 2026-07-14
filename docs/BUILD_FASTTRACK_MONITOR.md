# BUILD fast-track — monitor-only mode

**Ken intent:** run more dual BUILD labs. Jarvis/Ken only **monitor strategy-convergence drift**
and keep the program pointed at **funnel advancement → high-confidence strategy**, not
micromanage each wake or score capability residue as if it were a living trade.

## Operating contract

| Role | Does | Does not |
|---|---|---|
| **Trader (Sol→Grok dual)** | Free discovery, sims, falsify, strategy-run outcome, ONE next seed | Live/arm/real money |
| **Jarvis/Ken** | Check runs completed, **strategy verdict**, living funnel, L0–L4, drift flags | Force recipe menus every wake; treat process score as strategy closeness |
| **Schedule** | Sequential duals (lockfile) on densified cadence | Parallel duals on same repo |

## Success definition (program level)

1. **Strategy funnel advancement** — BETTER verdicts under the compounding contract (named candidate stage movement), not wake volume
2. **High confidence strategy** — first **L1** DNA (non-vacuous after-cost + B3 density + competitive ml/dd) after a living funnel seat
3. Then shift weight to **B6 paper** (not infinite BUILD)

Capability coverage and tooling remain useful **secondary** search information.

## Drift flags (monitor alerts on)

- `strategy_pivot_required` — ≥2 consecutive integrated wakes without strategy advance
- `strategy_burst_stop_required` — ≥3 consecutive no-advance (stop burst; reassess design/data)
- 3 consecutive complete duals with **INVALID_THRASH**
- High research-process scores (≥4) with **zero BETTER** advances (capability ≠ strategy)
- Incomplete duals / lock stuck / cron script missing
- Claimed L1/readiness without after-cost numbers
- Any live/arm/shadow auto-promote language

## Commands

```bash
# status
pgrep -fl trader_build_lab || true
ls -lt reports/trader-wakes/moa | head
.venv/bin/python scripts/trader_build_progress.py --write
.venv/bin/python scripts/trader_build_monitor.py --write

# manual dual (if idle) — zero-input preferred
bash scripts/trader_build_lab_moa.sh
# diagnosis/recovery only:
bash scripts/trader_build_lab_moa.sh --slot evening
```

See also: `docs/BUILD_PROGRESS_AND_CONFIDENCE.md`, `docs/BUILD_LAB_ENVIRONMENT.md` (strategy-run contract).

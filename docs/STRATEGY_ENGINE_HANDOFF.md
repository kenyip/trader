# Strategy Discovery Engine Handoff

Trader autonomous BUILD wakes are paused from open-ended strategy search until a Strategy Discovery Engine report is available.

## Purpose

The separate `kenyip/trader-strategy-engine` repo performs cheap, bounded strategy-route screening before Trader spends MoA BUILD reasoning. Trader should consume only a validated handoff report, not raw route ideas or one-off adjacent retunes.

## Required path for a new BUILD

```text
Strategy Discovery Engine route manifest + panel
  -> pre-outcome feasibility preflight
  -> train-only F0 screen
  -> sealed holdout identity packet
  -> report copied to .cache/strategy-engine/latest.json
  -> scripts/trader_strategy_engine_gate.py validates NEXT_SURVIVOR
  -> scripts/trader_build_lab_moa.sh launches MoA BUILD with strategy-engine-handoff.md
```

If the report is missing, malformed, `NO_QUALIFIED_STRATEGY`, unsafe, authority-positive, or leaks holdout outcomes, the gate blocks the new BUILD before a run branch is created.

## What the report may authorize

Only this:

- a `NEXT_SURVIVOR` handoff for deeper Trader reasoning;
- a sealed-holdout identity/hash/count packet;
- train-only F0 metrics that may support a discovery-stage claim.

It never authorizes:

- L1 / exact-payoff promotion;
- paper orders;
- shadow/live trading;
- broker login/session;
- funding;
- agentic arm.

## Recovery exception

Existing interrupted run recovery (`--resume`, run-branch zero-input recovery, finalizer/integrate-only) bypasses the strategy-engine launch gate. Recovery must finish or fail the already-started stamp; it must not start new strategy search.

## Manual bypass

`TRADER_STRATEGY_ENGINE_GATE_BYPASS=1` is a diagnostic/recovery bypass only. It is not valid for autonomous strategy discovery and should be cited explicitly if used.

# Trader Direct Path to Paper Opportunity Watch

Status: active operating plan, pinned 2026-07-16.

## Purpose

Reduce wasted full BUILD cycles while preserving evidence discipline. Trader should build toward a paper-opportunity watcher directly by separating cheap discovery, reusable option payoff validation, and watcher/order-packet plumbing.

This plan does **not** lower promotion gates. It changes the route from serial artisanal hypothesis tests to a staged funnel:

```text
cheap batch screen -> selected candidate deep validation -> reusable payoff map -> paper opportunity watcher -> paper packet
```

## Track A — Candidate factory / cheap triage

When there is no living candidate or a burst-stop just fired, prefer a candidate-factory wake over another one-off full trial. A factory wake may screen many predeclared mechanisms on train-only or development-only evidence, but must still close with exactly one claim-bearing decision or a dated reassessment.

Cheap screen gates before full MoA treatment:

1. enough observations/events for the claimed effect;
2. lag-safe chronology and no future leakage;
3. non-vacuous prior-only or same-date controls;
4. effect beats a simple baseline/control, not just zero;
5. tail and drawdown are plausible for the $3k sleeve;
6. a defined-risk option structure could plausibly express the forecast within $200-$300 one-lot risk;
7. opportunity frequency is high enough to matter;
8. no closed-family alias, threshold polish, or same-panel retune.

A screen may reject dozens of candidates as search information without writing each one as a full strategy family. A survivor earns deeper validation only after its rules, falsifier, controls, and sample partition are frozen.

## Track B — Reusable payoff validators

Do not rebuild option payoff logic per idea. Maintain reusable validators for:

- bull call / call debit spreads;
- bull put / put credit spreads;
- bullish diagonals;
- one-lot max loss and $3k sleeve overlap;
- dual-cost after-cost PnL;
- max drawdown and dense-negative windows;
- hard time stops, profit/loss exits, no same-bar reentry;
- listing/liquidity feasibility;
- proxy vs observed option evidence labeling.

A forecast can advance through discovery without these validators, but it cannot reach capital-seat / paper-path claims until the appropriate validator is exercised.

## Track C — Opportunity watcher scaffold

Build and keep a watcher scaffold even when there is no living strategy. Its normal output should be one of:

- `NO_QUALIFIED_STRATEGY` — no candidate has the required funnel/confidence stage;
- `NO_SETUP` — candidate exists, but market/regime/entry/liquidity/risk gates are not satisfied;
- `PAPER_PACKET_READY` — candidate is paper-authorized and a paper/suggested limit-order packet is ready;
- `GATED_LIVE_PACKET` — live packet prepared for Ken approval only after paper/shadow gates.

The watcher must be patient by design. No candidate means no trade. No setup means no trade. Stand-aside is success.

A paper packet should include: candidate id, confidence stage, forecast, structure, legs, sizing, max loss, entry limit, exit/management, invalidation, risk checks, data freshness, and why now. It must never imply broker/live authority.

## Track D — Run-count compression target

Target the next 15-35 BUILD wakes toward durable readiness primitives, not just more independent strategy volume:

1. one candidate factory or screen framework;
2. one or more reusable payoff validators for the preferred structure classes;
3. one watcher/no-trade scaffold that can run before a leader exists;
4. one successor epoch selected by the reassessment and tested through the cheap triage funnel;
5. only then deep validation and paper-packet plumbing for survivors.

## Authority boundaries

- Research and paper-only unless separately armed.
- No broker login/session, live orders, funding, shadow/live promotion, or autonomous limit orders from this plan.
- Suggested paper limit-order packets are allowed only after the candidate reaches the appropriate paper-ready stage.
- Live limit orders require paper evidence, risk/governor proof, a Ken-facing live packet, and explicit Ken approval.


## Strategy Discovery Engine handoff

New autonomous BUILD launches must first consume `.cache/strategy-engine/latest.json` through `scripts/trader_strategy_engine_gate.py`. The gate accepts only `NEXT_SURVIVOR` reports with sealed holdout identities and all authority fields false; it blocks `NO_QUALIFIED_STRATEGY` before a run branch is created.

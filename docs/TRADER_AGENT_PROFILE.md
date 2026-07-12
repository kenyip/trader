# Trader Hermes Profile

Dedicated **self-evolving** Hermes profile for Ken's research → paper → shadow → (armed) agentic_live income engine.

## Core reframe

| Wrong framing | Right framing |
|---|---|
| Caller supplies slot/goal/NEXT judgment | Caller runs `just trader-build-lab`; Trader orients and chooses autonomously |
| Evolution = `just evolve-tick` finished | Evolution = agent orients, chooses, builds, validates, leaves residue |
| Fixed strategy box (PMCC/short-premium only) | Seed sleeves are hypotheses; free search across DNA/structures |
| LaunchAgents as primary loop | Hermes **trader** gateway + agent crons |

Optional instruments (agent may choose):

```bash
just research-tick-paper
just evolve-tick
just learn-tick -- --apply
just platform-scout
just desk-brief
```

## Current local profile

```text
Profile: trader
Command: trader  (or hermes -p trader)
Path: /Users/jarvis/.hermes/profiles/trader
Default repo/cwd: /Users/jarvis/dev/tsla-tsll-options-tracker
SOUL: free self-evolving system operator
Skills: trader-self-evolution, trading-partner, pmcc-strategy
Gateway: ai.hermes.gateway-trader (cron-only; no Telegram — CoS sole Ken-facing GW)
```

Useful commands:

```bash
trader chat
trader chat -q "Load trader-self-evolution. Run one free self-evolution wake now."
trader chat -q "Load trading-partner and pmcc-strategy, then desk-brief status."
hermes -p trader gateway status
hermes -p trader cron list
hermes -p trader cron run efe58ee280c8
```

## Agent operating principles

1. Protect capital first; asymmetric opportunity second.
2. Prefer verifiable data, files, sims, audits over memory.
3. Closed loops beat digests — every wake changes something durable or records a falsification.
4. Build missing capability (code/skills) instead of pretending a fixed catalog is complete.
5. Never live-trade, broker-login, or auto-promote to shadow/live without explicit Ken mandate.
6. Never commit positions YAML, caches, Hermes secrets, broker creds, Telegram tokens.
7. Think in dollars, contracts, DTE, deltas, credits/debits when trade-shaped.
8. A wake is incomplete until scope is closed, checks are green, learning is promoted, and intended repo changes are committed, integrated to `main`, pushed, remote-verified, and clean.
9. Executor/challenger phases are evidence inputs. Only the finalizer plus deterministic completion gate may declare `RUN COMPLETE`.

## Canonical zero-input wake

`just trader-build-lab` is the normal BUILD interface for humans, Jarvis/coordinator, and cron. It loads the sole program goal from `configs/build_lab_free_goal.txt` and derives time/session metadata internally. Trader then orients from SOUL, doctrine, memory/skills, readiness, prior learning, and current context. Prior NEXT is context, not an order. `--goal`, `--slot`, structure, and recovery flags remain debug/recovery tools only.

## Wake protocol

Skill: `trader-self-evolution`

1. Orient (goals, hyps, audits, market regime)
2. Choose **one** closed loop
3. Act freely (research / build / sim / paper promote)
4. Durable residue + next-wake seed
5. Gate packet only for red-lane needs

Schedule (America/Los_Angeles):

| Job | When | Mode |
|---|---|---|
| `trader-self-evolution-daily` | Mon–Fri 16:45 | Agent |
| `trader-self-evolution-weekly` | Sun 17:00 | Agent (deeper critic) |

See [TRADER_LOOPS.md](TRADER_LOOPS.md) for shared loop map.

## Knowledge placement

- Compact profile memory only for routing/high-level stance
- `trader-self-evolution` for wake procedure
- `trading-partner` for trade analysis / desk brief
- `pmcc-strategy` for PMCC sleeve rules
- Repo docs/audits/scoreboard for dated evidence
- Per-run `learning-promotion.md` for verification, promoted lessons, and one NEXT
- `.cache/platform/completion/<stamp>.json` for machine-verified commit/merge/push/clean receipt
- Live fills only in private `pmcc_positions.yaml` (gitignored)

## Bootstrap / repair

```bash
scripts/bootstrap_trader_profile.sh
# then ensure agent crons + gateway:
hermes -p trader gateway install && hermes -p trader gateway start
hermes -p trader cron list
```

Bootstrap must not reintroduce program LaunchAgents as the primary tick path.

## Safety / migration

CoS remains sole Ken-facing Telegram gateway. Trader gateway is for **cron wakes** (and future non-CoS channels only if Ken approves).

24/7 path: prove local agent wakes → Mac Mini trader gateway + crons → optional Telegram for Trader only with explicit isolation → read-only broker → armed agentic live on isolated account only.

## Validation

```bash
hermes profile show trader
hermes -p trader config check
hermes -p trader skills list | grep -E 'trader-self-evolution|trading-partner|pmcc-strategy'
hermes -p trader gateway status
hermes -p trader cron list
trader chat -Q -t terminal -q "Use the terminal tool exactly once to execute: pwd. Then answer 'STDOUT: <the stdout>'."
trader chat -q "Reply with: (1) one sentence identity as free self-evolving trader (2) hard stops you never cross (3) confirm program ticks are optional tools."
```

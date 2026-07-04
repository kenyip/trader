# Trader Hermes Profile

This document describes the dedicated `trader` Hermes profile for trade analysis, PMCC management, and eventual always-on Mac Mini deployment.

The goal is to build a disciplined trading partner that is excellent at finding current data, understanding fundamentals and technicals, optimizing options strategies, monitoring risk, and producing concrete trade playbooks. It is not an execution bot until Ken explicitly grants brokerage access and an execution mandate.

## Current local profile

```text
Profile: trader
Command: trader
Path: /home/ken/.hermes/profiles/trader
Default repo/cwd: /home/ken/dev/tsla-tsll-options-tracker
Primary repo: ~/dev/tsla-tsll-options-tracker
Primary skills: trading-partner, pmcc-strategy
```

Useful commands:

```bash
trader chat
trader chat -q "Load trading-partner and pmcc-strategy, then run just pmcc-manage and summarize current PMCC risk."
trader status --all
trader skills list | grep -E 'trading-partner|pmcc-strategy'
```

## Agent operating principles

The profile's `SOUL.md`, curated memory, and `trading-partner` skill encode these rules:

1. Protect capital first; find asymmetric trades second.
2. Prefer current verifiable market data over memory.
3. Label stale, cached, weekend, or after-hours data clearly.
4. Blend fundamentals, technicals, option-chain structure, volatility/regime, portfolio exposure, buying-power/collateral effects, and scenario stress tests.
5. Think in dollars, contract counts, DTE, deltas, credits/debits, breakevens, and max adverse paths.
6. For PMCCs, load `pmcc-strategy` and respect Ken's core-vs-income sleeve framing.
7. Never submit orders or access brokerage accounts without explicit authorization.
8. Never commit live positions, market caches, Hermes secrets, broker credentials, or Telegram tokens.

## Knowledge placement

The profile intentionally avoids bloated memory. Use:

- `~/.hermes/profiles/trader/memories/MEMORY.md` for compact routing/high-level stance only.
- `trading-partner` for general trade-analysis workflow and memory-vs-skill routing.
- `pmcc-strategy` for durable PMCC strategy rules and detailed dated references.
- `docs/TRADER_KNOWLEDGE_MAP.md` for the index of past-weeks learnings and where each one lives.
- `session_search` only when a detail was not promoted into memory, skills, or repo docs.

Live fills and actual open positions belong only in `pmcc_positions.yaml`, which is private and gitignored.

## Trade-analysis output standard

For every meaningful recommendation, the agent should provide:

- data timestamp and source
- current exposure and position context
- thesis: fundamental, technical, volatility, event calendar, and regime framing
- exact legs: ticker, expiry, strike, contracts, target limit, debit/credit
- scenario table in dollars: flat/chop, drop-recovery, slow bull, fast rip, thesis failure
- management plan: harvest, roll, stop/invalidation, force-close, reload, and do-nothing triggers
- shares-vs-options comparison when relevant
- final stance: do now / wait for price / avoid / needs more data

## Local bootstrap / repair

From the repo root:

```bash
scripts/bootstrap_trader_profile.sh
```

The script is safe to re-run. It creates the `trader` profile if missing, sets its working directory to the repo, writes the trading SOUL/memory/skill, and does not copy positions, auth files, provider keys, or Telegram tokens into git.

## PMCC commands

```bash
cd ~/dev/tsla-tsll-options-tracker
just pmcc-manage
just pmcc-manage --monitor
just pmcc-manage --what-if 500
just pmcc-monitor
just pmcc-scan --preset managed --refresh
just pmcc-playbook-gen
```

Run long refresh scans in the background from Hermes with completion notification. During market hours, prefer strict live-chain scans. After-hours/weekends, warn that yfinance chain data can be corrupt; use cached/model-cleaned scans only for strategic ranking.

## Private files and migration boundaries

Tracked in git:

- repo code and tests
- docs such as this file and `docs/PMCC_MONITOR_DEPLOYMENT.md`
- safe examples like `pmcc_positions.example.yaml`
- bootstrap scripts like `scripts/bootstrap_trader_profile.sh` and `scripts/bootstrap_pmcc_monitor.sh`

Never commit:

- `pmcc_positions.yaml`
- `positions.yaml`
- `.cache/`
- Hermes `.env`, `auth.json`, OAuth files, provider keys, Telegram tokens
- brokerage credentials, session cookies, account exports, or statements unless explicitly sanitized

## Mac Mini always-on migration path

Use this order when moving off the laptop:

1. Clone this repo on the Mac Mini.
2. Run `scripts/bootstrap_trader_profile.sh` from the repo root.
3. Run `trader setup` or import a private profile archive if approved.
4. Transfer `pmcc_positions.yaml` privately, not through git.
5. Run `scripts/bootstrap_pmcc_monitor.sh` on the Mac Mini.
6. Configure Telegram gateway for the `trader` profile: `trader gateway setup telegram`.
7. Install/start the profile gateway: `trader gateway install && trader gateway start`.
8. Recreate cron on the Mac Mini; cron jobs and gateway pairings are machine-local.
9. Smoke-test: `trader chat -q "Load trading-partner and pmcc-strategy. Use terminal to run just pmcc-manage --monitor, then summarize whether action is needed."`
10. Only after read-only monitoring is reliable should broker/data integrations be added. Execution access is a separate explicit authorization step with hard risk limits.

## Profile export option

For a faithful private copy of the local agent, use Hermes profile export/import instead of git:

```bash
hermes profile export trader -o ~/trader-profile.tar.gz
scp ~/trader-profile.tar.gz USER@MAC_MINI:~/
# on Mac Mini
hermes profile import ~/trader-profile.tar.gz
```

Before sharing or archiving the tarball, remember it may contain config, `.env`, memories, skills, and other private profile state. Keep it private.

## Validation before declaring migration done

```bash
trader profile show trader
trader config check
trader skills list | grep -E 'trading-partner|pmcc-strategy'
cd ~/dev/tsla-tsll-options-tracker
just pmcc-manage --monitor
just pmcc-monitor
```

Expected:

- `trader` exists and points at the repo as `terminal.cwd`.
- `trading-partner` and `pmcc-strategy` are available.
- PMCC monitor is quiet when no action is needed.
- Alert-path test can be triggered with a simulated spot without editing positions.

# Agentic Autonomy Policy (anti-drift pin)

> **Pinned 2026-07-09.** Ken’s standing intent for the **isolated Agentic Robinhood account**.
> Product north star: [TRADER_PLATFORM_GOAL.md](TRADER_PLATFORM_GOAL.md).
> Code: `trader_platform/risk_governor.py`, `trader_platform/execution/`, `trader_platform/autonomy_loop.py`.

---

## Stage2 status (2026-07-09)

- RH **read-only** smoke + local snapshot readiness live under `trader_platform/rh_snapshot.py`.
- Default paper path uses `PaperRhBridge` (paper mutations + optional RH snapshot).
- **Agentic sleeve is currently unfunded and has no options level** — keep `agentic_live` off.
- Details: `docs/STAGE2_RH_READONLY_AND_CAPITAL.md`.

## Standing intent

Once Stage1 OAuth is complete and mode `agentic_live` is armed, the `trader` agent may **place / replace / cancel limit orders** on the isolated Agentic account **without per-order Ken approval**, subject only to the deterministic risk envelope below.

This is **not** permission to:

- trade non-Agentic accounts
- disable the risk governor
- market-spam when working limits are viable
- fund, transfer, or withdraw
- skip audit logging

---

## Mode flags

| Mode | Meaning | Default path |
|---|---|---|
| `research` | Hypotheses, scans, backtests only | Always allowed |
| `paper` | Local ledger; simulated limit lifecycle | **Default for autonomy loop** |
| `shadow` | Propose + risk-check + log; no broker mutate | Allowed |
| `agentic_live` | Real order mutations via broker MCP | **Blocked until connected + armed** |

**Hard rule:** default until MCP authed and explicitly armed: cannot be `agentic_live`.

Arming checklist (human, on Ken’s Mac — not automated here):

1. Stage1 Robinhood OAuth for the **isolated Agentic account only**
2. Broker MCP connected and healthy (no secrets in repo)
3. `trader_platform/risk_limits.yaml` reviewed
4. Kill switch file absent / cleared intentionally
5. Config: `agentic.enabled: true` **and** mode `agentic_live`
6. Strategy allowlist non-empty and promotion evidence present for live-status hypotheses

---

## Event / cron design

Allowed by design:

- Cron ticks (market open, mid-session, close)
- Event drivers: regime change, limit fill/cancel, IV shock stubs, position management triggers

**M0–M1:** implement as **local dry-run / paper stubs**.  
**Do not** register live Hermes cron that places orders until Stage1 is armed and a separate ops task enables it.

Later Hermes cron shape (documentation only):

```bash
# NOT registered in M0–M1 — example for future ops
cd ~/dev/tsla-tsll-options-tracker
.venv/bin/python -m trader_platform.autonomy_loop --mode paper --once
# after arming only:
# .venv/bin/python -m trader_platform.autonomy_loop --mode agentic_live --once
```

Just recipes: `just platform-scan`, `just platform-paper-tick`.

---

## Order style preference

1. Prefer **working limit orders**
2. **Amend / replace** rather than cancel+market when possible
3. Market orders only if explicitly allowed by risk config **and** strategy policy (default: deny market)

---

## Hard risk envelope

Defaults live in `trader_platform/risk_limits.yaml` (tunable in config, not chat secrets):

| Control | Purpose |
|---|---|
| `max_notional_per_order` | Cap dollar exposure of a single order |
| `max_contracts_per_order` | Cap size |
| `max_open_risk` | Cap aggregate open risk |
| `max_daily_loss` | Daily loss kill switch |
| `strategy_allowlist` / per-strategy disable | Only promoted strategies |
| `agentic.enabled` | Global soft kill |
| `agentic_kill.switch` file | Hard kill file (presence = deny all live/paper mutate if configured) |

Governor interface: proposed order intent → `allow` / `deny` + reasons. Every deny is audited.

---

## Promotion to live status

Hypotheses move: `candidate → testing → paper → shadow → live` (or `retired` / `rejected`).

- **No auto-promote to `live`** without an evidence record (walk-forward, scenarios, costs, drawdown checklist).
- Code: `trader_platform/promotion_gates.py` — structure real; criteria may be stubs with TODOs until gauntlet wiring deepens.

---

## Audit

Every propose → risk_check → execute attempt must leave a durable log line (local JSONL under `.cache/platform/` or paper ledger). No silent mutations.

---

## Forbidden (always)

- Guaranteed-income claims
- Secrets / tokens in docs or git
- Live RH place/cancel from this repo until Stage1 + arming
- Funding / transfers automation
- Per-trade Ken wait as a design dependency on the Agentic sleeve (risk envelope replaces chat approval)

---

## History

### 2026-07-09 — Policy pinned

Ken affirmed isolated Agentic account has total freedom to trade **without per-trade wait**, with cron/event scanning and autonomous limit set/modify. Risk governor + kill switch remain mandatory. M0–M1 codes the policy as mode flags + paper path; live blocked until OAuth.

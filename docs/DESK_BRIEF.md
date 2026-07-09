# Income Engine Desk Brief

**Status:** production playbook (Income Engine stage **I1**)  
**Owner profile:** `trader`  
**Repo:** `/Users/jarvis/dev/tsla-tsll-options-tracker`  
**Date:** 2026-07-09  

One coherent daily (or on-demand) status for Ken’s real-money sleeves: PMCC + short-premium + stance. Analysis and proposed tickets only — **never places trades**.

---

## 1. Purpose

Replace ad-hoc “run manage” / “run live” with a single operator surface:

1. Gather raw desk data (PMCC, short-premium, session quality).
2. Synthesize into the `trading-partner` checklist shape.
3. End with an **action queue** and a **final stance** (do now / wait / avoid / needs more data / do nothing).

Ken should be able to ask the `trader` agent once — or run `just desk-brief` for the raw gather — and get a complete Income Engine picture.

---

## 2. One-command entrypoints

From the repo root (also the `trader` profile default cwd):

```bash
# Raw gather only (script output for human or agent synthesis)
just desk-brief                 # monitor-style PMCC + short-premium live rec + data-quality banner
just desk-brief --full          # full pmcc-manage dashboard instead of --monitor
just desk-brief --no-live       # skip short-premium live.py if you only want position status

# Agent path (preferred for synthesis + stance)
trader chat -q "Run the Income Engine desk brief playbook (docs/DESK_BRIEF.md). Load trading-partner and pmcc-strategy. Gather with just desk-brief, then synthesize the standard output shape. Do not place trades."
```

Long scans (`just pmcc-scan --refresh`) are **not** part of the default desk brief. Kick them off separately in the background only when reloading shorts or re-ranking pairs.

---

## 3. Operator checklist (agent must follow)

Run in order. Skip only when a step is impossible and say so.

### A. Session and data quality (first line of the brief)

1. Local time + UTC timestamp.
2. Market session label using `pmcc.market_hours`:
   - RTH = Mon–Fri 09:30–16:00 America/New_York (no holiday calendar — note that gap).
   - Outside RTH: **label after-hours / weekend / pre-market** before any chain-based conclusion.
3. Cache policy: `cache_policy_label()` from `pmcc/market_hours.py`.
4. Data-quality rules:
   - **RTH:** prefer live chain marks; treat `just pmcc-manage` marks as tradeable context.
   - **After-hours / weekend:** yfinance option chains can be corrupted (zero bids, junk deltas). Treat short marks of `$0`, absurd IVs, or “HARVEST” from a zero mark as **suspect until RTH re-check**. Prefer last good session cache / model-cleaned tools for strategy ranking only — never as a hard trade ticket without re-validation.
5. State clearly: `DATA QUALITY: LIVE RTH` | `DATA QUALITY: AFTER-HOURS / CACHED — not ticketable alone`.

### B. Exposure map

Compose from private files + known Ken stance (do not invent fills):

| Sleeve | Source | What to report |
|--------|--------|----------------|
| Shares | Ken / memory (not in repo) | >300 TSLA if still true; margin note ~4.75%; collateral value |
| Core PMCC / LEAPS | `pmcc_positions.yaml` | ticker, LEAPS strike/expiry/debit, contracts, open short Y/N, DTE, mark P/L $ |
| Income PMCC sleeve | same file / notes | which legs are income-sleeve (capped-rip OK) vs core |
| Short-premium book | `positions.yaml` if present | side, strike, expiry, credit, contracts, DTE, mark P/L $ |
| Cash / BP | unknown unless Ken provides | say “unknown” rather than invent |

If a private file is missing:

- No `pmcc_positions.yaml` → PMCC section = “no private PMCC book on disk”.
- No `positions.yaml` → short-premium section = live **recommendation only** (no open book).

Never print full private YAML into git, Telegram, or commit messages. Summarize in dollars/contracts.

### C. Gather commands (raw inputs)

```bash
cd /Users/jarvis/dev/tsla-tsll-options-tracker

# Preferred single gather
just desk-brief

# Or manual pieces:
just pmcc-manage --monitor      # quiet-action oriented; use full manage when deciding
just pmcc-manage                # full marks, premium clock, next-short candidates
just pmcc-monitor               # silent unless action needed (cron path)

# Short-premium live recommendation (always available; engine path)
just test                       # live.py → TSLA + TSLL SELL_* or STAND_ASIDE

# Short-premium open book (only if positions.yaml exists)
just positions                  # exit-ladder status on open shorts
```

Optional, event-sensitive days only:

- Catalyst note via Hermes `x_search` (earnings, delivery, named events).
- `just pmcc-manage --what-if <spot>` for stress marks.
- `just pmcc-manage --triggers` when a short is challenged.

### D. Action queue (normalize every signal)

Map tool output into one queue. Allowed action types only:

| Action | When |
|--------|------|
| **HARVEST** | Short mark ≤ ~50% of credit (or manager says harvest) |
| **ROLL** | Gap-rip / challenged / proximity rules; prefer up-and-out |
| **FORCE-CLOSE** | ITM short near ≤14 DTE — never assign against LEAPS |
| **RELOAD** | LEAPS-only or post-harvest; premium clock allows; setup safe |
| **STAND ASIDE / DO NOTHING** | No signal, bad data, catalyst blackout, or wait budget |
| **WARN / NEEDS RTH RECHECK** | After-hours zero marks, corrupt chain, conflicting signals |

For each action item include when possible:

- Ticker, contracts, DTE, strike, credit/debit or mark in **$**
- Premium clock: $/day vs floor/good/strong (TSLA ≈ $10 / $15 / $20 per short; NVDA lower)
- Invalidation / “do nothing if…”

### E. Scenario / stance note

Even when recommending **do nothing**, state the regime frame in 2–5 lines:

- Flat/chop income floor
- Drop-recovery risk
- Slow bull path
- Fast rip (core vs income sleeve behavior)
- Thesis-failure case

If proposing any new short or structure, full scenario table in dollars is required (see §4).

### F. Final stance (required last line block)

Exactly one of:

- `DO NOW` — ticketable levels exist and data quality is RTH-grade (or Ken accepts AH risk explicitly)
- `WAIT FOR PRICE` — levels named
- `AVOID` — with reason
- `NEEDS MORE DATA` — what is missing
- `DO NOTHING` — hold / no reload; monitor only

---

## 4. Output shape (agent synthesis)

Match the `trading-partner` trade-analysis checklist. For the **desk brief** (daily status), use this template:

```text
# Income Engine Desk Brief
Timestamp: <local> / <UTC>
DATA QUALITY: <LIVE RTH | AFTER-HOURS/CACHED | WEEKEND — details>
Sources: just desk-brief / pmcc-manage / live.py / positions.yaml / ...

## 1. Exposure
- Shares: ...
- PMCC core: ... (contracts, strikes, DTE, open short Y/N, mark P/L $)
- PMCC income: ...
- Short-premium open: ... or "none on disk"
- Collateral / BP notes: ...

## 2. Thesis / regime (short)
- Spot context + vol/regime features from live.py if available
- Catalyst window: none | named event
- Sleeve intent: core managed up/out; income can cap/close-both

## 3. Action queue
1. [HARVEST|ROLL|FORCE-CLOSE|RELOAD|DO NOTHING|WARN] ...
   - $ / contracts / DTE / levels
   - Invalidation: ...

## 4. Proposed tickets (only if action ≠ do nothing)
- Exact legs, limit, credit/debit expected
- Stress $ table: flat/chop | drop-recovery | slow bull | fast rip | thesis failure
- Shares vs options note if relevant

## 5. Management triggers
- Harvest / roll / force-close / reload / stay naked rules for open legs

## 6. Final stance
STANCE: <DO NOW | WAIT FOR PRICE | AVOID | NEEDS MORE DATA | DO NOTHING>
One-sentence reason.
```

Rules:

- Percentages alone are not enough — dollars, contracts, DTE.
- Do not auto-submit orders.
- Do not reset LEAPS to a higher strike casually.
- Core sleeve: manage up/out; partial coverage ok; naked longs as buffer.
- Income sleeve: capped-rip acceptable; close-both on target is a feature, not a failure.

---

## 5. What `just desk-brief` does (and does not)

**Does:**

- Print data-quality / session banner (RTH vs closed + cache policy).
- Run `pmcc_manage.py --monitor` by default (or full manage with `--full`).
- Run short-premium `live.py` (`just test`) unless `--no-live`.
- If `positions.yaml` exists, run `manage_positions.py` status.
- Exit non-zero only if a required gather command crashes.

**Does not:**

- Place trades or touch broker APIs.
- Refresh multi-minute pair scans.
- Commit or modify `pmcc_positions.yaml` / `positions.yaml`.
- Synthesize the narrative stance (agent or human does that from the raw dump).

Implementation: `scripts/desk_brief.py` + Justfile recipe `desk-brief`.

**Pitfall:** the income package is `trader_platform/` (renamed from `platform/` to stop shadowing stdlib `platform`). `scripts/desk_brief.py` still seals stdlib as defense-in-depth.

---

## 6. Private-state boundaries

Never commit or paste into git:

- `pmcc_positions.yaml`
- `positions.yaml`
- `.cache/`
- Hermes secrets, broker credentials, Telegram tokens

Safe to commit: this doc, `scripts/desk_brief.py`, Justfile recipe, skill patches, examples.

---

## 7. Related docs and skills

| Artifact | Role |
|----------|------|
| `trading-partner` skill | Checklist + desk-brief workflow section |
| `pmcc-strategy` skill | PMCC management rules, premium clock, monitor resume |
| `docs/TRADER_AGENT_PROFILE.md` | Profile bootstrap / migration |
| `docs/PMCC_MONITOR_DEPLOYMENT.md` | Always-on quiet monitor + cron |
| `docs/TRADER_KNOWLEDGE_MAP.md` | Where learnings live |
| Parent plan `TRADER_PLATFORM_PLAN.md` | Income Engine I1 definition |

---

## 8. Acceptance smoke (I1)

```bash
cd /Users/jarvis/dev/tsla-tsll-options-tracker
just desk-brief | head -100
# Expect: DATA QUALITY banner, PMCC ACTION lines or empty-book note, short-premium live section
```

Agent smoke:

```bash
trader chat -q "Run docs/DESK_BRIEF.md playbook once. Use just desk-brief for gather. Produce the §4 template. No trades."
```

Done when Ken can get one coherent daily status without chaining ad-hoc commands.

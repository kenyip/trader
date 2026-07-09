# Research Scoreboard — Production Baselines + Lab Log

**Purpose:** Freeze the Income Engine production baseline and keep an **append-only** Free Strategy Research log so lab work cannot overwrite memory of wins / nulls / rejections.

**Related plan:** parent platform plan Lab stages **R0 (freeze production)** and **R3 (scoreboard file)** — `TRADER_PLATFORM_PLAN.md` §5 / §8 (kanban `t_dea619b7` / freeze task `t_6a6f8980`).

**Cold-start operator page:** [`docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md`](FREE_STRATEGY_RESEARCH_RUNBOOK.md) — weekly loop, Path A/B promotion, `just lab-smoke` / model recipes.

**Hard rules (do not violate):**
1. Do **not** enable model production flags (`enable_model_entry`, `enable_model_management` stay `False` until a validated ship).
2. Do **not** change `StrategyConfig` / `DEFAULT_CONFIG_BY_TICKER` defaults unless a proposal is marked **SHIP** after the real-data firewall.
3. Synthetic paths densify training and stress only — **shipping decisions use real history only**.
4. Prefer **NULL** over optimistic ship. Log nulls so they are not re-proposed.

---

## 1. Production baseline identity (frozen)

### 1.1 Short-premium engine — **v1.13**

| Field | Value |
|-------|--------|
| Identity | `v1.13` HoldToDecay short-premium stack |
| Code | `strategies.py` (`get_config`, `pick_entry`, `check_exits`, adaptive registries) |
| Docs | `STRATEGY.md` (rules + history), `ENGINE.md`, `GOAL.md` |
| Live path | `live.py` → same `pick_entry()` (no parallel live engine) |
| Model authority | **OFF** — both model flags default `False` |

**Per-ticker production adaptive rules (enabled):**

| Ticker | `adaptive_rules` |
|--------|------------------|
| TSLA | `tsla_skip_mild_intraday_up` |
| TSLL | `tsll_skip_marginal_up`, `tsll_skip_tuesday`, `tsll_skip_post_earnings_drift`, `tsll_skip_downtrend_high_iv`, `ride_high_credit_mgmt` |

Exit adaptive list default: empty (`exit_rules = ()`). Registered-but-not-enabled rules stay in `ADAPTIVE_RULES` / `ADAPTIVE_EXIT_RULES` for documentation / re-use, not live authority.

**Pinned reference baseline (STRATEGY.md, run 2026-05-14 `just backtest`):**

| Ticker | Window (as documented) | Trades | Win % | Total P/L | PF | Max DD |
|--------|------------------------|--------|-------|-----------|-----|--------|
| TSLA | 2022-06 → 2026-05 | 100 | 92.0% | +$17,790 | 5.25 | $1,107 |
| TSLL | 2023-09 → 2026-05 | 160 | 78.8% | +$3,250 | 4.28 | $144 |

### 1.2 PMCC — **managed** preset

| Field | Value |
|-------|--------|
| Identity | `managed` preset (`pmcc/config.py` PRESETS + `POLICY_BY_PRESET["managed"]`) |
| Scan / desk default | `just pmcc-scan --preset managed`, desk/manage paths default `preset="managed"` |
| Live state | private `pmcc_positions.yaml` only (gitignored) |
| Core management rules | max-DTE LEAPS preference; short ~60 DTE / ~0.30Δ; harvest ~50% profit; roll-up when challenged; **force-close ITM short at 14 DTE**; conditional LEAPS roll ~365 DTE remaining; **never casual higher-strike LEAPS reset** |

**Managed policy highlights** (`PlayPolicy` for `managed`):

| Knob | Value |
|------|-------|
| `short_dte_new` | 60 |
| `short_delta_new` | 0.30 |
| `harvest_profit_pct` | 0.50 |
| `roll_up_pct` | 0.10 |
| `roll_min_bump` | 45 |
| `force_close_dte` | 14 |
| `leaps_roll_dte` | 365 |
| `leaps_deep_itm_threshold` / extreme | 1.25 / 1.35 |
| `reentry_cooldown_days` | 21 |
| `min_roll_gap_days` | 18 |

PMCC stress/playbook work is **production-sleeve tooling**, not free authority to change short-premium defaults. Cross-template (defined-risk, strangles, calendars) stays lab-only until a separate firewall design exists.

---

## 2. Validation firewall (real data only)

Authoritative sources:

| Doc | Role |
|-----|------|
| [`GOAL.md`](../GOAL.md) | Critic-loop north star, cost function, success criteria, model flags off |
| [`simulator/CLOSED_LOOP_STRATEGY_FINDER.md`](../simulator/CLOSED_LOOP_STRATEGY_FINDER.md) | Closed-loop design; synthetic = density only; ship gate on real data |
| [`STRATEGY.md`](../STRATEGY.md) | How to add adaptive rules; history of ships + nulls |
| [`ENGINE.md`](../ENGINE.md) | Engine surfaces, harnesses, architecture |
| [`CLAUDE.md`](../CLAUDE.md) | Pre/post change gate: `just scenarios` |

**Ship gate (unchanged):** every candidate must pass on **real** surfaces before production:

1. 5y (or full available) backtest — `just backtest`
2. 12-regime stress suite — `just scenarios` (canonical windows in `scenarios.py`)
3. Walk-forward OOS — `validate_rule.py` / optimize static OOS as applicable
4. **Cost function:** `total_pnl − dd_weight × max_DD` (default `dd_weight = 1.0`, tail-first)
5. **No catastrophe regression:** no suite regime worse than the configured floor (default −$500)
6. Verdict language: **TRIPLE-WIN / MIXED / NULL** (or SHIP / NULL / REJECT / NEEDS MORE DATA)

**Commands (repo root, project venv):**

```bash
just scenarios          # REQUIRED regression gate
just backtest           # 5y / full-window baseline
just analyze            # proposer (does not ship)
.venv/bin/python validate_rule.py ...   # A/B vs baseline
just model-verify       # lab smoke only — does not flip production flags
```

---

## 3. Baseline freeze snapshot (R0)

Recorded so future research compares against a dated re-run, not only the May 2026 STRATEGY.md pin.

| Field | Value |
|-------|--------|
| Freeze task | `t_6a6f8980` |
| Run timestamp | **2026-07-09 00:03 PDT** |
| Host | local Mac; repo `/Users/jarvis/dev/tsla-tsll-options-tracker` |
| Command env | `.venv/bin/python` via `just scenarios` + `just backtest` |
| Strategy defaults changed? | **No** |
| Model flags changed? | **No** (`enable_model_entry=False`, `enable_model_management=False`) |

### 3.1 `just scenarios` (2026-07-09)

**TSLA** (`long_dte=7`, `long_target_delta=0.2`):

| Regime | Window | n | Win% | P/L | MaxDD | Dom. exit |
|--------|--------|---|------|-----|-------|-----------|
| huge_down | 2025-02-19 → 2025-03-19 | 0 | 0.0% | $+0 | $0 | — |
| normal_down | 2024-09-24 → 2024-10-22 | 3 | 100.0% | $+471 | $0 | daily_capture |
| flat | 2023-11-14 → 2023-12-13 | 0 | 0.0% | $+0 | $0 | — |
| normal_up | 2024-08-12 → 2024-09-10 | 9 | 88.9% | $+1,375 | $0 | profit_target |
| huge_up | 2024-10-22 → 2024-11-19 | 9 | 88.9% | $+2,374 | $0 | daily_capture |
| v_recovery | 2025-04-09 → 2025-05-08 | 6 | 100.0% | $+1,419 | $0 | profit_target |
| inverse_v | 2024-09-17 → 2024-10-15 | 6 | 100.0% | $+994 | $0 | daily_capture |
| gap_shock | 2024-10-01 → 2024-10-29 | 4 | 100.0% | $+549 | $0 | daily_capture |
| vol_crush | 2024-05-15 → 2024-06-13 | 0 | 0.0% | $+0 | $0 | — |
| vol_expansion | 2025-03-05 → 2025-04-02 | 0 | 0.0% | $+0 | $0 | — |
| chop_whipsaw | 2024-02-05 → 2024-03-05 | 0 | 0.0% | $+0 | $0 | — |
| earnings_window | 2025-10-15 → 2025-11-12 | 0 | 0.0% | $+0 | $0 | — |

- Profitable regimes: **6/12**
- Suite total P/L: **+$7,183.13**
- Worst regime: `huge_down` (**+$0** — no trades / no catastrophe)

**TSLL** (`long_dte=3`, `long_target_delta=0.3`):

| Regime | Window | n | Win% | P/L | MaxDD | Dom. exit |
|--------|--------|---|------|-----|-------|-----------|
| huge_down | 2025-02-21 → 2025-03-21 | 2 | 100.0% | $+61 | $0 | daily_capture |
| normal_down | 2025-06-10 → 2025-07-10 | 6 | 50.0% | $-4 | $39 | delta_breach |
| flat | *(no canonical window)* | — | — | — | — | — |
| normal_up | 2024-08-21 → 2024-09-19 | 8 | 87.5% | $+160 | $0 | profit_target |
| huge_up | 2024-11-14 → 2024-12-13 | 12 | 91.7% | $+690 | $0 | expired |
| v_recovery | 2024-07-24 → 2024-08-21 | 1 | 100.0% | $+9 | $0 | daily_capture |
| inverse_v | 2024-09-12 → 2024-10-10 | 8 | 62.5% | $-9 | $86 | profit_target |
| gap_shock | 2024-09-26 → 2024-10-24 | 6 | 66.7% | $+17 | $86 | expired |
| vol_crush | 2023-11-24 → 2023-12-22 | 2 | 100.0% | $+35 | $0 | profit_target |
| vol_expansion | 2024-01-24 → 2024-02-22 | 5 | 60.0% | $+54 | $4 | profit_target |
| chop_whipsaw | 2025-05-12 → 2025-06-10 | 10 | 90.0% | $+250 | $11 | daily_capture |
| earnings_window | 2025-10-10 → 2025-11-07 | 7 | 100.0% | $+288 | $0 | expired |

- Profitable regimes: **9/11** (flat undefined)
- Suite total P/L: **+$1,551.51**
- Worst regime: `inverse_v` (**$-9**)

### 3.2 `just backtest` (2026-07-09)

Rolling end date moves with data; headline metrics below are the **freeze re-run**, not a claim that STRATEGY.md May-14 numbers are wrong.

| Ticker | Window (this run) | Trades | Win % | Total P/L | PF | Max DD | Notes |
|--------|-------------------|--------|-------|-----------|-----|--------|-------|
| TSLA | 2022-08-16 → 2026-07-02 | 93 | 91.4% | **+$16,577.60** | 4.96 | **$1,107.09** | Max DD matches pinned $1,107; fewer trades / slightly lower P/L vs May pin as window rolled |
| TSLL | 2023-09-21 → 2026-07-02 | 162 | 76.5% | **+$3,082.90** | 3.36 | **$290.19** | P/L near pin; max DD higher than May $144 pin — treat as current data state, not a strategy change |

**Interpretation for researchers:**
- Use **§1.1 STRATEGY.md pin** as the historical v1.13 ship reference.
- Use **§3 freeze tables** as the **current regression baselines** when comparing new candidates (deltas vs this run).
- TSLL max-DD drift vs May pin is **data-window / market path**, not a config ship — re-validate before treating it as a production regression.

---

## 4. Append-only proposal log (R3)

**How to append:** add a new row at the **bottom** of the table. Never rewrite prior rows. Link notes (STRATEGY.md history entry, PR, workspace path, or dated doc).

| date | hypothesis | surfaces tested | verdict | metrics snapshot | notes / link |
|------|------------|-----------------|---------|------------------|--------------|
| 2026-05-14 | v1.13 adaptive rule fleet (4 new skips + M4/M5 plumbing) vs v1.12 | 5y + 12-regime + OOS via `validate_rule.py` | **SHIP** | TSLA +$17.8k / 92% WR / $1.1k DD; TSLL +$3.3k / 78.8% WR / $144 DD (STRATEGY pin) | `STRATEGY.md` v1.13 history; production identity above |
| 2026-05-14 | Archetype bake-off: QuickHarvest / PremiumSlow / ReversalScalp vs HoldToDecay v1.13 | 5y + suite + walk-forward static OOS | **NULL** | HoldToDecay dominant both tickers; no shape ship | `STRATEGY.md` 2026-05-14 bake-off; engine v1.10 only |
| 2026-07-09 | R0 freeze: re-run scenarios + backtest; no candidate | `just scenarios` + `just backtest` | **BASELINE** | See §3 tables | This file created; no strategy/default/flag change |

### Template row (copy when proposing)

```
| YYYY-MM-DD | one-line hypothesis | e.g. 5y / scenarios / OOS / validate_rule | SHIP \| NULL \| REJECT \| NEEDS_MORE_DATA | key $ P/L, DD, suite worst | path-to-notes |
```

**Verdict guide:**

| Verdict | Meaning |
|---------|---------|
| **SHIP** | Passed firewall + cost function; production defaults/rules updated and STRATEGY.md bumped |
| **NULL** | No improvement (or within noise); do not re-propose same idea without new evidence |
| **REJECT** | Catastrophe / OOS / cost-function failure; keep documented |
| **NEEDS_MORE_DATA** | Incomplete surfaces or weak sample; not a ship |
| **BASELINE** | Freeze / re-baseline only (no candidate) |
| **SHADOW** | Side-by-side vs production, no authority |

---

## 5. Lab operating notes

- Proposals may come from human intuition, `just analyze`, LLM critic, or model shadow — **trust is the validation gate**, not the proposer.
- Multi-testing: use BH-FDR / documented scan discipline when scanning many slices (`analyze.py`).
- Stand-aside is success.
- PMCC research stays in PMCC tools/playbooks; do not force short-premium model authority onto PMCC without a separate gate design.
- Proposed future CLI (not built): `just research-scoreboard` to print/append this log.

---

## 6. Change control for this file

| Allowed without ship | Not allowed without SHIP row + firewall |
|----------------------|----------------------------------------|
| Append proposal rows | Flip model production flags |
| Update freeze snapshots (new BASELINE row + new §3 block or dated subsection) | Quietly edit historical scoreboard rows |
| Fix typos / clarify firewall links | Change strategy defaults “to match lab” |

When a freeze is re-run later, **append** a new BASELINE row and a new dated subsection under §3 rather than erasing prior freeze numbers.

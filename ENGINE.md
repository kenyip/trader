# Backtest Engine

Source of truth for the **harness** — how we test strategies. Trading rules live in [STRATEGY.md](STRATEGY.md).

This document follows a fixed convention: **current state at top, dated history at bottom.** When the engine changes, the top is rewritten in place and the bottom gets a new dated entry.

---

## Current state — v1.10 harness + v1.14 observability (positions status now carries optional model_management_advice for advisor shadow; no change to event loop / check_exits)

> v1.10 introduces **trade-group bookkeeping** (chains of rolled positions counted as one logical trade), **group-level + capital-time metrics**, a **generalized roll mechanic** with explicit chain caps (`max_rolls_per_group`, `max_chain_loss_mult`), the **archetype bake-off harness** (`archetype_bakeoff.py` + `just bakeoff`) for head-to-head comparison of strategy *shapes* rather than individual knobs, and **`group_id` support in live position tracking** (`positions.yaml` schema gains `group_id` + retained `closed_positions:` history; `manage_positions.py` gains `roll` subcommand and chain P/L display). No strategy changes ship; the v1.13 strategy is bit-identical pre/post-v1.10. The bake-off's first run confirmed the v1.13 shape as dominant over three challenger archetypes — null-resulted in STRATEGY.md.

### Module map

| File | Purpose |
|---|---|
| `data.py` | yfinance loader (with disk cache in `.cache/`), feature pipeline, regime classifier |
| `pricing.py` | Black-Scholes price + greeks (Δ Γ Θ ν ρ), closed-form `strike_from_delta`, `Quote` dataclass, `peek_position` (v1.12) |
| `backtest.py` | `Position` (mark-to-market, v1.9 per-position overrides, v1.10 `group_id` for chain tracking), `Backtester` event loop (v1.10 chain accumulators + cap policy), `compute_metrics` (v1.10 group + capital-time keys), `groupwise_pnl_by_period`, `trades_to_dataframe` |
| `strategies.py` | `StrategyConfig`, `pick_entry()`, `check_exits()` (7-rung ladder + v1.9 exit-side adaptive hook), `ADAPTIVE_RULES` + `ADAPTIVE_EXIT_RULES` registries |
| `analyze.py` | Automated rule-proposer — quartile + custom-edge buckets, v1.13 narrow-window scan + 2-feature `--pairs` interactions, BH-FDR correction, emits v1.11 hook-syntax rule sketches |
| `validate_rule.py` | A/B harness — runs baseline vs candidate across 5y backtest + 12-regime suite + walk-forward OOS, emits a TRIPLE-WIN/MIXED/NULL verdict per the cost-function policy |
| `sweep.py` | Knob-sweep harness — 1-D / 2-D grids over `StrategyConfig` knobs with cost-function scoring + catastrophe flags |
| `archetypes.py` | v1.10 — named `StrategyConfig` presets (HoldToDecay / QuickHarvest / PremiumSlow / ReversalScalp) — coherent (entry × exit × chain-cap) tuples for head-to-head bake-offs |
| `archetype_bakeoff.py` | v1.10 — runs each archetype × ticker through 5y + 12-regime + walk-forward static OOS; comparative scoreboard with group-level + capital-time metrics |
| `run_backtest.py` | Driver — runs baseline on TSLA + TSLL |
| `optimize.py` | Walk-forward optimiser — rolling train/test windows, grid search over `StrategyConfig` knobs, composite score, modal-best aggregation |
| `scenarios.py` | Regime scenario suite — canonical 21-day historical windows per regime (huge_down, normal_down, flat, normal_up, huge_up, v_recovery, inverse_v); frozen for reproducibility |
| `run_scenarios.py` | Runs current strategy against the canonical scenario set; comparative per-regime table |
| `live.py` | Today's recommendation. Calls the **same** `pick_entry()` used by the backtest, so the live signal automatically tracks any strategy tuning. CLI + library |
| `tsla_options_dashboard.py` | Streamlit dashboard — Today / Positions / Performance / Scenarios tabs, all driven off the engine modules above |
| `positions.py` | Active-position tracker — loads `positions.yaml`, marks each open position with today's data, runs the exit ladder. Read-only against trading state. |
| `manage_positions.py` | CLI for the position tracker — `add` / `close` / `check` / `example` subcommands. `just positions` is the convenience recipe. |

### Data flow

```
yfinance OHLCV ──► data.build() ──► features DataFrame ──► Backtester ──► trades list
                       │                                       │
                       │                                       └► compute_metrics()
                       │
                       ├─ returns 1/5/14/30d
                       ├─ EMAs 9/21/55/200 + ema_stack score
                       ├─ RSI, MACD, ATR, Bollinger %B
                       ├─ HV20/30/60, iv_proxy (= HV30), iv_rank (252d percentile)
                       ├─ volume_surge (today / 20d avg)
                       ├─ intraday_return ((close-open)/open)
                       └─ regime tag + reversal/high_iv flags
```

### Pricing model

- **Black-Scholes** with continuous dividend yield `q` (default 0) and risk-free rate `r` (default 0.04)
- **Strike-from-delta is closed-form** (inverted via `norm.ppf`), no root-finder — round-trips to machine precision
- **Strikes round to $2.50** by default (`round_strike(K, 2.5)`)
- **IV proxy** = annualised HV30 from underlying. This is the v1 stand-in for real chain IV; live mode should overwrite the `iv_proxy` column with quoted IV
- **At expiration (T ≤ 0)** options settle at intrinsic; delta returns ±1 ITM or 0 OTM

### Event loop semantics

- **One position open at a time per ticker.** Stacking is not modelled in v1
- **Daily bars.** Decisions evaluated at each day's close. The exit ladder cannot fire intraday — this is the main known limitation (see below)
- **Per-bar sequence:**
  1. If a position is open: mark to market, run `check_exits()`, close if any rung fires
  2. If flat: run `pick_entry()`, open if a signal is returned
- **At end of data:** any open position is closed at the last bar's mark with reason `end_of_data`
- **DTE / time decay:** uses calendar days (`(expiration - today).days / 365`). Weekends decay correctly because they pass between trading rows.

### Metrics computed

Per backtest: `n_trades`, `win_rate_pct`, `total_pnl_per_contract`, `avg_pnl_per_contract`, `avg_win_per_contract`, `avg_loss_per_contract`, `profit_factor`, `max_dd_per_contract`, `avg_days_held`, and an `exit_reasons` breakdown (count by ladder rung). All P/L is per 1 contract (×100 the per-share number).

### How to run

```bash
just test                                  # today's live recommendation (TSLA + TSLL)
just run                                   # launch the Streamlit dashboard on localhost
just backtest                              # full backtest on TSLA + TSLL, 5y, defaults
just backtest -- --tickers TSLA --period 10y --dump-trades
just scenarios                             # regime stress-test — REQUIRED before/after strategy changes
just scenarios-discover                    # re-curate canonical windows (if data has drifted)
just optimize                              # walk-forward sweep, ~5s per ticker
just optimize -- --train-days 180 --test-days 45
.venv/bin/python live.py --help
.venv/bin/python run_backtest.py --help
.venv/bin/python optimize.py --help
.venv/bin/python run_scenarios.py --help
```

`--dump-trades` writes a per-trade CSV to `.cache/<ticker>_trades.csv` for inspection.

### Live recommendation + dashboard (`live.py`, `tsla_options_dashboard.py`)

- **Single source of truth.** `live.py::make_recommendation()` calls `strategies.pick_entry()` — the exact function the backtest uses. There is no parallel "live engine" with its own logic. Any change to `strategies.py` or `StrategyConfig` defaults flows through to the live signal automatically.
- **Stand-aside reasons are surfaced.** When the strategy says "no trade," the recommendation includes a `reason` field (low IV rank, bearish regime, etc.) so a human can sanity-check.
- **Exit-ladder targets are pre-computed.** Today's recommendation includes the exact buy-back price for profit target, the per-day daily-capture threshold, the max-loss buy-back price, and the delta-breach / DTE-stop levels. Print it once and you have the full exit plan.
- **Dashboard tabs:** `Today` (live rec + features), `Performance` (full-period equity curve + last 10 trades + exit-reason breakdown), `Scenarios` (regime suite table). All three views are driven by the engine modules — no duplicate logic.
- **Sidebar shows current `StrategyConfig`** read-only. Tuning happens in `strategies.py`, validated via `just scenarios` / `just optimize`. The dashboard does not edit the config — that's intentional separation of monitoring from research.
- **Caching:** Streamlit caches data loads and backtest runs for 1h via `@st.cache_data`. Edit a strategy file → restart Streamlit, or use the Rerun button.

### Scenario suite (`scenarios.py` + `run_scenarios.py`)

- **Purpose:** Stress-test every strategy change against fixed canonical windows representing each market regime. Aggregate metrics can hide regime-specific failure modes (e.g. selling short calls during a +59% rally) — only the per-regime view surfaces them.
- **12 regimes**, two categories:
  - **Direction / shape (mutually exclusive):** `huge_down`, `normal_down`, `flat`, `normal_up`, `huge_up`, `v_recovery`, `inverse_v`.
  - **Tail / vol / event (additive — can co-occur with direction):** `gap_shock`, `vol_crush`, `vol_expansion`, `chop_whipsaw`, `earnings_window`. Added 2026-05-12 to align the suite with the "manage extreme moves" cost function.
- **`classify_window` returns `set[str]`** — a single window can match multiple regimes (e.g. a window can be both `huge_up` and `vol_expansion`). Discovery buckets windows into all matching labels.
- **Canonical windows:** one fixed 21-day window per regime per ticker, hardcoded in `scenarios.py::CANONICAL_SCENARIOS`. Frozen so strategy A/B comparisons are direct. Earnings windows are anchored on the known TSLA earnings dates in `TSLA_EARNINGS_DATES`.
- **Re-curation:** if data drifts substantially over time (years), run `just scenarios-discover` to print fresh candidate windows and update `CANONICAL_SCENARIOS`.
- **TSLL flat is intentionally absent.** 2x leverage on a high-vol stock means TSLL almost never sits in a sub-7%-swing window — the discovery routine finds zero matches. Acknowledged limitation, not a bug.
- **CLAUDE.md rule:** `just scenarios` is required before AND after every strategy change. Aggregate-metric tuning is necessary but not sufficient.

### Walk-forward optimiser (`optimize.py`)

- **Windows:** train on the prior `train_days` (default 252), test on the next `test_days` (default 63), roll forward by `test_days`.
- **Grid:** edit `PARAM_GRID` at the top of `optimize.py` to choose knobs and values. Current sweep is 4 knobs × 54 combos.
- **Score:** `total_pnl_per_contract − 0.5 × max_dd_per_contract` with a minimum trade count of 5. The DD penalty is what stops the optimiser from chasing strategies that print P/L into a tail blow-up.
- **Aggregation:** per-window winners are reported individually plus a *modal-best* recommendation (the value of each knob that wins the most windows). Modal-best is the input to "what default should we ship" decisions.
- **Defaults rule (per CLAUDE.md):** only update `StrategyConfig` defaults when modal value has clear consensus across windows — not on ties.

### Known limitations (current)

1. **Daily-bar gap risk — partially mitigated in v1.5.** Exit ladder still cannot trigger intraday. Gap-day max_loss exits now apply a `gap_slippage_mult` shock so accounting reflects realistic fill, but the strategy still can't *react* to gaps mid-session. The `gap_shock` canonical scenario measures this. Full fix path: feed intraday bars to the same loop.
2. **IV proxy ≠ real IV.** `iv_proxy = HV30` underestimates real implied vol (which typically trades 3-15 vol points over HV). Credits collected in backtest are therefore lower than reality — strategies look slightly less profitable than they would be live. The bias is consistent across strategies, so *relative* comparisons are valid.
3. **No bid/ask spread modelled.** `slippage_pct` knob exists in `StrategyConfig` but defaults to 0. Should be set to ~1-2% for realistic fills.
4. **Single position per ticker.** No portfolio-level effects, no correlation between TSLA and TSLL trades. No assignment handling (Phase 7 wheel mechanic addresses this).
5. **No transaction costs / commissions.** Negligible at most brokers for the volumes we'd trade, but worth noting.
6. **Position sizing is per-contract.** No "% of capital" sizer — multiply outputs by your contract count.

### Configuration knobs (`StrategyConfig`)

See `strategies.py` for the dataclass. Current defaults documented in [STRATEGY.md](STRATEGY.md#current-config-defaults).

### Roadmap

- **Phase 7.5 (strategy, next):** Sweep `long_dte` to 7/14 days against the 12-regime suite. Sweep surfaced TSLA 5y P/L going from +$1,583 to +$4,286 with $579 DD at 7-DTE; must be regime-validated before shipping as v1.5 default.
- **Phase 8 (engine, stretch):** Intraday-bar mode (1m/5m yfinance bars, ~30-60 days available) to validate the intraday reversal rule and let exit-ladder stops fire mid-session. Would *avoid* the gap_slippage shock entirely.
- **Phase 9 (stretch):** Real historical option chains (Polygon/Tradier) to replace the HV30 IV proxy.
- **Phase 10 (research, stretch):** LLM critic loop — post-`just scenarios` feed the per-regime table + strategy source to an LLM that proposes a `StrategyConfig` diff. Hygiene rule: LLM sees only backward-looking summaries + code, never tomorrow's bars; proposed diffs are always validated by `just scenarios` before adoption.
- **Phase 11 (research, stretch):** Strategy registry. Refactor `pick_entry` into a registry of named strategies (single-leg short premium, wheel, short strangle, calendar spread, iron condor). Add a meta-layer that picks which strategy is *eligible* given today's features. Closes the loop on "find different strategies based on signals."
- **Done:** Phase 4.5 (v1.2 strategy fixes — bearish gate + defensive-call trend gate), Phase 5 (live + dashboard wired through `pick_entry()`), Phase 5.5 (scenario suite 7→12 regimes), Phase 6 (engine polish — min_credit_pct + gap-slippage), Phase 7 (wheel mechanic — opt-in mode; shipped but not enabled by default since data showed v1.3 short-premium is better than wheel on this history).

---

## History

### 2026-05-14 — Engine v1.10: trade-group bookkeeping + archetype bake-off framework

User's framing: "rolling a trade to manage out should be considered the same trade. Make every trade group positive, even if it became a small profit or breakeven." That reframes the unit of analysis — a *trade group* is the chain of one or more Positions linked by rolls (the originating entry + any defensive rolls + any wheel-continuation legs), terminating at a clean exit or a cap. P/L, win rate, worst-case, and capital-time are all measured at this group level. Aggregate P/L numbers under-counted fast-cycling archetypes and over-credited slow-rolling ones.

**Position + Backtester extensions:**
- `Position.group_id: int = -1` — chain id. Fresh entries get a new id via `Backtester._assign_new_group()`; rolled positions and wheel continuation legs (assigned stock, CC during HOLDING) inherit. `-1` is legacy (pre-v1.10 trades treated as single-position groups by `compute_metrics`).
- `Backtester._chain_position_count`, `_chain_realized_pnl`, `_chain_original_credit` — chain accumulators. Reset together via `_reset_chain()` when a chain terminates.
- **Generalized roll mechanic.** v1.8's `is_roll` single-flag check (one roll max) replaced with two cap fields on `StrategyConfig`:
  - `max_rolls_per_group: int = 1` (preserves v1.8 default behavior)
  - `max_chain_loss_mult: float = 2.0` (caps cumulative chain loss in multiples of the *first* position's credit)

  Both gate the existing `roll_on_max_loss` path. When either is exceeded the chain accepts the loss and resets; the next bar's entry opens a fresh group. Default values preserve v1.9 behavior — only archetypes that enable `roll_on_max_loss` see the new policy.

**`compute_metrics` — 10 new keys, all legacy keys preserved bit-identical:**

| Key | Meaning |
|---|---|
| `n_groups` | distinct chains (legacy trades = 1 group each) |
| `group_win_rate_pct` | % of groups with chain P/L ≥ 0 — the new cost-function primary |
| `avg/worst/best_group_pnl_per_contract` | distribution across groups |
| `avg/max_positions_per_group` | chain-length stats (1.00 = no rolls fired) |
| `capital_days_per_contract` | total strike-days at risk |
| `pnl_per_capital_year_pct` | annualized return on capital-at-risk — the *fair* score for archetypes that recycle capital at very different speeds |
| `trade_density_per_year` | groups per market-year |

**`groupwise_pnl_by_period(trades, freq='Q')`** — buckets group P/L by close-date period. Supports the "every quarter ≥ $0" criterion for archetype acceptance.

**Archetype bake-off (`archetypes.py` + `archetype_bakeoff.py` + `just bakeoff`):**

The shift from knob-sweep to *shape-sweep*. Four archetypes defined as coherent `(entry × exit × risk × roll-policy)` `StrategyConfig` tuples per ticker: **HoldToDecay** (v1.13 control), **QuickHarvest** (1–2 DTE, Δ0.35, 18% profit-take, 1.5× chain cap), **PremiumSlow** (14–21 DTE, Δ0.15, 50% profit-take, 2-roll chain), **ReversalScalp** (1 DTE, Δ0.40, 10% profit-take, no rolling). The harness runs each archetype × ticker through 5y backtest + 12-regime suite + walk-forward static OOS, scored on the new group-level + capital-time metrics. Non-control archetypes ship with `adaptive_rules=()` intentionally — the v1.13 rule fleet was derived under HoldToDecay's trade log and does not transfer; new archetypes must re-derive rules from their own output.

**Live position tracking (`positions.py` + `manage_positions.py`):** v1.10 brings group/chain support to live trading state.
- `positions.yaml` schema gains optional `group_id` field (auto-assigned on `add`, inherited on `roll`).
- New `closed_positions:` section retains the chain history when a position is closed or rolled — chain P/L stays inspectable for any still-open group.
- New `manage_positions.py roll` subcommand: closes one leg, opens a new leg in the same group, prints chain status.
- `positions.py::check_position` accepts `closed_positions=` and surfaces `chain_n_closed`, `chain_realized_pnl_per_share`, `chain_total_pnl_per_share` so the user sees the chain's cumulative P/L, not just the current leg's mark-to-market.

**Engine-level rationale.** Before v1.10 the engine measured per-position outcomes; after v1.10 it measures per-chain outcomes. That changes which strategies look good: TSLL's per-contract P/L is 1/5 of TSLA's but **per capital-year it's +232% vs +75% on TSLA** — TSLL recycles capital 2× as fast at smaller absolute scale. Without capital-time metrics, an archetype bake-off would have systematically misled in TSLA's favor. With them, comparisons across very different shapes (1-DTE quick scalps vs 21-DTE slow theta) are honest.

**Caveat noted, not yet fixed.** Across all four archetypes in the v1.10 bake-off, `avg_positions_per_group = 1.00` — no rolls actually fired despite QuickHarvest and PremiumSlow enabling `roll_on_max_loss=True`. `pick_roll`'s strategy-side safety rails (further-OTM strike + `roll_credit_ratio ≥ 1.0`) appear to decline every candidate. The bake-off's conclusion (HoldToDecay dominant) holds regardless — the alternatives lose on the *first* leg, before a roll could help — but a future engine-level investigation of why `pick_roll` declines is worth queuing.

### 2026-05-14 — Engine v1.9: per-position knob overrides + exit-side adaptive hook (M4 + M5)

Two extensions to the adaptive-rule contract, both at the boundary between `strategies.py` and `backtest.py`. No change to the event loop's per-bar sequence; the additions are pure extension points.

**Per-position overrides (M4).** `Position` gets three optional fields with `None` default:

```python
max_loss_mult_override: Optional[float] = None
delta_breach_override: Optional[float] = None
profit_target_override: Optional[float] = None
```

Plus `daily_capture_mult` (already on Position) and `min_credit_pct` (an entry-time filter, applied during `pick_entry`) become controllable per-entry. The entry-side rule dict contract grows the matching keys: any rule may return any subset of `{min_credit_pct, max_loss_mult, delta_breach, profit_target, daily_capture_mult}` alongside the v1.11 `{side, dte, target_delta, skip}`. `pick_entry` consumes them and stores override fields on the resulting `Position`. `check_exits` prefers position-level values over `cfg`. Verified: baseline 5y backtests are bit-for-bit identical before/after the plumbing on both tickers.

**Exit-side adaptive hook (M5).** Mirrors the entry hook pattern exactly:

```python
@dataclass
class StrategyConfig:
    exit_rules: tuple = ()      # names of rules from ADAPTIVE_EXIT_RULES

ADAPTIVE_EXIT_RULES: dict[str, Callable] = {}

def adapt_exit_params(position, mark, row, cfg) -> dict:
    """Run any active exit-side rules in registration order. First rule
    returning {'close': True, ...} wins; ladder is short-circuited."""
```

The hook is called at the top of `check_exits` after the expiration check and before the standard ladder. Skipped for `is_wheel_cc` positions (those have their own simplified ladder). When `cfg.exit_rules = ()`, the call is effectively a single dict lookup — zero behavioral or measurable performance cost.

**Engine-side rationale.** Both extensions are interface widenings, not new mechanics. They take the v1.11 architecture from "rules can choose to skip or modify the entry params" to "rules are the strategy's general-purpose customization layer for both entry and exit." A shipped rule is now a ≤30-line change that touches only `strategies.py` (no engine code, no caller code) — the GOAL.md "stable interface" criterion.

**Demonstration rule registered (not enabled in defaults):** `take_half_on_reversal` closes any short option when pnl ≥ 50% of credit AND today is a `reversal` (puts) or `bullish` (calls — for the bear-side call branch). Forced-fire test rule confirms the hook works end-to-end: with a permissive force-close rule active, exit_reasons shows 97 of 169 TSLL exits attributed to the new path; without it, the standard ladder gets all of them.

**Validation harness — `validate_rule.py`** (also added this session): single-shot A/B that runs baseline vs candidate across 5y backtest + 12-regime suite + walk-forward static OOS, prints per-regime deltas + cost-function score, emits a TRIPLE-WIN / MIXED / NULL verdict per the cost-function policy. Used to validate every adaptive rule shipped in v1.13. Lives alongside `sweep.py` in the operational-tooling tier.

### 2026-05-13 — Engine v1.8: roll-on-max_loss opt-in mechanic

User asked: when max_loss fires, can we roll instead of leaving flat? The mechanic was a meaningful engine extension — first engine-side change since the wheel mechanic in v1.6.

**Added:**
- `Position.is_roll: bool` field — flags positions opened via roll-on-max_loss so they can't roll recursively.
- `Backtester.roll_fn: Optional[Callable]` field — set by the driver to `strategies.pick_roll` when `cfg.roll_on_max_loss` is True.
- `Backtester.run()` inline handling: when `max_loss` fires and `roll_on_max_loss` is set and the closing position is *not itself a roll*, the engine calls `roll_fn(row, cfg, S, today, closed_position, close_cost)` immediately after `_close`. If the function returns a valid Position, the new position is opened on the same bar (the regular `pick_entry` flow is skipped that bar).
- `strategies.pick_roll(...)` — strategy-layer helper that constructs the candidate rolled position. Safety rails: same side, strictly further OTM than original strike, `new_credit ≥ roll_credit_ratio × close_cost`.
- `StrategyConfig` knobs: `roll_on_max_loss` (bool, default False), `roll_dte` (int, 14), `roll_target_delta` (float, 0.15), `roll_credit_ratio` (float, 1.0 = credit roll only).
- Wired through `run_backtest`, `sweep`, `run_scenarios`, `optimize`, `tsla_options_dashboard`.

**Engine-level rationale.** The trade log captures the roll cleanly as two consecutive Position records (a `max_loss` close immediately followed by a `regime_at_entry='rolled'` open on the same date). No bookkeeping changes to `compute_metrics` or `trades_to_dataframe`. This is the same pattern used for `wheel` mode — an opt-in mechanic with engine-level support but strategy-layer parameterization.

**Empirical outcome.** The mechanic itself works; the *hypothesis* didn't pan out. See [STRATEGY.md round 9 history](STRATEGY.md#history) for the sweep results. v1.8 ships the mechanic as a research capability — disabled by default, available for future use (e.g., once Phase 8 intraday-bar mode lands, rolls might catch faster recoveries that daily bars miss).

### 2026-05-13 — Phase 10: `sweep.py` — reusable knob-sweep harness for the critic loop

User feedback after 4 critic rounds: "build stronger with that — try and test out is what we need from the engine." Reified the LLM-critic loop's *try-and-test* pattern as a first-class engine capability.

**Added:**
- `sweep.py` — single tool that replaces the ad-hoc `sweep_*.py` scripts. Takes a `StrategyConfig` knob name + comma-separated values (1-D) or a `--vs` knob with `--vs-values` (2-D grid). For each cell: runs 5y backtest + 12-regime suite, computes cost-function score (`P/L − dd_weight × DD`), tracks the current per-ticker default and the best value found, flags catastrophic worst-regime regressions with `⚠`.
- `just sweep` recipe wiring `sweep.py` into the standard workflow.
- Knob-name validation against `StrategyConfig` (typo → list of available knobs).

**Why this matters architecturally:** before sweep.py, each critic round required ~50 lines of bespoke scaffolding (8 such scripts accumulated by round 4). The pattern was identical; the variation was just the knob name. Externalizing the pattern means future rounds are minutes, not 30+ minutes — and the same tool is available to the user for their own hypothesis tests without needing me in the loop.

**Used immediately in round 5 of the critic loop:** `just sweep max_loss_mult --values 1.2,1.5,1.8,2.0,2.5,3.0,4.0` produced the per-ticker analysis that shipped TSLL `max_loss_mult = 3.0`. Strategy-side write-up in STRATEGY.md v1.8 history.

**Older bespoke `sweep_*.py` scripts** (in repo root: `sweep_min_credit.py`, `sweep_delta_breach.py`, `sweep_daily_capture.py`, `sweep_iv_rank_min.py`, `sweep_profit_target.py`, `sweep_wheel.py`, `sweep_dte_delta.py`, `sweep_dte_delta_regimes.py`, `sweep_mcp_v15.py`) are now superseded. Kept as historical artifacts for now — each maps to a specific STRATEGY.md history entry — but should be deleted in a future cleanup pass.

### 2026-05-13 — Phase 9: active-position tracker (`positions.py` + dashboard tab)

User asked for a way to enter live open positions and have the engine compute daily exit guidance. Previously, the engine had no persistent state for "active" positions — the backtest's daily-mark-and-check loop only ran inside `Backtester.run()`, while `live.py` only returned static entry-time targets.

**Added:**
- `positions.py` — module that loads `positions.yaml` (gitignored), reconstructs `backtest.Position` objects from the user's records, pulls today's market data via `data.build()`, and runs `Position.mark()` + `strategies.check_exits()` against today's bar. Returns a status dict per position with explicit action recommendation. Supports `current_price_override` so the user can plug in the actual broker mark when the BSM/HV30 estimate diverges.
- `manage_positions.py` — CLI driver. Subcommands: `check` (default — status of all), `add`, `close`, `example`. Wired through `just positions`.
- Dashboard `Positions` tab — status table with HOLD/CLOSE flags, per-position expandable detail with full exit-ladder targets, add-position form, mark-as-closed buttons.
- `positions.yaml` added to `.gitignore` — user-specific trading state never committed.
- `pyyaml` added to `requirements.txt`.
- Dashboard's Today / Performance / Scenarios tabs **fixed to use `get_config(ticker)`** (was using bare `StrategyConfig()`, which silently fell back to v1.3-equivalent defaults instead of the v1.5+ per-ticker config). Sidebar now shows per-ticker config in expandable sections.

**Architecture:** `positions.py` is read-only against trading state — the engine never sends orders, only surfaces what the exit ladder says about today. The user's broker remains the source of truth for actual fills; the tool's job is "what would the engine do today if it were managing my positions."

### 2026-05-13 — Phase 8: walk-forward `--static` flag + LLM critic loop demonstrated

Two small additions to `optimize.py`:

- `walk_forward_static(df, cfg, ...)` — validates a fixed `StrategyConfig` across rolling OOS windows without sweeping. Used to confirm v1.5 generalizes (it does: TSLA OOS swing v1.1 → v1.5 of +$18,739, worst single window cut from −$5,960 to −$244).
- `--static` CLI flag plumbs the new mode through `optimize.py main()`.
- `optimize.py` now uses `get_config(ticker)` so the per-ticker defaults flow into walk-forward runs.

**LLM-critic loop demonstrated end-to-end.** Claude (acting as critic in-session) was given backward-looking inputs only (per-regime suite table, exit-reason breakdowns, `strategies.py` source, cost function) and proposed raising `delta_breach` from 0.38 (a v1.1-era value calibrated for 30-DTE puts) to a higher value for v1.5's short DTEs. Hypothesis: at 3-7 DTE, gamma is much higher, so 0.38 fires on routine noise. Validation sweep confirmed: TSLA optimum at 0.50 (+$1,160 P/L, −24% DD), TSLL optimum at 0.45 (modest improvement; 0.50 hurts because leveraged moves punish further-out tolerance). Shipped as v1.6 per-ticker defaults. Full write-up in STRATEGY.md v1.6 history entry.

**Engine-level observation.** The critic's value was *questioning constants*. The DTE × delta sweep held `delta_breach` fixed at 0.38; the LLM critic was the layer that noticed the implicit assumption baked into the grid. Future critic iterations should target other v1.1-era assumptions (`max_loss_mult`, `daily_capture_mult_*`, `iv_rank_min`) under the new short-DTE regime.

### 2026-05-12 — Phase 7: wheel mechanic — state machine + assignment handling (engine v1.6)

Architectural extension to `backtest.py`. `Backtester` now optionally runs a 4-state wheel machine (IDLE → SHORT_PUT → HOLDING → COVERED → IDLE) when `config.wheel_enabled = True`. Default is off, so all prior backtests are unchanged.

**New mechanics:**
- `Backtester.stock_basis` + `Backtester.stock_entry_date` track the long-stock leg.
- `_assign_put`: when a short put expires ITM in wheel mode, the put is recorded as `exit_reason='assigned'`, intrinsic-priced; `stock_basis = strike`.
- `_assign_call_away`: when a covered call expires ITM, the CC is closed at zero (assignment-away); a synthetic `Position(side='stock')` is appended with `credit=strike` (sale proceeds) and `exit_price=basis` so `compute_metrics` picks up the stock P/L naturally.
- `_close_stock`: realizes the stock leg as the synthetic Position. Also called at end-of-data if the wheel is mid-cycle.
- `Position.side` now legitimately includes `'stock'` for these synthetic legs. `Position.is_wheel_cc` flag tags covered calls so `check_exits` runs the simplified wheel-CC ladder.
- New `wheel_cc_fn` callable on `Backtester` (set by the driver to `pick_covered_call`); invoked when in HOLDING state to open a CC.

**Strategy layer additions** (`strategies.py`):
- `pick_covered_call` opens CCs at basis (aggressive — the wheel goal is to cycle out, not preserve stock).
- `pick_entry` switches to `wheel_put_dte` (default 14) when wheel is on.
- `check_exits` relaxes max_loss (via `wheel_put_max_loss_mult`), skips `dte_stop` / `delta_breach` / `regime_flip` for wheel-mode puts; runs a 2-rung ladder (expired + early-profit) for wheel CCs.

**CLI plumbing:**
- `run_backtest.py --wheel` and `run_scenarios.py --wheel` flip the flag.
- `sweep_wheel.py` is a parameter-sweep harness in the repo root that compares wheel variants against cash-only across both tickers and prints exit-reason breakdowns.

**Engine-level observations from the sweep.** The architecture works — `assigned`, `assigned_away`, and `wheel_close` exit reasons all fire correctly. But the v1.3 strategy's exit gates are so effective at avoiding wheel-eligible conditions that the mechanic rarely triggers (0–4 cycles over 5y depending on relaxation). The sweep's most valuable output was a *strategy-level* finding (short-DTE puts on TSLA), not a wheel-level one. See STRATEGY.md v1.4 for the full results table.

### 2026-05-12 — Phase 6: engine polish — gap-slippage shock + slippage accounting fix (engine v1.5)

Two engine-side changes in `backtest.py`. Strategy logic unchanged.

**New `Backtester._fill_price` method** — computes the effective exit price the engine actually fills at:

- Uniform `slippage_pct` applied on every exit (was previously applied only inside `check_exits` for the *decision*, while `exit_price` stored on the Position was the raw mark — a subtle accounting inconsistency that didn't bite because the default was 0.0).
- Plus a conditional `gap_slippage_mult` shock when `max_loss` fires AND overnight `|open − prev_close| / prev_close > gap_threshold_pct`. Models the realistic case where a stop "should have fired at yesterday's close" but the price gapped past it overnight, so the actual fill is the gap-open or worse.

**`Backtester.run` loop** — now tracks `prev_close` across iterations so `_fill_price` can detect gap days.

**Engine-level rationale.** The `gap_shock` canonical scenario added in v1.4 surfaced TSLA −$676 on a window where the underlying net move was only +0.6% — every dollar of loss came from gap-day exits at unrealistically good fills. The shock fixes that. After Phase 6, gap_shock loss became −$815 (the truth) and the TSLA 5y backtest went from a likely-overstated +$2,243 to a more honest +$1,583. This is information, not regression.

**Strategy-side knob added (`strategies.py`):** `min_credit_pct = 0.010` filter. Skips entries where `credit / strike` is below 1% — these were the dominant max-loss-tail mechanism, where a $1 credit on $250 strike could lose $20 before the multiplier-based stop catches it. Swept across `[0.0, 0.003, 0.005, 0.008, 0.010, 0.015, 0.020, 0.030]` against both 12-regime suite and 5y backtest; 0.010 is the unique value that improves both tickers simultaneously. TSLA max DD fell 28% ($4,910 → $3,534) and max_loss exit count fell from 15 → 10 (filter prevented the worst trades from being opened).

**Sweep harness** lives at `sweep_min_credit.py` in the repo root — useful template for similar one-shot parameter sweeps before reaching for the full walk-forward optimiser.

### 2026-05-12 — Phase 5.5: scenario suite expanded 7 → 12 regimes (engine v1.4)

Added five tail / vol / event regimes to `scenarios.py`: `gap_shock`, `vol_crush`, `vol_expansion`, `chop_whipsaw`, `earnings_window`. Refactored `classify_window` to return `set[str]` so a single window can match multiple regime labels. Added `TSLA_EARNINGS_DATES` constant for the event-anchored regime.

**Engine-level rationale.** The original 7 regimes covered net direction × shape but not the failure modes that dominate short-premium tail risk: overnight gaps, vol expansion, choppy whipsawing markets, and earnings-induced IV swings. Per the strategy cost function ("optimize for extreme-case management"), the suite needed to be expanded to make those failure modes measurable.

**Immediately surfaced findings on v1.2:**

- `gap_shock` is now a canonical test for the daily-bar engine limitation. TSLA lost $676 on a window where the net underlying move was only +0.6% — every dollar of loss came from gap days. This makes Phase 6 (`slippage_pct` shock on `max_loss` exits) a well-defined and measurable next step rather than a heuristic.
- `vol_expansion` and `chop_whipsaw` produced zero trades on TSLA — the existing gates correctly stand the strategy aside. This is a successful outcome under the tail-management cost function, not a missed-opportunity bug.
- TSLA-vs-TSLL divergence on `chop_whipsaw`: same code, same config, but TSLL whipsawed where TSLA stood aside. A new class of finding the 7-regime suite could not have surfaced.

### 2026-05-12 — Phase 4.5: strategy-side regime fixes (engine v1.3, strategy v1.2)

No engine changes; logged here because the `_classify_regime` fix lives in `data.py`. The bearish gate dropped its incoherent `rsi_14 > 75` clause and the defensive-call rule in `strategies.py::pick_entry` gained an `ema_21 < ema_55` trend confirmation. Full strategy-side write-up — including the scenario-suite and full-backtest swings — is in STRATEGY.md's v1.2 history entry.

**Engine-level observations from the fix:**

- The scenario suite did exactly what it was built to do: surfaced the `huge_up` failure that aggregate metrics had hidden, and now confirms the fix per-regime rather than only at the suite total. Both regime-fix targets were addressable as pure-logic edits (no engine work needed) because the engine's feature pipeline already exposed the right inputs (`ema_21`, `ema_55`, `macd`).
- Two regime regressions emerged (`normal_down`, `inverse_v`). The engine's transparent per-regime reporting is what makes these visible — and what makes the next tuning step (engine-side `min_credit_pct` filter + gap-slippage modeling) a well-defined "address the tradeoff" question rather than a blind sweep.

### 2026-05-12 — Phase 5 complete: live + dashboard unified (engine v1.3)

**Added**
- `live.py` — `make_recommendation()` and `format_recommendation()`. CLI prints today's pick for TSLA + TSLL with exit-ladder targets pre-computed in dollars.
- `tsla_options_dashboard.py` — real Streamlit dashboard (replacing the one-line stub). Three tabs: Today / Performance / Scenarios. Sidebar shows current `StrategyConfig`. All views driven by the engine modules — no parallel logic.

**Design decisions locked in**
- **No parallel live engine.** Live recommendation calls `strategies.pick_entry()` directly. The legacy `dynamic_parameter_engine.py` and `strategy_v6_dynamic.py` are no longer the live source of truth and won't be tuned going forward — they survive as historical artifacts only.
- **Dashboard is read-only for strategy.** Tuning happens via code + `just scenarios` + `just optimize`. The dashboard surfaces results, doesn't edit them. This keeps the "what we trade today" experience disconnected from the "what should our strategy be" research loop.
- **Caching at 1 hour** for `load_data` and `run_full_backtest`. Edit strategy → restart Streamlit.
- **`just test` now runs `live.py`** (was `strategy_v6_dynamic.py`).

**Validated**
- `just test` prints rec for both tickers with exit ladder.
- `just run` boots Streamlit on localhost, responds 200, no import errors.
- All three tabs render off the same `StrategyConfig` so changing `strategies.py` is reflected everywhere on next reload.

### 2026-05-12 — Scenario suite added (engine v1.2)

**Added**
- `scenarios.py` — regime classifier (7 regimes), historical-window discovery, frozen `CANONICAL_SCENARIOS` dict (one window per ticker per regime), `canonical_window()` accessor.
- `run_scenarios.py` — runs current strategy against the canonical set; prints per-regime comparative table.
- `just scenarios` and `just scenarios-discover` recipes.

**Design decisions**
- 21 trading days per scenario window (~one month).
- Canonical windows are frozen rather than auto-rediscovered so strategy A/B comparisons are reproducible. Re-curation happens explicitly via `just scenarios-discover` when needed.
- Per-ticker canonical windows. A "huge_down" period for TSLA is also a "huge_down" period for TSLL but with very different return magnitude — we pick windows by ticker so each lives squarely inside its regime band.
- TSLL has no canonical `flat` window — 2x leverage on a high-vol stock makes it impossible to find a 21-day window with <7% intra-window swing. Documented as expected behaviour.

**Validated**
- v1.1 defaults run cleanly across all canonical windows. 5/7 TSLA regimes profitable, 3/6 TSLL. Suite immediately surfaced a *new* failure mode (selling short calls in `huge_up` rallies) that aggregate metrics had hidden.

### 2026-05-12 — Phase 4 complete (engine v1.1)

**Added**
- `optimize.py` — walk-forward optimiser. Rolling windows (default 252 train / 63 test, rolling by test size), grid search over a configurable `PARAM_GRID`, composite scoring (`total_pnl − 0.5 × max_dd` with min-trade floor), per-window detail + modal-best recommendation. Replaces the broken `walk_forward_optimizer.py` (kept around for history only).
- `just optimize [-- args]` recipe.

**Validated**
- Ran 4-knob × 54-combo sweep on 11 TSLA + 6 TSLL quarterly windows in ~10s total. Modal-best converged strongly on two knobs (see STRATEGY.md history for the actual values).

**Engine-level observations from the sweep**
- The optimiser correctly surfaces the *strategy-side* limitation that the bearish regime gate doesn't fire enough — this isn't a bug in the engine but a bug in `data.py::_classify_regime`. Recording it here so we don't conflate "engine works" with "results are good."
- 54 combos × ~15 windows × 2 tickers is sub-10-second territory on stock numpy. Scaling the grid to ~500 combos is still tractable without parallelisation.

### 2026-05-12 — Phase 2 + 3 complete (engine v1.0)

**Added**
- `backtest.py` — `Position` dataclass with `mark()` (BSM during life, intrinsic at expiration); `Backtester` event loop (one position per ticker, strategy-supplied entry/exit callbacks); `compute_metrics`; `trades_to_dataframe`; `format_metrics`
- `strategies.py` — `StrategyConfig` (16 knobs); `pick_entry()` (regime → put/call/skip + strike-from-delta); `check_exits()` with full 7-rung ladder
- `run_backtest.py` — CLI driver with `--tickers` / `--period` / `--dump-trades`
- `just backtest` recipe

**Design decisions locked in**
- One position per ticker at a time (no stacking in v1)
- Exit ladder order: expiration → max_loss → daily_capture → profit_target → delta_breach → dte_stop → regime_flip (max_loss first so we never book a "profit" on a day we'd be stopped)
- DTE stop only applies to entries ≥14 DTE (no point on a 5 DTE trade)
- Calendar days for time decay (theta is per calendar day in reality)
- Credit at entry = theoretical BSM mid × (1 - slippage_pct); exit cost = BSM mid × (1 + slippage_pct)

**Baseline results found in run** — see [STRATEGY.md history](STRATEGY.md#history) for the strategy-side analysis.

### 2026-05-12 — Phase 1 complete (data + pricing modules)

**Added**
- `pricing.py` — Black-Scholes price + greeks + closed-form `strike_from_delta` (inverts to machine precision) + `Quote` dataclass + `round_strike` ($2.50 increments by default)
- `data.py` — yfinance loader with on-disk CSV cache; feature pipeline (returns, EMAs + stack score, RSI, MACD, ATR, BB %B, HV20/30/60, IV proxy + IV rank, volume surge, intraday return); regime classifier merging v5 trend logic + v6 reversal/high-IV flags
- `yfinance>=0.2.40` added to `requirements.txt`

**Validated**
- BSM inverse round-trips to ~1e-16 across put/call × delta {0.15..0.30}
- Pulled 5y TSLA (974 rows) and TSLL (662 rows) from yfinance; cache works
- All features compute without NaN explosions after the warmup drop (loses ~282 rows for `ema_200` + `iv_rank` percentile window)

**Caveat noted but deferred to Phase 3+**
- The bullish-regime gate (inherited from v5) is very strict — only ~4% of historical days qualify. The engine currently treats most days as `neutral`. May need to loosen the volume gate or split into `bullish_strong` / `bullish_lite` tiers if strategies want more bullish-day exposure.

### Pre-engine work (before 2026-05-12)

Strategy iteration happened in scattered scripts and one-off Markdown notes. Those files are preserved in the repo as historical artifacts but **are no longer source of truth**:

- `BACKTESTING_FRAMEWORK.md` — early framework notes
- `DYNAMIC_PARAMETER_MODEL.md`, `INTRADAY_REVERSAL_RULE.md` — small design fragments
- `SHORT_TERM_CALL_*.md` — short-call rules (now encoded in `StrategyConfig` defaults)
- `STRATEGY_OPTIMIZATION_2026-05-12.md` — detailed pre-engine analysis
- `STRATEGY_DEVELOPMENT_LOG.md`, `STRATEGY_RESET_2026-05-12.md` — stubs

The Python files from that era are similarly mixed-quality: `dynamic_parameter_engine.py`, `strategy_v5_optimized.py`, `strategy_v6_dynamic.py`, the two `backtest_*.py` synthetic GBM scripts, and `walk_forward_optimizer.py` (broken — imports a class from a stub) all predate the engine. `walk_forward_optimizer.py` will be replaced in Phase 4.

**v1.14+ note (2026-05-31)**: `Position` and status dicts now carry optional `model_management_advice` (from positions tracker when `StrategyConfig.enable_model_management`). This is read-only observability for the management advisor (traj features + close/roll proposals); does not affect `check_exits` execution or backtest loop. See `positions.py`, `strategies.recommend_management_advisor`, and `simulator/PLAN.md`.



### 2026-07-09 — Platform execution layer (paper-only)

Added local `platform/` package for income-engine autonomy scaffolding. Does **not** alter `backtest.py` event loop, `data.py`, or pricing.

- `platform/execution/broker_adapter.py` — Broker protocol; `PaperBroker` local ledger; `RobinhoodMcpBroker` raises NotConnected.
- `platform/risk_governor.py` + `platform/risk_limits.yaml` + kill-switch file support.
- `platform/autonomy_loop.py` — scan → propose → risk_check → paper_execute (default).
- CLI: `python -m platform.hypothesis_cli`, `just platform-scan`, `just platform-paper-tick`.
- Live broker mutations and Hermes cron that place orders remain **blocked** until Stage1 OAuth + arming (see docs/AGENTIC_AUTONOMY_POLICY.md).

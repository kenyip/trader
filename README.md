# TSLA / TSLL Options Premium Selling — Backtest Engine + Live Tracker

A research harness for designing and validating short-premium options strategies on TSLA and TSLL, plus a live daily-recommendation engine.

## Quick start

```bash
just setup                            # one-time: venv + deps (yfinance, scipy, pandas, pyyaml, …)
just test                             # today's live recommendation for TSLA + TSLL
just run                              # Streamlit dashboard (Today / Positions / Performance / Scenarios)
just backtest                         # full 5y backtest on TSLA + TSLL with per-ticker config
just scenarios                        # 12-regime stress-test (REQUIRED before/after strategy tweaks)
just optimize                         # walk-forward grid search over StrategyConfig knobs
just optimize -- --static             # walk-forward VALIDATION of current per-ticker defaults
just sweep KNOB --values v1,v2,v3     # reusable single-knob sweep (the LLM-critic harness)
just positions                        # status of open positions (per positions.yaml, gitignored)
just positions example                # write a sample positions.yaml template
just positions add ...                # append a position (see `just positions add --help`)

# Free strategy research lab (shadow only — see docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md)
just lab-smoke                        # model-verify + scenarios
just model-verify                     # feature parity smoke
just analyze                          # rule proposer (critic loop)

# PMCC / LEAPS diagonal monitor
just pmcc-manage                      # full PMCC dashboard: marks, premium clock, next action
just pmcc-monitor                     # quiet monitor: silent unless action is needed

# Income Engine desk brief (raw gather; agent synthesizes stance — docs/DESK_BRIEF.md)
just desk-brief                       # session banner + PMCC monitor + short-premium live rec
just desk-brief --full                # full pmcc-manage dashboard in the gather
```

## Source-of-truth documents

These three files are kept current. Everything else in the repo is either code or legacy notes.

| Doc | Covers |
|---|---|
| [**GOAL.md**](GOAL.md) | The end-state goal — data-driven critic loop, success criteria, sequenced milestones. Use as `/goal` input in new sessions. |
| [**ENGINE.md**](ENGINE.md) | The backtest harness — modules, data flow, pricing assumptions, event loop semantics, known limitations, roadmap |
| [**STRATEGY.md**](STRATEGY.md) | The trading rules — entry logic, exit ladder (incl. daily profit capture formula), `StrategyConfig` defaults, latest baseline results, next tuning targets |
| [**docs/PMCC_MONITOR_DEPLOYMENT.md**](docs/PMCC_MONITOR_DEPLOYMENT.md) | PMCC always-on monitor deployment, live position file transfer, Hermes cron, and Telegram gateway setup |
| [**docs/TRADER_AGENT_PROFILE.md**](docs/TRADER_AGENT_PROFILE.md) | Dedicated Hermes `trader` profile: trade-analysis operating principles, local bootstrap, Mac Mini migration path, and privacy boundaries |
| [**docs/TRADER_KNOWLEDGE_MAP.md**](docs/TRADER_KNOWLEDGE_MAP.md) | Memory-vs-skill-vs-repo routing map for the Trader profile, including where recent PMCC learnings and dated playbooks live |
| [**docs/DESK_BRIEF.md**](docs/DESK_BRIEF.md) | Income Engine daily desk brief playbook: one checklist for PMCC + short-premium + stance |
| [**docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md**](docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md) | Cold-start free strategy research lab: production vs lab boundary, weekly loop, Path A/B promotion, exact `just` commands |

Both follow the same convention: **current state at the top, dated history at the bottom.**

## Code map

```
# active engine
data.py                       yfinance loader + feature pipeline + regime classifier
pricing.py                    Black-Scholes price/greeks + strike-from-delta solver
backtest.py                   Position, Backtester event loop, metrics, wheel state machine
strategies.py                 StrategyConfig, DEFAULT_CONFIG_BY_TICKER, get_config(ticker),
                              pick_entry, check_exits, pick_covered_call (wheel)
scenarios.py                  canonical 12-regime windows (huge_down, flat, gap_shock,
                              vol_crush, vol_expansion, chop_whipsaw, earnings_window, ...)
run_backtest.py               CLI for the baseline backtest (--wheel flag for wheel mode)
run_scenarios.py              CLI for the canonical scenario suite
optimize.py                   walk-forward grid search + --static OOS validation of fixed config
sweep.py                      reusable knob-sweep harness (LLM-critic loop)
live.py                       today's recommendation (uses pick_entry + per-ticker get_config)
positions.py                  active-position tracker — runs exit ladder on user's open positions
manage_positions.py           CLI driver for positions (add/close/check/example)
tsla_options_dashboard.py     Streamlit dashboard — Today / Positions / Performance / Scenarios

# user-supplied (gitignored)
positions.yaml                user's open option positions, source of truth for `just positions`

# retired — kept as historical artifacts, do not extend or tune:
dynamic_parameter_engine.py   pre-engine "live" recommender (superseded by live.py)
strategy_v6_dynamic.py        thin wrapper for above
strategy_v5_optimized.py      scenario classifier class (logic absorbed into data.py)
walk_forward_optimizer.py     broken — replaced by optimize.py
tsla_tsll_options_tracker.py  one-line stub
strategy_v4.py / strategy_final.py / recent_performance.py / ab_test_v4_vs_v5.py  stubs
backtest_short_term_calls.py / backtest_strangle_early_exit.py  early synthetic-GBM experiments
sweep_*.py (multiple)         per-round bespoke sweep scripts from critic rounds 1-4 — all
                              superseded by sweep.py; kept for now as artifacts of each round.
```

## Session arc (2026-05-12 to 2026-05-14)

Strategy went from **v1.1 (−$6,242 on TSLA 5y, $12,292 max DD, profit factor 0.87)** to
**v1.13 (+$17,790 on TSLA 5y, $1,107 max DD, profit factor 5.25, 92% win rate)** —
a +$24,032 swing with 91% DD reduction, via the LLM-critic loop and a fleet of 5
empirically-validated adaptive rules.

- **v1.9** introduces the *symmetric direction* rule: regime tells us which side of
  the chain to sell (bullish/neutral → put, bearish → call), then per-ticker DTE ×
  delta tunes for reversal-resistance.
- **v1.10** decouples *exits* from entry signals per ticker. TSLA drops the
  `regime_flip` exit (+$2,214 P/L from letting positions ride to profit-based exits
  instead of being prematurely closed on regime change). TSLL effectively disables
  the `max_loss` dollar-threshold stop — the leveraged-ETF `delta_breach=0.45` is
  the real tail protection.
- **v1.11** lands the *adaptive-rules architecture* — `adapt_entry_params(row, cfg)`
  hook that lets context-aware rules adjust entry params on each bar using all
  available features. No rule ships in v1.11; the architecture is the extension
  point.
- **v1.12** wires the *data-driven proposer* — `analyze.py` ingests trade-log +
  feature-panel + greeks-at-entry, ranks features by effect size, emits rule
  sketches in hook syntax. Ships `tsll_skip_marginal_up` (first adaptive rule)
  validated triple-win.
- **v1.13** (this session) brings the loop to *production:* analyzer extensions
  (`--scan-narrow` with BH-FDR correction, `--pairs` for 2-feature interactions),
  per-position knob overrides (M4), an exit-side adaptive hook (M5), the
  `validate_rule.py` A/B harness, and **4 new adaptive rules** all surfaced
  directly by the analyzer:
  - `tsla_skip_mild_intraday_up` — skip when 0.5% ≤ intraday_return ≤ 1.6%
    (triple-win: +$1,511 P/L, −$749 DD, +$1,604 OOS)
  - `tsll_skip_tuesday` — skip Tuesday entries (3-of-4 surfaces positive)
  - `tsll_skip_post_earnings_drift` — skip 11–21 days after earnings (triple-win)
  - `tsll_skip_downtrend_high_iv` — pair conjunction `ret_14d × iv_rank`
    (triple-win, from `--pairs` scan)
  5 rules total; GOAL.md success criteria reached.

Full progression and per-version learning trail: see [STRATEGY.md history](STRATEGY.md#history)
and [ENGINE.md history](ENGINE.md#history).

## Disclaimer

Educational use only. This is research code, not trading advice.

# Justfile — Trader (Desk A personal tracker + Desk B Agentic engine)
# Repo: ~/dev/trader  ·  package: trader_platform

venv_dir := ".venv"
py       := venv_dir / "bin" / "python"
streamlit := venv_dir / "bin" / "streamlit"

# Show available commands
default:
    @just --list

# One-time setup: create venv and install dependencies
setup:
    #!/usr/bin/env bash
    set -euo pipefail

    # Pick a working python interpreter for bootstrapping
    if command -v python3 >/dev/null 2>&1; then
        BOOT_PY=python3
    elif command -v python >/dev/null 2>&1; then
        BOOT_PY=python
    else
        echo "Error: no 'python3' or 'python' found on PATH." >&2
        echo "Install Python 3.10+ first (e.g. 'sudo pacman -S python' on Arch)." >&2
        exit 1
    fi

    # Create the venv if it isn't there yet (prefer uv when available)
    if [ ! -x "{{py}}" ]; then
        echo "Creating virtual environment in {{venv_dir}}/ ..."
        if command -v uv >/dev/null 2>&1; then
            uv venv "{{venv_dir}}"
        else
            if ! "$BOOT_PY" -m venv "{{venv_dir}}"; then
                echo "" >&2
                echo "Failed to create venv. If you're on Debian/Ubuntu, run:" >&2
                echo "    sudo apt install python3-venv" >&2
                echo "Then re-run 'just setup'." >&2
                exit 1
            fi
        fi
    fi

    echo "Installing dependencies into {{venv_dir}} ..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "{{py}}" -r requirements.txt
    else
        "{{py}}" -m ensurepip --upgrade >/dev/null 2>&1 || true
        "{{py}}" -m pip install --upgrade pip
        "{{py}}" -m pip install -r requirements.txt
    fi

    echo ""
    echo "Setup complete. Try:  just test   or   just run"

# Today's live recommendation (uses the same engine code as the backtest)
test:
    {{py}} live.py

# Launch the Streamlit dashboard
run:
    {{streamlit}} run tsla_options_dashboard.py

# Detailed last 2 weeks trade log
recent-trades:
    {{py}} recent_performance.py

# Run baseline backtest on TSLA + TSLL
backtest *ARGS:
    {{py}} run_backtest.py {{ARGS}}

# Run strategy against canonical regime suite (huge_down, normal_down, flat, ...)
# Use BEFORE and AFTER every strategy tweak per CLAUDE.md
scenarios *ARGS:
    {{py}} run_scenarios.py {{ARGS}}

# Re-curate canonical scenario windows (after data drifts substantially)
scenarios-discover:
    {{py}} scenarios.py --discover

# Walk-forward optimization over StrategyConfig knobs
optimize *ARGS:
    {{py}} optimize.py {{ARGS}}

# Sweep a single StrategyConfig knob and report per-ticker P/L, DD, suite, score.
# Examples:
#   just sweep max_loss_mult --values 1.2,1.5,1.8,2.5
#   just sweep delta_breach --values 0.30,0.40,0.50,0.60 --tickers TSLA
#   just sweep long_dte --values 3,7,14 --vs long_target_delta --vs-values 0.15,0.20,0.30
sweep *ARGS:
    {{py}} sweep.py {{ARGS}}

# Run feature-importance analysis and emit candidate adaptive-rule sketches.
# This is the v1.12 automated rule-proposer for the critic loop.
# Examples:
#   just analyze
#   just analyze --tickers TSLL --top 5
#   just analyze --features iv_rank,ret_14d,ema_stack
analyze *ARGS:
    {{py}} analyze.py {{ARGS}}

# v1.14 archetype bake-off — head-to-head comparison of strategy archetypes
# (HoldToDecay / QuickHarvest / PremiumSlow / ReversalScalp) across 5y + suite + OOS.
bakeoff *ARGS:
    {{py}} archetype_bakeoff.py {{ARGS}}

# Active-position tracker: status of open positions (`positions.yaml`)
# `just positions`             — status of all open positions
# `just positions add TSLA put 385 2026-05-08 2026-05-15 4.40`
# `just positions close TSLA 385`
# `just positions example`     — write a sample positions.yaml
positions *ARGS:
    {{py}} manage_positions.py {{ARGS}}

# Simulator: focused scenario generation (Phase 1)
model-generate *ARGS:
    {{py}} simulator/generate_scenarios.py --per-regime 100 --focus high_gamma_marginal,v_recovery,post_earnings_weak {{ARGS}}

# Simulator: label + enrich training set (pass --scenarios PATH --low-regret-filter 25)
model-train-focus *ARGS:
    {{py}} simulator/build_training_set.py {{ARGS}}

# Simulator: merge real backtest trades into training parquet
model-join-real SYNTHETIC OUTPUT:
    {{py}} simulator/join_real_trades.py --synthetic {{SYNTHETIC}} --output {{OUTPUT}}

# Simulator: train policy + should-trade models (pass --input PATH)
model-train *ARGS:
    {{py}} simulator/train_should_trade_model.py {{ARGS}}
    {{py}} simulator/train_best_policy_model.py {{ARGS}}

# Simulator: validate model policy vs rules on real history
model-validate *ARGS:
    {{py}} simulator/validate_model_policy.py {{ARGS}}

# Simulator: model policy on canonical 12-regime windows
model-scenarios *ARGS:
    {{py}} simulator/validate_model_policy.py --canonical {{ARGS}}

# Simulator: feature parity smoke (Phase 0)
model-verify:
    {{py}} simulator/verify_model_features.py

# Lab one-command smoke: model feature parity + production 12-regime suite
# See docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md (cold-start free strategy research)
lab-smoke:
    {{py}} simulator/verify_model_features.py
    {{py}} run_scenarios.py

# PMCC / LEAPS diagonal snapshot — live chain grid (delta-based strike matching)
# Examples:
#   just pmcc-snapshot --preset balanced
#   just pmcc-snapshot --preset bullish --target-spot 550
#   just pmcc-snapshot --preset income --top 15
#   just pmcc-snapshot --refresh          # force live fetch
#   (default: 30m TTL when market open; after hours keeps last session cache)
pmcc-snapshot *ARGS:
    {{py}} pmcc_analyze.py {{ARGS}}

# Explain pair ranking — why 420/430? compare vs path-sim
#   just pmcc-rank --explain 420/430
#   just pmcc-rank --preset managed --compare
pmcc-rank *ARGS:
    {{py}} pmcc_pair_rank.py {{ARGS}}

# Compare default vs wide DTE grids; audit available chain expirations
pmcc-sweep-dte *ARGS:
    {{py}} pmcc_sweep_dte.py {{ARGS}}

# Scenario walkthrough (rip/drop) on best pair from preset
#   just pmcc-scenarios --preset bullish --target-spot 550
#   just pmcc-scenarios --preset balanced --leaps-strike 420 --short-strike 510
pmcc-scenarios *ARGS:
    {{py}} pmcc_scenarios.py {{ARGS}}

# Monthly playthrough to LEAPS expiry on bear→bull paths (best pair + roll rules)
#   just pmcc-playthrough --preset balanced
#   just pmcc-playthrough --preset bullish --path moonshot
pmcc-playthrough *ARGS:
    {{py}} pmcc_playthrough.py {{ARGS}}

# Optimized rules + daily spot/premium playbook (reentry + roll targets)
#   just pmcc-playbook --preset balanced
#   just pmcc-playbook --out .cache/pmcc_playbook.md
pmcc-playbook *ARGS:
    {{py}} pmcc_playbook.py {{ARGS}}

# Daily playthrough (1d steps) — gap-rip paths + pair comparison
#   just pmcc-daily --preset balanced
#   just pmcc-daily --compare --leaps-strike 420 --short-strike 430
#   just pmcc-daily --path single_day_rip_10
pmcc-daily *ARGS:
    {{py}} pmcc_daily_playthrough.py {{ARGS}}

# Discover TSLA historical patterns → PMCC path suggestions
pmcc-discover *ARGS:
    {{py}} pmcc_discover_paths.py {{ARGS}}

# Systematic rule tuner (whipsaw-weighted daily sim grid search)
#   just pmcc-tune --preset balanced --leaps-strike 420 --short-strike 430 --save
pmcc-tune *ARGS:
    {{py}} pmcc_tune.py {{ARGS}}

# Pair scan — path sim on strike combos (fast) or full grid (slow)
#   just pmcc-scan --refresh                    # sim-best DTE per strike pair (~8 min)
#   just pmcc-scan --mode full --refresh        # ~2950 grid cells (~20-40 min)
#   just pmcc-scan --ladder-short 490
pmcc-scan *ARGS:
    {{py}} pmcc_pair_scan.py {{ARGS}}

# Calibrate static scores against full-grid path sim (run full scan first)
#   just pmcc-calibrate --refresh               # full scan + report
#   just pmcc-calibrate --dte-table             # static vs sim DTE picks
pmcc-calibrate *ARGS:
    {{py}} pmcc_calibrate.py {{ARGS}}

# Scenario playbook — walk through each path with real premiums and trade logs
#   just pmcc-playbook-gen --leaps-strike 410 --short-strike 460
#   just pmcc-playbook-gen --leaps-strike 380 --short-strike 450 --out .cache/pmcc_playbook_380_450.md
pmcc-playbook-gen *ARGS:
    {{py}} pmcc_playbook_gen.py {{ARGS}}

# Live position manager — daily status + action recommendations
#   just pmcc-manage                    # check all positions
#   just pmcc-manage --spot 420         # override spot
#   just pmcc-manage --what-if 500      # what-if table at $500
#   just pmcc-manage --triggers         # full trigger playbook
pmcc-manage *ARGS:
    {{py}} pmcc_manage.py {{ARGS}}

# Quiet PMCC monitor for cron/alerts — silent unless action is needed
pmcc-monitor *ARGS:
    {{py}} pmcc_manage.py --monitor --quiet-ok {{ARGS}}

# Income Engine desk brief — raw gather only (PMCC + short-premium + data-quality banner)
# Synthesis/stance is agent or human work per docs/DESK_BRIEF.md
#   just desk-brief
#   just desk-brief --full
#   just desk-brief --no-live
desk-brief *ARGS:
    {{py}} scripts/desk_brief.py {{ARGS}}

# Compare 300 TSLA shares vs current PMCC stack under rip targets
pmcc-compare-stock *ARGS:
    {{py}} pmcc_stock_vs_pmcc.py {{ARGS}}

# Clean generated plots
clean:
    rm -f *.png
    echo "Cleaned generated files"

# --- Income platform M0–M2 (paper/local; no live RH) ---
# Seed + list hypotheses: just platform-hypotheses list
platform-hypotheses *ARGS:
    {{py}} -m trader_platform.hypothesis_cli {{ARGS}}

# Scan / propose / risk / paper execute one tick (default paper)
platform-paper-tick *ARGS:
    {{py}} -m trader_platform.autonomy_loop --mode paper --once {{ARGS}}

# Propose + risk only (no ledger mutate)
platform-scan *ARGS:
    {{py}} -m trader_platform.autonomy_loop --mode shadow --once {{ARGS}}

# Smoke: registry + risk + paper place/replace/cancel + Stage2 bridge
platform-smoke:
    {{py}} trader_platform/smoke_test.py

# Stage2: RH read-only snapshot readiness + capital plan recommendations
platform-rh-readiness *ARGS:
    {{py}} -m trader_platform.rh_readonly_cli {{ARGS}}

# Stage2: dry-review (RH review_* payloads only; no place)
platform-dry-review *ARGS:
    {{py}} -m trader_platform.autonomy_loop --mode paper --dry-review --once {{ARGS}}

# M2 research loop: regime→strategy→symbol→premium scout (intents only; paper-first)
platform-scout *ARGS:
    {{py}} -m trader_platform.premium_scout {{ARGS}}

# --- Multi-symbol research scout (universe ranking; paper-only; NOT live allowlist) ---
# Rank full research universe by vol / premium / alpha + capital-by-price
# Doctrine: Agentic pilot sleeve is $3000 (pass --sleeve-usd 3000 for capital-fit tops).
#   just research-tick
#   just research-tick -- --top 15 --json
#   just research-tick -- --sleeve-usd 3000 --write-report
#   just research-tick -- --promote --promote-top 5 --sleeve-usd 3000
# Paper recurring wrapper (dated report; optional promote). See docs/RESEARCH_CRON.md
#   just research-tick-paper
#   just research-tick-paper -- --sleeve-usd 3000 --promote
research-tick *ARGS:
    {{py}} -m trader_platform.research tick {{ARGS}}

# Paper-only recurring research tick: write dated report under .cache/platform/research_reports/
# Does NOT place orders / does NOT arm agentic / does NOT start a trading cron.
research-tick-paper *ARGS:
    {{py}} -m trader_platform.research tick --write-report --notes research_tick_paper {{ARGS}}

# Wire last-run top-N → hypothesis *candidates* (never live). Optional engine backtest hooks.
#   just research-promote-top
#   just research-promote-top -- --top 5 --sleeve-usd 3000
#   just research-promote-top -- --run-backtests --dry-run
research-promote-top *ARGS:
    {{py}} -m trader_platform.research promote-top {{ARGS}}

# Print last (or --run-id N) research tables (incl. capital columns)
#   just research-report
#   just research-report -- --run-id 1 --top 12
research-report *ARGS:
    {{py}} -m trader_platform.research report {{ARGS}}

# Show configured multi-symbol research universe
research-universe *ARGS:
    {{py}} -m trader_platform.research universe {{ARGS}}

# --- Learn tick (self-improve from outcomes; never live) — see docs/TRADER_LOOPS.md ---
#   just learn-tick
#   just learn-tick -- --apply
#   just learn-tick -- --apply --append-scoreboard
#   just learn-tick -- --json
learn-tick *ARGS:
    {{py}} -m trader_platform.learn_tick --once {{ARGS}}

# --- Evolve tick (FREE strategy DNA search + sim; never live; no strategies.py edits) ---
#   just evolve-tick
#   just evolve-tick -- --apply --top-symbols 8 --mutants 2
#   just evolve-tick -- --apply --structures short_put_credit wheel_assignment put_credit_spread
#   just evolve-tick -- --json
evolve-tick *ARGS:
    {{py}} -m trader_platform.evolve_tick --once {{ARGS}}

# Bootstrap burst: research → evolve → learn → paper scout (paper only)
bootstrap-ticks:
    {{py}} -m trader_platform.research tick --write-report --notes bootstrap --sleeve-usd 3000 --promote --promote-top 5
    {{py}} -m trader_platform.evolve_tick --once --apply --top-symbols 8 --mutants 2 --max-population 48 --max-create 8 --sleeve-usd 3000
    {{py}} -m trader_platform.learn_tick --once --apply
    {{py}} -m trader_platform.autonomy_loop --mode paper --once

# PCS regime stress (yearly / 6m / TSLL canon) for registered defined-risk hyps
#   just pcs-regime-stress
#   just pcs-regime-stress -- --write-hyps
pcs-regime-stress *ARGS:
    {{py}} scripts/pcs_regime_stress.py {{ARGS}}

# PCS B4 cost/slip sensitivity (1-lot) for registered defined-risk hyps
#   just pcs-cost-stress
#   just pcs-cost-stress -- --write-hyps --slips 0,0.02,0.05,0.10
pcs-cost-stress *ARGS:
    {{py}} scripts/pcs_cost_stress.py {{ARGS}}

# Human front door for agent wakes (not program ticks)
#   just trader-wakes
#   just trader-wakes --all
trader-wakes *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    dir="reports/trader-wakes"
    if [[ ! -d "$dir" ]]; then
      echo "No wake reports yet under $dir"
      exit 0
    fi
    if [[ "${1:-}" == "--all" ]]; then
      ls -1t "$dir"/*.md 2>/dev/null | grep -v README.md | head -50 || true
      exit 0
    fi
    echo "=== reports/trader-wakes/INDEX.md (head) ==="
    if [[ -f "$dir/INDEX.md" ]]; then head -40 "$dir/INDEX.md"; else echo "(no INDEX yet)"; fi
    echo
    echo "=== reports/trader-wakes/LATEST.md ==="
    if [[ -f "$dir/LATEST.md" ]]; then cat "$dir/LATEST.md"; else echo "(no LATEST yet — run a trader wake)"; fi

# Dual-pass MoA wake: GPT 5.6 Sol executor (writer) → Grok 4.5 challenger (read-only)
#   just trader-wake-moa
#   just trader-wake-moa --goal "stress only TSLL PCS"
#   just trader-wake-moa --executor-only
#   just trader-wake-moa --challenger-only --stamp 2026-07-09T2345
#   just trader-wake-moa --hyps id1,id2,id3
trader-wake-moa *ARGS:
    bash scripts/trader_wake_moa.sh {{ARGS}}

# Dual-model income BUILD lab (GPT 5.6 Sol → Grok 4.5). More discovery time.
#   just trader-build-lab
#   Zero-input is canonical for human, coordinator, and cron callers.
#   Optional --goal/--slot/--structures are debug or recovery overrides only.
trader-build-lab *ARGS:
    bash scripts/trader_build_lab_moa.sh {{ARGS}}

# Autonomous continuum (no Ken prompt): refresh strategy-engine handoff → MoA if NEXT_SURVIVOR else quality residual.
# Never live/shadow/arm/execute-paper. Single-flight via build_lab.lock.
trader-autonomous-tick:
    bash scripts/trader_autonomous_tick.sh

# Quality residual only (research + DR evolve + CSP evolve + shortlist stress + multi + dry paper).
trader-quality-residual:
    bash scripts/trader_quality_residual.sh

# Deterministic RTH residual (scout + autonomy dry-run). No agent import path. Never live/execute-paper.
trader-rth-ops:
    bash scripts/trader_rth_ops.sh

# Self-driving paper campaign (learn + shortlist paper place/manage). Never live/arm.
trader-paper-campaign:
    bash scripts/trader_paper_campaign.sh

# Fail-closed clean/main/origin completion check (BUILD wrapper runs this automatically).
trader-run-gate mode="preflight" *ARGS:
    {{py}} scripts/trader_run_completion_gate.py {{mode}} --repo . {{ARGS}}

# Catalog × hyp × sim coverage scoreboard (income lab)
#   just trader-income-coverage
trader-income-coverage *ARGS:
    {{py}} scripts/trader_income_coverage.py {{ARGS}}

# ── Desk B spine (self-sufficient loop; research/paper only) ──────────────
# Evaluate a frozen StrategySpec (dual-cost train → holdout → living registry)
#   just trader-eval
#   just trader-eval -- --spec configs/strategy_specs/regime_router_income_45d_v1.json
trader-eval *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "{{ARGS}}" ]; then
      {{py}} scripts/evaluate_strategy_spec.py \
        --spec configs/strategy_specs/regime_router_income_v1.json \
        --out .cache/platform/spine/eval_LATEST.json
    else
      {{py}} scripts/evaluate_strategy_spec.py {{ARGS}}
    fi

# Bounded StrategySpec evolve → evaluate → registry
#   just trader-evolve
#   just trader-evolve -- --max-mutants 2 --symbols BAC,KO
trader-evolve *ARGS:
    {{py}} scripts/trader_evolve_specs.py \
      --seed configs/strategy_specs/regime_router_income_v1.json {{ARGS}}

# Living registry status (F2 watchable seats)
trader-living:
    {{py}} scripts/trader_living_status.py

# Easy progress: stats + top holdout passes (plain English)
#   just trader-progress
#   just trader-progress --watch
#   just trader-progress --top 5
#   just trader-progress --full
trader-progress *ARGS:
    {{py}} scripts/trader_progress.py {{ARGS}}

# Patient opportunity watcher (NO_QUALIFIED / NO_SETUP / PAPER_PACKET_READY)
trader-watch *ARGS:
    {{py}} scripts/trader_watcher.py {{ARGS}}

# Desk B loop smoke: living status + watcher
trader-loop-status:
    {{py}} scripts/trader_living_status.py
    {{py}} scripts/trader_watcher.py

# Discovery universe (add/remove/list underlyings)
#   just trader-universe
#   just trader-universe list --status active
#   just trader-universe add NVDA --tags ai_growth,high_vol,liquid
#   just trader-universe demote SOFI --notes "barren"
#   just trader-universe activate RKLB
trader-universe *ARGS:
    {{py}} scripts/trader_universe.py {{ARGS}}

# Promote top F2 living seats → paper_eligible (plumbing path)
#   just trader-promote-paper
#   just trader-promote-paper --top 5
trader-promote-paper *ARGS:
    {{py}} scripts/trader_promote_paper.py {{ARGS}}

# Bootstrap shortlist: collect theses/F2 → dual-cost re-prove → reports/bootstrap/LATEST.json
#   just trader-bootstrap --candidates-only
#   just trader-bootstrap --max-f2 10
trader-bootstrap *ARGS:
    {{py}} scripts/trader_bootstrap.py {{ARGS}}

# Staged market-path stress (after dual-cost F2): quick pack → full suite if pass
#   just trader-path-stress --spec configs/strategy_specs/pcs_bull_neutral_income_45d_v1.json --symbols BAC --quick-only
#   just trader-path-stress --spec path/to/mutant.json --symbols AMZN
trader-path-stress *ARGS:
    {{py}} scripts/trader_path_stress.py {{ARGS}}

# Paper residual loop for starter seats (watch + dry handoff; optional --execute-paper)
#   just trader-paper-loop
#   just trader-paper-loop --plumbing-smoke
trader-paper-loop *ARGS:
    {{py}} scripts/trader_paper_loop.py {{ARGS}}

# Multi-symbol re-prove densify DNA (kill single-name luck)
#   just trader-multi-symbol-reprove
#   just trader-multi-symbol-reprove --symbols BAC,KO,IWM,AMZN
trader-multi-symbol-reprove *ARGS:
    {{py}} scripts/trader_multi_symbol_reprove.py {{ARGS}}

# Paper handoff (dry-run default; plumbing-smoke forces one ledger order)
#   just trader-paper-handoff
#   just trader-paper-handoff --plumbing-smoke
#   just trader-paper-handoff --execute-paper
trader-paper-handoff *ARGS:
    {{py}} scripts/trader_paper_handoff.py {{ARGS}}

# Full Desk B cycle (legacy one-shot): evolve → living → watch → paper handoff
# Prefer `trader-discover` for strategy search and `trader-opportunity` for market wait.
trader-desk-b-loop *ARGS:
    {{py}} scripts/trader_desk_b_loop.py \
      --seed configs/strategy_specs/pcs_iv_rich_noncollapse_21d_v1.json {{ARGS}}

# Tight simulation discovery (PURE PYTHON SIMS — not LLM)
# Mutate StrategySpec → dual-cost train/holdout → living registry
# Parallel process pool: --workers 0 (auto) or e.g. --workers 8
#   just trader-discover --until-f2 --keep-going --workers 8
trader-discover *ARGS:
    {{py}} scripts/trader_discover.py --summary-only {{ARGS}}

# Patient opportunity loop only (watch + paper handoff; no evolve)
#   just trader-opportunity
trader-opportunity *ARGS:
    {{py}} scripts/trader_opportunity_loop.py {{ARGS}}

# Evaluate the IV-rich non-collapse seed
trader-eval-iv-rich *ARGS:
    {{py}} scripts/evaluate_strategy_spec.py \
      --spec configs/strategy_specs/pcs_iv_rich_noncollapse_21d_v1.json \
      --out .cache/platform/spine/pcs_iv_rich_noncollapse_21d_v1_LATEST.json {{ARGS}}

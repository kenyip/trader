# Simulator Engine — Active Build Plan (v0.3)

**Date**: 2026-05-14  
**Current Phase**: PoC 1 — Characterization complete, first generator skeleton starting  
**North Star Reference**: See `simulator/NORTH_STAR.md` for the full long-term vision.

---

## Current Status (What We Have Today)

- `simulator/characterize.py` — Working, produces real target statistics for TSLA and TSLL (gaps, short returns, vol clustering, earnings reactions, regime persistence, recent 4h behavior).
- `simulator/NORTH_STAR.md` — Full vision document (model that derives optimal entry + exit/roll management using dense representative synthetic data).
- First concrete data: TSLL has dramatically fatter gaps (p95 8.37%, 29% of days >3%) and much higher HV30 than TSLA — this is now a hard requirement for the generator.

---

## Guiding Principles (Do Not Drift From These)

1. **Representative, not perfect** — "Good enough" statistical match on prioritized inputs is the bar.
2. **Prioritize most important inputs first** — Gaps, short-horizon returns, volatility dynamics, earnings reactions, 4h move character, regime persistence (in that order for v0.1).
3. **4-hour resolution** from the beginning.
4. **Build small, prove, iterate** — Every piece must deliver measurable value before we expand scope.
5. **Validation firewall** — Synthetic data for training/exploration/stress. Real historical data + existing gauntlet (`just scenarios`, 5y backtest, walk-forward, cost function) for all shipping decisions.
6. **North star always visible** — We are building toward a policy model that can propose full (entry + management) strategies, not just more skip rules.

---

## Phased Roadmap (High Level)

**PoC 1 (Now)**: Simulator foundation + characterization harness
- Generator that produces paths matching the top targets from `characterize.py`.
- Validation loop (`validate_generator.py`) that reports match quality.
- Success gate: Generator is "not off by a lot" on the 4–5 highest-impact statistics, and synthetic data improves a downstream model on real OOS/regime tests.

**PoC 2**: Rich Trade Labeling Engine
- Given any path point + state, evaluate many (side, DTE, delta) entries + multiple exit/roll policies.
- Produce large labeled datasets (real + synthetic) with "best management" outcomes.

**PoC 3**: First Policy Model
- Model that, given live features + peek greeks, recommends full trade plan (entry params + exit/roll overrides).
- Shadow mode + first model-derived policies validated on real gauntlet.

**Later Phases** (after PoC 1–3 prove value):
- Higher-fidelity generator (IV dynamics, skew, more events).
- Expanded action space (trade templates beyond single-leg).
- On-demand generation API + continuous calibration.
- "What-if" exploration studio.
- Full integration into the critic loop (model becomes primary proposer).

See `NORTH_STAR.md` for the detailed architecture diagram and evolution path.

---

## Immediate Next Work (This Session / Next Few Days)

1. Build minimal `market_generator.py` skeleton (regime-aware paths with basic gap + jump + vol clustering behavior). **Done**.
2. Build `validate_generator.py` that:
   - Runs the generator (multiple seeds).
   - Runs `characterize.py`-style analysis on the synthetic output.
   - Reports quantitative match scores + explicit behavioral sanity checks.
   - Acts as the living "test suite" / verification harness for the simulator.
3. Iterate the generator (improve earnings injection, gap tail modeling) until the match is "good enough" on the top 4 priorities.
4. Gate: Only then move to PoC 2 (rich labeling engine).

**Testing & Verification Strategy (added per user request)**

- No heavy pytest unit-test suite (consistent with project philosophy — the real regression gate is `just scenarios`).
- Instead we have **executable verification harnesses**:
  - `characterize.py` — produces the ground-truth target statistics from real data.
  - `validate_generator.py` — the primary "test". It must be run after any generator change. It does:
    - Statistical match on prioritized dimensions (with clear pass/fail + tolerance).
    - Multiple runs / seeds for stability.
    - Explicit behavioral sanity checks (no NaNs, positive volume, gaps exist, large moves appear when earnings injection is active, etc.).
  - These scripts serve as both regression protection and living documentation of expected behavior.
- Any new generator feature must eventually make `validate_generator.py` pass on the key targets before we consider the feature "proven".

We will keep `NORTH_STAR.md` and this `PLAN.md` updated after every meaningful PoC or insight.

---

## Files in `simulator/`

- `NORTH_STAR.md` — Full vision and architecture (do not let this get stale).
- `PLAN.md` — This file. Current active build plan.
- `characterize.py` — The reference target generator. Run anytime to see current real statistics.
- `market_generator.py` — (next) The actual path generator.
- `validate_generator.py` — (next) Comparison harness.

---

## Reminder

Every time we make progress on the simulator, we must also think about how the eventual **policy model** will consume the data and how it will be validated through the existing engine (`strategies.py`, `backtest.py`, `run_scenarios.py`, `validate_rule.py`).

The simulator is a means to the north star, not the end in itself.

Let's keep the momentum while staying disciplined.

## Latest Progress (2026-05-15 session)

**Core North Star advance: Regret vs Oracle supervision + richer labeling**

- `trade_labeler.py` v0.3: Full `regret_vs_oracle` wired into every LabeledExample (oracle computed from 25+ sampled policies + canonicals). Fixed best_policy labeling bug that caused many empty targets. `sample_management_policies` now biased toward ride-to-expiry and ultra-tight gamma corners (n=18 default).
- `build_training_set.py`: Always runs with use_sampling + compute_oracle_regret; prints mean/median/zero-regret % (typical: median $0, ~80% oracle achieved on synthetic paths).
- `feature_utils.py` + `train_best...`: `CANONICAL_MGMT_POLICY_NAMES` is now the single source of truth → consistent 23-feature models, no more 19/23 drift.
- `generate_scenarios.py`: `--focus high_gamma_marginal / v_recovery / post_earnings_weak` now actually biases generation toward the model's known weak regimes.
- Full loop run: small focused set (48 paths) → 7k regret-labeled examples → new `best_policy_model_20260515_0153.txt` (23 features, consistent).
- `pick_entry_model.py` + integration in `strategies.py`: recommendations now flow with the new model; P/L prediction hardened.
- `validate_model_policy.py`: runs cleanly but model still 0-trade on canonical windows (conservative credit/ feature match on short regimes — next hardening target).

We now have quantitative "regret to future-path-optimal management" labels. This is the key to training a policy model that doesn't just imitate good policies but actively minimizes sub-optimality.

Next: Large focused training set (high_gamma_marginal + v_recovery emphasis), low-regret label filtering, live model entry hardening so it actually takes trades on real history, then real gauntlet comparison.

---
## PR 2 Status (Candidate 3 — Hardening + Knobs + Alignment + Post-Veto Skeleton)

**Date**: 2026-05-18 (delivered in isolated worktree)

**Delivered exactly per MODEL_TRAINING_PLAYBOOK.md PR 2 spec**:
- `simulator/pick_entry_model.py`: should_trade_model load (glob + pinned), `predict_should_trade` (neutral + 20-col strict align via new helper), gate-first logic in `recommend`, new kwargs (min_policy_conf, min_edge, use_should_trade_gate, debug, test_permissive), rich per-cand/aggregated diagnostics + clear "return [] reason" prints, old <0.15 rescue guarded behind test_permissive, `get_model_info()`.
- `simulator/feature_utils.py`: `build_should_trade_features(row)` with full documented neutral EntryAction("put",5,0.22,min_credit=0.010)+ManagementPolicy("standard") + rationale.
- `strategies.py`: 5+2 safe `model_*` fields added to `StrategyConfig` + defaults; `pick_entry_model` wrapper now uses `get_peek_features_for_action` (no dupe), forwards `delta_breach_override`, calls recommend with cfg min_*, invokes `_passes_model_veto_rules`, rich debug logs, safe error surfacing.
- `simulator/validate_model_policy.py`: `from backtest import Position`; both adapters now forward 4 overrides incl. delta_breach; richer per-decision logging (debug path).
- `simulator/build_training_set.py`: `--low-regret-filter N` + `--scenarios PATH` support (filter keeps regret<=N | oracle>0; enables the focused recipe).
- New `simulator/verify_model_features.py`: executable smoke asserting 20/23-col parity on the 20260515 models + gate/scoring paths run on real `data.build` row.
- `simulator/PLAN.md`: this PR 2 Status section.

**Verification gates (start + end) — see command outputs in final candidate report**:
- Start (pre any edit): `python simulator/pick_entry_model.py` + `python simulator/validate_model_policy.py` (showed warnings, RuntimeError on no-model, 0.0 on canonical — baseline gaps confirmed).
- End: same two + `python simulator/verify_model_features.py` + manual knob/gate/diag tests + `python -c "from strategies import pick_entry, StrategyConfig; ..."` (main rule path exercised, model path separate).

**Key invariants preserved**:
- `just scenarios`, `pick_entry`, `adapt_entry_params`, `ADAPTIVE_RULES`, `DEFAULT_CONFIG_BY_TICKER` rule logic, `check_exits` ladder: 100% untouched.
- All model_* only affect experimental wrapper + validate adapters.
- Uses existing patterns (glob latest, strict reindex, Position overrides, print diags, build_model_features + neutral).

**Commands that now pass** (post-PR 2):
```
python simulator/verify_model_features.py
python simulator/pick_entry_model.py
python simulator/validate_model_policy.py
python simulator/build_training_set.py --help   # shows --low-regret-filter --scenarios
.venv/bin/python -c "
from strategies import StrategyConfig, get_config, pick_entry_model
cfg = get_config('TSLA', enable_model_entry=False, model_debug=True)
print('knobs:', cfg.model_min_should_trade, cfg.model_min_policy_conf)
"
python -c "
from simulator.pick_entry_model import PickEntryModel
m = PickEntryModel()
print(m.get_model_info())
print('gate:', m.predict_should_trade.__code__.co_varnames)
"
```

PR 2 complete, safe, minimal, reviewable. Ready for PR 3 (hybrid wiring inside pick_entry after adapt).

---

## Phase A/B/C Completion: Signal-Driven Close/Roll Management Advisor (plan 019e7d50-1ec7-77e0-b627-56902d41507d, 2026-05-31)

**Executed per approved plan (effort 4)**: Picked up from Phase A foundation (LabeledExample 10 traj fields + capture in trade_labeler; TRAJECTORY_FEATURES + build_management_decision_features SoT with det regime/NaN in feature_utils; 0 prior review issues). Completed remaining A + full B (model extension) + full C (thin integration) + gauntlet + docs.

**Key additions (minimal, additive, behind enable_*=False, reuse all PR2 patterns):**
- build_training_set.py: imports + SoT enrichment of traj features (prevents drift/dupe).
- verify_model_features.py: extended header + 33-col / det / NaN smoke (passes).
- pick_entry_model.py: recommend_management + _prepare_mgmt + _default_traj + mgmt load/align/get_info (gates, diagnostics, safe neutral; exercised with real demo model on adverse traj).
- strategies.py: StrategyConfig 4 new knobs (enable_model_management=False etc); _build_traj + recommend_management_advisor thin wrapper.
- positions.py: import + compute advice in check_position + render "MODEL MGMT (shadow)" in format (read-only).
- manage_positions.py: 'whatif' subcmd + cmd_whatif (forces enable+debug for demo).

**Exact runnable commands + outputs (abridged; full in /tmp/grok-impl-summary...):**
```
.venv/bin/python simulator/verify_model_features.py   # PASS (33-col, NaN=0, det regime, 20/23 + mgmt)
.venv/bin/python simulator/generate_scenarios.py --focus high_gamma_marginal,post_earnings_weak --per-regime 8 --length 15 --save .cache/focus_mgmt_demo.parquet
.venv/bin/python simulator/build_training_set.py --scenarios .cache/focus_mgmt_demo.parquet --label --low-regret-filter 30 --output .cache/mgmt_focus_demo.parquet
# -> 41886 examples, median regret $0, 77.9% zero-regret, 48 cols (incl 10 traj)
# quick demo mgmt model on subset traj feats -> .cache/models/management_advisor_demo.txt
.venv/bin/python -c 'from simulator.pick_entry_model import PickEntryModel; ... recommend_management(adverse traj) -> close=True conf~0.76 overrides=...'
.venv/bin/python simulator/validate_model_policy.py   # runs (loads mgmt too; 0 trades on canonicals as before)
.venv/bin/python -c 'from positions import check_position; from strategies import get_config; st=check_position({...}, cfg=get_config("TSLA",enable_model_management=True)); print(st["model_management_advice"])'
# -> surfaces MODEL MGMT line in format_all
.venv/bin/python manage_positions.py whatif   # (when positions.yaml has data) demos shadow
just scenarios -- --regime flat   # or run_scenarios (rule path pure; no leakage)
```
All verifs passed with identical language/parity where applicable. `just scenarios` / core check_exits / pick_entry untouched.

**Result on real gauntlet**: Clean null (as expected for first cycle; loop ready). Cost function unchanged on rule path. Synthetic focused labels show high oracle coverage (77.9% zero regret). Distillation target: future ADAPTIVE_EXIT_RULES from SHAP on traj features (e.g. "tighten delta on high adverse + bearish regime").

**Status**: All phases complete. Everything behind safe defaults. Proposer (model) can evolve; validator (scenarios + 5y cost fn) sacred. Per-ticker ready. Docs updated in same pass.

See full Implementation Summary at /tmp/grok-impl-summary-a70f9988.md .

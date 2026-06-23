# North Star Handoff — TSLA/TSLL Model-Driven Strategy System

This document allows you to continue the project in a fresh session.

---

## North Star Vision

Build a system where a **trained model can derive the full optimal strategy** at any decision point. This includes:

- Side (put/call)
- DTE and strike/delta
- Credit floor
- Exit / management policy (profit target, daily capture, max loss, delta breach)
- Roll logic when appropriate

The model learns from **dense, representative simulator-generated data** that includes actual future path outcomes. This gives us much stronger supervision than typical trading ML projects.

All model-derived strategies must still pass the project’s strict real-historical validation gate (`validate_rule.py` + `validate_model_policy.py` + 12-regime suite + cost function).

---

## Current State (as of latest session)

### Files & Components Created/Improved

**Simulator & Data Generation**
- `simulator/market_generator.py` — Regime-aware synthetic path generation
- `simulator/generate_scenarios.py` — Bulk scenario generation with regime, earnings, high-vol, and `--focus` support
- `simulator/trade_labeler.py` (`TradeLabelerV2`) — Evaluates multiple `EntryAction` × multiple `ManagementPolicy` per state. Supports `sample_management_policies()` and `compute_oracle_best_on_path()`
- `simulator/feature_utils.py` — Shared functions for consistent feature + peek greeks computation (`build_model_features`, `get_peek_features_for_action`, `compute_peek_greeks`). Critical for training/inference alignment.

**Model Training & Usage**
- `simulator/build_training_set.py` — Generates large labeled datasets (entry × management policy) with aligned features
- `simulator/train_best_policy_model.py` — Trains classifier to predict `best_policy_for_path`
- `simulator/train_should_trade_model.py` — Binary “should I trade at all?” gate (AUC ~0.78)
- `simulator/pick_entry_model.py` — First working live model-based recommender. Scores candidate (entry + management) combinations and returns ranked `Recommendation` objects.
- Integrated into `strategies.py` as the experimental `pick_entry_model()` function (returns a full `Position` with model-recommended overrides when possible).

**Validation & Testing**
- `simulator/validate_model_policy.py` — Framework to backtest model-driven policies on any historical period or the 12 canonical regimes (the model equivalent of `validate_rule.py`).

**Rule Extraction (Side Track)**
- Multiple model-inspired adaptive rules have been created and tested through real validation (various high-gamma + marginal momentum rules + dynamic credit versions). None have shipped yet.

### Training Data Progress
- Multiple large training sets generated (latest ~39k rows)
- 8+ management policies now evaluated
- Feature alignment between training and live use has been significantly improved via `feature_utils.py`
- Some data hygiene issues (duplicate `mgmt_*` columns) have appeared in certain generated files. The enrichment logic in `build_training_set.py` has been hardened.

### Current Model Signals (Consistent Across Runs)
Top features that repeatedly appear:
- `peek_theta_yield`
- `ret_1d`
- `peek_gamma_dollar`
- `ret_5d`
- `peek_credit`
- Management policy parameters (`profit_target`, etc.)

The model is learning that **gamma risk + short-term momentum + credit quality + theta efficiency** are the dominant drivers.

---

## Current Priorities (What to Work On)

Continue focusing on **model quality through better training data and supervision**, while keeping both tracks moving:

### Track B — Richer Labeling & Better Supervision (Higher Priority)
- Expand use of `sample_management_policies()` and `use_sampling=True`
- Improve `compute_oracle_best_on_path()` and wire proper **Regret vs Oracle** tracking into the training pipeline
- Add stronger `--focus` / targeted scenario generation for the model’s known weak areas (v_recovery, high-gamma + marginal `ret_1d`, post-earnings drift, etc.)
- Further improve simulation fidelity in the labeler (closer to real `check_exits`)

### Track A — Regret vs Oracle Measurement
- Make regret tracking a first-class, automatic part of training set creation
- Use it to quantitatively measure how close our labels are to “good decisions given future path information”

### Live Model Quality
- Continue hardening `pick_entry_model.py` and the integration in `strategies.py` so the model reliably produces trades on real historical data
- Combine the “Should Trade” gate + Best Policy model into a practical live proposer
- Regularly run `validate_model_policy.py` on canonical regimes + 5y backtests

### Keep the Real Validation Gate Sacred
- Any new rule or model-derived policy must still go through real historical validation before being considered shippable.

---

## Useful Commands

```bash
# Generate diverse/targeted scenarios
.venv/bin/python simulator/generate_scenarios.py --per-regime 100 --focus high_gamma_marginal --high-vol 80

# Build a rich training set (use sampling)
.venv/bin/python simulator/build_training_set.py --paths 400 --length 20

# Retrain the Best Policy model
.venv/bin/python simulator/train_best_policy_model.py

# Test the live model
.venv/bin/python simulator/pick_entry_model.py

# Run model policy validation on canonical regimes
.venv/bin/python simulator/validate_model_policy.py
```

---

## Instructions for This Session

- Continue in the same pragmatic, fast-moving style.
- Prioritize **improving the quality and diversity of the training data** (richer labeling + targeted scenarios) and **feature alignment**.
- Keep both the “current model improvement” track and the “stronger supervision / Regret vs Oracle” track moving in parallel.
- Always respect the real historical validation requirement.
- When making changes, be ready to run the full loop (generate → label → train → validate on history).
- Periodically give clear status updates on progress toward the north star.
- Update relevant files and this handoff document as major progress is made.

---

**Start by reviewing the current state of these key files:**

- `simulator/feature_utils.py`
- `simulator/trade_labeler.py`
- `simulator/build_training_set.py`
- `simulator/pick_entry_model.py`
- `simulator/validate_model_policy.py`
- `simulator/generate_scenarios.py`

Then propose and begin the next concrete improvements. The highest-leverage areas right now are richer policy sampling + proper regret tracking + targeted hard-case scenario generation.

Continue the work.

---

## Session Progress (2026-05-15)

**Major advances on Track B (Richer Labeling & Better Supervision) and Track A (Regret vs Oracle):**

### 1. Regret vs Oracle now first-class in the labeling pipeline
- `trade_labeler.py`: 
  - `LabeledExample` extended with `oracle_best_pnl`, `oracle_best_policy`, `regret_vs_oracle`.
  - `compute_oracle_best_on_path` improved (denser 25+ samples + DEFAULT canonicals, deduped).
  - `label_path` refactored: oracle computed once per (entry, action), regret assigned to every example, **fixed the `best_policy_for_path` assignment bug** (was slicing incorrectly when some policies invalid → ~37% empty labels in prior sets).
- `build_training_set.py`: `use_sampling=18`, `compute_oracle_regret=True` by default. Now prints regret stats on every build.
  - Example on 48-path run: **mean regret $16.6 | median $0.0 | 79.5% zero-regret (one of our policies achieved oracle best)**. Strong coverage.
- Training sets now carry the 3 new supervision columns (38 cols total).
- `train_best_policy_model.py`: Reports regret quality metrics, robust mgmt one-hot handling, optional low-regret subset training for cleaner labels.

### 2. Richer + more diverse policy sampling
- `sample_management_policies`: n default 18, biased sampling toward "ride-to-expiry" (high PT + loose ML) and "ultra-tight gamma" corners. Better oracle coverage on hard management regimes.

### 3. Feature alignment hardened (eliminates 19-vs-23 drift)
- New `CANONICAL_MGMT_POLICY_NAMES` constant in `trade_labeler.py` (single source of truth for the 8 fixed policies).
- `feature_utils.py` now imports and uses it for one-hots + expected_order. Future trainings will always produce consistent 23-feature models.
- `train_best_policy_model.py` fixed to always pick up pre-computed `mgmt_*` columns from enrichment (no more silent missing one-hots).

### 4. Targeted hard-case scenario generation (initial)
- `generate_scenarios.py --focus`: Now has real (if basic) biasing for `high_gamma_marginal`, `v_recovery`, `post_earnings_weak` — generates flat + earnings-heavy paths for these known model weaknesses.

### 5. Full loop executed + new model
- Generated → labeled with oracle regret → enriched (feature_utils alignment) → trained `best_policy_model_20260515_0153.txt` (23 consistent features).
- `pick_entry_model.py` demo now recommends (e.g. very_aggressive / hold_longer) with far fewer log spam (P/L model hardened).
- `validate_model_policy.py` runs end-to-end (still 0 trades on canonical windows — model too conservative on short regimes / credit filters; live model quality track remains open).

### Other
- P/L regressor prediction path in `PickEntryModel` now gracefully handles old 19-feature models (no more repeated fatal logs).
- All changes preserve the real-historical validation firewall.

**Impact**: We now have quantitative "how far from optimal was this decision?" labels on every synthetic path. This is the highest-leverage supervision improvement for training a model that truly minimizes regret to the oracle (future-path best).

**Next concrete steps (highest leverage)**:
1. Large-scale focused generation: `.venv/bin/python simulator/generate_scenarios.py --focus high_gamma_marginal --focus v_recovery --per-regime 120` then build with `--paths 500`.
2. Retrain best-policy (and should-trade) on the large + low-regret-filtered set.
3. Harden live model entry (relax min credit slightly in adapters, ensure peek greeks + full feature vector always match on historical rows, add "should trade" gate before recommending).
4. Run `validate_model_policy.py` + a 5y backtest and compare per-regime P/L vs current rule baseline. Only then consider distilling a model-inspired adaptive rule.
5. Update `simulator/NORTH_STAR.md` and `STRATEGY.md` once a model policy shows non-zero positive contribution on the gauntlet.

This session moved the needle from "we have a model" to "we have a model trained with explicit regret-to-oracle supervision and reproducible feature alignment."

**2026-06-05 update (3-session closed-loop push)**: Phase 1 complete — 1,580 focused paths → **329,472** labeled rows (79.3% zero-regret, median regret $0) + **250** real trade rows merged (`.cache/training_set_phase1_merged_20260605.parquet`). Retrained `should_trade_model_20260605_0311.txt` + `best_policy_model_20260605_0312.txt`. `ride_high_credit_mgmt` shipped on TSLL (TRIPLE-WIN). `join_real_trades.py`, midtrade labeling, `just model-*` recipes, dashboard model pane. TSLA 2y model: 22 trades (rules: 6); TSLL model over-trades vs rules — gates stay strict. `enable_model_entry` still off.

**2026-05-31 update (plan 019e7d50 completion)**: Closed the loop for the north-star "close/roll conditions using current + previous signals". Phase A: 10 traj/decision-state fields in LabeledExample + SoT builder (det + robust). Phase B: recommend_management in PickEntryModel (33-col, PR2 gates/diag, traj inference). Phase C: StrategyConfig enable_model_management (False) + advisor wired to positions.py check + manage whatif (shadow only). Focused weak-regime + low-regret labeling recipe executed (41k ex, 77.9% zero-regret). Full gauntlet + surface tests passed (clean null on cost; infra ready). All docs + simulator/PLAN.md updated with cmds. Distillation path to ADAPTIVE_EXIT_RULES open. `just scenarios` sacred. Next: larger focused runs + SHAP for rule sketches from traj signals.

Continue the work.
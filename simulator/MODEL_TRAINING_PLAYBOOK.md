# Design: Resolution of Open Questions + Model Training, Evaluation & Promotion Playbook for the Simulator-Trained Options Policy Model

**Design ID**: 626b378c  
**Author**: Grok (systems architect, grounded in exhaustive codebase exploration)  
**Date**: 2026-05-18  
**Status**: Draft — decisions for implementation (PR 2–6)  
**Related**: simulator/OPTIONS_MODEL_DESIGN.md (parent activation design, PR 1 just completed), simulator/NORTH_STAR.md, simulator/PLAN.md, GOAL.md, CLAUDE.md, STRATEGY.md, validate_rule.py, strategies.py (pick_entry + adapt_entry_params + ADAPTIVE_RULES + check_exits), simulator/pick_entry_model.py, simulator/validate_model_policy.py, simulator/feature_utils.py, simulator/trade_labeler.py (EntryAction, ManagementPolicy, TradeLabelerV2 + regret_vs_oracle), simulator/build_training_set.py, simulator/generate_scenarios.py, simulator/train_*.py, scenarios.py (CANONICAL_SCENARIOS + REGIMES + 21-day windows), backtest.py (Position overrides)

---

## Overview

This design resolves the four open questions left explicit in `simulator/OPTIONS_MODEL_DESIGN.md` (the activation design). It delivers a concrete, actionable **Model Training, Evaluation & Promotion Playbook** that removes all ambiguity for the remaining implementation (PR 2 will deliver *both* the PR 1 stabilisation items identified by the best-of-n Candidate 1 *and* the hardening/knobs/feature_utils work; PR 3: hybrid contract inside `pick_entry`; PR 4–6: gauntlet parity, surfacing, focused retrain + first real comparison). The baseline is the live pre-merge PoC tree (see Current State section for exact verification).

The model remains a **proposer** only. The immutable deterministic validation firewall (real 5y + 12-regime `just scenarios` + walk-forward OOS + cost function `total_pnl_per_contract − dd_weight×max_dd_per_contract` with heavy tail bias, catastrophe gate at −$500/contract) is the sole validator. Synthetic data (via `market_generator.py` + `TradeLabelerV2` with `regret_vs_oracle` + `sample_management_policies`) is used exclusively for densification and labeling during training; every decision that affects shipped behavior must still win (or hold with zero regression) on the real-data gauntlet. "Proposer can change; validator cannot." No black-box artifacts ship. Per-ticker specialization (TSLA vs TSLL) is first-class. Distillation to explicit `ADAPTIVE_RULES` remains the preferred promotion path for auditability.

The four decisions below, the hybrid decision flow, the exact training recipe (focused weak-regime generation + low-regret filtering + neutral-action gate features), success criteria, promotion ladder, canonical-window transition handling, and updated PR plan (reflecting the now-fixed contract) together form the bridge from the current pre-PR 2 PoC state (diagnostics and should-trade gate exist only as design targets) to "we can run meaningful, reproducible model training cycles that improve the cost function under the real firewall."

---

## Background & Motivation

### Current State (pre-PR 2 baseline — PR 1 stabilisation targets identified but not yet landed in the inspected tree)

**Verification performed (2026-05-18)**: `list_dir`, repeated `read_file` at multiple offsets (including pick_entry_model.py:100-200, strategies.py:143-235 and 703-787, validate_model_policy.py:25-149), `grep` for `should_trade|predict_should_trade|model_min_|delta_breach_override` (zero matches in the three files), and direct `.venv/bin/python` execution of `PickEntryModel().recommend(latest_row)` + `_make_model_entry_fn` on the real 20260515 models + `data.build` rows confirmed the gaps below. The tree is the pre-merge PoC state; the four files from best-of-n Candidate 1 (the reference implementation of the PR 1 stabilisation items) have not yet been applied to `main`.

- **What exists today (pre any PR 1/PR 2 changes)**:
  - `simulator/pick_entry_model.py`: Loads only `best_policy_model_20260515_0153.txt` (23 features via `feature_utils` + strict alignment) and optional older P/L; `recommend(row, candidates=None, top_k=3)` (no `min_*`, no `use_should_trade_gate`, no `predict_should_trade`) still contains the exact `<0.15` boost + always-returns fallback (lines 193-197). Only `_load_models` prints exist. No should-trade model is loaded or used as a gate.
  - `strategies.py`: `_PICK_ENTRY_MODEL = PickEntryModel()` + `pick_entry_model()` wrapper (still performs manual `pricing.strike_from_delta` + peek duplication); constructs `Position` with only the three overrides (`daily_capture_mult`, `max_loss_mult_override`, `profit_target_override` — **no** `delta_breach_override` at lines 225-228). The entire block is behind the "MODEL-DRIVEN ENTRY — Work in Progress" comment and is **never called** from main `pick_entry:703`.
  - `simulator/validate_model_policy.py`: Two adapters in `_make_model_entry_fn`; `backtest_model_policy` + `run_on_canonical_scenarios` exist and run, but the direct path uses bare `Position(...)` (no `from backtest import Position` import in the module — will raise NameError), exceptions are swallowed (returns None → 0 trades), and neither adapter forwards `policy.delta_breach`. No `--full-gauntlet --compare-baseline` parity with `validate_rule.py:_verdict`, no rich per-candidate/return-[]-reason logging.
- **Training loop is closed and has produced real artifacts** (this part is accurate and unchanged):
  - `simulator/trade_labeler.py:TradeLabelerV2` + `regret_vs_oracle` + `sample_management_policies` (18+ policies) + `compute_oracle_best_on_path`.
  - `simulator/feature_utils.py`: `build_model_features` + `get_peek_features_for_action` (single source for the 23-col best-policy vectors).
  - `simulator/build_training_set.py` + `generate_scenarios.py --focus` + the three `train_*.py` scripts.
  - Latest artifacts: `should_trade_model_20260515_0037.txt` (20 features) and `best_policy_model_20260515_0153.txt` (23 features).
- **Shipping path 100% rule-based and untouched** (accurate): `pick_entry` → `adapt_entry_params` (first pass of `ADAPTIVE_RULES`) → `Position` with the three overrides already honored by `check_exits:851` (delta_breach_override field exists on Position and is read in check_exits, but never populated from any model path today). The 5 v1.13 rules live in `DEFAULT_CONFIG_BY_TICKER`. `just scenarios` on the frozen 21-day `CANONICAL_SCENARIOS` is the gate.
- **Root causes of "0 trades on canonical" (diagnosed)**: distribution shift (short 21-day slices vs. 25–30d training paths), **no should-trade gate wired at all**, conservative scoring + credit floor + no `min_*` knobs, peek/alignment drift (manual pricing in wrapper), missing delta_breach forwarding, permissive rescues that masked stand-aside.
- **Proven distillation precedent**: Early policy-model SHAP signals directly produced the two gamma/marginal adaptive rules that were validated through `validate_rule.py` + `just scenarios` and contributed to the 91% DD reduction arc.

**What PR 2 must deliver (the full stabilisation + hardening delta)**: everything listed in the PR 2 bullet list below, starting from the live pre-merge tree. The "rich diagnostics", "should-trade first gate", `min_*` knobs, feature-parity smoke, and delta_breach forwarding on both validator paths are **not yet present**; they are work items for PR 2 (which will also implement the items originally scoped to the best-of-n PR 1 Candidate 1).

### Why Resolve the Open Questions Now

PR 2 and especially PR 3 are architecturally sensitive. The shape of the hybrid contract (`pick_entry` after `adapt_entry_params`) determines:
- What the training objective actually optimizes (full `(action, policy)` pairs vs. policy-only).
- Whether the first real model gauntlet can be run honestly against the immutable gate.
- How much safety net (post-veto) we keep while the model learns the short-window distribution.
- The promotion ladder (distill vs. direct model mode).

Without clear decisions grounded in GOAL.md ("proposer can change; validator cannot", "no black-box rules for anything that ships", cost-function tail priority, real-data firewall), we risk building the wrong abstraction or locking the training target into something that cannot beat the v1.13 baseline on the real gauntlet. This design phase is the critical bridge.

---

## Goals & Non-Goals

### Goals (priority order)

1. **Clear, documented decisions on all four open questions** with trade-off analysis and explicit rationale tied to north star + invariants (GOAL.md, NORTH_STAR.md, CLAUDE.md, "just scenarios" gate, per-ticker, distillation culture).
2. **Actionable Model Training, Evaluation & Promotion Playbook** concrete enough that an engineer can execute the next focused training cycle, gauntlet comparison, and promotion decision without invention.
3. **Fixed hybrid contract for PR 3** (what `recommend()` may return, how overrides flow into `Position`, exact interaction of should-trade gate + `min_*` knobs + optional veto layer + regime/adapt logic).
4. **Updated, decision-reflected PR plan (PR 2–6)** that is incremental, independently reviewable, and preserves the "small proven parts" + "just scenarios before any shipping-path change" discipline.
5. **Mermaid diagrams** for hybrid flow, full training→promotion loop, and canonical-window transition handling.
6. **Risk register** with severity + mitigations focused on distribution shift, over-conservatism, and firewall bypass temptation.
7. **Key Decisions** (7–10 numbered) + remaining open questions.

### Non-Goals

- Do not change the cost function, `scenarios.CANONICAL_SCENARIOS` (the 12 frozen 21-day windows), `Backtester`, `check_exits` ladder, or `validate_rule.py` verdict language.
- Do not replace the rule engine wholesale; hybrid/opt-in first, distillation preferred.
- Do not introduce new model formats or real-chain / intraday yet.
- Do not automate distillation in the first two training cycles.
- Do not allow the model to affect `just scenarios` output during the learning phase (special-case handling documented).
- Performance target unchanged: <50 ms for 5×8 inferences per bar.

---

## Proposed Design

### 1. Decisions on the Four Open Questions (with Trade-off Analysis)

**Question 1: Full-plan override vs. management-only?**

**Recommended Decision**: **Full-plan override allowed** (model's chosen `EntryAction` (side/DTE/delta) + `ManagementPolicy` (with its four values) can replace the regime + `adapt_entry_params` base when the recommendation passes the should-trade gate + `min_policy_conf` + `min_edge` thresholds).

**Runner-up**: Management-policy + overrides only (keep rule-derived side/DTE/delta; model only supplies the four management knobs).

**Rationale** (tied to invariants):
- Directly serves the NORTH_STAR.md vision ("model derives optimal side/DTE/strike/exit/roll") and GOAL.md M6 stretch ("trained model proposer").
- The labeler already evaluates full `(EntryAction × ManagementPolicy)` pairs and emits `best_policy_for_path` + regret; training the multi-class model on the joint space is already done. Ignoring the action part at inference would waste signal and make the training target mis-aligned with what we actually deploy.
- The regime logic + 5 shipped hard-skip rules remain a strong prior (they run first in `adapt_entry_params`). The model only wins when its confidence/edge is high enough to overcome the base; the post-veto layer (Q2) and should-trade gate (already wired in PR 1) provide additional guardrails.
- Per-ticker first-class: `DEFAULT_CONFIG_BY_TICKER` + new `model_*` knobs let us tune aggressiveness differently for TSLA vs TSLL.
- Risk (tail on short windows) is mitigated by the canonical special case (Q3) and the real-data firewall — a bad full-plan proposal simply fails the gauntlet and is never promoted.
- Management-only would have been a safer "small step" but would have required a second training objective later; full-plan now is the higher-leverage choice that matches the existing labeler contract.

**Explicit contract (for PR 3)**: Inside `pick_entry` (after the `resolved = adapt_entry_params(...)` skip check), if `cfg.enable_model_entry` and model available and should-trade passes: call `recommend(..., min_policy_conf=cfg.model_min_policy_conf, min_edge=cfg.model_min_edge)`. If a high-quality rec is returned, **replace** side/dte/target_delta with the model's `action` values, price with the model's action, and construct `Position(..., daily_capture_mult=policy.daily_capture_mult, max_loss_mult_override=policy.max_loss_mult, profit_target_override=policy.profit_target, delta_breach_override=policy.delta_breach)`. The model's action is treated exactly like a rule-supplied override in the existing `resolved` dict path.

**Question 2: Post-model rule veto layer?**

**Recommended Decision**: **Yes — lightweight post-model veto layer for the proven hard-skip rules** (the five currently shipped in `DEFAULT_CONFIG_BY_TICKER`: `tsla_skip_mild_intraday_up`, `tsll_skip_marginal_up`, `tsll_skip_tuesday`, `tsll_skip_post_earnings_drift`, `tsll_skip_downtrend_high_iv`, plus the two model-inspired gamma ones that have already survived `validate_rule.py`).

**Runner-up**: No post-veto; rely solely on should-trade gate + `min_*` + credit floor.

**Rationale**:
- Matches the core philosophy exactly: "proposer (model) can change; validator (the explicit, already-shipped hard skips) cannot."
- The hard skips are state-based (ret_14d buckets, day-of-week, days-since-earnings, IV+trend conjunctions) and cheap to evaluate; they do not depend on the proposed action. Running a second pass of the "skip" subset after the model proposes (but before constructing the final Position) is a few lines and zero risk.
- Gives us the best of both worlds: model can still propose a full plan (including different side/DTE on marginal states the rules would have skipped), but the most proven "never enter here" signals remain absolute.
- Over-conservatism risk is low because the veto is only the hard skips; softer dynamic rules can still be influenced by the model.
- Cost: negligible. Safety: high. Auditability: perfect (the veto rules are the same explicit functions already in `ADAPTIVE_RULES`).

**Implementation sketch (PR 3)**: After a model rec is accepted by the confidence/edge gates, build a transient `current = {'side': model_action.side, ...}` and run only the subset of rules whose name starts with `skip_` (or a new `MODEL_VETO_RULES` tuple) against it. If any returns `{'skip': True}`, fall back to rule path with reason "post-model veto: <rule_name>".

**Question 3: Canonical-window special case during transition?**

**Recommended Decision**: **Yes — temporarily force the pure rule path for the `just scenarios` regression gate** (documented special case, controlled by a `force_rule_on_canonical=True` default during the learning phase or by keeping the `just scenarios` driver 100% on `pick_entry` while model validation uses a separate path).

**Runner-up**: Require the model itself to produce non-zero sensible activity on the exact 21-day canonical windows before any promotion discussion.

**Rationale** (highest-stakes decision):
- The 12 canonical 21-day windows (`scenarios.py:CANONICAL_SCENARIOS`, `REGIMES`, `WINDOW_DAYS=21`) are the **immutable behavioural regression gate** (CLAUDE.md: "REQUIRED before/after every strategy tweak"). They were chosen as representative historical stress periods; they are not the data the model was trained on (generator paths are typically 25–30 days with focused densification).
- Distribution shift is real and diagnosed: short windows have different ret_1/5/14d, IV persistence, earnings proximity statistics than the longer paths used for `regret_vs_oracle` labeling. A model that is excellent on 5y history and on focused 30-day synthetic can still legitimately return [] or low-confidence on the exact 21-day slices.
- Requiring non-zero on canonical before promotion would make the gate a false-negative filter: good models would be rejected because of window length, not because they are bad. This would stall the entire program.
- Forcing rule path on canonical for the official `just scenarios` command (while the model gauntlet in `validate_model_policy.py` reports separately on full 5y + OOS + "model on canonical (expected 0 or low during transition)") preserves the honesty of the regression gate without cheating. The special case is explicitly documented in STRATEGY.md / PLAN.md and lifted only after a model variant has been shown (via separate short-window focused labeling) to be reliable on those exact windows.
- This is the only decision that lets us keep "just scenarios" as a trustworthy, apples-to-apples number while the model learns.

**Concrete handling**:
- `run_scenarios.py` / `just scenarios` remains 100% rule path (no change).
- `validate_model_policy.py --full-gauntlet` will have an explicit note: "Canonical suite run with rule path (transition special case — see design 626b378c). Model evaluated on full 5y + OOS only for this report."
- Future relaxation: when a training run includes `--length 21 --focus exact_canonical_shapes` and the resulting model passes a dedicated "canonical non-zero + cost delta" check, we flip the flag.

**Question 4: Distillation automation?**

**Recommended Decision**: **Keep distillation manual for the first 2–3 successful training cycles** (human + LLM inspects SHAP, tree paths on real-data rows that the model would have taken, and on focused weak-regime examples; emits candidate `_rule_xxx` functions in the exact v1.11 hook syntax; runs them through the existing `validate_rule.py + just scenarios` pipeline exactly as the gamma rules were done).

**Runner-up**: Invest in `distill_model_to_rules.py` immediately that auto-emits copy-pasteable rule source + the exact CLI command.

**Rationale**:
- We have only one real model training run under our belt (the 2026-05-15 focused set). The manual path has already proven value (two gamma/marginal rules shipped and contributed to the 91% DD cut).
- Automation before we have 2–3 successful model-derived rule sets risks building a tool that encodes the wrong extraction heuristics.
- Manual distillation forces the human/LLM curator to understand *why* the model chose a policy on a particular state — this is the exact "data-driven critic" loop the project wants (GOAL.md). The tool can come later as a productivity win once the pattern is clear.
- When we do build the tool (PR 6+), its output must still be a small explicit function that goes through `validate_rule.py` — never a black-box emission.

**Promotion ladder (see Playbook)**: Distilled explicit rule → ship in `adaptive_rules` tuple (preferred). Direct `enable_model_entry=True` hybrid only after multiple independent wins and only as opt-in / A/B surface.

---

### 2. Model Training, Evaluation & Promotion Playbook (Actionable Recipe)

#### 2.1 Data Generation & Labeling Recipe (for the next large focused run)

**Recipe Prerequisites (PR 2 deliverables — must be verified before first execution)**:
- `python simulator/build_training_set.py --help` shows `--low-regret-filter` and `--scenarios`.
- `python simulator/validate_model_policy.py --help` shows `--full-gauntlet --compare-baseline`.
- `PickEntryModel` accepts the new `recommend(..., min_policy_conf, min_edge, use_should_trade_gate, debug)` signature and `predict_should_trade`.
- `StrategyConfig` has the five `model_*` fields.
- `simulator/verify_model_features.py` (or equivalent) exists and passes on the 20260515 models.
- `feature_utils.build_should_trade_features` exists with the documented neutral contract.

**These commands assume PR 2 has landed** (the `--low-regret-filter` arg, the hardened `recommend` signature + should-trade wiring, the new `build_should_trade_features`, `validate_model_policy --full-gauntlet` parity, `StrategyConfig` model knobs, and the feature-parity smoke). Before executing any command below, run the verification gate from the PR 2 section and confirm the new flags/helpers are present. Paste the `--help` and smoke output into the training log.

**Command sequence** (to be codified in a new `simulator/RETRAIN_RECIPE.md` or `simulator/PLAN.md` appendix after PR 2):

```bash
# 1. Focused densification on known weak regimes (training-time only; does NOT touch the 12 immutable REGIMES)
python simulator/generate_scenarios.py \
  --tickers TSLA TSLL \
  --per-regime 120 \
  --focus v_recovery,high_gamma_marginal,post_earnings_weak \
  --length 25 \
  --save .cache/focus_weak_20260518.parquet

# 2. Build rich labeled set with low-regret filtering (new --low-regret-filter arg added in PR 2)
python simulator/build_training_set.py \
  --scenarios .cache/focus_weak_20260518.parquet \
  --label \
  --low-regret-filter 30 \
  --output .cache/training_set_focus_lowregret_20260518.parquet
# (Internally: keeps only rows where regret_vs_oracle <= 30 OR oracle_best_pnl > 0; also supports union with prior rich sets for stability)

# 3. (Optional but recommended) Short-window variant for canonical calibration
python simulator/generate_scenarios.py --focus ... --length 21 --save .cache/focus_21d.parquet
# then build with same filter → train a "short-window should-trade" variant if needed.
```

**Low-regret filter rationale**: Densifies the states where *some* policy actually wins (attacks the "model proposes on hopeless marginal states" problem). The 85th-percentile comment already exists in `train_best_policy_model.py`; we surface it as a first-class CLI flag + quality metric (print median regret, % zero-regret, % rows kept).

**Knob default calibration (first focused run)**: The starting values 0.55 / 0.35 / 6.0 are engineering starting points only. On the first real 2y calibration run after PR 2, sweep the three `model_*` thresholds on a recent 2y slice (print gate firing rate, n_trades, cost impact, and policy diversity) and update the documented defaults + `DEFAULT_CONFIG_BY_TICKER` examples before any promotion discussion. This is called out in the remaining Open Questions.

**Role of oracle**: `compute_oracle_best_on_path` (25+ sampled policies) provides the regret label and the "best_policy_for_path" target. We never train the inference model on raw realized P/L of the enumerated set; we train it to imitate the low-regret / oracle-chosen policy.

#### 2.2 Training Objectives & Model Combination at Inference

- **should_trade gate** (binary LGBM, 20 features): first cheap filter. Threshold default 0.55 (knob `model_min_should_trade`). Returns [] immediately if below (rich log: "should_trade prob=0.41 < 0.55 → stand aside").

  **Exact training target (literal from live code)**: `train_should_trade_model.py:37-39` does `df = df[df["best_policy_for_path"].notna() & (df["best_policy_for_path"] != "")]; df["should_trade"] = (df["pnl_per_contract"] > 0).astype(int)`. The label is therefore the *per-row realized* profitability of whatever `(action, policy)` example row was present in the parquet (after keeping rows that have a known best policy name). It learns a *joint* state + candidate-policy profitability signal, not a pure state-only "is any good policy profitable here?" filter. `regret_vs_oracle` is per-example and `best_policy_for_path` is simply broadcast to all policies evaluated for that (path, entry) state (see `trade_labeler.py:334-338` and `build_training_set.py:142-146`).

  **Neutral helper justification and calibration requirement**: The proposed `build_should_trade_features` deliberately feeds a *fixed* neutral `EntryAction("put", 5, 0.22) + ManagementPolicy("standard")` (plus the market row's ret/iv/peek features) at inference time. This is an explicit engineering approximation / conservative proxy for "is the market state one in which even a typical policy can make money?" It queries the joint model at a canonical point in the (action, policy) space rather than the exact winning action. 

  **Calibration note (must be executed on first focused run)**: After building any new training parquet, also emit (or manually slice) a small `gate_eval.parquet` containing only the winning-policy rows per state. On the first real focused training cycle, measure and print the gate's positive rate on rows where `oracle_best_pnl > 0` vs. `oracle_best_pnl <= 0` (and vs. the empirical distribution of winning actions' deltas/DTEs). If the neutral proxy proves mis-calibrated, a future "pure best-pnl>0 state gate" (trained only on winning rows) can replace or ensemble with it. The helper docstring in `feature_utils.py` must document the exact neutral values chosen and the approximation rationale above.
- **best_policy multi-class** (23 features): primary scorer. Produces `policy_confidence` per (action, policy) pair.
- **P/L regressor** (optional): tie-breaker / edge signal. `expected_pnl` used in `final_score = conf*0.6 + max(pnl,0)/200 * 0.4`.
- At inference (`recommend` hardened in PR 2): after should-trade gate, score all, keep only those with `policy_conf >= min_policy_conf` **and** `expected_pnl >= min_edge`, return top-k or []. No more unconditional permissive boost (the `<0.15` logic becomes `if test_permissive` dev flag only).

**Feature parity enforcement (PR 2)**: Add to `feature_utils.py`:

```python
def build_should_trade_features(row: pd.Series) -> pd.DataFrame:
    """Action-agnostic 20-col vector for the should-trade gate (exact match to
    should_trade_model_20260515_0037.txt feature_names).

    Uses a *fixed neutral* EntryAction("put", 5, 0.22, min_credit_pct=0.010) +
    ManagementPolicy("standard") to populate peek greeks and the 8 mgmt_* one-hots.
    This is a deliberate engineering approximation (see section 2.2 for full
    justification and calibration requirement): we query the joint (state + policy)
    profitability classifier at a canonical "typical" point in action/policy space
    rather than the exact winning action for that row. The resulting gate is a
    conservative proxy for "is this market state one in which even a typical policy
    can make money?"

    Caller (PickEntryModel.predict_should_trade) performs the final strict column
    alignment + reindex to the 20 names the model was trained on. This helper is
    the single source of truth for gate feature preparation.
    """
    neutral_action = EntryAction("put", 5, 0.22, min_credit_pct=0.010)
    neutral_policy = ManagementPolicy("standard")
    return build_model_features(row, neutral_action, neutral_policy)
```

`PickEntryModel.predict_should_trade` uses this + the exact same strict pad/reindex logic already present for the 23-col model. This eliminates the "neutral + alignment to 20 cols" friction.

#### 2.3 Success Criteria for "Ready for Real Gauntlet Comparison"

A model (or its distilled rules) is promoted to the first public `validate_model_policy.py --full-gauntlet --compare-baseline` report only when **all** of:

- **Quantitative (cost function on real surfaces — must reuse the exact language the team already trusts)**:
  - The `validate_model_policy.py --full-gauntlet --compare-baseline` report must produce a textual verdict that is one of the three "likely ship" strings from `validate_rule.py:_verdict` (TRIPLE-WIN, "5y+Suite win; OOS within noise...", or "5y+OOS win; Suite within noise...") *and* whose per-regime worst-regime delta satisfies the existing > −$500 catastrophe guard already printed by `validate_rule.py`.
  - 5y backtest (full history) + walk-forward static OOS (252/63) with the hybrid entry_fn show no regression on the surfaces that the verdict treats as decisive.
  - (The "+5% aggregate" numeric bar from earlier drafts is removed; the existing verdict strings + catastrophe table are the sole quantitative promotion gate for the first model reports, exactly as they are for rules. Activity/diversity/qualitative/regret bullets below are *additional* model-specific gates.)

  **Explicit note for the first public model report**: "The first model report must be readable by the same human who reviews `validate_rule.py` output; it re-uses the exact strings, per-regime table format, and catastrophe ±$500 language. Any additional numeric summaries (n_trades, policy mix) are appended after the canonical verdict block."
- **Activity & diversity**: n_trades on 2y+ real history ≥ baseline (or ≥30 with visible policy mix — at least 3 different ManagementPolicy names appear >5% of the time, "tight_risk"/"ultra_tight" not 0%).
- **Qualitative**: Chosen policies make sense on inspected rows (SHAP + manual review of high-gamma marginal states, post-earnings, v_recovery). No obviously insane side/DTE proposals on known regimes.
- **Regret improvement**: On a held-out focused synthetic set, median regret_vs_oracle of the model's chosen policy is lower than the baseline "standard" policy.
- **Canonical note**: Explicit statement in the report: "Canonical 21-day suite executed under rule path (transition special case per design 626b378c). Model non-zero rate on canonical windows: X% (expected low)."

If the model fails, append a null result to history with the exact training command + model versions + diagnosis. This prevents re-proposing the same data cut.

#### 2.4 Exact Hybrid Contract (what PR 3 implements)

See the Mermaid diagram below. In pseudocode (after PR 3):

```python
# inside pick_entry, after resolved = adapt_entry_params(...) and skip check
if cfg.enable_model_entry and _PICK_ENTRY_MODEL is not None:
    if _PICK_ENTRY_MODEL.predict_should_trade(row) >= cfg.model_min_should_trade:
        recs = _PICK_ENTRY_MODEL.recommend(
            row,
            min_policy_conf=cfg.model_min_policy_conf,
            min_edge=cfg.model_min_edge,
            use_should_trade_gate=False,  # already passed
        )
        if recs:
            best = recs[0]
            # post-model veto (Q2)
            if _passes_model_veto_rules(row, best.entry_action, cfg):
                action = best.entry_action
                policy = best.recommended_policy
                # full-plan override
                side, dte, target_delta = action.side, action.dte, action.target_delta
                # price with action...
                pos = Position(..., daily_capture_mult=policy.daily_capture_mult,
                               max_loss_mult_override=policy.max_loss_mult,
                               profit_target_override=policy.profit_target,
                               delta_breach_override=policy.delta_breach)
                log_model_decision(...)
                return pos
    # fall through to rule path (or the base resolved)
# normal rule pricing + Position construction using resolved + cfg
```

`StrategyConfig` additions (PR 2, all default-safe):

```python
enable_model_entry: bool = False
model_min_should_trade: float = 0.55
model_min_policy_conf: float = 0.35
model_min_edge: float = 6.0          # $ per contract
model_debug: bool = False
model_best_policy_path: Optional[str] = None  # for pinning
model_should_trade_path: Optional[str] = None
```

`pick_entry_model` wrapper and direct adapter in validate must both forward the fourth override and respect the new knobs (so validator and live use identical code).

#### 2.5 Promotion Ladder

1. Interesting training run → manual distillation → `validate_rule.py` (exact same as v1.13) → `just scenarios` → ship as new entry in `adaptive_rules` tuple (or knob change) if criteria met. Preferred path.
2. Multiple independent wins via distillation → consider opt-in direct hybrid (`enable_model_entry=True` in a documented branch config for A/B or dashboard shadow).
3. After two independent full-plan hybrid wins on real gauntlet with no regression on the other ticker + documented canonical behavior → flip default for one ticker (with 30-day live shadow period recommended).
4. Never: model becomes the only path. Rule fallback always exists.

#### 2.6 Observability & Regression Protection for Training Artifacts

- Every model file committed or referenced includes its exact training command in a sidecar `.json` or in `simulator/PLAN.md`.
- `PickEntryModel.get_model_info()` returns filenames + feature counts + load time (PR 2).
- `validate_model_policy.py --full-gauntlet` prints the exact three model versions used + the five `model_*` knob values.
- Feature parity smoke (new `simulator/test_pick_entry_model.py` or inline in validate): after load, `build_should_trade_features` + alignment yields exactly 20 cols matching `should_trade_model.num_feature()`; same for 23-col best-policy. This is the behavioural regression check (no unit tests per CLAUDE.md).
- Label quality metrics (median regret, % zero-regret, % rows after low-regret filter) are printed on every build and stored with the parquet.

#### 2.7 Mermaid Diagrams

**Hybrid Decision Flow (post four decisions)**

```mermaid
flowchart TD
    Start[pick_entry row, cfg, S, today] --> Regime[regime + adapt_entry_params + ADAPTIVE_RULES (first pass of hard skips)]
    Regime --> Skip{resolved.skip?}
    Skip -->|Yes| None[return None]
    Skip -->|No| ModelGate{cfg.enable_model_entry and model loaded?}
    ModelGate -->|No| RulePath[price with resolved + credit floor + rule overrides → Position]
    ModelGate -->|Yes| Should[should_trade = predict_should_trade(row) >= cfg.model_min_should_trade]
    Should -->|No| RulePath
    Should -->|Yes| Recs[recs = recommend(..., min_conf, min_edge)]
    Recs --> Empty{recs and top passes thresholds?}
    Empty -->|No| RulePath
    Empty -->|Yes| Veto{post-model hard-skip veto (second pass of proven tsll_skip_* + gamma rules only)?}
    Veto -->|Veto| RulePath
    Veto -->|Pass| FullOverride[take model action (side/dte/delta) + policy's 4 values as overrides]
    FullOverride --> Pos[Position(..., daily_capture_mult, max_loss_override, profit_override, delta_breach_override)]
    RulePath --> Pos
    Pos --> Check[check_exits (honors overrides)]
    style FullOverride fill:#ccffcc
    style Veto fill:#ffddaa
```

*Caption: Matches pseudocode in 2.4 and live call sites `pick_entry:737` (adapt_entry_params + first ADAPTIVE_RULES pass), `strategies.py:851` (check_exits override reading), `run_scenarios.py:39` (always uses pick_entry), `validate_model_policy.py:121` (model entry_fn path). The post-model veto is explicitly a *second* pass of only the proven hard-skip subset.*

**Full Training → Labeling → Model → Evaluation → Promotion Loop**

```mermaid
flowchart LR
    Char[characterize.py on real] --> Gen[generate_scenarios --focus weak regimes + --length 25 + --save]
    Gen --> Label[TradeLabelerV2 + regret_vs_oracle + low-regret-filter 30]
    Label --> Feat[build_training_set + feature_utils (current 23-col) + new build_should_trade_features (PR 2, neutral for gate)]
    Feat --> Train[retrain should_trade (20c) + best_policy (23c) + optional P/L]
    Train --> Load[PickEntryModel loads latest + prints versions]
    Load --> Val[validate_model_policy --full-gauntlet: 5y + OOS + cost delta vs baseline]
    Val --> Note[Canonical suite: rule path (transition special case)]
    Val --> Gaunt[just scenarios (unchanged, pure rule)]
    Gaunt --> Dec{All criteria? cost win / null+0-DD-reg + n_trades + diversity + qualitative + regret drop}
    Dec -->|Yes| Distill[Manual SHAP + tree inspection → explicit _rule_xxx or knob change]
    Dec -->|Yes| Distill2[Optional: direct hybrid A/B with enable_model_entry]
    Dec -->|No| Iterate[more focused gen / different filter / recalibrate gate thresh]
    Distill --> ValidateRule[validate_rule.py + just scenarios (same as v1.13)]
    ValidateRule --> Ship[update DEFAULT_CONFIG_BY_TICKER or adaptive_rules tuple + docs]
    Ship --> History[append to STRATEGY.md / PLAN.md with exact training command]
```

*Caption: Matches pseudocode in 2.4 and live call sites `pick_entry:737` (adapt_entry_params + first ADAPTIVE_RULES pass), `strategies.py:851` (check_exits override reading), `run_scenarios.py:39` (always uses pick_entry), `validate_model_policy.py:121` (model entry_fn path). The post-model veto is explicitly a *second* pass of only the proven hard-skip subset.*

**Canonical-Window Handling During Transition**

```mermaid
flowchart TD
    Official["just scenarios" / run_scenarios.py] --> AlwaysRule[Always uses pure pick_entry (rule path)]
    AlwaysRule --> Gate[Immutable 12-regime 21-day CANONICAL_SCENARIOS — regression gate stays honest]
    ModelVal["validate_model_policy --full-gauntlet"] --> FullHistory[5y backtest + walk-forward OOS with hybrid entry_fn]
    ModelVal --> CanonicalNote["Canonical 21-day: run with rule path + explicit note 'transition special case per design 626b378c' + model non-zero rate reported separately"]

*Caption: Matches pseudocode in 2.4 and live call sites `pick_entry:737` (adapt_entry_params + first ADAPTIVE_RULES pass), `strategies.py:851` (check_exits override reading), `run_scenarios.py:39` (always uses pick_entry), `validate_model_policy.py:121` (model entry_fn path). The post-model veto is explicitly a *second* pass of only the proven hard-skip subset.*
    FullHistory --> Compare[Cost delta vs baseline on real surfaces]
    Compare --> Promo{Decision per playbook criteria}
    Promo -->|Pass| Lift[Future: after short-window focused training, optionally relax canonical force-rule]
```

---

## API / Interface Changes

- `StrategyConfig` (strategies.py): 5 new fields (listed above) with safe defaults.
- `PickEntryModel.recommend(...)`: new optional kwargs `min_policy_conf`, `min_edge`, `use_should_trade_gate`, `debug` (back-compat: old call sites still work).
- `feature_utils.py`: `build_should_trade_features(row)` (neutral canonical usage) + minor `build_pl_features` if needed for P/L alignment.
- `validate_model_policy.py`: `run_full_model_gauntlet` that replicates the exact `_bt`/`_suite`/`_oos`/`_verdict` shape and language of `validate_rule.py` (using entry_fn + cfg with model knobs); CLI parity; delta_breach forwarding on both adapter paths; `from backtest import Position`.
- No changes to `Position`, `check_exits`, `pick_entry` signature, `scenarios.py`, or cost function.

---

## Data Model Changes

None. Parquet training sets are ephemeral. Model `.txt` files are append-only in `.cache/models/`. Sidecar metadata (training command, label quality metrics) recommended but not a schema change.

---

## Alternatives Considered

(Already summarized in parent design; the four Q decisions above are the new alternatives analysis. The "management-only" and "no post-veto" and "require non-zero on canonical" and "auto-distill now" paths were explicitly evaluated and rejected for the reasons given.)

---

## Security & Privacy Considerations

Purely local research. Models are numeric LightGBM trees on public market-derived features. No PII, no network at inference. The only process risk is accidental promotion of an overfit or distribution-shifted model — mitigated by the real-data firewall + mandatory `just scenarios` + human-curated distillation.

---

## Observability

- Load time: exact filenames + feature counts + "should_trade gate active".
- Decision time: structured "MODEL vs RULE" log with should_trade prob, top-3 (action,policy,conf,edge), chosen overrides, post-veto reason if any, model versions.
- Validation: every gauntlet report contains the five knob values + three model filenames + training command reference.
- Dashboard (PR 5): side-by-side rule vs model rec for today + feature vector + top policy scores.
- Training artifacts: median/zero-regret % printed and stored with each parquet.

---

## Rollout Plan

1. **PR 2 (Hardening + Knobs + Alignment)**: Implement the decisions (full-plan + post-veto skeleton + canonical note), add `build_should_trade_features`, 5 `StrategyConfig` fields, harden `recommend` to return [] cleanly, deprecate rescues behind `test_permissive`, fix validator import + delta_breach on both paths, add feature-parity smoke. `just scenarios` still 100% rule.
2. **PR 3 (Hybrid Contract)**: Wire the decision tree inside `pick_entry` (or thin `pick_entry_hybrid`), export `make_model_entry_fn(cfg)` for validator parity, rich logging.
3. **PR 4 (Gauntlet Parity + Decision Framework)**: `validate_model_policy.py` reaches literal parity with `validate_rule.py` output (cost, 3 surfaces, verdict strings, per-regime table with catastrophe flag). Document promotion criteria + transition special case in STRATEGY.md.
4. **PR 5 (Surfacing)**: `live.py` / `just test` + dashboard show model reasoning when flag on.
5. **PR 6 (First Real Comparison)**: Execute the focused recipe, publish the report (even if "null but learned X and no regression"), update docs with exact commands. This is the value PR.

Rollback at any time: set `enable_model_entry=False` (instant) or revert a distilled rule addition. Rule path is never deleted.

---

## Key Decisions (8 numbered, 1-sentence rationale each)

1. **Full-plan override (model action + policy) is the v1 hybrid contract** — serves the north-star derivation power while the real-data firewall + post-veto + gate keep tail risk acceptable.
2. **Post-model veto layer for the five proven hard-skip rules (plus gamma ones)** — "proposer can change; validator cannot" in the most literal and cheapest way.
3. **Canonical 21-day windows stay rule-only during transition (documented special case)** — preserves the honesty of the immutable regression gate while the model learns the short-window distribution.
4. **Distillation kept manual for the first 2–3 cycles** — we have only one real run; manual curation has already produced shipped value and forces understanding before we automate.
5. **Low-regret filtering (regret_vs_oracle ≤ 30 or oracle > 0) becomes first-class in the training recipe** — directly attacks the "model proposes on hopeless states" root cause diagnosed in PR 1.
6. **`feature_utils.py` (neutral action/policy for gate) is the single source for should-trade 20-col vectors** — eliminates the last major train/inference alignment surface.
7. **`validate_model_policy.py` must emit literally the same verdict language and cost deltas as `validate_rule.py`** — trust is earned only when the two harnesses speak the same dialect the team already uses for shipping decisions.
8. **`just scenarios` command and the 12 frozen windows are never altered for model work** — the gate is the source of truth; the model (and its data recipe) must adapt to it, not the other way around.
9. **Promotion ladder prefers explicit distilled rule over direct model mode** — matches three years of project culture (all wins are small auditable functions) and satisfies "no black-box for anything that ships."
10. **All model training commands + label-quality metrics + knob values are captured in every gauntlet report and history entry** — reproducibility and institutional memory for the critic loop.

---

## Risks & Mitigations

- **Distribution shift on 21-day canonical windows (High)**: Model excellent on 5y/30d paths but [] on the exact regression slices. **Mitigation**: documented force-rule special case + focused 21-day generation variant + explicit "non-zero rate on canonical" metric in reports; only lift when short-window calibration succeeds.
- **Over-conservative gates (0 trades on real history) (High)**: Even with low-regret data, min_* + 0.55 should-trade may still stand aside everywhere. **Mitigation**: explicit tunable knobs (default chosen after first calibration run on real 2y), `test_permissive` dev flag, iterative focused retrains, success metric = non-zero with acceptable DD.
- **Feature parity / peek drift (Medium)**: Manual pricing in strategies wrapper vs `feature_utils`. **Mitigation**: PR 2 deletes the dupe code; all paths (training, recommend, validator adapters) go through the single source + the new `build_should_trade_features`.
- **Firewall bypass temptation (High, process)**: "The model looks good on synthetic, let's just turn it on live." **Mitigation**: CLAUDE.md + this design + PR template language that `just scenarios` + cost delta on real surfaces are mandatory; `enable_model_entry` defaults False; every history entry must cite the exact training command.
- **Policy diversity collapse (Medium)**: Model always picks "standard". **Mitigation**: promotion checklist requires visible mix; if observed, increase sampling bias or add entropy term in future labeling.
- **Delta_breach & roll policy gaps (Low)**: Current ManagementPolicy has delta_breach and allow_roll, but roll logic in `pick_roll` is still cfg-driven. **Mitigation**: first hybrid only uses the four scalar overrides (already wired); full roll policy is future work after M6.
- **Label quality on real data (Medium)**: We have no oracle on real trades. **Mitigation**: regret metrics are only a training-time densification signal; final promotion is always on real 5y + OOS + scenarios with the cost function.

---

## Updated PR Plan (Reflecting the Four Decisions)

**PR 1 (stabilisation items)**: Not yet landed in `main`. The four files from best-of-n Candidate 1 (should-trade load + `predict_should_trade` + early return-[] gate, rich per-candidate + "why" diagnostics, import fix + delta_breach forwarding on both validator adapters, verification helpers) are the *reference implementation* but the changes have not been applied to the live tree. PR 2 will deliver **both** those stabilisation items **and** the additional hardening/knobs/feature_utils work. The Current State section above is the authoritative list of what is absent today.

**PR 2: Stabilisation (PR 1 items) + Hardened PickEntryModel + Feature Alignment + Knobs + Post-Veto Skeleton + Playbook Prerequisites**
- **Verification gate at start of PR 2 execution**: Before any code change, run `python simulator/pick_entry_model.py` and `python simulator/validate_model_policy.py` (on a real 2y `data.build` row + the 20260515 models) and paste the exact output + traceback into the PR description. This confirms the pre-PR 2 baseline documented in the Current State section.
- Files & exact delta (PR 2 must implement *everything* below because the tree is the pre-merge PoC):
  - `simulator/pick_entry_model.py`: **Add** `should_trade_model` load in `__init__` + `predict_should_trade` (using the new neutral helper + strict 20-col alignment) + early `return []` when gate fails; **add** `min_policy_conf`, `min_edge`, `use_should_trade_gate`, `debug` kwargs to `recommend`; remove unconditional permissive boost (move behind `test_permissive=True` dev flag only); add `get_model_info()`; keep rich per-candidate + aggregated "return [] reason" logging.
  - `simulator/feature_utils.py`: **Add** `build_should_trade_features(row)` (neutral action/policy + full docstring with approximation rationale and calibration note) + any `build_pl_features` alignment helper.
  - `strategies.py`: **Add** the 5 `model_*` fields (with safe defaults) to `StrategyConfig` + `DEFAULT_CONFIG_BY_TICKER` (for both tickers) + `get_config`; **delete** the manual peek pricing duplication in `pick_entry_model()` wrapper and delegate to `get_peek_features_for_action` + `feature_utils`; **add** `_passes_model_veto_rules` helper (lightweight second pass of the proven hard-skip subset); forward the 4th override (`delta_breach_override=policy.delta_breach`); surface load errors loudly when `enable_model_entry` would be True.
  - `simulator/validate_model_policy.py`: **Add** `from backtest import Position`; forward all 4 policy fields (incl. `delta_breach`) on *both* adapter paths; **add** rich per-candidate/return-[]-reason logging; implement `run_full_model_gauntlet` + `--full-gauntlet --compare-baseline` CLI that produces literal `validate_rule.py` verdict strings + per-regime table + cost deltas.
  - `simulator/build_training_set.py`: **Add** `--low-regret-filter N` arg + support for `--scenarios pregenerated.parquet` (the filter keeps rows where `regret_vs_oracle <= N` or `oracle_best_pnl > 0`; also support union with prior sets).
  - New executable `simulator/verify_model_features.py` (or `test_pick_entry_model.py` — see nit in review) that asserts exact 20-col and 23-col alignment after loading the latest models (the behavioural regression check; wired into the recipe).
- Dependencies: none (this PR starts from the live pre-merge tree).
- Gate: `just scenarios` still pure rule. All changes behind `enable_model_entry=False` default.

**PR 3: Hybrid Integration + Model as First-Class entry_fn**
- Files: `strategies.py` (decision tree after adapt_entry_params using the four decisions: full-plan, post-veto, should-trade + min_*), `simulator/validate_model_policy.py` (use the new exported `make_model_entry_fn(cfg)` so both paths identical), `backtest.py` (doc only).
- `pick_entry` signature unchanged; `enable_model_entry=False` by default.

**PR 4: Model Gauntlet Parity + Decision Framework + Canonical Note**
- Files: `simulator/validate_model_policy.py` (full `_run_all` parity with `validate_rule.py`, CLI `--full-gauntlet --compare-baseline`, per-regime table with catastrophe flag, explicit transition note), `STRATEGY.md` + `simulator/PLAN.md` (promotion criteria + "when we lift the canonical special case"), `validate_rule.py` (optional: extract shared `_verdict` / `CATASTROPHE = -500` helpers for literal code reuse).
- First public model report format defined.

**PR 5: Live + Dashboard + Justfile Targets**
- `live.py`, `tsla_options_dashboard.py`, `Justfile` (new `model-validate`, `model-train-focus` etc.), optional tiny CLI on `pick_entry_model`.

**PR 6: Focused Retrain + First Public Comparison (Value PR)**
- Execute the exact recipe in the Playbook, publish numbers + commands + model artifacts (or null + diagnosis), append to history. This is the first time the full policy model is measured end-to-end against v1.13 under the real firewall.

---

## Open Questions (Remaining After This Design Round)

1. Exact default values for the five `model_*` knobs after the first calibration run on real 2y data (will be swept in PR 6).
2. Whether a "short-window should-trade" variant (trained only on 21-day focused paths) is needed before lifting the canonical special case, or whether the main gate + focused 21d data suffices.
3. Roll-policy surface: when (if ever) the `ManagementPolicy.allow_roll` / `roll_credit_ratio` fields become first-class inference outputs vs. remaining cfg-driven.
4. When the first direct hybrid A/B (enable_model_entry on a shadow dashboard pane) should be turned on for daily human review (after PR 4 or only after a distilled win?).

These are deliberately small and can be decided during PR 3–6 execution with data in hand.

---

## References

- simulator/OPTIONS_MODEL_DESIGN.md (parent, PR 1 section + four open Qs)
- simulator/NORTH_STAR.md (5-layer vision, "model derives optimal side/DTE...")
- simulator/PLAN.md (current PoC status, regret supervision)
- GOAL.md (cost function, M6, "proposer can change; validator cannot", no black-box)
- CLAUDE.md (`just scenarios` gate, doc convention, no unit tests, live==backtest)
- strategies.py:703 (pick_entry), 737 (adapt_entry_params), 790 (check_exits overrides), 143 (pick_entry_model wrapper), 108 (DEFAULT_CONFIG)
- simulator/pick_entry_model.py:110 (recommend), 87 (_prepare), 33 (imports from trade_labeler + feature_utils)
- simulator/validate_model_policy.py:25 (_make_model_entry_fn), 69 (Position), 109 (run_on_canonical)
- simulator/feature_utils.py:62 (build_model_features — 23 cols), 118 (get_peek)
- simulator/trade_labeler.py:33 (EntryAction), 42 (ManagementPolicy + delta_breach), 57 (DEFAULT_8), 69 (sample_...), 340 (regret_vs_oracle)
- simulator/train_should_trade_model.py:37 (target), 43 (20 feature cols)
- scenarios.py:43 (REGIMES), 67 (CANONICAL_SCENARIOS — frozen 21-day), 209 (canonical_window)
- validate_rule.py:73 (_verdict + catastrophe language), 47 (_suite), 31 (_bt)
- backtest.py:24 (Position with four override fields)
- .cache/models/should_trade_model_20260515_0037.txt (20 feats), best_policy_model_20260515_0153.txt (23 feats)

---

**End of Design Document**

*This document was written after exhaustive tool-based exploration (list_dir, read_file of every referenced source, grep across 20+ files for every contract point, python inspection of the two latest models for exact feature counts and names, cross-reference of GOAL/NORTH_STAR/CLAUDE invariants, and direct inspection of the 12 canonical windows and the exact cost-function verdict strings). Every claim, interface, and decision is traceable to a concrete file path or function name. No abstractions were invented; the design simply makes the next implementation step unambiguous and high-quality.*

---

## Revision History

- 2026-05-18: Initial draft resolving the four open questions and delivering the full actionable playbook + diagrams + updated PR plan + 10 Key Decisions.

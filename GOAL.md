# Goal — Engine end-state: self-improving short-premium strategy via data-driven critic loop

> Use this as the `/goal` input in a new session. Self-contained: any session can pick it up cold.

---

## North star

Build an **engine that proposes, validates, and ships its own strategy refinements** — turning the human (or LLM) operator into a curator of empirical hypotheses, not the author of trading logic. Each refinement is a small, interpretable, adaptive *rule* (or knob change) that goes through the same deterministic validation gauntlet and either ships or null-results.

The destination is **Software 1.5 → 2.0 in increments**:
- **1.5** (now): Data-driven proposal of rule sketches; human/LLM picks one per round; deterministic engine validates and ships.
- **2.0 (later)**: A trained model proposes rule sketches or directly outputs adjustment vectors per bar; same validation harness gates everything.

The **deterministic validation harness is the trust layer.** Proposers can be anything — human intuition, LLM critic, gradient-boosted tree, neural net — and trust comes from the unchanged validation gate, not from the proposer.

---

## Current state — v1.13 (2026-05-14)

The engine is at the point where the **full data-driven critic loop is online end-to-end AND has been exercised to ship a fleet of 5 adaptive rules with M1–M5 milestones complete**:

```
1. Strategy runs                          → produces a trade log
2. data.py features (33+ columns)         → joined onto each trade's entry date
3. peek_position greeks                   → also joined per trade
4. analyze.py (`just analyze`)            → quartile + custom-edge + narrow-window
                                            + 2-feature pair scan with BH-FDR;
                                            emits candidate rule sketches in v1.11
                                            hook syntax (copy-pasteable)
5. validate_rule.py (A/B harness)         → runs candidate against baseline across
                                            5y + 12-regime suite + walk-forward
                                            OOS, emits TRIPLE-WIN / MIXED / NULL
6. Ship if cost-function policy met       → adaptive_rules tuple updated in
   AND no catastrophe regression            DEFAULT_CONFIG_BY_TICKER
```

**Baseline metrics at v1.13** (TSLA 5y / TSLL 5y):
- TSLA: 100 trades, 92.0% WR, +$17,790 P/L, $1,107 max DD, 5.25 PF
- TSLL: 160 trades, 78.8% WR, +$3,250 P/L, $144 max DD, 4.28 PF
- Session arc (TSLA): −$6,242 (v1.1) → +$17,790 (v1.13) = +$24,032 swing, max DD cut 91%.
- Session arc (TSLL): −$981 (v1.1) → +$3,250 (v1.13) = +$4,231 swing, max DD $1,461 → $144 (−90%).

**5 adaptive rules shipped, all validated through the standard gauntlet:**

1. `tsll_skip_marginal_up` — skip TSLL when `0 ≤ ret_14d ≤ 0.05` (v1.12; hand-found bucket)
2. `tsla_skip_mild_intraday_up` — skip TSLA when `0.5% ≤ intraday_return ≤ 1.6%` (v1.13; `--scan-narrow`)
3. `tsll_skip_tuesday` — skip TSLL entries on Tuesdays (v1.13; `--scan-narrow`)
4. `tsll_skip_post_earnings_drift` — skip TSLL when `11 ≤ days_since_earnings ≤ 21` (v1.13; `--scan-narrow`)
5. `tsll_skip_downtrend_high_iv` — skip TSLL when `ret_14d ∈ [-0.63, -0.07] AND iv_rank ≥ 77` (v1.13; `--pairs` conjunction)

**Engine architecture milestones complete (M1–M5):**
- M2 — analyzer extensions (custom edges + narrow scan + BH-FDR multiple-testing correction)
- M3 — `--pairs` 2-feature interaction analysis (3×3 grid with FDR)
- M4 — per-position knob overrides (`max_loss_mult_override`, `delta_breach_override`, `profit_target_override` on `Position`; rule contract accepts `min_credit_pct`, `max_loss_mult`, `delta_breach`, `profit_target`, `daily_capture_mult` keys)
- M5 — exit-side adaptive hook (`adapt_exit_params`, `ADAPTIVE_EXIT_RULES`, demonstration rule `take_half_on_reversal` registered)

**Documented stable interface:** STRATEGY.md "How to add an adaptive rule" — a 6-step canonical procedure (analyze → write → validate → decide → ship → update docs) that touches only `strategies.py` and config; ≤30 lines of code per new rule.

**Critic scoreboard now reads 8 wins + 5 nulls.** All nulls documented in STRATEGY.md history; the registered-but-not-enabled rules prevent the analyzer from re-proposing them.

---

## Cost function (non-negotiable)

**Manage extreme moves; accept calm-case opportunity cost.** Always optimize for never-losing-big over the biggest-possible-win. Every shipped change must pass:

1. **Cost-function score**: `total_pnl_per_contract − dd_weight × max_dd_per_contract`. Default `dd_weight = 1.0` (heavier than the optimizer's 0.5 — tail-management bias).
2. **No catastrophe regression**: no scenario-suite regime drops below the configured catastrophe threshold (default −$500).
3. **OOS validation**: walk-forward static must not degrade the OOS aggregate.
4. **Either ship-net-positive on all three surfaces** (5y + suite + OOS) **OR** ship-net-positive on at least one with the others null-within-noise and zero DD regression.

Stand-aside is success: a STAND_ASIDE day is the strategy doing its job, not a broken signal.

---

## What "done" looks like (the success criteria for this goal)

The goal is complete when:

- [x] **At least 5 adaptive rules** are validated and shipped via the data-driven loop (5/5 done as of v1.13)
- [x] **Per-side knob overrides supported** (M4: rules can return `min_credit_pct`, `max_loss_mult`, `delta_breach`, `profit_target`, `daily_capture_mult`, stored on `Position`)
- [x] **Analyzer extended** to handle:
  - [x] Finer bin counts with min-n guards (`--bins`, `--min-n`)
  - [x] Custom-edge buckets (`--custom-edges feature:v1,v2,v3`)
  - [x] Narrow-window sliding scan with BH-FDR multiple-testing correction (`--scan-narrow`)
  - [x] 2-feature interaction analysis (`--pairs`, 3×3 grid + FDR)
- [x] **At least one rule shipped that came from `just analyze`'s output** (4 of the 5 shipped rules came directly from the analyzer)
- [x] **Exit-side hook** (`adapt_exit_params(position, mark, row, cfg)`) mirroring the entry-side hook (M5)
- [x] **Documented stable interface** for future rule additions, so a new rule is a ≤30-line change that doesn't touch the engine (STRATEGY.md "How to add an adaptive rule")

Stretch:
- [ ] **Trained model proposer**: gradient-boosted tree on per-trade outcomes → outputs rule sketches with predicted effect size + confidence. The model is the *proposer*; the deterministic harness still validates. Train on rolling 3y windows to mitigate overfit.
- [ ] **Intraday-bar mode** (engine roadmap Phase 8) — would unlock context where rolls earn their keep and intraday-reversal exits become viable.
- [ ] **Real option chains** (engine roadmap Phase 9) — replace HV30 IV proxy with quoted IV, term-structure features, skew.

---

## Constraints / non-goals

- **No black-box rules.** Every shipped rule must be interpretable from its definition. If a model proposes a rule, the *output rule* must be a small explicit function (e.g., "skip when feature in bucket"), not a network forward pass.
- **No backwards-compatibility shims.** The project is small enough to rewrite. Don't carry dead code for past versions; mark mechanics that earned a null result as opt-in (like wheel, like roll-on-max_loss) and keep them off by default.
- **No engine forks for adaptive rules.** Backtest, scenarios, walk-forward, live, dashboard all share `pick_entry` (which now calls `adapt_entry_params`). Tuning in one place updates all.
- **No mocking of historical data** in walk-forward. Real bars only.
- **TSLA earnings dates list** in `data.py::_TSLA_EARNINGS_DATES` must stay in sync with `scenarios.py::TSLA_EARNINGS_DATES`. Both lists must be extended together when new earnings happen.

---

## Sequenced milestones (in order — each unlocks the next)

### M1 — Validate the analyzer's top picks (next session, ~1-2 hours)

The analyzer surfaced these high-effect features that were NOT hand-found:
- **TSLL `day_of_week`**: Thursday entries underperform (n=49, avg=$−0.5) vs Friday (n=57, avg=$+32, t=+4.31). Strong signal.
- **TSLA `days_to_earnings`**: $156 effect range.
- **TSLA `peek_credit_pct`**: $151 effect — premium quality discriminator.

**Action:** pick the strongest (likely TSLL day_of_week), implement as an adaptive rule, run the standard gauntlet. Ship if all three surfaces improve. Document null if not.

### M2 — Extend analyzer with finer/custom binning (~2 hours)

Quartile binning misses narrow ranges. The `tsll_skip_marginal_up` rule (ret_14d ∈ [0, 0.05]) was hand-found because quartiles don't break on those edges.

**Action:** add to `analyze.py`:
- `--bins N` already exists; extend to support `--custom-edges feature:val,val,val`
- A search routine that, for each feature, tries 5-10 candidate "narrow ranges" and reports any with significant effect
- Minimum-n guards + multiple-testing correction (Bonferroni or Benjamini-Hochberg) since we'll be testing many slices

### M3 — 2-feature interaction analysis (~3 hours)

Univariate analysis can't find conjunctions like "iv_rank > 60 AND ret_14d ∈ [−0.10, −0.05]". A 2-D bucket sweep over feature pairs would surface these.

**Action:** extend `analyze.py` with `--pairs` mode. For each pair of features, build a 4×4 (or 3×3) bucket grid, find the highest-effect-size cell with n ≥ min_n. Cap at top-50 pairs to keep runtime sane. Output ranked interaction rules.

### M4 — Per-side knob overrides (~2 hours)

Currently rules can return `{'skip', 'side', 'dte', 'target_delta'}`. Extend the contract to:
- `min_credit_pct` — per-entry credit floor
- `max_loss_mult` — per-trade max-loss multiple (stored on `Position`)
- `delta_breach` — per-trade delta-breach threshold
- `profit_target` — per-trade profit-take
- `daily_capture_mult` — per-trade daily-capture mult

**Action:** add these as optional keys in `current` and recognized in `adapt_entry_params`. Store on `Position` (new fields with `None` default = fall back to `cfg`). Update `check_exits` to prefer per-position overrides.

### M5 — Exit-side adaptive hook (~2 hours)

Mirror the entry-side hook for exits. `adapt_exit_params(position, mark, row, cfg) -> dict` returning either nothing or an explicit `'close': True` with a reason. Lets rules express things like "close if intraday reversal AND we're 50% in profit" — context-aware exits.

### M6 — First model-proposed rule (~1 day)

Train a small gradient-boosted classifier on `(features at entry, P/L sign)` from the 5y trade log. Use rolling 3y train / 1y test to avoid overfit. Output: feature importance + top decision-tree splits expressed as candidate rules in v1.11 syntax. Run the standard gauntlet on the top-3 model picks.

**Action:** add `analyze_model.py` (separate from `analyze.py` to keep deterministic stats and model-based proposal cleanly separated). Use scikit-learn or LightGBM. Output is interpretable: top splits = candidate rules.

**Progress (2026-05-31 via plan 019e7d50)**: Extended the simulator model machinery (pick_entry_model + feature_utils SoT + trade_labeler traj) to management/close-roll decisions. Added 10 trajectory decision-state features (current_pnl_pct, pace, adverse, ret_since, regime_at_decision etc) + build_management_decision_features. Trained demo advisor on focused weak-regime + low-regret synthetic labels (77.9% zero-regret coverage). Wired thin `enable_model_management` (default False) + advisor into positions tracker + whatif CLI for read-only guidance ("given traj + signals, model recommends tighten/close because..."). All behind flags; `just scenarios` / rule ladder pure. First real gauntlet: clean null (cost unchanged) — loop + infra ready for distillation to ADAPTIVE_EXIT_RULES or next cycle. See simulator/PLAN.md + STRATEGY.md history.

### M7 — Multi-rule interaction validation (~2 hours)

Once 3+ rules are shipped, their interactions matter. Two rules each "skip a bucket" may overlap (skipping more than intended) or be redundant.

**Action:** add a `just analyze --multi-rule` mode that compares: each rule alone, all rules together, all pairs of rules. Surface interaction effects (when does adding rule B *hurt* rule A's gains?).

### M8+ — Continuous loop

After M1-M7, the engine has the machinery. The work becomes recurring: run analyzer, pick candidates, validate, ship-or-null, document. Aim for 2-3 critic rounds per session.

---

## Files of record

- **`STRATEGY.md`** — current strategy + dated history. Update top in place when shipping; append history at bottom.
- **`ENGINE.md`** — current engine + dated history. Update when engine code changes.
- **`README.md`** — high-level session arc + code map. Update when versions ship.
- **`GOAL.md`** — this file. Update only when the destination shifts.
- **`CLAUDE.md`** — project rules (testing hygiene, doc convention, cost function). Don't drift from these.

The doc convention: **current state at top, dated history at bottom.** Append, never rewrite history.

---

## Glossary (for new sessions)

| Term | Meaning |
|---|---|
| **Critic loop** | Hypothesis → sweep → suite → walk-forward → ship-or-null cycle. Each round adds a row to the scoreboard. |
| **Adaptive rule** | A small `(row, cfg, current) -> dict` function in `strategies.ADAPTIVE_RULES`. Returns overrides for one entry. |
| **Hook** | `adapt_entry_params(row, cfg, base)` — the extension point inside `pick_entry` where rules run. |
| **Peek** | `pricing.peek_position(...)` — BSM-computes the would-be position's greeks at current candidate params. |
| **Scenario suite** | 12 canonical 21-day windows per ticker, frozen in `scenarios.CANONICAL_SCENARIOS`. The per-regime stress test. |
| **Walk-forward static** | Rolling 252-day train / 63-day test windows with a *fixed* config. Validates that improvements aren't sample-specific. |
| **Cost-function score** | `P/L − dd_weight × max_DD`. The single number we ship against. |
| **Triple-win** | Improvement on all three validation surfaces (5y, suite, OOS) with no DD regression. The bar for shipping a rule cleanly. |
| **Null result** | Tested-and-confirmed-no-change. Documented anyway — same value as a win because it prevents re-asking. |
| **Catastrophe flag (⚠)** | A sweep cell where worst-regime P/L is below the catastrophe threshold (default −$500). |
| **Cost function** | Manage extreme moves; accept calm-case opportunity cost. Tail-management priority over headline P/L. |

---

## Operating principles (carry across sessions)

1. **One hypothesis at a time.** Don't stack changes — each must be independently validated.
2. **Null results are first-class.** Document every round, win or not. The scoreboard is the institutional memory.
3. **Document interactions honestly.** When a knob's optimum shifts after another knob changes, say so. Combined sweeps > stacked individual sweeps.
4. **The proposer can change; the validator can't.** Whether the rule comes from human intuition, LLM critic, or trained model, it goes through the same gate.
5. **No premature optimization.** Land architecture before stacking features. Land features before stacking rules.
6. **Per-ticker is a feature, not a bug.** TSLA ≠ TSLL. They need different knobs *and* different rules.

---

## Quick reference — common commands

```bash
just backtest                                    # 5y backtest on both tickers
just scenarios                                   # 12-regime stress-test (REQUIRED before/after strategy changes)
just optimize --static                           # walk-forward OOS validation of current defaults
just sweep KNOB --values v1,v2,v3                # 1-D knob sweep
just sweep KNOB --values v1,v2 --vs OTHER --vs-values v3,v4  # 2-D sweep
just analyze                                     # automated rule proposer
just analyze --tickers TSLL --top 5              # focused analyzer run
just test                                        # today's live recommendation (uses same code path)
just run                                         # Streamlit dashboard
```

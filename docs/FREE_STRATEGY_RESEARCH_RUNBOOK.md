# Free Strategy Research Runbook — Cold Start

**Purpose:** One page so any `trader` session can resume the **research lab** without re-reading `GOAL.md` + `simulator/CLOSED_LOOP_STRATEGY_FINDER.md` + `NORTH_STAR_HANDOFF.md` from scratch.

**Audience:** Hermes `trader` profile / Ken  
**Repo:** `/Users/jarvis/dev/tsla-tsll-options-tracker`  
**Status:** Operator runbook (docs). Model path remains **shadow / lab only**.  
**Related plan concepts:** Trader platform two-pillar split (Income Engine production vs Free Strategy Research lab) — see kanban `t_dea619b7` / `TRADER_PLATFORM_PLAN.md` if present in workspace; concepts restated below.

---

## 0. Mission in one paragraph

Continuously **generate candidates** for better short-premium entry/management policy (and later multi-structure templates) while **production stays frozen** until the real-data firewall accepts a ship. “Free” means unconstrained exploration capacity (many candidates, synthetic densification, multi-template experiments) that stays **free of production authority**. It is not free money and not unvalidated live trading.

Capital order never changes: **protect capital first → asymmetric opportunity second → audit trail always clear.**

---

## 1. Production vs lab boundary (hard)

| Sleeve | Job | Authority |
|--------|-----|-----------|
| **Income Engine (production)** | Real dollars: short-premium v1.14 rules + PMCC core/income sleeves | Live recs, manage/monitor, proposed tickets only (no auto-broker) |
| **Free Strategy Research (lab)** | Propose / stress / score candidates | Shadow tables, scoreboard, optional flags **default OFF** |

| Boundary | Rule |
|----------|------|
| Validation firewall | Real **5y** + **12-regime `just scenarios`** + **walk-forward OOS** + **cost function**; **synthetic never ships alone** |
| Production flags | `enable_model_entry` / `enable_model_management` stay **False** until explicit ship decision |
| Shipped form | Prefer small **interpretable** `ADAPTIVE_RULES` / exit hooks; no black-box forward pass as the live rule |
| Private state | Never git: `positions.yaml`, `pmcc_positions.yaml`, `.cache/`, Hermes secrets, broker creds, Telegram tokens |
| Execution | Analysis / proposed orders only until Ken gives an explicit mandate + hard risk limits |
| PMCC | Keep PMCC sims/playbooks in the **production** income path; do **not** force short-premium model machinery onto PMCC without a separate firewall design |

**Production baseline (document, do not casually rewrite):** short-premium stack in `STRATEGY.md` (v1.14: fixed policy + 6 adaptive rules, mostly TSLL). PMCC managed preset + core vs income sleeve in `pmcc-strategy` skill / repo PMCC docs.

---

## 2. Cold-start checklist (first 10 minutes)

From repo root:

```bash
cd /Users/jarvis/dev/tsla-tsll-options-tracker
just setup                    # if venv missing
# Model lab needs LightGBM (not always in requirements.txt — install if missing):
.venv/bin/python -c "import lightgbm" 2>/dev/null || .venv/bin/pip install lightgbm
just lab-smoke                # model-verify + scenarios (or run the two commands below)
# Equivalent:
#   just model-verify
#   just scenarios
```

**Pass criteria for lab smoke**

1. `just model-verify` — feature parity / model load smoke (`simulator/verify_model_features.py`) exits 0.  
2. `just scenarios` — production **rule** path green on the 12-regime suite (sacred gate; never skip after strategy edits).

If `model-verify` fails on missing models under `.cache/models/`, you can still run **Path A (rules)** fully. Model Path B needs trained artifacts or a regenerate/train cycle (see §4–5).

**Read order if deeper context needed (only if stuck):**

1. This runbook  
2. `GOAL.md` — cost function, critic loop, non-goals  
3. `STRATEGY.md` — “How to add an adaptive rule” + active rule table  
4. `simulator/CLOSED_LOOP_STRATEGY_FINDER.md` — full loop design  
5. `NORTH_STAR_HANDOFF.md` — model/sim session state + next levers  
6. `simulator/NORTH_STAR.md` / `simulator/PLAN.md` — long vision / PoC status  

---

## 3. Cost function & ship bar (non-negotiable)

From `GOAL.md` (always re-check there if numbers change):

- **Score:** `total_pnl_per_contract − dd_weight × max_dd_per_contract` (default `dd_weight = 1.0` — tail bias).  
- **No catastrophe regression:** no suite regime below threshold (default **−$500**/contract).  
- **OOS:** walk-forward static must not degrade aggregate OOS.  
- **Ship policy:** triple-win on 5y + suite + OOS **or** net-positive on ≥1 surface with others null-within-noise and **zero DD regression**.  
- **Stand-aside is success.** Prefer **NULL** over optimistic ship.  
- **One hypothesis at a time.** Multi-testing: BH-FDR when scanning many slices (`just analyze --scan-narrow` / `--pairs`).

---

## 4. Weekly research loop (target cadence)

```
1. Characterize / generate   → densify weak regimes (synthetic)
2. Label                     → entry × management (+ regret vs oracle)
3. Train / analyze           → should_trade + policy models  OR  just analyze on real trades
4. Propose                   → rule sketch  OR  model policy delta (shadow)
5. Validate on REAL only     → 5y + 12 regimes + OOS + cost function
6. Decision                  → SHIP | NULL | NEEDS MORE DATA
7. Scoreboard                → append wins / nulls / rejected catastrophe
8. Never auto-enable         → production flags stay off without human ship step
```

### 4.1 Path A — Distill to rules (preferred for production)

Proven path (v1.13–v1.14 fleet). Full procedure: `STRATEGY.md` → “How to add an adaptive rule”.

```bash
# 1) Produce / refresh trade log + features (via backtest path used by analyze)
just backtest
# Optional dump if your local analyze workflow needs it:
# just backtest -- --dump-trades   # only if run_backtest supports it in this checkout

# 2) Propose candidates
just analyze
just analyze --tickers TSLL --top 5
just analyze --tickers TSLA TSLL --scan-narrow --pairs --alpha 0.10

# 3) Implement rule in strategies.py (≤30 lines) + register in ADAPTIVE_RULES
# 4) A/B gauntlet (real data only)
.venv/bin/python validate_rule.py --ticker TSLL --rule <rule_name>
.venv/bin/python validate_rule.py --ticker TSLA --rule <rule_name>

# 5) Full suite after any ship candidate still under consideration
just scenarios
just optimize -- --static          # walk-forward static OOS of defaults

# 6) SHIP only if policy met: enable in DEFAULT_CONFIG_BY_TICKER adaptive_rules
#    Update STRATEGY.md (version line, table, history). Do not enable model flags.
```

**Path A promotion checklist**

- [ ] Hypothesis from analyzer / model SHAP / human — single, interpretable  
- [ ] Rule pure function on `(row, cfg, current)` (or exit hook contract)  
- [ ] `validate_rule.py` verdict: TRIPLE-WIN / acceptable MIXED per cost policy  
- [ ] No catastrophe ⚠ on suite  
- [ ] `just scenarios` green after enable  
- [ ] STRATEGY.md + history updated; scoreboard row logged  
- [ ] Registered-but-disabled nulls kept so analyzer does not re-propose  

### 4.2 Path B — Hybrid model (shadow until proven)

North-star path. Flags stay off. Use for denser supervision and **distillation** into Path A.

```bash
# Smoke
just model-verify

# Generate focused synthetic paths (defaults bake in known weak foci)
just model-generate
# Extra args example:
# just model-generate -- --high-vol 80
# Raw: .venv/bin/python simulator/generate_scenarios.py --per-regime 100 \
#        --focus high_gamma_marginal,v_recovery,post_earnings_weak

# Label + enrich training set (pass paths / filters explicitly)
just model-train-focus -- --scenarios .cache/<scenarios>.parquet --low-regret-filter 25
# Or full builder:
# .venv/bin/python simulator/build_training_set.py --paths 400 --length 20

# Optional: merge real backtest trades into synthetic parquet
just model-join-real .cache/training_set_synth.parquet .cache/training_set_merged.parquet

# Train should_trade + best_policy (writes under .cache/models/)
just model-train -- --input .cache/training_set_merged.parquet

# Validate model policy on real history (not synthetic metrics)
just model-validate
just model-validate -- --ticker TSLA --period 2y
just model-scenarios                 # model on canonical windows
just scenarios                       # rules baseline still sacred

# Live/shadow inspect (no production authority)
.venv/bin/python simulator/pick_entry_model.py
just test                            # rule path today; dashboard may show model pane read-only
```

**Path B promotion checklist**

- [ ] Training used regret/oracle hygiene; note row counts + % zero-regret  
- [ ] Feature alignment via `feature_utils` / `just model-verify` green  
- [ ] `validate_model_policy.py` shows non-zero useful trades **and** cost ≥ policy vs rules  
- [ ] Prefer **distill** winning slices to `ADAPTIVE_RULES` (Path A) over flipping `enable_model_*`  
- [ ] If considering flag enable: full gauntlet + docs + scoreboard; **human decision only**  
- [ ] Never ship on synthetic P/L alone  

Optional helpers (Python, not always wrapped in just):

```bash
.venv/bin/python simulator/characterize.py
.venv/bin/python simulator/distill_rule_sketches.py
.venv/bin/python simulator/sweep_model_gates.py
.venv/bin/python simulator/validate_generator.py
```

---

## 5. Exact command inventory (lab-relevant)

### 5.1 Just recipes (current)

| Command | Role |
|---------|------|
| `just setup` | Venv + deps |
| `just lab-smoke` | Lab one-command smoke: `model-verify` then `scenarios` |
| `just model-verify` | Feature parity / model load smoke |
| `just model-generate *ARGS` | Focused synthetic scenario generation |
| `just model-train-focus *ARGS` | `build_training_set.py` label/enrich |
| `just model-join-real SYNTHETIC OUTPUT` | Merge real trades into training parquet |
| `just model-train *ARGS` | Train should_trade + best_policy |
| `just model-validate *ARGS` | Model policy vs rules on real history |
| `just model-scenarios *ARGS` | Model on canonical 12 windows |
| `just analyze *ARGS` | Rule proposer (quartiles, narrow, pairs + FDR) |
| `just backtest *ARGS` | 5y baseline both tickers |
| `just scenarios *ARGS` | 12-regime stress (required pre/post strategy change) |
| `just scenarios-discover` | Re-curate canonical windows (rare) |
| `just optimize *ARGS` | Walk-forward search / `--static` validation |
| `just sweep *ARGS` | Knob sweep harness |
| `just bakeoff *ARGS` | Archetype bake-off |
| `just test` | Today’s **production** live recommendation |
| `just run` | Streamlit dashboard |
| `just positions *ARGS` | Open short-premium book (`positions.yaml`) |

PMCC production commands (`just pmcc-*`) are **Income Engine**, not this lab’s closed loop. Use them for desk work; do not treat PMCC path-sim as substitute for short-premium rule gauntlet.

### 5.2 Core Python modules (lab)

| Module | Role |
|--------|------|
| `analyze.py` | Critic / rule sketches |
| `validate_rule.py` | A/B rule gauntlet (5y + suite + OOS) |
| `strategies.py` | `ADAPTIVE_RULES`, hooks, defaults |
| `simulator/generate_scenarios.py` | Synthetic paths |
| `simulator/trade_labeler.py` | Entry × management + oracle regret |
| `simulator/build_training_set.py` | Training parquet |
| `simulator/join_real_trades.py` | Real + synth merge |
| `simulator/train_should_trade_model.py` | Gate model |
| `simulator/train_best_policy_model.py` | Policy model |
| `simulator/pick_entry_model.py` | Model recommender |
| `simulator/validate_model_policy.py` | Model gauntlet |
| `simulator/verify_model_features.py` | Lab smoke |
| `simulator/feature_utils.py` | Train/infer feature SoT |
| `simulator/distill_rule_sketches.py` | Model → rule sketches |

### 5.3 Typical data locations (gitignored)

| Path | Contents |
|------|----------|
| `.cache/*.parquet` | Scenarios, training sets, chain caches |
| `.cache/models/*.txt` | LightGBM model dumps |
| `positions.yaml` / `pmcc_positions.yaml` | Live books — never commit |

---

## 6. Scoreboard (institutional memory)

Append every lab round (win **or** null) to **`docs/RESEARCH_SCOREBOARD.md`** (R0/R3 freeze + append-only log). **STRATEGY.md history** remains the narrative production scoreboard. Lab log row format (also used in RESEARCH_SCOREBOARD):

```text
| Date | Path | Ticker | Candidate | Surfaces (5y/suite/OOS/DD) | Verdict | Notes |
| 2026-06-05 | A | TSLL | ride_high_credit_mgmt | + / 0 / 0 / flat | SHIP | model distill |
| 2026-06-05 | A | TSLA | tight_risk_high_gamma | … | NULL | registered, not enabled |
```

Rules:

- Nulls are first-class (prevent re-proposal).  
- Do not re-run known nulls without new data/feature justification.  
- Catastrophe rejects get a row too.

---

## 7. Explicit non-goals

1. **No auto-ship** — no cron or agent flips production flags or merges rules without a human ship step.  
2. **Synthetic never ships alone** — densify + stress only; ship metrics are real-history only.  
3. **No black-box production rules** — model may propose; shipped logic stays small explicit functions (unless Ken later mandates a gated hybrid after full gauntlet).  
4. **No mocked historical walk-forward data.**  
5. **No casual LEAPS/PMCC research coupling** — separate firewall before any capital.  
6. **No broker login / order submit** from research loops.  
7. **No multi-ticker expansion** as a substitute for finishing TSLA/TSLL desk + always-on.  
8. **No “improve headline P/L at any DD cost”** — cost function is tail-first.

---

## 8. Decision matrix (end of a lab session)

| Outcome | Action |
|---------|--------|
| TRIPLE-WIN rule | Ship: enable in ticker config → `just scenarios` → STRATEGY.md → scoreboard |
| MIXED / weak | Prefer NULL; document; leave registered-off if useful |
| Catastrophe ⚠ | Reject; do not enable; document regime |
| Model improves shadow only | Keep flags off; distill or iterate data |
| Model clean null | Document; improve labels/focus; do not force enable |
| Smoke red | Fix env/models before any promotion talk |

---

## 9. Document map (cross-links)

| Doc | Use when |
|-----|----------|
| **This file** `docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md` | Cold start / weekly ops |
| [`GOAL.md`](../GOAL.md) | Destination, cost function, M1–M8, non-goals |
| [`STRATEGY.md`](../STRATEGY.md) | Live rules, how to add a rule, baselines, history |
| [`ENGINE.md`](../ENGINE.md) | Harness semantics |
| [`docs/RESEARCH_SCOREBOARD.md`](RESEARCH_SCOREBOARD.md) | Frozen baselines + append-only lab SHIP/NULL log |
| [`simulator/CLOSED_LOOP_STRATEGY_FINDER.md`](../simulator/CLOSED_LOOP_STRATEGY_FINDER.md) | Full closed-loop design + phases |
| [`NORTH_STAR_HANDOFF.md`](../NORTH_STAR_HANDOFF.md) | Model/sim handoff + next levers |
| [`simulator/NORTH_STAR.md`](../simulator/NORTH_STAR.md) | 5-layer long-term vision |
| [`simulator/PLAN.md`](../simulator/PLAN.md) | PoC status |
| [`simulator/OPTIONS_MODEL_DESIGN.md`](../simulator/OPTIONS_MODEL_DESIGN.md) | Hybrid integration design |
| [`simulator/MODEL_TRAINING_PLAYBOOK.md`](../simulator/MODEL_TRAINING_PLAYBOOK.md) | Training decisions |
| [`CLAUDE.md`](../CLAUDE.md) | Project hygiene (scenarios before/after changes) |
| [`docs/TRADER_KNOWLEDGE_MAP.md`](TRADER_KNOWLEDGE_MAP.md) | Where learnings live (memory vs skill vs repo) |
| [`docs/TRADER_AGENT_PROFILE.md`](TRADER_AGENT_PROFILE.md) | `trader` profile ops |
| Platform plan concepts | Two pillars, R0–R6 lab stages, weekly loop, Path A/B — restated in §§0–1,4; full plan from task `t_dea619b7` |

---

## 10. Lab stages (from platform plan — research sleeve)

| Stage | Deliverable | Operator note |
|-------|-------------|----------------|
| **R0** Freeze production | v1.14 + PMCC managed as baseline | Re-run `just scenarios` / `just backtest` when freezing numbers |
| **R1** One-command lab smoke | `just lab-smoke` | Requires lightgbm for model half |
| **R2** This runbook | Cold-start single doc | You are here |
| **R3** Scoreboard file | Append-only proposals/nulls | `docs/RESEARCH_SCOREBOARD.md` |
| **R4** Shadow recommender | Side-by-side vs production | No live authority |
| **R5** First post-baseline ship | Only if triple-win | Prefer rules |
| **R6** New templates later | Labeler + firewall first | No capital without design |

---

## 11. Quick “resume tomorrow” card

```text
Repo: tsla-tsll-options-tracker
Lab smoke: just lab-smoke   # or just model-verify && just scenarios
Prefer Path A: analyze → rule ≤30 lines → validate_rule.py → scenarios → ship/null
Path B: model-generate → train-focus → train → model-validate (flags OFF)
Ship bar: cost function + no catastrophe; synthetic never alone
Docs: docs/FREE_STRATEGY_RESEARCH_RUNBOOK.md → GOAL.md → STRATEGY.md
```

---

*Runbook created for kanban task t_219adad0 (parent platform plan t_dea619b7). Update this file when just recipes or promotion policy change; leave dated narrative in STRATEGY/GOAL history.*

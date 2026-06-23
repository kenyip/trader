# Simulator + Policy North Star — Full Vision

**Date**: 2026-05-14 (initial)  
**Status**: Living document — will be updated as we learn and as PoCs complete.

---

## The North Star (User's Intent)

Build a system where, at any moment in time, given all available inputs (price action, momentum, direction, volume, IV dynamics, greeks at decision time, calendar events, regime state, etc.), a **model can derive the optimal strategy** for that specific situation.

"Optimal strategy" here means:
- The best entry: side (put/call), size, DTE, strike/delta, min credit floor.
- The best exit + management policy: profit target, daily capture multiplier, max loss tolerance, delta breach level, roll rules (when and how to roll, how many times, to what parameters).
- Or "stand aside / do nothing".

The goal is to know, across **almost all plausible situations** (including rare tails and combinations never seen in the exact historical record), how any given trade would perform and the best way to manage it with minimal loss.

This gives a genuine, data-driven edge: the system has "seen" the response surface of the market far more densely than any human or simple rule set can.

---

## How the Simulator Engine Fits the North Star

The Simulator is not just "more data for training".

It is the mechanism that lets us:
1. **Densify the state space** — Generate representative 4h paths for regimes, earnings, vol environments, gap clusters, etc. that are rare or absent in the real 5y tape.
2. **Create perfect counterfactual labels** — For every generated state, evaluate dozens of entry parameterizations + multiple exit/roll management policies and record which one performed best on that specific path (including path-dependent roll decisions).
3. **Stress test policies** — Run candidate policies (human rules or model-derived) on thousands of synthetic versions of extreme regimes and see failure modes before they happen live.
4. **Support "beating the game" exploration** — Because we control the generator, we can ask "what if" questions at scale (what if gaps are 20% worse? what if earnings jumps are asymmetric in a new way? what if vol clustering is stronger?).

The generator must be **algorithmic and representative** (calibrated and continuously validated against real historical statistics), not a black-box GAN that could hallucinate unrealistic dynamics.

---

## Full Architecture Vision (North Star)

```
Real Historical Data (daily + 4h where available)
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Market + Trade Simulator Engine (on-demand, 4h resolution) │
│  - Regime-conditional stochastic vol + jumps + events       │
│  - Earnings reaction module (learned distributions)         │
│  - Gap + intraday move generator                            │
│  - Volume correlation                                       │
│  - Continuous calibration against characterize.py targets   │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Trade Labeling Engine                                      │
│  - At any point on any path, enumerate entry candidates     │
│    (side × DTE × delta grid or smarter proposals)           │
│  - For each, simulate full life + multiple exit/roll policies│
│  - Record rich outcome vector (final P/L, MAE, best mgmt,   │
│    probability of roll needed, etc.)                        │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Policy Model (the "derives the strategy" part)             │
│  - Input: live features + peek greeks + candidate actions   │
│  - Output: recommended (side, DTE, delta, credit_floor,     │
│            exit_overrides, roll_policy) + confidence/edge   │
│  - Can be a gradient-boosted model, small NN, or hybrid     │
│  - Distillable to interpretable rules for audit             │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
Live Recommendation (unified with current live.py path)
          │
          ▼
Validation Firewall (never bypassed)
- Real 5y backtest + 12-regime suite + walk-forward OOS
- Cost function (P/L − heavy DD weight) + catastrophe gates
- Synthetic stress suite (optional but powerful)
```

---

## Evolution Path (How We Get There Without Big Bang)

**Current (v1.13 engine)**: Fixed policy + hand + analyzer-proposed skip rules.

**Phase 1 (now — PoC1)**: Simulator foundation
- Representative 4h generator calibrated on top inputs (gaps, short returns, vol, earnings).
- Characterization harness (`characterize.py`) as permanent spec.

**Phase 2 (PoC2)**: Rich labeling + counterfactuals
- Trade labeler that can say "in this state, entry X + management Y was best on this path".
- First large synthetic + real training datasets.

**Phase 3 (PoC3)**: Policy model prototype
- Model that scores or directly proposes full entry + exit/roll plan.
- Shadow mode in live system.
- First model-derived policies that beat v1.13 on real gauntlet.

**Phase 4+ (North Star iterations)**:
- Higher fidelity generator (better IV dynamics, skew awareness, more event types).
- Expanded action space (different trade templates: strangles, calendars, defined-risk, etc.).
- Hierarchical policy (first choose template, then parameters + management).
- On-demand generation API + continuous recalibration loop.
- "What-if" studio for human + model exploration.
- Eventually: the model becomes the primary way new adaptive rules or even entirely new strategy shapes are proposed.

---

## Key Technical Decisions Already Made (Toward North Star)

- 4-hour bars as base resolution (good compromise between daily simplicity and intraday fidelity for short-DTE + gap/reversal modeling).
- Representative / algorithmic generation (not pure learned generative model initially) — easier to validate and debug.
- Strong validation firewall: synthetic data for training, exploration, and stress testing; real historical data + existing gauntlet for all shipping decisions.
- Reuse as much as possible: `data.add_features`, `pricing.peek_position`, `backtest.Position` + `check_exits`, the 12-regime suite, `validate_rule.py`, cost function.
- Per-ticker specialization remains first-class (TSLA vs TSLL have very different statistics — generator and policy must respect this).

---

## Open Questions (to be resolved in later phases)

- How sophisticated does the pricing inside the labeler need to become? (Pure BSM vs local vol / stochastic vol pricing for more accurate greeks on generated paths.)
- When do we introduce multiple trade templates (single-leg vs spreads vs calendars)?
- How do we handle "best management" labeling when the optimal exit/roll policy may be path-dependent and non-myopic?
- What is the right interface for the policy model to output "roll logic" (currently the engine has limited roll support)?
- How much human-interpretable distillation do we still require as the policy becomes more powerful?

These will be answered after we have working PoC1–PoC3 and real data on what the model actually learns.

---

## Relationship to Existing Project Documents

- This simulator + policy work directly fulfills **GOAL.md M6** (model-proposed rules) and the stretch goal of a trained model proposer.
- It evolves the "LLM-critic loop" into a "data + model-critic loop" while preserving the deterministic validation gate.
- The cost function ("manage extreme moves, accept calm-case opportunity cost") remains the non-negotiable north star for everything we ship.
- All changes to the strategy layer will still require `just scenarios` + real-data validation before adoption.

---

## Living Document

This file will be updated after every major PoC or when the north star vision is refined based on what we learn from the data and the models.

Next update expected after PoC1 (first generator) completes and we see what the characterization comparison tells us.

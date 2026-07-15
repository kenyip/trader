# Trader Layered Edge Doctrine

Pinned 2026-07-15 from Ken/Jarvis first-principles review.

This doctrine makes Trader reason from market advantage layers instead of searching for named option recipes. A named option structure is not a strategy. A strategy is a falsifiable forecast expressed through a payoff shape, in a regime, with bounded risk and evidence appropriate to the claim.

## Core rule

```text
Do not search for "an options strategy."

Search for a repeatable market forecast that can be expressed through a defined-risk option payoff, works only in named regimes, has explicit entry/exit/risk rules, and can be falsified before it reaches paper or live.
```

Options are the preferred Trader research surface over stock-only exposure because they expose more control knobs: direction, time, volatility, skew, convexity, leverage, and defined maximum loss. Those knobs are only useful when they express a validated forecast. Options do not create edge by themselves.

## Layered Edge Stack

Every trade-shaped BUILD candidate must carry this stack in its strategy decision charter, executor report, challenger critique, and finalizer judgment.

| Layer | Required question | Examples / notes |
|---|---|---|
| 1. Market / underlying | Why this market, symbol set, or index? | Liquidity, options chain depth, spread cost, borrow/dividend/assignment risk, event calendar, sufficient history. |
| 2. Forecast type | What exactly can Trader predict? | Direction up/down, non-collapse, range, realized-vs-implied volatility, timing, skew, convexity, cross-sectional relative strength. |
| 3. Economic mechanism | Why should the forecast be repeatable after costs? | Behavioral overreaction, structural hedging flow, volatility risk premium, post-event drift, underreaction, risk-transfer premium. |
| 4. Option structure | Which payoff shape monetizes that forecast? | Put credit spread, call debit spread, diagonal, calendar, iron condor, butterfly, stock/option hybrid. |
| 5. Greek exposures | What is being bought or sold? | Delta, theta, vega, gamma, skew, term structure; name the intended exposure and the dangerous unintended one. |
| 6. Regime envelope | When should this work and when must it stand aside? | Trend/vol/stress/liquidity/catalyst filters; explicit invalid regimes. |
| 7. Entry trigger | What observable, lag-safe condition opens the trade? | Completed-bar signal, event date, vol threshold, support/level, relative spread; no lookahead. |
| 8. Exit / management | How is edge harvested or risk cut? | Profit target, thesis invalidation, max-loss stop, time stop, roll rule, event exit, stand-aside. |
| 9. Risk / capital fit | What is the bounded loss and sleeve allocation? | `capital_fit_usd`, one-lot `max_loss_usd`, `max_lots`, portfolio overlap, drawdown budget, kill switch. |
| 10. Evidence / falsifier | What would prove, narrow, or kill it? | Discovery/train, untouched holdout, regime/cost stress, negative controls, paper behavior, observed fills. |
| 11. Confidence stage | What is it allowed to do now? | F0/F1/F2/F3/F4 and L0/L1/L2/L3/L4. Research progress is not live permission. |

If any layer is missing, the candidate may be researched but cannot be called strategy advancement.

## Required candidate schema

A BUILD wake may explore a population, but its chosen decision candidate must be summarized in this shape before acting and reconciled after acting:

```yaml
candidate_id:
structure_family:
forecast_type: direction_up | direction_down | non_collapse | range_bound | realized_vs_implied_vol | timing | skew | convexity | relative_value
underlying_universe:
economic_mechanism:
regime_hypothesis:
entry_trigger:
exit_rule:
management_rule:
greek_exposures:
  intended:
  dangerous_unintended:
capital_fit:
  sleeve_usd: 3000
  one_lot_max_loss_usd:
  max_lots:
  portfolio_overlap_rule:
mispricing_claim:
predeclared_falsifier:
evidence_stage: F0_MECHANISM | F1_TRAIN | F2_UNTOUCHED_HOLDOUT | F3_ROBUST_PAPER_PLAN | F4_OBSERVED_PAPER
bar_claimed: discovery | capital_seat | paper | shadow | live_arm_packet
stand_aside_rule:
```

## Preferred initial exploration lanes

These lanes match Ken's desired income + long-bias prior for a small defined-risk sleeve. They are preferences, not an allowlist. Trader may supersede them only by naming a better economic mechanism and completing the Layered Edge Stack.

| Lane | Forecast | Default structure | Why it fits |
|---|---|---|---|
| Long-biased theta income | Underlying will not fall too much before expiry | Bull put / put credit spread | Income plus bullish/neutral exposure with defined risk. |
| Directional swing convexity | Underlying rises enough inside the holding window | Call debit spread | Bounded-loss participation in price swings without raw long-call decay overload. |
| Long-biased diagonal income | Mild bullish path with uncertain timing and harvestable front-month decay | Bullish diagonal | Blends direction and time decay, but requires stronger Greek/regime discipline. |

Naked/undefined-risk selling is off the capital path for the $3,000 sleeve unless worst-case loss is otherwise explicitly bounded and Ken separately approves the risk envelope.

## Challenger and finalizer gate

`STRATEGY_ADVANCED` requires all of the following:

1. A complete Layered Edge Stack.
2. Forecast type and option structure are aligned.
3. Evidence matches the claimed stage and bar.
4. Risk is defined and fits the sleeve for any capital-path claim.
5. Regime and stand-aside rules are explicit.
6. The falsifier was predeclared and actually tested or honestly reached `EVIDENCE_WAIT`.

Reject or narrow the claim when the report is just tooling, plumbing, coverage, vague "promising" language, or option-structure enthusiasm without a repeatable forecast.

## Confidence ladder

| Stage | Meaning | Allowed action |
|---|---|---|
| F0 | Mechanism hypothesized | Research only. |
| F1 | Train evidence positive under discovery bar | More simulation / robustness. |
| F2 | Untouched holdout survives | Robust paper-plan design. |
| F3 | Robust paper plan exists | Paper candidate, no live. |
| F4 | Observed paper behavior collected | Shadow proposal candidate. |
| L1 | Capital-seat bar clears | Still no live; paper path only. |
| L2 | Multi-session paper B6 | Shadow proposal only. |
| L3 | Shadow B7 | Live arm packet candidate. |
| L4 | Funded + Ken explicitly arms | First real 1-lot inside risk governor. |

Confidence is evidence-stage permission, not model confidence. Stand-aside remains success when any required layer fails.

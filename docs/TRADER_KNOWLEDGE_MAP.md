# Trader Knowledge Map

This file keeps the `trader` Hermes profile useful without bloating its memory. It answers: what belongs in memory, what belongs in skills, what belongs in the repo, and where the last few weeks of PMCC learnings live.

## Rule: memory is routing, skills/repo are substance

Use profile memory only for compact facts that should load every session:

- profile command/path/cwd
- private-state boundaries
- high-level PMCC stance and comparison standards
- where detailed knowledge lives
- persistent user preferences that prevent repeated steering

Do not put these in memory:

- exact one-day chain quotes
- stale spot prices
- completed-session logs
- full playbooks
- detailed simulation tables
- individual fills that will change
- data that is already in `pmcc_positions.yaml`, the repo, or skill references

Put durable process and strategy rules in skills. Put dated analysis/playbooks and code-specific implementation details in the repo.

## Always-loaded compact memory should say only this kind of thing

- `trader` is the dedicated trading profile; cwd is this repo.
- Use `pmcc-strategy` + `trading-partner` for PMCC/trade work.
- Use fresh market data before trade conclusions.
- Compare in dollars, contracts, DTE, greeks, buying-power/collateral impact, and scenario stress paths.
- Keep `pmcc_positions.yaml`, `.cache/`, Hermes credentials, broker credentials, and Telegram tokens out of git.
- Detailed PMCC rules/playbooks live in skills and this repo; use this map before searching sessions.

## Skills: durable behavior

### `trading-partner`

Purpose: general trading-agent behavior and workflow.

It should contain:

- trade-analysis output checklist
- knowledge-routing policy
- private-state boundaries
- staged path to Mac Mini / Telegram / read-only broker access / later execution access
- requirement to fetch fresh data and label stale/after-hours/cached data
- requirement to challenge weak trades

It should not contain:

- every TSLA quote table
- every historical playbook
- fill-specific live position state

### `pmcc-strategy`

Purpose: PMCC-specific rules, validated simulations, commands, pitfalls, and references.

It should contain durable rules like:

- max-DTE LEAPS generally win; roll/refresh at 365 DTE unless deep/extreme ITM
- managed preset: 60 DTE / ~0.30 delta shorts; force-close ITM shorts at 14 DTE
- never let assignment forfeit LEAPS time value
- never casually reset LEAPS higher; original/lower strike is the premium-selling anchor
- use premium clock: TSLA floor/good/strong about `$10/$15/$20` per short per day; NVDA lower
- shares-vs-PMCC comparisons must include collateral/buying-power value
- PMCC analysis must show shares baseline, flat/chop, drop-recovery, bullish path, and fast-rip path
- for X/Twitter catalyst checks, use Hermes `x_search` toolset; `xurl` was blocked
- market-hours strict scans beat weekend/after-hours yfinance chains, which can be corrupted

## Repo: durable artifacts and dated analysis

Repo code/docs are the right place for detailed playbooks and scripts:

- `pmcc/positions.py` and `pmcc_manage.py`: live PMCC state, LEAPS-only state, premium clock, monitor output
- `pmcc/staged_entry.py`: dynamic TSLA staged short-entry plan for dashboard/desk
- `pmcc_income_sleeve_scan.py`: income-sleeve PMCC scanner for capped-rip acceptable sleeves
- `docs/TRADER_AGENT_PROFILE.md`: how to operate/migrate the dedicated profile
- `docs/PMCC_MONITOR_DEPLOYMENT.md`: always-on monitor, Telegram, cron, private transfer rules
- `scripts/bootstrap_trader_profile.sh`: canonical local/Mac profile repair/recreate path
- `scripts/bootstrap_pmcc_monitor.sh`: writes the local Hermes monitor script

## Key dated PMCC learnings from recent sessions

These belong in `pmcc-strategy` references or repo references, not memory.

### 2026-06-21: managed PMCC engine correction

What we learned:

- Old scoring was inverted because it held LEAPS to expiry and hit a theta cliff.
- Correct managed model rolls/refreshes LEAPS around 365 DTE, force-closes ITM shorts at 14 DTE, and can go naked when LEAPS are extreme ITM.
- 60 DTE / 0.30 delta shorts beat longer/lower-delta shorts in the updated sweep.
- No-foresight comparisons must always re-enter and run the same horizon.

Where it lives:

- `pmcc-strategy` main body
- `pmcc-strategy/references/leaps-dte-validation.md`
- `pmcc-strategy/references/roll-management.md`
- `pmcc_refresh_frequency.py`, `pmcc_roll_dte_sweep.py`, `pmcc_leaps_dte_fair.py`

### 2026-06-23/24: NVDA PMCC and target-premium framing

What we learned:

- NVDA is calmer and can have better yield-on-debit, but tighter caps.
- Existing NVDA Jun 2028 `$210` LEAPS at `$52.50` is acceptable.
- Evaluate NVDA shorts by target premium first: `$240C` ideal near `$2.35-$2.50`; `$235C` can substitute if income is urgent.
- Upside room means `short_strike / spot - 1`, not total PMCC return cap.

Where it lives:

- `pmcc-strategy` NVDA section
- `pmcc-strategy/references/nvda-pmcc-analysis-2026-06-23.md`
- `pmcc-strategy/references/nvda-target-premium-and-premium-clock-2026-06-24.md`

### 2026-06-25: margin-aware TSLA shares vs PMCC framing

What we learned:

- Do not compare naked shares vs capped PMCC as the main decision.
- Compare managed covered shares vs managed PMCCs under similar roll rules, then separately price the value of margin collateral.
- User has more than 300 TSLA shares; the 300-share sleeve is a strategy sleeve, not total TSLA exposure.
- PMCCs can beat managed covered shares before collateral value in tested paths, but shares remain valuable as marginable permanent exposure.
- A balanced end state is often better than all-or-nothing: shares for collateral/uncapped exposure plus PMCCs for capital-efficient income.

Where it lives:

- `pmcc-strategy` cross-ticker/share-conversion section
- `pmcc-strategy/references/tsla-300-share-sleeve-and-4-leaps-management-2026-06-25.md`
- dashboard/desk staged-entry logic

### 2026-06-25/26: X research and catalyst checks

What we learned:

- `x_search` is a Hermes toolset, not a skill.
- `x_search` worked for TSLA catalyst research; `xurl` was blocked by auth/credits.
- Future catalyst checks should use `hermes chat -t x_search` or the `x_search` tool when available.
- X-based catalyst notes must separate official facts from speculative chatter.

Where it lives:

- `pmcc-strategy/references/tsla-300-share-sleeve-and-4-leaps-management-2026-06-25.md`
- `trading-partner` knowledge routing

### 2026-06-28: 8-LEAPS partial coverage / trim buffer

What we learned:

- With many LEAPS and catalyst risk, do not default to fully covering every LEAPS.
- For 8 TSLA LEAPS, 6 shorts can be better than 8 because naked longs serve as trim/roll buffer.
- `$15/day/short` is a practical target, but not at the cost of over-capping a TSLA rip.
- If TSLA rips hard, trim a higher-basis/higher-strike LEAPS to fund roll tax and lock profit.

Where it lives:

- `pmcc-strategy/references/tsla-8-leaps-15day-rip-management-2026-06-28.md`
- `pmcc-strategy` short-call management section

### 2026-06-30: income sleeve and capped-rip framework

What we learned:

- Split core/rip sleeve from income/capped sleeve.
- For income sleeve, short strike is an intentional monetization/exit level, not just a temporary cap.
- Capped-rip survival formula:
  `spread_width + LEAPS time value + short credit - LEAPS basis`.
- Existing `$410` LEAPS with `$13k` basis need wider shorts than `$460C` to survive a conservative `$700` stress; Aug `$475/$480` are safer minimums, and Oct `$475/$480` improve cushion.
- Lower-strike `$380-$400` LEAPS are more robust for new income-sleeve entries than high-strike cheap LEAPS.
- Income sleeve should close both legs when profit target or loss floor is hit; do not roll-and-pray like the core sleeve.

Where it lives:

- `pmcc_income_sleeve_scan.py`
- `pmcc-strategy/references/tsla-income-sleeve-capped-rip-framework-2026-06-30.md`
- `pmcc-strategy/references/income-focused-capped-rip-underlying-selection-2026-06-30.md`

### 2026-06-30: rip reload ladder

What we learned:

- If TSLA is ripping and one wide short is only slightly red, do not close it just because it is red.
- If adding, ladder one new short above the existing strike; do not duplicate/crowd the same strike and do not jump to full coverage.
- Immediate workflow: record fill, run full scan in background, use snapshot/manage for near-term candidates.

Where it lives:

- `pmcc-strategy/references/tsla-rip-reload-ladder-2026-06-30.md`

### 2026-07-01/02: delivery beat, sell-the-news, and July 7 catalyst risk

What we learned:

- Pre-delivery playbooks were useful before the event, but after July 2 they became stale.
- Tesla Q2 2026 deliveries were a blowout beat, then TSLA still sold off about `-7.5%`.
- Correct post-event framing: blowout beat + sell-the-news/crowded positioning/macro washout, not a fundamental delivery miss.
- With all/most TSLA LEAPS uncovered and July 7 Lars/Cybercab catalyst still ahead, the default was not to aggressively sell depressed calls before July 7.
- Base plan after selloff: `0` shorts under `$400`; `1` starter short only on reclaim; `2` max before July 7 around `$405-$410+`; keep most LEAPS naked.

Where it lives:

- `references/tsla-delivery-day-conditional-playbook-2026-07-01.md`
- `references/tsla-pmcc-moa-brief-2026-07-02.md`
- should also be mirrored into `pmcc-strategy` references for the `trader` profile

### 2026-07-03: dedicated Trader profile

What we did:

- Created Hermes profile `trader`.
- Set `terminal.cwd` to this repo.
- Wrote trading-focused `SOUL.md`, compact profile memory, and profile-local `trading-partner` skill.
- Added `docs/TRADER_AGENT_PROFILE.md` and `scripts/bootstrap_trader_profile.sh`.
- Pushed profile/bootstrap docs to GitHub.

Where it lives:

- `docs/TRADER_AGENT_PROFILE.md`
- `scripts/bootstrap_trader_profile.sh`
- `trading-partner` skill
- compact profile memory

## When to use session search

Use `session_search` only when:

- the user asks what happened in a previous conversation
- a detail is missing from the skill/repo docs
- you need to recover reasoning that was intentionally not promoted to memory/skills
- a repo/skill reference says “see session” but does not contain the needed table

Promote anything repeatedly useful from session search into:

1. a skill rule, if it changes future agent behavior;
2. a repo reference, if it is a dated analysis/playbook;
3. compact memory, only if it is a stable routing fact or high-level preference.

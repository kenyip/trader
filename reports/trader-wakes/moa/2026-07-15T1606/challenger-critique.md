# MOA BUILD challenger critique — 2026-07-15T1606

ROLE: Grok 4.5 challenger (read-only judgment)
PHASE: BUILD / L0 discovery
SLEEVE_USD: 3000
PAPER_ONLY: true
SESSION: postclose
HARD STOPS HONORED: no evolve --apply; no broker; no arm; no commit/push; no RUN COMPLETE

## Overall disposition

**PASS with nits.** Accept executor outcome `STRATEGY_ADVANCED` for `MULTINAME_BREAKOUT_BULL_CALL_14D_V1` as a **discovery-bar F1→F2/L0** advance only. The one-shot holdout evidence, claim boundaries, capital honesty, and next-seed direction are sound. Finalizer must tighten a few labels and option-freeze constraints; none of the nits reverse the pooled F2 decision under the predeclared gate.

## Verified evidence (independent)

| Claim | Independent check | Result |
|---|---|---|
| Canonical cache exists | `.cache/platform/breakout_continuation_holdout_2026-07-15T1606.json` size 94859 | PASS |
| SHA | `dd30bee303b7e08dc5932f1bbd69177dcf26c63141b0b09a7aabd7a2baf40e7d` | PASS (matches durable summary) |
| Summary vs cache metrics | n=113; treated +2.2298%; control −1.4955%; excess +3.7254%; LB90 +1.8624%; gate true | PASS exact |
| Frozen train source | `.cache/platform/breakout_continuation_train_2026-07-15T1515.json` SHA `2ea7d7f2…` | PASS |
| Holdout was unread before open | frozen `untouched_holdout.outcome_metrics_read=false`, `simulation_run=false`, n_blueprints=113 | PASS |
| Population | 281 / 168 / 113; identity SHAs in summary | PASS as reported; identity repro is tool-tested |
| Option authority | `pricing_calls=0`; `l1_or_capital_seat=false`; `paper_or_higher=false` | PASS |
| Focused suite | `tests.test_breakout_continuation_holdout_lab` + train lab | **15/15 OK** re-run by challenger |
| Living leader / capital path | readiness + coverage | none / empty |
| Epoch status | `configs/search_epoch.json` `status=completed` with F2 result + do_not list | PASS as handoff state |
| Skill pitfall | profile `trader-self-evolution` downstream-holdout one-shot pitfall present | PASS |

Executor-claimed full suite 319/319 and overwrite guard were not re-run end-to-end by challenger beyond the focused 15; finalizer still owns full-suite + integration verification.

## Rubric

1. **Strategy charter — PASS.** Mechanism, family scope, funnel F1→F2, predeclared falsifier, and single closed outcome `STRATEGY_ADVANCED` are explicit in charter + closeout + compounding.
2. **Strategy vs operations — PASS.** One-shot holdout runner/tests are capability, but the dependent experiment was exercised in-wake to a strategy decision. Not capability-only.
3. **Goal progress — PASS.** Highest-information reserved holdout closed; genuine F2 discovery signal for a paper-testable path *if* option freeze later survives. Chance of a durable paper candidate improved vs F1-only.
4. **Creativity / independence — PASS.** Continuation of prior NEXT was justified by epoch success definition and one-shot evidence uniqueness; not a familiar PCS tunnel; no thrash of unchanged search.
5. **Claim validity — PASS with nits.** Only holdout prerequisites used. L0/discovery bar only. No L1/seat/paper/shadow/live claim. See nits on `f2_or_l1_claim` naming and heterogeneity overclaim risk.
6. **Evidence / test quality — PASS.** Real cache + summary + scripts/tests; behavioral/boundary/negative controls (tamper hash, changed identity, overwrite refusal, authority labels, non-positive LB gate in train suite). Observed vs proxy correctly: underlying adjusted-close, labeled 20 bps sensitivity, no option marks.
7. **Falsification — PASS.** Predeclared six-check pooled gate; failure would have been `FAMILY_CLOSED`. Concentration diagnostics mandatory non-gating; not post-hoc gate mutation.
8. **Capital honesty — PASS.** Living leader none; structural future `$100`/`max_lots=1` only; capital-seat bar not claimed; proxy/underlying cannot earn L1 stated repeatedly.
9. **Research freedom — PASS.** No false freeze from archive/observed-option blockage; holdout path was the right highest-info loop.
10. **ONE NEXT — PASS with tightening nits.** `BREAKOUT_F2_OPTION_PAYOFF_FREEZE` is correct direction; challenger tightens absolute-path and horizon constraints below. No live/shadow promotion.

## Accepted core judgment

- Pooled holdout **does** clear the frozen discovery bar: n113 ≥80, 8≥6 symbols, treated mean >0 after labeled 20 bps, paired excess >0, LB90 >0, integrity empty.
- Leave-one-symbol-out pooled LB90 all positive (≈+1.13% to +2.77%) — no single name is necessary for the pooled pass.
- Claim scope is correctly **underlying directional F2/L0**, not option payoff, not L1, not capital seat.
- Epoch completion + `do_not` rules correctly block: retune of frozen geometry, relabeling opened 113 as new untouched option holdout, option pricing before freeze-on-168.

## Material nits (finalizer must address or explicitly accept)

### N1 — `f2_or_l1_claim: true` is overloaded (label repair)

Holdout payload sets `"f2_or_l1_claim": advanced`. Elsewhere in the repo this flag is almost always `false` on non-L1 work and is read by humans as “claiming F2 **or** L1.” Combined with a true F2 advance, a hurried reader can blur L1.

**Required repair:** keep `authority.l1_or_capital_seat=false` (already true) and either:
- rename/split to `funnel_claim_f2=true` + `l1_claim=false`, or
- keep the field but assert in test + durable surfaces that F2 discovery ≠ L1, and never surface `f2_or_l1_claim` alone as seat evidence.

Not claim-invalidating for this wake because claim_scope/authority/bar_claimed already block L1.

### N2 — Heterogeneity and control-driven excess constrain the option freeze

Independent per-symbol holdout slices (from canonical cache concentration diagnostics):

| Symbol | n | treated | excess | LB90 |
|---|---:|---:|---:|---:|
| AMD | 16 | +7.73% | +9.45% | +3.60% |
| TSLA | 8 | +7.47% | +14.79% | +10.50% |
| GOOGL | 15 | +2.46% | +4.88% | +3.16% |
| AAPL | 14 | +1.21% | +3.27% | +2.14% |
| NVDA | 19 | +0.94% | +3.33% | +0.38% |
| MSFT | 9 | +0.89% | +0.88% | −1.53% |
| AMZN | 16 | **−0.46%** | +0.10% | **−2.79%** |
| META | 16 | **−0.24%** | **−2.52%** | **−6.18%** |

Chronological tertile 1 (2022-03-24→2023-10-25): treated **−0.06%**, excess +1.62%, LB90 **−1.48%**.
Tertiles 2–3: strong absolute treated and positive LB90.

Also: holdout **control mean ≈ −1.50%** (systematically negative). Paired excess is partly “controls lost,” not only “breakouts won.” Absolute treated gate still passed (+2.23%), which is necessary for a long call debit thesis — good — but bull-call payoff tracks **absolute** underlier path (and option path), not paired excess.

**Required freeze constraints (NEXT tightening):**
1. Option DNA freeze and primary dual-cost judgment on the **168 development rows only**.
2. Primary success metric = **absolute after-cost option PnL / path risk**, not underlying paired excess.
3. Report (non-gating or hard, but explicit) symbol and time concentration on option results; do not claim universal multi-name option edge from pooled underlying F2.
4. Do not “rescue” a weak absolute option path by pointing at underlying paired excess or control underperformance.
5. Prefer listing-available ATM/near ATM `$1` vertical construction that monetizes `direction_up`; if a name has no liquid strike grid in sim, fail closed for that name rather than inventing fills.

### N3 — Horizon alignment (10-session evidence vs 14-DTE package)

Evidence measures **fixed 10-session** underlying returns. Conditional structure is a **14-DTE** bull-call. Executor labels this as approximate pre-screen — correct.

**Required in NEXT:** hard management must match measured horizon (10-session time stop already proposed). Do not silently evaluate a full-to-expiry 14-session path as if it were the F2 outcome. If the freeze uses DTE=14, the primary exit for claim alignment is the predeclared 10-session stop / 50%-max harvest / invalidation below pre-breakout high — not hope-to-expiry.

### N4 — Tiny epoch_result float drift

`configs/search_epoch.json` `epoch_result.paired_excess_mean` ≈ `0.037253986…` vs canonical holdout / summary `0.037253613…` (same for LB90 at ~1e-7). Not decision-changing; finalizer should pin epoch_result to the canonical holdout summary fields exactly.

### N5 — Full-suite and integration still finalizer-owned

Challenger re-verified focused 15/15 and summary/SHA consistency. Executor’s 319/319, secret review, commit, main integration, and completion receipt remain **not done**. Partial phase only.

### N6 — Capability residue is good, not oversold

Accept as search information: one-shot holdout lab + tests + epoch do_not rewrite. Strategy progress remains the F2 stage move only.

## Rejected / not applicable findings

- **Reject “must FAMILY_CLOSE because META/AMZN weak.”** Concentration was predeclared non-gating; mutating the pooled gate after inspection would be post-hoc. Correct handling is F2 + narrowed claim + freeze constraints (N2).
- **Reject “no advance without option marks.”** Discovery bar + doctrine allow underlying F2 before option pricing; option is the next stage, not a retroactive F2 requirement.
- **Reject capital-seat or L1 promotion.** Not claimed; keep empty path.
- **Reject thrash / wrong loop.** One-shot holdout was the right loop.

## Layered Edge Stack completeness (challenger view)

| Field | Status |
|---|---|
| Market/underlying | Complete; survivorship labeled |
| Forecast | `direction_up` / 10 sessions — complete |
| Mechanism | Complete and falsifiable |
| Option structure | Conditional only; unpriced — honest for F2 |
| Greeks | Intended/dangerous labeled; unmeasured — honest |
| Regime / entry / stand-aside | Complete and lag-safe as described |
| Exit/management | Measured fixed 10s; managed option exits untested — honest |
| Risk/capital | Structural 100/100/1 — not observed debit |
| Evidence/falsifier | Complete for F2 discovery bar |
| Confidence | F2/L0 — accepted |

Structure monetizes stated forecast **if and when** priced; current wake does not pretend otherwise.

## Freedom / thrash audit

- No unnecessary freeze from observed-option archive limits.
- No TSLL PCS tunnel.
- Prior NEXT honored for good reason (reserved one-shot).
- Epoch success definition satisfied → completed status is appropriate, not premature seat talk.

## Strategy outcome (challenger)

- **Accept:** `STRATEGY_ADVANCED`, funnel `F1_TRAIN → F2_UNTOUCHED_HOLDOUT`, bar `discovery_bar_L0_only`, strategy advancement **true**.
- **Search information:** holdout integrity machinery + heterogeneity map + epoch close rules.
- **Not accepted as:** L1, capital seat, paper plan completion (F3), option edge, or live readiness.

## ONE merged NEXT (see also merged-next-seed.md)

`BREAKOUT_F2_OPTION_PAYOFF_FREEZE` — freeze **one** claim-aligned 14-DTE `$1`-wide bull-call debit specification **only on the original 168 development rows**: listed expiry/strike availability, entry next session after lag-safe breakout, management = 50%-of-max harvest / invalidate below pre-breakout 20s high / **hard 10-session stop** (aligned to F2 evidence), dual multi-leg costs (fixed-$ and %), no-same-bar reentry, one-lot max loss, path DD, density. Judge primarily on **absolute after-cost option PnL and path risk**, not underlying paired excess. Use opened 113 **only** as labeled secondary stress (never a new untouched option holdout). Reject unless development dual-cost non-vacuous positive edge with max loss ≤`$300` and window DD ≤`$75` (still L0 proxy; no L1/seat). Report symbol/time concentration; no universal-panel option claim. Fresh live-clock paper still required before F4. No paper/shadow/arm/live in the freeze wake unless filters and F3 plan separately authorize paper-only path later.

## Readiness NEXT

Current readiness NEXT already matches the seed; **no readiness NEXT rewrite required** beyond finalizer applying N1–N4 label/pin repairs if they touch living surfaces.

## Phase boundary

Challenger partial only. Sol finalizer repairs accepted nits, re-verifies, promotes learning, prepares integration. Deterministic gate alone may declare RUN COMPLETE.

MOA_CHALL_DONE

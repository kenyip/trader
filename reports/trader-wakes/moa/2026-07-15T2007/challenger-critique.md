# MOA challenger critique — 2026-07-15T2007

ROLE: Grok 4.5 / Trader critic (read-only judgment)
PHASE: BUILD / L0 research only
SLEEVE: $3,000
STATUS: PARTIAL critique phase only — no commit, push, merge, evolve --apply, broker, arm, or `RUN COMPLETE`

## Verdict

**PASS WITH NITS** — accept executor strategy outcome `FAMILY_CLOSED` at `F0_MECHANISM -> F0_MECHANISM` for exact `LOW_DOWNSIDE_SEMIVARIANCE_ETF_PCS_21D_V1`. Reject the executor's plain-HV continuation NEXT as the post-wake seed; after this wake the active epoch no-advance streak becomes two and doctrine requires a material mechanism/evidence pivot.

## Rubric

1. Strategy charter — **PASS**
   Economic mechanism (cross-sectional left-tail heterogeneity / downside-semivariance rank), family scope, funnel F0→F0, predeclared falsifier including mechanism-specificity, and exactly one closed outcome `FAMILY_CLOSED` are explicit in charter + closeout + payload.

2. Strategy vs operations — **PASS**
   New lab/tests are support, not the claimed progress. Outcome is a train disposition on the predeclared mechanism, not capability-only handoff.

3. Goal progress — **PASS**
   Useful search information: decisive falsification that absolute/relative/tail non-collapse can pass while a fancier left-tail feature still fails specificity against plain total HV. No false advancement; chance of a durable paper edge improved by quarantine and a cleaner failure mode.

4. Creativity and independence — **PASS WITH NIT**
   Accepted prior NEXT with justification (ETF population, direct barrier, date-block dependence, specificity). Not TSLA/TSLL tunnel. Nit: post-close NEXT proposes plain-HV barrier ranking on the same absolute-tail lane rather than the required two-no-advance pivot.

5. Claim validity — **PASS**
   No F1/F2/L1/capital seat/registry/paper/shadow/arm/live claim. Option stage `NOT_RUN_TRAIN_GATE_FAILED`, pricing_calls `0`, holdout outcomes unread, `l1_claim=false`, `funnel_claim_f2=false`.

6. Evidence and test quality — **PASS WITH NITS**
   Evidence path: `reports/trader-wakes/moa/2026-07-15T2007/downside-semivariance-etf-train.json`. Independent recompute from `train.rank_dates` (n=178) matches reported breach rates, edges, tails, same-symbol overlap, zero path-overlap integrity, and date-block LB90 (`0.03932584269662921`). Focused suite re-run green: `7/7 OK`. Tests include chronology/non-overlap, absolute-gate negative control, plain-HV specificity fail, overlap integrity, fixed-panel rejection, sealed holdout + capital stack.
   Nits: (a) dominant-failure prose in payload overstates a multi-gate stack failure when only `semivariance_edge_exceeds_plain_hv` failed; (b) closeout holdout end wording is slightly looser than identity (`last_rank_date=2019-11-13…2026-06-16`, exit through `2026-07-02`); (c) concentration is severe (low: SPY 83 / XLV 60; high: XLE 107) — labeled, not claim-rescuing.

7. Falsification — **PASS**
   Predeclared conjunctive gates; only specificity failed; holdout unspent; exact family quarantined from threshold/lookback/panel retune. Correct refusal to promote on absolute hazard alone.

8. Capital honesty — **PASS**
   Living leader remains none. Structural planned PCS only: `capital_fit_usd=200`, one-lot `max_loss_usd=200`, `max_lots=1`, one global bullish unit. Capital-seat bar not invoked. No stale leader resurrected.

9. Research freedom — **PASS**
   Observed-option archive blockage did not freeze valid underlying discovery. Multi-ETF panel chosen without instrument allowlist. No red-lane action.

10. ONE highest-information NEXT — **FAIL as written / REWRITE**
    Executor NEXT `LOW_TOTAL_HV_ETF_BARRIER_EXTERNAL_TRAIN_F0` correctly labels 2010–2019 plain-HV as inspected development and asks for an independent sample, but it is **not** a material pivot. Epoch context: `2026-07-15-tail-hazard-discovery`, prior completed wake `2026-07-15T1912` already `FAMILY_CLOSED` with no strategy advance; this wake is the second consecutive epoch no-advance. Doctrine: after two consecutive completed epoch wakes without `STRATEGY_ADVANCED`, the next wake must pivot to a materially different economic mechanism or evidence class. Plain total-HV absolute close-barrier ranking on the same ETF panel remains the same direct-tail rank lane and risks laundering the inspected comparator into a new family label.
    Merged ONE NEXT is rewritten below (also `merged-next-seed.md`).

## Accepted claims

- Exact family `noncollapse|cross_section_low_downside_semivariance_60d|liquid_etfs_spy_qqq_iwm_xlf_xle_xlk_xli_xlv|spy_sma100_uptrend_positive60d|10session_close_barrier5pct|pcs21d2wide_planned` is `FAMILY_CLOSED` at F0.
- Train n=178; low/high 5% close-barrier breach ≈4.4944% / 11.2360%; semivariance edge ≈+6.7416pp; date-block LB90 ≈+3.9326pp; low/high worst-decile min-close ≈−4.917% / −8.065%.
- Same-date plain-HV edge ≈+7.8652pp exceeds semivariance; rank overlap 134/178 low and 141/178 high.
- Holdout identity SHA-256 `72a6d18430031f03421d27a2680f53d42f099357a5c6685b1b3db2ce1a7dcd5d` remains unread; no option pricing.
- Search information yes; strategy advancement no.
- No living quality leader / L1 / capital seat.

## Rejected / narrowed claims

- Reject any implication that absolute hazard success nearly earned F1 — specificity was frozen and failed.
- Reject promoting or “almost promoting” plain-HV from the same inspected train partition.
- Reject executor NEXT as the integrated seed (pivot required).
- Reject any capital-path, paper-force, registry, shadow, arm, or live reading of this residue.

## Finalizer must repair / record

1. Rewrite durable NEXT to the merged pivot seed (not plain-HV barrier continuation).
2. Tighten dominant-failure wording to **mechanism non-specificity only** wherever it still lists the full gate stack as failed.
3. Update readiness decision block for stamp `2026-07-15T2007` (not NEXT-only patch if decision text still points at the now-closed semivariance seed as the live experiment).
4. Carry quarantine: semivariance family + nearby lookback/barrier/panel retunes; do not reopen closed low-HV mean-return or recent-downshock timer families; do not spend holdout `72a6d184…` on a different mechanism.
5. Note post-integration epoch counters: consecutive no-advance → 2; `strategy_pivot_required=true` for the next zero-input wake; third consecutive no-advance would force burst-stop reassessment.
6. Keep partial-phase boundaries until deterministic postflight.

## Independent checks performed

- Read: SOUL-relevant skill `trader-self-evolution`, `docs/BUILD_LAB_ENVIRONMENT.md`, `docs/INCOME_STRATEGY_COVERAGE.md`, meta/orientation/charter/closeout/exec wake, readiness LATEST + income-coverage LATEST, `configs/search_epoch.json`, train JSON, lab script, tests.
- Recomputed train metrics and approximate circular block bootstrap LB90 from persisted rank rows — match.
- Re-ran `python -m unittest tests.test_downside_semivariance_etf_barrier_train_lab -v` → `Ran 7 tests … OK`.
- Confirmed dirty run branch `trader/run-2026-07-15T2007` and no challenger commit/push.

## Disposition for finalizer

Accept strategy closeout. Accept evidence integrity at L0 for the closed claim. Rewrite NEXT to material pivot. Then finalizer verification, learning promotion, and integration as usual.

MOA_CHALL_DONE

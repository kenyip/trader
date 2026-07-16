# MOA executor closeout — 2026-07-16T0454

Role: GPT 5.6 Sol executor / only writer
Phase: BUILD / L0 official-source underlying discovery
Session: premarket
Status: EXECUTOR PARTIAL — challenger and finalizer pending; no commit/push/merge/RUN COMPLETE

## Strategy decision charter

The pre-outcome charter is preserved at `strategy-charter.md` in this directory.

Chosen loop: exercise one materially different official corporate-information mechanism and close exactly one named decision. This wake followed the active-epoch pivot requirement by leaving the closed market-price, scheduled-macro, cross-sectional, credit, and daily option-signal families untouched. The prior Form 4 NEXT was useful context rather than an order; it was selected because it introduced official point-in-time issuer filings and could be exercised to a real decision in-wake.

## Complete Layered Edge Stack

- Candidate: `SEC_FORM4_CLUSTERED_INSIDER_BUYING_CALL_21D_V1`.
- Family: `SEC_FORM4_CLUSTERED_OPEN_MARKET_BUYING_FORWARD_UPDRIFT`.
- Market / underlying: fixed present-day liquid US single-name panel `AAPL, MSFT, NVDA, AMZN, META/FB, GOOGL/GOOG, AMD, NFLX, TSLA, COIN, PLTR, SMCI, AVGO, MU, JPM, XOM, BAC, F, SOFI, AAL, PFE, SNAP, CCL`.
- Forecast: issuer-specific bullish ten-session drift after a public qualified cluster.
- Economic mechanism: multiple officers/directors spending their own capital on direct open-market common shares may convey issuer-specific valuation/operating information that diffuses after public filing.
- Structure: future conditional one-lot 18–24 DTE $2-wide bull-call debit spread, long near 0.55 delta and short $2 higher. No option was priced in this F0 run.
- Intended Greeks: positive delta, limited positive gamma/vega, defined debit.
- Dangerous exposures: negative theta, volatility crush, gap loss, capped upside, assignment/exercise and closing friction; all remain unmeasured at F0.
- Regime / evidence envelope: original timely Form 4; non-derivative code P; acquired A; direct D; officer/director; common-equity title; transaction value >=$10,000; two distinct owners and accessions within 20 calendar days; aggregate >=$100,000. Broad-market SMA100 state is controlled rather than post-hoc filtered.
- Entry / exit: signal is the first filing date that makes the cluster knowable; feature data ends strictly before filing; entry is first session close strictly after filing; F0 exits ten sessions later. Future option management is +50% spread value, -50% debit, or ten-session time stop; no roll or averaging.
- Risk: `capital_fit_usd=200`, planning frictionless structural `max_loss_usd=200` before debit/closing friction, `max_lots=1`; actual option debit/path loss is unmeasured; no same-symbol overlap and at most one risk unit.
- Evidence / falsifier: official SEC quarterly archives, frozen 60/40 chronology, prior-only same-symbol controls, 10-bps underlying hurdle, density/specificity/uncertainty/tail/integrity conjunction. Any gate failure closes the exact family.
- Confidence: F0/L0 before and after; no F1 because the full discovery conjunction failed.
- Stand aside: absent/ambiguous/late/amended/derivative/indirect filing, missing issuer or price mapping, no prior comparable control, illiquid future option, debit above $200, or any risk conflict.

## Frozen official-source design

New runner: `scripts/sec_form4_clustered_buying_train_lab.py`.

- Source: SEC Insider Transactions Data Sets, 48 official quarterly Form 3/4/5 ZIPs from `2014q1_form345.zip` through `2025q4_form345.zip`.
- Each ZIP is persisted under `.cache/platform/sec_form345/`, re-read before claim evaluation, SHA-256 cited, and parsed only for `SUBMISSION.tsv`, `REPORTINGOWNER.tsv`, and `NONDERIV_TRANS.tsv`.
- Amendments (`4/A`), derivatives, indirect ownership, non-purchase codes, disposed rows, preferred/units/depositary/restricted/phantom titles, non-officer/director accessions, nonfinite values, purchases below $10,000, and filings more than five calendar days after transaction fail closed.
- Cluster threshold is first-publicly-knowable two-owner/two-accession/$100,000 within 20 calendar days; subsequent signals within 20 days are suppressed.
- Distinct accessions are required so one joint filing cannot alone manufacture a two-insider cluster. The bulk schema still does not attribute every transaction row to one reporting owner, so this remains an L0 limitation.
- Signal features use the issuer and SPY session strictly before filing. Entry is the first issuer session strictly after filing, avoiding same-day acceptance-time ambiguity because the quarterly archive provides filing date but not acceptance timestamp.
- Controls are deterministic, prior-only, same-symbol, no-reuse, non-event, same SPY SMA100 state, and nearest 20-session issuer return within five percentage points; the control ten-session outcome must finish before the public event signal.
- The first 60% of price-complete signals is development train; the final 40% is identity-only and outcome-unread.

## Exact claim-bearing outcome

`FAMILY_CLOSED` for exact `SEC_FORM4_CLUSTERED_INSIDER_BUYING_CALL_21D_V1` / `SEC_FORM4_CLUSTERED_OPEN_MARKET_BUYING_FORWARD_UPDRIFT`, `F0_MECHANISM -> F0_MECHANISM`. Strategy advancement is false.

Canonical evidence: `sec-form4-clustered-buying-train.json` in this directory.

- Executor-phase pre-finalizer raw SHA-256: `8840bfbe5817a2cccb7fcb1119063fe83ebe160f2e21a052fb6e00f35cac96a9`.
- Executor-phase normalized SHA-256 excluding only `generated_at`: `6c44d951aece846a19b638b6441494af01d327de9367d486f955200fba06624b`.
- Finalizer label-only regeneration (event-return tail made explicit) supersedes those bytes with current raw/normalized SHA `26691ba3923a9b9185173852aaa47ceb8050565870b44a9caa30e8ae91a427af` / `a603b29b5736adc12110239ef99c44aeb57f22a9f75e0b9eb782a7e54fb53263`; substantive rows, metrics, gates, and outcome are unchanged.
- Exact persisted-cache replay equality excluding only `generated_at`: `true`.
- Qualified accession-level purchases: **153**.
- Cluster signals: **13**; price-complete blueprints: **13**; price rejects: **0**.
- Chronological train eligible/matched: **7 / 6**; support **85.7143%**. XOM 2020-03-19 was the one unmatched train/control blueprint.
- Train coverage: only **2016 and 2019**, across **AAL, BAC, CCL, F, TSLA**.
- Event mean after 10 bps: **+1.482930%**.
- Prior same-symbol control mean after 10 bps: **+1.016569%**.
- Paired excess mean: **+0.466362%**; median **-1.224306%**.
- Circular three-pair-block LB90: **-2.665298%**.
- Positive frequency: **50.0%**.
- Event-return worst-decile mean after 10 bps: **-5.585214%**.
- Control distance median/max: **641.5 / 1,254 sessions**.
- Integrity violations: **0**.
- Passed gates: control support, event mean, paired mean, worst-decile floor, integrity.
- Failed gates: n24 density, six-year coverage, six-symbol coverage, positive dependence-aware LB90, and 55% positive frequency.
- Holdout: **6 / 6** matched identities from 2021-08-19 through 2023-11-09, SHA `dbff0318d403e9ef14c77d74e48a5b7f03a2956e07ceda020efa69134ec47791`; outcome metrics unread, simulation false, option pricing calls zero.

Dominant failure mechanism: the exact high-specificity cluster geometry is too sparse to identify a durable train effect, and its favorable six-pair mean is not stable under dependence-aware uncertainty or sign consistency. Very remote controls further weaken local specificity. Positive point estimates cannot rescue n6, two years, five symbols, 50% hits, or a -2.6653% LB90.

Quarantine: do not rerun the same original-Form-4 / code-P / direct-common / officer-director / >=$10k transaction / two-owner-and-accession / >=$100k / 20-calendar-day / next-session / ten-session geometry, nearby threshold nudges, present-panel expansion, or an option-wrapper substitution. Reopening requires a materially different corporate-information mechanism or evidence class predeclared before outcomes—for example verified acceptance timestamps plus a different information event, not merely loosening cluster density.

## Search information, separate from strategy advancement

The wake added a reusable official SEC Form 4 archive adapter and a claim-scoped train-only event-study runner with source hashes, strict transaction filters, first-public-date signals, accession/owner cluster integrity, prior-only controls, sealed holdout identities, strict JSON, and deterministic cache replay. It was exercised immediately against the named candidate and therefore produced a real `FAMILY_CLOSED` decision rather than a capability-only handoff.

The first implementation persisted transient `download` versus `cache` provenance and evaluated the response bytes before reopening the written archive. That would make exact replay differ for a non-economic reason. The executor repaired the boundary so claim evaluation always re-reads the persisted bytes and provenance contains only stable source URL/cache/hash fields; the unchanged dependent experiment then replayed substantively equal.

Search information is useful but strategy advancement remains false.

## Evidence validity critique

- Leakage / timing: features end before filing; entry is strictly after filing. Filing-date-only source avoids same-day ambiguity by never entering on filing day.
- Source provenance: official SEC quarterly archives and exact ZIP hashes are durable. No third-party insider screen was used.
- Amendment / derivatives / ownership: original Form 4, P/A/D, common-equity, officer/director filters are fail-closed and fixture-tested.
- Joint-filing ambiguity: two accessions are required, but bulk tables still do not attach each transaction row to one owner. Claim remains exact L0 and does not generalize to transaction-level owner attribution.
- Population: fixed present-day symbols and aliases create survivorship/current-ticker limitations. The exact family closes on this panel; it does not claim all issuers lack insider-buying effects.
- Control quality: support is adequate, but 641.5/1,254-session distances are coarse. That weakens the favorable point estimate; it cannot salvage failed density/uncertainty/hit gates.
- Density: n6 across two years and five symbols decisively misses the predeclared n24/six-year/six-symbol discovery bar.
- Costs / fills: 10 bps is an underlying hurdle only, not option bid/ask, IV, debit, assignment, or management realism.
- Holdout: six identities are sealed; no outcomes or option marks were read.
- Contract availability: no historical option contract or listed expiry was selected. The future bull-call is a complete planning expression only.
- Capital: planned one-lot debit cap fits $3,000, but actual debit/path loss is unmeasured and grants no L1 or seat.
- Ranking / leaders: readiness has no living candidate, L1 survivor, quality leader, or capital seat; no stale reference was used.
- Search freedom: the official corporate-information route was materially independent. No caller slot, TSLA tunnel, or fixed catalog recipe constrained the choice.

## Verification completed by executor

- New focused parser/filter, cluster-threshold/overlap, lag/next-session, full-gate positive-control, favorable-point/nonpositive-uncertainty negative-control, and stable-ID tests: **6/6**.
- Adjacent new + candidate-factory behavior/boundary/negative-control suite: `Ran 13 tests in 4.582s`, `OK`.
- Strict compile: green.
- Full unittest suite: `Ran 422 tests in 27.361s`, `OK`.
- Full pytest suite: `432 passed, 18 subtests passed in 28.39s`.
- `just test`: exit 0; TSLA and TSLL both `STAND ASIDE`; no broker action.
- Deterministic real-data replay: substantive equality true; hashes above.
- Income coverage refresh: **21 structures / 246 hypotheses / 70 evolve artifacts / no quality leader**, written at 2026-07-16T0508.

## Readiness / authority

No phase or B3/B4/B6+ gate advanced. Official-source point-in-time discovery and auditability improve B1/B5 BUILD evidence only. Living candidates remain 0; L1 candidates 0; quality leaders 0; capital seats 0. No registry status, paper intent, paper ledger, shadow, broker, funding, arm, or live surface changed.

If accepted by challenger/finalizer, this is the active epoch's third consecutive no-strategy-advance decision (`0335`, `0408`, `0454`), so `strategy_burst_stop_required=true`. The next wake must reassess search design/data; it must not launch a fourth mechanism search inside this exhausted epoch.

Freedom audit: symbol and strategy freedom remained open; the executor selected official issuer filings and a future defined-risk bullish debit expression because they maximize information gain under the mandatory pivot, not because NEXT was binding.

## Durable lesson

Future Trader can ingest and hash-cite official SEC Form 4 bulk archives, fail closed on common transaction ambiguities, align public filing dates to strictly later market entries, and preserve a sealed chronological holdout. The exact clustered-direct-purchase geometry is not a viable F1 candidate on the frozen liquid panel: six train pairs are favorable on average but sparse, remote-controlled, sign-inconsistent, and uncertainty-unbounded.

## ONE NEXT

`SEARCH_DESIGN_REASSESS_AFTER_FORM4_CLUSTER_DENSITY_UNCERTAINTY_CLOSE`: stop the active three-no-advance burst. Reconcile the 0335 sector-leader close, 0408 credit-risk close, and 0454 Form 4 cluster close; inventory which independent economic mechanisms and point-in-time data classes remain genuinely open; diagnose why the current train-only factory keeps producing sparse or uncertainty-failing exact families; and either close the epoch with a new successor charter and predeclared success criterion or declare `DIMINISHING_RETURNS`. Do not open any sealed holdout, loosen this Form 4 cluster after seeing n6, or launch another strategy test before reassessment.

No commit, push, merge, deterministic completion gate, or RUN COMPLETE claim was attempted in this executor phase.

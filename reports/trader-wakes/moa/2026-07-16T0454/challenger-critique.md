# MOA challenger critique — 2026-07-16T0454

Role: Grok 4.5 challenger / read-only judgment
Phase: BUILD / L0 official-source underlying discovery
Status: CHALLENGER PARTIAL — finalizer/integration pending; no commit, push, merge, or RUN COMPLETE

## Verdict

**PASS WITH NITS**

Accept the executor's exact claim-bearing outcome:

- `FAMILY_CLOSED` for `SEC_FORM4_CLUSTERED_INSIDER_BUYING_CALL_21D_V1` / `SEC_FORM4_CLUSTERED_OPEN_MARKET_BUYING_FORWARD_UPDRIFT`
- Funnel: `F0_MECHANISM -> F0_MECHANISM`
- Strategy advancement: **false**
- Search information: useful (official Form 4 archive lab + exercised decision + provenance re-read repair)
- Capital / L1 / seat / paper / shadow / arm / live: **none**

If finalizer integrates this close, the active epoch (`POST_REASSESSMENT_INDEPENDENT_DEFINED_RISK_DISCOVERY_V1`, started `2026-07-16T0335`) reaches **three** consecutive counted no-advance decisions (`0335`, `0408`, `0454`). Set `strategy_burst_stop_required=true` and do **not** launch a fourth mechanism search inside this epoch.

## Independent verification (read-only)

Canonical artifact: `reports/trader-wakes/moa/2026-07-16T0454/sec-form4-clustered-buying-train.json`

| Check | Result |
|---|---|
| Raw SHA-256 | `8840bfbe5817a2cccb7fcb1119063fe83ebe160f2e21a052fb6e00f35cac96a9` — **matches** file bytes |
| Normalized SHA (exclude only `generated_at`, sort_keys compact JSON) | `6c44d951aece846a19b638b6441494af01d327de9367d486f955200fba06624b` — **matches** |
| Train pairs | n=6; symbols AAL/BAC/CCL/F/TSLA; years 2016/2019 only |
| Event / control / paired means after 10 bps | +1.482930% / +1.016569% / +0.466362% — **reproduced** |
| Paired median / positive frequency | −1.224306% / 50.0% — **reproduced** |
| Circular 3-pair-block LB90 | −2.665298% — **reproduced** (seed-stable across 0/1/7/42/2026) |
| Chronology | control_exit < signal_date and entry_date > signal_date for all 6 pairs — **ok** |
| Control distances | median 641.5 / max 1254 sessions — **reproduced** |
| Holdout | 6 identities, outcomes unread, simulation false, option_pricing_calls=0 — **ok** |
| Authority labels | `l1_claim=false`, `f2_claim=false`, `claim_bar=L0_DISCOVERY_ONLY` — **ok** |
| Capital planning fields | capital_fit_usd=200, max_loss_usd=200 (frictionless planning cap), max_lots=1 — **ok** |
| Runner / tests present | `scripts/sec_form4_clustered_buying_train_lab.py`, `tests/test_sec_form4_clustered_buying_train_lab.py` |

Failed gates in the executor-phase artifact match independent recomputation for density/year/symbol/support/means/hit/integrity. The conjunction fails closed; favorable point means cannot rescue n6.

Finalizer note: the verified `8840bfbe…` / `6c44d951…` hashes above are the pre-reconciliation phase bytes. The accepted N1 label repair regenerated the same substantive claim with explicit `event_return_worst_decile_mean` / event-tail gate names; current raw/normalized SHA are `26691ba3923a9b9185173852aaa47ceb8050565870b44a9caa30e8ae91a427af` / `a603b29b5736adc12110239ef99c44aeb57f22a9f75e0b9eb782a7e54fb53263`. Metrics, failed-gate set, holdout identity, and `FAMILY_CLOSED` are unchanged.

## Rubric

1. **Strategy charter** — **PASS**. Economic mechanism (clustered direct officer/director open-market buying → delayed issuer updrift), candidate/family IDs, funnel F0→F1 or close, predeclared multi-gate falsifier, and exact closed outcome `FAMILY_CLOSED` are explicit in `strategy-charter.md` + closeout.
2. **Strategy vs operations** — **PASS**. New SEC lab is not sold as strategy progress alone; it was exercised same-wake to advance-or-close. Provenance re-read repair is correctly reported as search information under a `FAMILY_CLOSED` outcome, not a fake `STRATEGY_ADVANCED`.
3. **Goal progress** — **PASS**. Honest close of a new official corporate-information class improves the chance of a durable paper-testable edge by eliminating a sparse/unstable exact geometry and forcing burst-stop reassessment rather than more volume.
4. **Creativity / independence** — **PASS**. Materially different evidence class vs closed market-price, scheduled-macro, cross-sectional, credit, and daily option-signal families. Honors `strategy_pivot_required` from streak-2 orientation. Prior Form 4 NEXT used as context and exercised, not blindly polished.
5. **Claim validity** — **PASS**. Prerequisites match the chosen F0 underlying event study. No L1, no option edge, no registry/paper promotion. Proxy/option marks correctly zero.
6. **Evidence and test quality** — **PASS WITH NITS**. Real runner, SHA-cited SEC ZIPs, sealed holdout, focused positive/negative controls, and full-suite claims are cited. Independent metric/SHA replay matches. Nits below are label/clarity items, not outcome-changers.
7. **Falsification** — **PASS**. Frozen gates predeclared; no post-hoc relaxation; dominant failure (sparsity + uncertainty + sign inconsistency) recorded; dual-ID quarantine + nearby-threshold/panel/option-wrapper anti-salvage stated.
8. **Capital honesty** — **PASS**. No living leader/L1/seat claimed. Absolute discovery bar used. Planning structural debit cap labeled frictionless and unmeasured for path/assignment.
9. **Research freedom** — **PASS**. Observed-option archive thinness did not freeze this independent historical/official route. No unnecessary allowlist tunnel.
10. **ONE NEXT** — **PASS**. Burst-stop reassessment is the only highest-information seed. No live/shadow promotion.

## Accepted disposition

| Item | Disposition |
|---|---|
| Outcome | Accept `FAMILY_CLOSED` F0→F0 |
| Advancement | Accept false |
| Dominant failure | Accept: exact high-specificity cluster geometry too sparse (n6 / 2y / 5 symbols) and uncertainty/sign-unstable (LB90 −2.665%, hit 50%, median negative) |
| Quarantine | Accept exact Form 4 P/A/D common officer-director two-owner-and-accession ≥$100k / 20d / next-session / 10-session geometry; nearby threshold nudges; present-panel expansion; option-wrapper salvage |
| Epoch implication | Accept third no-advance → `strategy_burst_stop_required=true` after integration |
| ONE NEXT | Accept `SEARCH_DESIGN_REASSESS_AFTER_FORM4_CLUSTER_DENSITY_UNCERTAINTY_CLOSE` |

## Findings / nits (finalizer should reconcile; none reverse the close)

### N1 — Label worst-decile as **event** path, not paired excess (clarity)

Script `_worst_decile` is applied to **event** returns (`tail = _worst_decile(events)`), yielding −5.585214% and a pass on the ≥ −8% gate. The six paired-excess values have a more severe worst single episode ≈ −8.59%. Charter wording says only “signed worst-decile mean” without event-vs-paired. Family still closes on other gates, so this is **not** claim-invalidating, but finalizer should:

- label readiness/closeout/claim methodology as **event-return worst-decile**;
- optionally add a one-line regression or comment so future readers do not assume paired-tail.

### N2 — Option horizon vs F0 horizon alignment (planning stack)

F0 measures a **ten-session** underlying drift. Planned expression is **18–24 DTE** bull-call with management including a ten-session time stop. Monetization of forecast is directionally aligned (bullish debit), but F0 does **not** measure theta/vega/debit path over the full DTE. Executor already says option marks = 0 and planning-only; finalizer should keep that boundary sharp so no reader skims “21D call” as validated.

### N3 — Control local-specificity is weak even where support passes

Median/max control distance 641.5 / 1,254 sessions means the “same-regime nearest ret20” control is often multi-year remote. Support 85.7% passes the frozen ≥70% gate, but local specificity is poor. Executor correctly treats this as weakening the favorable point estimate rather than rescuing the family. Finalizer: preserve distance diagnostics in any durable closed-family record and in reassessment inventory as a recurring train-only factory weakness (too-specific event definitions → sparse n + remote controls).

### N4 — Bulk Form 4 owner-attribution L0 limit remains material

Two-accession rule reduces joint-filing false clusters, but quarterly bulk tables still do not attach every transaction row to one owner. Claim correctly stays L0 and closed. Reassessment should not reopen “same geometry with better owner join” without a **new predeclared evidence class** (e.g. acceptance-timestamped EDGAR or a different corporate-info event), not silent threshold softening after n6.

### N5 — Present-day panel survivorship is an L0 scope limit, not a free reopen

Fixed current liquid tickers / aliases are labeled. Do not treat “expand the panel” as a new mechanism after seeing sparsity. Quarantine text already covers panel expansion; keep it.

### N6 — Integration-state counters must not be written by challenger

`configs/search_epoch.json` still shows `counted_no_advance_decisions=2` / `strategy_burst_stop_required=false` because this phase is pre-integration. That is correct. Finalizer/deterministic gate owns bumping to 3 + burst-stop + completed-epoch or successor reassessment docs. Challenger does not mutate epoch config.

### N7 — Verification counts are executor-attested

Challenger independently verified claim metrics/SHAs/chronology and presence of runner/tests. Full unittest/pytest/`just test` green counts are accepted as executor-attested evidence paths for finalizer re-run; challenger did not re-execute the full suite (read-only budget). Finalizer must re-run focused + full-suite before RUN COMPLETE.

## Rejected misreads (do not do these)

- Do **not** salvage via looser cluster thresholds, single-insider signals, or inspecting holdout outcomes.
- Do **not** wrap the same underlying geometry in an option sim and call it a new family.
- Do **not** treat official-source plumbing alone as `STRATEGY_ADVANCED`.
- Do **not** start a fourth F0 mechanism search before search-design reassessment.
- Do **not** claim capital seat, L1, paper packet, shadow, or arm.

## Freedom / thrash audit

- Freedom preserved: official Form 4 corporate-information route was available and used.
- No observed-archive freeze of unrelated historical discovery.
- Not thrash: new evidence class + real decision + third-streak stop rule.
- Anti-thrash NEXT correctly redirects to reassessment / possible `DIMINISHING_RETURNS`, not another factory clone.

## ONE merged NEXT seed

`SEARCH_DESIGN_REASSESS_AFTER_FORM4_CLUSTER_DENSITY_UNCERTAINTY_CLOSE`

Stop the active three-no-advance burst. Reconcile integrated closes at `0335` (sector-leader continuation), `0408` (HY credit risk-off), and `0454` (Form 4 clustered buying). Inventory genuinely open economic mechanisms and point-in-time data classes that are **not** nearby retunes of closed families. Diagnose why the train-only defined-risk factory keeps emitting sparse or uncertainty-failing exact geometries (density bars vs control remoteness vs event rarity). Either:

1. write a successor-epoch charter + predeclared success criterion and mark this epoch completed, or
2. declare `DIMINISHING_RETURNS` if no materially new informative route remains.

Do not open sealed holdouts; do not loosen Form 4 thresholds after seeing n6; do not launch another strategy test first.

## Challenger phase boundary

No evolve `--apply`, no broker, no arm, no commit/push/merge, no RUN COMPLETE. Finalizer owns repair of accepted nits, verification re-run, learning promotion, and integration prep.

MOA_CHALL_DONE

## VERIFICATION

Finalizer-owned evidence (not inherited from executor counts):

- `.venv/bin/python -m unittest tests.test_sec_form4_clustered_buying_train_lab -v` — `Ran 8 tests in 0.232s`, `OK`. This exercises official-archive filtering, persisted-byte re-open behavior, cluster/accession/owner boundaries, overlap suppression, lag-safe chronology, positive gate behavior, non-positive uncertainty fail-close, stable IDs, and an event-tail-versus-paired-tail negative control.
- Integration-residue repair: after wrapper integration exposed `git diff --check` whitespace and a completion-gate secret-marker false positive on novelty strings such as `risk-off`, trailing whitespace was stripped and `scripts/trader_run_completion_gate.py` now requires token-marker boundary context before matching `sk-*`; `tests.test_trader_run_completion_gate` covers the `risk-off` / `defined-risk` novelty-key regression.
- `.venv/bin/python -m unittest tests.test_trader_build_compounding tests.test_trader_run_completion_gate tests.test_trader_completion_contract tests.test_trader_income_coverage` — `Ran 55 tests in 8.418s`, `OK` before the final integration-residue repair; the wrapper-owned integration rerun revalidates the updated completion-gate test before `RUN COMPLETE`.
- Persisted-cache canonical replay with only `generated_at` removed — canonical raw SHA `26691ba3923a9b9185173852aaa47ceb8050565870b44a9caa30e8ae91a427af`; canonical normalized SHA `a603b29b5736adc12110239ef99c44aeb57f22a9f75e0b9eb782a7e54fb53263`; replay normalized SHA `a603b29b5736adc12110239ef99c44aeb57f22a9f75e0b9eb782a7e54fb53263`; `normalized_equal=true`; `substantive_outcome=FAMILY_CLOSED`; `holdout_outcome_metrics_read=false`; `holdout_simulation_run=false`; `option_pricing_calls=0`.
- `.venv/bin/python -m unittest discover -s tests` — `Ran 424 tests in 27.290s`, `OK`.

The deterministic completion, secret-safety, clean-diff, and integration checks remain wrapper-owned. Integration is pending the deterministic wrapper gate; this report does not claim commit, merge, push, remote verification, or `RUN COMPLETE`.

## DURABLE

Strategy charter and outcome:

- Charter: `reports/trader-wakes/moa/2026-07-16T0454/strategy-charter.md` freezes original timely Form 4 direct open-market common-share purchases by officers/directors; at least two distinct owners and accessions; at least $100,000 inside 20 calendar days; first-public filing date; next-session-close entry; ten-session underlying outcome; prior-only same-symbol controls; chronological 60/40 train/sealed holdout; zero option pricing; and a future conditional one-lot 18-24 DTE $2-wide bull-call debit-spread planning cap (`capital_fit_usd=200`, frictionless `max_loss_usd=200` before closing friction, `max_lots=1`).
- Outcome: `FAMILY_CLOSED` at F0 for both `SEC_FORM4_CLUSTERED_INSIDER_BUYING_CALL_21D_V1` and `SEC_FORM4_CLUSTERED_OPEN_MARKET_BUYING_FORWARD_UPDRIFT`. Only 6 matched train pairs survived, spanning 2 signal years and 5 symbols. Event/control/paired means after 10 bps were +1.482930%/+1.016569%/+0.466362%; paired median -1.224306%; circular three-pair-block LB90 -2.665298%; event hit rate 50%; explicitly labeled event-return worst-decile -5.585214%. Density, year, symbol, positive-LB90, and 55%-hit gates failed. Median/max prior-control distance was 641.5/1,254 sessions. No holdout outcome or option price was read.
- Exact-family quarantine: no threshold drift, single-insider fallback, owner-join polish, panel expansion, sign/horizon retune, holdout opening, or option-wrapper rescue can reopen this family without a materially different predeclared mechanism/evidence class.

Challenger reconciliation:

- N1 accepted and repaired. Script, machine claim, gate key, methodology boundary, charter, executor/critic phase annotations, readiness/finalizer surfaces, and focused tests now identify the tail as the event-return worst decile after 10 bps. The negative-control test deliberately makes event and paired tails differ. Canonical bytes were regenerated; old executor/challenger hashes are retained only as pre-reconciliation phase evidence and current hashes are cited everywhere living.
- N2 accepted as a methodology caveat, not a new code defect. The ten-session F0 underlying endpoint remains distinct from the unvalidated 18-24 DTE option plan; theta/vega/debit/fill/management paths remain unmeasured, option calls remain zero, and no F1/L1/paper authority is claimed.
- N3 accepted and promoted. The 641.5/1,254-session control-distance weakness is explicit in the completed epoch record, finalizer evidence, compounding residue, readiness, and reassessment seed; no tolerance was widened.
- N4 accepted and retained as an L0 limit. Bulk rows still do not attribute each transaction to a specific owner; two accession/owner support is required, and the limitation cannot be polished into a same-family reopen after outcomes.
- N5 accepted and retained as an L0 limit. The fixed present-day panel carries survivorship/ticker-alias bias and panel expansion is not novelty.
- N6 accepted as finalizer-owned integration state. `configs/search_epoch.json` now counts the 0335, 0408, and 0454 closes as 3 consecutive no-advances, sets pivot/burst-stop true, marks the epoch completed at 0454, preserves the reassessment route, and does not open a successor epoch prematurely.
- N7 accepted. Finalizer independently reran focused and full suites; no executor count is used as final proof.
- No material challenger finding was rejected as unsupported. In `compounding.json`, N2-N7 use `rejected` only in the schema's defect-disposition sense: the caveats/process requests were accepted, but they were not latent machinery defects requiring a code repair.

Durable surfaces:

- Machinery/tests: `scripts/sec_form4_clustered_buying_train_lab.py`, `tests/test_sec_form4_clustered_buying_train_lab.py`.
- Claim/charter/closeout: `reports/trader-wakes/moa/2026-07-16T0454/sec-form4-clustered-buying-train.json`, `strategy-charter.md`, `executor-closeout.md`, `challenger-critique.md`, `compounding.json`, and this file.
- Search governance: `configs/search_epoch.json`, `docs/SEARCH_EPOCH_2026-07-16T0335.md`, `reports/trader-wakes/moa/2026-07-16T0454/merged-next-seed.md`.
- Living derived truth is carried by `reports/trader-wakes/2026-07-16T0454-moa-merge.md`, `reports/trader-wakes/LATEST.md`, `reports/trader-wakes/INDEX.md`, `reports/readiness/LATEST.md`, and its dated readiness source.
- Reusable procedure promoted to profile skill `options-strategy-analysis`: machine-label metric populations, test divergent event versus paired tails, and parse/hash the persisted representation on first download and replay.
- No profile-memory update: this wake's dated family result and epoch count belong in repo evidence, while the reusable procedure belongs in the narrow skill; adding either to near-capacity global memory would duplicate or stale quickly.

## LESSON

Future Trader can now consume official quarterly SEC Form 4 bulk archives through a tested, lag-safe F0 event-study path and can prove first-download/replay representation parity instead of merely hashing a cache. It also has a regression pattern that prevents an absolute event tail from being mislabeled as paired excess. Economically, the exact high-specificity clustered-buying train is not identified: attractive six-pair point means coexist with sparse years/symbols, remote controls, a negative uncertainty bound, and a 50% hit rate. The correct action is family close plus search-design reassessment, not threshold or option-wrapper salvage. Governance now closes the three-no-advance epoch at its burst stop rather than silently carrying a stale count into a fourth test.

## NEXT

`SEARCH_DESIGN_REASSESS_AFTER_FORM4_CLUSTER_DENSITY_UNCERTAINTY_CLOSE`: stop the completed three-no-advance burst. Reconcile the 0335 sector-leader, 0408 credit-risk-off, and 0454 Form 4 closes; inventory genuinely open mechanisms and point-in-time data classes not covered by nearby-retune quarantines; diagnose recurring sparse-event, remote-control, uncertainty-bound, and horizon/expression weaknesses; then either write a successor epoch with a revised charter and predeclared success criterion or declare `DIMINISHING_RETURNS`. Do not open sealed holdouts, loosen the Form 4 geometry, or launch a fourth strategy test before reassessment.

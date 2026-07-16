# Learning promotion — 2026-07-15T2254

## VERIFICATION

Strategy charter/outcome: `BROAD_SECTOR_BREADTH_THRUST_SPY_BULL_CALL_21D_V1` / `BROAD_SECTOR_BREADTH_THRUST_FORWARD_DRIFT`, `F0_MECHANISM -> F0_MECHANISM`, exact `FAMILY_CLOSED`, strategy advancement false. The planned one-lot 18–24 DTE `$2`-wide SPY bull-call debit spread remains conditional context only: `capital_fit_usd=$200`, frictionless structural `max_loss_usd=$200` only when entry debit is `<= $200`, `max_lots=1`; no option marks, F1/F2/L1, capital seat, registry, paper, shadow, arm, broker, funding, or live authority.

- Red repair test: `.venv/bin/python -m unittest tests.test_sector_breadth_thrust_train_lab.SectorBreadthThrustTrainLabTest.test_run_lab_keeps_holdout_outcomes_sealed_and_closes_when_specificity_fails` -> `FAILED (failures=1)` because `strategy_advancement` was a prose string rather than boolean false.
- Green new lab suite: `.venv/bin/python -m unittest tests.test_sector_breadth_thrust_train_lab` -> `Ran 5 tests in 0.203s — OK` after machine-label, match-quality, density/tail, horizon, and quarantine repairs.
- Focused behavioral/boundary/negative-control/regression suite: `.venv/bin/python -m pytest tests/test_sector_breadth_thrust_train_lab.py tests/test_low_hv_cross_section_train_lab.py tests/test_trader_income_coverage.py -q` -> `13 passed in 1.15s`.
- Required full suite: `.venv/bin/python -m unittest discover -s tests` -> `Ran 373 tests in 19.168s — OK`.
- Full pytest regression: `.venv/bin/python -m pytest -q` -> `383 passed, 18 subtests passed in 21.78s`.
- Canonical replay/regeneration: `.venv/bin/python scripts/sector_breadth_thrust_train_lab.py --out .cache/platform/sector_breadth_thrust_train_2026-07-15T2254.json` -> `FAMILY_CLOSED`, train n20. Finalizer SHA-256 is `0180dfe59ec20a8b6699116edc21ae20d57953520f5ebf03b1a7716df49252cf`; executor/challenger phase SHA `471866c6...` is superseded only by added diagnostics/claim-boundary fields. All economic metrics, failed gates, pair rows, and sealed holdout identity `c701202882297dd064cf186080865754678e0c904eb03f0c11fd574fdca76060` remained equal.
- Finalizer diagnostics: train calendar-distance min/median/max `12/68/360` sessions; breadth-distance min/median/max `0/0/0.181818`; return-60 distance `0.006056/0.030272/0.102795`; HV-ratio distance `0.004050/0.245795/0.484548`; year counts `2019:3, 2020:4, 2021:8, 2022:1, 2023:4`; thin worst-decile `n=2`.
- Coverage regeneration: `just trader-income-coverage` -> 21 structures / 246 hypotheses / 70 evolve artifacts / no living leader; dated surface `reports/readiness/income-coverage-2026-07-15T2334.md` and matching LATEST written.

Accepted/repaired challenger findings:

1. F1 accepted: quarantine now covers the exact family plus nearby same-panel 8–10/11 breadth, five-session thrust/control-band, 5–15-session horizon, SMA50/SMA100, and same-novelty retunes. Reopening requires a materially new mechanism or evidence class.
2. F2 accepted: canonical train residue now serializes calendar, breadth, return-60, and HV-ratio match-distance summaries; coarse controls are not called tight local matches.
3. F3 accepted: `strategy_advancement` is machine boolean false with separate explanatory summary.
4. F4 accepted: schema-v2 `closed_families` registers the family, candidate, and expanded same-panel quarantine on the orientation-facing durable surface.
5. F5 accepted: the XLC-limited 2018-06-19 panel floor and year clustering are explicit non-generalizing density context. Dropping XLC or loosening the eight-year gate after inspection is forbidden.
6. F6 accepted: the failed predeclared worst-decile gate is retained and labeled thin (`n=2`), not redefined post hoc.
7. F7 accepted: ten-session underlying drift does not validate the full 18–24 DTE option path, IV crush, debit fills, or early-exit economics.
8. F8 accepted without additional correction: `configs/search_epoch.json` correctly records two completed no-advance decisions, pivot required, burst-stop false; pure distinct-RTH append reaffirmations remain streak-exempt.
9. F9 accepted: focused, full unittest, and full pytest suites were independently rerun green by the finalizer.
10. F10 accepted: the legacy combined flag remains false for compatibility and is accompanied by explicit `f2_claim=false` and `l1_or_capital_seat_claim=false` fields.

Rejected interpretations: positive 65% hit rate is not edge; the sealed holdout is not opened; the family is not inverted into a fade; XLC/density/match gates are not loosened; no option stage, registration, paper force, or capital/readiness promotion is allowed.

Integration is pending the deterministic wrapper gate. This artifact is a green handoff, not a `RUN COMPLETE` claim.

## DURABLE

- Machinery: `scripts/sector_breadth_thrust_train_lab.py` now emits boolean advancement, split authority labels, match-quality summaries, year counts, tail sample size, dynamic panel-history floor, expanded quarantine, and explicit option-horizon boundaries.
- Tests: `tests/test_sector_breadth_thrust_train_lab.py` asserts all repaired machine and claim boundaries while preserving chronology, sealed holdout, specificity failure, and holdout-price negative control.
- Project truth/history: finalizer merge/LATEST/INDEX/readiness/coverage surfaces and this learning record state the exact F0 family close, coarse matching, thin tail, no option authority, and pivot requirement.
- Orientation durability: `compounding.json` registers the closed family/candidate and same-panel retune quarantine with unique novelty keys.
- Search state: `configs/search_epoch.json` retains the parked observed TSLL diagonal while recording the second no-advance decision and required off-hours pivot.
- Skill: no edit. The loaded `trader-self-evolution` skill already requires claim-boundary critique, negative controls, durable closed-family registration, and full-suite completion; this wake adds experiment-specific evidence rather than a missing general procedure.
- Memory: no edit. The new information is dated project evidence and an experiment-specific quarantine, not a stable user preference or routing fact; profile memory is already near capacity and repo/skill surfaces are authoritative.

## LESSON

Future Trader can now serialize and test match geometry instead of leaving “matched control” as an unauditable label. A positive hit rate under high breadth does not identify a breadth-thrust edge: the thrust must beat prior-only high-breadth non-thrust controls under magnitude and dependence-aware uncertainty, and readers need calendar/feature-distance summaries to judge how local those controls really are.

The exact SPY + eleven-sector thrust family failed because treated mean (`+0.245246%`) trailed control (`+0.370614%`), paired excess was `-0.125368%`, LB90 was `-0.883946%`, and the thin worst-decile was `-6.981542%`. Five clustered train years and coarse match distances reinforce rejection; neither licenses post-inspection panel, threshold, horizon, or SMA polish. The ten-session underlying study also cannot validate 18–24 DTE option IV/fill/path economics.

## NEXT

`TSLL_OBSERVED_TERM_CARRY_DATA_OR_MATERIALLY_DIFFERENT_L0_PIVOT`: use exactly one branch per wake—on a distinct weekday-RTH date while the frozen 12-date/3-cycle/20-path/8-control floor is unmet, append one provenance-safe all-expiration TSLL snapshot and report counters only (`EVIDENCE_WAIT`, reaffirmation streak-exempt); off-hours, pivot to a materially different non-quarantined mechanism/evidence class outside sector-breadth directional continuation and all integrated closed families; once the observed floor is met, evaluate exact parked `TSLL_OBSERVED_TERM_CARRY_DIAGONAL_V1` development 60% and keep the final 40% unread. No same-date churn, same-panel breadth retune, holdout salvage, registry/paper force, shadow, arm, broker, funding, or live action.

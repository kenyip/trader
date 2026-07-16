# MOA challenger critique — 2026-07-15T2254

WAKE: 2026-07-15T2254
PHASE: BUILD / L0 underlying discovery only
ROLE: Grok 4.5 challenger (read-only judgment)
SESSION: off-hours PDT / market closed
SLEEVE: $3,000
STATUS: partial MOA critique phase only; no evolve --apply; no broker; no commit/push/merge; no RUN COMPLETE

## Verdict

**PASS WITH NITS**

Accept executor outcome: exact `FAMILY_CLOSED` at `F0_MECHANISM -> F0_MECHANISM` for
`BROAD_SECTOR_BREADTH_THRUST_SPY_BULL_CALL_21D_V1` /
`BROAD_SECTOR_BREADTH_THRUST_FORWARD_DRIFT`. Strategy advancement is false. No
option stage, F1/F2, L1, living leader, capital seat, registry, paper, shadow,
arm, broker, funding, or live claim is warranted.

Independent challenger checks (read-only):

- Artifact SHA-256 matches cited path:
  `.cache/platform/sector_breadth_thrust_train_2026-07-15T2254.json` =
  `471866c6f922ab85fea0e9463dc3968bf4420347d9dc50ba2ee49adecc0d3fbb`
- Replay payload equals canonical payload excluding only `generated_at`
- Holdout sealed: no `pairs`, `outcome_metrics_read=false`, `simulation_run=false`,
  identity `c701202882297dd064cf186080865754678e0c904eb03f0c11fd574fdca76060`
- From frozen train pairs: treated mean `+0.245246%`, control `+0.370614%`,
  paired excess `-0.125368%`, positive frequency `65%`, worst-decile n=2 mean
  `-6.981542%`, years `[2019..2023]`
- Recomputed three-signal-date block-bootstrap LB90 matches artifact to float noise
  (`-0.883946%`)
- Predeclared failed gates recompute as fail-closed; integrity violations empty
- Blueprint rebuild: 34 total pairs; train calendar-distance min/med/max
  `12 / 68 / 360` sessions; breadth-match often exact; ret60/hv distances within
  frozen tolerances

Challenger did **not** re-run full unittest/pytest discovery; finalizer must
re-verify the claimed green suites before integration.

## Rubric

1. Strategy charter — **PASS**
   Economic mechanism, candidate/family, funnel F0→F0, predeclared falsifier, and
   exact outcome `FAMILY_CLOSED` are explicit in charter + closeout + artifact.

2. Strategy vs operations — **PASS**
   New lab/tests are search information, not strategy progress. Outcome is an
   honest family close, not capability-as-progress.

3. Goal progress — **PASS**
   Useful search information: one new participation-acceleration mechanism is
   falsified with sealed holdout and reusable control geometry. Chance of a durable
   paper-testable edge improves by not spending more wakes on this exact thrust claim.

4. Creativity and independence — **PASS**
   Off-hours correctly superseded unmet RTH observed-diagonal data seed. Sector
   breadth-thrust with prior-only high-breadth non-thrust controls is materially
   different from quarantined low-HV, momentum, breakout, post-shock, earnings,
   OPEX/TOM, and SPY theta-carry families. Not a familiar PCS/TSLL tunnel.

5. Claim validity — **PASS**
   Prerequisites match experiment: adjusted closes, train-only, no option marks.
   Present-day fixed sector panel / XLC listing floor / survivorship bias are labeled.
   No L1/proxy-option overclaim.

6. Evidence and test quality — **PASS WITH NITS**
   Real lab + 5 behavioral/boundary/negative-control tests + deterministic replay.
   Useful checks: next-session entry lag, sealed holdout, specificity fail close,
   holdout-price non-influence, chronology fail-closed.
   Nits below do not overturn the rejection.

7. Falsification — **PASS**
   Dominant failure is mechanism-specific: thrust did not beat high-breadth
   non-thrust controls (paired magnitude, uncertainty, and mean superiority all fail).
   Density, absolute mean, and tail failures reinforce; none is used as salvage.

8. Capital honesty — **PASS**
   Living leader remains none. `$200` / max_lots1 is only the future same-expiry
   `$2`-wide debit-spread structural ceiling with debit `<= $200`, not observed max
   loss, fill, or seat admission. No capital-path language earned.

9. Research freedom — **PASS**
   Observed-option archive thinness did not freeze this independent L0 route.
   Parked diagonal not proxy-satisfied. No allowlist tunnel.

10. ONE NEXT seed — **PASS WITH NIT**
    Dual RTH-append / off-hours-pivot / evaluate-when-floor seed is one compound
    seed with clear branch conditions. Accept, with quarantine/pivot wording
    tightened below. No live/shadow promotion.

## Accepted claims

- Exact family closed at F0; funnel does not advance.
- Incremental edge absent: control mean exceeds treated; paired LB90 negative.
- Holdout 14-pair identity sealed and unread; option pricing calls zero.
- Epoch progress after this counted no-advance: consecutive_no_strategy_advance=2,
  strategy_pivot_required=true, burst-stop false (post-2152 active epoch).
- Search information yes; strategy advancement no.

## Findings (finalizer must address)

### F1 — Broaden quarantine scope (claim-boundary nit)

Executor quarantine of "unchanged threshold/horizon reruns" is too narrow.
Quarantine the exact family **and** nearby same-panel retunes that would re-spend
the inspected train without a new mechanism:

- breadth thresholds near 9/11 (e.g. 8/11, 10/11)
- thrust change near +3/11 over 5 sessions
- non-thrust control band near <=1/11
- horizons near 10 sessions (5–15) on the same thrust definition
- SMA50 sector / SMA100 SPY lookback nudges on the same panel
- same novelty class without a new control design

Reopening requires a materially new economic mechanism or evidence class, not
knob polish.

### F2 — Persist match-quality diagnostics (evidence completeness nit)

Train artifact outcomes omit blueprint match distances. Independent rebuild shows
TRAIN calendar-distance min/med/max `12 / 68 / 360` sessions and HV-ratio distance
median ~0.21 (max near the 0.50 cap). Coarse time matching does **not** rescue
the family — if anything it makes the failed specificity result more cautionary —
but finalizer should serialize calendar/breadth/ret60/hv distance summaries into
durable residue or methodology_boundaries so future readers do not treat pairs as
tight local matches.

### F3 — Machine `strategy_advancement` boolean vs prose string (schema nit)

Artifact uses string
`strategy_advancement: "none; exact mechanism family closed at F0"`.
Doctrine/readiness prose expects boolean false. Keep outcome enum authoritative;
normalize machine field to boolean false (or dual fields) in handoff/compounding
so orientation does not parse prose.

### F4 — Durable closed-family registration

Ensure
`BROAD_SECTOR_BREADTH_THRUST_FORWARD_DRIFT` /
`BROAD_SECTOR_BREADTH_THRUST_SPY_BULL_CALL_21D_V1`
is appended to the durable closed-family / novelty surfaces used by orientation
(not only wake prose). Orientation at wake start listed 29 closed families and
did not yet include this one.

### F5 — Year clustering is density context, not a second mechanism

Train year counts: 2019:3, 2020:4, 2021:8, 2022:1, 2023:4. Sparse 2022 and
XLC-limited history correctly fail the eight-year gate. Do not reopen via
dropping XLC or shortening min years after seeing outcomes. Label non-generalizing
panel floor explicitly in learning promotion.

### F6 — Tail metric thinness (label only)

Worst-decile mean uses n=2 of 20. Gate failure is still valid and aligned with
the predeclared falsifier; do not retune decile definition post hoc. Prefer
wording "thin worst-decile sample (n=2) also failed" in readiness.

### F7 — Horizon vs option DTE alignment (already mostly honest)

F0 measures 10-session underlying drift; planned option is 18–24 DTE with a
10-session management exit. Accept as labeled conditional stack. Finalizer should
keep the statement that F0 does **not** validate full-DTE option path, IV crush
after breadth thrust, or debit-fill economics.

### F8 — Epoch counting acceptance

Start orientation: consecutive_no_strategy_advance=1, pivot false (prior counted
decision was 2152 `EVIDENCE_WAIT` for the parked diagonal, not a pure-append
reaffirmation). This wake is a second completed no-advance strategy decision →
streak 2, pivot required, burst-stop false. Accept executor epoch_progress update
pending finalizer integration. Next **off-hours strategy** wake must pivot; pure
distinct-RTH append reaffirmations remain streak-exempt.

### F9 — Verification re-run required

Executor claims focused 13, full unittest 373, full pytest 383+18 subtests.
Challenger verified artifact math and lab rebuild only. Finalizer must re-run
focused + full suites and refuse integration on any red.

### F10 — Combined `f2_or_l1_claim` flag

Legacy combined boolean is false; prefer split funnel/authority labels if touching
the payload. Not claim-invalidating.

## Rejected interpretations

- Do not treat positive 65% hit rate as edge.
- Do not open holdout to salvage.
- Do not price options / register / paper-force this family.
- Do not drop XLC or loosen density/match gates after inspection.
- Do not invert to "fade breadth thrust" from inspected train outcomes.
- Do not count tooling alone as STRATEGY_ADVANCED.
- Do not freeze all L0 discovery because observed TSLL archive is thin.
- Do not claim living capital leader or readiness B-check upgrade.

## Freedom / thrash audit

Freedom preserved. Highest-information off-hours loop was a new within-market
participation mechanism, not another observed-archive wait and not a closed-family
reopen. After this close, unchanged breadth-thrust volume would be thrash; NEXT
must pivot off-hours or pure-append on RTH only.

## Capital / readiness

- Phase remains BUILD.
- Living leader: none.
- Parked `TSLL_OBSERVED_TERM_CARRY_DIAGONAL_V1` remains candidate-scoped
  `EVIDENCE_WAIT` with unproven structural max loss and floor unmet.
- Readiness NEXT is directionally correct; finalizer should only patch if quarantine
  / pivot wording is weaker than F1/F8 above.

## ONE merged NEXT seed

`TSLL_OBSERVED_TERM_CARRY_DATA_OR_MATERIALLY_DIFFERENT_L0_PIVOT`

Branch conditions (exactly one path per wake):

1. **Distinct weekday-RTH** and observed floor unmet
   (`>=12` RTH dates, `>=3` short cycles, `>=20` paths, `>=8` controls) → append one
   provenance-safe all-expiration TSLL snapshot; report only density / path /
   admission / control counters (`EVIDENCE_WAIT` reaffirmation exempt from streak).
2. **Off-hours / non-RTH strategy wake** → because pivot is required after two
   no-advances, choose a **materially different** non-quarantined economic mechanism
   or evidence class **outside** sector-breadth directional continuation and outside
   other closed families; complete a full Layered Edge Stack + predeclared falsifier.
3. **Observed floor met** → evaluate exact parked diagonal development 60% only;
   keep final 40% unread; no BS proxy substitution.

Hard bans: same-date churn; unchanged breadth retune; registry/paper force; shadow;
arm; broker; funding; live.

## Partial-phase boundary

Challenger writes critique + merge seed residue only. No commit, push, merge,
deterministic integration, or RUN COMPLETE. Finalizer repairs accepted findings,
re-runs verification, promotes learning, and prepares integration.

MOA_CHALL_DONE

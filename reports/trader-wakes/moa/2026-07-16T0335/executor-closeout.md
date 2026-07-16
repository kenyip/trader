# Executor closeout — 2026-07-16T0335

Phase: BUILD / L0 underlying discovery only
Role: GPT 5.6 Sol executor, only writer
Status: executor partial; challenger/finalizer/integration pending; no `RUN COMPLETE` claim
Outcome: `FAMILY_CLOSED`
Funnel: `F0_MECHANISM -> F0_MECHANISM_CLOSED`
Strategy advancement: false
Authority: L0 discovery only

## Strategy decision charter

Exact candidate: `MONTHLY_SECTOR_LEADER_CONTINUATION_BULL_CALL_35D_V1`

Exact family: `SECTOR_ALLOCATION_RELATIVE_STRENGTH_CONTINUATION`

Economic mechanism: monthly institutional and benchmark sector reallocations may be implemented over multiple sessions, so a liquid sector ETF that is already the 63-session relative-strength leader, remains above its 126-session trend, and leads the cross-sectional median materially may continue upward and outperform its same-date sector peers for another trading month.

Frozen geometry:

- fixed nine-original Select Sector SPDR panel: `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`;
- split/dividend-adjusted daily closes from 1998-12-22 through 2026-07-15, inner joined with no forward fill;
- signal only on the final completed session of each calendar month;
- rank on completed 63-session return; require leader return >0, completed close >SMA126, and leader-minus-panel-median return >=5 percentage points;
- next completed close entry and 20-session exit;
- same-date equal-weight basket of the eight nonleaders as the specificity control;
- 10-bps round-trip underlying hurdle for leader and control;
- chronological first 60% train and final 40% identity-sealed/outcome-unread;
- circular three-signal-date bootstrap and zero option pricing.

Conditional future structure only: one-lot 30-45 DTE $2-wide bull call debit spread on the selected leader, `capital_fit_usd=200`, width-bound planning `max_loss_usd=200` before debit slippage/closing friction, `max_lots=1`. This is planning geometry, not observed or proxy option evidence.

Frozen falsifier required at least 60 train signals and 10 years, no chronology/month-end/window/overlap/population/holdout/strict-JSON violations, leader mean after 10 bps >0.50%, positive frequency >=55%, paired excess versus nonleaders >=0.30%, paired-excess LB90 >0, worst-decile leader return >=-8%, and a weaker nonleader control. Any failure closes the exact family without formation-horizon, separation, SMA, hold, top-two, rank-weight, or option-wrapper salvage.

## Orientation and anti-thrash decision

The prior `MACRO_INFORMATION_RESOLUTION_TWO_CLOSE_PIVOT_REASSESSMENT` is closed by pivoting away: direct BLS access remains blocked, and another scheduled information-resolution event study would repeat the recently closed FOMC/Beige Book evidence class. The broad candidate-factory suggestion remained context rather than an order; a single frozen sector-allocation experiment was the smallest decision-changing test.

This is a materially new evidence class for the closed fixed-14-stock monthly 12-1 momentum family: a nine-sector ETF allocation panel, 63-session formation, same-date nonleader control, and approximately 1999-forward history. It uses the independent panel-construction reopen condition rather than retuning the prior stock panel.

Freedom audit: symbol, structure, and mechanism remained catalog-free; the choice was evidence-driven and not restricted to TSLA/TSLL, PCS, short premium, or a caller-selected NEXT.

## Train-only experiment

Claim artifact: `reports/trader-wakes/moa/2026-07-16T0335/monthly-sector-leader-train.json`

Raw SHA-256: `7ac37abc182c67dbf56bfaa572f13fc126200a79de6a9a6aef175a21b73886ba`

Population and partition:

- common adjusted-close panel start: 1998-12-22;
- 171 frozen eligible monthly signals;
- train: 102 signals across 17 years, 1999 through 2015;
- sealed holdout: 69 signals from 2015-04-30 through 2026-04-30;
- holdout identity SHA-256: `2691ebb857fc6552890c9b559535e6ed30cb49007410ca957d06d794f11fb464`;
- holdout outcomes unread; simulation false; option marks/pricing absent;
- train integrity violations: zero.

Train metrics after the labeled 10-bps hurdle:

- leader mean return: **-0.130819%** versus required >+0.50%;
- equal-weight nonleader mean return: **+0.732793%**;
- leader positive frequency: **48.0392%** versus required >=55%;
- paired leader-minus-nonleader mean: **-0.863612%** versus required >=+0.30%;
- paired median: **-1.105473%**;
- paired positive frequency: **36.2745%**;
- circular date-block LB90: **-1.455459%** versus required >0;
- leader worst-decile mean: **-9.375157%** versus required >=-8%.

Leader counts were `XLE=28`, `XLU=22`, `XLK=15`, `XLF=12`, `XLV=8`, `XLY=8`, `XLB=6`, `XLP=3`; no `XLI` signal entered the train population. This concentration is diagnostic and does not alter the frozen gates.

## Closed outcome

`SECTOR_ALLOCATION_RELATIVE_STRENGTH_CONTINUATION` / `MONTHLY_SECTOR_LEADER_CONTINUATION_BULL_CALL_35D_V1` is `FAMILY_CLOSED` at F0.

The failure is economic, not merely statistical density: the selected leaders lost 0.1308% on average after cost while contemporaneous nonleaders gained 0.7328%, producing a -0.8636% paired edge and -1.4555% LB90. Absolute hit rate and worst-decile quality also failed. A future bull-call wrapper would monetize the wrong signed forecast and cannot rescue the underlying mechanism.

Exact-family quarantine includes the same nine-sector panel with 42-126-session formation nudges, 3-8-point separation retunes, 10-30-session holds, SMA100-SMA150 trend nudges, or top-two/rank-weight variants. Reopening requires an independent panel construction, observed option-flow evidence, or another materially different economic mechanism/evidence class.

No holdout opening, option simulation, registry insertion, F1/F2/L1 claim, living candidate, quality leader, capital seat, paper packet, shadow, arm, broker, funding, or live authority was earned.

## Search information versus strategy advancement

Search information: added and exercised a reusable train-only monthly dynamic-leader lab with a fixed liquid sector panel, exact month-end/next-close chronology, same-date nonleader specificity control, sealed chronological holdout, source hashes, strict JSON, dependence-aware uncertainty, and fail-closed capital/option labels.

Strategy advancement: none. The exact mechanism failed six economic/risk gates and remains closed at F0. Tooling and test output are not counted as strategy progress.

## Evidence validity critique

- Leakage/lookahead: features stop at the completed month-end signal; entry is the next completed close. A future-price perturbation cannot change the first frozen identity. The final 40% serializes identity only.
- Contract availability: no historical option contract, debit, IV, skew, or fill claim exists. The $200 bull-call width is conditional planning geometry only.
- Costs: 10 bps round trip is labeled underlying discovery friction, not option friction. Because the result is strongly negative, missing option spread friction cannot reverse the close in the favorable direction.
- Provenance: every ETF source reports `yfinance auto_adjust=True`, 6,931 rows, 1998-12-22 through 2026-07-15, with per-file SHA-256 in the claim artifact.
- Population purity: fixed present-day sector ETF survivors, inner join, no forward fill. `XLC` and `XLRE` are deliberately excluded to preserve the long common sample; historical constituent membership is not reconstructed. Generalization beyond this panel is not claimed.
- Dependence: uncertainty uses circular three-signal-date blocks; month-end windows are non-overlapping.
- Ranking completeness: all nine frozen names must be finite at every selected signal; the leader and all eight peers are explicit.
- Path realism: only entry-to-20-session close returns are measured. Intraperiod option P&L, management, assignment, IV, and executable fills remain unmeasured.
- Capital fit: future one-lot width bound is $200 and max_lots is 1, but no capital seat can be earned from proxy-free underlying discovery.

## Verification

- New focused behavioral/boundary/negative-control suite: `7 passed`.
- Focused plus adjacent sector/cross-section/compounding regression set: `50 passed`.
- Full pytest: `419 passed + 18 subtests` in 23.78s.
- Repository `just test` smoke: exit 0; both TSLA and TSLL returned `STAND ASIDE` from the existing live.py research smoke. No broker action occurred.
- Deterministic cache replay: payload equality true after excluding only `generated_at`; outcome, train metrics, source provenance, and sealed holdout identity reproduced.
- Income coverage refreshed at 2026-07-16T0349: 21 catalog structures / 246 hypotheses / 70 evolve artifacts / no quality leader.
- `git diff --check`: green.
- No completion/integration claim: branch remains intentionally dirty with executor artifacts for challenger/finalizer review; no commit, merge, push, or postflight was attempted.

## Durable learning

Future Trader can now test dynamic monthly sector leadership without truncating history to late-listed sector ETFs, compare the chosen leader against an outcome-independent same-date peer basket, and seal the later chronology before inspecting train outcomes. The observed result is a strong anti-edge: intermediate-term sector leaders underperformed their peers in the frozen train population, so the next loop must not spend another wake polishing the same rank/hold/trend geometry.

No phase or B-check changed. Readiness remains BUILD / NOT READY, with zero living candidates, zero leaders, and zero capital seats.

## Exactly one NEXT seed

`TRAIN_ONLY_DEFINED_RISK_CANDIDATE_FACTORY_V1`: build a cheap predeclared train-only funnel across several genuinely independent, non-quarantined economic mechanisms, but require each row to carry a complete Layered Edge Stack and a frozen specificity control before outcome access. Exercise the factory in the same wake and close exactly one named survivor as `STRATEGY_ADVANCED` F0->F1 or one named mechanism as `FAMILY_CLOSED`; do not count the factory itself as strategy progress, reopen sealed holdouts, retune this sector-leader family, or claim L1/paper/shadow/arm/live authority.

MOA_EXEC_DONE

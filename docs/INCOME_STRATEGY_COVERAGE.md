# Income Strategy Coverage Map

**Goal:** steady income on $3k sleeve via multi-structure search, not one-name monomania.
**Updated:** 2026-07-12

## Axes we care about

| Axis | Meaning | How we use it |
|---|---|---|
| **Structure** | What we trade (PCS, CCS, IC, …) | `STRUCTURE_CATALOG` + sim engine |
| **Symbol** | Where | `universe.yaml` research rank |
| **Time bias** | DTE bucket, hold days, entry weekday/session | `pcs_time_bias_grid.py` covers multi-hyp DTE/profit-target/DTE-stop + entry-weekday/cost slices; lagged completed-bar close-shock filters and chronological selection/holdout falsification are built; session pending |
| **Direction / regime / volatility bias** | Bull / bear / neutral / compression / expansion / stand-aside | Shared-window scoreboard plus `regime_router_sim.py`: one no-lookahead PCS/CCS/IC position with standalone controls; router, four adjacent-daily PCS families, a multi-horizon trend-pullback PCS family, and a bearish volatility-expansion CCS family were rejected |
| **Risk fit** | 1-lot max_loss, open risk, BP | capital_fit + quality bar |
| **Falsify** | Regime windows + cost/slip | B3/B4 scripts + fixed-dollar per-leg half-spread axis across all defined-risk proxy sims |

## Catalog status (sim today)

| Structure | Sim engine | Income role | Direction bias | Time knobs | Sleeve-fit path | Status |
|---|---|---|---|---|---|---|
| `put_credit_spread` | pcs_sim | Core bullish/neutral credit | Prefer put; stand aside bear | DTE, width, credit% | Strong | Active research; **no living quality leader** |
| `call_credit_spread` | pcs_sim | Bearish/neutral credit | Prefer call | DTE, width | Strong | Active research; OPEN_CCS paper partial |
| `iron_condor` | pcs_sim | Neutral or bullish-skewed range credit | Range-bound / high IV; side-specific deltas/widths + regime gate supported | DTE, per-side delta/width, regime | Strong if width tight | Active; symmetric and capped-jade-shaped asymmetric grids cost-rejected |
| `calendar_spread` | calendar_sim | Long-debit time spread | Neutral-to-bullish put calendar | Front/back DTE/IV multipliers, put skew, target, stop | Defined debit | Assumption-aware scaffold + chronological OOS; all tested SHIPs cost-fragile |
| `diagonal_spread` | diagonal_sim | Long-debit directional time spread | Bullish; stand aside bear | Short/long DTE and delta, expiry IV multipliers | Defined debit | Scaffold + B3/B4 + exact-DNA OOS + announcement-time dividend/short-call assignment guard; archived Nasdaq provider is usable only for supported eventful listings; AAPL has bounded 40/40 issuer corroboration for announcement date/amount/common-stock identity, not ex-date or pre-2016 history; SMCI remains provider-blocked and rejected on zero recent holdout entries/worse ml-dd |
| `butterfly_spread` | butterfly_sim | Long-debit same-expiry convexity | Neutral-to-bullish target pin; stand aside bear | DTE, body delta, symmetric wing width | Defined debit | Minimal BS scaffold + evolve/B3/B4; observed surfaces and pin/assignment realism missing |
| `iron_butterfly` | iron_butterfly_sim | Credit same-expiry neutral income | Neutral pin; stand aside directional regimes | DTE, symmetric wing width, credit floor | Defined width less credit | Minimal BS scaffold + evolve/B3/B4; tested proxies cost-fragile; observed surfaces and pin/assignment realism missing |
| `broken_wing_iron_butterfly` | iron_butterfly_sim | Asymmetric credit income | Bullish/not-bearish; wider put wing, narrower call wing | DTE, near/far wing widths, credit floor | Defined widest wing less credit | Scaffold + evolve/B3/B4/fixed-cost wiring; first SMCI/XOM set cost-rejected and DD-heavy |
| `put_ratio_backspread` | put_ratio_backspread_sim | Bearish convexity / crash payoff | Bear/neutral; stand aside bull | DTE, short-put delta, strike width, loss exit | Defined valley loss | Scaffold + structure-pure evolve/B3/B4/fixed-cost wiring; SMCI/BAC cost survivors still fail absolute DD/risk gates |
| `collared_covered_call` | collar_sim | Stock-backed income with protective floor | Bullish/not-bearish; non-levered spot*100≤$3k | DTE, put/call delta, profit/loss exits | Full 100-share notional + downside floor | 1,152-row exact management grid rejected: zero rows meet $75 window-DD on both cost axes; dividends/assignment unmodeled |
| `bull_call_debit_spread` | debit_vertical_sim | Long-debit bullish direction | Bull/neutral; stand aside bear | DTE, long delta, width | Defined debit | Minimal BS scaffold + evolve/B3/B4 + announcement-time dividend/short-call assignment guard; archived Nasdaq provider works for supported eventful listings and AAPL has bounded issuer corroboration for announcement date/amount/common-stock identity only; ex-dates and observed surfaces remain missing |
| `bear_put_debit_spread` | debit_vertical_sim | Long-debit bearish direction | Bear/neutral; stand aside bull | DTE, long delta, width | Defined debit | Minimal BS scaffold + evolve/B3/B4; observed surfaces and short-put assignment realism missing |
| `regime_short_premium` | single-leg | Regime-directed premium | Regime side | Short/long DTE | Weak on levered names | Research toy unless resized |
| `short_put_credit` | single-leg | Bull put premium | Put-only | DTE | Weak CSP-scale | Research toy for $3k |
| `short_call_credit` | single-leg | Bear call premium | Call-only | DTE | Weak | Research toy |
| `short_dte_aggressive` | single-leg | Fast theta | Regime | 2–5 DTE | Weak | Research only |
| `long_dte_conservative` | single-leg | Slow theta | Regime | 21–45 DTE | Weak | Research only |
| `wheel_assignment` | single-leg + wheel | Assignment cycle | Put→CC | Wheel DTEs | Usually oversized | Research / personal desk only |
| `cash_secured_put` | single-leg | CSP | Put | DTE | Usually oversized | Research toy |
| `roll_defend` | single-leg | Management | — | roll DTE | — | Management gene |

## Gaps (build order for income lab)

Priority for **new sim classes** (not just knob polish):

1. **Calendar observed-surface realism** — explicit front/back IV and put-skew assumptions + chronological OOS now exist; historical expiry-specific option IV inputs are still absent
2. **Diagonal realism** — scaffold, exact-DNA chronological OOS+density, an injectable announcement-time dividend/short-call assignment guard, and a fail-closed archived Nasdaq declaration-date provider exist; AAPL has 40/40 issuer concordance for announcement date/amount/common-stock identity over a bounded 2016-07-26–2026-04-30 window, while ex-dates/earlier events remain single-source; the source is unsupported/ambiguous for some symbols and does not replace observed expiry-specific surfaces
3. **Butterfly realism** — long call and credit iron-butterfly scaffolds exist; observed surfaces and pin/assignment realism remain
4. **Debit-vertical realism** — bull-call/bear-put scaffolds exist; bull-call has the same injectable guard, supported-listing archived declaration-date provider, and bounded AAPL issuer corroboration, while ex-dates, observed surfaces, and short-put assignment remain
5. **Jade lizard / other skewed-risk structures** — broken-wing credit iron butterfly and defined-risk put ratio backspread scaffolds exist; jade lizard remains undefined downside risk unless capped
6. **Covered call on cheap shares / LEAPS** only if max_loss fits $3k (usually fails → keep on main desk)

Until a gap has a sim engine, evolve may **document the gap** and optionally scaffold code — never invent SHIP metrics.

Cost realism now includes `scripts/defined_risk_fixed_cost_stress.py`: one uniform fixed-dollar option-price half-spread per leg, applied adversely at entry and exit for PCS/CCS/IC/iron butterfly/calendar/diagonal/butterfly/debit-vertical proxies. It is a sensitivity axis, not observed quote evidence. `scripts/option_quote_observations.py` adds a normalized bid/ask archive boundary; capture now fetches every available expiration by default, appends atomically without duplicating identical rows, and reports a fail-closed three-market-date density gate. Synthetic fixtures are calibration-ineligible. `scripts/observed_quote_coverage.py` adds an exact non-future PCS/CCS/IC strategy-leg/expiry/strike/time join and rejects incomplete entry/exit coverage. `ArchivedContractGridProvider` turns normalized observed rows into market-date-specific actual expiry/right/strike grids with request coverage counters; missing dates fail closed. Synthetic mode remains explicit for discovery. The all-expiration TSLL archive still covers only 2026-07-11, so provider-backed historical simulation and observed-cost calibration remain blocked until at least three distinct market dates (`docs/OPTION_QUOTE_DATA_BOUNDARY.md`).

The defined-risk time lab at `scripts/pcs_time_bias_grid.py` compares one or more registered PCS/CCS/IC DNA across DTE, profit target, DTE-stop, and entry-weekday slices while retaining 1-lot capital fields. It can rerun the same grid with explicit slippage. `scripts/pcs_time_variant_stress.py` applies exact B3+B4 to an unregistered winning time row without mutating the registry, including an optional spread-width override. Session-time slices remain absent, and a full-history winner still requires competitive ml/dd before registration or promotion.

The direction lab now has a paper-only comparator at `scripts/pcs_direction_scoreboard.py`. It consumes dated B3/B4 JSON, intersects yearly and canonical labels so structures are judged on shared windows, and ranks positive non-vacuous 5% slip before B3/B4 and ml/dd. `trader_platform/research/regime_router_sim.py` adds a current-row-only shared-position router (bullish→PCS, bearish→CCS, neutral high-IV→IC, otherwise stand aside) and `scripts/pcs_regime_router_lab.py` compares it against standalone controls with baseline, 5% slip, fixed-$0.01/leg, window, routing-purity, no-reentry, independently recomputed ledger checks, and a selected→accepted→exact counterfactual reject-reason funnel. The default-DNA eight-symbol run selected CCS 2,427 times and IC 2,592 times but accepted only 19/23; credit-floor rejection dominated. `pcs_close_shock_lab.py` adds lagged completed-bar return/volume entry bounds and mirror/unconditional controls; its lone full-sample SMCI pass did not survive chronological train-selection/holdout testing. `pcs_momentum_walkforward_lab.py` adds strict 60/40 train selection and untouched holdout for prior-bar return plus RSI; its first eight-symbol bullish-momentum run produced zero complete holdout passes. `pcs_pullback_rolling_origin_lab.py` then tested one predeclared 7-DTE mild-pullback DNA without a grid across three expanding-origin folds per symbol; zero of eight symbols passed all folds, with only 3/24 train folds clearing both proxy cost gates. `pcs_vol_compression_rolling_origin_lab.py` adds a fail-closed prior-bar `hv_20/hv_60` filter and tests one predeclared ratio≤0.80 14-DTE PCS against unconditional and ratio≥1.20 expansion controls across the same rolling-origin design. Zero of eight symbols passed any train gate or complete fold. `ccs_vol_expansion_rolling_origin_lab.py` tests the direction-aligned complement: one 14-DTE CCS after prior-bar ratio≥1.20 plus non-positive return. It likewise produced zero of 24 train-gate or complete-fold passes. All persisted strategy summaries for both volatility families retained exact ledger/signal integrity, so these signal families remain research-rejected rather than tuned.

## Time × direction research recipe (BUILD)

Each dual-lab wake should pick **one** of:

A. **Structure rotation** — sim under-covered catalog classes on top research symbols
B. **Time bias grid** — same structure, DTE / profit_target / dte_stop mutants
C. **Direction bias grid** — PCS vs CCS vs IC under bull/bear/neutral windows
D. **Quality falsify** — B3+B4 + ml/dd vs current capital example
E. **Sim class build** — implement one missing structure’s sim (code + smoke)

Do not run A–E every wake. Leave one NEXT seed.

## Quality bar (capital path)

A DNA may sit on capital path only if:

- Defined risk preferred; 1-lot max_loss competitive for $3k
- Full-history not thin vanity SHIP
- B3 soft-hold + B4 cost soft-hold
- With no living leader, clear explicit absolute gates: non-vacuous after-cost SHIP, B3 hold, max loss ≤$300, window max DD ≤$75, and dense-negative windows ≤5; `b195f5fe` is historical context only
- B6 live-clock paper sample still separate

**Diversify-for-fear is lazy.** Multi-name is discovery, not a quota seat.

## Commands

```bash
just trader-income-coverage
just trader-build-lab
just evolve-tick -- --apply --structures put_credit_spread call_credit_spread iron_condor --top-symbols 8 --mutants 2 --sleeve-usd 3000
.venv/bin/python scripts/pcs_time_bias_grid.py --hyp hyp_dna_tsll_put_credit_spread_b195f5fe --period 5y --out .cache/platform/time_bias_lab.json
```

## History

### 2026-07-10 — Minimal calendar simulator + first falsification

Added `calendar_spread` to Strategy DNA with a daily-bar Black-Scholes long put-calendar simulator, defined debit risk fields, evolve dispatch, and B3/B4 dispatch. The first registered TSLL calendar SHIP (`d5e00af5`) fit the sleeve but failed B4 badly at 5% slip (−$895.64 across 94 trades) and had window DD $230.79, so it remains research-only. The simulator still lacks expiry-specific IV term structure/skew; its baseline SHIP is not readiness evidence.

### 2026-07-10 — Defined-risk time-bias grid scaffold

Added a real-sim DTE × profit-target × DTE-stop grid for registered defined-risk hypotheses. Weekday/session entry slicing remains the precise time-axis gap; grid winners remain research-only until B3+B4.

### 2026-07-10 — Calendar term/skew assumptions + OOS falsification

Added explicit front/back IV multipliers and put-skew inputs to `calendar_sim`, mutation bounds, synthetic smoke coverage, and `scripts/calendar_oos_stress.py` for chronological registered-DNA splits. Three assumption-aware calendar SHIPs passed baseline/OOS checks but all failed non-vacuous B4 at 5% slip, so none entered the capital path. Historical expiry-specific option IV surfaces remain the realism gap.

### 2026-07-10 — Minimal diagonal simulator + first falsification

Added `diagonal_spread` to Strategy DNA with a daily-bar Black-Scholes long-call diagonal simulator, explicit short/long expiry IV multipliers, defined debit risk, evolve dispatch, synthetic smoke, and B3/B4 dispatch. SMCI `d1017453` is a non-vacuous after-cost SHIP at 5% slip (24 trades / +$107.35) and regime soft-holds, but fails L1: max loss $294.03 and window DD $153.30 are worse than leader $76.32 / $74.85, while entries concentrate in 2022–23 with zero in 2025–26. It remains candidate/research-only.

### 2026-07-10 — Diagonal exact-DNA OOS rejection

Added `scripts/diagonal_oos_stress.py` with chronological 60/40 exact-DNA baseline/5%-slip reruns and entry-year density reporting. SMCI `d1017453` retained its old-train result but produced zero entries in the 2024-12-17–2026-07-10 holdout at both baseline and 5% slip. The proxy edge is capital-path rejected; observed historical surfaces and assignment realism remain prerequisites before revisiting it.

### 2026-07-11 — Shared-window direction scoreboard

Added `scripts/pcs_direction_scoreboard.py` with tests. The first shared 15-window PCS/CCS/IC comparison retained TSLL PCS `b195f5fe` as the relative ml/dd leader, but no row was positive at 5% slip. New SMCI/NFLX calendar SHIPs were also cost-rejected. The scoreboard closes the basic direction-comparison plumbing gap without advancing readiness.

### 2026-07-11 — Long call butterfly scaffold + cost rejection

Added `butterfly_spread` with a same-expiry symmetric long-call Butterfly BS simulator, defined debit/max-loss fields, evolve dispatch, synthetic smoke, and B3/B4 dispatch. Six registered butterfly candidates all regime soft-held, but every one failed non-vacuous 5% leg-slip stress; the best baseline rows therefore remain research-only and no L1 edge emerged. Observed option surfaces, pin/assignment realism, and the iron-butterfly credit variant remain gaps.

### 2026-07-11 — Bull-call / bear-put debit vertical scaffold + rejection

Added `bull_call_debit_spread` and `bear_put_debit_spread` through a shared same-expiry BS simulator with defined debit/max-loss, catalog/evolve/B3/B4 dispatch, synthetic tests/smoke, and B3/B4 dispatch. One focused run registered eight candidates. All eight failed non-vacuous 5% leg-slip stress; the best baseline MU bull call changed from n116 / +$2,303.91 to n126 / −$15,146.17, and its $232.45 max loss / $569.66 window DD also missed the PCS quality bar. No L1 edge emerged; both structures remain research-only.

### 2026-07-11 — Entry-weekday time slices + cost-aware rejection

Extended the PCS time grid and simulator with entry-weekday gating plus explicit slippage reruns. The headline Thursday 14-DTE row was vacuous at 5% slip (zero trades). A 30-DTE all-day row remained non-vacuous after cost (21 trades / +$10.52) and regime soft-held, but missed L1 because window max DD $97.14 and seven dense-negative windows were worse than leader $74.85 / five. No candidate was registered or promoted.

### 2026-07-11 — Multi-hyp cost-aware time lab

Extended `pcs_time_bias_grid.py` to compare multiple registered PCS/CCS/IC hypotheses in one cost-aware grid and added exact transient variant B3+B4 tooling. A BAC PCS Friday 7-DTE / PT35 / stop5 row was dense and positive at 5% slip (189 trades / +$690.05), with B3 soft-hold and two dense-negative windows, but missed L1 because max loss $184.55 and window max DD $87.29 were worse than leader $76.32 / $74.85. It remains unregistered research only.

### 2026-07-11 — BAC PCS width-resize falsification

Added a spread-width override to exact transient B3+B4. The BAC Friday 7-DTE row at $1 nominal width remained dense and positive at 5% slip (196 trades / +$397.68), improved baseline window DD to $69.64 with two dense-negative windows, but still missed the leader max-loss bar ($87.64 vs $76.32). A nominal $0.50 width produced identical metrics because the proxy rounded to the same effective strikes, so the width path was rejected without further tuning; readiness remains L0.

### 2026-07-11 — Credit iron-butterfly scaffold + cost rejection

Added `iron_butterfly` with a same-expiry ATM short straddle plus symmetric long wings, defined max loss, catalog/evolve/B3/B4 dispatch, tests, and synthetic smoke. The focused 36-DNA population produced no iron-butterfly SHIP at 2y. Five-year B3 made SMCI `8444c65b` a baseline SHIP and both tested candidates regime soft-held, but 5% adverse leg slip produced dense REJECTs (SMCI n251/−$29,018.86; TSLL n180/−$12,172.17). No L1 edge emerged; the proxy class remains research-only.

### 2026-07-11 — Uniform fixed-dollar defined-risk cost axis

Added `half_spread_per_leg` entry/exit pricing to PCS/CCS/IC and credit iron-butterfly sims, plus `scripts/defined_risk_fixed_cost_stress.py` and synthetic tests. At a $0.01 per-leg half-spread (round trip $4 per vertical / $8 per four-leg structure), TSLL PCS `b195f5fe`, AMD IC `b3056133`, SMCI iron butterfly `8444c65b`, and TSLL iron butterfly `486c4c32` were all negative. The axis rejects the representative set without relying on cadence-distorting percentage slip, but remains sensitivity rather than observed quotes.

### 2026-07-11 — Fixed-dollar cost axis completed across proxy sims

Extended adverse `half_spread_per_leg` entry/exit pricing and the uniform stress runner to calendar, diagonal, long butterfly, and debit-vertical proxies. TSLL calendar `fcc76896` remained dense and positive at $0.01 per leg (116 trades / +$298.28; max loss $66.97), but fixed-cost max DD rose to $115.81 versus the $74.85 leader bar, so it failed the proxy quality bar; Black-Scholes proxy results cannot earn L1. New PLTR/NFLX/XOM calendars that survived $0.01 had materially worse max-loss/DD; new TSLA/MU butterflies and the TSLL debit vertical failed the fixed-dollar axis. Observed quotes remain the next realism boundary.

### 2026-07-11 — Observed quote archive boundary

Added a validated normalized bid/ask observation adapter, synthetic fixture smoke that is explicitly barred from calibration, and forward-only current yfinance snapshot capture. A live TSLL snapshot returned 70 bid/ask rows with median per-leg half-spread $0.035, but one cross-section is not historical B3/B4 evidence. Installed yfinance exposes current chains only; no verified no-paid historical chain backfill was found, so readiness stays L0.

### 2026-07-11 — Exact observed leg/time coverage reject gate

Added a non-future exact-contract join for registered PCS/CCS/IC simulated entry and exit legs. Against the only 70-row TSLL snapshot, leader `b195f5fe` required 228 leg observations and matched 0, correctly returning `REJECT_INSUFFICIENT_COVERAGE`. Join plumbing is closed; forward archive density blocks only observed-option replay/calibration claims, not independent historical-underlying/Black-Scholes-proxy discovery, and no proxy metric was promoted.

### 2026-07-11 — Friday weekly-expiry realism and leader rejection

PCS/CCS/IC entries now select the first Friday on or after target DTE and use the resulting actual DTE for pricing and management. The exact join now emits Friday expirations and still rejects calibration at 0/248 matched legs. B3+B4 restress changed `b195f5fe` to full n62/+$42.54, max loss $75.35, window max DD $88.39, and 5% n13/−$13.18; because DD deteriorated beyond the prior $74.85 quality bar and after-cost evidence remains thin/negative, it is removed from the capital path. `l1_hyp_ids=[]`.

### 2026-07-11 — Injectable actual contract-grid boundary

Added an optional PCS/CCS/IC contract-grid provider that supplies symbol/date-specific expirations and right-specific strikes. Required mode is fixture-tested to fail closed when coverage or a valid wing is missing; synthetic Friday/rounded-strike discovery remains the default and is labeled in sim metrics. One free pop36 produced three defined-risk SHIPs, but all failed the L1 after-cost bar: SMCI/NFLX calendars were dense 5% REJECTs and the tight-risk TSLA butterfly collapsed to n529/−$94,077.49. No capital path was restored.

### 2026-07-11 — Archive-backed contract-grid replay

Added a market-timezone-aware provider that converts normalized observed quote archives into exact date-specific expiry/right/strike grids and reports covered versus missing requests. The existing 70-row TSLL snapshot replay covered its single 2026-07-11 market date and failed closed for 2026-07-10, proving the plumbing but not historical density. One required pop36 produced three new defined-risk SHIPs; all failed the non-vacuous after-cost proxy metric bar; proxy option marks cannot earn L1, so the capital path remains empty.

### 2026-07-11 — Append-safe all-expiration archive capture

Current-chain capture now requests all available expirations by default and writes through an atomic, history-preserving, identical-row-deduplicating archive path. Density reporting fails closed below three distinct New York market dates. The first all-expiration TSLL run captured 600 observed quotes across 12 expirations but still only one market date, so observed-grid evolve and provider-backed historical option replay remain blocked. Independent broad historical-underlying/Black-Scholes-proxy discovery remains available at L0; no quality leader exists.

### 2026-07-11 — Broken-wing credit iron butterfly scaffold + rejection

Added a bullish/not-bearish broken-wing credit iron butterfly using a wider put wing and narrower call wing, with enforced strike-grid asymmetry, defined widest-wing-minus-credit risk, evolve/B3/B4/fixed-cost dispatch, and tests. Three baseline SHIPs across SMCI/XOM all failed 5% cost stress and became negative at a $0.01 per-leg half-spread; every window max drawdown exceeded the absolute $75 gate. The family is research-only and creates no L1 leader.

### 2026-07-11 — Put ratio backspread scaffold + risk rejection

Added a bearish 1x2 put ratio backspread with exact signed payoff, closed-form valley max loss, structure-pure evolve filtering, and B3/B4/fixed-cost dispatch. The pure 22-DNA run produced six baseline SHIPs. SMCI remained SHIP at 5% slip and $0.01 per-leg cost but failed regime hold, max loss ($365.81), and window DD ($530.47); BAC regime-held and remained positive at $0.01 per leg but was negative at 5% slip and had window DD $149.86. Both miss the absolute $300/$75 gates, so no L1 leader exists.

### 2026-07-11 — Shared-position regime router rejection

Added a no-lookahead shared-position PCS/CCS/IC router and an eight-symbol falsification lab with identical-loop standalone controls, baseline/5%-slip/$0.01-per-leg costs, yearly/6m windows, routing-purity and no-same-bar-reentry checks, plus independent PnL/DD recomputation. None of TSLL, SMCI, TSLA, PLTR, AAPL, AMD, ARM, or QQQ cleared the absolute gates. Five-percent slip was mostly vacuous (0–4 trades), while every dense baseline missed the $75 window-DD gate; the family is rejected this cycle and no L1 leader exists.

### 2026-07-12 — Router entry-acceptance funnel

Added selected/accepted/rejected counts and implementation-counterfactual rejection reasons to the same eight-symbol router. All 96 policy/mode funnels reconciled. Baseline selection was not the bottleneck: CCS selected 2,427 bars but accepted 19 (0.78%); IC selected 2,592 but accepted 23 (0.89%). Credit-floor rejection accounted for 2,145 CCS and 1,926 IC rejects. This explains the prior PCS-heavy population without tuning a family already rejected on costs/drawdown; no hypothesis was registered or promoted.

### 2026-07-12 — Collared covered-call scaffold + reject-unless falsify

Added `collared_covered_call`: long 100 shares + long protective put + short covered call. The scaffold is capital-honest for the $3k sleeve: `capital_fit_usd` is full 100-share notional plus any net option debit, `max_loss_usd` is the protected downside floor, levered/exotic symbols (including TSLL) fail closed, and no-close-bar reentry is tested. Expanded the research universe with non-levered sub-$30 optionables (F/SOFI/AAL/PFE/SNAP/NIO/CCL). Immediate lab `.cache/platform/collar_scaffold_lab_2026-07-12T0205.json` rejected the class this cycle: 8 eligible names, no 5% + $0.01 survivor; dense names miss the $75 window-DD gate and SMCI is vacuous n=1. No proxy SHIP was registered; dividends and early assignment remain unmodeled.

### 2026-07-12 — Collar management-grid falsification

Closed the collar gate loophole that allowed non-positive after-cost PnL to pass, then ran 1,152 exact DNA rows across eight non-levered sub-$30 names, four DTEs, three put deltas, three call deltas, two profit targets, and two loss exits under both 5% slip and $0.01-per-leg costs. Independent ledger recomputation and no-close-bar-reentry checks passed for every row. Although 258 rows were positive on both cost axes and every row stayed below $300 worst-case loss, zero rows met the $75 window-DD gate; the tightest worst-axis result was SMCI at $142.48. The family is rejected from capital search this cycle with no registration or promotion.

### 2026-07-12 — Asymmetric capped-jade condor falsification

Added transient side-specific put/call delta and width knobs plus an explicit allowed-regime gate to `pcs_sim` iron condors. Corrected the condor close-debit boundary from the sum of both non-overlapping wing widths to the widest wing, so simulated loss cannot exceed the stated widest-wing-minus-credit payoff. A 96-row, six-symbol bullish/neutral grid was dense and produced 29 positive baseline SHIPs, but zero row remained positive under either 5% adverse leg slip or a $0.01-per-leg half-spread; all 288 full-run ledgers recomputed exactly with zero close-bar re-entry. The asymmetric family is rejected this cycle; observed surfaces remain required for any L1 claim.

### 2026-07-12 — Lagged close-shock PCS falsification

Added optional current-row bounds for return, volume, and RSI to `pcs_sim`, plus an explicit signal lag so completed close/volume features can be consumed only on a later bar. An eight-symbol, 64-DNA downside-close-shock PCS grid used unconditional and mirror-up controls, 5% slip, $0.01-per-leg cost, exact ledgers, and no-reentry/signal-purity checks. One full-sample SMCI row passed the proxy absolute gates, but a chronological 60/40 train-selection/holdout test selected PLTR and TSLL instead; PLTR holdout drawdown was $155.05/$122.80 and TSLL holdout PnL was negative on both cost axes. Decision: reject this family this cycle; no registration, L1, or living leader.

### 2026-07-12 — Lagged bullish-momentum PCS walk-forward falsification

Added `scripts/pcs_momentum_walkforward_lab.py`, a strict per-symbol 60/40 chronological harness that ranks a 16-row 7/14-DTE × prior-day return × RSI grid only on train, evaluates one selected DNA once on untouched holdout, and checks 5% leg slip, $0.01-per-leg cost, exact ledgers, no close-bar re-entry, signal-lag purity, max loss, and drawdown. The final gate requires both train and holdout gates; inclusive zero-return mirror controls are explicitly disjoint. None of eight symbols passed the complete walk-forward gate. BAC was the sole train-gate pass; holdout remained positive at 5% slip (42 trades / +$42.88) but failed fixed cost (39 / −$53.59) and drawdown ($94.72/$96.12). Dense-negative holdout windows are currently fixed-cost-only and labeled as such. No hypothesis, L1 seat, or living leader was created.

### 2026-07-12 — Predeclared mild-pullback rolling-origin PCS falsification

Added `scripts/pcs_pullback_rolling_origin_lab.py` to test exactly one 7-DTE lagged mild-pullback DNA (`ret_1d≤−0.5%`, RSI 35–50) across BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL. Each symbol used expanding 40/60/80% train endpoints followed by non-overlapping 20% holdouts; every fold required its train gate plus untouched holdout 5% and $0.01-per-leg positive SHIP, max loss ≤$300, DD ≤$75, and exact ledger/signal integrity. Zero of eight symbols passed all three folds; only PLTR fold 2, SMCI fold 1, and AMD fold 0 passed train, and each failed its holdout. All 286 persisted candidate/control/window summaries had exact integrity with zero signal or same-bar violations. The family is rejected without grid expansion or registration; proxy evidence cannot earn L1.

### 2026-07-12 — Realized-volatility-compression PCS falsification

Added a fail-closed `hv_20/hv_60` PCS entry filter and `scripts/pcs_vol_compression_rolling_origin_lab.py`. One predeclared 14-DTE compression DNA (prior completed-bar ratio ≤0.80) was tested across BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL using expanding 40/60/80% train gates, untouched following 20% holdouts, 5% leg-slip and $0.01-per-leg costs, unconditional and ratio≥1.20 expansion controls, exact ledger/signal checks, and the absolute $300 max-loss/$75 drawdown gates. Zero of 24 train folds and zero of 24 complete folds passed. Minimum strategy-axis sample counts ranged from two to seven by symbol and worst fold drawdown ranged from $119.35 to $425.53; all 286 candidate/control/window summaries had exact integrity with zero signal violations or same-bar re-entry. The family is rejected without threshold/DTE tuning or registration; observed option-history density remains required for any L1 claim.

### 2026-07-12 — Realized-volatility-expansion CCS falsification

Added `scripts/ccs_vol_expansion_rolling_origin_lab.py` to test one predeclared direction-aligned 14-DTE CCS after prior completed-bar `hv_20/hv_60 >= 1.20` and non-positive return. Across the same eight-symbol expanding 40/60/80% rolling-origin design, zero of 24 train folds and zero complete folds passed both proxy cost axes. Minimum strategy-axis samples were 0–6; worst per-symbol fold drawdown was $76.20–$347.91 while worst one-lot max loss was $94.71–$237.36. Unconditional and compression CCS controls were persisted, and all 286 strategy/control/window summaries had exact ledgers with zero signal or same-bar violations. The family is rejected without tuning, registration, or L1 claim.

### 2026-07-12 — Multi-horizon trend-pullback PCS falsification

Extended the fail-closed PCS signal boundary to lagged `ret_5d`, `ret_14d`, and EMA-stack bounds, then tested one predeclared 21-DTE PCS after a non-positive five-day return inside a ≥3% fourteen-day return and bullish EMA stack. Across BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL and three expanding rolling-origin folds, four of 24 train gates passed but zero complete folds survived untouched holdouts under both 5% leg slip and $0.01-per-leg costs. All 286 strategy/control/window summaries had exact ledgers with zero signal or same-bar violations. The multi-horizon family is rejected without threshold tuning or registration; option marks remain Black-Scholes proxies and cannot earn L1.

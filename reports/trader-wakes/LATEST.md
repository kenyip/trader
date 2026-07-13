# Trader historical BUILD unblock — 2026-07-12T1735

WAKE: 2026-07-12T1735 PDT (Sunday; market closed)
PHASE: BUILD / L0
SLEEVE: $3,000
PAPER_ONLY: true
OUTCOME: REPAIRED

## Diagnosis

The 1700 wake incorrectly let a future TSLL archive dependency dominate orientation. The absence of a second/third forward option snapshot blocks only observed-option replay/calibration claims. It does not remove 58 cached 1y/2y/5y/10y historical-underlying datasets, eight option-proxy simulator modules, broad symbol/strategy DNA freedom, rolling-origin falsification, negative controls, or simulator capability work.

Corrected model:

1. `data.py` obtains real historical underlying OHLCV through yfinance and derives lagged features/regimes. `pcs_sim` (PCS/CCS/IC), calendar, diagonal, butterfly, debit vertical, iron butterfly, put-ratio backspread, collar, regime-router-over-PCS, and the single-leg StrategyConfig/backtest path replay those real underlying bars but mark option legs with Black-Scholes/`iv_proxy`, rounded/listed-Friday assumptions, and proxy costs. They are L0 discovery/falsification only.
2. `simulator/market_generator.py` block-bootstraps and perturbs historical underlying segments. Its generated paths are synthetic stress/training data, not direct historical replay and not observed-option evidence.
3. `ArchivedContractGridProvider` and exact leg/time joins can constrain availability using timestamped archived rows, but the local TSLL archive is only one current cross-section/date (600 rows, 12 expirations) and matches 0/248 historical leg requirements. Cached PMCC TSLA/NVDA parquets are current chain cross-sections, not timestamped historical surfaces.
4. Installed yfinance 1.5.1 exposes current `Ticker.options`/`option_chain`, not historical chains. There is no broad local/no-credential historical bid/ask surface or installed external provider adapter. Real historical replay remains blocked on an external licensed dataset/provider decision.
5. Three distinct forward dates can validate capture/dedup/date-grid/join plumbing or begin observed-cost calibration. Three dates cannot establish a strategy edge or earn L1.

## Repair

- Added strategy-free `orientation.json.research_routes`: actual local historical data/simulator capability remains executable while observed historical option replay is explicitly blocked.
- Scoped redirects: an archive-dependent `DIMINISHING_RETURNS` is overturned when an independent route remains informative; honest non-archive information-exhaustion stops remain valid.
- Added a fail-closed L1 provenance policy. Black-Scholes/unknown option marks cannot earn L1; even observed marks require more than three dates, complete entry/exit joins, and demonstrated sufficient history.
- Hardened the BS direction scoreboard so stuffed top-level observed metadata cannot turn proxy rows into `l1_hyp_ids`; metric eligibility is reported separately.
- Corrected canonical goal, zero-input executor contract, and option-data doctrine without selecting a symbol, structure, or recipe.
- Added `docs/HISTORICAL_OPTION_DATA_DECISION_PACKET.md`; default is $0 forward-only, with no credential/account/terms/spend action.

## Challenger review

Grok 4.5 initially FAILed three issues: an over-broad permanent DR ban, self-asserted batch L1 metadata, and incomplete boundary tests. All were repaired. Read-only re-review returned PASS on archive-scoped redirect semantics, scoreboard stuffing resistance, three-date plumbing-only semantics, and strategy freedom. Residuals are non-blocking: archive-stop wording uses a token heuristic; observed replay remains deliberately hard-false until a real adapter exists; future readiness callers must use computed coverage rather than self-asserted payload metadata.

## VERIFICATION

- Focused behavioral/boundary/negative suite: `tests.test_trader_build_compounding`, `tests.test_evidence_policy`, `tests.test_pcs_direction_scoreboard`, option-observation and contract-grid tests — 33/33 green.
- Full unittest discovery — 134/134 green.
- Current route smoke: 58 cached historical-underlying datasets, eight simulator modules, historical proxy discovery/capability executable, TSLL observed archive 1 date, observed historical replay blocked, `archive_dependent_stop_invalidated=true`.
- `git diff --check` — green.
- No broker, order, paper/live trade, credential, secret, schedule, gateway, spend, shadow, arm, or readiness promotion action.

## Readiness / capital

No living leader and no capital seat. BUILD/L0 and all formal B checks remain unchanged. This repair changes research routing and evidence provenance, not strategy performance. No trade-shaped candidate was produced, so structure/capital-fit/max-loss/max-lots are not applicable.

## DURABLE

The route inventory is machine-readable in zero-input `orientation.json`; provenance/L1 behavior is centralized in `trader_platform/research/evidence_policy.py`; corrected project truth and the provider gate are tracked in the option-data docs and readiness report.

## LESSON

A dataset gate is claim-scoped, not program-scoped. Real historical underlying replay with proxy option marks can productively discover and falsify strategy DNA, but proxy provenance must remain explicit and can never cross L1. Sparse forward archives are plumbing/calibration evidence, not edge evidence.

## NEXT

On the next zero-input BUILD wake, inventory open independent historical routes against closed novelty keys and autonomously choose one highest-information predeclared broad historical simulation/falsification or missing simulator-capability loop. Keep option marks explicitly Black-Scholes proxy/L0, do not force a symbol or structure, and treat forward archive capture as parallel only when a distinct RTH market date exists.

Integration state: direct-main commit/push/postflight pending; the deterministic receipt is authoritative for completion.

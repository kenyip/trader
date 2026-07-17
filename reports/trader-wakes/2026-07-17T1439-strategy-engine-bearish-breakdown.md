# Strategy Engine loop — bearish breakdown terminal F0

Bottom line: One predeclared broad-index volatility-expansion breakdown route exercised the new short terminal-return path but failed all five frozen train gates. It is not a survivor; Trader BUILD remains paused, continuous densify remains disabled, and all execution authority remains false.

Pre-mutation base: `39d6addc478ab83c4d858a701995ecc1e7e2a0db` on clean synchronized `main`; Strategy Engine `16cf86d0b22b2b9e1502bb1cb512cbecc6235666` on clean synchronized `main`. No BUILD lock or active BUILD process was present. Foreground Jarvis acted as the bounded worker because this cron runtime exposed no delegate/Kanban dispatch primitive.

## PRE-EDIT MAP

- Target files: `scripts/trader_strategy_engine_route_batch.py`, `tests/test_strategy_engine_route_batch.py`, and this tracked wake report.
- Callers/dependents: route-batch CLI → Strategy Engine handoff runner → fail-closed Trader gate. Strategy Engine already validates `direction=short` and applies the short sign during train evaluation.
- Tests: focused route-batch/handoff/gate tests, full Strategy Engine suite, full Trader unittest suite, full Trader pytest suite, and real cached-data route → handoff → gate smoke.
- Local pattern: stdlib/pandas bridge, immutable `RouteSpec`, one source-coded variant per exact route, explicit same-date controls, chronological train/identity-only holdout split, and authority false.
- Sensitive boundary: cached market OHLCV and generated research reports remain ignored local artifacts; no position, account, broker, credential, or secret data entered git.

## CHANGES

- Added exactly one route: `cached_broad_index_volatility_breakdown_put_debit_5d_v1` / `CACHED_BROAD_INDEX_VOLATILITY_EXPANSION_BREAKDOWN`.
- Frozen mechanism: SPY/QQQ/IWM close below SMA100, 20-session return below -5%, 5-session return below -2%, and 20-session realized volatility above its trailing 252-session 65th percentile; five-session terminal underlying return; 15 bps event cost; same-date SPY/QQQ peer control; future defined-risk debit-put-spread expression only.
- Added minimum support for unsigned terminal underlying returns on `direction=short`; Strategy Engine remains the sole signing layer. Path-managed short fills remain explicitly unsupported.
- Added focused coverage for route shape, one-variant budget, defined-risk put expression, terminal-close semantics, and raw negative terminal return preservation.
- Deliberately not built: short stop/gap/intraday fill logic, parameter search, new dependencies, new abstractions, holdout evaluation, or any execution/paper/live surface.

## VERIFICATION

- Focused Trader route/handoff/gate suite: `.venv/bin/python -m unittest tests.test_strategy_engine_route_batch tests.test_strategy_engine_handoff_gate tests.test_strategy_engine_handoff_runner` → `Ran 18 tests`, `OK`.
- Full Strategy Engine suite: `PYTHONPATH=src python3 -m unittest discover -s tests` → `Ran 25 tests`, `OK`.
- Full Trader unittest suite: `.venv/bin/python -m unittest discover -s tests` → `Ran 451 tests`, `OK`.
- Full Trader pytest suite: `.venv/bin/python -m pytest -q` → `461 passed, 18 subtests passed`.
- Diff hygiene: `git diff --check` passed.
- Real cached-data smoke generated 9 routes / 21,838 panel rows. Handoff returned `NO_QUALIFIED_STRATEGY` with `gate_status=validated_no_qualified_strategy`; direct gate emitted expected `NO_STRATEGY_STATUS` and exit `2`. No BUILD launched.
- New route preflight: 110 chronological train events and controls across 3 years; 48 sealed holdout identities; no preflight outcome reads.
- Frozen train-only metrics: event mean after cost `-0.01344929211909091`; paired excess mean `-0.0026893040590909097`; lower bound `-0.005338936759605661`; hit rate `0.42727272727272725`; worst-decile tail `-0.0763108811`. All five gates failed.
- Holdout remained identity/hash/count only (`3c504452a2ee3d889433865c4e8aa010e544b1b3cf743f65dac803de9ee7e206`). Authority remained false for L1, paper, shadow, broker, funding, arm, and live.

## DURABLE

- Trader now supports unsigned terminal underlying returns for `direction=short` while preserving Strategy Engine as the sole signing layer.
- The exact volatility-expansion broad-index short continuation route and its one-variant budget are source-coded and regression-covered.
- `NO_QUALIFIED_STRATEGY` remains fail-closed: densify stays disabled and no BUILD or execution authority is granted.

## LESSON

Outcome: `NO_QUALIFIED_STRATEGY`. The exact volatility-expansion broad-index short continuation route is closed; do not retune its momentum, volatility, horizon, cost, or tail thresholds and do not invert it into a rebound claim from these observed outcomes.

Minimum terminal short support is useful infrastructure, but market-direction breakdown alone did not isolate a bearish edge. The route lost absolutely and versus same-date peers, with weak hit rate and tail; more adjacent volume or threshold nudging is low-information.

Unresolved risk: evidence remains cached-underlying F0 only. Fixed-universe survivorship, benchmark-control dependence, clustered event dates, option pricing/liquidity/IV, listed payoff paths, execution friction, and paper behavior are not validated. No promotion claim is supported.

## NEXT

`CROSS_SECTIONAL_RELATIVE_WEAKNESS_F0`: add minimum point-in-time benchmark-relative feature support, then predeclare exactly one high-liquidity single-name relative-weakness continuation route whose trigger is frozen from prior closes against QQQ/SPY, whose event return is paired to the same-date benchmark return, and whose future expression is a defined-risk debit put spread. Keep one source-coded variant, fixed chronology/cost/gates, sealed holdout identity, and authority false; stop on `NO_QUALIFIED_STRATEGY`, and do not reuse, invert, or retune the closed broad-index breakdown route.

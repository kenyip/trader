# MOA BUILD executor closeout — 2026-07-13T0026

WAKE: 2026-07-13 02:00 PDT (Monday; premarket)
PHASE: BUILD / L0
SLEEVE: $3,000
ROLE: GPT 5.6 Sol executor; only writer; Grok challenger/finalizer/integration pending
OUTCOME: CAPABILITY_ADDED / PREDECLARED_PROXY_CONFIG_REJECTED
PAPER_ONLY: true

## ORIENTATION / CHOICE

Current living quality leader: **none**. Orientation carried 20 catalog structures, 245 hypotheses, 67 evolve artifacts, an empty capital path, and open historical-underlying/simulator-capability routes. The observed TSLL option archive remains one market date and blocks only observed-option replay/calibration. The prior NEXT was accepted because the four-leg double-diagonal/double-calendar family was absent from the catalog and therefore unlocked a genuinely new capability rather than repeating a closed daily-bar signal family.

**Hypothesis:** one predeclared neutral/high-IV 14/60-DTE symmetric double-calendar/inside-wing diagonal can remain non-vacuously positive and bounded on chronological train and untouched holdout under both exact four-leg 5% adverse percentage slip and $0.01 half-spread per leg.

**Falsifier:** reject this exact proxy configuration for this cycle if no symbol among BAC/F/SOFI/PLTR/TSLL/SMCI/AMD/AAPL passes train and holdout on both costs with at least eight trades, positive PnL, one-lot max loss ≤$300, max drawdown ≤$75, exact ledger/no same-bar reentry, holdout window drawdown ≤$75, and at most five dense-negative windows.

## DID

- Added `double_diagonal_spread` to the open strategy catalog with a dedicated `double_diagonal_sim` dispatch path and mutation controls.
- Added a paper-only four-leg Black-Scholes/daily-bar simulator: front put/call shorts plus same-strike or inward protective back-month put/call longs; one-position event loop; profit, defined-loss, front-expiry, and end-of-data exits. The predeclared configuration disables regime-flip exits, and this scoped simulator does not implement or claim one.
- Repaired the first outward-long shape before relying on it. Farther-OTM back longs do not support the claimed debit-only maximum loss. For the retained same-strike/inward protective shape, paid debit is only the frictionless one-lot structural bound before explicit closing friction; finalized capital also covers larger observed stressed path loss. Outward evidence was discarded.
- Added exact adverse entry/exit accounting across all four option legs for percentage slippage and fixed half-spread cost.
- Added fail-closed IV/regime/IV-rank/debit-budget boundaries, exact ledger metrics, no same-bar reentry, structure-pure population/evolve dispatch, distinct provenance, and optional trade-ledger evidence.
- Repaired the two interrupted arithmetic-test failures minimally: those tests now use an explicit `$500` research-only debit ceiling so they isolate cost arithmetic, while a separate test proves the normal `$300` candidate ceiling rejects the same fixed-cost and 5%-slip entries.
- Ran the predeclared eight-symbol 60/40 chronological dual-cost experiment and registered no hypothesis.

## TRADE SHAPE / CAPITAL

Structure: one front-month short OTM put + one front-month short OTM call, protected by one same-strike or inward back-month long put + call. Research seed: 14 short DTE / 60 long DTE / 0.30 short delta / zero inward offset / neutral regime / IV-rank floor 20.

For each accepted entry:

- `structural_max_loss_usd = entry_debit × 100` is the frictionless structural bound before closing costs.
- `capital_fit_usd = max_loss_usd = max(structural_max_loss_usd, observed_path_worst_loss_usd)` in finalized evidence.
- Candidate budget: `max_loss_usd ≤ $300`; otherwise fail closed.
- Conservative operating sizing is enforced as `max_lots = 1`; `theoretical_max_lots` separately preserves generic sleeve/open-risk capacity math and may be 2–3. No candidate or capital seat was created.

Deterministic fixture evidence: mid entry max loss `$297.37`; adding `$0.01` half-spread on four entry legs raises it to `$301.37`; 5% adverse leg slip raises it to `$329.65`. Both stressed entries therefore fail the normal `$300` boundary even though the isolated arithmetic tests are allowed to construct them under a `$500` research-only ceiling.

## CHRONOLOGICAL RESULT

Evidence: `.cache/platform/double_diagonal_chronological_lab_2026-07-13T0026.json`.

- Population completed: **8/8**, errors **0**.
- Complete train+holdout dual-cost passes: **0/8**.
- 5% slip, train: no positive symbol; six symbols were non-vacuous; PnL range `$-1,202.85` to `$0`; maximum drawdown `$1,193.97`.
- 5% slip, holdout: only SMCI was positive, but it was vacuous at one trade; no gate passed; dense symbols were negative and/or above the `$75` drawdown bar.
- Fixed `$0.01` half-spread, train: TSLL `n=20 / +$92.34 / DD $119.15` and SMCI `n=30 / +$399.64 / DD $126.47`; both fail drawdown, and no train row passed the full gate.
- Fixed `$0.01` half-spread, holdout: F `n=28 / +$7.39 / DD $84.82`, SOFI `n=25 / +$215.25 / DD $316.44`, TSLL `n=13 / +$239.88 / DD $129.22`, and SMCI `n=2 / +$184.62 / DD $0`; all fail drawdown and/or density. No holdout row passed the full gate.
- Every persisted train/holdout/window ledger recomputed within `1e-8`; same-bar reentries were zero.
- Decision: `REJECT_DOUBLE_DIAGONAL_PROXY_THIS_CYCLE` for this exact seed/configuration. No grid expansion, registration, L1, or capital-path promotion.

## CLAIM CRITIQUE / BOUNDARIES

- All option marks and cost stresses are synthetic Black-Scholes proxies; the lab cannot earn L1 or support real-fill, assignment, or observed-edge claims.
- The seed assumes favorable front/back IV multipliers `1.05/0.95`; failure under that assumption is useful negative discovery evidence, not proof that every double-diagonal/calendar DNA is universally invalid.
- The 60/40 split is chronological and the configuration was predeclared, but daily-bar entry still uses same-bar close/proxy state. This blocks promotion claims and is one reason the decision is scoped to this proxy configuration/cycle rather than a universal family closure.
- Contract availability, listed strike/expiry grids, dividends/early assignment, observed bid/ask surfaces, commissions, and exercise handling are not calibrated here.
- Zero-trade capital fields are budget placeholders, not observed entry risk. AMD/AAPL and the PLTR holdout are vacuous, not successful stand-aside evidence.
- No current leader exists; absolute risk/evidence gates were used. Positive fixed-cost rows do not survive the complete dual-cost/drawdown/density gate.

## VERIFICATION

- Focused double-diagonal behavior/boundary/negative controls: `tests.test_double_diagonal_sim` → **6/6 OK**.
- Related fixed-cost/diagonal/ratio regression: double diagonal + `test_defined_risk_fixed_cost` + `test_diagonal_oos_stress` + `test_put_ratio_backspread_sim` → **17/17 OK**.
- Lab artifact assertions: decision, 8/8 completion, 0/8 passes, ledger tolerance, no same-bar reentry, and window integrity → **OK**.
- Platform smoke: `just platform-smoke` → **OK**; `agentic_live` stayed blocked at Stage1 OAuth.
- Role-time full suite: `.venv/bin/python -m unittest discover -s tests -v` → **177/177 OK** in 6.787s (historical executor evidence; superseded by the final reconciliation count below).
- Changed-Python `py_compile` + `git diff --check` → **OK**.
- Coverage refreshed: **21 structures / 245 hypotheses / 67 artifacts / no leader**.

## FREEDOM AUDIT

One exact symmetric double-calendar/inside-wing proxy seed was rejected; no symbol or strategy allowlist was added, no unrelated family was frozen, and the one-date observed archive was not allowed to block historical-underlying/capability work.

## DURABLE / LESSON

Future Trader now has a distinct, structure-pure four-leg simulator and exact round-trip cost boundary. The key capital lesson is that outward back-month longs do not justify a debit-only maximum-loss claim; for retained same-strike/inward protective back legs, paid debit is a frictionless structural bound before closing friction and capital must also cover larger observed stressed path loss. Arithmetic tests must separate construction budget from candidate eligibility so cost mechanics can be tested without weakening the `$300` gate, and generic lot capacity must remain distinct from the enforced one-lot operating posture.

## ONE NEXT SEED

Build one no-lookahead intraday session-time evidence route for defined-risk PCS/CCS/IC: use completed 30-minute bars to compare open/midday/late entry buckets across the same liquid multi-symbol universe, carry only prior-completed regime features, apply both 5% and `$0.01` per-leg costs, and reject unless untouched chronological holdouts meet `$300` max loss, `$75` window drawdown, density, and exact-ledger gates. Keep L0 and register nothing on the first pass.

## PHASE STATUS

Executor phase only. No commit, push, merge, branch switch, challenger, finalizer, paper order, shadow, arm, broker access, or live action occurred. Deterministic completion remains pending later phases.

## FINALIZER AMENDMENT

Sol finalizer preserved the executor's config-scoped rejection but repaired a capital-honesty boundary discovered during reconciliation. American protective back legs now retain intrinsic value, package liquidation remains signed instead of clipping adverse closing friction to zero, and capital reports the larger of structural entry debit and observed stressed path loss. Paid debit is therefore labeled a frictionless structural bound before closing friction, not an unconditional hard live loss bound. A checked-in chronological runner and explicit passing-holdout/failing-train negative control close challenger F1/F2.

The exact lab rerun remains `REJECT_DOUBLE_DIAGONAL_PROXY_THIS_CYCLE`: 8/8 complete, 0/8 all-axis passes, no errors, ledger delta ≤`1.14e-13`, no same-bar reentry, maximum holdout-window DD `$249.34`. Updated representative fixed-cost rows: F holdout `n28/+$7.33/DD$84.82` with train `-$179.35`; SOFI holdout `n25/+$214.34/DD$317.35` with train `-$291.90`; TSLL train/holdout `+$92.34/+$239.88` but DD `$119.15/$129.22`; TSLL 5% train/holdout `-$538.36/-$372.81`. Finalized simulator output now enforces `max_lots=1` while retaining generic 2–3-lot arithmetic only as `theoretical_max_lots`; the direct boundary assertion keeps the `$300` gate unchanged. Final focused simulator/gate tests are 9/9, the integrate-only recovery parser regression is 1/1, platform smoke is green, and the full suite is **181/181**. Original executor metrics below are preserved as role-time evidence and superseded where they differ by this amendment. Integration remains pending the deterministic wrapper gate.

MOA_EXEC_DONE

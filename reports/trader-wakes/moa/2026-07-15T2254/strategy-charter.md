# Strategy decision charter — BROAD_SECTOR_BREADTH_THRUST_SPY_BULL_CALL_21D_V1

Status: predeclared before outcomes; BUILD/L0 underlying discovery only. This is independent of and does not mutate or proxy-satisfy parked `TSLL_OBSERVED_TERM_CARRY_DIAGONAL_V1`.

## Exact decision

Test one new, non-quarantined economic mechanism and close exactly one decision: advance `F0_MECHANISM -> F1_TRAIN` under the discovery bar if every frozen train gate passes, otherwise `FAMILY_CLOSED` at F0. The untouched final 40% and option-pricing stage remain unread/unrun in this executor loop.

## Layered Edge Stack

- Candidate id: `BROAD_SECTOR_BREADTH_THRUST_SPY_BULL_CALL_21D_V1`.
- Family id: `BROAD_SECTOR_BREADTH_THRUST_FORWARD_DRIFT`.
- Market / underlying: SPY is the prospective traded underlying; the eleven liquid Select Sector SPDRs (`XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY`) form a fixed breadth panel. This reduces single-name event concentration and gives a broad participation measure on a liquid optionable index ETF.
- Forecast type: `direction_up` over the next ten completed sessions.
- Economic mechanism: a rapid expansion from narrow to broad sector participation inside an already positive SPY trend reflects institutionally distributed demand and slow information/position diffusion; participation should persist long enough to create incremental ten-session upside versus high-breadth but non-thrust same-regime controls.
- Option structure: future conditional one-lot 18–24 DTE `$2`-wide SPY bull call debit spread; buy approximately 0.55–0.65 delta call, sell the next listed strike about `$2` higher. No option pricing occurs unless the underlying mechanism first reaches F1 and later survives untouched holdout.
- Intended Greeks: positive delta and gamma with bounded negative theta; the spread caps vega and premium outlay relative to a naked call.
- Dangerous unintended exposures: paying too much implied volatility after a broad rally, negative theta if continuation stalls, upside cap, gap risk, dividend/early-assignment mechanics on the short call, and temporary share exposure if expiration/assignment is mishandled.
- Regime envelope: signal only when the completed SPY close is above a fully warmed SMA100 and its completed 60-session return is positive. Stand aside when either condition fails.
- Entry trigger: after a completed signal bar, sector breadth above each sector's fully warmed SMA50 must be at least `9/11`, and breadth must have risen by at least `3/11` over the prior five completed sessions. Enter no earlier than the next completed-session close; the signal bar cannot set the entry mark.
- Control: prior-only, same-regime, high-breadth (`>=9/11`) but non-thrust (`five-session breadth change <=1/11`) SPY dates. Match without outcomes on breadth level, SPY 60-session return, SPY `HV20/HV60`, and calendar distance; one-to-one, no reuse, control outcome window must end before the treated signal, and treated/control windows cannot overlap.
- Exit / management: planned option expression exits at first of +50% debit, -50% debit, ten completed sessions, five DTE, SPY close below prior completed SMA100, or ex-dividend/assignment guard; no roll, averaging down, same-session re-entry, or overlapping SPY directional option exposure.
- Risk / capital fit: `capital_fit_usd=200`; one-lot `max_loss_usd=200` frictionless same-expiry `$2`-wide debit-spread payoff bound with entry debit required `<= $200`; `max_lots=1`; portfolio overlap rule forbids concurrent SPY/QQQ/IWM or sector-option positive-delta risk in the Agentic sleeve. This is a planned structural bound, not observed fill or L1 evidence.
- Evidence stage: `F0_MECHANISM`; claimed bar is discovery only; adjusted underlying closes with frozen chronology and no option marks. Proxy or underlying discovery cannot earn L1 or a capital seat.
- Stand-aside rule: no trade when trend, breadth-thrust, option debit/liquidity, event, max-loss, or overlap gate fails.

## Frozen evidence design and predeclared falsifier

Use adjusted daily closes from 2010-01-01 through 2026-07-15, inner-joined without forward fill. Construct all signal/control geometry from completed bars, split chronologically 60/40 by treated signal date, evaluate only the first 60%, and serialize only holdout identity/count/date boundaries with `outcome_metrics_read=false`.

Close the exact family at F0 if any train gate fails:

1. fewer than 20 one-to-one train pairs or fewer than eight distinct signal years;
2. any chronology, overlap, control-reuse, feature-warmup, or signal/entry-lag violation;
3. treated mean ten-session SPY return after a labeled 10-bps round-trip underlying sensitivity is not above `+0.50%`;
4. fewer than 55% of treated paths finish positive after that sensitivity;
5. treated mean return does not exceed matched control mean by at least `+0.25%`;
6. the one-sided 90% date-block-bootstrap lower bound for paired excess is not positive;
7. treated worst-decile terminal return is below `-3.00%`; or
8. the mechanism-specificity control wins: high breadth without a thrust has equal or better mean return.

If and only if every gate passes, advance to F1 train discovery. Do not inspect holdout, price options, register a hypothesis, claim F2/L1, or move onto paper in this wake.

## Freedom / anti-thrash audit

This supersedes the parked diagonal's RTH-data NEXT because local time is 22:55 PDT/off-hours and its frozen data wake condition is unmet. It is materially independent of quarantined cross-sectional low-HV/downside-semivariance, monthly momentum, OPEX/TOM, breakout, post-shock compression, earnings drift, SPY theta-carry, and daily PCS signal families: the new mechanism is within-market sector participation acceleration with a prior-only high-breadth non-thrust control and no option-payoff evaluation at F0.

# TSLL Covered-Call Selection

**As of:** 2026-09-03 | TSLL **10.75** (MEASURED yfinance + Robinhood cross-check) | TSLA **383.37**

Analysis only. Nothing placed. Builds on [PR #1](https://github.com/kenyip/trader/pull/1) (full overwrite ~0.30Δ, no re-entry after assignment).

## Recommended trade

- **SELL 25× TSLL 2026-10-16 13C** limit **0.53** (bid **0.53** / ask **0.56**, robinhood_crosscheck, 2026-09-03T16:12:45Z)
- **SELL 25× TSLL 2026-11-20 14C** limit **0.77** (bid **0.77** / ask **0.84**, robinhood_crosscheck, 2026-09-03T16:12:45Z)

**Total premium at bid: $3,250** on 5,000 unwritten shares (7,000 total; 2,000 already covered by existing Nov-20 12/13C).

**Why calendar split:** Cybercab launch is **today** (Sep 3) — the Oct-16 13C leg (~0.31Δ) captures the pop/fade window and expires **before** Q3 earnings. The Nov-20 14C leg (~0.34Δ) owns the earnings/event vol sleeve (Oct 21, unverified) with +30% upside room to strike for happy assignment. This balances scenario **A** (ride to strike) and **B** (sell rich IV, keep premium after crush) better than either expiry alone.

**Second choice:** sell **50× Oct-16 13C** @ **0.53** (~$2,650 premium) — Higher premium/delta on Cybercab window alone; loses Nov-20 earnings/event IV sleeve.

## Scenario table — recommended calendar split (MODEL, 5,000-share block)

| TSLA move | Combined P/L | Notes |
|---|---:|---|
| tsla +10pct | $10,305 | Both legs likely ITM near expiry; partial assignment |
| tsla +20pct | $16,871 | Assignment on both; capped upside above strikes |
| tsla +40pct | $17,000 | Full assignment; client-desired outcome on Oct leg |
| tsla -10pct | $-10,026 | Keep premium + IV crush on Nov leg offsets share drop |
| tsla -20pct | $-20,186 | Premium + crushed short option; share mark still hurts |

## Top ranked single-leg candidates (5,000 shares, MEASURED bids)

| Rank | Exp | Strike | Bid | Δ | OI | Premium $ | Assigned $ | Prem/Δ |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2026-09-18 | 10.0 | 1.15 | 0.70 | 12353 | $5,750 | $5,750 | 1.652 |
| 2 | 2026-09-25 | 10.0 | 1.26 | 0.68 | 1605 | $6,300 | $6,300 | 1.850 |
| 3 | 2026-09-18 | 10.5 | 0.85 | 0.59 | 607 | $4,250 | $4,250 | 1.436 |
| 4 | 2026-10-02 | 10.0 | 1.29 | 0.67 | 627 | $6,450 | $6,450 | 1.926 |
| 5 | 2026-09-18 | 11.0 | 0.65 | 0.49 | 6799 | $3,250 | $4,500 | 1.337 |
| 6 | 2026-09-25 | 10.5 | 0.93 | 0.59 | 850 | $4,650 | $4,650 | 1.573 |
| 7 | 2026-10-09 | 10.0 | 1.39 | 0.67 | 90 | $6,950 | $6,950 | 2.088 |
| 8 | 2026-10-16 | 10.0 | 1.51 | 0.66 | 5195 | $7,550 | $7,550 | 2.280 |

## Structure comparison

- **single_50x:** $2,650 — 50× 2026-10-16 13.0C
- **ladder_nov20:** $5,091 — 17/17/16 on Nov-20 12/13/14C
- **calendar_split:** $3,250 — 25× Oct-16 13C + 25× Nov-20 14C
- **consolidate_nov20_14C_x70:** $4,460 (buyback debit $930) — Buy back existing Nov-20 12/13C; sell 70× Nov-20 14C
- **keep_existing_plus_50x_nov20_14C:** $3,850 — Keep Nov-20 12/13C; sell 50× Nov-20 14C on unwritten shares

**Consolidate vs keep existing:** Buying back Nov-20 12C/13C at live asks vs sold 0.75/0.77 costs ~$930 net debit (MEASURED), then rewriting 70× 14C yields ~$4,460 net credit vs ~$3,850 for keep+50× 14C. Consolidation wins ~$610 but adds leg risk during buyback; **keeping existing + new 50× 14C is simpler** unless you want one clean strike.

## Liquidity thresholds

- Min bid: $0.05; max spread: 40% of mid; min OI: 25
- Rejected: 116 strikes (see RESULT.json)

## IV term structure

- Nov-20 carries ~4.0 vol points over Oct-16 at ~35Δ; ~35 extra days span Q3 earnings (2026-10-21, unverified).
- TSLL 20d realized vol **96.1%** (MEASURED) vs Nov-20 ~35Δ IV **~89%** — implied still elevated but below recent realized.

## k-decay interaction (MEASURED k + MODEL roll)

- Monthly k decay: **-2.96%** (yfinance daily closes 2026-01-02 → 2026-09-02)
- Single Nov-20 write: $3,850 premium − $3,983 decay drag = **$-133** net
- Repeated 43d cycles (MODEL): $1,039 net — only wins if post-crush re-write ≥85% of today's bid

## LEAP diagonal lane (separate — not vs shares)

- Short TSLL calls against long TSLA LEAPs are **not covered**; assignment on TSLL shorts does not pair with LEAP exercise.
- **Jan-2027 600C ×25:** too near-dated for 6mo overwrite horizon — do not write against.
- Jun-2027 / Jun-2028 LEAPs: viable for TSLA-call diagonals only; TSLL share overwrite remains the primary lane.

## Management

- **Let assign:** If TSLL closes ≥ strike on expiry and you still want exit, let assign. Do not rebuy TSLL (per PR #1).
- **Roll trigger:** Roll only if TSLL spot exceeds strike by >8% with >10 DTE left AND IV rank >70th pct; otherwise let ride to assignment.

## Catalyst calendar

- **Cybercab:** MEASURED — invite-only Austin launch event today per Tesla/Teslarati/CNBC
- **TSLA Q3 earnings:** 2026-10-21 (pm), verified=False

Runnable: `python3 scripts/tsll_covered_call_selection.py` → `studies/tsll_covered_call/RESULT.json`

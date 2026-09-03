# Trader wake — 2026-09-03 — tsll overwrite study

Research / paper only. No broker, order, arm, or live authority.

## Chose
Decision-grade dollars on the real 7,000-share TSLL block: HOLD vs full overwrite vs current 20-of-70 vs ROTATE into TSLA LEAPs.

## Did
- Re-derived k = TSLL/TSLA² and 150-session beta from yfinance closes (2022-08-09 → 2026-09-02, n=1021).
- Confirmed TSLL listed-option history is UNKNOWN for arms (Robinhood daily bars interpolated until 2026-07-06).
- Built `scripts/tsll_overwrite_study.py` using `data.load_history` + `pricing` Black-Scholes. Tagged MODEL vs MEASURED.
- Wrote `studies/tsll_overwrite/RESULT.json` + `SUMMARY.md`.
- Live first-trade quotes from Robinhood (read-only): Oct 16 13C bid 0.49 / ask 0.52.

## VERIFICATION
- `.venv/bin/python -m unittest tests.test_tsll_overwrite_study -v` — 14/14 pass (assignment, re-entry, partial cover, no future leak in k, dollar scale).
- `.venv/bin/python scripts/tsll_overwrite_study.py --outdir studies/tsll_overwrite --period 5y` — exit 0; recommendation `FULL_OVERWRITE_d0.30_no_reentry`.
- MEASURED: unrealized 7000×(10.59−12.76) = −$15,190; beta_150 = 2.033 (n=150, R² 0.998); k Jan 30 = 9.236e-5; k anchor = 7.316e-5; monthly decay −3.23%.
- MODEL 6m flat: HOLD −$12,752; 0.30 overwrite +$1,073; ROTATE −$18,969. 2026 YTD no-reentry overwrite −$29,163 vs HOLD −$61,250 vs re-entry overwrite −$77,248.
- No orders placed. Robinhood used for quotes only.

## DURABLE
- `scripts/tsll_overwrite_study.py` — runnable study.
- `tests/test_tsll_overwrite_study.py` — behavioral tests.
- `studies/tsll_overwrite/RESULT.json` — machine-readable arms.
- `studies/tsll_overwrite/SUMMARY.md` — human answer, dollars first.
- Lesson: automatic re-entry after TSLL assignment is the historical value destroyer; write the uncovered 50 and stay out if called away.

## LESSON
Overwrite P/L without assignment is HOLD plus premium. The live question is assignment policy, not “whether to write.” Re-buying 7,000 decaying shares after a call-away repeats the k-bleed. ROTATE only wins a 6-month horizon if TSLA is a ~+40% path; on flat it loses to both HOLD and overwrite because the replacement is long premium.

## NEXT
If Ken wants the first trade: sell 50 TSLL Oct 16 2026 13C at 0.50 (bid 0.49 / ask 0.52) against the uncovered 5,000 shares. Do not auto-rebuy TSLL if assigned. A follow-up can mark the existing Nov-20 12/13 mix vs buying it back — not required to start the 50-lot. `DIMINISHING_RETURNS` on further static-knob overwrite variants until a real TSLL option tape exists.

# Manual research wake — 2026-09-03T1640 UTC

WAKE: 2026-09-03T1640 UTC (RTH; TSLA +7% / TSLL +14% into an evening Austin Cybercab event)
PHASE: RESEARCH (no strategy-code change; no trade)
SLEEVE: TSLA/TSLL covered-call decision support

## Did

1. Preflight clean on `main` @ `b8ae922e535ba8d669d876eaba450d2019db2575`. Branched `cursor/tesla-cybercab-research-6ce2`.
2. Replaced a failed research handoff with primary-source work: Tesla IR Q1/Q2 2026 + 10-K, tesla.com/robotaxi, Cybercab first-responder plan (2026-07-16), Tesla/@robotaxi/@elonmusk/@aelluswamy X posts, TxDMV AV program, CA DMV permit holders, NHTSA PE25012/EA26002/Part 555, Waymo blog, Alphabet Q1/Q2 2026, Robinhood live equity/option marks, Yahoo event study (n=16).
3. Wrote `studies/tesla_cybercab_2026_09/{RESEARCH,SOURCES,RESULT}.md/json` plus a stdlib `event_study.py`. No `strategies.py` / engine edits. No broker orders.

## VERIFICATION

- Preflight: `{"ok": true, "mode": "preflight", "completion": false}`.
- `RESULT.json` parses; event list defined before returns; 16/16 events produced 1d/5d/20d excess.
- Live quotes timestamped (TSLA/TSLL/SPY 16:33Z; TSLL calls 16:39Z; TSLA 380 straddles 16:41Z).
- Negative controls: tesla.com still says Cybercab is future; CA DMV has Tesla on drivered testing only; no public NHTSA Cybercab exemption found; BOM UNKNOWN; Waymo $/mi not invented.
- Boundary: research cut is mid-session *before* the livestream — evening outcomes are falsifiers, not facts.
- Full unit suite: not required to validate markdown research; run after setup if the environment has a venv. No strategy behavior changed.

## DURABLE

- Do not treat a Tesla “launch day” headline as a public paid-service launch. Check tesla.com/robotaxi + IR city table + CA/TX permit lists first.
- Texas AV authorization is self-certification. California driverless permission is the harder US gate and Tesla does not have it.
- Cybercab vehicle production ≠ Robotaxi service ≠ FSD (Supervised). Conflating them is how the failed handoff went wrong.
- Autonomy event studies: mean 1d excess ~0, 5d more often fade. We, Robot (−9% XS 1d) is the demo analog; Austin 2025-06-22 (+7% then fade) is the first-paid-service analog. Today’s +7% already looks like the anticipation print.
- Tesla-owned fleet “at this time” (first-responder plan) — owner-supplied Tesla Network is not the 2026 mechanism.
- Never infer unsupervised safety from miles without matched incidents and ODD.

## LESSON

A research wake that starts from media “launch” language and does not open Tesla’s own product page + latest IR exhibit will ship a false operational inflection. The binding check is: *can a non-invite public book a Cybercab tomorrow, and what permit is that ride running under?*

## NEXT

After the 2026-09-03 livestream and the next two Austin sessions, re-score the 2×2 using only: (1) whether tesla.com/robotaxi still says Cybercab is future, (2) whether the Robotaxi app exposes Cybercab as a public vehicle type for 5 consecutive days, (3) any TxDMV/NHTSA/incident print. Do not change StrategyConfig from this memo. No paper/live order from this wake.

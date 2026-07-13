# MOA BUILD merge (finalizer) — 2026-07-12T1806

WAKE: 2026-07-12T1845 PDT (Sunday; market closed)
PHASE: BUILD / L0
SLEEVE: $3,000
ROLES: GPT 5.6 Sol executor → Grok 4.5 challenger → GPT 5.6 Sol finalizer
OUTCOME: CAPABILITY accepted; challenger **PASS 8/8**
PAPER_ONLY: true

## CHOSE (executor)

Build a no-lookahead dividend/ex-date and early-assignment boundary for short-call diagonal and bull-call debit simulators. Falsify if later announcements leak backward, required data fails open, a known dividend-dominant ITM short call remains open, or bear-put behavior is contaminated. Weekend correctly skipped one-date archive append.

## DID

- `corporate_action_risk.py`: DividendEvent + known_at visibility + conservative dividend-vs-extrinsic short-call guard.
- Optional/required injection into `diagonal_sim` and bull-call `debit_vertical_sim`; fail closed on missing provider/coverage/malformed data.
- Assignment-risk exits precede normal management; metrics label mode and exit counts.
- Bear-put isolated as `not_applicable_put`.
- Doctrine + coverage surfaces updated; no hyp/B-check/capital/paper/live mutation.

## CHALLENGER JUDGMENT

PASS 8/8. Independent re-run: focused 13/13, smoke green, full suite 143/143. Claims stay machinery-only L0; default mode disabled so prior proxy history is not silently rewritten. Nits (non-blocking): catalog DNA exit/limitations lag; optional below-threshold and exit-precedence sim tests.

## FINALIZER RECONCILIATION

- Repaired catalog honesty: diagonal and bull-call DNA now put `early_assignment_risk` first and state provider-dependent, honest-`known_at`, and non-dividend-assignment limits.
- Added both requested simulator controls: below-extrinsic dividends continue without assignment exits, and assignment wins when profit target is simultaneously true.
- Accepted the NEXT-scope caution; `merged-next-seed.md` already permits zero-input supersession after a hard provider-data block, so no discovery allowlist or extra machinery restriction was added.
- Promoted the `None` missing-coverage versus `[]` covered/no-event boundary, non-fabricated `known_at`, and test method to `trader-self-evolution`.
- Finalizer verification: focused 16/16, platform smoke green, full suite 146/146, structured handoff validator green. No edge, candidate, B-check, paper, shadow, arm, or live mutation.

Critique: `reports/trader-wakes/moa/2026-07-12T1806/challenger-critique.md`
Merge: `reports/trader-wakes/2026-07-12T1806-moa-merge.md`
NEXT file: `reports/trader-wakes/moa/2026-07-12T1806/merged-next-seed.md`

## CAPITAL / READINESS

No living quality leader. BUILD/L0 unchanged. No seat, shadow, arm, or live claim.

## NEXT SEED

Inventory no-paid historical corporate-action sources for both ex-date and honest announcement-time provenance (`known_at`); implement an archived `DividendEventProvider` only if `known_at` can be represented honestly; otherwise write a fail-closed data decision packet and keep required-mode diagonal/bull-call simulations blocked rather than backfilling announcement dates from ex-dates.

## PHASE STATUS

Finalizer handoff is green and ready for the deterministic wrapper gate. Integration remains pending; this phase did not commit, push, merge, switch branches, or claim RUN COMPLETE.

Verification and learning paths:
- `reports/trader-wakes/moa/2026-07-12T1806/learning-promotion.md`
- `reports/trader-wakes/moa/2026-07-12T1806/compounding.json`

MOA_FINALIZE_READY

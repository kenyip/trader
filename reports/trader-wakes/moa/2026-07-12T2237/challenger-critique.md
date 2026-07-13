# MOA BUILD challenger critique — 2026-07-12T2237

ROLE: Grok 4.5 challenger (read-only judgment)
PHASE: BUILD / L0
SLEEVE: $3,000
PAPER_ONLY: true
OUTCOME: **PASS 8/8** (nits only; no claim-invalidating defects)

## Scope reviewed

- `reports/trader-wakes/moa/2026-07-12T2237/meta.json`
- `reports/trader-wakes/moa/2026-07-12T2237/executor-closeout.md`
- `reports/trader-wakes/moa/2026-07-12T2237/orientation.json`
- `reports/trader-wakes/2026-07-12T2237-moa-exec.md` / `reports/trader-wakes/LATEST.md`
- `reports/readiness/income-coverage-LATEST.md`
- `reports/readiness/LATEST.md` (top / living-leader / NEXT context)
- `docs/DIVIDEND_EVENT_DATA_BOUNDARY.md`
- `trader_platform/research/dividend_event_crosscheck.py`
- `scripts/dividend_event_crosscheck.py`
- `tests/test_dividend_event_crosscheck.py`
- `.cache/platform/dividend_event_crosscheck_2026-07-12T2237.json`

No evolve `--apply`, broker, paper mutation, shadow, arm, or live path exercised by critic.

## Rubric

1. **Goal progress — PASS**
   Material capability advance on the open corporate-action evidence route: independent Apple Newsroom primary-source cross-check of the AAPL Nasdaq archive. Does not produce a paper-testable trading rule or edge, but it does raise the chance that short-call assignment guards can later use dual-sourced AAPL `known_at`/amount/security-identity inside a bounded interval without inventing completeness. Honest L0 partial outcome beats vanity strategy retune.

2. **Creativity and independence — PASS**
   Justified continuation of the 1835 NEXT (issuer/filing cross-check for AAPL after archive provider). New evidence class = canonical issuer sitemap + results releases, not another proxy DNA polish or closed-family reopen. Orientation shows closed daily-bar signal families left closed; `redirect_required=false` and executable historical/capability routes remain.

3. **Claim validity — PASS**
   Claim is correctly narrowed to `partial_issuer_corroboration` for fields `known_at`, `amount_per_share`, `security_identity` over **2016-07-26 through 2026-04-30** only. Explicit non-claims: whole-provider completeness, pre-window 13 events, `ex_date`, split-adjusted economics, assignment calibration, observed option surfaces, L1, capital seat, B3/B4, paper/shadow/live. Matching logic uses archive `known_at` vs issuer `published_on` + amount; record/payment dates are stored but not promoted to ex-date. `claim_limit` on the JSON matches doctrine.

4. **Evidence and test quality — PASS**
   Cited live artifact reproduces: 40/40 archive and issuer events in window, 0 conflicts, 0 unmatched archive/issuer dates, 13 before-window archive events, `provider_status=partial_issuer_corroboration`. Challenger re-ran `tests.test_dividend_event_crosscheck` → **9/9 OK**. Suite covers: explicit common-stock wording requirement, modern/legacy wording variants, sitemap host/path allowlist, complete bounded qualify-only fields, amount conflict fail-closed, missing event fail-closed, duplicate publication date, forged/non-canonical issuer URL. Not mere implementation mirrors; negative controls exist. Full-suite **164/164** remains executor-reported for finalizer re-gate (not re-run here).

5. **Falsification — PASS**
   Predeclared falsifiers (missing event, amount mismatch, duplicate date, noncanonical URL, identity wording failure, chronology defects) fail closed to `single_source_conflict` or raise. Live path did not trigger them; judgment correctly promotes only bounded partial corroboration, not provider completeness or L1.

6. **Capital honesty — PASS**
   Living leader remains **none**. No hyp registration, no B-check mutation, no capital_fit/max_loss/max_lots trade-shaped claim, no paper/shadow/arm/live. Absolute gates still authoritative. Coverage refresh still 20 / 245 / 67 / no leader.

7. **Research freedom — PASS**
   AAPL-only issuer qualification is evidence labeling, not an instrument allowlist. MU not pursued is justified (prior NEXT required a normalized MU archive first). One-date TSLL option archive correctly does not freeze this capability loop. Symbol/strategy freedom and open historical-underlying routes remain.

8. **ONE highest-information NEXT — PASS (tightened wording below)**
   Executor NEXT (explicit historical `ex_date` source or close route at partial L0 and redirect) is directionally right. Keep the stop-or-redirect clause so dividend provenance does not thrash. Prefer a short fail-closed inventory over multi-wake polish if no independent labeled ex-date source exists.

## Findings (finalizer action)

| Severity | Finding | Disposition |
|---|---|---|
| Nit | “Security identity” is issuer-wording + hardcoded field after regex match, not a full Nasdaq preferred-security row audit. Doctrine already says identity is cleared only for matched releases — keep that language; do not broaden to whole-provider security-class proof. | Accept / no code change required unless wording drifts |
| Nit | Completeness is intersection completeness inside the issuer-sitemap span (window starts at first issuer release). Dual silent omission of the same event remains theoretically possible. Executor already denies whole-provider completeness — preserve. | Accept |
| Nit | Optional stronger negative control: assert that archive `ex_date` equal to issuer `record_date` still leaves `ex_date` unqualified. Would lock the anti-substitution claim in tests. | Optional repair |
| Nit | `reports/readiness/LATEST.md` top NEXT still points at the 1835 issuer cross-check, now completed by this wake — stale. | Patch NEXT (challenger) |
| Note | Full suite 164/164 not re-run by challenger; finalizer must re-verify focused + full suite before integration. | Finalizer gate |

No claim-invalidating defect found. No force-reject of the capability advance.

## Capital / promotion gates

- No candidate advance to testing/paper/shadow/live
- No living leader seat
- Proxy/BS marks remain L0
- Observed option archive density still blocks observed-option claims only

## Freedom audit

No removable restriction introduced. Do not let continued AAPL dividend provenance freeze multi-symbol historical-underlying discovery if the ex-date inventory fails closed.

## Judgment

**ACCEPT** executor outcome `CAPABILITY_ADVANCE / BOUNDED_PARTIAL_CORROBORATION` with nits only.
**PASS 8/8.**

MOA_CHALL_DONE

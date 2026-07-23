# Go-live readiness — Agentic $3k sleeve

**Purpose:** Decide when the system may draft a **live arm packet** for Ken.
Not a vibe. Evidence + Ken explicit arm.

**Capital:** $3,000 USD planning sleeve. Free within sleeve; use wisely; prefer 1-lot confident entries.

**Phases:** `BUILD` → `PAPER` → `SHADOW` → `LIVE_PACKET` → (Ken arms) `agentic_live`

Trader maintains: `reports/readiness/LATEST.md` (and dated copies).
Human front door: `just trader-status` (simple 3-layer) · wakes in `reports/trader-wakes/LATEST.md`.

---

## Simple model (primary)

```text
EDGE  — sims find & kill strategies (24/7; no market hours required)
ROBOT — paper + shadow prove the machine works (short live-clock sample)
ARM   — Ken funds/arms 1-lot real money (never automatic)
```

| Layer | Question | Main evidence |
|---|---|---|
| **EDGE** | Is there a real after-cost strategy? | Shortlist B3+B4, pack-grade, capital-fit, placeable structure |
| **ROBOT** | Does the software work end-to-end? | Paper open/manage/close across a few sessions; shadow propose→risk→log |
| **ARM** | Should real cash trade? | LIVE_PACKET + Ken yes |

**Rules of thumb**
- Sims decide if it’s **good**. Paper/shadow decide if the **robot works**. Ken decides to **arm**.
- Paper is a short dress rehearsal — **not** a second full proof of edge.
- First live on RH MCP today = **single-leg** class (CSP/long). Multi-leg PCS/CCS stays research/paper until RH multi-leg place exists.
- Letter gates A/B/C below are the detailed checklist behind the simple view (`just trader-status --json` / `--legacy`).

---

## A. Platform ready

| # | Check | Evidence |
|---|---|---|
| A1 | `python -m trader_platform.smoke_test` green | smoke output / CI |
| A2 | Risk limits tuned for **$3k** (not leftover $5k defaults) | `risk_limits.yaml` + note |
| A3 | Paper path durable (ledger, marks, fees assumptions documented) | paper ledger path |
| A4 | Shadow path: propose → risk_check → log; **no** broker mutate | shadow run artifact |
| A5 | Kill switch path documented and testable | policy + file path |
| A6 | No secrets/positions in git | git status hygiene |
| A7 | Live still disarmed (`agentic.enabled=false`) until Ken arm day | config |

## B. Strategy ready (per hyp — first live is **one** hyp)

Discovery is free across symbols/structures; go-live still requires **one** hyp that clears B1–B7. Do not force the first live hyp to be TSLA/TSLL or wheel — pick the best evidence under capital-fit.

**Ken rank pin (2026-07-10):** first-money / first-paper order is **evidence-ranked** (capital fit, regime stress, cost/slip falsify, multi-name multi-structure). **Plumbing readiness is not a rank key** — incomplete CCS/IC OPEN is parallel build debt; do not promote TSLL PCS solely because `OPEN_PCS` is wired, and do not demote stronger mid-slip DNA for that reason.

**Ken better-trades pin (2026-07-10):** capital path seats require **independent trade quality**, not a multi-name quota. **Diversify-for-fear is lazy** — if a hyp exists only as a TSLL diversifier, remove it from the capital path (`candidate`/research). Multi-name freedom is for discovery; re-promote only when quality beats the bar without diversifier rationale. Paper-first; no live/agentic/fund.

| # | Check | Evidence |
|---|---|---|
| B1 | `capital_fit_usd` ≤ 3000; `max_loss_usd` within budget (~5–10% sleeve default) | hyp fields |
| B2 | Ship bar: enough trades, not thin-perfect; finite scores | evolve / last_sim |
| B3 | Multi-regime or scenario stress (not single lucky path) | scenario/report paths |
| B4 | Costs/slippage assumed; edge still positive at 1-lot | note in hyp/evidence |
| B5 | Explicit invalidation + management DNA (entry + exit knobs learned, not vibes) | DNA entry_plan + exit_plan |
| B6 | Live-clock paper sample (target: multi-session / many closed paper trades) | paper ledger + learn_tick |
| B7 | Shadow window: would-have trades acceptable under risk envelope | shadow logs |

## C. Opportunity ready (day-of)

| # | Check | Evidence |
|---|---|---|
| C1 | Regime matches hyp’s trained regime | desk/regime note |
| C2 | Size = min (1 lot); no “catch up” sizing | order plan |
| C3 | BP/margin free; no correlated pile-on | buying power check |
| C4 | Daily loss stop armed in risk config | risk_limits |

## D. Ken arm packet (red gate)

When A+B green (and C when market open), Trader may **draft** only:

- Context, hyp id, capital fit, max loss, expected income range (honest)
- Evidence paths (B2–B7)
- Risk / rollback / kill
- Exact approve/decline: arm `agentic_live` for allowlist `[hyp_id]` only

**No self-arm. No main-account trading.**

---

## Scoreboard row (paste into `reports/readiness/LATEST.md`)

```text
PHASE: BUILD|PAPER|SHADOW|LIVE_PACKET
SLEEVE_USD: 3000
PLATFORM: A1..A7  pass/fail
TOP_HYP: <id or none>
STRATEGY: B1..B7  pass/fail/na
OPPORTUNITY: C1..C4  pass/fail/na (na off RTH)
BLOCKERS: <list>
NEXT: <one concrete build or validate step>
```

## First live posture (when armed)

- One strategy allowlist, one open risk unit, hard daily loss stop
- Proof of ops first weeks; income is secondary to not blowing the sleeve
- Auto-disarm on kill switch or daily stop (when wired)

# WAKE — 2026-08-14T1501 continuum judgment / coach

WAKE: 2026-08-14 ~15:01 PDT / 18:01 ET / 22:01 UTC (after RTH close)
PHASE: **SHADOW** ops + PAPER manage + EDGE coach
SLEEVE: 3000 plan · test cash≈500 · live_armed=false
ECONOMIC MECHANISM: time-decay defined-risk multi-leg income (paper research) + MCP single-leg first-live lane
CANDIDATE/FAMILY SCOPE: leftover INTC IC paper + hunt beyond F/INTC leftover (SNAP/TSLL/CCL) + campaign NEXT_SEED preserve
FUNNEL: F4_OBSERVED_PAPER manage (leftover) · no new F0
PREDECLARED FALSIFIER: Friday F fade-below-14.15 restores both IC wings **or** campaign keeps erasing RTH marks with no restore hook
OUTCOME: **BLOCKER_REMOVED_AND_RETESTED**
STRATEGY ADVANCEMENT: false (EDGE still Ken-frozen; no capital_path stage move; first-live still SNAP CSP)
SEARCH INFORMATION: true — Friday F fade thesis closed; SNAP/TSLL/CCL not pack-grade; campaign-thin now has a restore hook
NO-ADVANCE STREAK: n/a (coach ops; no F0 BUILD streak)
CHOSE: **close remake leftover INTC + hunt SNAP/TSLL/CCL + ship campaign NEXT_SEED preserve** — honor Ken freeze; do not prune; do not absorb pack_grade WIP

## Self-eval (last residue)

- Last RTH 12:42 PDT **did** change: remade INTC at 102.87 mid +24.78/adv +8.28; F IC both wings dead at 14.38; INTEREST fade-below-14.15.
- Campaign then thinned NEXT_SEED again (`source=trader_paper_campaign`, order_id only) — same 2026-07-30 / 08-03 / 08-10 / 08-14T0943 race.
- Hourly 21:59Z already hunted AMD/SMCI (`n_alive=0`). Repeating F/INTC mid-session marks would be parks-with-no-delta.

## Orient

- Status: Phase SHADOW · IN_PROGRESS · search EDGE_FROZEN_KEN · ROBOT paper=ok shadow=PASS · ARM blocked
- Worker ON · cycle_n~24017 · hb_age 0 · all rc=0 · wall~36s · registry 6,000,873 · EDGE Ken-frozen (evolve/stress/multi skipped)
- Session: **closed** (RTH last 16:00 ET). Quotes used: RH MCP 19:59:59Z official close prints.
- Paper: 1 working leftover INTC IC `paper_b5b969c4a65f` risk $188.72
- Research leaders: F IC dens0 · first-live SNAP CSP fit_3k (hyp often ghost)
- Concurrent dirty: `data.py` / `trader_paper_campaign.sh` / `trader_promote_paper.py` / `trader_paper_mark.py` left unstaged

## DID

1. Close remake leftover INTC IC from RH adjacent 87/88p + 122/123c at 19:59Z: spot **102.54** (−1.93%), mid **+$26.78**, adverse **+$5.78** vs PT **$18.38**, dual false → **HOLD**. Wings OTM 15.0p / 20.0c. Mid greener vs 12:42 (+24.78); adverse worse (close spreads).
2. Retested F IC DNA at close 14.365: fade-below-14.15 **never printed**. 14p quotes again (net 0.085) but pick still `put_wing_none`; call 15/16 net 0.05 < need 0.08. **Friday fade thesis closed.**
3. Hunt beyond leftover (2y regime + RH close): SNAP +2.45% **neutral** IVR75 (first-live CSP ghost; pack-owns); TSLL +1.45% **bearish** IVR94; CCL −1.06% **neutral** IVR25; PFE flat neutral. Pack `watch_once` **NO_SETUP** on living PLTR `pcs_bull_only:neutral`.
4. Shipped `trader_platform/execution/preserve_rth_next_seed.py` + CLI + hook in `trader_quality_cycle` after campaign. Tests restore marks/hunt onto current working ids.
5. Rewrote INTEREST for weekend/Monday: leftover INTC + F Monday fade prove + SNAP/TSLL/CCL hunt; all `rh_wake=false`. Kept hourly AMD/SMCI `n_alive=0` (do not invent DNA).
6. No evolve / no prune / no live / no arm / no hyp yaml / no pack_grade absorb.

## EVIDENCE

- `.cache/platform/coach_close_20260814T1501.json`
- `.cache/platform/rth_eval_marks_latest.json` (stamp 20260814T1501, PT 18.38)
- `trader_platform/execution/preserve_rth_next_seed.py`
- `scripts/trader_preserve_rth_next_seed.py`
- `scripts/trader_quality_cycle.py` (`next_seed_preserve`)
- `tests/test_preserve_rth_next_seed.py`

## DURABLE

- Campaign-thin NEXT_SEED is a systems bug, not a new manage decision. Restore from sidecar + marks after every campaign.
- Friday F fade-below-14.15 is closed. Monday prove is a **new session**, not a reprint of 14.38 wings-dead.
- SNAP first-live CSP remains a lane-board ghost; pack-owns new opens. TSLL is bearish — not a bull-put overlay.

## VERIFICATION

- `pytest tests/test_preserve_rth_next_seed.py tests/test_paper_book_guards.py` (see closeout)
- live_armed=false · ken_required=false · EDGE still frozen
- No MCP place_* · no broker login

## INTEGRATION

Selective commit: preserve module + CLI + quality_cycle hook + tests + wake/INDEX/LATEST + NEXT_SEED. Concurrent pack_grade / campaign.sh / promote / data.py / trader_paper_mark.py left unstaged. No hypotheses.yaml.

## LESSON

Worker cycles will keep thinning NEXT_SEED every ~2 minutes while EDGE is frozen. A rich RTH seed that is not sidecar-preserved is already gone. Hook restore into the cycle, do not ask the next coach to re-derive.

## NEXT SEED

`manage_open_paper_campaign` — Monday RTH remake leftover INTC on live RH; only reopen F IC if new-session fade <14.15 restores **both** wings. ken_required=false.

GATES: none (Ken freeze still holds; do not unfreeze EDGE or ARM)

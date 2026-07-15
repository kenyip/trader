# Trader doctrine update — Layered Edge Stack — 2026-07-15T1347

## Outcome

Applied Ken/Jarvis first-principles strategy reasoning as durable Trader doctrine and BUILD prompt contract.

## Changes

- Added `docs/TRADER_LAYERED_EDGE_DOCTRINE.md`.
- Updated `docs/TRADER_PLATFORM_GOAL.md` to point to the doctrine and replace the old broad edge stack with the explicit forecast → payoff → regime → risk → evidence stack.
- Updated `configs/build_lab_free_goal.txt` so future BUILD wakes must include the Layered Edge Stack in strategy decision charters and so challenger/finalizer reject incomplete stack claims.

## Doctrine encoded

Trader should not search for “an options strategy.” Trader should search for a repeatable market forecast that can be expressed through a defined-risk option payoff, works only in named regimes, has explicit entry/exit/risk rules, and can be falsified before paper or live.

Preferred initial exploration lanes remain preferences, not allowlists:

1. Long-biased theta income via bull put / put credit spreads.
2. Directional swing capture via call debit spreads.
3. Long-biased diagonal income via bullish diagonals.

## Verification

- `LAYERED_EDGE_DOCTRINE_ASSERTIONS_OK` — doctrine/config/platform references and required terms present.
- `.venv/bin/python -m unittest discover -s tests -v` — 297/297 OK.
- `git diff --check` — OK.

## Safety / authority

- No broker login, orders, paper placement, shadow/live promotion, funding, or arming.
- The auto-started `2026-07-15T1344` BUILD had only orientation/prompt/log prelude and no strategy charter or experiment; it was stopped and its pre-action residue removed before this doctrine update.

## Next

Next Trader BUILD wake should inherit the doctrine from `configs/build_lab_free_goal.txt` and produce a strategy charter with the full Layered Edge Stack before claiming any strategy progress.

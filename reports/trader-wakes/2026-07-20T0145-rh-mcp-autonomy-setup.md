# WAKE — 2026-07-20T0145 rh-mcp-autonomy-setup

WAKE: 2026-07-20 ~01:45 PDT  
PHASE: PAPER / BUILD  
SLEEVE: 3000 planning (Agentic cash $0)  
CHOSE: RH MCP account probe + autonomy setup for Trader self-direction toward live readiness

## DID

- Live RH MCP: get_accounts, portfolio, positions, quotes, option chains, options upgrade URL
- Confirmed isolation: Agentic agentic_allowed=true; main non-agentic
- Documented gaps: unfunded, no options level, MCP single-leg only, platform place_* NotImplemented
- Wrote `docs/AGENTIC_SLEEVE_AUTONOMY_SETUP.md` (funding T0.5→T1, autonomy contract, MCP-native first live)
- Updated AGENTIC_AUTONOMY_POLICY Stage2 status + readiness LATEST
- Receipt script `scripts/trader_write_rh_probe_receipt.sh` → `.cache/platform/rh_mcp_probe_LATEST.json`

## EVIDENCE

- Agentic ••••8507: cash, $0, option_level empty, agentic_allowed true
- Main ••••5223: option_level_3, agentic_allowed false (correct)
- IWM chains readable; SPY/IWM/AMZN quotes OK
- No place_* invoked

## VERIFICATION

- Read-only MCP only; agentic.enabled remains false
- Docs secret-safe (masked account digits in prose; upgrade URL uses full account_number as RH requires)

## DURABLE

Autonomy + MCP constraint now first-class so BUILD prefers live-feasible structures for first arm.

## NEXT SEED

Ken: options L2+ + optional $300-500 test. Trader continuum: quality TOP_HYP biased to MCP-native CSP/single-leg; keep multi-leg paper research.

## GATES

none opened

# Promotion Gates

Code: `platform/promotion_gates.py`  
Policy: [AGENTIC_AUTONOMY_POLICY.md](AGENTIC_AUTONOMY_POLICY.md)

## Ladder

```
candidate → testing → paper → shadow → live
                 ↘ rejected / retired
```

**No auto-promote to `live` without an evidence record.**

## Checklist (required for live)

| Gate | Meaning |
|---|---|
| walk_forward | OOS / walk-forward validation recorded |
| scenarios | 12-regime suite green or explicit tradeoffs |
| costs | Slippage/cost assumptions stated |
| drawdown | Cost function / catastrophe threshold respected |
| evidence_record | ≥1 `evidence_links` entry on the hypothesis |
| null_results_logged | Competing falsifications noted (preferred) |
| risk_envelope | Fits `platform/risk_limits.yaml` |
| human_arm_live | Stage1 OAuth + `agentic_live` arming on Ken’s Mac |

M0–M1: only `evidence_record` is auto-checked from registry data; other gates are structured TODOs that still **block live** until marked pass/skip via overrides or future wiring to `validate_rule.py` / `run_scenarios.py`.

## CLI

```bash
.venv/bin/python -m platform.hypothesis_cli gate hyp_short_premium_tsla --target live
.venv/bin/python -m platform.hypothesis_cli status hyp_pmcc_income testing
.venv/bin/python -m platform.hypothesis_cli status hyp_x live --evidence path/to/report.md
```

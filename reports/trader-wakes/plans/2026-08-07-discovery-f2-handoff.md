# Plan — Discovery F2 → pack-grade handoff fix

**Branch:** `feat/discovery-f2-handoff`  
**Worktree:** `/Users/jarvis/dev/trader-handoff-gap`  
**Authority:** research/framework only — no live/arm/paper place/broker  
**Do not touch:** `trader_platform/data/hypotheses.yaml` (worker owns), live broker, densify re-arm

## Problem (pinned)

`MULTI_SYMBOL_REPROVE` only re-proves bootstrap densify shortlist DNA (old 07-19 cells). Discovery marathon writes `STRATEGY_ADVANCED_F2` prove_evals under `.cache/platform/spine/discovery/gen_*/` but **nothing promotes them into the reprove pool**. Six pack-grade-shaped new-axis candidates exist (incl. AMZN+INTC book-testable) and never get tested → `n_quality_pass=0` forever.

Root cause doc: `~/.local/state/jarvis/trader-guidance/knowledge/2026-08-05-discovery-bootstrap-handoff-gap.md`  
Census: `.../2026-08-07-discovery-archive-full-pack-grade-census.md`

## Goal / done

1. New loadable surface: `reports/bootstrap/DISCOVERY_F2_CANDIDATES.json`
2. Ingest script + library API scans discovery prove_evals and writes that surface
3. `load_dna_items_for_multi_symbol` / `run_multi_symbol_pack` **include** discovery F2 candidates (with valid `spec_path`)
4. Quality cycle calls ingest before multi-symbol reprove (or multi-symbol always loads the surface)
5. Tests green (unit + optional small integration with fixtures)
6. Acceptance: after ingest + multi-symbol run, `MULTI_SYMBOL_REPROVE` results include ≥1 new-axis candidate_id matching `dn_d5|dn_d7|g_d5|g_d7`

## Design

### A. `trader_platform/research/discovery_f2_handoff.py` (new)

```python
# Core API
scan_discovery_f2_candidates(
  discovery_root: Path,  # default .cache/platform/spine/discovery
  *,
  min_generated_at: str | None = "2026-08-05",  # optional filter
  require_f2: bool = True,
  min_dual_cost_symbols: int = 1,  # include single-symbol F2 too; pack-grade is multi_symbol_reprove job
  min_trades_worst_axis: int = 12,
) -> list[dict]

write_discovery_f2_candidates(path, candidates) -> Path  # atomic write

# Candidate row shape (stable):
{
  "candidate_id": str,
  "family_id": str | None,
  "spec_path": str,  # absolute path to *__prove.json or *screen.json sibling if prove missing — MUST exist
  "prove_eval_path": str,
  "symbols_proved": [str, ...],  # dual-cost pass + thick enough
  "n_holdout_pass": int,
  "funnel_stage_after": str,
  "decision": str,
  "generated_at": str,
  "source": "discovery_prove_eval",
  "axis_markers": ["dn_d5", ...],  # parsed from candidate_id
  "pack_grade_shaped": bool,  # >=2 thick dual-cost symbols
  "capital_path_ok": False,  # honesty: F2 discovery ≠ B3/B4 capital path
  "live_authority": False,
  "trading_authority": False,
}
```

Rules:
- Scan `**/ * __prove_eval.json` under discovery root
- Admit when `decision` contains F2 / `STRATEGY_ADVANCED_F2` OR `funnel_stage_after == F2_UNTOUCHED_HOLDOUT`
- Resolve `spec_path`: prefer sibling `__prove.json`, else `__screen.json`, else path from eval payload if present
- Skip if no readable spec_path
- Dedupe by candidate_id keeping newest generated_at / most symbols_proved
- Atomic write via temp + replace
- Never claims pack-grade or live authority

### B. `scripts/trader_ingest_discovery_f2.py` (new CLI)

```
just trader-ingest-discovery-f2   # or python scripts/trader_ingest_discovery_f2.py
--discovery-root
--out reports/bootstrap/DISCOVERY_F2_CANDIDATES.json
--min-generated-at
--json stdout summary: n_candidates, n_pack_grade_shaped, n_new_axis
```

### C. Wire bootstrap multi-symbol

In `trader_platform/research/bootstrap.py`:
- `DEFAULT_DISCOVERY_F2 = reports/bootstrap/DISCOVERY_F2_CANDIDATES.json`
- `load_dna_items_for_multi_symbol(..., include_discovery_f2: bool = True)`  
  Append discovery candidates after densify shortlist; dedupe by candidate_id
- `run_multi_symbol_pack` passes through `include_discovery_f2=True` by default
- Report payload fields: `n_discovery_f2`, `discovery_f2_candidate_ids` (or include in honesty)

### D. Quality cycle

In `scripts/trader_quality_cycle.py` multi-symbol step:
- Before `trader_multi_symbol_reprove.py --from-shortlist`, run ingest CLI (best-effort; log rc)
- Or call library function if importing is cleaner

### E. Justfile

```
trader-ingest-discovery-f2:
  .venv/bin/python scripts/trader_ingest_discovery_f2.py
```

### F. Tests `tests/test_discovery_f2_handoff.py`

- Fixture tiny prove_eval + prove.json under tmp discovery root
- scan admits F2, rejects non-F2
- write + load roundtrip
- `load_dna_items_for_multi_symbol` includes discovery row when surface present
- pack_grade_shaped true when 2 thick dual-cost symbols
- Does not require network or full registry

### G. Optional STRESS_ROTATION note

**Do NOT** set `capital_path_ok=true` on discovery F2 without B3/B4. That would lie.  
Pack-grade path is multi_symbol_reprove, not capital_path_ok.  
If a pointer section is useful, add `discovery_f2_refs` list on DISCOVERY_F2 surface only.

## Explicit non-goals

- No hypotheses.yaml mutation
- No weakening min_symbols_with_f2 / trade bars / $300 first-live
- No densify re-arm
- No engine experiment in this slice (P2 next)
- No absorbing main worker dirt

## Verification

```bash
cd /Users/jarvis/dev/trader-handoff-gap
.venv/bin/python -m pytest tests/test_discovery_f2_handoff.py -q
# use canonical venv if worktree has no .venv:
/Users/jarvis/dev/trader/.venv/bin/python -m pytest tests/test_discovery_f2_handoff.py -q

# live ingest against real cache (read-only scan → write bootstrap surface in worktree)
/Users/jarvis/dev/trader/.venv/bin/python scripts/trader_ingest_discovery_f2.py --json
# expect n_pack_grade_shaped >= 6 (or >=1) if cache present via shared .cache

# optional dry multi-symbol if fast enough; else unit proof is enough for ship
```

Symlink or use real `.cache` from main repo: worktree may share nothing — point `--discovery-root /Users/jarvis/dev/trader/.cache/platform/spine/discovery` for live smoke.

## Commit message

```
fix(handoff): ingest discovery F2 prove_evals into multi-symbol reprove pool

Close the discovery→bootstrap handoff gap so new-axis F2 candidates
are loadable and included in MULTI_SYMBOL_REPROVE instead of only old densify cells.
```

## After ship (coordinator)

1. Merge to main when clean window (or PR merge without touching worker YAML)
2. Run ingest on main + multi-symbol once
3. Confirm MULTI_SYMBOL_REPROVE includes dn_d5_* candidates
4. P1 clean-window + P2 engine experiment next

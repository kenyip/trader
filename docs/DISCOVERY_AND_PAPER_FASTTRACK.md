# Expanding sims / knobs · parallel · paper fast-track

## Expand the simulation grid (knobs)

Edit **`configs/discovery_grid.json`** — no code change required:

| Axis | Meaning |
|---|---|
| `dtes` | Days to expiration targets |
| `profit_targets` | Fraction of credit to take as profit (0.5 = 50%) |
| `deltas` | Short-leg target delta |
| `iv_rank_mins` | Minimum IV rank filter |
| `policies` | `pcs_bull_only` / `pcs_non_bear` / `router` |
| `min_credit_pcts` | Min credit as fraction of width |
| `spread_widths` | Wing width in $ (optional; omit/`[]` = keep seed default) |

**After editing:** restart discovery (grid is cached per process).

```bash
# see new size
.venv/bin/python -c "from trader_platform.research.discovery_loop import all_grid_mutants, list_seed_specs, load_grid_config; print(load_grid_config()); print(len(list_seed_specs())*len(all_grid_mutants()))"

just trader-discover --until-f2 --keep-going --workers 9 --max-mutants-per-gen 12
# background marathon (writes marathon.pid for trader-progress):
# nohup .venv/bin/python -u scripts/trader_discover.py --until-f2 --keep-going --workers 9 --max-mutants-per-gen 12 --summary-only \
#   > .cache/platform/spine/discovery/marathon.log 2>&1 & echo $! > .cache/platform/spine/discovery/marathon.pid
```

### Other expansion levers

| Lever | How |
|---|---|
| **New forecast seeds** | Add `configs/strategy_specs/*.json` (new mechanism, not just knobs) |
| **Symbols** | Change `symbols` array inside each seed (or pass `--symbols` for a faster subset) |
| **Cost axes** | Dual cost is fixed in `evaluate_proxy` (5% slip + $0.01/leg) — change there for harder proof |
| **Holdout fraction** | `train_fraction` on each StrategySpec (default 0.6) |
| **Gen feed rate** | `--max-mutants-per-gen` ≥ workers so the pool stays full |

Finite bag size ≈ `(# seeds) × (# grid plans)`. Expanding JSON axes grows the bag.

---

## Parallelism

| Flag | Effect |
|---|---|
| `--workers 0` | Auto: **CPU−1** (on a 10-core Mac → 9) |
| `--workers 9` | Explicit |
| `--max-mutants-per-gen 9` | Feed the pool (jobs per generation) |

Mutants in one generation run in a **process pool**. Registry writes stay serial.

```bash
just trader-discover --until-f2 --keep-going --workers 9 --max-mutants-per-gen 9
```

More than `cpu_count` workers usually hurts.

---

## Paper path (plumbing before live)

Sim remains the edge filter. Paper proves **plumbing**:

```text
F2 holdout → promote paper_eligible → paper handoff / plumbing smoke → (later) live arm
```

```bash
just trader-promote-paper              # top diversified F2 → paper_eligible
just trader-paper-handoff --plumbing-smoke   # force one paper ledger order
just trader-paper-handoff --execute-paper    # real setup only (regime must match)
just trader-opportunity                      # watch + dry handoff
```

**Live** still requires: funded Agentic sleeve, options level, risk proof, **explicit Ken arm**. Paper does not auto-live.

---

## Priority Ken set

1. **Sim discovery** (parallel, expanded grid) — primary  
2. **Paper plumbing** — verify OPEN path works  
3. **Live** — only after 1–2 are healthy  

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
| **Symbols / underlyings** | **`configs/discovery_universe.json`** (source of truth). CLI: `just trader-universe` |
| **Cost axes** | Dual cost is fixed in `evaluate_proxy` (5% slip + $0.01/leg) — change there for harder proof |
| **Holdout fraction** | `train_fraction` on each StrategySpec (default 0.6) |
| **Gen feed rate** | `--max-mutants-per-gen` ≥ workers so the pool stays full |

Finite bag size ≈ `(# seeds) × (# grid plans)`. Expanding JSON axes grows the bag.

---

## Symbols / underlyings

Managed list: **`configs/discovery_universe.json`**. Discovery loads `status=active` by default (not each seed’s frozen list).

```bash
just trader-universe                         # counts
just trader-universe list --status active
just trader-universe add TSLA --tags ai_growth,high_vol,liquid --notes "wave2"
just trader-universe demote SOFI --notes "no F1 after denser grid"
just trader-universe activate RKLB           # promote watch → active
just trader-universe remove F                # soft demote
just trader-universe remove F --hard         # delete entry

# one-off override (ignores universe for that run)
just trader-discover --symbols KO,INTC,TSLA --until-f2 --keep-going --workers 9
just trader-discover --no-universe           # fall back to seed JSON symbols
```

| Status | Effect |
|---|---|
| `active` | Evaluated in discovery |
| `watch` | Noted only; not evaluated |
| `demoted` | Soft-removed (kept for history) |
| `banned` | Never use |

**How to pick names (heuristic, not gospel):**

1. **Liquidity** (live path) — options volume/OI, tight markets  
2. **Premium / IV** — higher IV → richer credit *and* fatter tails; dual-cost holdout decides  
3. **Directional bias fit** — long/non-collapse PCS likes names that don’t structurally die; AI/growth mega-caps fit the *theme* but still need holdout proof  
4. **Capital fit** — `$300` max loss → prefer `$1–3` width viable; mega-priced names (NVDA/TSLA) need narrow wings or they fail gates  
5. **Demote on evidence** — no train/F2 after meaningful bag share → `demote`

**SPCX:** not a standard listed ticker (SpaceX private). Space beta proxies on the watch list: `RKLB`, `ASTS`. Activate if you want them in the sim.

Restart discovery after large universe edits so new names get evaluated.

---

## Parallelism

| Flag | Effect |
|---|---|
| `--workers 0` | Auto: **CPU−1** (on a 10-core Mac → 9) |
| `--workers 9` | Explicit |
| `--max-mutants-per-gen 12` | Feed the pool (jobs per generation) |

Mutants in one generation run in a **process pool** (one mutant eval per worker process). Registry writes stay serial. Parent process is `scripts/trader_discover.py`; children are multiprocessing `spawn_main` workers.

```bash
just trader-discover --until-f2 --keep-going --workers 9 --max-mutants-per-gen 12
```

More than `cpu_count` workers usually hurts.

---

## How workers run · reboot / restart

### What is running now

| Piece | Role |
|---|---|
| **Parent** | `scripts/trader_discover.py --until-f2 --keep-going --workers N` |
| **Workers** | N child processes (process pool); each evaluates one mutant at a time across the active universe |
| **PID file** | `.cache/platform/spine/discovery/marathon.pid` (progress UI reads this) |
| **State** | `.cache/platform/spine/discovery_state.json` (`grid_cursor`, gen, workers, symbols) |
| **Log** | `.cache/platform/spine/discovery/marathon.log` |

The current marathon was started with **`nohup`** (survives terminal close, **dies on machine reboot**).

### Auto-restart (Hermes cron)

Hermes job **`trader-desk-b-loop`** runs every **~30 minutes**:

- Script: `~/.hermes/scripts/trader_discovery_cron.sh`
- If a live `trader_discover.py` is already running → skip
- If not → start a new marathon (background) and write `marathon.pid`
- After reboot: first cron tick (or manual start below) brings it back
- Resume is safe: **`grid_cursor`** + living registry skip already-evaluated DNA

Also: **`trader-opportunity-loop`** every ~60m (market watch / paper handoff — not the sim workers).

Requires the **Hermes gateway / cron scheduler** to be up after login.

### Manual start (any time)

```bash
cd ~/dev/trader

# one-shot foreground (blocks until campaign stops)
just trader-discover --until-f2 --keep-going --workers 9 --max-mutants-per-gen 12

# background marathon (recommended after reboot)
mkdir -p .cache/platform/spine/discovery
nohup .venv/bin/python -u scripts/trader_discover.py \
  --until-f2 --keep-going --workers 9 --max-mutants-per-gen 12 --summary-only \
  >> .cache/platform/spine/discovery/marathon.log 2>&1 &
echo $! > .cache/platform/spine/discovery/marathon.pid

# or let the cron script do it
bash ~/.hermes/scripts/trader_discovery_cron.sh

just trader-progress          # confirm ● RUNNING · parallel N workers
```

### After reboot checklist

1. Machine up, `~/dev/trader` + `.venv` available  
2. Hermes cron running **or** run the manual block above  
3. `just trader-progress` → `● RUNNING · parallel 9 workers`  
4. No need to re-promote paper seats; living registry is on disk  

**Not auto-started by launchd** today — reboot recovery is Hermes cron (30m) or the manual `nohup` / cron script.

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

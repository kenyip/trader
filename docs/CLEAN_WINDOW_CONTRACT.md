# Clean-window contract (framework)

**Purpose:** let engine experiments and handoff commits land without perpetual `repo_not_clean` veto from quality-worker thrash.

## Rules

1. **One writer at a time for shared surfaces**
   - Worker owns: `trader_platform/data/hypotheses.yaml` thrash, stress rotation churn.
   - Engine / framework owns: strategy_specs, discovery handoff surfaces, engine panels, docs.

2. **Open window** (pause worker)
   ```bash
   just trader-clean-window open -- --minutes 90 --reason engine_experiment
   ```
   - Stops quality worker.
   - Writes `.cache/platform/clean_window/STATE.json` with `closes_at`.

3. **Inside window (green)**
   - Run frozen one-lever engine experiments.
   - Commit experiment artifacts + knowledge.
   - Do **not** restart densify MoA thrash or free evolve storm.

4. **Close window**
   ```bash
   just trader-clean-window close
   just trader-quality-worker status   # must be RUNNING
   ```

5. **Honesty**
   - Clean window is ops/research only.
   - Never live/arm.
   - Do not absorb worker dirt into experiment commits.

## Default cadence (event-driven judgment)

Prefer judgment wakes on:
- `n_quality_pass` flip
- handoff surface refresh with new pack-grade-shaped rows
- family closed with evidence
- clean window opened/closed
- capital_path / first-live seat change

Avoid denser 30m “same blocker” diaries when no clean window and no new evidence.

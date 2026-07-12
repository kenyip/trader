# Trader repository completion contract

This repository is a finance research/paper engine. Evidence and safety gates remain authoritative; this file governs how code, docs, and run artifacts are completed.

## Start clean

Before mutation, run:

```bash
.venv/bin/python scripts/trader_run_completion_gate.py preflight --repo .
```

A dirty checkout, detached head, unfinished Git operation, missing remote, or local/remote divergence is a blocker. Never absorb, discard, stash, reset, or hide pre-existing residue to start another wake.

## Finish shipped and recoverable

A changed-repository wake is `RUN COMPLETE` only when all are true:

1. Scoped implementation/artifacts are complete or the claim is explicitly falsified/narrowed.
2. Claim-relevant behavioral, boundary, negative-control, regression, and full-suite verification is green.
3. The wake report records exact evidence, failures, outcome, durable lessons, unresolved risks, and exactly one NEXT seed or `DIMINISHING_RETURNS`.
4. Learning is promoted deliberately: repo docs/reports for project truth/history; Trader skills for reusable procedures/pitfalls; compact profile memory only for stable stance/preferences. Superseded guidance is rewritten, not stacked.
5. Intended paths are reviewed for secrets/private positions and committed coherently. Raw session logs, auth, `.env`, caches, provider dumps, and live position files stay untracked.
6. The run branch is pushed normally, integrated into `main`, `main` is pushed, the run commit is an ancestor of remote `main`, and the canonical checkout is clean.
7. The deterministic postflight gate passes and atomically writes its receipt under `.cache/platform/completion/`.

Wrapper BUILD wakes use `postflight --stamp <stamp>` and retain the full MoA artifact contract. Manual/direct-main infrastructure wakes use `postflight --report <tracked-wake-report>` with the pre-mutation base and integrated run commit. Both paths prove clean synchronized `main`, remote ancestry, and an advanced HEAD; both emit `mode: postflight` and `completion: true`. Preflight emits `completion: false` and is forbidden from writing a completion receipt.

Executor/challenger output is a partial phase, never completion. On failure preserve the run branch and artifacts, report `RUN INCOMPLETE` with exact residue, and resume the contract-v2 BUILD stamp with `scripts/trader_build_lab_moa.sh --stamp <stamp> --resume` (or `--finalizer-only` after a successful critique).

## Safety

No force push, destructive cleanup, secret resolution, gateway restart, public release/PR, broker login, broker paper/live order, agentic arm, or shadow/live promotion is authorized by this completion contract. Local research, simulation, and paper-ledger artifacts remain allowed under existing Trader doctrine.

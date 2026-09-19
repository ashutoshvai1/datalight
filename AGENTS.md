# Datalight agent instructions

## Purpose

Build a trustworthy local data-reliability monitor for the Norrin challenge: understand data, assess quality, monitor changes, explain evidence, and preserve human review. Keep the complete vision in the README and roadmap while implementing only the agreed phase.

## Read before working

1. This file, then [current state](devlog/current.md) and [durable decisions](devlog/decisions.md).
2. Only the workstream and stable documentation linked from the active task.
3. `git status --short --branch`; preserve unrelated tracked and untracked work.

## Non-negotiable boundaries

- Raw observations stay local. Only the typed aggregate payload in `backend/src/datalight/providers.py` may reach a model. Never send rows, observation sequences, evaluation labels, secrets, or original column names to the provider.
- Keep `faultNumber`, `fault_status`, `source`, and `simulationRun` outside detector inputs and prompts. `sample` serves ordering only. Do not infer physical roles from recognizable dataset/header names.
- Respect sequence boundaries. Do not concatenate separate runs into temporal evidence or invent timestamps/units.
- Treat the initial window as provisional. Quality defects, deviations, hypotheses, and causal diagnoses are different claims.
- Every conclusion needs evidence, an uncertainty/basis statement, and traceability. Do not display fabricated metrics or placeholder findings as real results.
- Reviews append history; they never erase evidence, alter original findings, or silently change thresholds/baselines.
- Batch results and checkpoints commit together. Preserve source identity, bounded memory, job leases, and retry safety.
- Exclude real datasets and credentials from Git, images, logs, fixtures, and screenshots. Synthetic fixtures are explicitly allowed.

## Collaboration

- Claim one bounded task with an owner, relevant paths, dependencies, and acceptance criteria in the active workstream.
- Concurrent contributors use separate branches/worktrees. Agree on API contracts and schema changes before parallel implementation.
- The integration owner coordinates migrations, generated contracts, root instructions, and `devlog/current.md`. Workstream owners maintain focused context and provide handoff notes with their changes.
- Delegate only independently useful, explicitly scoped tasks. Do not let multiple agents edit the same contract or migration independently.
- Keep changes within the claimed scope. Do not add infrastructure or later-phase features merely because they may be useful.
- Never paste API keys into chat or docs. Keep model credentials backend-only in ignored configuration.

## Context ownership

- `devlog/current.md`: the sole live coordination page; replace stale state, retain stable headings, keep it around 100 lines.
- `devlog/decisions.md`: durable project choices and rationale, linked to stable implementation/docs.
- `devlog/workstreams/<name>.md`: active workstream context, interfaces, relevant evidence, and next steps. Create only when real work needs it.
- `docs/`: architecture, development procedures, and the phased roadmap.
- Application database: operational reports, evidence, flags, model calls, and human reviews.
- Git: chronology. Devlogs are curated context, not transcripts, command dumps, experiments, or per-agent diaries.

## Validation and handoff

- Use `make check` for the foundation's lint, type, CPU-test, build, and documentation checks.
- Run `make test-postgres` when persistence, migrations, controls, or queue behavior changes.
- Run the browser workflow against the synthetic Docker deployment for user-flow changes.
- Regenerate types with `make types` whenever public API schemas change; commit both generated files.
- Use `make smoke-data CSV_PATH=...` for bounded-memory checks on real input; do not commit real-derived results.
- After work, update the relevant workstream and any changed durable decision. The integration owner reconciles current state, blockers, validation evidence, and ordered continuation steps.
- Report checks actually run and distinguish skipped/unverified integration from successful verification. Never label the Norrin service verified merely because the adapter works with a fake transport.

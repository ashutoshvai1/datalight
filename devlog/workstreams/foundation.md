# Foundation

## Objective

Deliver a real, recoverable slice of the mounted-file workflow with operator-visible evidence and durable review. Preserve the broader vision without presenting deferred features as implemented.

## Ownership

Integration owner: current implementation agent. Scope: initial monorepo, pure analysis/ingestion, API/worker/storage, three React areas, Compose, CI, and collaboration documentation. No concurrent file ownership is active. Future contributors claim bounded tasks and coordinate shared contracts/migrations before editing.

## Interfaces

- Backend Pydantic/OpenAPI contracts generate frontend types; run `make types` after changes.
- Ingestion returns metadata-free bounded windows; analysis is independent of transport/storage.
- Provider takes only a typed derived summary; no observations or source names.
- Replay atomically commits batch evidence and cursor. Human review appends without updating original conclusions.
- Root devlog reconciles status; this page owns focused implementation context.

## Evidence

- [Architecture](../../docs/architecture.md): ownership, data flow, crash/retry semantics, and limitations.
- [Development guide](../../docs/development.md): reproducible commands and test isolation.
- Synthetic fixture contains controlled shifts, missingness, a sequence reset, legitimate holds, and a zero-variance channel. No industrial rows are copied.
- Automated tests cover metadata isolation, quality suppression, record boundaries, lease recovery, transaction rollback, model payloads, and human review.
- Verification status and live-provider outcomes are maintained in [current state](../current.md).

## Next steps

Foundation is ready for review; no implementation task remains claimed. See current state for exact validation results and remaining judge-readiness measurements. Broader diagnostic/rule/portability work awaits an explicit next-phase decision.

The provider uses a strict typed summary and validates complete JSON (including a single code fence), one hypothesis per channel, and exact evidence references. Calls are limited to the initial report and first deviation per run. The live model ID is configurable and was discovered from the service, not inferred from its URL.

For concurrent follow-up work, coordinate API/schema changes through one integration owner. Frontend pages are split under `apps/web/src/pages`; statistical functions remain pure in `backend/src/datalight/analysis.py`, with ingestion, orchestration, providers, and persistence separate.

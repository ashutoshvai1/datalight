# Foundation

## Objective

Deliver a real, recoverable slice of the mounted-file workflow with operator-visible evidence and durable review. Preserve the broader vision without presenting deferred features as implemented.

## Ownership

Completed documentation follow-up: integrated [DATASET.md](../../docs/DATASET.md) as the primary testbed/demo reference, linked from product, agent, architecture, development, and roadmap documentation. [D009](../decisions.md) preserves the generic-product boundary: dataset facts inform offline work, not implicit detector knowledge or model prompts. Current source conventions and remaining portability work are explicit; application behavior is unchanged.

Completed follow-up: current agent selected two complete original-data runs for the local demo (one labeled normal, one labeled faulted). Bounded source inspection, reproducible extraction, local mount configuration, and live replay validation are complete. Both runs and sequence coordinates are preserved, selection metadata stays outside detector inputs, synthetic CI fixtures are unchanged, and the running app uses the selected pair with successful model interpretations. See current state for exact checks.

Integration owner: current implementation agent. Scope: initial monorepo, pure analysis/ingestion, API/worker/storage, three React areas, Compose, CI, and collaboration documentation. No concurrent file ownership is active. Future contributors claim bounded tasks and coordinate shared contracts/migrations before editing.

Completed follow-up: current agent owned original-data demo validation. Scope: an ignored contiguous CSV slice, local Compose configuration, replay/browser checks, and live provider verification. The mounted slice yields a report, replay respects sequence boundaries and reaches EOF, and the demo remains available at localhost:8080 with existing history preserved. Both live model purposes were tested at 30 and 120 seconds and timed out; see current state for the availability limitation.

## Interfaces

Completed endpoint retest: authenticated discovery succeeds and a live 52-channel summary completion returns eight validated hypotheses in 20.88 seconds. Retest attempts are appended to the existing model-call audit without changing replay, reviews, or published findings. The local endpoint was corrected from base `/v1` to full `/v1/chat/completions`; the running worker already used the full route. See current state for the latest verification and earlier timeouts.

- Backend Pydantic/OpenAPI contracts generate frontend types; run `make types` after changes.
- Ingestion returns metadata-free bounded windows; analysis is independent of transport/storage.
- Provider takes only a typed derived summary; no observations or source names.
- Replay atomically commits batch evidence and cursor. Human review appends without updating original conclusions.
- Root devlog reconciles status; this page owns focused implementation context.

## Evidence

- [Architecture](../../docs/architecture.md): ownership, data flow, crash/retry semantics, and limitations.
- [Development guide](../../docs/development.md): reproducible commands and test isolation.
- [Primary testbed reference](../../docs/DATASET.md): schema, ordering, labels, and observed characteristics for offline source/demo work; not an application-wide input contract.
- Synthetic fixture contains controlled shifts, missingness, a sequence reset, legitimate holds, and a zero-variance channel. No industrial rows are copied.
- Automated tests cover metadata isolation, quality suppression, record boundaries, lease recovery, transaction rollback, model payloads, and human review.
- Verification status and live-provider outcomes are maintained in [current state](../current.md).

## Next steps

Foundation is ready for review; no implementation task remains claimed. See current state for exact validation results and remaining judge-readiness measurements. Broader diagnostic/rule/portability work awaits an explicit next-phase decision.

The local demo uses root `demo.csv`: two full 960-sample test runs, `simulationRun=1`, normal (`faultNumber=0`) then faulted (`faultNumber=1`). Reproduce with `uv run --project backend python scripts/prepare_demo.py te_process.csv`. The extractor selects labels offline and preserves original fields; live analysis and prompts still exclude evaluation metadata. Provenance and validation stay in ignored `runtime/`. `.env` preserves the mount path and a 120-second provider timeout. Use New analysis with 500 initial observations to replay the pair. Synthetic-only browser/restart scripts still require the unchanged synthetic fixture; do not run them against this real-data session.

The provider uses a strict typed summary and validates complete JSON (including a single code fence), one hypothesis per channel, and exact evidence references. Calls are limited to the initial report and first deviation per run. The live model ID is configurable and was discovered from the service, not inferred from its URL.

For concurrent follow-up work, coordinate API/schema changes through one integration owner. Frontend pages are split under `apps/web/src/pages`; statistical functions remain pure in `backend/src/datalight/analysis.py`, with ingestion, orchestration, providers, and persistence separate.

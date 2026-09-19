# Current state

## Objective

Foundation implemented and verified: mounted CSV → initial report → batch monitoring → evidence → persistent human review. Preserve the [roadmap](../docs/roadmap.md); Phase 2 is not selected.

## Constraints

- Raw data stays local; model egress accepts only typed aggregates.
- Evaluation labels/metadata cannot influence live detection or interpretation.
- Reference is provisional; sequence boundaries are explicit; quality and deviations are distinct.
- Reviews append history and do not adapt thresholds or baselines.
- One local deployment and one active replay. Phase 2 remains TBD.

## Active work

| Workstream | Owner | Status | Integration surface |
|---|---|---|---|
| [Foundation](workstreams/foundation.md) | Initial implementation agent; handoff ready | Complete | API/OpenAPI, migrations, Compose, root docs |

## Blockers

None for foundation. Full-file throughput/storage measurement and second-provider verification remain judge-readiness work, not completed claims.

## Validation

Verified locally on 2026-09-19:

- 15 CPU/backend tests: metadata isolation, sequence/hold semantics, quality/deviation separation, source replacement, lease recovery, atomic rollback, reviews, provider egress/failure handling, and selected-finding limits.
- 2 PostgreSQL tests: clean migrations/schema drift, concurrent bootstrap/claims, append-only evidence.
- Python lint/types, frontend TypeScript/ESLint/production build, generated API contracts, and devlog links/structure pass.
- Docker starts all four runtime services after migrations and automatically produces a synthetic report.
- Browser workflow passes: evidence, pause/resume, fast-forward/EOF, override/reload, desktop/mobile layout, no JavaScript errors.
- Actual database/API/worker restart preserves checkpoint, acceptance/question/override records, and original conclusion; replay completes 1,600 rows in 12 unique contiguous batches.
- Read-only Docker mount smoke on the 6,011,495,524-byte CSV: 20,500 observations, 52 channels, 56.5 MiB peak RSS, 3.08 seconds. Partial scan only; no real-derived artifacts committed.
- Norrin live synthetic-summary calls succeed for both initial hypotheses and selected-deviation interpretation. Exact model discovered via authenticated `/v1/models`; invalid earlier attempts remain visible in the local audit history.

## Next steps

1. Review the running synthetic demo at localhost:8080 and the [development guide](../docs/development.md).
2. Before judging, measure a full replay's runtime and database growth; use fast-forward to reach row 250,001 without skipping batches.
3. Select Phase 2 explicitly from the [coverage gaps](../docs/roadmap.md).

The local ignored `.env` contains the provisioned provider settings; no key is in repository files. The running Compose project uses the synthetic fixture. GitHub Actions is configured for pushes and pull requests; consult its run status separately from the local verification recorded above.

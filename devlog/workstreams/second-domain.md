# Second-domain demonstration

## Objective

Demonstrate generic rule extraction, drift detection and evidence-grounded investigation on synthetic web-service telemetry through the existing CSV upload workflow. The implementation plan is approved; no causal-diagnosis claim or production detector change is included.

## Ownership

Owner: integration agent. Scope: offline generator, committed synthetic CSV, focused backend/browser tests, synthetic model fixture and documentation. Dependencies: existing upload, replay, reviewed rules and question APIs. Preserve the completed confidence feature and all existing demos.

## Interfaces

No production API, schema, database or UI changes. Four numeric columns, 1,500 observations, 500-row reference and 100-row batches. Model payloads keep opaque IDs and aggregate evidence. Acceptance requires baseline-only replay, renamed-header equivalence, applied-rule evidence and cited discussion.

## Evidence

Verified on 2026-09-20:

- `make check` passes: Ruff, mypy, TypeScript, ESLint, 65 CPU tests, documentation links and production build. Existing dependency deprecation warnings and Vite chunk-size advisory remain non-blocking.
- The 56,298-byte committed CSV regenerates byte-for-byte. Both original and neutral headers complete all 1,500 rows in ten monitoring batches with identical trigger metrics and intervals. The two pre-change batches are OK; traffic has no triggers; CPU, latency and errors each trigger drift; no quality warnings occur. Initial reports remain unchanged.
- Separate applied-rule replay matches exactly the 532 observations where latency exceeds 400 (first at row 967). Counts, sparse intervals, rule identity and persisted evidence are checked against the CSV.
- Initial interpretation, proposal and question mocks verify the real request boundary: original headers and observations are absent, typed payloads carry opaque IDs, and returned citations resolve. Mock output tests integration, not model reasoning.
- All five browser workflows pass against `datalight-qa` on localhost:18080. The new workflow uploads the committed CSV, verifies the unapplied proposal, applies it, plays all ten batches, asks a question, opens threshold evidence and reloads persisted discussion. Understanding and monitoring screenshots were inspected; artifacts remain ignored under `apps/web/test-results/`.
- Two actual calls to the configured Norrin provider succeed using a temporary local database and synthetic aggregates: a `c003 > 400` fault-effect proposal, followed by an answer citing five valid evidence IDs. The answer identifies the three level deviations and 100 final-batch custom-rule violations, and explicitly states that the evidence does not establish cause. Both recorded request payloads pass the privacy checks. This is one successful live example, not general model-accuracy evidence.
- No production source, API contract or database migration changed. PostgreSQL-specific tests were not rerun because persistence and controls were unchanged. The operator stack at localhost:8080 was not restarted; the demo works through its existing upload flow.

## Next steps

Use the [walkthrough](../../docs/SECOND_DOMAIN_DEMO.md) for presentation: first replay without a custom rule, then optionally repeat with the reviewed latency rule and live-provider discussion. Synthetic QA responses remain visibly labeled as test output.

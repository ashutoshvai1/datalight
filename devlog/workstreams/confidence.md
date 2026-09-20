# Suspected-fault confidence

## Ownership and scope

Owner: integration agent. Implement the approved evidence-v1 Low/High decision confidence policy across deterministic evaluation, persisted decision evidence, provider aggregates and UI. Dependencies: existing monitoring-v2 replay and applied rules. No detection threshold changes or model-assigned confidence.

## Acceptance

Every new suspected-fault decision has an explainable, reproducible label. Persistence crosses batches and restarts, respects discontinuities, and commits with the checkpoint. Legacy decisions remain readable without backfill. Verify CPU, PostgreSQL, generated contracts and synthetic browser workflows.

## Status

Implemented. Policy: ten same-direction abrupt/level evaluations, three drift checks, or ten applied fault-rule matches; automatic evidence also requires a usable initial profile and 50 reference measurements. Any qualifying evidence within the batch wins. Quality-only rules and unrelated weak evidence cannot promote confidence. The initial reference remains provisional.

## Interfaces and compatibility

- Decision JSON contains optional typed confidence with policy, label, reason, evidence IDs and a single strongest calculation basis. Temporal/rule evidence also retains the strongest basis per source.
- Existing JSON detector state stores abrupt/level and rule persistence; the existing drift streak is reused. Prefix context is never counted twice. Missing new counters start at zero. Counter/evidence/checkpoint publication is atomic.
- Old decisions read with null confidence and show “Confidence not recorded”; OK hides the label. Reviews and the legacy finding-level `measured` field are unchanged. No migration or backfill.
- Question context includes typed confidence with opaque IDs; the provider does not assign it. No additional model call. API contracts regenerated.

## Verification

- `make check`: 62 CPU tests, Ruff, mypy, TypeScript, ESLint, docs and production build pass. Covers 9/10 boundary, sustained/isolated and opposite-direction changes, reference count/usability, constant references, rule types and discontinuities, batch-size-invariant sample qualification, duplicate replay, reviews, metadata isolation and exclusions.
- `make test-postgres` on isolated QA port 15433: six tests pass, including rollback before batch commit followed by retry and duplicate delivery. Only disposable test schemas are used.
- Four synthetic Playwright workflows pass on port 18080. The confidence workflow checks Low/High, evidence drawer, override/reload, historical missing fields and OK. Desktop/mobile screenshots inspected; synthetic screenshots stay ignored under web test-results.
- Local command workarounds: `UV_CACHE_DIR=/private/tmp/datalight-uv-cache` and `WEB='pnpm --config.verify-deps-before-run=false --dir apps/web'`. Docker uses explicit context `lima-docker`. The existing Vite chunk-size advisory and Python dependency deprecations remain non-blocking.

## Handoff

Synthetic QA contains the feature. The operator stack on port 8080 has not been restarted; use the documented `make demo` command to adopt the build. No live Norrin accuracy claim or probability calibration is implied. Exact policy is documented in architecture and the in-app Docs page (D015).

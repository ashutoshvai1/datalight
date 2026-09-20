# Demo backend

Owner: backend agent, isolated branch codex/demo-backend.

Scope: uploads and reader modes, pre-monitoring configuration, reviewed AI rules, bounded historical traces, and backend tests. Public contracts are coordinated with the integration owner; conversation work is owned separately.

Acceptance: local persistent uploads, immutable original references, settings locked at first Play, typed privacy-safe rule proposals and aggregate evidence, bounded three-batch trace windows.

## Implementation and handoff

- CSV multipart uploads use UUID local paths, bounded copies, 256 MiB default application cap, source fingerprints, and a shared persistent uploads volume. The image initializes that directory for UID 10001. The shared `MAX_UPLOAD_BYTES` setting configures both services; the Nginx entrypoint adds 1 MiB of multipart overhead and renders its template.
- Uploaded sources persist `reader_mode=rows`; mounted/legacy sources retain sample resets. Recognized evaluation fields and ordering-only sample remain excluded from numeric detector features.
- Selection and applied rules live in Run.config and lock at first resume. Full initial report/references remain unchanged. Rule proposals use existing leased jobs and ModelCall auditing, opaque eligible IDs and explicitly reviewed normalized definitions; no generated code.
- Decisions store aggregate user-rule matches and immutable rule evidence with precise contiguous violation intervals, with fault versus quality effects. Q&A receives typed rule definitions/counts without coordinates or original names. Integration must retain conversation changes and apply its excluded-channel filter to the union of temporal and user-rule target channels.
- Historical traces read only selected batches and bounded causal context, retaining a compact selected-channel array. The legacy 1000-point default remains compatible; `batch_window=3` opts into explicit paging.

## Validation

Python lint and configured mypy pass. All 29 CPU tests pass, including uploads/cleanup, row order, immutable references, exclusions and first-Play lock, historical forecast alignment, provider proposal privacy/schema/review/apply behavior, unavailable rules, typed user-rule Q&A, and quality-only rules preserving process status. PostgreSQL and Docker/browser checks belong to root integration and are not claimed here. Public generated types must be regenerated after integration.


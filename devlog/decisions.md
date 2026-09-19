# Durable decisions

## D001 — Progressive replay, not full import

The default source is a read-only mounted CSV. Initial analysis and subsequent batches use bounded windows with record-aligned checkpoints. This keeps startup independent of the full dataset's size. Source changes require a new analysis. See [architecture](../docs/architecture.md).

## D002 — One operational database

PostgreSQL stores jobs, analysis artifacts, evidence, and review history. A worker consumes leased jobs; Redis and a second analytics database are unnecessary for the agreed foundation. Raw observations remain in the file.

## D003 — Evidence before interpretation

Deterministic statistics and quality checks are authoritative computed artifacts. Model output is an uncertain interpretation with validated references. Numerical deviation is not a named fault or a causal diagnosis. The initial window is a provisional reference.

## D004 — Metadata isolation and sequence semantics

Remove evaluation fields before analysis/model serialization. Use sample coordinates for ordering only. Reset temporal calculations at new sequences; never invent physical time or rely on familiar sensor header names as evidence.

## D005 — Explicit model egress

An OpenAI-compatible HTTP adapter accepts only typed aggregate summaries. Norrin is the supplied default provider, with configurable endpoint/model/auth. The deployment slug returned HTTP 404. Authenticated `/v1/models` discovery supplied the exact ID `mistralai/Mistral-Large-3-675B-Instruct-2512-NVFP4`; use it as the configurable default. At most one initial-report and one selected-deviation interpretation are queued per run. Credentials remain backend-only. Statistical monitoring continues if interpretation is unavailable. Live access is not implied by fake-transport tests.

## D006 — Human review preserves history

Accept/question/override records are append-only, with self-declared operator names. An override revises the human assessment, not the original machine record or future monitoring. Changing rules, thresholds, or baselines is a separate decision.

## D007 — Context has owners

Use one live coordination page, durable decisions, and active workstream context. Stable knowledge belongs in docs; runtime logs/evidence belong in the database; chronology belongs in Git. No research experiment machinery or unstarted workstream pages. See [devlog guide](README.md).

## D008 — Foundation only; next phase undecided

The full challenge vision is retained as coverage gaps in the [roadmap](../docs/roadmap.md). Future phases remain TBD until selected; do not silently promote backlog items into the current scope.

# Durable decisions

## D001 — Progressive replay, not full import

The default source is a read-only mounted CSV; explicit browser uploads use a separate persistent local volume. Initial analysis and subsequent batches use bounded windows with record-aligned checkpoints. This keeps startup independent of the full dataset's size. Source changes require a new analysis. See [architecture](../docs/architecture.md).

## D002 — One operational database

PostgreSQL stores jobs, analysis artifacts, evidence, and review history. A worker consumes leased jobs; Redis and a second analytics database are unnecessary for the agreed foundation. Raw observations remain in the file.

## D003 — Evidence before interpretation

Deterministic statistics and quality checks are authoritative computed artifacts. Model output is an uncertain interpretation with validated references. Numerical deviation is not a named fault or a causal diagnosis. The initial window is a provisional reference.

## D004 — Metadata isolation and sequence semantics

Remove evaluation fields before analysis/model serialization. Use sample coordinates for ordering only. Reset temporal calculations at new sequences; never invent physical time or rely on familiar sensor header names as evidence.

## D005 — Explicit model egress

An OpenAI-compatible HTTP adapter accepts only typed aggregate summaries. Norrin is the supplied default provider, with configurable endpoint/model/auth. The deployment slug returned HTTP 404. Authenticated `/v1/models` discovery supplied the exact ID `mistralai/Mistral-Large-3-675B-Instruct-2512-NVFP4`; use it as the configurable default. At most one initial-report and one selected-deviation interpretation are queued per run. Credentials remain backend-only. Statistical monitoring continues if interpretation is unavailable. Live access is not implied by fake-transport tests.

## D006 — Human review preserves history

Accept/question/override records are append-only, with a default Local user identity and preserved historical names. An override revises the human assessment, not the original machine record or future monitoring. Changing rules, thresholds, or baselines is a separate decision.

## D007 — Context has owners

Use one live coordination page, durable decisions, and active workstream context. Stable knowledge belongs in docs; runtime logs/evidence belong in the database; chronology belongs in Git. No research experiment machinery or unstarted workstream pages. See [devlog guide](README.md).

## D008 — Foundation only; next phase undecided

The full challenge vision is retained as coverage gaps in the [roadmap](../docs/roadmap.md). Future phases remain TBD until selected; do not silently promote backlog items into the current scope.

## D009 — Generic product, explicit testbed knowledge

Datalight is a generic CSV reliability and monitoring application. [DATASET.md](../docs/DATASET.md) owns descriptive knowledge of the primary Tennessee Eastman testbed and demo source. It informs offline preparation and evaluation, not detector features, universal thresholds, physical-role assumptions, or model prompts. Dataset-specific conventions belong in ingestion adapters/configuration and offline tools; the current reader's recognized metadata/sample fields are a documented portability limit. Future domain rules must be explicit and versioned. See [architecture](../docs/architecture.md) and the [roadmap](../docs/roadmap.md).

## D010 — Approved simplification and explicit setup

The 2026-09-19 approved plan supersedes D008's undecided next phase and D005's two-call cap. A mounted directory supplies selectable sources. Explicit setup defaults to 500 initial samples, 100 per batch and 10 seconds. Initial reporting leaves playback paused. Per-channel synthesis is grouped by eight; questions are separate evidence-grounded jobs. No automatic model call runs for each fault batch.

## D011 — Sample-based detection and separate quality

Rolling 10-sample OLS predicts five horizons; 20-sample adjacent-mean changes, 50-sample persistent slopes, and 10-sample median deviations use fixed initial reference statistics. Rules operate independently of playback batches. Quality warnings remain separate. At the user's explicit choice, insufficient coverage retains OK with a prominent limitation warning. See [architecture](../docs/architecture.md) for exact rules.

## D012 — One batch decision and append-only discussion

Every monitoring batch has one automated decision. Accept/question/override and model answers preserve it. Latest accept/override determines the visible human assessment without adapting the baseline. The simplified UI hides processing ledgers and model wire payloads while retaining backend traceability. Auto-pause and a last-value forecast comparator remain unapproved suggestions.

## D013 — Approved demo improvements

Browser uploads use file row order and keep raw observations local. Legacy mounted sources retain their ordering convention; recognized metadata never becomes a feature. After understanding, users may exclude numeric channels and explicitly apply AI-proposed single-channel rules. First Play locks both settings atomically. The initial report and reference values remain unchanged.

Rule compilation sends only a sanitized explicit request and eligible opaque IDs. Deterministic comparisons, outside-range and missing-value checks produce separate typed evidence and a reviewed fault/quality effect; no model-generated code runs. Questions now include up to ten preceding completed exchanges scoped to the decision, with frozen per-job context and a complete local transcript. Reviews no longer require a name. See [architecture](../docs/architecture.md).

Monitoring defaults to three actual batches and rereads older local windows on demand. A standalone Docs tab explains implemented metrics, detection criteria and evidence; no physical-fault catalogue is inferred from the demo.

## D014 — Sidebar message and one-command demo

The 2026-09-20 follow-up keeps the product tagline only in the sidebar, with one sentence per line; the setup heading remains “Understand first. Monitor next.”. `make demo` starts the local stack and waits for health, selecting prepared demos when present or the synthetic fixture otherwise. Dataset preparation and optional model configuration remain separate from the minimal quickstart.

## D015 — Deterministic suspected-fault confidence

The approved evidence-v1 policy assigns Low/High evidence strength per automated fault decision, independently of fault status, severity and model availability. High requires persistent evidence and, for built-in detectors, a usable initial profile with 50 reference measurements. See [architecture](../docs/architecture.md) for exact criteria and compatibility. Counters cross batch boundaries and commit with the checkpoint; reviews preserve the recorded confidence. No probability calibration, threshold adaptation or history backfill is implied.

## D016 — Synthetic second-domain portability demonstration

The approved [web-service demo](../docs/SECOND_DOMAIN_DEMO.md) uses a committed synthetic CSV and the existing upload flow. Its generator and scenario remain offline; production algorithms, prompts and schemas are unchanged. Baseline-only replay and renamed-header equivalence demonstrate detector portability independently of explicit operator rules. Evidence-backed discussion supports root-cause investigation without claiming causal identification or general detection accuracy.

## D017 — Apache 2.0 licensing

On 2026-09-23, the user selected Apache License 2.0 for Datalight. The root [LICENSE](../LICENSE) contains the official unmodified text, and backend/frontend package metadata use `Apache-2.0`. Third-party dependencies, datasets and challenge materials retain their own terms. See the [licensing workstream](workstreams/licensing.md).

# Current state

## Objective

The approved suspected-fault confidence feature is implemented: deterministic Low/High evidence strength, persisted calculation basis, evidence links, question context and monitoring/decision-card labels. It builds on the completed demo improvements and is deployed to synthetic QA on localhost:18080. The operator deployment on localhost:8080 still runs the prior demo-improvements build until rebuilt.

The product remains generic. [DATASET.md](../docs/DATASET.md) is offline testbed context. Earlier foundation verification is preserved in [the historical handoff](foundation-verification.md).

The [second-domain web-service demo](../docs/SECOND_DOMAIN_DEMO.md) is implemented and verified through existing upload/replay APIs, with a reproducible synthetic CSV and an architectural portability explanation. Production analysis logic is unchanged.

## Constraints

- Raw CSV observations stay local. Model calls contain typed aggregates, sanitized questions/conversation or sanitized rule requests with opaque channel IDs.
- Evaluation metadata and sample never become detector features. Uploaded CSVs use file row order; legacy mounted sources retain sequence resets.
- Initial references remain provisional and fixed. Exclusions and explicitly applied deterministic rules lock at first Play.
- Quality warnings stay separate from process status unless the user explicitly applied a fault-effect rule. Insufficient coverage retains OK with a visible limitation.
- Confidence describes evidence strength, not probability or severity. Fixed evidence-v1 criteria and initial references remain provisional; historical decisions and reviews are not rewritten.
- One active replay; bounded reading, source identity checks, atomic batch/checkpoint commits and append-only evidence/reviews remain intact.
- Compound/temporal custom rules, auto-pause and a last-value predictor comparator remain outside implemented scope.

## Active work

| Workstream | Owner | Status | Integration surface |
|---|---|---|---|
| [Second-domain demo](workstreams/second-domain.md) | Integration agent | Complete; synthetic QA and live provider verified | Synthetic generator/CSV, upload acceptance tests, walkthrough |
| [Fault confidence](workstreams/confidence.md) | Integration agent | Complete; synthetic QA verified | Persistence counters, decision JSON, provider aggregates, UI and Docs |
| [Demo improvements](workstreams/demo-improvements.md) | Integration agent | Complete; deployed on localhost:8080 | Uploads, configuration/rules, conversation, charts, Docs |
| [Simplification](workstreams/simplification.md) | Prior integration | Complete | Initial report and deterministic monitoring |
| [Foundation](workstreams/foundation.md) | Prior handoff | Historical | Storage/recovery basis |

## Blockers

None. Use Docker context `lima-docker` explicitly on this machine; the shell's default endpoint targets a stopped VM. The existing Vite large-chunk advisory is non-blocking.

## Validation

Verified on 2026-09-20:

- Second domain: `make check` passes with 65 CPU tests; all five synthetic browser workflows pass and new screenshots were inspected. Header renaming preserves detections, normal batches and traffic stay unflagged, and the latency rule matches all 532 expected observations. Two live Norrin calls verify the rule proposal and a five-citation answer with an explicit causal limitation. See the [second-domain workstream](workstreams/second-domain.md).

- Confidence: `make types` and `make check` pass with 62 CPU tests. Six PostgreSQL tests include atomic confidence/checkpoint rollback and retry. Four synthetic browser workflows pass, including Low-to-High transition, review/reload, evidence links and legacy/OK rendering; desktop/mobile confidence screenshots inspected. No migration or added model call. See the [confidence workstream](workstreams/confidence.md).

- Landing-page/quickstart follow-up: tagline only in sidebar, sentence line breaks visually checked; one-command `make demo` startup succeeds. Re-ran `make check` and all three synthetic browser workflows successfully; localhost:8080 updated. See the [quickstart](../README.md#quickstart).

- `make check`: Ruff, mypy, TypeScript, ESLint, 40 CPU tests, documentation links and production build pass. Final frontend wheel/slider changes also pass lint/build.
- Five PostgreSQL tests pass: migrations/schema parity, immutable evidence, replay/claim concurrency, one pending question per decision, and first-Play races with configuration save/rule Apply.
- Three synthetic Docker Playwright workflows pass: Docs without an analysis; prepared-source setup/replay/review; uploaded CSV through exclusion, rule proposal/apply, replay, numbered evidence, two-turn conversation and reload. Desktop/mobile screenshots inspected.
- Historical browsing stays pinned as batches arrive; horizontal wheel/keyboard/slider work; Latest and page reload select the latest three batches. Trace tests cover >1,000 points, initial-only and partial final batches, matching forecast overlap and clipped flag intervals.
- Synthetic database/API/worker restart preserves the uploaded source, rule/configuration, checkpoint, trace, decisions and two-turn conversation exactly.
- Configured live Norrin provider succeeds for one synthetic threshold-rule proposal and a cited question/follow-up. Only synthetic aggregate evidence and opaque IDs were sent. This does not establish general model accuracy.
- Local deployment health passes for database/API/worker/web. All 12 pre-existing analyses and demo source choices are preserved; startup created no analysis. No database migration was needed for the new compatible JSON fields.
- Public OpenAPI and TypeScript contracts are regenerated. Final source formatting and diff whitespace checks pass.

## Next steps

1. For the second-domain presentation, upload `tests/fixtures/demo_web_service.csv` using the [walkthrough](../docs/SECOND_DOMAIN_DEMO.md); select 500 / 100 / 1 second. Otherwise preview confidence on synthetic QA at localhost:18080, or rebuild the operator deployment with `make demo DOCKER='docker --context lima-docker'`. Existing immutable decisions have no backfilled confidence. Default setup remains 500 / 100 / 10 seconds.
2. Review Understanding, save any channel exclusions, and optionally propose/review/apply a simple rule. Press Play to lock settings and begin monitoring.
3. Use Docs for metrics/criteria/evidence explanations and Decision log for continued conversations. Provider outages do not stop deterministic monitoring.

The synthetic QA stack remains isolated on port 18080 under `datalight-qa`, with the explicitly synthetic model fixture from `compose.qa.yaml`. Real demo files remain in ignored `runtime/demos/`; credentials remain in ignored `.env`. Uploads live in persistent named volumes, separate from the read-only demo mount. All screenshots use synthetic data.

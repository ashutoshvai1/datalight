# Current state

## Objective

Implement the approved simplification: explicit CSV setup → initial understanding → paused monitoring → one evidence-backed decision per batch → append-only review and questions. Implementation and local deployment verification are complete.

The product remains generic. [DATASET.md](../docs/DATASET.md) is offline testbed context, never runtime model knowledge. Prior foundation verification is preserved in [the historical handoff](foundation-verification.md).

## Constraints

- Raw observations remain in local CSV files; provider requests contain typed aggregates and explicit operator questions only.
- Metadata cannot influence live detectors or model interpretations. Original channel names are replaced with opaque IDs for questions.
- Quality warnings remain separate from process status. Per user choice, insufficient coverage displays OK with a prominent limitation warning.
- Initial references remain provisional and fixed; reviews never adapt thresholds.
- One active replay. Sequence boundaries and malformed/order-invalid observations cannot be bridged by temporal windows.
- Optional auto-pause and a last-value predictor comparison remain excluded pending approval.

## Active work

| Workstream | Owner | Status | Integration surface |
|---|---|---|---|
| [Simplification](workstreams/simplification.md) | Current agent | Complete; deployed on localhost:8080 | Backend, UI, migrations, local demos, documentation |
| [Foundation](workstreams/foundation.md) | Prior handoff | Retained as storage/recovery basis | Historical reports and reviews |

## Blockers

No implementation blockers. The shell's default Docker endpoint targets a stopped VM; the working app is on context `lima-docker`. Use the explicit context locally rather than changing global Docker settings.

## Validation

Verified on 2026-09-19:

- `make check`: Python lint, configured mypy with untyped-body checking, TypeScript, ESLint, 22 CPU tests, documentation links and production web build pass.
- Existing deployment migration preserves all 9 analyses, 12,347 evidence records, 502 findings and 6 reviews. Health and the three preloaded source choices are verified; startup creates no analysis.
- Two PostgreSQL tests pass: complete migration chain/schema parity, concurrent claims, unique decisions and immutable evidence.
- Synthetic Playwright workflow passes: setup defaults, paused report, trace, override/question persistence, reload, EOF, desktop/mobile layout, no page errors. Screenshots inspected; panel spacing corrected.
- Synthetic database/API/worker restart preserves checkpoint, temporal state, original decision, three reviews, 11 monitoring decisions and 12 contiguous batches.
- Live configured Norrin requests succeed for a complete four-channel synthetic report and an evidence-grounded review question. Final paired check took 14.38 seconds. This verifies the configured provider with synthetic aggregates, not all 52 real-data explanations.
- A live Q&A response originally invented the citation `decision`; responses now require a real stored decision-evidence ID. Rejected attempts stayed unavailable and the corrected live request passed. A regression test covers invented citations.
- Temporal tests cover forecast alignment/no future leakage, noise, steps, drift, holds, constants, range/missing values, malformed records, metadata isolation, boundaries, and identical triggered observations across batch sizes 7/37/100/173 with pause/restart.
- Original-data preparation evaluates all 20 faulty test scenarios, run 1. Three CSVs each contain healthy runs 1 and 2 followed by one faulty run, 2,880 rows total. Values and resets remain unchanged.
- Each real demo completes in 25 monitoring batches with zero process-warning batches during the two healthy runs. First detections occur at faulty-run samples 240 (abrupt), 166 (drift), and 225 (multichannel). Respectively 4, 29 and 45 channels trigger; the latter two also produce separate stuck-value warnings. These are selected demonstration results, not general accuracy estimates.

## Next steps

1. Open localhost:8080, choose one of the three CSVs and submit the setup. Defaults are 500 initial samples, 100 per batch and 10 seconds. Press Play on Monitoring after reviewing the report.
2. Recheck provider availability before a live demonstration; outages leave deterministic monitoring operational.
3. Consider only explicitly approved follow-up work from the [roadmap](../docs/roadmap.md).

Local data and provenance: `runtime/demos/`, `runtime/demo-selection.json`, `runtime/demo-validation.json`. Existing database backup: ignored `runtime/pre-v2-database.sql`. The ignored `.env` selects `DATA_DIR=./runtime/demos` and preserves backend provider credentials. The synthetic QA stack is isolated on port 18080 under project `datalight-qa`; real data is never used in browser captures.

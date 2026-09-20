# Demo improvements

## Objective

Implement the approved upload, monitoring setup, AI rule, conversation, visualization and Docs improvements while preserving fixed references, local observations and existing history.

## Ownership

- Integration / main worktree: App setup/upload, MonitoringSetup UI, generated contracts, end-to-end verification and durable docs.
- Backend / `codex/demo-backend`: uploads, reader mode, exclusion/rules, locking and trace API in an isolated worktree.
- Conversations / `codex/demo-conversation`: question history snapshots and review contract in an isolated worktree.
- UI / `codex/demo-ui`: charts, matrix, citations, review conversation and Docs in an isolated worktree.

## Contracts

Source upload returns SourceView; run creation and preview accept source_id alongside existing path selection. RunConfig gains reader_mode, excluded_channel_ids, rules and monitoring_locked. Monitoring configuration locks at first Play. Rule proposals are asynchronous and require explicit Apply. Trace supports a three-batch historical window. All new stored fields have historical defaults.

## Acceptance

Synthetic upload through report, saved exclusions, AI-proposed/applied rule and replay; multi-turn conversation and cited evidence; older chart browsing; clear matrix and Docs. Run make check, PostgreSQL checks and synthetic browser/restart checks. Preserve real data and existing analyses.

## Status

Implementation, integration and local deployment verification complete. The app at localhost:8080 is healthy; all 12 prior analyses and demo choices were preserved, and startup created no analysis.

## Validation

- `make check`: Python Ruff/mypy, TypeScript/ESLint, 40 CPU tests, docs links and production build pass. Existing Vite chunk-size advisory remains.
- Five PostgreSQL tests pass, including schema/migration parity, immutable evidence, concurrent question submission and first-Play races against configuration save/rule Apply.
- Three synthetic Docker browser workflows pass: Docs without an analysis, prepared-source replay/review, and upload through exclusions, applied rule, monitoring, cited two-turn conversation and reload. Desktop/mobile screenshots inspected.
- Browser regression covers the historical viewport staying pinned during polling, horizontal wheel navigation, Latest, and reload defaulting to the latest three batches. A controlled slider prevents browser scroll restoration from choosing an old batch; live charts render without reveal animation.
- Restarting synthetic database/API/worker preserves uploaded source, applied rule, configuration, checkpoint, trace, decisions and two-turn answers exactly.
- The configured live provider succeeds for a synthetic threshold-rule proposal plus an evidence-cited question and follow-up. No raw observations or original channel names were sent.
- Generated OpenAPI/browser contracts are updated. New analyses publish terminal unavailable results for cancelled pending questions/proposals so historical discussions can continue; late responses cannot replace them.

## Remaining boundaries

Uploads accept the existing UTF-8/header CSV format and bounded numeric discovery, with configurable 256 MiB default size and existing column/record limits. Rules support one scalar comparison, outside range or missing check; compound/temporal formulas remain unsupported. Model context includes ten prior completed turns, while older transcript pages remain available locally.

## Follow-up: landing page and quickstart

Owner: integration agent. Scope: App.tsx/sidebar styling, Makefile, README and developer guide. Keep the product tagline only in the sidebar with sentence line breaks. Add a single demo startup command with service-health waiting, prepared/synthetic selection, and a short setup-to-Play walkthrough. Acceptance: verified synthetic browser layout/workflow, make check, startup target, and refreshed local web deployment. Status: complete. `make check` passes (40 CPU tests); all three synthetic Docker browser workflows pass. The landing-page screenshot confirms the sidebar line breaks and single center heading. `make demo DOCKER='docker --context lima-docker'` successfully waits for health and updates localhost:8080. No persistence/schema changes; PostgreSQL tests were not repeated.

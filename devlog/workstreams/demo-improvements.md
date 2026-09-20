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

Implementation in progress; integration owner will record final validation here and reconcile current.md.

# Simplification

## Objective

Implement the approved setup → understanding → paused monitoring flow, deterministic prediction/change detection, three local demos, and batch review with evidence-grounded questions.

## Ownership

Owner: current agent. Paths: backend, web, demo preparation, Compose, tests and documentation. Existing local documentation and demo extractor changes are preserved and extended.

## Interfaces

Versioned analysis; selected local source; typed prediction/decision/trace/question contracts. Preserve historical evidence and append-only reviews. Optional automatic pause and persistence-predictor comparison are excluded.

## Evidence

Implementation and validation complete; see the results below.

## Next steps

Use the setup screen to select a demo, review its report, then press Play. Optional auto-pause and comparator remain excluded.

## Implemented behavior

Setup and optional bounds, selected directory-backed sources, paused initial report, causal regression metrics, cadence-aware holds, fixed-reference abrupt/drift/level rules, sample traces, one decision per batch, explicit coverage, append-only human assessment and typed Q&A are implemented. Three measured original-data demos are prepared locally. Existing documents and dataset context are retained; the prior current-state record is archived in [foundation verification](../foundation-verification.md).

## Validation results

`make check` passes with 22 CPU tests and configured mypy checking all function bodies. Two PostgreSQL tests pass. Synthetic browser workflow and actual service restart pass. Desktop/mobile captures were inspected and layout defects fixed. Live Norrin initial synthesis and question answering pass using synthetic aggregates. All three real demos complete without process warnings in healthy runs; detailed local-only measurements are in `runtime/demo-validation.json`.

The local `.env` now selects the demo directory; credentials are preserved. Database backup and before/after counts are ignored runtime artifacts. The Docker context needed an explicit `lima-docker` override because the inherited default points to a stopped VM.

The existing local deployment is updated on localhost:8080. Migration preserved all 9 runs, 12,347 evidence records, 502 findings and 6 reviews; old reviews have a read-only history view. The source picker exposes all three generated CSVs.

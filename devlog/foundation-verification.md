# Current state

## Objective

Foundation implemented and verified: mounted CSV → initial report → batch monitoring → evidence → persistent human review. Preserve the [roadmap](../docs/roadmap.md); Phase 2 is not selected.

The product is generic CSV reliability and monitoring. [DATASET.md](../docs/DATASET.md) describes the primary testbed/demo source and belongs to offline development context, not runtime model knowledge or universal application rules. See [D009](decisions.md).

## Constraints

- Raw data stays local; model egress accepts only typed aggregates.
- Evaluation labels/metadata cannot influence live detection or interpretation.
- Dataset-specific facts stay in source adapters/configuration or offline tools; do not turn the testbed reference into generic thresholds, schema assumptions, or prompt context.
- Reference is provisional; sequence boundaries are explicit; quality and deviations are distinct.
- Reviews append history and do not adapt thresholds or baselines.
- One local deployment and one active replay. Phase 2 remains TBD.

## Active work

| Workstream | Owner | Status | Integration surface |
|---|---|---|---|
| [Foundation](workstreams/foundation.md) | Current agent; handoff ready | Complete; two-run demo verified | Offline extraction, local Compose mount, docs |

## Blockers

The two-run local demo works with successful initial and selected-deviation model interpretations. Earlier original-data analysis attempts retain their historical timeout records. Full-file throughput/storage measurement and second-provider verification remain judge-readiness work, not completed claims.

## Validation

Verified locally on 2026-09-19:

- 15 CPU/backend tests: metadata isolation, sequence/hold semantics, quality/deviation separation, source replacement, lease recovery, atomic rollback, reviews, provider egress/failure handling, and selected-finding limits.
- 2 PostgreSQL tests: clean migrations/schema drift, concurrent bootstrap/claims, append-only evidence.
- Python lint/types, frontend TypeScript/ESLint/production build, generated API contracts, and devlog links/structure pass.
- Docker starts all four runtime services after migrations and automatically produces a synthetic report.
- Browser workflow passes: evidence, pause/resume, fast-forward/EOF, override/reload, desktop/mobile layout, no JavaScript errors.
- Actual database/API/worker restart preserves checkpoint, acceptance/question/override records, and original conclusion; replay completes 1,600 rows in 12 unique contiguous batches.
- Read-only Docker mount smoke on the 6,011,495,524-byte CSV: 20,500 observations, 52 channels, 56.5 MiB peak RSS, 3.08 seconds. Partial scan only; no real-derived artifacts committed.
- Norrin live synthetic-summary calls succeed for both initial hypotheses and selected-deviation interpretation. Exact model discovered via authenticated `/v1/models`; invalid earlier attempts remain visible in the local audit history.

Previous original-data follow-up on 2026-09-19:

- Mounted an ignored, byte-preserving contiguous slice of original data rows 249,501–255,000: 5,500 observations, 52 channels, a 500-row reference, and 100-row monitoring batches. This is a selected demo slice, not a replay of all preceding source rows.
- Replay completes in 51 unique contiguous batches across 11 sequences without crossing a sequence boundary. Quality checks pass while evidence-linked reference deviations are recorded separately.
- Browser evidence/trends, pause/reload, resume, fast-forward, EOF, and worker restart recovery pass. A clearly labeled QA question survives reload; the original conclusion remains intact. Browser console reports no errors.
- Mutating all four evaluation metadata fields leaves profiles, quality checks, correlations, and detector results identical throughout the slice.
- Full-slice deterministic smoke: 48.9 MiB peak host RSS, 0.73 seconds. This excludes database/model work and is not a full 6 GB benchmark.
- Both initial and selected-deviation Mistral calls time out with 30-second and 120-second settings. Authenticated model listing also times out after 20 seconds. Earlier successful synthetic calls do not establish current availability. Typed outgoing summaries exclude raw rows, original column names, evaluation metadata, and credentials; degraded state and attempts remain visible.

Latest endpoint retest, 2026-09-19 at approximately 16:36 Helsinki time:

- Authenticated model discovery returns HTTP 200 and advertises the configured model. A completion using the existing 52-channel typed summary succeeds in 20.88 seconds with eight schema- and evidence-validated hypotheses.
- The local `.env` had changed to the base `/v1` URL, which returns HTTP 404 for a completion POST. Corrected only `LLM_ENDPOINT` to the full `/v1/chat/completions` route. The running worker already used the full route; this local configuration issue does not explain the earlier worker timeouts.
- Both manual retest attempts are recorded in the current run's model-call audit with purpose `user_requested_endpoint_retest`. Replay, reviews, and published conclusions were preserved; use New analysis to refresh the report's model interpretation.

Two-run demo selection on 2026-09-19:

- The complete export contains 21,000 simulation runs: training runs have 500 samples; test runs have 960. Selected `source=test`, `simulationRun=1` under `faultNumber=0` and `faultNumber=1`, normal first. Root `demo.csv` holds 1,920 rows with all original fields preserved.
- The paired sensor observations are identical through sample 160; the faulted scenario first diverges at sample 161. This is observed divergence, not an onset inferred from the run-wide `fault_status` label.
- With the default 500-row reference and 100-row batches, deterministic validation finds no normal-run warnings and 33 fault-run warnings. The first warnings cover fault-run samples 201–300 (demo rows 1,161–1,260). All implemented quality checks pass; the sample reset at demo row 961 is preserved.
- `scripts/prepare_demo.py` reproduces the selection from the original CSV. Real observations and provenance remain ignored (`demo.csv`, `runtime/demo-selection.json`); the tracked synthetic fixture is unchanged. Selection uses evaluation metadata offline; application analysis does not.
- `make check` passes after adding the extractor and README instructions. The live app completes all 1,920 rows in 16 unique contiguous batches across two sequences, reproduces the deterministic warning counts, and succeeds on both Mistral calls. The browser displays the 52-channel report with model hypotheses and no console errors.

## Next steps

1. Review the two-run demo at localhost:8080 and the [development guide](../docs/development.md). New analysis replays the mounted normal/faulted pair; use the default 500-row reference. Existing runs and reviews remain available.
2. Recheck Norrin availability again before judging.
3. Before judging, measure a full source replay's runtime and database growth; use fast-forward to reach row 250,001 without skipping batches.
4. Select Phase 2 explicitly from the [coverage gaps](../docs/roadmap.md).

The local ignored `.env` contains the provisioned provider settings, `CSV_PATH=./demo.csv`, and `LLM_TIMEOUT=120`; no key is in repository files. Compose mounts that two-run original-data demo read-only. Provenance and validation output stay in ignored `runtime/`; application history remains in PostgreSQL. GitHub Actions is configured for pushes and pull requests; consult its run status separately from the local verification recorded above.

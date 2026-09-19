# Phased roadmap and challenge coverage

## Phase 1 — Foundation

Deliver the mounted-CSV report → quality checks → basic deviation warning → evidence inspection → persisted human-review workflow. Include container startup, recoverable jobs, provider boundaries, synthetic tests, and concise collaboration context.

Acceptance gates: Docker startup on the synthetic fixture; bounded-memory real-file smoke; successful pause/resume/EOF and crash recovery; distinct quality/deviation findings; durable human review; isolated metadata; fake-provider egress/failure tests; PostgreSQL migration/concurrency checks; browser workflow; generated-contract and devlog validation. Verification status belongs in [current state](../devlog/current.md).

## Phase 2 — TBD

The next phase has not been selected. Preserve these gaps without inventing a schedule or creating workstream stubs:

| Challenge requirement | Foundation status | Remaining work |
|---|---|---|
| Automatic initial understanding | Basic implementation | Richer interpretation and coverage assessment |
| Channel statistics and correlations | Implemented | Lagged cross-correlation and clustering |
| Functional roles and measured/actuator distinction | Tentative model hypotheses only | Better structural evidence and review |
| Quality on each incoming batch | Missingness, numeric validity, schema, sequence | Domain ranges, units, validated frozen-sensor rules |
| Natural-language operating rules | Not implemented | Approved declarative rules and traceable execution |
| Abrupt anomalies and gradual drift | Basic batch-median reference deviation | Gradual and multivariate detectors; evaluation |
| Fault type and ranked contributors | Not implemented | Evidence-backed diagnosis; no causal overclaiming |
| Accept/question/override | Implemented on findings, including reference/hypotheses | Broader operator feedback workflows |
| Complete decision/model-call log | Implemented locally | Export/retention policy and usability improvements |
| Full dataset handling | Incremental reader and recoverable replay | Full-pass timing and storage measurement |
| Local/EU model swapping | Configurable adapter; live Norrin calls verified | Verify a second provider |
| Cross-domain adaptability | Architecture separates domain parsing from core | Demonstrate a business dataset or formal walkthrough |
| Browser upload | Deferred by agreed scope | Bounded local upload/source lifecycle |

Human overrides remain review records. Any proposal to automatically update baselines, rules, or thresholds requires a separate decision with validation and audit implications.

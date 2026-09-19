# Roadmap and challenge coverage

Datalight is a generic local CSV understanding and monitoring app. The [primary testbed](DATASET.md) informs offline demos, not implicit product rules. Selected demonstrations do not establish general fault-detection accuracy.

## Implemented foundation and approved simplification

Explicit source setup; initial quality/statistical/prediction report; complete channel synthesis in bounded LLM groups; paused batch replay; sample-level charts; abrupt change, persistent drift and level-deviation rules; evidence-backed batch decisions; separate quality warnings; append-only accept/question/override history and asynchronous answers; recovery and source-identity checks. Three local original-data demos use two healthy runs followed by a faulty run.

Validation and current limitations are recorded in [current state](../devlog/current.md). The prior foundation remains the storage and recovery basis; the approved simplification supersedes its automatic startup, one-second pacing, partial role hypotheses and per-channel finding UI.

## Suggestions awaiting approval

- Optional automatic pause at the first suspected fault.
- Compare regression MAE with a last-value prediction baseline.

Neither suggestion is implemented.

## Future work, not approved

- Natural-language operating rules, unit validation and wall-clock timeliness.
- Validated physical fault diagnosis and causal explanations.
- Lagged relationships, multivariate detectors and domain-specific evaluation.
- Additional source adapters and a second-domain demonstration. The current reader recognizes the primary testbed's metadata fields and sample-reset convention.
- Full-file replay/storage measurement, retention policy, and a second live provider.
- Browser uploads, remote streaming, authentication and multi-tenancy.
- Baseline or threshold adaptation from human review. Overrides currently change only the recorded human assessment.

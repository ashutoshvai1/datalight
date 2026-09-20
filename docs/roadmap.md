# Roadmap and challenge coverage

Datalight is a generic local CSV understanding and monitoring app. The [primary testbed](DATASET.md) informs offline demos, not implicit product rules. Selected demonstrations do not establish general fault-detection accuracy.

## Implemented foundation and approved simplification

Explicit source setup; initial quality/statistical/prediction report; complete channel synthesis in bounded LLM groups; paused batch replay; sample-level charts; abrupt change, persistent drift and level-deviation rules; evidence-backed batch decisions; separate quality warnings; append-only accept/question/override history and asynchronous answers; recovery and source-identity checks. Three local original-data demos use two healthy runs followed by a faulty run.

The approved demo improvements add local browser uploads, pre-Play channel selection and reviewed AI rule proposals, multi-turn questions, three-batch chart history, an expanded correlation matrix and in-app Docs.

Validation and current limitations are recorded in [current state](../devlog/current.md). The prior foundation remains the storage and recovery basis; the approved simplification supersedes its automatic startup, one-second pacing, partial role hypotheses and per-channel finding UI.

The [synthetic web-service demonstration](SECOND_DOMAIN_DEMO.md) adds a reproducible second-domain pass through the existing upload, reference learning, drift detection, reviewed-rule and evidence-citing question paths. Header-renaming checks and an architectural explanation demonstrate portability; causal diagnosis and general accuracy remain unproven.

## Suggestions awaiting approval

- Optional automatic pause at the first suspected fault.
- Compare regression MAE with a last-value prediction baseline.

Neither suggestion is implemented.

## Future work, not approved

- Richer compound/temporal operating rules, unit validation and wall-clock timeliness.
- Validated physical fault diagnosis and causal explanations.
- Lagged relationships, multivariate detectors and domain-specific evaluation.
- Additional source adapters. Mounted sources retain the sample-reset convention; uploaded CSVs use file row order. Recognized evaluation metadata remains excluded.
- Full-file replay/storage measurement, retention policy, and a second live provider.
- Remote streaming, authentication and multi-tenancy.
- Baseline or threshold adaptation from human review. Overrides currently change only the recorded human assessment.

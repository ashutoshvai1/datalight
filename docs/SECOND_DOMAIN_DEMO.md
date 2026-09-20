# Second domain: synthetic web-service telemetry

This small demo exercises the same CSV upload, reference learning, drift detection, reviewed rules and evidence-backed discussion as the industrial demo. No production algorithm, prompt, API or UI branches on this file or its domain. It is a reproducible portability demonstration, not an accuracy benchmark or a validated causal diagnosis.

## Data and reproduction

The included [demo_web_service.csv](../tests/fixtures/demo_web_service.csv) contains 1,500 ordered observations and four numeric columns. It is entirely synthetic and safe to commit and use for screenshots. Regenerate it from the repository root with Python 3.12 (standard library only):

```bash
python3 scripts/generate_web_service_demo.py
# Optional alternate destination:
python3 scripts/generate_web_service_demo.py --output /tmp/demo_web_service.csv
```

The [generator](../scripts/generate_web_service_demo.py) uses `random.Random(2026)`, five decimal places and LF line endings. Its Gaussian noise standard deviations are 20 requests/second, 1 CPU percentage point, 4 ms and 0.03 error percentage points. The first 700 rows are stable; additive ramps progress by 1/300 of the change per observation, then plateau:

| Column | Initial center | Changed center | Ramp rows, inclusive |
|---|---:|---:|---|
| `requests_per_second` | 1,000 | 1,000 | None; stable comparison channel |
| `cpu_percent` | 35 | 80 | 701–1000 |
| `p95_latency_ms` | 120 | 620 | 801–1100 |
| `error_rate_percent` | 0.2 | 3.2 | 901–1200 |

These are generation assumptions, not configured physical limits or detector thresholds. CPU, latency and errors are scripted to rise at different points; the generator does not model a proven causal mechanism. No timestamp, sample index, incident label or scenario metadata appears in the CSV. There is no assumed sampling interval: model slopes remain units per observation and playback seconds only control presentation speed.

## Presentation walkthrough

1. Start the app using the [README quickstart](../README.md#quickstart). Choose **New analysis → Upload CSV** and select `tests/fixtures/demo_web_service.csv`. This also works when the existing Tennessee Eastman demos are mounted; upload storage is separate.
2. Keep **500 initial samples** and **100 samples per batch**; set **Seconds between batches** to **1**. Build the understanding report. Inspect all four channels, initial statistics, forecast errors and learned references. The initial reference is provisional, not verified healthy operation.
3. For the clearest built-in detection demonstration, use no custom rule. Press **Play**. The two batches covering rows 501–700 should be OK. Subsequent batches show changes in CPU, latency and errors, while traffic remains stable. Inspect linked evidence and use chart history to find the onset.
4. To demonstrate natural-language rule extraction, start a fresh analysis with the same file and settings. Before Play, request **“Flag a fault if p95_latency_ms exceeds 400”**. Review that the proposal names the latency channel, uses **> 400**, and has the **Fault Suspected** effect, then click **Apply rule**. The threshold is an explicit operator policy, not a rule inferred from web-service expertise. Play locks the monitoring setup; built-in rules still run independently.
5. On a flagged decision, ask **“Which measurements support the flagged decision, and do they establish a cause?”** Inspect the answer's evidence links. The answer should discuss supplied measurements and uncertainty, not assert a physical cause. Operator questions can also name a channel; the backend substitutes its opaque ID before model egress.

Rule proposals and discussion require the [optional model configuration](demo-setup.md#enable-model-explanations-questions-and-rules). Without it, the report and deterministic replay still work. The isolated QA server produces explicitly synthetic test responses; those verify integration, not live model reasoning. Do not use its canned answers as model-quality evidence.

## How this addresses the challenge

| Requirement | Evidence supplied by this demo | Limit of the claim |
|---|---|---|
| Rule extraction is generic | The initial CSV window supplies fresh reference distributions; an optional sanitized operator request produces a reviewed, typed latency rule. | Reference learning and translating an operator policy are different capabilities; neither infers physical safety limits. |
| Drift detection is generic | A full run without custom rules detects drift on three changing channels. Renaming every header leaves trigger metrics and intervals unchanged. | One scripted numeric domain does not establish general detection accuracy. |
| Root-cause logic is not dataset-specific | The existing question path receives aggregate decision evidence, thresholds and opaque IDs and returns evidence-citing discussion without a fault catalogue. | This supports investigation. The current prompts prohibit inferring causes, so it is not causal root-cause identification. |

Shared execution path:

```text
CSV upload → numeric column inference → initial reference learning
           → fixed rolling-window evaluation → persisted decision/evidence
           → aggregate-only, evidence-citing explanation on request
```

`ingestion.py` reads observations, `analysis.py` infers numeric channels, and `temporal.py` learns and evaluates the same fixed-reference rules for either domain. `rules.py` validates reviewed proposals and evaluates them deterministically. `service.py` persists results and constructs typed summaries; `providers.py` substitutes opaque IDs, limits egress and validates evidence citations. The CSV generator and this document are offline artifacts, never runtime or model context. See [architecture](architecture.md) for the exact algorithms and boundaries.

Existing portability limits remain: UTF-8 numeric CSVs, numeric inference from the initial window, file row order for uploads, recognized evaluation/sample columns excluded from monitoring, and sample-reset conventions for legacy mounted sources. This demo has one continuous sequence. Arbitrary uploaded run boundaries, timestamp interpretation, units, multivariate causal models and physical-role inference are not added.

## Verification

The [backend acceptance tests](../backend/tests/test_second_domain.py) exercise the public upload/run APIs and actual replay service with a temporary database. They verify byte-for-byte regeneration, all 1,500 rows, healthy pre-change monitoring, drift on the three changing channels, stable traffic, unchanged initial reports, renamed-header equivalence, exact custom-rule intervals/counts, and private model payloads with resolvable citations.

The [browser workflow](../apps/web/e2e/second-domain.spec.ts) uploads the committed CSV, reviews/applies the latency rule, replays the data, asks a question, opens cited evidence and reloads the persisted discussion. Use the isolated synthetic stack described in [development](development.md#demo-improvement-verification). Current executed checks and any live-provider result are recorded in the [workstream](../devlog/workstreams/second-domain.md).

# Datalight

**Illuminate your data. Talk to it. Evidence centric analysis. Your data stays private.**

Datalight is a local CSV data-understanding and monitoring application for the [Norrin challenge](Norrin_Hackathon_Challenge_Sep_2026.pdf). Choose a file, build an initial understanding report, then press Play to replay the remaining observations in batches. Computed evidence and human reviews remain traceable.

The [Tennessee Eastman export](docs/DATASET.md) is the primary testbed. Its labels, channel identities, ranges and fault catalogue are offline context, never detector inputs or model knowledge. The product's source-convention portability limits remain explicit in the [roadmap](docs/roadmap.md).

## Run it

Requirements: Docker with Compose, approximately 4 GB available memory, and readable UTF-8 CSVs. A small synthetic fixture is included.

```bash
# Synthetic deployment; no download or model credentials required.
DATA_DIR=./tests/fixtures docker compose up --build -d
```

Open **http://localhost:8080**. Nothing is analyzed automatically. Select a CSV from the mounted directory or upload a CSV, then choose initial samples, batch size, and seconds between batches. Defaults are **500 / 100 / 10 seconds**. Optional minimum/maximum channel limits are under a collapsed setup section. Custom paths must remain inside the data directory. Uploads are stored in a separate persistent local volume; the default upload limit is 256 MiB (`UPLOAD_MAX_MIB`).

The understanding report opens after submission. Monitoring remains paused until **Play**. Pause/resume preserves the checkpoint; EOF completes playback. Before first Play, Understanding lets you exclude numeric channels and propose additional monitoring rules. The UI contains Understanding, Monitoring, Decision log, and Docs. Docs is available before starting an analysis. Historical reports and reviews remain accessible. Old foundation analyses are readable; start a new analysis to use the new detectors.

The directory is mounted read-only. Files can be selected without restarting Docker. Source replacement requires a new analysis. `docker compose down` preserves database history.

## Three local demos

```bash
uv run --project backend python scripts/prepare_demo.py te_process.csv
DATA_DIR=./runtime/demos docker compose up --build -d
```

The extractor streams the original export, evaluates test run 1 of all 20 faulty scenarios, and selects distinct examples of abrupt change, sustained drift, and broad multichannel change. Ties use the scenario number. Each output contains healthy test runs 1 and 2 followed by one complete faulty test run: **2,880 rows**, with unchanged observations, headers, and sample resets. With a 500-row reference, healthy monitoring precedes the faulted scenario.

Generated files are `runtime/demos/demo_abrupt.csv`, `demo_drift.csv`, and `demo_multichannel.csv`. Selection scores and source provenance remain in ignored `runtime/demo-selection.json`. Files, real-derived metrics, and credentials are excluded from Git and Docker images. Only synthetic data is used for committed fixtures and browser screenshots. Selection metadata never guides live monitoring.

## Understanding and monitoring

- **Quality:** completeness and invalid counts, user-configured bounds, and possible frozen behavior. Unspecified bounds are “Not configured.” Stuck warnings require a hold of at least 20 samples or five times the initial typical completed hold, whichever is larger. A constant initial channel is explicitly inconclusive.
- **Statistics:** mean, standard deviation, observed minimum/maximum, strongest Pearson relationships with paired counts, and an expandable full correlation matrix.
- **Prediction:** per-channel least-squares trend lines on 10 preceding samples forecast the next 5. The report gives chronologically evaluated MAE, signed mean slope and slope variability. Slopes are units per sample, never units per playback second.
- **Change detection:** adjacent 10-sample mean differences, persistent 50-sample slopes, and fixed-reference level deviations. Temporal rules and reference scales are fixed from the initial window. Windows never bridge invalid values, configured-range violations, ordering gaps or independent runs.
- **Monitoring:** the latest three batches of sample-level values and five-step-ahead forecasts, with flagged intervals. Scroll horizontally to retrieve older batches; Latest returns to live playback. Each batch has one **OK / Fault Suspected** decision and a separate quality warning. OK means no process rule triggered; insufficient coverage appears prominently beside it.
- **Review:** accept, question or override each batch decision. Overrides specify a status and reason; the latest human assessment is shown beside the preserved automated conclusion. Questions receive asynchronous LLM answers when configured, with follow-up conversation context. Reviews require no name field. Reviews never recalibrate thresholds.

Uploaded files use file row order; prepared demos retain their sample-reset boundaries. Recognized evaluation metadata and sample columns are unavailable as detector inputs. Numeric columns are inferred from the initial window; text columns are not monitored. A short file may be fully consumed by the initial report.

Natural-language rules use the configured model to propose one threshold, outside-range, or missing-value check. Review the exact channel, condition and fault/quality effect before Apply. Only applied rules run, using deterministic checks with linked evidence. Channel exclusions and rules lock at first Play. Rules do not change the initial reference or existing quality-limit masking.

The reference is provisional. A statistical change is not a fault diagnosis, and a repeated value is not by itself a proven sensor failure. See [architecture](docs/architecture.md) for exact rules, persistence, and model boundaries.

## Optional LLM synthesis and questions

```bash
cp .env.example .env
# Set LLM_ENABLED=true and the organizer-provided LLM_API_KEY in .env.
```

Provider settings remain backend-only. The default Norrin endpoint and exact configured model ID are in `.env.example`; compatible providers can be configured through `LLM_ENDPOINT`, `LLM_MODEL`, and `LLM_API_KEY`. A host-local compatible endpoint can use `host.docker.internal` where supported.

Initial explanations cover every channel in groups of eight. The LLM receives opaque channel IDs and typed computed summaries. Explicit operator questions and up to ten previous completed exchanges from the same decision are sent with decision evidence; original channel names are replaced by IDs, and pasted numerical sequences/evaluation metadata are rejected. Do not put raw data or secrets in questions. Rule proposals send only the sanitized request and eligible opaque channel IDs. The full conversation is stored locally, although model context is limited to ten preceding completed exchanges. Raw observations are never attached to provider requests.

Coverage and evidence references are validated. Failed groups remain visibly unavailable or partial. Model outages do not stop deterministic monitoring or reviews. Fault explanations are generated immediately from metrics; there is no automatic LLM call per monitoring batch. Detailed model attempts remain available through the API, outside the main UI.

## Development and validation

Python 3.12, uv, Node 24, pnpm 11.19.0. Locked dependencies are committed.

```bash
make install
make db
make migrate
make api
make worker
make web
make check
make test-postgres
make test-browser          # requires a running synthetic deployment
make smoke-restart         # synthetic deployment only
make types                 # after public contract changes
make smoke-data CSV_PATH=./te_process.csv
```

See the [development guide](docs/development.md) for environment and isolated test setup, [current state](devlog/current.md) for verified results, [decisions](devlog/decisions.md) for durable choices, and [roadmap](docs/roadmap.md) for unapproved future work.

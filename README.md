# Datalight

**Illuminate your data. Talk to it. Evidence centric analysis. Your data stays private.**

Datalight is a local CSV data-understanding and monitoring application for the [Norrin challenge](Norrin_Hackathon_Challenge_Sep_2026.pdf). Choose a file, build an initial understanding report, then press Play to replay the remaining observations in batches. Computed evidence and human reviews remain traceable.

The [Tennessee Eastman export](docs/DATASET.md) is the primary testbed. Its labels, channel identities, ranges and fault catalogue are offline context, never detector inputs or model knowledge. The product's source-convention portability limits remain explicit in the [roadmap](docs/roadmap.md).

## Quickstart

You need Docker running with Compose, `make`, and about 4 GB of available memory. No Python, Node, data download, or model key is needed to try the included demo.

**1. Start the app.** In the `datalight` repository folder, run:

```bash
make demo
```

The first build takes a few minutes. Wait for **Ready: http://localhost:8080**. This command uses prepared files in `runtime/demos` when available, or the included synthetic `demo.csv` otherwise. It preserves existing analyses, uploads, and model settings in `.env`.

**2. Load a demo.** Open [Datalight](http://localhost:8080), click **New analysis**, and select **demo abrupt** (or **demo** for the included synthetic file). Keep the defaults—**500** initial samples, **100** samples per batch, **10** seconds between batches—and click **Build understanding report**. For a faster presentation, change the interval to **1** second before building the report.

**3. Review and play.** Read Understanding. Optionally exclude channels and click **Save monitoring setup**. Open **Monitoring** and press **Play**. Inspect a flagged batch's evidence, then use **Decision log** to accept, question, or override it. **Docs** explains the metrics. Questions and natural-language rules need the [optional model setup](#optional-llm-synthesis-and-questions).

To use your own file, choose **Upload CSV** instead of a demo. Use a UTF-8 CSV with a header row and numeric data (up to 256 MiB by default). Playback starts after the initial window; a shorter file can produce a report with no rows left to monitor.

Run `make demo` again to restart or rebuild. Use `docker compose stop` to stop the app while keeping history. To choose another data directory, run `make demo DEMO_DIR=/path/to/csv-folder`. Mounted files remain read-only; uploads use a separate persistent local volume.

If Docker cannot connect on this development Mac, use `make demo DOCKER='docker --context lima-docker'`. If port 8080 is busy, use `make demo WEB_PORT=8081`. For startup errors, run `docker compose logs --tail=50 api worker` (use the same Docker context as startup).

## Prepare the three presentation demos (optional)

If you have the Tennessee Eastman export and `uv`, prepare the files once, then follow the quickstart above:

```bash
uv run --project backend python scripts/prepare_demo.py te_process.csv
make demo
```

The extractor streams the original export, evaluates test run 1 of all 20 faulty scenarios, and selects distinct examples of abrupt change, sustained drift, and broad multichannel change. Ties use the scenario number. Each output contains healthy test runs 1 and 2 followed by one complete faulty test run: **2,880 rows**, with unchanged observations, headers, and sample resets. With a 500-row reference, healthy monitoring precedes the faulted scenario.

Generated files are `runtime/demos/demo_abrupt.csv`, `demo_drift.csv`, and `demo_multichannel.csv`. Selection scores and source provenance remain in ignored `runtime/demo-selection.json`. Files, real-derived metrics, and credentials are excluded from Git and Docker images. Only synthetic data is used for committed fixtures and browser screenshots. Selection metadata never guides live monitoring.

## Try a second domain

Upload the included [synthetic web-service CSV](tests/fixtures/demo_web_service.csv) through **New analysis → Upload CSV**. Use 500 initial samples, 100 per batch and a 1-second interval. Traffic stays stable while CPU, latency and errors rise; the same detector learns references and finds changes without domain-specific code. The [walkthrough](docs/SECOND_DOMAIN_DEMO.md) covers optional reviewed rules, evidence-citing questions, architectural portability and the limits of causal interpretation. No download or model key is needed for deterministic monitoring.

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
cp -n .env.example .env
# Edit .env: set LLM_ENABLED=true and LLM_API_KEY to your provider key.
make demo
```

The copy command preserves an existing `.env`. Restarting with `make demo` loads the settings; start a new analysis for model-generated initial explanations.

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

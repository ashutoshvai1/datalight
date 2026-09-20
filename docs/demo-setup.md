# Optional demo setup

The [README quickstart](../README.md#quickstart) is enough to run the included synthetic demo. Use this guide only to enable a model, prepare the Tennessee Eastman presentation files, or customize startup. Run these commands from the `datalight` repository folder.

## Enable model explanations, questions and rules

```bash
cp -n .env.example .env
# Edit .env: set LLM_ENABLED=true and LLM_API_KEY to your provider key.
```

The copy command preserves an existing `.env`. Run the [quickstart](../README.md#quickstart) startup command after saving the settings; start a new analysis for model-generated initial explanations.

Provider settings remain backend-only. The default Norrin endpoint and exact configured model ID are in [`.env.example`](../.env.example); compatible providers can be configured through `LLM_ENDPOINT`, `LLM_MODEL`, and `LLM_API_KEY`. A host-local compatible endpoint can use `host.docker.internal` where supported.

Initial explanations cover every channel in groups of eight. The LLM receives opaque channel IDs and typed computed summaries. Explicit operator questions and up to ten previous completed exchanges from the same decision are sent with decision evidence; original channel names are replaced by IDs, and pasted numerical sequences/evaluation metadata are rejected. Do not put raw data or secrets in questions. Rule proposals send only the sanitized request and eligible opaque channel IDs. The full conversation is stored locally, although model context is limited to ten preceding completed exchanges. Raw observations are never attached to provider requests.

Coverage and evidence references are validated. Failed groups remain visibly unavailable or partial. Model outages do not stop deterministic monitoring or reviews. Fault explanations are generated immediately from metrics; there is no automatic LLM call per monitoring batch. Detailed model attempts remain available through the API, outside the main UI.

## Prepare the three presentation demos

If you have the Tennessee Eastman export and `uv`, prepare the files once before starting the app:

```bash
uv run --project backend python scripts/prepare_demo.py te_process.csv
```

Then follow the [quickstart](../README.md#quickstart), or rerun its startup command if the app is already running.

The extractor streams the original export, evaluates test run 1 of all 20 faulty scenarios, and selects distinct examples of abrupt change, sustained drift, and broad multichannel change. Ties use the scenario number. Each output contains healthy test runs 1 and 2 followed by one complete faulty test run: **2,880 rows**, with unchanged observations, headers, and sample resets. With a 500-row reference, healthy monitoring precedes the faulted scenario.

Generated files are `runtime/demos/demo_abrupt.csv`, `demo_drift.csv`, and `demo_multichannel.csv`. Selection scores and source provenance remain in ignored `runtime/demo-selection.json`. Files, real-derived metrics, and credentials are excluded from Git and Docker images. Only synthetic data is used for committed fixtures and browser screenshots. Selection metadata never guides live monitoring.

## Restart, stop and troubleshoot

Rerun `make demo` to rebuild or restart the stack. Existing analyses, uploads and `.env` settings are preserved. Stop it with `docker compose stop`; the database and upload volumes remain intact.

| Need | Command |
|---|---|
| Use another CSV directory | `make demo DEMO_DIR=/path/to/csv-folder` |
| Force the included synthetic demos | `make demo DEMO_DIR=./tests/fixtures` |
| Use another port | `make demo WEB_PORT=8081` (then open http://localhost:8081) |
| Use this development Mac's running Docker context | `make demo DOCKER='docker --context lima-docker'` |
| Inspect startup errors | `docker compose logs --tail=50 api worker` |

Use the same Docker context for startup, logs and stop commands; for example, `docker --context lima-docker compose stop`. The Lima context is specific to this development machine, not a prerequisite for other machines. Mounted CSVs remain read-only; uploads use a separate persistent local volume.

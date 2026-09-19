# Datalight

**Understand the data. Check its quality. Monitor changes. Keep human judgment in the loop.**

Datalight is a local decision-support application for the [Norrin challenge](Norrin_Hackathon_Challenge_Sep_2026.pdf). It reads an initial window from a mounted CSV, builds an evidence-backed understanding report, then replays subsequent batches as a stream. Findings and human reviews remain traceable to their original evidence.

## Run it

Requirements: Docker with Compose, about 4 GB available memory, and a readable UTF-8 CSV. Images and dependencies download on the first build. No GPU is needed.

```bash
# From this repository. A synthetic demo is included; no data download required.
CSV_PATH=./tests/fixtures/demo.csv docker compose up --build

# Or use your own mounted dataset.
CSV_PATH=/absolute/path/te_process.csv docker compose up --build
```

Open **http://localhost:8080**. Initial analysis starts automatically; reopening the browser does not duplicate it. The input file is mounted read-only and excluded from Docker images. The database persists across restarts. `docker compose down` preserves its volume.

For the real dataset, select **Fast-forward** to reach later observations: its first nonzero evaluation label is at row 250,001. Fast-forward processes every batch; labels never guide replay or live detection.

### Optional model interpretation

Statistical analysis works without model access. To enable Norrin interpretation:

```bash
cp .env.example .env
# Edit .env: set LLM_ENABLED=true and LLM_API_KEY to your organizer-provided key.
# Then run the same Docker command above.
```

The default endpoint is the supplied Norrin chat-completions endpoint. `LLM_MODEL=mistralai/Mistral-Large-3-675B-Instruct-2512-NVFP4` is the exact identifier returned by its model-list route. Change `LLM_ENDPOINT`, `LLM_MODEL`, and `LLM_API_KEY` to switch compatible providers. A local compatible endpoint can omit the key. Docker containers reach a host-local server via `host.docker.internal`, where supported by the Docker runtime.

**The CSV path is the only per-launch input after model credentials are provisioned once.** Never put secrets in `VITE_` variables. Only typed aggregate summaries reach the model; inspect every request and response in the decision log. Model outages leave statistical monitoring active and explicitly mark interpretation unavailable.

## Foundation capabilities

- **Understanding:** column classification, numeric profiles, completeness, robust statistics, update cadence, lag-1 behavior, and pairwise correlation with sample counts. Optional role hypotheses cite computed evidence. The first detected deviation per run can receive a separate model interpretation.
- **Monitoring:** 500 initial observations, then 100-row batches at one-second intervals; pause/resume, fast-forward, restart with another window size, and previous-run access.
- **Quality:** missing/non-finite/unparseable values, malformed record widths, sample gaps, duplicates, and ordering failures.
- **Deviation:** a fixed-reference batch-median warning, using `abs(batch median − reference median) / (1.4826 × reference MAD) > 6`. Unsupported or unreliable channels are explicitly listed.
- **Review:** accept, question, or override a conclusion with a self-declared operator name. Reviews preserve the original conclusion and never change future thresholds automatically.
- **Recovery:** record-aligned checkpoints, atomic batch commits, leased jobs, source replacement detection, and append-only evidence/review tables.

The initial reference is **provisional**, not certified healthy operation. Quality failures and process deviations are separate. Sequence boundaries reset temporal comparisons. Sample coordinates do not imply a timestamp or sampling interval. A statistically unusual value is not automatically invalid data.

Physical/unit validation, validated stuck-sensor rules, lagged cross-correlation, clustering, natural-language rules, gradual drift, fault diagnosis, browser uploads, and a second-domain demonstration remain **unimplemented**. See the [requirement coverage and roadmap](docs/roadmap.md). This is a single local workspace, with no login or multi-tenancy.

## Running and validating the repository

Development uses Python 3.12, `uv`, Node 24, and pnpm 11.19.0. Locked dependencies are committed.

```bash
make install
make db                 # PostgreSQL exposed locally at port 5433
make migrate
make api                # terminal 1; localhost:8000
make worker             # terminal 2; synthetic fixture by default
make web                # terminal 3; localhost:5173
make check              # lint, types, CPU tests, devlog validation, web build
make test-postgres      # migrations, concurrent claims, immutable records
make test-browser       # running Docker app on localhost:8080 + synthetic fixture
make smoke-restart      # synthetic stack only; restarts db/API/worker and checks recovery
make smoke-data CSV_PATH=./te_process.csv
```

`make types` regenerates frontend types from the backend's OpenAPI schema. Native development commands read `.env`; `make` supplies the local database and source paths. See the [development guide](docs/development.md) for service lifecycle, browser setup, environment overrides, and test isolation.

## Find the right context

| Need | Start here |
|---|---|
| Agent instructions and invariants | [AGENTS.md](AGENTS.md) |
| Active objective, owners, blockers, next steps | [Current state](devlog/current.md) |
| Durable choices and rationale | [Decisions](devlog/decisions.md) |
| System boundaries and data/model flow | [Architecture](docs/architecture.md) |
| Phase status and challenge coverage | [Roadmap](docs/roadmap.md) |
| Hierarchical handoff/context conventions | [Devlog guide](devlog/README.md) |

Development context belongs in the devlog; operational evidence and human reviews belong in the application database. Git owns chronology.

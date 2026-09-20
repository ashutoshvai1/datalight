# Development and validation

## Setup

Use Python 3.12, uv, Node 24 (`.nvmrc`), and pnpm 11.19.0 (`packageManager`). Install pnpm through Corepack or your normal package manager. `make install` installs the locked Python/JS dependencies. Only esbuild's required dependency build script is enabled.

`make db` starts PostgreSQL and exposes localhost:5433 through the development Compose override. `make migrate` upgrades it. Run `make api`, `make worker`, and `make web` in separate terminals; Vite proxies requests to localhost:8000. Defaults use the synthetic fixture. Use `DATA_DIR` for a directory of selectable sources; native `make` defaults derive it from `CSV_PATH`. Model settings come from ignored `.env`, while Make supplies the local database URL and data path.

For the production-like local stack, run `DATA_DIR=./tests/fixtures docker compose up --build -d`. The browser is localhost:8080. Run `docker compose logs --tail=100 api worker` to diagnose startup. Missing mounts fail clearly; source changes require a new analysis. `docker compose down` preserves database history. Deleting the named volume destroys all reports and reviews; it is not part of normal restart or validation.

The default Docker context is machine-specific. On this development machine, an existing ARM Lima VM can be addressed with `DOCKER_HOST=unix://$HOME/.lima/docker/sock/docker.sock`; this is optional local setup, not a repository dependency. No command changes the user's global Docker context.

## Checks

Use [DATASET.md](DATASET.md) for the primary testbed's schema, run boundaries, labels, and measured characteristics when preparing or evaluating the demo. Use [architecture](architecture.md) for application behavior and source-adapter limits. The reference's aggregate ranges and known labels must not seed detector thresholds or model prompts. Keep synthetic fixtures for isolated CI checks; the ignored real-data demo can be recreated with `uv run --project backend python scripts/prepare_demo.py te_process.csv` as described in the [README](../README.md).

| Command | Coverage |
|---|---|
| `make check` | Ruff, mypy, CPU tests, devlog links/structure, TypeScript, ESLint, production web build |
| `make test-postgres` | Real migrations, schema drift, concurrent bootstrap/claims, immutable evidence |
| `make types` | Export OpenAPI and regenerate committed browser types |
| `make test-browser` | Actual browser/API workflow against the running synthetic deployment |
| `make smoke-restart` | Synthetic Compose stack only; restarts database/API/worker, checks all review actions and contiguous replay |
| `make smoke-data CSV_PATH=./te_process.csv` | Bounded deterministic analysis on 200 subsequent windows; reports peak RSS |

PostgreSQL tests use `TEST_DATABASE_URL` and create/drop only UUID-named test schemas. They never clear the application schema. CPU tests use temporary SQLite databases for fast behavioral coverage; PostgreSQL-specific correctness requires the dedicated tests. CI runs both.

Browser setup: `cd apps/web && pnpm exec playwright install chromium`. Tests require a synthetic deployment at `BASE_URL` (default http://localhost:8080), create a fresh analysis, and append clearly named test reviews. Do not point them at an operator's real session. CI starts an isolated Compose project. Screenshots and traces remain ignored build artifacts.

`make smoke-data` is a partial bounded-window check, not a full-file throughput claim. Full dataset runtime/database growth should be measured before judging. No real-derived report artifacts are committed.

## Contracts and changes

The backend owns public schemas. After editing them, run `make types` and commit `apps/web/openapi.json` and `apps/web/src/generated/api.ts`. CI detects drift. Errors use FastAPI's standard `detail` envelope; controls reject completed runs with 409. List resources are bounded/paginated. SSE notifications can be replayed with `Last-Event-ID`; the UI refetches authoritative REST state.

Add schema changes as Alembic revisions; do not edit already-shipped revisions. Coordinate shared contracts and migration ownership when multiple contributors work concurrently. Use separate worktrees/branches, focused tests, and the [agent workflow](../AGENTS.md).

## Provider verification

Set `LLM_ENABLED=true`, the organizer's key, and the exact model identifier in `.env`. The default `mistralai/Mistral-Large-3-675B-Instruct-2512-NVFP4` was discovered through the supplied endpoint's `/v1/models` route; the shorter deployment slug is not its model ID. Recreate API/worker to load changed environment variables, then start a new analysis. Verify the model-call record and evidence-linked hypotheses. Do not use raw-data prompts to test access.

The fake transport tests prove request shape, validation, and failure behavior; they cannot prove endpoint availability, geographic hosting, or the deployed model identifier. A provider swap changes settings, not analysis code. No automatic external retry runs for an ordinary invalid response/timeout; start a new analysis after fixing configuration. A crash with an unknown request outcome is separately recorded before a leased-job retry.

## Simplification workflow

Open the setup screen and submit a CSV path before expecting a report. The report leaves playback paused; tests must explicitly resume. UI review now targets one decision per monitoring batch, including OK. Historical foundation reports remain readable but should not be resumed with the new detector.

For an isolated Compose test project, set `COMPOSE_PROJECT_NAME`, `WEB_PORT`, `DATA_DIR=./tests/fixtures` and `LLM_ENABLED=false`. `make test-browser` takes `BASE_URL`. The restart smoke also accepts `COMPOSE_COMMAND` (for example `docker --context lima-docker compose -p datalight-qa`) so it restarts only the intended synthetic project. Never point browser/restart tests at real observations.

If a host-level `DOCKER_HOST` selects a stopped daemon, use an explicit running context for this command; do not silently change the global context. Some pnpm installations request a module purge when their store differs; local verification can use `WEB='pnpm --config.verify-deps-before-run=false --dir apps/web'` with the existing locked installation. `UV_CACHE_DIR=/tmp/datalight-uv` keeps cache writes in the sandbox.

## Demo-improvement verification

Uploads use `UPLOAD_DIR` (Docker: `/uploads`) and `MAX_UPLOAD_BYTES` (default 268435456). API and worker share the persistent uploads volume. The web entrypoint derives the proxy limit from the same byte setting plus 1 MiB for multipart framing; the backend enforces the exact file limit. Native development can set `UPLOAD_DIR=./runtime/uploads` to use a writable local directory.

The committed model fixture answers only synthetic test requests. To verify the complete asynchronous rule and conversation workflow without external credentials:

```bash
DATA_DIR=./tests/fixtures WEB_PORT=18080 docker --context lima-docker compose -p datalight-qa -f compose.yaml -f compose.qa.yaml up --build -d
BASE_URL=http://localhost:18080 MODEL_QA=1 make test-browser
```

Use the available Docker context on another machine. The override explicitly selects the synthetic model and clears provider credentials. It exposes only loopback API/database ports for tests, and must never be used with real observations. The browser tests cover anonymous review, two-turn conversation, uploads, exclusions, reviewed rules, frozen configuration, historical scrolling and reload behavior. API tests also cover cancelled question recovery, large/partial historical windows and first-Play races.

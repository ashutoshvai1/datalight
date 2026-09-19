# Development and validation

## Setup

Use Python 3.12, uv, Node 24 (`.nvmrc`), and pnpm 11.19.0 (`packageManager`). Install pnpm through Corepack or your normal package manager. `make install` installs the locked Python/JS dependencies. Only esbuild's required dependency build script is enabled.

`make db` starts PostgreSQL and exposes localhost:5433 through the development Compose override. `make migrate` upgrades it. Run `make api`, `make worker`, and `make web` in separate terminals; Vite proxies requests to localhost:8000. Defaults use the synthetic fixture. Override `CSV_PATH` for another source. Model settings come from ignored `.env`, while Make supplies the local database URL and data path.

For the production-like local stack, run `CSV_PATH=./tests/fixtures/demo.csv docker compose up --build -d`. The browser is localhost:8080. Run `docker compose logs --tail=100 api worker` to diagnose startup. Missing mounts fail clearly; source changes require a new analysis. `docker compose down` preserves database history. Deleting the named volume destroys all reports and reviews; it is not part of normal restart or validation.

The default Docker context is machine-specific. On this development machine, an existing ARM Lima VM can be addressed with `DOCKER_HOST=unix://$HOME/.lima/docker/sock/docker.sock`; this is optional local setup, not a repository dependency. No command changes the user's global Docker context.

## Checks

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

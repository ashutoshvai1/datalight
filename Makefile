SHELL := /bin/sh
.DEFAULT_GOAL := install
CSV_PATH ?= ./tests/fixtures/demo.csv
DATABASE_URL ?= postgresql+psycopg://datalight:datalight@localhost:5433/datalight
export DATABASE_URL
export DATA_PATH := $(abspath $(CSV_PATH))
export CSV_PATH
DATA_DIR ?= $(dir $(abspath $(CSV_PATH)))
export DATA_DIR
UV := uv run --project backend
WEB := pnpm --dir apps/web
DOCKER ?= docker
DEMO_DIR ?= $(if $(wildcard runtime/demos/demo_abrupt.csv),./runtime/demos,./tests/fixtures)
WEB_PORT ?= 8080
export WEB_PORT

.PHONY: demo install db migrate api worker web up down types lint typecheck test test-postgres test-browser docs check smoke-data smoke-restart
demo:
	@echo "Starting Datalight with CSVs from $(DEMO_DIR)"
	DATA_DIR="$(DEMO_DIR)" $(DOCKER) compose up --build --wait
	@echo "Ready: http://localhost:$(WEB_PORT) — choose New analysis to load a demo."
install:
	uv sync --project backend --frozen
	$(WEB) install --frozen-lockfile
db:
	docker compose -f compose.yaml -f compose.dev.yaml up -d db
migrate:
	cd backend && uv run alembic upgrade head
api:
	$(UV) uvicorn datalight.api:app --host 127.0.0.1 --port 8000 --reload
worker:
	$(UV) python -m datalight.worker
web:
	$(WEB) dev
up:
	docker compose up --build -d
down:
	docker compose down
types:
	$(UV) python scripts/export_openapi.py
	$(WEB) api:generate
lint:
	$(UV) ruff check backend scripts
	$(WEB) lint
typecheck:
	$(UV) mypy --config-file backend/pyproject.toml backend/src/datalight
	$(WEB) typecheck
test:
	$(UV) pytest backend/tests -m 'not postgres' -q
test-postgres:
	TEST_DATABASE_URL="$(DATABASE_URL)" $(UV) pytest backend/tests/test_postgres.py -q
test-browser:
	$(WEB) test:e2e
docs:
	$(UV) python scripts/check_devlog.py
check: lint typecheck test docs
	$(WEB) build
smoke-data:
	$(UV) python scripts/smoke_csv.py "$(CSV_PATH)"
smoke-restart:
	$(UV) python scripts/smoke_restart.py

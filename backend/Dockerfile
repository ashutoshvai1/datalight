FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5.31 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
RUN uv sync --frozen --no-dev && useradd --create-home --uid 10001 datalight
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER datalight
CMD ["uvicorn", "datalight.api:app", "--host", "0.0.0.0", "--port", "8000"]

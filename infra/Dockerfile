FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install curl and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Install uv pinned version by digest (AUD-38, RV-13)
COPY --from=ghcr.io/astral-sh/uv:0.6.3@sha256:dcc87ef71c5e5d344f09ea24942907c3e2e60eeeb6fac866f8212c185edbf55b /uv /bin/uv

# Copy project definition and lockfile
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN uv sync --frozen --no-dev

# Copy application source (RV-08: never copy local data/ SQLite artifacts into image)
COPY backend/ ./backend/
COPY schemas/ ./schemas/
COPY sim/ ./sim/
COPY config/ ./config/
COPY alembic.ini ./

# RV-13: Create unprivileged runtime user and writable empty data directory
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

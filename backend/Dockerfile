# Automation Center backend. Multi-arch (amd64/arm64) via python:slim.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
# Install runtime deps only (resolved from pyproject).
RUN pip install --no-cache-dir "." && pip uninstall -y automation-center-backend

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./
COPY entrypoint.sh ./

RUN useradd --system --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=20s \
    CMD curl -fsS http://localhost:8080/api/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# --- test stage: `docker build --target test` runs the suite ---
FROM base AS test
USER root
RUN pip install --no-cache-dir "pytest==8.3.4" "pytest-cov==6.0.0" "anyio==4.7.0"
COPY tests ./tests
ENV AC_ENVIRONMENT=testing AC_DATABASE_URL=sqlite+pysqlite:///:memory:
RUN pytest -q --tb=short -rf

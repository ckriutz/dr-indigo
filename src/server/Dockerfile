# Shared base image and tooling for runtime and evaluation targets
FROM --platform=linux/amd64 python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency definitions before the rest of the source for better caching
COPY pyproject.toml uv.lock ./

# Runtime container for serving the FastAPI application
FROM base AS runtime

RUN uv sync --frozen --no-dev --no-cache

ENV PATH="/app/.venv/bin:${PATH}" \
	PORT=8000

# Copy the rest of the application code
COPY . .

EXPOSE 8000

# Health check tailored for Azure App Service
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
	CMD python -c "import os, urllib.request; url = f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/openapi.json'; urllib.request.urlopen(url, timeout=5).read()"

# Entrypoint uses the PORT provided by Azure App Service
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

# Evaluation container used for local or CI eval runs
FROM base AS eval

RUN uv sync --frozen --no-dev --no-cache --group eval

ENV PATH="/app/.venv/bin:${PATH}" \
	AGENT_SERVER_URL="http://api:8000"

COPY . .

ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "python", "-m", "eval.local_evaluation"]
CMD []

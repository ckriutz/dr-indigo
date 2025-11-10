# Base image compatible with Azure App Service
FROM python:3.12-slim

# Configure environment and working directory
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PORT=8000

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Prepare project layout expected by the application imports
RUN mkdir -p src/server

# Install system dependencies and uv package manager
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#         curl \
#         gcc \
#     && rm -rf /var/lib/apt/lists/* && \
#     curl -LsSf https://astral.sh/uv/install.sh | sh && \
#     mv /root/.local/bin/uv /usr/local/bin/uv

# Create a non-root user for security
# RUN useradd -m -u 1000 appuser && \
#     chown -R appuser:appuser /app

# USER appuser

# Copy dependency definitions before the rest of the source for better caching
COPY pyproject.toml uv.lock ./src/server/

WORKDIR /app/src/server

# Sync pinned dependencies into a project-local virtualenv using uv.lock
RUN uv sync --frozen --no-dev --no-cache

# Ensure the virtual environment binaries are on PATH for subsequent layers and runtime
ENV PATH="/app/src/server/.venv/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Copy the rest of the application code
COPY . .

# Document the port the container listens on
EXPOSE 8000

# Health check tailored for Azure App Service
# HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
#     CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}').read()"

# Entrypoint uses the PORT provided by Azure App Service
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

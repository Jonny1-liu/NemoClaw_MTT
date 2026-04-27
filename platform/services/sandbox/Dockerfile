FROM python:3.12-slim AS base
WORKDIR /app
RUN pip install uv

# ─── Dev stage
FROM base AS dev
COPY pyproject.toml .
RUN uv sync --extra dev
COPY src/ src/
CMD ["uv", "run", "uvicorn", "sandbox.main:app", "--host", "0.0.0.0", "--port", "3002", "--reload"]

# ─── Production stage
FROM base AS prod
COPY pyproject.toml .
RUN uv sync --no-dev
COPY src/ src/
CMD ["uv", "run", "uvicorn", "sandbox.main:app", "--host", "0.0.0.0", "--port", "3002", "--workers", "2"]

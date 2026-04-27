FROM python:3.12-slim AS base
WORKDIR /workspace
RUN pip install uv

# ─── Dev stage
FROM base AS dev
COPY pyproject.toml /workspace/pyproject.toml
COPY packages/shared /workspace/packages/shared
COPY services/sandbox /workspace/services/sandbox
WORKDIR /workspace/services/sandbox
RUN uv sync --extra dev
CMD ["uv", "run", "uvicorn", "sandbox.main:app", "--host", "0.0.0.0", "--port", "3002", "--reload"]

# ─── Production stage
FROM base AS prod
COPY pyproject.toml /workspace/pyproject.toml
COPY packages/shared /workspace/packages/shared
COPY services/sandbox /workspace/services/sandbox
WORKDIR /workspace/services/sandbox
RUN uv sync --no-dev
CMD ["uv", "run", "uvicorn", "sandbox.main:app", "--host", "0.0.0.0", "--port", "3002", "--workers", "2"]

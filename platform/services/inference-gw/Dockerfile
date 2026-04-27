FROM python:3.12-slim AS base
WORKDIR /workspace
RUN pip install uv

# ─── Dev stage
FROM base AS dev
COPY pyproject.toml /workspace/pyproject.toml
COPY packages/shared /workspace/packages/shared
COPY services/inference-gw /workspace/services/inference-gw
WORKDIR /workspace/services/inference-gw
RUN uv sync --extra dev
CMD ["uv", "run", "uvicorn", "inference_gw.main:app", "--host", "0.0.0.0", "--port", "3003", "--reload"]

# ─── Production stage
FROM base AS prod
COPY pyproject.toml /workspace/pyproject.toml
COPY packages/shared /workspace/packages/shared
COPY services/inference-gw /workspace/services/inference-gw
WORKDIR /workspace/services/inference-gw
RUN uv sync --no-dev
CMD ["uv", "run", "uvicorn", "inference_gw.main:app", "--host", "0.0.0.0", "--port", "3003", "--workers", "2"]

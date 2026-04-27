FROM python:3.12-slim AS base
WORKDIR /workspace
RUN pip install uv

# ─── Dev stage
FROM base AS dev
# 複製 workspace 根設定（uv 需要它來解析 shared 依賴）
COPY pyproject.toml /workspace/pyproject.toml
# 複製 shared 套件
COPY packages/shared /workspace/packages/shared
# 複製服務本身
COPY services/tenant /workspace/services/tenant
WORKDIR /workspace/services/tenant
RUN uv sync --extra dev
CMD ["uv", "run", "uvicorn", "tenant.main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]

# ─── Production stage
FROM base AS prod
COPY pyproject.toml /workspace/pyproject.toml
COPY packages/shared /workspace/packages/shared
COPY services/tenant /workspace/services/tenant
WORKDIR /workspace/services/tenant
RUN uv sync --no-dev
CMD ["uv", "run", "uvicorn", "tenant.main:app", "--host", "0.0.0.0", "--port", "3001", "--workers", "2"]

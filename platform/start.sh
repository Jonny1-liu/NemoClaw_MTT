#!/usr/bin/env bash
# NemoClaw SaaS Platform — 智慧啟動腳本
#
# 自動偵測 PostgreSQL 是否已在本機運行：
#   有 native PostgreSQL → 直接啟動平台服務（跳過 DB 容器）
#   無 native PostgreSQL → 同時啟動 DB + 平台服務
#
# 用法：
#   ./start.sh                   啟動核心服務（Tenant + Sandbox）
#   ./start.sh --with-inference  同時啟動 Inference GW（需要 NVIDIA_API_KEY）
#   ./start.sh --stop            停止所有服務
#   ./start.sh --logs            查看所有服務日誌
#   ./start.sh --status          查看服務狀態

set -e

ENV_FILE="$(dirname "$0")/.env"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-nemoclaw}"
WITH_INFERENCE=false

# ─── 參數處理 ─────────────────────────────────────────────────

for arg in "$@"; do
  case "$arg" in
    --stop)
      echo "Stopping all services..."
      docker compose --profile with-inference down 2>/dev/null || docker compose down
      exit 0
      ;;
    --logs)
      docker compose logs -f
      exit 0
      ;;
    --status)
      docker compose ps
      exit 0
      ;;
    --with-inference)
      WITH_INFERENCE=true
      ;;
    --help|-h)
      grep "^#" "$0" | grep -v "^#!/" | sed 's/^# \?//'
      exit 0
      ;;
  esac
done

# ─── 前置檢查 ─────────────────────────────────────────────────

echo "NemoClaw SaaS Platform — Starting..."
if $WITH_INFERENCE; then
  echo "  Mode: Core + Inference Gateway"
else
  echo "  Mode: Core only (Tenant + Sandbox)"
  echo "  Tip:  Add --with-inference to also start Inference GW"
fi
echo ""

if [ ! -f "$ENV_FILE" ]; then
  echo "  [WARN] .env not found, copying from .env.example..."
  cp "$(dirname "$0")/.env.example" "$ENV_FILE"
  echo "  [INFO] Please edit .env and set your passwords/API keys, then re-run."
  exit 1
fi

# 安全讀取 .env（不 source，避免密碼特殊字元造成 bash 語法錯誤）
_read_env() {
  local key="$1" default="$2"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null \
    | head -1 | cut -d'=' -f2- \
    | sed "s/^['\"]//; s/['\"]$//" \
    | grep . || echo "${default}"
}

POSTGRES_HOST=$(_read_env "POSTGRES_HOST" "localhost")
POSTGRES_PORT=$(_read_env "POSTGRES_PORT" "5432")
POSTGRES_USER=$(_read_env "POSTGRES_USER" "nemoclaw")

# ─── 偵測 PostgreSQL ──────────────────────────────────────────

echo "  Checking PostgreSQL..."

check_postgres() {
  pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" \
             -U "${POSTGRES_USER}" -q 2>/dev/null
}

COMPOSE_PROFILES=()
if check_postgres; then
  echo "  ✅ PostgreSQL running at ${POSTGRES_HOST}:${POSTGRES_PORT} (native)"
  export POSTGRES_HOST="${POSTGRES_HOST}"
else
  echo "  ⚠️  PostgreSQL not found → starting container..."
  COMPOSE_PROFILES+=("with-db")
  export POSTGRES_HOST="host.docker.internal"
fi

if $WITH_INFERENCE; then
  COMPOSE_PROFILES+=("with-inference")
fi

# ─── 啟動服務 ─────────────────────────────────────────────────

echo ""
echo "  Building and starting services..."

if [ ${#COMPOSE_PROFILES[@]} -gt 0 ]; then
  PROFILE_ARGS=""
  for p in "${COMPOSE_PROFILES[@]}"; do
    PROFILE_ARGS="$PROFILE_ARGS --profile $p"
  done
  docker compose $PROFILE_ARGS up -d --build
else
  docker compose up -d --build
fi

# ─── 等待健康檢查 ─────────────────────────────────────────────

echo ""
echo "  Waiting for services to become healthy..."
sleep 8

# 核心服務
SERVICES=("tenant:3001" "sandbox:3002")
if $WITH_INFERENCE; then
  SERVICES+=("inference-gw:3003")
fi

ALL_OK=true
for svc in "${SERVICES[@]}"; do
  name="${svc%%:*}"
  port="${svc##*:}"
  if curl -sf "http://localhost:${port}/health" > /dev/null 2>&1; then
    echo "  ✅ ${name} (port ${port})"
  else
    echo "  ⏳ ${name} (port ${port}) — still starting"
    ALL_OK=false
  fi
done

echo ""
if $ALL_OK; then
  echo "All services are up!"
  echo ""
  echo "  Tenant Service  : http://localhost:3001/docs"
  echo "  Sandbox Service : http://localhost:3002/docs"
  $WITH_INFERENCE && echo "  Inference GW    : http://localhost:3003/docs"
  echo "  Compatibility   : http://localhost:3002/admin/compatibility"
  echo ""
  echo "  Logs : $(cd "$(dirname "$0")" && pwd)/../logs/"
  echo ""
  echo "  To stop  : ./start.sh --stop"
  echo "  To view  : ./start.sh --logs"
else
  echo "Services are still starting. Check with: ./start.sh --logs"
fi

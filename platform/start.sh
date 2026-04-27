#!/usr/bin/env bash
# NemoClaw SaaS Platform — 智慧啟動腳本
#
# 自動偵測 PostgreSQL 是否已在本機運行：
#   有 native PostgreSQL → 直接啟動平台服務（跳過 DB 容器）
#   無 native PostgreSQL → 同時啟動 DB + 平台服務
#
# 用法：
#   ./start.sh          一般啟動
#   ./start.sh --stop   停止所有服務
#   ./start.sh --logs   查看日誌

set -e

ENV_FILE="$(dirname "$0")/.env"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-nemoclaw}"

# ─── 參數處理 ─────────────────────────────────────────────────

case "${1:-}" in
  --stop)
    echo "⏹  Stopping all services..."
    docker compose down
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
esac

# ─── 前置檢查 ─────────────────────────────────────────────────

echo "NemoClaw SaaS Platform — Starting..."
echo ""

# 確認 .env 存在
if [ ! -f "$ENV_FILE" ]; then
  echo "  [WARN] .env not found, copying from .env.example..."
  cp "$(dirname "$0")/.env.example" "$ENV_FILE"
  echo "  [INFO] Please edit .env and set your passwords/API keys, then re-run."
  exit 1
fi

# 安全讀取 .env（不用 source，避免密碼特殊字元造成 bash 語法錯誤）
_read_env() {
  local key="$1"
  local default="$2"
  local val
  # grep 取得該行，cut 取 = 後的值，sed 移除首尾引號
  val=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null \
        | head -1 \
        | cut -d'=' -f2- \
        | sed "s/^['\"]//; s/['\"]$//")
  echo "${val:-$default}"
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

if check_postgres; then
  echo "  ✅ PostgreSQL is running at ${POSTGRES_HOST}:${POSTGRES_PORT}"
  echo "     → Using native PostgreSQL, skipping DB container"
  COMPOSE_PROFILES=""
  export POSTGRES_HOST="${POSTGRES_HOST}"
else
  echo "  ⚠️  PostgreSQL not detected at ${POSTGRES_HOST}:${POSTGRES_PORT}"
  echo "     → Starting PostgreSQL container..."
  COMPOSE_PROFILES="with-db"
  export POSTGRES_HOST="host.docker.internal"
fi

# ─── 啟動服務 ─────────────────────────────────────────────────

echo ""
echo "  Starting platform services..."

if [ -n "$COMPOSE_PROFILES" ]; then
  docker compose --profile "$COMPOSE_PROFILES" up -d --build
else
  docker compose up -d --build
fi

# ─── 等待健康檢查 ─────────────────────────────────────────────

echo ""
echo "  Waiting for services to become healthy..."
sleep 5

SERVICES=("tenant:3001" "sandbox:3002" "inference-gw:3003")
ALL_OK=true

for svc in "${SERVICES[@]}"; do
  name="${svc%%:*}"
  port="${svc##*:}"
  if curl -sf "http://localhost:${port}/health" > /dev/null 2>&1; then
    echo "  ✅ ${name} (port ${port})"
  else
    echo "  ❌ ${name} (port ${port}) — not responding yet"
    ALL_OK=false
  fi
done

echo ""
if $ALL_OK; then
  echo "All services are up and running!"
  echo ""
  echo "  Tenant Service  : http://localhost:3001/docs"
  echo "  Sandbox Service : http://localhost:3002/docs"
  echo "  Inference GW    : http://localhost:3003/docs"
  echo "  Compatibility   : http://localhost:3002/admin/compatibility"
  echo ""
  echo "  Logs            : $(dirname "$0")/../logs/"
else
  echo "Some services are still starting. Check logs with: ./start.sh --logs"
fi

"""Tenant Service — 租戶管理、配額、Schema 佈建"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

# .env 必須在所有模組載入前讀入 os.environ
# 讓 AUTH_MODE 等環境變數對 shared.auth 可見
from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[4] / ".env", override=False)

import structlog
import uvicorn
from fastapi import FastAPI

from tenant.config import settings
from tenant.routes.health import router as health_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("tenant_service.starting", port=settings.service_port)
    # TODO: 初始化 DB 連線池、Redis client
    yield
    log.info("tenant_service.stopping")
    # TODO: 關閉 DB 連線池


app = FastAPI(
    title="Tenant Service",
    description="租戶管理、配額控制、Schema-per-tenant 佈建",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)

from tenant.routes.tenants import router as tenants_router
app.include_router(tenants_router)


if __name__ == "__main__":
    uvicorn.run(
        "tenant.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True,
    )

"""Billing Service — 訂閱方案、Stripe 整合、用量計費"""
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import APIRouter, FastAPI

from shared.types import HealthResponse

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("billing_service.starting")
    # TODO: 初始化 Stripe client、DB 連線
    yield
    log.info("billing_service.stopping")


app = FastAPI(
    title="Billing Service",
    description="訂閱方案管理、Stripe Webhook 處理、用量計費",
    version="0.1.0",
    lifespan=lifespan,
)

health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    return HealthResponse(service="billing")


app.include_router(health_router)

# TODO:
# from billing.routes.subscriptions import router as subs_router
# from billing.routes.webhooks import router as webhook_router
# app.include_router(subs_router, prefix="/subscriptions")
# app.include_router(webhook_router, prefix="/webhooks/stripe")


if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", "3004"))
    uvicorn.run("billing.main:app", host="0.0.0.0", port=port, reload=True)

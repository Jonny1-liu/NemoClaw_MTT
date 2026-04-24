"""平台共用基礎型別 — 所有服務共享，不依賴任何外部系統"""
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

# ─── ID 型別別名 ──────────────────────────────────────────────

TenantID = Annotated[str, Field(pattern=r"^[a-z0-9]{8,32}$")]
SandboxID = Annotated[str, Field(pattern=r"^sb-[a-z0-9]{16}$")]
UserID = UUID


# ─── 訂閱方案 ────────────────────────────────────────────────

class Plan(str):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


# ─── 共用 Response 格式 ───────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None

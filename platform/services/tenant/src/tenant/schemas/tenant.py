"""Pydantic schemas — API 請求與回應格式（與 ORM 模型分離）"""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from tenant.models.tenant import Plan, TenantStatus

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


# ─── Request schemas ─────────────────────────────────────────

class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=3, max_length=63,
                      description="URL-safe 識別符，小寫英數字與連字號")
    plan: Plan = Plan.FREE

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug 只能包含小寫英數字與連字號，不能以連字號開頭或結尾"
            )
        return v


class UpdateTenantRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    plan: Plan | None = None


class ConsumeQuotaRequest(BaseModel):
    resource: str = Field(description="'tokens' 或 'sandboxes'")
    amount:   int = Field(description="消耗數量（正數）或釋放數量（負數，用於刪除沙箱）")


# ─── Response schemas ────────────────────────────────────────

class QuotaItemResponse(BaseModel):
    resource:  str
    limit:     int   # -1 = 無限制
    used:      int
    remaining: int   # -1 = 無限制
    reset_at:  datetime | None

    model_config = {"from_attributes": True}


class TenantResponse(BaseModel):
    id:         uuid.UUID
    name:       str
    slug:       str
    plan:       Plan
    status:     TenantStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantWithQuotaResponse(TenantResponse):
    quotas: list[QuotaItemResponse] = []

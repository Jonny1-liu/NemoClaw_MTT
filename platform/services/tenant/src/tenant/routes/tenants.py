"""Tenant API routes — 只負責 HTTP 層（解析請求、轉換例外、回傳回應）"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import TokenPayload, require_auth, require_tenant_access
from tenant.db import get_session
from tenant.repositories.tenant_repo import TenantRepository
from tenant.schemas.tenant import (
    ConsumeQuotaRequest,
    CreateTenantRequest,
    QuotaItemResponse,
    TenantResponse,
    TenantWithQuotaResponse,
    UpdateTenantRequest,
)
from tenant.services.tenant_service import (
    InvalidPlanDowngradeError,
    QuotaExceededError,
    SlugAlreadyExistsError,
    TenantNotFoundError,
    TenantService,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


# ─── Dependency：組裝 Service（方便測試時替換）────────────────

def get_service(session: AsyncSession = Depends(get_session)) -> TenantService:
    return TenantService(TenantRepository(session))


# ─── Endpoints ───────────────────────────────────────────────

@router.post(
    "/",
    response_model=TenantWithQuotaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立新租戶",
)
async def create_tenant(
    body: CreateTenantRequest,
    svc: TenantService = Depends(get_service),
    _user: TokenPayload = Depends(require_auth),   # 需登入，任何角色皆可
) -> TenantWithQuotaResponse:
    try:
        tenant = await svc.create_tenant(
            name=body.name, slug=body.slug, plan=body.plan
        )
        return TenantWithQuotaResponse.model_validate(tenant)
    except SlugAlreadyExistsError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/{tenant_id}",
    response_model=TenantWithQuotaResponse,
    summary="查詢租戶（含配額）",
)
async def get_tenant(
    tenant_id: uuid.UUID,
    svc: TenantService = Depends(get_service),
    user: TokenPayload = Depends(require_tenant_access()),  # 只能查自己的租戶
) -> TenantWithQuotaResponse:
    try:
        tenant = await svc.get_tenant(tenant_id)
        return TenantWithQuotaResponse.model_validate(tenant)
    except TenantNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="更新租戶（名稱 / 方案）",
)
async def update_tenant(
    tenant_id: uuid.UUID,
    body: UpdateTenantRequest,
    svc: TenantService = Depends(get_service),
    user: TokenPayload = Depends(require_tenant_access()),  # 只能改自己的租戶
) -> TenantResponse:
    try:
        tenant = await svc.update_tenant(
            tenant_id, name=body.name, plan=body.plan
        )
        return TenantResponse.model_validate(tenant)
    except TenantNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    except InvalidPlanDowngradeError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/{tenant_id}/quota/{resource}",
    response_model=QuotaItemResponse,
    summary="查詢單項配額",
)
async def get_quota(
    tenant_id: uuid.UUID,
    resource: str,
    svc: TenantService = Depends(get_service),
    user: TokenPayload = Depends(require_tenant_access()),
) -> QuotaItemResponse:
    try:
        quota = await svc.get_quota(tenant_id, resource)
        return QuotaItemResponse.model_validate(quota)
    except TenantNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post(
    "/{tenant_id}/quota/consume",
    response_model=QuotaItemResponse,
    summary="扣減配額（由 Inference GW 等內部服務呼叫）",
)
async def consume_quota(
    tenant_id: uuid.UUID,
    body: ConsumeQuotaRequest,
    svc: TenantService = Depends(get_service),
    _user: TokenPayload = Depends(require_auth),   # 內部服務呼叫，只需登入
) -> QuotaItemResponse:
    try:
        quota = await svc.consume_quota(
            tenant_id, resource=body.resource, amount=body.amount
        )
        return QuotaItemResponse.model_validate(quota)
    except TenantNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    except QuotaExceededError as e:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "QUOTA_EXCEEDED",
                "resource": e.resource,
                "limit": e.limit,
                "used": e.used,
            },
        )

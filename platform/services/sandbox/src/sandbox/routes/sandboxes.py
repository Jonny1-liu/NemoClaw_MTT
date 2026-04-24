"""Sandbox API routes"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sandbox.db import get_session
from sandbox.repositories.sandbox_repo import SandboxRepository
from sandbox.schemas.sandbox import (
    CreateSandboxRequest, SandboxListResponse, SandboxResponse,
    UpdateNetworkPolicyRequest,
)
from sandbox.repositories.sandbox_repo import SandboxNameConflictError
from sandbox.services.sandbox_service import (
    SandboxNotFoundError, SandboxNotStoppedError, SandboxService,
)
from sandbox.services.tenant_client import QuotaExceededError, TenantClient
from shared.auth import TokenPayload, require_auth, require_tenant_access

router = APIRouter(prefix="/sandboxes", tags=["sandboxes"])

# Sandbox backend 為 module-level singleton（由 main.py 初始化）
_backend = None
_tenant_client = TenantClient()


def set_backend(b) -> None:
    global _backend
    _backend = b


def get_service(session: AsyncSession = Depends(get_session)) -> SandboxService:
    return SandboxService(
        repo=SandboxRepository(session),
        backend=_backend,
        tenant_client=_tenant_client,
    )


@router.post(
    "/",
    response_model=SandboxResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立沙箱",
)
async def create_sandbox(
    body: CreateSandboxRequest,
    svc:  SandboxService = Depends(get_service),
    user: TokenPayload   = Depends(require_auth),
) -> SandboxResponse:
    try:
        sb = await svc.create_sandbox(
            tenant_id=user.tenant_id,
            name=body.name,
            inference_model=body.inference_model,
            allow_domains=body.network_policy.allow_domains,
        )
        return SandboxResponse.model_validate(sb)
    except QuotaExceededError as e:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "SANDBOX_QUOTA_EXCEEDED",
                    "limit": e.limit, "used": e.used},
        )
    except SandboxNameConflictError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/", response_model=SandboxListResponse, summary="列出沙箱")
async def list_sandboxes(
    svc:  SandboxService = Depends(get_service),
    user: TokenPayload   = Depends(require_auth),
) -> SandboxListResponse:
    items, total = await svc.list_sandboxes(user.tenant_id)
    return SandboxListResponse(
        items=[SandboxResponse.model_validate(s) for s in items],
        total=total,
    )


@router.get("/{sandbox_id}", response_model=SandboxResponse, summary="查詢沙箱")
async def get_sandbox(
    sandbox_id: uuid.UUID,
    svc:  SandboxService = Depends(get_service),
    user: TokenPayload   = Depends(require_auth),
) -> SandboxResponse:
    try:
        sb = await svc.get_sandbox(sandbox_id, user.tenant_id)
        return SandboxResponse.model_validate(sb)
    except SandboxNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sandbox not found")


@router.post("/{sandbox_id}/start", response_model=SandboxResponse, summary="啟動沙箱")
async def start_sandbox(
    sandbox_id: uuid.UUID,
    svc:  SandboxService = Depends(get_service),
    user: TokenPayload   = Depends(require_auth),
) -> SandboxResponse:
    try:
        sb = await svc.start_sandbox(sandbox_id, user.tenant_id)
        return SandboxResponse.model_validate(sb)
    except SandboxNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sandbox not found")
    except SandboxNotStoppedError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/{sandbox_id}/stop", response_model=SandboxResponse, summary="停止沙箱")
async def stop_sandbox(
    sandbox_id: uuid.UUID,
    svc:  SandboxService = Depends(get_service),
    user: TokenPayload   = Depends(require_auth),
) -> SandboxResponse:
    try:
        sb = await svc.stop_sandbox(sandbox_id, user.tenant_id)
        return SandboxResponse.model_validate(sb)
    except SandboxNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sandbox not found")
    except SandboxNotStoppedError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.delete(
    "/{sandbox_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除沙箱（Running 狀態需加 ?force=true 才可強制刪除）",
)
async def delete_sandbox(
    sandbox_id: uuid.UUID,
    force: bool = False,
    svc:  SandboxService = Depends(get_service),
    user: TokenPayload   = Depends(require_auth),
) -> None:
    try:
        await svc.delete_sandbox(sandbox_id, user.tenant_id, force=force)
    except SandboxNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sandbox not found")
    except SandboxNotStoppedError as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e) + " 若要強制刪除，請加上 ?force=true 參數",
        )


@router.put(
    "/{sandbox_id}/policies",
    response_model=SandboxResponse,
    summary="更新網路政策（動態套用，不重啟沙箱）",
)
async def update_policy(
    sandbox_id: uuid.UUID,
    body: UpdateNetworkPolicyRequest,
    svc:  SandboxService = Depends(get_service),
    user: TokenPayload   = Depends(require_auth),
) -> SandboxResponse:
    try:
        sb = await svc.update_network_policy(
            sandbox_id, user.tenant_id,
            allow_domains=body.allow_domains,
            deny_all_other=body.deny_all_other,
        )
        return SandboxResponse.model_validate(sb)
    except SandboxNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

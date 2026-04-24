"""
JWT Authentication — 可插拔設計

開發模式（AUTH_MODE=mock）：
  接受任何帶有 X-Mock-Tenant-ID header 的請求
  不驗證簽名，方便本機開發和測試

生產模式（AUTH_MODE=keycloak，預設）：
  從 Keycloak JWKS 端點取得公鑰
  用 RS256 驗證 JWT 簽名、過期時間、issuer

切換方式：只改 .env 的 AUTH_MODE，程式碼零修改
"""
import os
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# 讓 Swagger UI 的 Authorize 按鈕顯示 X-Mock-Tenant-ID 輸入欄
_mock_tenant_scheme = APIKeyHeader(
    name="X-Mock-Tenant-ID",
    scheme_name="MockTenantID",
    description="開發模式：填入 Tenant UUID（AUTH_MODE=mock 時使用）",
    auto_error=False,
)

# ─── Token Payload（從 JWT 解析出來的資訊）────────────────────

class TokenPayload(BaseModel):
    sub:        str                    # 使用者 UUID
    tenant_id:  str                    # 租戶 ID（自訂 claim）
    plan:       str = "free"           # 訂閱方案
    roles:      list[str] = []         # 角色清單
    email:      str | None = None


# ─── JWKS 公鑰快取（服務啟動後只抓一次）─────────────────────

_jwks_cache: dict[str, Any] = {}


async def _get_jwks(jwks_url: str) -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


# ─── 驗證邏輯 ─────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def _verify_keycloak_token(token: str) -> TokenPayload:
    """RS256 驗證 — 生產環境使用"""
    keycloak_url  = os.environ["KEYCLOAK_URL"]
    realm         = os.environ.get("KEYCLOAK_REALM", "nemoclaw")
    jwks_url      = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
    issuer        = f"{keycloak_url}/realms/{realm}"

    try:
        jwks = await _get_jwks(jwks_url)
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=issuer,
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenPayload(
        sub       = payload["sub"],
        tenant_id = payload.get("tenant_id", ""),
        plan      = payload.get("plan", "free"),
        roles     = payload.get("roles", []),
        email     = payload.get("email"),
    )


async def _verify_mock_token(request: Request) -> TokenPayload:
    """
    Mock 驗證 — 開發環境使用，不驗證簽名
    用 X-Mock-Tenant-ID header 指定租戶
    用 X-Mock-Roles header 指定角色（逗號分隔）
    """
    tenant_id = request.headers.get("X-Mock-Tenant-ID", "dev-tenant")
    roles     = request.headers.get("X-Mock-Roles", "admin").split(",")
    plan      = request.headers.get("X-Mock-Plan", "pro")

    return TokenPayload(
        sub       = "dev-user-00000000",
        tenant_id = tenant_id,
        plan      = plan,
        roles     = [r.strip() for r in roles],
        email     = "dev@nemoclaw.local",
    )


# ─── FastAPI Dependency（所有服務共用）────────────────────────

async def require_auth(
    request:     Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    _mock_tid:   str | None = Depends(_mock_tenant_scheme),  # Swagger UI 用
) -> TokenPayload:
    """
    使用方式：
        @router.get("/sandboxes")
        async def list_sandboxes(user: TokenPayload = Depends(require_auth)):
            print(user.tenant_id)
    """
    mode = os.environ.get("AUTH_MODE", "keycloak").lower()

    # Mock 和 Keycloak 模式都需要 Bearer Token，差別只在驗證方式
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if mode == "mock":
        # Mock 模式：Bearer 值不驗證（填任意字串即可），但必須存在
        return await _verify_mock_token(request)

    return await _verify_keycloak_token(credentials.credentials)


# ─── RBAC 輔助 Dependency ────────────────────────────────────

def require_role(*allowed_roles: str):
    """
    使用方式：
        @router.delete("/tenants/{id}")
        async def delete_tenant(
            user: TokenPayload = Depends(require_role("admin", "owner"))
        ):
            ...
    """
    async def _check(user: TokenPayload = Depends(require_auth)) -> TokenPayload:
        if not any(r in user.roles for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {list(allowed_roles)}",
            )
        return user
    return _check


def require_tenant_access(tenant_id_param: str = "tenant_id"):
    """
    確認請求者只能存取自己的租戶資料。
    Platform Admin 可跨租戶存取。

    使用方式：
        @router.get("/tenants/{tenant_id}")
        async def get_tenant(
            tenant_id: uuid.UUID,
            user: TokenPayload = Depends(require_tenant_access()),
        ):
            ...
    """
    async def _check(
        request: Request,
        user: TokenPayload = Depends(require_auth),
    ) -> TokenPayload:
        if "platform:admin" in user.roles:
            return user  # Platform Admin 不受限制

        path_tenant_id = request.path_params.get(tenant_id_param, "")
        if str(path_tenant_id) != user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: tenant mismatch",
            )
        return user
    return _check

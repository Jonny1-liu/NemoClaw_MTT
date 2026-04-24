"""
Tenant Service HTTP Client

Sandbox Service 呼叫 Tenant Service 查詢 sandbox 配額。
服務間通訊使用 mock token（AUTH_MODE=mock 時）。
"""
import httpx
import structlog

from sandbox.config import settings

log = structlog.get_logger()


class TenantServiceError(Exception):
    pass


class QuotaExceededError(Exception):
    def __init__(self, limit: int, used: int) -> None:
        self.limit = limit
        self.used = used
        super().__init__(f"Sandbox quota exceeded ({used}/{limit})")


class TenantClient:

    def __init__(self) -> None:
        self._base = settings.tenant_service_url
        # 服務間呼叫使用 mock token，production 會換成 service account JWT
        self._headers = {
            "Authorization": "Bearer service-account-token",
            "X-Mock-Tenant-ID": "",   # 每次呼叫時動態設定
            "X-Mock-Roles":    "admin",
        }

    async def check_sandbox_quota(self, tenant_id: str) -> None:
        """
        確認 sandbox 配額未超限。
        超限時拋出 QuotaExceededError。
        """
        headers = {**self._headers, "X-Mock-Tenant-ID": tenant_id}
        url = f"{self._base}/tenants/{tenant_id}/quota/sandboxes"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=5)

        if resp.status_code == 404:
            log.warning("tenant_client.quota_not_found", tenant_id=tenant_id)
            return   # 查不到就放行（新租戶可能尚未有 quota 記錄）

        if resp.status_code != 200:
            raise TenantServiceError(
                f"Tenant Service error: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        limit = data["limit"]
        used  = data["used"]

        if limit != -1 and used >= limit:
            raise QuotaExceededError(limit=limit, used=used)

        log.info("tenant_client.quota_ok", tenant_id=tenant_id,
                 used=used, limit=limit)

    async def consume_sandbox_quota(self, tenant_id: str) -> None:
        """建立沙箱後扣減 sandbox 配額（+1）"""
        headers = {**self._headers, "X-Mock-Tenant-ID": tenant_id}
        url = f"{self._base}/tenants/{tenant_id}/quota/consume"

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers,
                                     json={"resource": "sandboxes", "amount": 1},
                                     timeout=5)

        if resp.status_code not in (200, 402):
            log.warning("tenant_client.consume_failed",
                        status=resp.status_code, body=resp.text)

    async def release_sandbox_quota(self, tenant_id: str) -> None:
        """刪除沙箱後釋放 sandbox 配額（-1）"""
        headers = {**self._headers, "X-Mock-Tenant-ID": tenant_id}
        url = f"{self._base}/tenants/{tenant_id}/quota/consume"

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers,
                                     json={"resource": "sandboxes", "amount": -1},
                                     timeout=5)

        if resp.status_code not in (200,):
            log.warning("tenant_client.release_failed",
                        status=resp.status_code, body=resp.text)

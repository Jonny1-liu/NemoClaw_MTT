"""
Tenant Service — 業務邏輯層

規則：
  1. 不直接使用 SQLAlchemy，只呼叫 Repository
  2. 所有業務規則（配額、方案限制）集中於此
  3. 拋出語意明確的 Exception，由 Route 層轉換為 HTTP 錯誤
"""
import uuid

import structlog

from tenant.models.tenant import Plan, Tenant, TenantQuota
from tenant.repositories.tenant_repo import TenantRepository

log = structlog.get_logger()


# ─── 業務例外（語意化，不直接用 HTTP status code）────────────

class TenantNotFoundError(Exception):
    pass

class SlugAlreadyExistsError(Exception):
    pass

class QuotaExceededError(Exception):
    def __init__(self, resource: str, limit: int, used: int) -> None:
        self.resource = resource
        self.limit = limit
        self.used = used
        super().__init__(f"Quota exceeded: {resource} ({used}/{limit})")

class InvalidPlanDowngradeError(Exception):
    """降級方案時當前用量超過新方案上限"""
    pass


# ─── Service ─────────────────────────────────────────────────

class TenantService:

    def __init__(self, repo: TenantRepository) -> None:
        self._repo = repo

    async def create_tenant(
        self, name: str, slug: str, plan: Plan
    ) -> Tenant:
        log.info("tenant.create", slug=slug, plan=plan)

        if await self._repo.slug_exists(slug):
            raise SlugAlreadyExistsError(f"Slug '{slug}' is already taken")

        tenant = await self._repo.create(name=name, slug=slug, plan=plan)
        log.info("tenant.created", tenant_id=str(tenant.id), slug=slug)
        return tenant

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        return tenant

    async def update_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str | None = None,
        plan: Plan | None = None,
    ) -> Tenant:
        # 方案降級檢查：確認當前用量不超過新方案上限
        if plan is not None:
            await self._validate_plan_downgrade(tenant_id, plan)

        tenant = await self._repo.update(tenant_id, name=name, plan=plan)
        if not tenant:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")

        log.info("tenant.updated", tenant_id=str(tenant_id),
                 name=name, plan=plan)
        return tenant

    async def get_quota(
        self, tenant_id: uuid.UUID, resource: str
    ) -> TenantQuota:
        # 確認租戶存在
        await self.get_tenant(tenant_id)

        quota = await self._repo.get_quota(tenant_id, resource)
        if not quota:
            raise TenantNotFoundError(
                f"Quota record not found: {tenant_id}/{resource}"
            )
        return quota

    async def consume_quota(
        self,
        tenant_id: uuid.UUID,
        resource: str,
        amount: int,
    ) -> TenantQuota:
        """
        扣減配額主流程：
          1. 取得 quota（含 SELECT FOR UPDATE）
          2. 檢查是否會超量
          3. 扣減
        """
        quota = await self._repo.get_quota(tenant_id, resource)
        if not quota:
            raise TenantNotFoundError(
                f"Quota record not found: {tenant_id}/{resource}"
            )

        # Enterprise (-1) = 無限制，直接跳過檢查
        # amount 可為負數（釋放），釋放時不需要超量檢查
        if amount > 0 and quota.limit != -1 and (quota.used + amount) > quota.limit:
            raise QuotaExceededError(
                resource=resource,
                limit=quota.limit,
                used=quota.used,
            )

        quota = await self._repo.consume_quota(tenant_id, resource, amount)
        log.info("quota.consumed",
                 tenant_id=str(tenant_id), resource=resource, amount=amount,
                 used=quota.used, limit=quota.limit)
        return quota

    # ─── 內部輔助 ─────────────────────────────────────────────

    async def _validate_plan_downgrade(
        self, tenant_id: uuid.UUID, new_plan: Plan
    ) -> None:
        """若方案降級，確認當前用量不超過新方案上限"""
        from tenant.models.tenant import PLAN_QUOTAS
        new_limits = PLAN_QUOTAS[new_plan]

        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")

        for quota in tenant.quotas:
            new_limit = new_limits.get(quota.resource, 0)
            if new_limit != -1 and quota.used > new_limit:
                raise InvalidPlanDowngradeError(
                    f"Cannot downgrade to {new_plan}: "
                    f"{quota.resource} usage ({quota.used}) "
                    f"exceeds new plan limit ({new_limit})"
                )

"""
Tenant Repository — 所有資料庫操作集中於此

規則：
  1. 每個查詢都必須含 tenant_id 過濾（RLS 替代方案）
  2. 不允許裸 SQL 字串，全用 SQLAlchemy ORM
  3. Service 層不直接使用 SQLAlchemy，只透過此層
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tenant.models.tenant import PLAN_QUOTAS, Plan, Tenant, TenantQuota, TenantStatus


class TenantRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ─── Tenant CRUD ─────────────────────────────────────────

    async def create(self, name: str, slug: str, plan: Plan) -> Tenant:
        """建立租戶，同時建立對應 quota 記錄"""
        tenant = Tenant(name=name, slug=slug, plan=plan)
        self._s.add(tenant)
        await self._s.flush()   # 取得 id，尚未 commit

        # 依方案建立 quota 記錄
        limits = PLAN_QUOTAS[plan]
        reset_at = _next_month_start()
        for resource, limit in limits.items():
            self._s.add(TenantQuota(
                tenant_id=tenant.id,
                resource=resource,
                limit=limit,
                used=0,
                reset_at=reset_at,
            ))

        await self._s.flush()
        # quota 記錄已寫入 DB，重新載入 relationship 到記憶體
        # 避免 Pydantic 序列化時觸發 async lazy load 失敗
        await self._s.refresh(tenant, attribute_names=["quotas"])
        return tenant

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self._s.execute(
            select(Tenant)
            .where(Tenant.id == tenant_id)
            .where(Tenant.status != TenantStatus.DELETED)
            .options(selectinload(Tenant.quotas))
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self._s.execute(
            select(Tenant)
            .where(Tenant.slug == slug)
            .where(Tenant.status != TenantStatus.DELETED)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str | None = None,
        plan: Plan | None = None,
    ) -> Tenant | None:
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            return None

        if name is not None:
            tenant.name = name

        if plan is not None and plan != tenant.plan:
            tenant.plan = plan
            # 方案變更時同步更新 quota 上限
            new_limits = PLAN_QUOTAS[plan]
            for quota in tenant.quotas:
                if quota.resource in new_limits:
                    quota.limit = new_limits[quota.resource]

        return tenant

    async def soft_delete(self, tenant_id: uuid.UUID) -> bool:
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            return False
        tenant.status = TenantStatus.DELETED
        return True

    # ─── Quota 操作 ───────────────────────────────────────────

    async def get_quota(
        self, tenant_id: uuid.UUID, resource: str
    ) -> TenantQuota | None:
        """
        注意：這裡一定要同時過濾 tenant_id，
        沒有 DB 層 RLS，紀律不能鬆懈。
        """
        result = await self._s.execute(
            select(TenantQuota)
            .where(TenantQuota.tenant_id == tenant_id)   # ← 不能省
            .where(TenantQuota.resource == resource)
            .with_for_update()     # SELECT FOR UPDATE，防止並發超量
        )
        return result.scalar_one_or_none()

    async def consume_quota(
        self,
        tenant_id: uuid.UUID,
        resource: str,
        amount: int,
    ) -> TenantQuota:
        """
        扣減配額（原子操作）
        呼叫前必須先確認 quota 未超量（由 Service 層負責）
        """
        quota = await self.get_quota(tenant_id, resource)
        if not quota:
            raise ValueError(f"Quota record not found: {tenant_id}/{resource}")
        quota.used += amount
        return quota

    async def slug_exists(self, slug: str) -> bool:
        result = await self._s.execute(
            select(Tenant.id).where(Tenant.slug == slug)
        )
        return result.scalar_one_or_none() is not None


# ─── 工具函式 ─────────────────────────────────────────────────

def _next_month_start() -> datetime:
    """取得下個月 1 日 00:00:00 UTC"""
    now = datetime.now(tz=timezone.utc)
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1,
                           hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1,
                       hour=0, minute=0, second=0, microsecond=0)

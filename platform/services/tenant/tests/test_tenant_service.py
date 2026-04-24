"""
Tenant Service 單元測試

Mock Repository → 完全不需要資料庫。
測試純業務邏輯：配額計算、方案限制、例外行為。
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tenant.models.tenant import PLAN_QUOTAS, Plan, Tenant, TenantQuota, TenantStatus
from tenant.services.tenant_service import (
    InvalidPlanDowngradeError,
    QuotaExceededError,
    SlugAlreadyExistsError,
    TenantNotFoundError,
    TenantService,
)


# ─── Fixtures ────────────────────────────────────────────────

def make_mock_repo() -> AsyncMock:
    """建立 Mock TenantRepository"""
    return AsyncMock()


def make_tenant(plan: Plan = Plan.PRO) -> Tenant:
    """建立測試用 Tenant 物件"""
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    tenant.name = "Test Corp"
    tenant.slug = "test-corp"
    tenant.plan = plan
    tenant.status = TenantStatus.ACTIVE
    tenant.created_at = datetime.now(tz=timezone.utc)
    tenant.updated_at = datetime.now(tz=timezone.utc)
    tenant.quotas = [
        make_quota("tokens",    PLAN_QUOTAS[plan]["tokens"],    used=0),
        make_quota("sandboxes", PLAN_QUOTAS[plan]["sandboxes"], used=0),
    ]
    return tenant


def make_quota(resource: str, limit: int, used: int = 0) -> TenantQuota:
    quota = MagicMock(spec=TenantQuota)
    quota.resource = resource
    quota.limit = limit
    quota.used = used
    quota.remaining = -1 if limit == -1 else max(0, limit - used)
    quota.is_exceeded = (limit != -1 and used >= limit)
    quota.reset_at = None
    return quota


# ─── 建立租戶 ────────────────────────────────────────────────

async def test_create_tenant_success() -> None:
    repo = make_mock_repo()
    repo.slug_exists.return_value = False
    repo.create.return_value = make_tenant(Plan.FREE)
    svc = TenantService(repo)

    tenant = await svc.create_tenant("Test Corp", "test-corp", Plan.FREE)

    repo.slug_exists.assert_awaited_once_with("test-corp")
    repo.create.assert_awaited_once_with(
        name="Test Corp", slug="test-corp", plan=Plan.FREE
    )
    assert tenant is not None


async def test_create_tenant_duplicate_slug_raises() -> None:
    repo = make_mock_repo()
    repo.slug_exists.return_value = True   # slug 已存在
    svc = TenantService(repo)

    with pytest.raises(SlugAlreadyExistsError, match="test-corp"):
        await svc.create_tenant("Test Corp", "test-corp", Plan.FREE)

    repo.create.assert_not_awaited()   # 不應呼叫 create


# ─── 查詢租戶 ────────────────────────────────────────────────

async def test_get_tenant_not_found_raises() -> None:
    repo = make_mock_repo()
    repo.get_by_id.return_value = None
    svc = TenantService(repo)

    with pytest.raises(TenantNotFoundError):
        await svc.get_tenant(uuid.uuid4())


# ─── 方案升降級 ───────────────────────────────────────────────

async def test_downgrade_fails_when_usage_exceeds_new_limit() -> None:
    """Pro → Free 降級，但 token 用量已超過 Free 上限"""
    repo = make_mock_repo()
    tenant = make_tenant(Plan.PRO)
    # 模擬已使用 500K tokens（超過 Free 的 100K 上限）
    tenant.quotas = [
        make_quota("tokens",    PLAN_QUOTAS[Plan.PRO]["tokens"], used=500_000),
        make_quota("sandboxes", PLAN_QUOTAS[Plan.PRO]["sandboxes"], used=1),
    ]
    repo.get_by_id.return_value = tenant
    svc = TenantService(repo)

    with pytest.raises(InvalidPlanDowngradeError):
        await svc.update_tenant(tenant.id, plan=Plan.FREE)


async def test_upgrade_always_succeeds() -> None:
    """Free → Pro 升級，用量不影響"""
    repo = make_mock_repo()
    tenant = make_tenant(Plan.FREE)
    repo.get_by_id.return_value = tenant
    repo.update.return_value = make_tenant(Plan.PRO)
    svc = TenantService(repo)

    result = await svc.update_tenant(tenant.id, plan=Plan.PRO)
    assert result.plan == Plan.PRO


# ─── 配額消耗 ─────────────────────────────────────────────────

async def test_consume_quota_success() -> None:
    repo = make_mock_repo()
    quota = make_quota("tokens", limit=1_000_000, used=400_000)
    repo.get_quota.return_value = quota
    repo.consume_quota.return_value = quota
    svc = TenantService(repo)

    result = await svc.consume_quota(uuid.uuid4(), "tokens", 1000)

    repo.consume_quota.assert_awaited_once()
    assert result is quota


async def test_consume_quota_exceeded_raises() -> None:
    repo = make_mock_repo()
    # 已使用 999_500，再扣 1000 會超過 1_000_000
    quota = make_quota("tokens", limit=1_000_000, used=999_500)
    repo.get_quota.return_value = quota
    svc = TenantService(repo)

    with pytest.raises(QuotaExceededError) as exc_info:
        await svc.consume_quota(uuid.uuid4(), "tokens", 1000)

    assert exc_info.value.resource == "tokens"
    assert exc_info.value.limit == 1_000_000
    repo.consume_quota.assert_not_awaited()   # 超量不應扣減


async def test_enterprise_quota_never_exceeded() -> None:
    """Enterprise 方案：limit=-1，任何用量都不超限"""
    repo = make_mock_repo()
    quota = make_quota("tokens", limit=-1, used=99_999_999)
    repo.get_quota.return_value = quota
    repo.consume_quota.return_value = quota
    svc = TenantService(repo)

    # 不應拋出例外
    result = await svc.consume_quota(uuid.uuid4(), "tokens", 9_999_999)
    assert result is quota


async def test_consume_quota_not_found_raises() -> None:
    repo = make_mock_repo()
    repo.get_quota.return_value = None
    svc = TenantService(repo)

    with pytest.raises(TenantNotFoundError):
        await svc.consume_quota(uuid.uuid4(), "tokens", 100)

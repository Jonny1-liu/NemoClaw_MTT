"""Sandbox Service 單元測試（不需要 DB、不需要 NemoClaw）"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox.adapters.mock_adapter import MockSandboxAdapter
from sandbox.models.sandbox import Sandbox, SandboxStatus
from sandbox.services.sandbox_service import (
    SandboxNotFoundError, SandboxNotStoppedError, SandboxService,
)
from sandbox.services.tenant_client import QuotaExceededError


def make_mock_repo():
    return AsyncMock()


def make_sandbox(status: SandboxStatus = SandboxStatus.RUNNING) -> Sandbox:
    sb = MagicMock(spec=Sandbox)
    sb.id          = uuid.uuid4()
    sb.tenant_id   = "tenant-test"
    sb.name        = "test-box"
    sb.status      = status
    sb.external_id = "mock-ext-id"
    sb.adapter     = "mock"
    sb.created_at  = datetime.now(tz=timezone.utc)
    sb.started_at  = datetime.now(tz=timezone.utc)
    sb.stopped_at  = None
    sb.error_message = None
    return sb


def make_service(repo=None, backend=None, tenant_client=None) -> SandboxService:
    return SandboxService(
        repo          = repo or make_mock_repo(),
        backend       = backend or MockSandboxAdapter(),
        tenant_client = tenant_client or AsyncMock(),
    )


# ─── 建立沙箱 ────────────────────────────────────────────────

async def test_create_sandbox_success() -> None:
    repo = make_mock_repo()
    sb   = make_sandbox(SandboxStatus.CREATING)
    repo.create.return_value = sb
    repo.set_running.return_value = sb

    svc = make_service(repo=repo)
    result = await svc.create_sandbox(
        tenant_id="tenant-test", name="test-box",
        inference_model="llama-3.1-70b", allow_domains=[],
    )
    repo.create.assert_awaited_once()
    repo.set_running.assert_awaited_once()
    assert result is sb


async def test_create_sandbox_quota_exceeded_cleans_up() -> None:
    repo = make_mock_repo()
    sb   = make_sandbox(SandboxStatus.CREATING)
    repo.create.return_value = sb

    tc = AsyncMock()
    tc.check_sandbox_quota.side_effect = QuotaExceededError(limit=1, used=1)

    svc = make_service(repo=repo, tenant_client=tc)
    with pytest.raises(QuotaExceededError):
        await svc.create_sandbox(
            tenant_id="tenant-test", name="test-box",
            inference_model="llama-3.1-70b", allow_domains=[],
        )
    # quota 超限時不應建立 DB 記錄
    repo.create.assert_not_awaited()


# ─── 查詢 / 列表 ─────────────────────────────────────────────

async def test_get_sandbox_not_found_raises() -> None:
    repo = make_mock_repo()
    repo.get.return_value = None
    svc  = make_service(repo=repo)

    with pytest.raises(SandboxNotFoundError):
        await svc.get_sandbox(uuid.uuid4(), "tenant-test")


async def test_list_sandboxes_returns_only_own_tenant() -> None:
    repo = make_mock_repo()
    sb1 = make_sandbox()
    repo.list_by_tenant.return_value = ([sb1], 1)
    svc  = make_service(repo=repo)

    items, total = await svc.list_sandboxes("tenant-test")
    repo.list_by_tenant.assert_awaited_once_with("tenant-test")
    assert total == 1
    assert items[0] is sb1


# ─── 停止 / 啟動 ──────────────────────────────────────────────

async def test_stop_running_sandbox() -> None:
    repo = make_mock_repo()
    sb   = make_sandbox(SandboxStatus.RUNNING)
    repo.get.return_value = sb
    repo.set_stopped.return_value = sb
    svc  = make_service(repo=repo)

    result = await svc.stop_sandbox(sb.id, "tenant-test")
    repo.set_stopped.assert_awaited_once_with(sb)
    assert result is sb


async def test_stop_already_stopped_raises() -> None:
    repo = make_mock_repo()
    sb   = make_sandbox(SandboxStatus.STOPPED)
    repo.get.return_value = sb
    svc  = make_service(repo=repo)

    with pytest.raises(SandboxNotStoppedError):
        await svc.stop_sandbox(sb.id, "tenant-test")


# ─── 刪除 ────────────────────────────────────────────────────

async def test_delete_running_sandbox_calls_destroy() -> None:
    backend = MockSandboxAdapter()
    backend.destroy = AsyncMock()
    repo    = make_mock_repo()
    sb      = make_sandbox(SandboxStatus.RUNNING)
    repo.get.return_value = sb
    svc     = make_service(repo=repo, backend=backend)

    await svc.delete_sandbox(sb.id, "tenant-test")
    backend.destroy.assert_awaited_once()
    repo.soft_delete.assert_awaited_once_with(sb)

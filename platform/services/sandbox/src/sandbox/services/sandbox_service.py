"""Sandbox Service — 業務邏輯層"""
import uuid

import structlog

from sandbox.adapters.mock_adapter import MockSandboxAdapter
from sandbox.models.sandbox import Sandbox, SandboxStatus
from sandbox.ports.sandbox_backend import (
    InferenceConfig, NetworkPolicy, SandboxBackend, SandboxHandle, SandboxSpec,
)
from sandbox.repositories.sandbox_repo import SandboxRepository
from sandbox.services.tenant_client import QuotaExceededError, TenantClient

log = structlog.get_logger()


class SandboxNotFoundError(Exception):
    pass

class SandboxNotStoppedError(Exception):
    pass


class SandboxService:

    def __init__(
        self,
        repo:          SandboxRepository,
        backend:       SandboxBackend,
        tenant_client: TenantClient,
    ) -> None:
        self._repo    = repo
        self._backend = backend
        self._tc      = tenant_client

    async def create_sandbox(
        self,
        tenant_id:       str,
        name:            str,
        inference_model: str,
        allow_domains:   list[str],
    ) -> Sandbox:
        log.info("sandbox.create", tenant_id=tenant_id, name=name)

        # 1. 配額前置檢查（呼叫 Tenant Service）
        await self._tc.check_sandbox_quota(tenant_id)

        # 2. 建立 DB 記錄（status: creating）
        sb = await self._repo.create(
            tenant_id=tenant_id, name=name,
            inference_model=inference_model,
            blueprint_config={"allow_domains": allow_domains},
        )

        # 3. 呼叫 Adapter 實際建立沙箱
        try:
            spec = SandboxSpec(
                tenant_id=tenant_id,
                sandbox_id=str(sb.id),
                name=name,
                inference_config=InferenceConfig(
                    endpoint="http://inference-gw:3003/v1",
                    model=inference_model,
                ),
                network_policy=NetworkPolicy(allow_domains=allow_domains),
            )
            handle: SandboxHandle = await self._backend.create(spec)

            # 4. 更新狀態為 running
            await self._repo.set_running(
                sb,
                external_id=handle.external_id,
                adapter=handle.adapter,
            )

            # 5. 非同步扣減配額（不影響主流程）
            try:
                await self._tc.consume_sandbox_quota(tenant_id)
            except Exception as e:
                log.warning("sandbox.quota_consume_failed", error=str(e))

        except QuotaExceededError:
            await self._repo.soft_delete(sb)
            raise
        except Exception as e:
            await self._repo.set_error(sb, str(e))
            raise

        log.info("sandbox.created", sandbox_id=str(sb.id), adapter=handle.adapter)
        return sb

    async def list_sandboxes(
        self, tenant_id: str
    ) -> tuple[list[Sandbox], int]:
        return await self._repo.list_by_tenant(tenant_id)

    async def get_sandbox(
        self, sandbox_id: uuid.UUID, tenant_id: str
    ) -> Sandbox:
        sb = await self._repo.get(sandbox_id, tenant_id)
        if not sb:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} not found")
        return sb

    async def stop_sandbox(
        self, sandbox_id: uuid.UUID, tenant_id: str
    ) -> Sandbox:
        sb = await self.get_sandbox(sandbox_id, tenant_id)
        if sb.status != SandboxStatus.RUNNING:
            raise SandboxNotStoppedError(
                f"Cannot stop sandbox in status '{sb.status}'"
            )
        handle = SandboxHandle(
            sandbox_id=str(sb.id),
            external_id=sb.external_id or "",
            adapter=sb.adapter,
        )
        await self._backend.stop(handle)
        await self._repo.set_stopped(sb)
        return sb

    async def start_sandbox(
        self, sandbox_id: uuid.UUID, tenant_id: str
    ) -> Sandbox:
        sb = await self.get_sandbox(sandbox_id, tenant_id)
        if sb.status != SandboxStatus.STOPPED:
            raise SandboxNotStoppedError(
                f"Cannot start sandbox in status '{sb.status}'"
            )
        handle = SandboxHandle(
            sandbox_id=str(sb.id),
            external_id=sb.external_id or "",
            adapter=sb.adapter,
        )
        await self._backend.start(handle)
        sb.status = SandboxStatus.RUNNING
        return sb

    async def delete_sandbox(
        self, sandbox_id: uuid.UUID, tenant_id: str, *, force: bool = False
    ) -> None:
        sb = await self.get_sandbox(sandbox_id, tenant_id)

        if sb.status == SandboxStatus.RUNNING:
            if not force:
                raise SandboxNotStoppedError(
                    f"Sandbox '{sb.name}' is currently running. "
                    "Stop it first, or use force=true to force delete."
                )
            # force=True：呼叫 NemoClaw destroy（成功後才更新 DB）
            handle = SandboxHandle(
                sandbox_id=str(sb.id),
                external_id=sb.external_id or "",
                adapter=sb.adapter,
            )
            await self._backend.destroy(handle)

        await self._repo.soft_delete(sb)

        # 釋放配額（刪除後 used - 1）
        try:
            await self._tc.release_sandbox_quota(tenant_id)
        except Exception as e:
            log.warning("sandbox.quota_release_failed", error=str(e))

        log.info("sandbox.deleted", sandbox_id=str(sandbox_id))

    async def update_network_policy(
        self, sandbox_id: uuid.UUID, tenant_id: str,
        allow_domains: list[str], deny_all_other: bool,
    ) -> Sandbox:
        sb = await self.get_sandbox(sandbox_id, tenant_id)
        policy = NetworkPolicy(
            allow_domains=allow_domains, deny_all_other=deny_all_other
        )
        handle = SandboxHandle(
            sandbox_id=str(sb.id),
            external_id=sb.external_id or "",
            adapter=sb.adapter,
        )
        await self._backend.apply_network_policy(handle, policy)
        await self._repo.save_policy(
            sb.id, {"allow_domains": allow_domains, "deny_all_other": deny_all_other}
        )
        return sb

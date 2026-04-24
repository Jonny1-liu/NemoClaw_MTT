"""Sandbox Repository — 所有 SQL 集中於此，每查必帶 tenant_id"""
import uuid
from datetime import datetime, timezone

from asyncpg.exceptions import UniqueViolationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sandbox.models.sandbox import NetworkPolicyRecord, Sandbox, SandboxStatus


class SandboxNameConflictError(Exception):
    """同一租戶內沙箱名稱重複"""
    pass


class SandboxRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ─── CRUD ────────────────────────────────────────────────

    async def create(
        self, *, tenant_id: str, name: str,
        inference_model: str, blueprint_config: dict,
    ) -> Sandbox:
        sb = Sandbox(
            tenant_id=tenant_id, name=name,
            inference_model=inference_model,
            blueprint_config=blueprint_config,
        )
        self._s.add(sb)
        try:
            await self._s.flush()
        except IntegrityError as e:
            await self._s.rollback()
            if "uix_sandbox_tenant_name" in str(e.orig):
                raise SandboxNameConflictError(
                    f"Sandbox name '{name}' already exists in this tenant"
                )
            raise
        return sb

    async def get(self, sandbox_id: uuid.UUID, tenant_id: str) -> Sandbox | None:
        """tenant_id 雙重過濾，確保跨租戶不可見"""
        result = await self._s.execute(
            select(Sandbox)
            .where(Sandbox.id == sandbox_id)
            .where(Sandbox.tenant_id == tenant_id)      # ← 不能省
            .where(Sandbox.status != SandboxStatus.DELETED)
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Sandbox], int]:
        base = (
            select(Sandbox)
            .where(Sandbox.tenant_id == tenant_id)      # ← 不能省
            .where(Sandbox.status != SandboxStatus.DELETED)
        )
        total_result = await self._s.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = total_result.scalar_one()

        items_result = await self._s.execute(
            base.order_by(Sandbox.created_at.desc()).limit(limit).offset(offset)
        )
        return list(items_result.scalars()), total

    async def count_active(self, tenant_id: str) -> int:
        """計算目前 running + creating 的沙箱數（用於配額前置檢查）"""
        result = await self._s.execute(
            select(func.count())
            .where(Sandbox.tenant_id == tenant_id)
            .where(Sandbox.status.in_([SandboxStatus.RUNNING, SandboxStatus.CREATING]))
        )
        return result.scalar_one()

    # ─── 狀態更新 ─────────────────────────────────────────────

    async def set_running(
        self, sb: Sandbox, *, external_id: str, adapter: str
    ) -> Sandbox:
        sb.status      = SandboxStatus.RUNNING
        sb.external_id = external_id
        sb.adapter     = adapter
        sb.started_at  = datetime.now(tz=timezone.utc)
        return sb

    async def set_stopped(self, sb: Sandbox) -> Sandbox:
        sb.status     = SandboxStatus.STOPPED
        sb.stopped_at = datetime.now(tz=timezone.utc)
        return sb

    async def set_error(self, sb: Sandbox, message: str) -> Sandbox:
        sb.status        = SandboxStatus.ERROR
        sb.error_message = message
        return sb

    async def soft_delete(self, sb: Sandbox) -> Sandbox:
        sb.status = SandboxStatus.DELETED
        return sb

    # ─── 網路政策 ─────────────────────────────────────────────

    async def save_policy(
        self, sandbox_id: uuid.UUID, policy_config: dict
    ) -> NetworkPolicyRecord:
        record = NetworkPolicyRecord(
            sandbox_id=sandbox_id,
            policy_config=policy_config,
            applied_at=datetime.now(tz=timezone.utc),
        )
        self._s.add(record)
        return record

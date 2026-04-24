"""
Mock Adapter — 本機開發 / Windows / Unit Test 專用

不需要 NemoClaw、Docker、k3s。
所有操作回傳假資料，讓平台其他服務可以在任何環境開發和測試。

切換方式：設定環境變數 SANDBOX_BACKEND=mock
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import structlog

from sandbox.ports.sandbox_backend import (
    LogLine,
    NetworkPolicy,
    SandboxBackend,
    SandboxHandle,
    SandboxPhase,
    SandboxSpec,
    SandboxStatus,
    SnapshotRef,
)

log = structlog.get_logger()


class MockSandboxAdapter(SandboxBackend):
    """
    完整模擬沙箱行為，包含非同步延遲，
    讓上層服務的非同步邏輯可以被真實測試。
    """

    def __init__(self) -> None:
        self._sandboxes: dict[str, SandboxPhase] = {}
        log.info("mock_adapter.initialized", note="NemoClaw NOT used")

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        log.info("mock.create", sandbox_id=spec.sandbox_id, tenant=spec.tenant_id)

        self._sandboxes[spec.sandbox_id] = SandboxPhase.CREATING
        await asyncio.sleep(0.1)   # 模擬建立延遲（真實環境約 30-60 秒）
        self._sandboxes[spec.sandbox_id] = SandboxPhase.RUNNING

        return SandboxHandle(
            sandbox_id=spec.sandbox_id,
            external_id=f"mock-{spec.sandbox_id}",
            adapter="mock",
        )

    async def stop(self, handle: SandboxHandle) -> None:
        log.info("mock.stop", sandbox_id=handle.sandbox_id)
        self._sandboxes[handle.sandbox_id] = SandboxPhase.STOPPED

    async def start(self, handle: SandboxHandle) -> None:
        log.info("mock.start", sandbox_id=handle.sandbox_id)
        self._sandboxes[handle.sandbox_id] = SandboxPhase.RUNNING

    async def destroy(self, handle: SandboxHandle) -> None:
        log.info("mock.destroy", sandbox_id=handle.sandbox_id)
        self._sandboxes.pop(handle.sandbox_id, None)

    async def get_status(self, handle: SandboxHandle) -> SandboxStatus:
        phase = self._sandboxes.get(handle.sandbox_id, SandboxPhase.ERROR)
        return SandboxStatus(
            phase=phase,
            started_at=datetime.now(tz=timezone.utc) if phase == SandboxPhase.RUNNING else None,
        )

    async def stream_logs(
        self, handle: SandboxHandle, *, tail: int = 100
    ) -> AsyncIterator[LogLine]:
        mock_lines = [
            "[MOCK] OpenClaw agent initializing...",
            "[MOCK] Loading inference config...",
            "[MOCK] Agent ready.",
        ]
        for msg in mock_lines:
            yield LogLine(
                timestamp=datetime.now(tz=timezone.utc),
                level="info",
                message=msg,
            )
            await asyncio.sleep(0.05)

    async def apply_network_policy(
        self, handle: SandboxHandle, policy: NetworkPolicy
    ) -> None:
        log.info(
            "mock.apply_policy",
            sandbox_id=handle.sandbox_id,
            allow_count=len(policy.allow_domains),
        )

    async def create_snapshot(self, handle: SandboxHandle) -> SnapshotRef:
        ref = SnapshotRef(
            snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(tz=timezone.utc),
            size_bytes=1024,
        )
        log.info("mock.snapshot_created", ref=ref.snapshot_id)
        return ref

    async def restore_snapshot(
        self, handle: SandboxHandle, ref: SnapshotRef
    ) -> None:
        log.info("mock.snapshot_restored", ref=ref.snapshot_id)
        self._sandboxes[handle.sandbox_id] = SandboxPhase.RUNNING

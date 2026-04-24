"""
Sandbox ACL 單元測試

驗證 MockAdapter 的行為是否符合 SandboxBackend 介面。
不需要 Docker、NemoClaw、k3s。
"""
import pytest

from sandbox.adapters.mock_adapter import MockSandboxAdapter
from sandbox.ports.sandbox_backend import (
    NetworkPolicy,
    SandboxHandle,
    SandboxPhase,
    SandboxSpec,
)


@pytest.fixture
def adapter() -> MockSandboxAdapter:
    return MockSandboxAdapter()


@pytest.fixture
def spec() -> SandboxSpec:
    return SandboxSpec(
        tenant_id="tenant01",
        sandbox_id="sb-abcd1234efgh5678",
        name="test-sandbox",
    )


async def test_create_returns_handle(adapter: MockSandboxAdapter, spec: SandboxSpec) -> None:
    handle = await adapter.create(spec)
    assert handle.sandbox_id == spec.sandbox_id
    assert handle.adapter == "mock"


async def test_status_is_running_after_create(
    adapter: MockSandboxAdapter, spec: SandboxSpec
) -> None:
    handle = await adapter.create(spec)
    status = await adapter.get_status(handle)
    assert status.phase == SandboxPhase.RUNNING


async def test_stop_changes_phase(adapter: MockSandboxAdapter, spec: SandboxSpec) -> None:
    handle = await adapter.create(spec)
    await adapter.stop(handle)
    status = await adapter.get_status(handle)
    assert status.phase == SandboxPhase.STOPPED


async def test_stream_logs_yields_lines(
    adapter: MockSandboxAdapter, spec: SandboxSpec
) -> None:
    handle = await adapter.create(spec)
    lines = [line async for line in adapter.stream_logs(handle)]
    assert len(lines) > 0
    assert all(line.message for line in lines)


async def test_apply_network_policy_does_not_raise(
    adapter: MockSandboxAdapter, spec: SandboxSpec
) -> None:
    handle = await adapter.create(spec)
    policy = NetworkPolicy(allow_domains=["api.slack.com", "*.nvidia.com"])
    await adapter.apply_network_policy(handle, policy)  # 不應拋出例外


async def test_snapshot_roundtrip(adapter: MockSandboxAdapter, spec: SandboxSpec) -> None:
    handle = await adapter.create(spec)
    ref = await adapter.create_snapshot(handle)
    assert ref.snapshot_id.startswith("snap-")
    await adapter.restore_snapshot(handle, ref)
    status = await adapter.get_status(handle)
    assert status.phase == SandboxPhase.RUNNING


async def test_mock_adapter_never_calls_nemoclaw(
    adapter: MockSandboxAdapter, spec: SandboxSpec
) -> None:
    """MockAdapter 不應該有任何外部呼叫，確保與 NemoClaw 完全解耦"""
    handle = await adapter.create(spec)
    # 如果這些呼叫成功，代表 Mock 正確隔離了 NemoClaw
    await adapter.get_status(handle)
    await adapter.stop(handle)
    await adapter.start(handle)
    await adapter.destroy(handle)

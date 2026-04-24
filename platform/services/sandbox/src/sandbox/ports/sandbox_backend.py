"""
Sandbox Backend — Anti-Corruption Layer (ACL) 核心介面

這是平台與 NemoClaw 之間的唯一邊界。
平台所有程式碼只能透過這個 Protocol 與沙箱溝通，
絕對不允許直接呼叫 NemoClaw CLI 或 OpenShell API。

NemoClaw 升版時，只需修改 adapters/nemoclaw_adapter.py，
其他所有服務完全不受影響。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator


# ─── 我們的領域模型（與 NemoClaw 內部格式無關）──────────────────


class SandboxPhase(str, Enum):
    CREATING = "creating"
    RUNNING  = "running"
    STOPPING = "stopping"
    STOPPED  = "stopped"
    ERROR    = "error"


@dataclass
class ResourceRequirements:
    cpu:    str = "500m"   # Kubernetes 格式
    memory: str = "512Mi"


@dataclass
class InferenceConfig:
    """沙箱內的推理設定 — 指向我們的 Inference Gateway，不直接呼叫外部 LLM"""
    endpoint: str          # 例如 http://inference-gw:3003/v1
    model:    str = "llama-3.1-70b"


@dataclass
class NetworkPolicy:
    allow_domains: list[str] = field(default_factory=list)
    deny_all_other: bool = True


@dataclass
class SandboxSpec:
    """建立沙箱時的完整規格（我們的語言，非 NemoClaw 的語言）"""
    tenant_id:        str
    sandbox_id:       str
    name:             str
    resources:        ResourceRequirements = field(default_factory=ResourceRequirements)
    inference_config: InferenceConfig | None = None
    network_policy:   NetworkPolicy = field(default_factory=NetworkPolicy)


@dataclass
class SandboxHandle:
    """建立後的沙箱參考（含 Adapter 識別，供 ACL 內部使用）"""
    sandbox_id:  str
    external_id: str        # Pod / sandbox 名稱（乾淨，無前綴）
    adapter:     str        # "k8s" | "openshell" | "mock"
    namespace:   str = ""   # K8sAdapter 使用：tenant-{tenant_id}


@dataclass
class SandboxStatus:
    phase:      SandboxPhase
    started_at: datetime | None = None
    error_msg:  str | None = None


@dataclass
class LogLine:
    timestamp: datetime
    level:     str
    message:   str
    source:    str = "sandbox"


@dataclass
class SnapshotRef:
    snapshot_id: str
    created_at:  datetime
    size_bytes:  int = 0


# ─── 抽象介面（所有 Adapter 必須實作）──────────────────────────

class SandboxBackend(ABC):
    """
    所有與沙箱相關的操作都透過此介面。
    平台其他服務只能看到這個介面，看不到任何 NemoClaw 細節。
    """

    @abstractmethod
    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        """建立並啟動沙箱（非同步，可能需要 30-60 秒）"""
        ...

    @abstractmethod
    async def stop(self, handle: SandboxHandle) -> None:
        """優雅停止沙箱（保留狀態）"""
        ...

    @abstractmethod
    async def start(self, handle: SandboxHandle) -> None:
        """從 stopped 狀態重新啟動"""
        ...

    @abstractmethod
    async def destroy(self, handle: SandboxHandle) -> None:
        """永久銷毀沙箱及其所有資源"""
        ...

    @abstractmethod
    async def get_status(self, handle: SandboxHandle) -> SandboxStatus:
        """查詢沙箱當前狀態"""
        ...

    @abstractmethod
    async def stream_logs(
        self, handle: SandboxHandle, *, tail: int = 100
    ) -> AsyncIterator[LogLine]:
        """串流日誌（async generator）"""
        ...

    @abstractmethod
    async def apply_network_policy(
        self, handle: SandboxHandle, policy: NetworkPolicy
    ) -> None:
        """動態更新網路政策（不重啟沙箱）"""
        ...

    @abstractmethod
    async def create_snapshot(self, handle: SandboxHandle) -> SnapshotRef:
        """建立沙箱狀態快照"""
        ...

    @abstractmethod
    async def restore_snapshot(
        self, handle: SandboxHandle, ref: SnapshotRef
    ) -> None:
        """從快照還原沙箱狀態"""
        ...

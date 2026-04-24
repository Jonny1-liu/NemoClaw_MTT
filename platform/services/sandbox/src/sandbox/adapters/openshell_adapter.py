"""
OpenShell Adapter — 透過 openshell CLI 管理沙箱

架構說明：
  NemoClaw onboard（一次性）→ 建立 OpenShell Gateway（Docker + k3s）
  OpenShell Adapter（日常）  → 呼叫 openshell CLI 管理 Sandbox CRD
                              → agent-sandbox-controller 監聽 CRD 建立 Pod

沙箱命名規則（確保多租戶唯一性）：
  格式：t-{tenant_id_前8碼}-{sandbox_name}
  範例：t-9bc7f337-my-assistant

切換方式：SANDBOX_BACKEND=openshell
"""
import asyncio
import json
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
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

# K8s 名稱只能有小寫英數字與連字號，且不能以連字號開頭/結尾
_K8S_NAME_RE = re.compile(r"[^a-z0-9-]")


def _sanitize(s: str) -> str:
    return _K8S_NAME_RE.sub("-", s.lower())


class OpenShellAdapter(SandboxBackend):
    """
    使用 openshell CLI 管理沙箱生命週期。
    openshell binary 必須在 PATH 中，且 gateway 必須已由 NemoClaw onboard 建立。
    """

    def __init__(
        self,
        sandbox_image: str = "openclaw",
        gateway_endpoint: str | None = None,
    ) -> None:
        """
        sandbox_image: openshell --from 的值（community name 或 image reference）
        gateway_endpoint: OpenShell gateway URL（空則使用 openshell 已儲存的 gateway）
        """
        self._image = sandbox_image
        self._endpoint = gateway_endpoint
        log.info("openshell_adapter.initialized",
                 image=sandbox_image, endpoint=gateway_endpoint)

    # ─── 名稱工具 ──────────────────────────────────────────────

    def _make_name(self, tenant_id: str, sandbox_name: str) -> str:
        """
        產生全域唯一的 K8s 名稱
        格式：t-{tenant_id 前8碼}-{sandbox_name}
        最長 63 字元（K8s Pod name 限制）
        """
        tenant_prefix = _sanitize(tenant_id[:8])
        name = _sanitize(sandbox_name)
        result = f"t-{tenant_prefix}-{name}"
        return result[:63].rstrip("-")

    def _gateway_args(self) -> list[str]:
        if self._endpoint:
            return ["--gateway-endpoint", self._endpoint]
        return []   # 使用 openshell 已儲存的 gateway 設定

    # ─── 生命週期 ──────────────────────────────────────────────

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        name = self._make_name(spec.tenant_id, spec.name)
        log.info("openshell.create", name=name, tenant=spec.tenant_id)

        cmd = [
            "openshell", "sandbox", "create",
            "--name",         name,
            "--from",         self._image,   # "openclaw" or custom image
            "--no-bootstrap",                 # gateway 必須已存在
            "--no-auto-providers",            # 不自動建立 provider
            "--no-tty",                       # 非互動模式
        ]

        # 加入網路政策（如有自訂）
        if spec.network_policy and spec.network_policy.allow_domains:
            policy_path = await self._write_policy_yaml(spec.network_policy, name)
            cmd += ["--policy", str(policy_path)]

        cmd += self._gateway_args()

        await self._run(cmd)
        log.info("openshell.created", name=name)

        return SandboxHandle(
            sandbox_id=spec.sandbox_id,
            external_id=name,
            adapter="openshell",
        )

    async def stop(self, handle: SandboxHandle) -> None:
        """
        OpenShell 沒有 pause/stop 概念，sandbox 持續運行直到刪除。
        此方法目前為 no-op（不操作）。
        未來可透過 openshell sandbox exec 終止主程序。
        """
        log.info("openshell.stop_noop", name=handle.external_id,
                 note="openshell has no stop command; sandbox continues running")

    async def start(self, handle: SandboxHandle) -> None:
        """同 stop，目前為 no-op。"""
        log.info("openshell.start_noop", name=handle.external_id)

    async def destroy(self, handle: SandboxHandle) -> None:
        log.info("openshell.destroy", name=handle.external_id)
        cmd = ["openshell", "sandbox", "delete", handle.external_id,
               "--yes"]   # 跳過確認提示
        cmd += self._gateway_args()
        await self._run(cmd)
        log.info("openshell.destroyed", name=handle.external_id)

    # ─── 狀態查詢 ──────────────────────────────────────────────

    async def get_status(self, handle: SandboxHandle) -> SandboxStatus:
        cmd = ["openshell", "sandbox", "get", handle.external_id,
               "--output", "json"]
        cmd += self._gateway_args()
        try:
            stdout = await self._run(cmd)
            return self._parse_status(stdout)
        except RuntimeError:
            return SandboxStatus(phase=SandboxPhase.ERROR,
                                 error_msg="Failed to get status")

    def _parse_status(self, stdout: str) -> SandboxStatus:
        """解析 openshell sandbox get --output json 的輸出"""
        try:
            data = json.loads(stdout)
            phase_map = {
                "Ready":   SandboxPhase.RUNNING,
                "Pending": SandboxPhase.CREATING,
                "Error":   SandboxPhase.ERROR,
            }
            phase_str = data.get("phase", data.get("status", ""))
            phase = phase_map.get(phase_str, SandboxPhase.ERROR)
            return SandboxStatus(
                phase=phase,
                started_at=datetime.now(tz=timezone.utc) if phase == SandboxPhase.RUNNING else None,
            )
        except (json.JSONDecodeError, KeyError):
            # 若輸出不是 JSON，嘗試從文字判斷
            if "Ready" in stdout:
                return SandboxStatus(phase=SandboxPhase.RUNNING,
                                     started_at=datetime.now(tz=timezone.utc))
            return SandboxStatus(phase=SandboxPhase.ERROR,
                                 error_msg=f"Unexpected output: {stdout[:200]}")

    # ─── 日誌串流 ──────────────────────────────────────────────

    async def stream_logs(
        self, handle: SandboxHandle, *, tail: int = 100
    ) -> AsyncIterator[LogLine]:
        """
        透過 openshell sandbox exec 取得日誌。
        TODO: 實作真正的日誌串流（可能需要 SSH 或 exec）
        """
        log.info("openshell.stream_logs", name=handle.external_id)
        yield LogLine(
            timestamp=datetime.now(tz=timezone.utc),
            level="info",
            message=f"[openshell] Sandbox {handle.external_id} is running",
        )

    # ─── 網路政策 ──────────────────────────────────────────────

    async def apply_network_policy(
        self, handle: SandboxHandle, policy: NetworkPolicy
    ) -> None:
        """
        更新網路政策並同步至沙箱。
        TODO: openshell 目前支援 --policy 參數在 create 時設定，
              動態更新需要進一步研究 OpenShell gRPC API。
        """
        log.info("openshell.apply_policy",
                 name=handle.external_id,
                 allow_count=len(policy.allow_domains))
        policy_path = await self._write_policy_yaml(policy, handle.external_id)
        log.info("openshell.policy_written", path=str(policy_path),
                 note="Dynamic policy update TODO")

    async def _write_policy_yaml(
        self, policy: NetworkPolicy, sandbox_name: str
    ) -> Path:
        """將 NetworkPolicy 寫成 openshell policy YAML 檔案"""
        # openshell policy YAML 格式（依官方文件）
        allowed = "\n".join(
            f"  - {domain}" for domain in policy.allow_domains
        )
        yaml_content = f"""# Auto-generated policy for sandbox: {sandbox_name}
network:
  egress:
    allowed_domains:
{allowed if allowed else "    []"}
    deny_all_other: {str(policy.deny_all_other).lower()}
"""
        tmp = Path(tempfile.mktemp(suffix=".yaml", prefix=f"policy-{sandbox_name}-"))
        tmp.write_text(yaml_content)
        return tmp

    # ─── 快照 ──────────────────────────────────────────────────

    async def create_snapshot(self, handle: SandboxHandle) -> SnapshotRef:
        """
        使用 openshell sandbox download 下載沙箱工作目錄作為快照。
        TODO: 實作完整快照流程（下載 → 壓縮 → 上傳至 S3）
        """
        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        log.info("openshell.snapshot_todo", name=handle.external_id,
                 snapshot_id=snapshot_id)
        return SnapshotRef(
            snapshot_id=snapshot_id,
            created_at=datetime.now(tz=timezone.utc),
            size_bytes=0,
        )

    async def restore_snapshot(
        self, handle: SandboxHandle, ref: SnapshotRef
    ) -> None:
        """
        使用 openshell sandbox upload 還原快照。
        TODO: 實作完整還原流程（從 S3 下載 → 上傳至沙箱）
        """
        log.info("openshell.restore_todo",
                 name=handle.external_id, snapshot_id=ref.snapshot_id)

    # ─── 內部工具 ──────────────────────────────────────────────

    async def _run(self, args: list[str]) -> str:
        cmd_str = " ".join(args)
        log.debug("openshell.exec", cmd=cmd_str)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode().strip()
            log.error("openshell.exec_failed",
                      cmd=cmd_str, returncode=proc.returncode, stderr=error_msg)
            raise RuntimeError(
                f"openshell command failed: {' '.join(args[:3])}\n"
                f"stderr: {error_msg}"
            )

        return stdout.decode()

"""
NemoClaw Adapter — 對接真實 NemoClaw CLI

這是 ACL（Anti-Corruption Layer）的實作層。
所有 NemoClaw 版本相關的翻譯邏輯都集中在這裡。
NemoClaw 升版 → 只改這個檔案。

使用條件：
  - Linux / Ubuntu 環境
  - 已安裝 NemoClaw（NEMOCLAW_BIN 路徑正確）
  - Docker + OpenShell 正常運作

切換方式：設定環境變數 SANDBOX_BACKEND=nemoclaw
"""
import asyncio
import json
import shutil
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


class NemoclawAdapter(SandboxBackend):
    """
    透過 NemoClaw CLI 管理沙箱。

    ── 版本對應 ───────────────────────────────────────────────
    當前對應版本：NemoClaw Alpha（2026-03 ~ ）
    若 NemoClaw 升版導致 CLI 格式改變，只需更新：
      1. _spec_to_blueprint_args()   ← Blueprint 參數翻譯
      2. _parse_status_output()      ← 狀態輸出解析
      3. _policy_to_yaml()           ← 網路政策格式翻譯
    ────────────────────────────────────────────────────────────
    """

    def __init__(self, nemoclaw_bin: str = "nemoclaw") -> None:
        if not shutil.which(nemoclaw_bin):
            raise RuntimeError(
                f"NemoClaw binary not found at '{nemoclaw_bin}'. "
                "Please install NemoClaw or use SANDBOX_BACKEND=mock."
            )
        self._bin = nemoclaw_bin
        log.info("nemoclaw_adapter.initialized", bin=nemoclaw_bin)

    # ─── 生命週期 ────────────────────────────────────────────

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        """
        呼叫：nemoclaw sandbox create --name <name> [--blueprint ...]
        TODO: 等 NemoClaw API 穩定後完善參數格式
        """
        args = self._spec_to_create_args(spec)
        await self._run(args)
        return SandboxHandle(
            sandbox_id=spec.sandbox_id,
            external_id=spec.name,   # NemoClaw 用 name 識別
            adapter="nemoclaw",
        )

    async def stop(self, handle: SandboxHandle) -> None:
        await self._run(["sandbox", "stop", handle.external_id])

    async def start(self, handle: SandboxHandle) -> None:
        await self._run(["sandbox", "start", handle.external_id])

    async def destroy(self, handle: SandboxHandle) -> None:
        await self._run(["sandbox", "destroy", handle.external_id, "--yes"])

    async def get_status(self, handle: SandboxHandle) -> SandboxStatus:
        stdout = await self._run(["sandbox", "status", handle.external_id, "--json"])
        return self._parse_status_output(stdout)

    async def stream_logs(
        self, handle: SandboxHandle, *, tail: int = 100
    ) -> AsyncIterator[LogLine]:
        proc = await asyncio.create_subprocess_exec(
            self._bin, handle.external_id, "logs", "--follow",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        async for raw in proc.stdout:
            yield LogLine(
                timestamp=datetime.now(tz=timezone.utc),
                level="info",
                message=raw.decode().rstrip(),
            )

    async def apply_network_policy(
        self, handle: SandboxHandle, policy: NetworkPolicy
    ) -> None:
        # TODO: 確認 NemoClaw 動態政策更新的 CLI 格式
        policy_yaml = self._policy_to_yaml(policy)
        await self._run(["policy", "apply", "--sandbox", handle.external_id,
                         "--inline", policy_yaml])

    async def create_snapshot(self, handle: SandboxHandle) -> SnapshotRef:
        # TODO: 確認 NemoClaw snapshot CLI
        stdout = await self._run(["sandbox", "snapshot", handle.external_id, "--json"])
        data = json.loads(stdout)
        return SnapshotRef(
            snapshot_id=data["snapshot_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            size_bytes=data.get("size_bytes", 0),
        )

    async def restore_snapshot(
        self, handle: SandboxHandle, ref: SnapshotRef
    ) -> None:
        await self._run(["sandbox", "restore", handle.external_id,
                         "--snapshot", ref.snapshot_id])

    # ─── 翻譯方法（NemoClaw 版本升級時只改這區）────────────────

    def _spec_to_create_args(self, spec: SandboxSpec) -> list[str]:
        """
        將 SandboxSpec（我們的模型）翻譯成 NemoClaw CLI 參數。
        NemoClaw Alpha 目前的 CLI 格式（待確認正式 API 後更新）：
          nemoclaw onboard → 互動式，不適合程式呼叫
          nemoclaw sandbox create --name <name>
        """
        args = ["sandbox", "create", "--name", spec.name]
        # TODO: 加入 blueprint、inference endpoint 等參數
        # args += ["--blueprint", self._generate_blueprint_yaml(spec)]
        return args

    def _parse_status_output(self, stdout: str) -> SandboxStatus:
        """解析 NemoClaw status --json 輸出"""
        try:
            data = json.loads(stdout)
            phase_map = {
                "running": SandboxPhase.RUNNING,
                "stopped": SandboxPhase.STOPPED,
                "creating": SandboxPhase.CREATING,
                "error": SandboxPhase.ERROR,
            }
            return SandboxStatus(
                phase=phase_map.get(data.get("status", ""), SandboxPhase.ERROR),
                started_at=datetime.fromisoformat(data["started_at"])
                           if data.get("started_at") else None,
                error_msg=data.get("error"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            log.error("nemoclaw.parse_status_failed", error=str(e), raw=stdout)
            return SandboxStatus(phase=SandboxPhase.ERROR, error_msg=str(e))

    def _policy_to_yaml(self, policy: NetworkPolicy) -> str:
        """翻譯 NetworkPolicy → NemoClaw YAML 格式"""
        lines = ["allow:"]
        for domain in policy.allow_domains:
            lines.append(f"  - domain: {domain}")
            lines.append("    ports: [443]")
        if policy.deny_all_other:
            lines.append("deny_all_other: true")
        return "\n".join(lines)

    # ─── 內部工具 ────────────────────────────────────────────

    async def _run(self, args: list[str]) -> str:
        cmd = [self._bin, *args]
        log.debug("nemoclaw.exec", cmd=" ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f"NemoClaw command failed: {' '.join(args)}\n"
                f"stderr: {stderr.decode()}"
            )
        return stdout.decode()

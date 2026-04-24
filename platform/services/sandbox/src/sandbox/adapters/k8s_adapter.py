"""
K8sAdapter — 透過 k3s（OpenShell 容器內部）實現真正的多租戶隔離

架構：
  我們的服務 → Docker Python SDK → docker exec → kubectl → k3s

隔離方式：
  每個 Tenant 有獨立的 K8s Namespace（tenant-{tenant_id}）
  Sandbox 名稱就是用戶設定的名稱，完全乾淨，無前綴

  tenant-abc123/
    ├── Pod: my-assistant        ← 乾淨名稱
    ├── PVC: workspace-my-assistant
    └── ResourceQuota

  tenant-def456/
    └── Pod: my-assistant        ← 同名但完全隔離！

切換方式：SANDBOX_BACKEND=k8s
"""
import asyncio
import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import structlog

# K8s 名稱只能有小寫英數字與連字號
_K8S_NAME_RE = re.compile(r"[^a-z0-9-]")


def _sanitize(s: str) -> str:
    """將字串轉為 K8s 合法名稱格式"""
    return _K8S_NAME_RE.sub("-", s.lower())

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

# OpenShell cluster Docker 容器名稱的匹配字串
_CONTAINER_PATTERN = "openshell-cluster"

# Sandbox Pod 映像（啟動時從 asus-claw pod 動態偵測，無需在 NemoClaw 升版時修改）
_SANDBOX_IMAGE_FALLBACK = "openshell/sandbox-from:latest"

# OpenShell gRPC endpoint（容器內 k3s 的 Service DNS）
_OPENSHELL_ENDPOINT = "https://openshell.openshell.svc.cluster.local:8080"

# OpenShell 的 TLS Secret 名稱（在 openshell namespace）
_TLS_SECRET_NAME = "openshell-client-tls"
_OPENSHELL_NS    = "openshell"


class K8sAdapter(SandboxBackend):
    """
    使用 k3s K8s API 建立 Namespace-per-Tenant 的真正多租戶隔離。
    透過 docker exec 在 OpenShell 容器內執行 kubectl 指令。
    """

    def __init__(self, container_pattern: str = _CONTAINER_PATTERN) -> None:
        import docker
        self._docker = docker.from_env()
        self._container = self._find_container(container_pattern)
        # 動態偵測 sandbox 映像，跟著 NemoClaw 版本走
        self._sandbox_image = self._detect_sandbox_image()
        log.info("k8s_adapter.initialized",
                 container=self._container.name,
                 sandbox_image=self._sandbox_image)

    def _find_container(self, pattern: str):
        for c in self._docker.containers.list():
            if pattern in c.name and c.status == "running":
                log.info("k8s_adapter.container_found", name=c.name)
                return c
        raise RuntimeError(
            f"No running container matching '{pattern}'. "
            "Is NemoClaw/OpenShell installed and running?"
        )

    def _detect_sandbox_image(self) -> str:
        """
        從 asus-claw（OpenShell 的初始 sandbox）動態取得映像版本。
        NemoClaw 升版時映像 tag 會改變，這樣不需要手動修改程式碼。
        """
        try:
            result = self._container.exec_run(
                ["kubectl", "get", "pod", "asus-claw", "-n", "openshell",
                 "-o", "jsonpath={.spec.containers[0].image}"],
                user="root", demux=True,
            )
            image = result.output[0].decode().strip() if result.output[0] else ""
            if image:
                log.info("k8s_adapter.image_detected", image=image)
                return image
        except Exception as e:
            log.warning("k8s_adapter.image_detect_failed", error=str(e))
        log.warning("k8s_adapter.using_fallback_image", image=_SANDBOX_IMAGE_FALLBACK)
        return _SANDBOX_IMAGE_FALLBACK

    # ─── 生命週期 ──────────────────────────────────────────────

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        """
        呼叫 openshell sandbox create 建立 sandbox。
        這是唯一能正確向 OpenShell gateway 登記 sandbox spec 的方式。

        執行步驟：
          openshell sandbox create --name <crd_name> -- /bin/true
          → gateway 登記 sandbox spec
          → controller 建立 Pod
          → /bin/true 立即退出，sandbox 繼續在背景運行
        """
        crd_name = self._make_crd_name(spec.tenant_id, spec.name)
        log.info("k8s.create", crd_name=crd_name, tenant=spec.tenant_id)

        cmd = [
            "openshell", "sandbox", "create",
            "--name", crd_name,
            "--no-bootstrap",
            "--no-auto-providers",
            "--no-tty",
            "--", "/bin/true",   # 立即退出，sandbox 持續在背景運行
        ]
        await self._run_host(cmd)

        # 等待 openshell sandbox 進入 Ready 狀態
        await self._wait_openshell_ready(crd_name, timeout=120)

        log.info("k8s.created", crd_name=crd_name)
        return SandboxHandle(
            sandbox_id=spec.sandbox_id,
            external_id=crd_name,
            adapter="k8s",
            namespace=_OPENSHELL_NS,
        )

    async def stop(self, handle: SandboxHandle) -> None:
        """
        K8s 沒有 pause 概念。
        可以縮減 Pod replicas 至 0，或直接讓 Pod 繼續運行。
        目前實作為 no-op，Pod 保持運行。
        """
        log.info("k8s.stop_noop", pod=handle.external_id)

    async def start(self, handle: SandboxHandle) -> None:
        log.info("k8s.start_noop", pod=handle.external_id)

    async def destroy(self, handle: SandboxHandle) -> None:
        """使用 openshell sandbox delete 刪除 sandbox"""
        crd_name = handle.external_id
        log.info("k8s.destroy", crd_name=crd_name)
        await self._run_host(["openshell", "sandbox", "delete", crd_name, "--yes"])
        log.info("k8s.destroyed", crd_name=crd_name)

    # ─── 狀態查詢 ──────────────────────────────────────────────

    async def get_status(self, handle: SandboxHandle) -> SandboxStatus:
        """透過 Sandbox CRD 狀態查詢"""
        try:
            out = await self._kubectl(
                f"get sandbox {handle.external_id} -n {_OPENSHELL_NS} -o json"
            )
            return self._parse_sandbox_crd_status(out)
        except RuntimeError:
            return SandboxStatus(phase=SandboxPhase.ERROR,
                                 error_msg="Sandbox CRD not found")

    def _parse_sandbox_crd_status(self, crd_json: str) -> SandboxStatus:
        try:
            crd = json.loads(crd_json)
            conditions = crd.get("status", {}).get("conditions", [])
            for cond in conditions:
                if cond.get("type") == "Ready" and cond.get("status") == "True":
                    return SandboxStatus(
                        phase=SandboxPhase.RUNNING,
                        started_at=datetime.now(tz=timezone.utc),
                    )
            return SandboxStatus(phase=SandboxPhase.CREATING)
        except (json.JSONDecodeError, KeyError) as e:
            return SandboxStatus(phase=SandboxPhase.ERROR, error_msg=str(e))

    # ─── 日誌串流 ──────────────────────────────────────────────

    async def stream_logs(
        self, handle: SandboxHandle, *, tail: int = 100
    ) -> AsyncIterator[LogLine]:
        namespace = self._handle_namespace(handle)
        try:
            out = await self._kubectl(
                f"logs {handle.external_id} -n {namespace} --tail={tail}"
            )
            for line in out.splitlines():
                yield LogLine(
                    timestamp=datetime.now(tz=timezone.utc),
                    level="info",
                    message=line,
                )
        except RuntimeError as e:
            yield LogLine(
                timestamp=datetime.now(tz=timezone.utc),
                level="error",
                message=str(e),
            )

    # ─── 網路政策 ──────────────────────────────────────────────

    async def apply_network_policy(
        self, handle: SandboxHandle, policy: NetworkPolicy
    ) -> None:
        """
        套用 K8s NetworkPolicy（需要 CNI 支援 NetworkPolicy）。
        OpenShell sandbox 本身也有 OPA/Rego 的應用層網路控制。
        """
        namespace = self._handle_namespace(handle)
        yaml = self._network_policy_yaml(namespace, policy)
        await self._apply(yaml)
        log.info("k8s.policy_applied",
                 namespace=namespace, allow=len(policy.allow_domains))

    # ─── 快照（TODO）──────────────────────────────────────────

    async def create_snapshot(self, handle: SandboxHandle) -> SnapshotRef:
        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        log.info("k8s.snapshot_todo", pod=handle.external_id)
        return SnapshotRef(
            snapshot_id=snapshot_id,
            created_at=datetime.now(tz=timezone.utc),
        )

    async def restore_snapshot(
        self, handle: SandboxHandle, ref: SnapshotRef
    ) -> None:
        log.info("k8s.restore_todo", snapshot_id=ref.snapshot_id)

    # ─── Sandbox CRD 模板（正確做法）────────────────────────────

    def _sandbox_crd_yaml(
        self,
        crd_name:   str,
        sandbox_id: str,
        ssh_secret: str,
        spec:       SandboxSpec,
        image:      str = _SANDBOX_IMAGE_FALLBACK,
    ) -> str:
        """
        建立 Sandbox CRD（基於 asus-claw 的結構，v0.0.36 格式）。
        agent-sandbox-controller 監聽此 CRD 並自動：
          - 向 OpenShell gateway 登記 sandbox_id
          - 建立 Pod、PVC、Service
        """
        inference_ep = (
            spec.inference_config.endpoint
            if spec.inference_config else "http://inference-gw:3003/v1"
        )
        return f"""apiVersion: agents.x-k8s.io/v1alpha1
kind: Sandbox
metadata:
  name: {crd_name}
  namespace: {_OPENSHELL_NS}
  labels:
    openshell.ai/managed-by: openshell
    openshell.ai/sandbox-id: "{sandbox_id}"
    nemoclaw.ai/tenant-id: "{spec.tenant_id}"
    nemoclaw.ai/user-sandbox-name: "{spec.name}"
spec:
  podTemplate:
    spec:
      hostAliases:
      - ip: "172.17.0.1"
        hostnames:
        - host.docker.internal
        - host.openshell.internal
      initContainers:
      - name: workspace-init
        image: {image}
        imagePullPolicy: Never
        command: ["sh", "-c"]
        args:
        - |
          if [ ! -f /workspace-pvc/.workspace-initialized ]; then
            if [ -d /sandbox ]; then
              tar -C /sandbox -cf - . | tar -C /workspace-pvc -xpf -
            fi
            touch /workspace-pvc/.workspace-initialized
          fi
        securityContext:
          runAsUser: 0
        volumeMounts:
        - name: workspace
          mountPath: /workspace-pvc
      containers:
      - name: agent
        image: {image}
        imagePullPolicy: Never
        command: ["/opt/openshell/bin/openshell-sandbox"]
        env:
        - name: OPENSHELL_SANDBOX_ID
          value: "{sandbox_id}"
        - name: OPENSHELL_SANDBOX
          value: "{crd_name}"
        - name: OPENSHELL_ENDPOINT
          value: "{_OPENSHELL_ENDPOINT}"
        - name: OPENSHELL_SANDBOX_COMMAND
          value: "sleep infinity"
        - name: OPENSHELL_SSH_SOCKET_PATH
          value: "/run/openshell/ssh.sock"
        - name: OPENSHELL_SSH_HANDSHAKE_SECRET
          value: "{ssh_secret}"
        - name: OPENSHELL_SSH_HANDSHAKE_SKEW_SECS
          value: "300"
        - name: OPENSHELL_TLS_CA
          value: "/etc/openshell-tls/client/ca.crt"
        - name: OPENSHELL_TLS_CERT
          value: "/etc/openshell-tls/client/tls.crt"
        - name: OPENSHELL_TLS_KEY
          value: "/etc/openshell-tls/client/tls.key"
        - name: NEMOCLAW_INFERENCE_ENDPOINT
          value: "{inference_ep}"
        securityContext:
          runAsUser: 0
          capabilities:
            add: [SYS_ADMIN, NET_ADMIN, SYS_PTRACE, SYSLOG]
        volumeMounts:
        - name: openshell-client-tls
          mountPath: /etc/openshell-tls/client
          readOnly: true
        - name: openshell-supervisor-bin
          mountPath: /opt/openshell/bin
          readOnly: true
        - name: workspace
          mountPath: /sandbox
      volumes:
      - name: openshell-client-tls
        secret:
          secretName: {_TLS_SECRET_NAME}
          defaultMode: 256
      - name: openshell-supervisor-bin
        hostPath:
          path: /opt/openshell/bin
          type: DirectoryOrCreate
  volumeClaimTemplates:
  - metadata:
      name: workspace
    spec:
      accessModes: [ReadWriteOnce]
      resources:
        requests:
          storage: 2Gi
"""

    async def _wait_sandbox_ready(self, crd_name: str, timeout: int = 120) -> None:
        """等待 Sandbox CRD 進入 Ready 狀態（kubectl wait）"""
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._container.exec_run(
                f"kubectl wait sandbox/{crd_name} "
                f"-n {_OPENSHELL_NS} "
                f"--for=condition=Ready "
                f"--timeout={timeout}s",
                user="root",
            )
        )

    async def _wait_openshell_ready(
        self, crd_name: str, timeout: int = 120
    ) -> None:
        """
        輪詢 openshell sandbox list 等待 sandbox 進入 Ready 狀態。
        用於 openshell sandbox create 之後確認就緒。
        """
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                out = await self._run_host(
                    ["openshell", "sandbox", "list", "--output", "json"],
                    check=False,
                )
                if f'"name":"{crd_name}"' in out.replace(" ", ""):
                    if "Ready" in out:
                        log.info("k8s.sandbox_ready", crd_name=crd_name)
                        return
            except Exception:
                pass
            await asyncio.sleep(5)
        log.warning("k8s.sandbox_not_ready", crd_name=crd_name, timeout=timeout)

    async def _run_host(
        self, args: list[str], *, check: bool = True
    ) -> str:
        """在 Ubuntu host 上執行指令（不是在 container 內）"""
        cmd_str = " ".join(args)
        log.debug("k8s.host_exec", cmd=cmd_str)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if check and proc.returncode != 0:
            raise RuntimeError(
                f"Command failed: {cmd_str}\n"
                f"stderr: {stderr.decode()}"
            )
        return stdout.decode()

    def _make_crd_name(self, tenant_id: str, sandbox_name: str) -> str:
        """
        產生 Sandbox CRD 名稱（在 openshell namespace 內唯一）
        格式：t-{tenant_id 前8碼}-{sandbox_name}
        用戶看到的是 sandbox_name（存在 DB），CRD 名稱是內部的
        """
        tenant_prefix = _sanitize(tenant_id[:8])
        name = _sanitize(sandbox_name)
        result = f"t-{tenant_prefix}-{name}"
        return result[:63].rstrip("-")

    # ─── 舊版 YAML 模板（保留供參考，已改用 CRD 方式）──────────

    def _namespace_yaml(self, namespace: str, tenant_id: str) -> str:
        # 不設定 PodSecurity，因為 OpenShell sandbox Pod
        # 需要 SYS_ADMIN / NET_ADMIN 等高權限能力。
        # 安全控制由 OpenShell 的 Landlock / seccomp / OPA 在應用層處理，
        # 不依賴 K8s PodSecurity Standards。
        return f"""apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
  labels:
    nemoclaw.ai/tenant-id: "{tenant_id}"
    nemoclaw.ai/managed-by: "nemoclaw-platform"
"""

    def _resource_quota_yaml(self, namespace: str, resources) -> str:
        # ResourceQuota = 整個 namespace 的總量上限（不是單個 Pod 的限制）
        # Pro 方案：最多 5 個 Sandbox，每個 2 CPU / 4Gi → 總量 10 CPU / 20Gi
        return f"""apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
  namespace: {namespace}
spec:
  hard:
    requests.cpu: "2500m"
    requests.memory: "2560Mi"
    limits.cpu: "10"
    limits.memory: "20Gi"
    pods: "10"
    persistentvolumeclaims: "10"
"""

    def _pvc_yaml(self, namespace: str, pod_name: str) -> str:
        return f"""apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: workspace-{pod_name}
  namespace: {namespace}
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 5Gi
"""

    def _pod_yaml(
        self,
        namespace: str,
        pod_name:  str,
        sandbox_id: str,
        ssh_secret: str,
        spec: SandboxSpec,
        image: str = _SANDBOX_IMAGE_FALLBACK,
    ) -> str:
        """
        根據 asus-claw Pod YAML 模板建立新 sandbox Pod。
        所有環境變數、Volume、安全設定均與原始 Pod 一致。
        """
        inference_endpoint = (
            spec.inference_config.endpoint
            if spec.inference_config
            else "http://inference-gw:3003/v1"
        )
        return f"""apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {namespace}
  labels:
    nemoclaw.ai/sandbox-name: "{pod_name}"
    nemoclaw.ai/tenant-id: "{spec.tenant_id}"
spec:
  restartPolicy: Always
  hostAliases:
  - ip: "172.17.0.1"
    hostnames:
    - host.docker.internal
    - host.openshell.internal
  initContainers:
  - name: workspace-init
    image: {image}
    imagePullPolicy: Never
    command: ["sh", "-c"]
    args:
    - |
      if [ ! -f /workspace-pvc/.workspace-initialized ]; then
        if [ -d /sandbox ]; then
          tar -C /sandbox -cf - . | tar -C /workspace-pvc -xpf -
        fi
        touch /workspace-pvc/.workspace-initialized
      fi
    resources:
      requests:
        cpu: "100m"
        memory: "128Mi"
      limits:
        cpu: "500m"
        memory: "256Mi"
    securityContext:
      runAsUser: 0
    volumeMounts:
    - name: workspace
      mountPath: /workspace-pvc
  containers:
  - name: agent
    image: {image}
    imagePullPolicy: Never
    command: ["/opt/openshell/bin/openshell-sandbox"]
    resources:
      requests:
        cpu: "250m"
        memory: "512Mi"
      limits:
        cpu: "2"
        memory: "4Gi"
    env:
    - name: OPENSHELL_SANDBOX_ID
      value: "{sandbox_id}"
    - name: OPENSHELL_SANDBOX
      value: "{pod_name}"
    - name: OPENSHELL_ENDPOINT
      value: "{_OPENSHELL_ENDPOINT}"
    - name: OPENSHELL_SANDBOX_COMMAND
      value: "sleep infinity"
    - name: OPENSHELL_SSH_LISTEN_ADDR
      value: "0.0.0.0:2222"
    - name: OPENSHELL_SSH_HANDSHAKE_SECRET
      value: "{ssh_secret}"
    - name: OPENSHELL_SSH_HANDSHAKE_SKEW_SECS
      value: "300"
    - name: OPENSHELL_TLS_CA
      value: "/etc/openshell-tls/client/ca.crt"
    - name: OPENSHELL_TLS_CERT
      value: "/etc/openshell-tls/client/tls.crt"
    - name: OPENSHELL_TLS_KEY
      value: "/etc/openshell-tls/client/tls.key"
    - name: NEMOCLAW_INFERENCE_ENDPOINT
      value: "{inference_endpoint}"
    securityContext:
      runAsUser: 0
      capabilities:
        add: [SYS_ADMIN, NET_ADMIN, SYS_PTRACE, SYSLOG]
    volumeMounts:
    - name: openshell-client-tls
      mountPath: /etc/openshell-tls/client
      readOnly: true
    - name: openshell-supervisor-bin
      mountPath: /opt/openshell/bin
      readOnly: true
    - name: workspace
      mountPath: /sandbox
  volumes:
  - name: openshell-client-tls
    secret:
      secretName: {_TLS_SECRET_NAME}
      defaultMode: 256
  - name: openshell-supervisor-bin
    hostPath:
      path: /opt/openshell/bin
      type: DirectoryOrCreate
  - name: workspace
    persistentVolumeClaim:
      claimName: workspace-{pod_name}
"""

    def _network_policy_yaml(self, namespace: str, policy: NetworkPolicy) -> str:
        # 僅在 CNI 支援 NetworkPolicy 時有效（需要 Calico/Cilium）
        egress_rules = ""
        for domain in policy.allow_domains:
            egress_rules += f"""  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
    ports:
    - protocol: TCP
      port: 443
"""
        return f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sandbox-egress
  namespace: {namespace}
spec:
  podSelector: {{}}
  policyTypes: [Egress]
  egress:
{egress_rules if egress_rules else "  []"}
"""

    # ─── K8s 操作工具 ─────────────────────────────────────────

    def _tenant_namespace(self, tenant_id: str) -> str:
        # K8s namespace 只允許小寫英數字與連字號，最長 63 字元
        safe = tenant_id.lower().replace("_", "-")[:50]
        return f"tenant-{safe}"

    def _handle_namespace(self, handle: SandboxHandle) -> str:
        """從 SandboxHandle 取得 namespace"""
        if handle.namespace:
            return handle.namespace
        raise ValueError(
            f"SandboxHandle.namespace is empty for handle {handle.sandbox_id}. "
            "K8sAdapter requires namespace to be set."
        )

    async def _apply(self, yaml_content: str) -> str:
        """kubectl apply -f - (從 stdin)"""
        return await self._kubectl_stdin("apply -f -", yaml_content)

    async def _copy_secret(
        self, secret_name: str, src_ns: str, dst_ns: str
    ) -> None:
        """將 Secret 從一個 namespace 複製到另一個"""
        # 取得原始 Secret
        out = await self._kubectl(
            f"get secret {secret_name} -n {src_ns} -o json"
        )
        data = json.loads(out)

        # 清除 source namespace 相關的 metadata
        data["metadata"] = {
            "name":      data["metadata"]["name"],
            "namespace": dst_ns,
        }

        # 在 dst namespace 建立（若已存在則略過）
        try:
            await self._kubectl_stdin(
                "apply -f -", json.dumps(data)
            )
        except RuntimeError as e:
            if "already exists" not in str(e):
                raise
        log.info("k8s.secret_copied",
                 secret=secret_name, src=src_ns, dst=dst_ns)

    async def _wait_ready(
        self, namespace: str, pod_name: str, timeout: int = 120
    ) -> None:
        """等待 Pod 進入 Running 狀態"""
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._container.exec_run(
                f"kubectl wait pod/{pod_name} "
                f"-n {namespace} "
                f"--for=condition=Ready "
                f"--timeout={timeout}s",
                user="root",
            )
        )

    async def _kubectl(self, command: str) -> str:
        """在容器內執行 kubectl 指令，回傳 stdout"""
        full_cmd = f"kubectl {command}"
        log.debug("k8s.kubectl", cmd=full_cmd)

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._container.exec_run(
                ["sh", "-c", full_cmd],
                user="root",
                demux=True,
            )
        )
        stdout = result.output[0].decode() if result.output[0] else ""
        stderr = result.output[1].decode() if result.output[1] else ""

        if result.exit_code != 0:
            raise RuntimeError(
                f"kubectl command failed: {command}\n"
                f"stderr: {stderr}"
            )
        return stdout

    async def _kubectl_stdin(self, command: str, stdin_data: str) -> str:
        """將 YAML/JSON 透過 stdin 傳給 kubectl"""
        # 將 YAML 先寫到容器內的暫存檔，再 apply
        import tempfile
        tmp_name = f"/tmp/k8s-apply-{uuid.uuid4().hex[:8]}.yaml"

        # 寫入暫存檔
        escaped = stdin_data.replace("'", "'\\''")
        write_cmd = f"printf '%s' '{escaped}' > {tmp_name}"

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._container.exec_run(
                ["sh", "-c", write_cmd],
                user="root",
            )
        )

        try:
            result = await self._kubectl(f"{command.replace('-f -', f'-f {tmp_name}')}")
        finally:
            # 清除暫存檔
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._container.exec_run(
                    f"rm -f {tmp_name}", user="root"
                )
            )
        return result

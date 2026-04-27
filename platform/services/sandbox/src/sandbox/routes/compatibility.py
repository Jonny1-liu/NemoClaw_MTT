"""
NemoClaw / OpenShell 相容性測試端點

GET /admin/compatibility
  → 快速檢查（不建沙箱，只驗環境）

GET /admin/compatibility/full
  → 完整測試（含沙箱建立/刪除，約 60 秒）

每次 NemoClaw 升版後執行，確認各項整合點仍正常。
"""
import asyncio
import json
import os
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, status

log = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin"])


# ─── 測試結果資料結構 ─────────────────────────────────────────

class CheckResult:
    def __init__(self, name: str):
        self.name     = name
        self.status   = "unknown"
        self.detail   = ""
        self.duration_ms = 0

    def ok(self, detail: str = "") -> "CheckResult":
        self.status = "ok"
        self.detail = detail
        return self

    def fail(self, detail: str) -> "CheckResult":
        self.status = "fail"
        self.detail = detail
        return self

    def warn(self, detail: str) -> "CheckResult":
        self.status = "warn"
        self.detail = detail
        return self

    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "status":      self.status,
            "detail":      self.detail,
            "duration_ms": self.duration_ms,
        }


# ─── 個別檢查項目 ─────────────────────────────────────────────

async def _run_check(name: str, coro) -> CheckResult:
    result = CheckResult(name)
    t0 = time.monotonic()
    try:
        await coro(result)
    except Exception as e:
        result.fail(f"Exception: {type(e).__name__}: {e}")
    result.duration_ms = int((time.monotonic() - t0) * 1000)
    return result


async def check_docker_container(result: CheckResult) -> None:
    """OpenShell Docker 容器是否在跑"""
    import docker
    client = docker.from_env()
    pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
    for c in client.containers.list():
        if pattern in c.name and c.status == "running":
            # 取得版本資訊
            image = c.image.tags[0] if c.image.tags else c.image.short_id
            result.ok(f"name={c.name} image={image}")
            return
    result.fail(f"No running container matching '{pattern}'")


async def check_container_version(result: CheckResult) -> None:
    """取得 OpenShell 版本號"""
    import docker
    client = docker.from_env()
    pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
    for c in client.containers.list():
        if pattern in c.name and c.status == "running":
            image = c.image.tags[0] if c.image.tags else "unknown"
            # 從 image tag 提取版本（格式：ghcr.io/nvidia/openshell/cluster:0.0.36）
            version = image.split(":")[-1] if ":" in image else "unknown"
            result.ok(f"version={version} image={image}")
            return
    result.fail("Container not found")


async def check_kubectl_access(result: CheckResult) -> None:
    """kubectl 是否可在 container 內正常執行"""
    import docker
    client = docker.from_env()
    pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
    for c in client.containers.list():
        if pattern in c.name:
            r = c.exec_run(
                "kubectl version --client --output=json",
                user="root", demux=True,
            )
            if r.exit_code == 0:
                out = r.output[0].decode() if r.output[0] else ""
                try:
                    data = json.loads(out)
                    ver = data.get("clientVersion", {}).get("gitVersion", "unknown")
                    result.ok(f"kubectl={ver}")
                except Exception:
                    result.ok("kubectl available (json parse failed)")
            else:
                result.fail(f"kubectl failed: {r.output[1].decode() if r.output[1] else 'unknown'}")
            return
    result.fail("Container not found")


async def check_sandbox_image(result: CheckResult) -> None:
    """偵測當前 sandbox 映像版本（從 asus-claw pod）"""
    import docker
    client = docker.from_env()
    pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
    for c in client.containers.list():
        if pattern in c.name:
            r = c.exec_run(
                "kubectl get pod asus-claw -n openshell "
                "-o jsonpath={.spec.containers[0].image}",
                user="root", demux=True,
            )
            if r.exit_code == 0 and r.output[0]:
                image = r.output[0].decode().strip()
                result.ok(f"image={image}")
            else:
                result.warn("asus-claw pod not found (NemoClaw may not be onboarded)")
            return
    result.fail("Container not found")


async def check_openshell_sandbox_list(result: CheckResult) -> None:
    """`openshell sandbox list` 是否可正常執行"""
    proc = await asyncio.create_subprocess_exec(
        "openshell", "sandbox", "list",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        lines = stdout.decode().strip().splitlines()
        sandbox_count = max(0, len(lines) - 1)  # 扣掉 header
        result.ok(f"sandboxes={sandbox_count}")
    else:
        result.fail(f"exit_code={proc.returncode} stderr={stderr.decode()[:200]}")


async def check_k3s_namespaces(result: CheckResult) -> None:
    """k3s 中必要的 namespace 是否存在"""
    import docker
    client = docker.from_env()
    pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
    for c in client.containers.list():
        if pattern in c.name:
            r = c.exec_run(
                "kubectl get namespaces -o jsonpath={.items[*].metadata.name}",
                user="root", demux=True,
            )
            if r.exit_code == 0:
                namespaces = r.output[0].decode().split() if r.output[0] else []
                required = {"openshell", "kube-system", "agent-sandbox-system"}
                missing = required - set(namespaces)
                if missing:
                    result.fail(f"missing namespaces: {missing}")
                else:
                    result.ok(f"all required namespaces present: {sorted(namespaces)[:6]}...")
            else:
                result.fail("kubectl failed")
            return
    result.fail("Container not found")


async def check_agent_sandbox_controller(result: CheckResult) -> None:
    """agent-sandbox-controller 是否在跑"""
    import docker
    client = docker.from_env()
    pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
    for c in client.containers.list():
        if pattern in c.name:
            r = c.exec_run(
                "kubectl get pod agent-sandbox-controller-0 "
                "-n agent-sandbox-system "
                "-o jsonpath={.status.phase}",
                user="root", demux=True,
            )
            if r.exit_code == 0:
                phase = r.output[0].decode().strip() if r.output[0] else "Unknown"
                if phase == "Running":
                    result.ok(f"phase={phase}")
                else:
                    result.warn(f"phase={phase} (expected Running)")
            else:
                result.fail("agent-sandbox-controller-0 not found")
            return
    result.fail("Container not found")


async def check_sandbox_crd_exists(result: CheckResult) -> None:
    """Sandbox CRD (agents.x-k8s.io) 是否存在"""
    import docker
    client = docker.from_env()
    pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
    for c in client.containers.list():
        if pattern in c.name:
            r = c.exec_run(
                "kubectl get crd sandboxes.agents.x-k8s.io "
                "-o jsonpath={.metadata.name}",
                user="root", demux=True,
            )
            if r.exit_code == 0 and r.output[0]:
                result.ok(f"crd={r.output[0].decode().strip()}")
            else:
                result.fail("sandboxes.agents.x-k8s.io CRD not found")
            return
    result.fail("Container not found")


# ─── 完整測試（含沙箱建立/刪除）────────────────────────────────

async def check_sandbox_lifecycle(result: CheckResult) -> None:
    """建立一個測試沙箱，等待 Ready，然後刪除（完整生命週期測試）"""
    test_name = f"compat-test-{int(time.time())}"
    created = False
    try:
        # 建立
        proc = await asyncio.create_subprocess_exec(
            "openshell", "sandbox", "create",
            "--name", test_name,
            "--no-bootstrap", "--no-auto-providers", "--no-tty",
            "--", "/bin/true",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
        if proc.returncode != 0:
            result.fail(f"sandbox create failed: {stderr.decode()[:300]}")
            return
        created = True

        # 等待 Ready（最多 60 秒）
        deadline = time.monotonic() + 60
        phase = "unknown"
        while time.monotonic() < deadline:
            list_proc = await asyncio.create_subprocess_exec(
                "openshell", "sandbox", "list",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await list_proc.communicate()
            if test_name in out.decode() and "Ready" in out.decode():
                phase = "Ready"
                break
            await asyncio.sleep(5)

        if phase != "Ready":
            result.warn(f"sandbox created but phase={phase} after 60s")
        else:
            result.ok(f"sandbox '{test_name}' created and became Ready")

    finally:
        # 清理（無論成功與否）
        if created:
            try:
                del_proc = await asyncio.create_subprocess_exec(
                    "openshell", "sandbox", "delete", test_name,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(del_proc.communicate(), timeout=30)
            except Exception:
                pass  # 清理失敗不影響測試結果


# ─── API 端點 ─────────────────────────────────────────────────

@router.get(
    "/compatibility",
    summary="NemoClaw 快速相容性檢查（不建沙箱）",
)
async def compatibility_check():
    """
    執行 7 項快速檢查，通常在 5 秒內完成。
    NemoClaw 升版後執行此端點確認相容性。
    """
    checks = [
        ("docker_container",       check_docker_container),
        ("container_version",      check_container_version),
        ("kubectl_access",         check_kubectl_access),
        ("sandbox_image",          check_sandbox_image),
        ("openshell_sandbox_list", check_openshell_sandbox_list),
        ("k3s_namespaces",         check_k3s_namespaces),
        ("agent_sandbox_ctrl",     check_agent_sandbox_controller),
        ("sandbox_crd",            check_sandbox_crd_exists),
    ]

    results = []
    for name, fn in checks:
        r = await _run_check(name, fn)
        results.append(r.to_dict())
        log.info(f"compat.{r.status}", check=name, detail=r.detail)

    passed  = sum(1 for r in results if r["status"] == "ok")
    warned  = sum(1 for r in results if r["status"] == "warn")
    failed  = sum(1 for r in results if r["status"] == "fail")
    overall = "ok" if failed == 0 else "degraded" if passed > 0 else "fail"

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "overall":   overall,
        "summary":   {"ok": passed, "warn": warned, "fail": failed},
        "checks":    results,
    }


@router.get(
    "/compatibility/full",
    summary="NemoClaw 完整相容性測試（含沙箱建立/刪除，約 60-90 秒）",
)
async def compatibility_full():
    """
    在快速檢查的基礎上，額外執行完整的沙箱生命週期測試：
    建立測試沙箱 → 等待 Ready → 自動刪除。
    """
    # 先跑快速檢查
    quick = await compatibility_check()
    if quick["overall"] == "fail":
        return {**quick, "note": "Skipped full lifecycle test due to quick check failures"}

    # 加入生命週期測試
    lifecycle = await _run_check("sandbox_lifecycle", check_sandbox_lifecycle)
    quick["checks"].append(lifecycle.to_dict())

    if lifecycle.status == "fail":
        quick["overall"] = "degraded"
        quick["summary"]["fail"] += 1
    elif lifecycle.status == "warn":
        quick["summary"]["warn"] += 1
    else:
        quick["summary"]["ok"] += 1

    return quick

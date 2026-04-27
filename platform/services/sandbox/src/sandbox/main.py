"""Sandbox Service"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[4] / ".env", override=False)

from shared.logging_config import setup_logging
setup_logging(
    "sandbox",
    logs_root=Path(__file__).parents[4] / "logs",
)

import structlog
import uvicorn
from fastapi import APIRouter, FastAPI

from sandbox.config import settings
from sandbox.ports.sandbox_backend import SandboxBackend
from sandbox.routes.sandboxes import router as sandboxes_router, set_backend
from shared.types import HealthResponse

log = structlog.get_logger()


def _create_backend() -> SandboxBackend:
    backend = settings.sandbox_backend.lower()

    if backend == "k8s":
        from sandbox.adapters.k8s_adapter import K8sAdapter
        container_pattern = os.getenv("K8S_CONTAINER_PATTERN", "openshell-cluster")
        log.info("sandbox.backend", type="k8s", container=container_pattern)
        return K8sAdapter(container_pattern=container_pattern)

    if backend == "openshell":
        from sandbox.adapters.openshell_adapter import OpenShellAdapter
        log.info("sandbox.backend", type="openshell",
                 image=settings.openshell_sandbox_image)
        return OpenShellAdapter(
            sandbox_image=settings.openshell_sandbox_image,
            gateway_endpoint=settings.openshell_gateway_endpoint or None,
        )

    if backend == "nemoclaw":
        # 保留舊名稱相容性，實際指向 OpenShellAdapter
        from sandbox.adapters.openshell_adapter import OpenShellAdapter
        log.info("sandbox.backend", type="openshell(nemoclaw alias)")
        return OpenShellAdapter(
            sandbox_image=settings.openshell_sandbox_image,
        )

    log.info("sandbox.backend", type="mock")
    from sandbox.adapters.mock_adapter import MockSandboxAdapter
    return MockSandboxAdapter()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    backend = _create_backend()
    set_backend(backend)
    log.info("sandbox_service.ready", backend=type(backend).__name__)
    yield
    log.info("sandbox_service.stopping")


app = FastAPI(
    title="Sandbox Service",
    description="沙箱生命週期管理（NemoClaw ACL 隔離）",
    version="0.1.0",
    lifespan=lifespan,
)

health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    return HealthResponse(service="sandbox")


app.include_router(health_router)
app.include_router(sandboxes_router)

from sandbox.routes.compatibility import router as compat_router
app.include_router(compat_router)


if __name__ == "__main__":
    uvicorn.run("sandbox.main:app", host="0.0.0.0",
                port=settings.service_port, reload=True)

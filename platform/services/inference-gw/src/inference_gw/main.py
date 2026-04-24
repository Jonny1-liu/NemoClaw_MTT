"""Inference Gateway — 多供應商 LLM 代理、計量、速率限制"""
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI

from inference_gw.router import ProviderRouter

log = structlog.get_logger()

router: ProviderRouter


def _build_router() -> ProviderRouter:
    """依環境變數中已設定的 API Key 啟用對應供應商"""
    from inference_gw.providers.base import LLMProvider
    providers: dict[str, LLMProvider] = {}

    if key := os.getenv("NVIDIA_API_KEY"):
        from inference_gw.providers.nvidia import NVIDIAAdapter
        providers["nvidia"] = NVIDIAAdapter(api_key=key)
        log.info("inference_gw.provider_enabled", provider="nvidia")

    if key := os.getenv("OPENAI_API_KEY"):
        from inference_gw.providers.openai import OpenAIAdapter
        providers["openai"] = OpenAIAdapter(api_key=key)
        log.info("inference_gw.provider_enabled", provider="openai")

    if key := os.getenv("ANTHROPIC_API_KEY"):
        from inference_gw.providers.anthropic import AnthropicAdapter
        providers["anthropic"] = AnthropicAdapter(api_key=key)
        log.info("inference_gw.provider_enabled", provider="anthropic")

    if url := os.getenv("OLLAMA_BASE_URL"):
        from inference_gw.providers.ollama import OllamaAdapter
        providers["ollama"] = OllamaAdapter(base_url=url)
        log.info("inference_gw.provider_enabled", provider="ollama")

    if not providers:
        log.warning("inference_gw.no_providers", hint="Set at least one *_API_KEY in .env")

    return ProviderRouter(providers)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global router
    router = _build_router()
    log.info("inference_gw.ready",
             providers=list(router._providers.keys()))
    yield
    log.info("inference_gw.stopping")


app = FastAPI(
    title="Inference Gateway",
    description="多供應商 LLM 代理（NVIDIA / OpenAI / Anthropic / Google / Ollama）",
    version="0.1.0",
    lifespan=lifespan,
)

# Health
from fastapi import APIRouter
from shared.types import HealthResponse

health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    return HealthResponse(service="inference-gw")


app.include_router(health_router)

# TODO: 加入推理 route
# from inference_gw.routes.chat import router as chat_router
# app.include_router(chat_router, prefix="/v1")


if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", "3003"))
    uvicorn.run("inference_gw.main:app", host="0.0.0.0", port=port, reload=True)

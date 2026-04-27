"""Inference Gateway — 多供應商 LLM 代理、計量、速率限制"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[4] / ".env", override=False)

from shared.logging_config import setup_logging
setup_logging(
    "inference-gw",
    logs_root=Path(__file__).parents[4] / "logs",
)

import os
import structlog
import uvicorn
from fastapi import APIRouter, FastAPI

from inference_gw.config import settings
from inference_gw.router import ProviderRouter
from inference_gw.routes.chat import router as chat_router, set_provider_router
from shared.types import HealthResponse

log = structlog.get_logger()


def _build_router() -> ProviderRouter:
    """依 .env 中已設定的 API Key 啟用對應供應商"""
    from inference_gw.providers.base import LLMProvider
    providers: dict[str, LLMProvider] = {}

    if settings.nvidia_api_key:
        from inference_gw.providers.nvidia import NVIDIAAdapter
        providers["nvidia"] = NVIDIAAdapter(api_key=settings.nvidia_api_key)
        log.info("inference_gw.provider_enabled", provider="nvidia")

    if settings.openai_api_key:
        from inference_gw.providers.openai import OpenAIAdapter
        providers["openai"] = OpenAIAdapter(api_key=settings.openai_api_key)
        log.info("inference_gw.provider_enabled", provider="openai")

    if settings.anthropic_api_key:
        from inference_gw.providers.anthropic import AnthropicAdapter
        providers["anthropic"] = AnthropicAdapter(api_key=settings.anthropic_api_key)
        log.info("inference_gw.provider_enabled", provider="anthropic")

    if settings.ollama_base_url:
        from inference_gw.providers.ollama import OllamaAdapter
        providers["ollama"] = OllamaAdapter(base_url=settings.ollama_base_url)
        log.info("inference_gw.provider_enabled", provider="ollama")

    if not providers:
        log.warning("inference_gw.no_providers",
                    hint="Set NVIDIA_API_KEY or other provider keys in .env")

    return ProviderRouter(providers)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    provider_router = _build_router()
    set_provider_router(provider_router)
    log.info("inference_gw.ready",
             providers=list(provider_router._providers.keys()))
    yield
    log.info("inference_gw.stopping")


app = FastAPI(
    title="Inference Gateway",
    description="多供應商 LLM 代理（NVIDIA / OpenAI / Anthropic / Google / Ollama）",
    version="0.1.0",
    lifespan=lifespan,
)

health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    return HealthResponse(service="inference-gw")


app.include_router(health_router)
app.include_router(chat_router)   # /v1/chat/completions


if __name__ == "__main__":
    uvicorn.run("inference_gw.main:app", host="0.0.0.0",
                port=settings.service_port, reload=True)

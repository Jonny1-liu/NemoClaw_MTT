"""NVIDIA Endpoints Adapter"""
import time
import uuid
from typing import AsyncIterator

import httpx
import structlog

from inference_gw.providers.base import (
    CompletionDelta, CompletionRequest, CompletionResponse,
    LLMProvider, Message, MessageRole, TokenCost, TokenUsage,
)

log = structlog.get_logger()

_MODEL_MAP: dict[str, str] = {
    # NVIDIA 自有模型
    "nemotron-super":        "nvidia/nemotron-3-super-120b-a12b",
    # Meta Llama 系列
    "llama-3.1-70b":         "meta/llama-3.1-70b-instruct",
    "llama-3.1-8b":          "meta/llama-3.1-8b-instruct",
    "llama-3.3-70b":         "meta/llama-3.3-70b-instruct",
    # DeepSeek
    "deepseek-v3":           "deepseek-ai/deepseek-v3.2",
    "deepseek-coder":        "deepseek-ai/deepseek-coder-6.7b-instruct",
    # Google
    "gemma-3-27b":           "google/gemma-3-27b-it",
    "gemma-3-12b":           "google/gemma-3-12b-it",
    "gemma-3-4b":            "google/gemma-3-4b-it",
}

_PRICING: dict[str, TokenCost] = {
    "nemotron-super":  TokenCost(input_per_1k=0.008, output_per_1k=0.024),
    "llama-3.1-70b":   TokenCost(input_per_1k=0.003, output_per_1k=0.006),
    "llama-3.1-8b":    TokenCost(input_per_1k=0.001, output_per_1k=0.002),
    "llama-3.3-70b":   TokenCost(input_per_1k=0.003, output_per_1k=0.006),
    "deepseek-v3":     TokenCost(input_per_1k=0.002, output_per_1k=0.004),
    "gemma-3-27b":     TokenCost(input_per_1k=0.002, output_per_1k=0.004),
}

_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NVIDIAAdapter(LLMProvider):

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    @property
    def provider_id(self) -> str:
        return "nvidia"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        real_model = _MODEL_MAP.get(request.model, request.model)
        t0 = time.monotonic()

        resp = await self._client.post("/chat/completions", json={
            "model": real_model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        })
        resp.raise_for_status()
        data = resp.json()

        return CompletionResponse(
            id=data["id"],
            model=request.model,
            provider=self.provider_id,
            message=Message(
                role=MessageRole.ASSISTANT,
                content=data["choices"][0]["message"]["content"],
            ),
            usage=TokenUsage(
                input_tokens=data["usage"]["prompt_tokens"],
                output_tokens=data["usage"]["completion_tokens"],
            ),
            finish_reason=data["choices"][0]["finish_reason"],
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionDelta]:
        # TODO: 實作 SSE 串流
        raise NotImplementedError("NVIDIA streaming — TODO")

    async def validate_config(self) -> bool:
        try:
            resp = await self._client.get("/models")
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, request: CompletionRequest) -> TokenCost:
        return _PRICING.get(request.model, TokenCost(input_per_1k=0.005, output_per_1k=0.015))

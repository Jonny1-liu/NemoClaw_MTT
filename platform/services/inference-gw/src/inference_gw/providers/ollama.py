"""Ollama Adapter（本機 / 私有部署 LLM）"""
import time
import uuid
from typing import AsyncIterator

import httpx

from inference_gw.providers.base import (
    CompletionDelta, CompletionRequest, CompletionResponse,
    LLMProvider, Message, MessageRole, TokenCost, TokenUsage,
)


class OllamaAdapter(LLMProvider):
    """
    Ollama 支援 OpenAI-compatible API，格式翻譯最少。
    可指向任意 Ollama 端點（本機或私有伺服器）。
    本機推理對租戶計費為 0（硬體成本由平台吸收）。
    """

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=120.0)

    @property
    def provider_id(self) -> str:
        return "ollama"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        t0 = time.monotonic()

        resp = await self._client.post("/v1/chat/completions", json={
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
        })
        resp.raise_for_status()
        data = resp.json()

        return CompletionResponse(
            id=data.get("id", str(uuid.uuid4())),
            model=request.model,
            provider=self.provider_id,
            message=Message(
                role=MessageRole.ASSISTANT,
                content=data["choices"][0]["message"]["content"],
            ),
            usage=TokenUsage(
                input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                output_tokens=data.get("usage", {}).get("completion_tokens", 0),
            ),
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionDelta]:
        raise NotImplementedError("Ollama streaming — TODO")

    async def validate_config(self) -> bool:
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, request: CompletionRequest) -> TokenCost:
        return TokenCost(input_per_1k=0.0, output_per_1k=0.0)   # 本機免費

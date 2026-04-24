"""OpenAI Adapter（ChatGPT）"""
import time
from typing import AsyncIterator

from openai import AsyncOpenAI

from inference_gw.providers.base import (
    CompletionDelta, CompletionRequest, CompletionResponse,
    LLMProvider, Message, MessageRole, TokenCost, TokenUsage,
)

_MODEL_MAP = {
    "gpt-4o":       "gpt-4o",
    "gpt-4o-mini":  "gpt-4o-mini",
    "o1":           "o1",
    "o3-mini":      "o3-mini",
}

_PRICING = {
    "gpt-4o":       TokenCost(input_per_1k=0.005,   output_per_1k=0.015),
    "gpt-4o-mini":  TokenCost(input_per_1k=0.00015, output_per_1k=0.0006),
    "o1":           TokenCost(input_per_1k=0.015,   output_per_1k=0.060),
    "o3-mini":      TokenCost(input_per_1k=0.0011,  output_per_1k=0.0044),
}


class OpenAIAdapter(LLMProvider):

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    @property
    def provider_id(self) -> str:
        return "openai"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        real_model = _MODEL_MAP.get(request.model, request.model)
        t0 = time.monotonic()

        resp = await self._client.chat.completions.create(
            model=real_model,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return CompletionResponse(
            id=resp.id,
            model=request.model,
            provider=self.provider_id,
            message=Message(role=MessageRole.ASSISTANT,
                            content=resp.choices[0].message.content or ""),
            usage=TokenUsage(
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            ),
            finish_reason=resp.choices[0].finish_reason or "stop",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionDelta]:
        raise NotImplementedError("OpenAI streaming — TODO")

    async def validate_config(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    def estimate_cost(self, request: CompletionRequest) -> TokenCost:
        return _PRICING.get(request.model, TokenCost(input_per_1k=0.005, output_per_1k=0.015))

"""Anthropic Claude Adapter"""
import time
from typing import AsyncIterator

import anthropic as sdk

from inference_gw.providers.base import (
    CompletionDelta, CompletionRequest, CompletionResponse,
    LLMProvider, Message, MessageRole, TokenCost, TokenUsage,
)

_MODEL_MAP = {
    "claude-opus-4":    "claude-opus-4-6",
    "claude-sonnet-4":  "claude-sonnet-4-6",
    "claude-haiku-4":   "claude-haiku-4-5-20251001",
}

_PRICING = {
    "claude-opus-4":    TokenCost(input_per_1k=0.015,  output_per_1k=0.075),
    "claude-sonnet-4":  TokenCost(input_per_1k=0.003,  output_per_1k=0.015),
    "claude-haiku-4":   TokenCost(input_per_1k=0.0008, output_per_1k=0.004),
}


class AnthropicAdapter(LLMProvider):

    def __init__(self, api_key: str) -> None:
        self._client = sdk.AsyncAnthropic(api_key=api_key)

    @property
    def provider_id(self) -> str:
        return "anthropic"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        real_model = _MODEL_MAP.get(request.model, request.model)
        t0 = time.monotonic()

        # Anthropic 的 system message 是獨立欄位
        system = next((m.content for m in request.messages
                       if m.role == MessageRole.SYSTEM), None)
        chat_messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages if m.role != MessageRole.SYSTEM
        ]

        resp = await self._client.messages.create(
            model=real_model,
            max_tokens=request.max_tokens,
            system=system or sdk.NOT_GIVEN,
            messages=chat_messages,
        )

        return CompletionResponse(
            id=resp.id,
            model=request.model,
            provider=self.provider_id,
            message=Message(role=MessageRole.ASSISTANT, content=resp.content[0].text),
            usage=TokenUsage(
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
            ),
            finish_reason="stop" if resp.stop_reason == "end_turn" else "length",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionDelta]:
        resp = await self.complete(request)
        yield CompletionDelta(delta=resp.message.content, finish_reason=resp.finish_reason, usage=resp.usage)

    async def validate_config(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    def estimate_cost(self, request: CompletionRequest) -> TokenCost:
        return _PRICING.get(request.model, TokenCost(input_per_1k=0.003, output_per_1k=0.015))

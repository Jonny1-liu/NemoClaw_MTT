"""Inference Gateway Router 單元測試（不需要真實 API Key）"""
import pytest

from inference_gw.providers.base import (
    CompletionRequest, CompletionResponse, LLMProvider,
    Message, MessageRole, TokenCost, TokenUsage,
)
from inference_gw.router import ProviderRouter


# ─── Stub Provider（測試用）─────────────────────────────────

class StubProvider(LLMProvider):
    def __init__(self, provider_id: str) -> None:
        self._id = provider_id

    @property
    def provider_id(self) -> str:
        return self._id

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError

    async def stream(self, request):
        raise NotImplementedError

    async def validate_config(self) -> bool:
        return True

    def estimate_cost(self, request: CompletionRequest) -> TokenCost:
        return TokenCost(input_per_1k=0.001, output_per_1k=0.002)


# ─── Tests ───────────────────────────────────────────────────

@pytest.fixture
def router() -> ProviderRouter:
    return ProviderRouter({
        "nvidia":    StubProvider("nvidia"),
        "openai":    StubProvider("openai"),
        "anthropic": StubProvider("anthropic"),
    })


def make_request(model: str) -> CompletionRequest:
    return CompletionRequest(
        model=model,
        messages=[Message(role=MessageRole.USER, content="hello")],
    )


def test_explicit_provider_takes_priority(router: ProviderRouter) -> None:
    provider = router.route(make_request("gpt-4o"), explicit_provider="anthropic")
    assert provider.provider_id == "anthropic"


def test_tenant_preferred_used_when_no_explicit(router: ProviderRouter) -> None:
    provider = router.route(make_request("llama-3.1-70b"), tenant_preferred="openai")
    assert provider.provider_id == "openai"


def test_model_catalog_selects_correct_provider(router: ProviderRouter) -> None:
    provider = router.route(make_request("claude-sonnet-4"))
    assert provider.provider_id == "anthropic"


def test_nvidia_model_routes_to_nvidia(router: ProviderRouter) -> None:
    provider = router.route(make_request("nemotron-super"))
    assert provider.provider_id == "nvidia"


def test_unknown_model_falls_back_to_default(router: ProviderRouter) -> None:
    # 預設 provider 是 nvidia（環境變數 INFERENCE_DEFAULT_PROVIDER）
    provider = router.route(make_request("some-unknown-model"))
    assert provider.provider_id == "nvidia"


def test_raises_when_no_providers_available() -> None:
    empty_router = ProviderRouter({})
    with pytest.raises(ValueError, match="No available provider"):
        empty_router.route(make_request("gpt-4o"))

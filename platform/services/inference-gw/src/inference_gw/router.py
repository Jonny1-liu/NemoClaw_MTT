"""
Provider Router — 依租戶設定、模型名稱、成本策略選擇供應商

優先序：
  1. 請求明確指定的供應商（X-Provider header）
  2. 租戶設定的 preferred_provider
  3. Model Catalog 的預設供應商
  4. 平台預設（環境變數 INFERENCE_DEFAULT_PROVIDER）
"""
import os

import structlog

from inference_gw.providers.base import CompletionRequest, LLMProvider

log = structlog.get_logger()

# 模型目錄：邏輯模型名 → 預設供應商
MODEL_CATALOG: dict[str, str] = {
    # NVIDIA Endpoints 上的模型（可透過 NVIDIA API Key 存取）
    "nemotron-super":                   "nvidia",
    "llama-3.1-70b":                    "nvidia",
    "llama-3.1-8b":                     "nvidia",
    "llama-3.3-70b":                    "nvidia",
    "deepseek-v3":                      "nvidia",
    "deepseek-coder":                   "nvidia",
    "gemma-3-27b":                      "nvidia",
    "gemma-3-12b":                      "nvidia",
    "gemma-3-4b":                       "nvidia",
    # 完整模型名稱（OpenClaw 傳來的格式）
    "meta/llama-3.1-8b-instruct":       "nvidia",
    "meta/llama-3.1-70b-instruct":      "nvidia",
    "meta/llama-3.3-70b-instruct":      "nvidia",
    "nvidia/nemotron-3-super-120b-a12b":"nvidia",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1": "nvidia",
    # OpenAI
    "gpt-4o":           "openai",
    "gpt-4o-mini":      "openai",
    "o1":               "openai",
    "o3-mini":          "openai",
    # Anthropic
    "claude-opus-4":    "anthropic",
    "claude-sonnet-4":  "anthropic",
    "claude-haiku-4":   "anthropic",
    # Ollama（本機）
    "llama3.2:3b":      "ollama",
    "qwen2.5:7b":       "ollama",
}


class ProviderRouter:

    def __init__(self, providers: dict[str, LLMProvider]) -> None:
        self._providers = providers
        self._default = os.getenv("INFERENCE_DEFAULT_PROVIDER", "nvidia")

    def route(
        self,
        request: CompletionRequest,
        *,
        explicit_provider: str | None = None,
        tenant_preferred: str | None = None,
    ) -> LLMProvider:
        """選擇最適合的 LLM Provider"""

        # 優先序 1：明確指定
        if explicit_provider and explicit_provider in self._providers:
            log.debug("router.explicit", provider=explicit_provider)
            return self._providers[explicit_provider]

        # 優先序 2：租戶偏好
        if tenant_preferred and tenant_preferred in self._providers:
            log.debug("router.tenant_preferred", provider=tenant_preferred)
            return self._providers[tenant_preferred]

        # 優先序 3：Model Catalog
        catalog_provider = MODEL_CATALOG.get(request.model)
        if catalog_provider and catalog_provider in self._providers:
            log.debug("router.catalog", model=request.model, provider=catalog_provider)
            return self._providers[catalog_provider]

        # 優先序 4：平台預設
        if self._default in self._providers:
            log.debug("router.default", provider=self._default)
            return self._providers[self._default]

        raise ValueError(
            f"No available provider for model '{request.model}'. "
            f"Registered providers: {list(self._providers.keys())}"
        )

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.provider_id] = provider
        log.info("router.provider_registered", provider=provider.provider_id)

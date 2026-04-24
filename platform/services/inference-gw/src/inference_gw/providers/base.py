"""
LLM Provider 抽象介面

所有供應商（NVIDIA、OpenAI、Anthropic、Google、Ollama）都實作這個 Protocol。
Inference Gateway 只認識這個介面，不直接依賴任何供應商 SDK。

新增供應商：實作此 Protocol → 在 router.py 登記 → 完成。
其他所有程式碼不需要修改。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator


# ─── 統一請求 / 回應格式（OpenAI-compatible，業界事實標準）──────


class MessageRole(str, Enum):
    SYSTEM    = "system"
    USER      = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    role:    MessageRole
    content: str


@dataclass
class CompletionRequest:
    """供應商無關的推理請求格式"""
    model:       str              # 邏輯模型名（Router 負責翻譯成各供應商的實際 ID）
    messages:    list[Message]
    temperature: float = 0.7
    max_tokens:  int   = 1024
    stream:      bool  = False


@dataclass
class TokenUsage:
    input_tokens:  int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CompletionResponse:
    """統一回應格式（翻譯自各供應商的原生回應）"""
    id:            str
    model:         str
    provider:      str            # 實際使用的供應商（透明度）
    message:       Message
    usage:         TokenUsage
    finish_reason: str            # "stop" | "length" | "error"
    latency_ms:    int = 0


@dataclass
class CompletionDelta:
    """串流模式的逐 token 回應"""
    delta:         str
    finish_reason: str | None = None
    usage:         TokenUsage | None = None   # 只在最後一個 chunk 附上


@dataclass
class TokenCost:
    """每 1K token 的 USD 成本，用於路由決策"""
    input_per_1k:  float
    output_per_1k: float

    def estimate(self, usage: TokenUsage) -> float:
        return (usage.input_tokens / 1000 * self.input_per_1k +
                usage.output_tokens / 1000 * self.output_per_1k)


# ─── Provider 抽象介面 ────────────────────────────────────────

class LLMProvider(ABC):

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """供應商識別符，例如 'nvidia'、'openai'"""
        ...

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """非串流完成"""
        ...

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionDelta]:
        """串流完成（async generator）"""
        ...

    @abstractmethod
    async def validate_config(self) -> bool:
        """測試 API Key 是否有效"""
        ...

    @abstractmethod
    def estimate_cost(self, request: CompletionRequest) -> TokenCost:
        """估算此請求的 token 成本（用於路由決策）"""
        ...

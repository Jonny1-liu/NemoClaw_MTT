# Inference Gateway：多供應商設計

> 文件版本：v1.0 | 撰寫日期：2026-04-21
> 修正：取代原 01-platform-services.md 中推理 Gateway 的單一 NVIDIA 設計

---

## 1. 問題：原設計的彈性不足

原設計直接硬編碼呼叫 NVIDIA Endpoints，導致：

```
問題點：
  - 供應商鎖定（Vendor Lock-in）
  - 每次換供應商都需要大量改寫
  - 無法讓租戶自行選擇偏好的 LLM
  - 無法做多供應商的成本比較與路由優化
  - 未來 BYOK（Bring Your Own Key）難以支援
```

---

## 2. 解法：Provider Abstraction Layer

與 NemoClaw 解耦策略相同的思維，在 Inference Gateway 中也引入抽象層：

```
┌────────────────────────────────────────────────────────────────┐
│                   Inference Gateway                             │
│                                                                 │
│  請求進入                                                       │
│     │                                                           │
│     ▼                                                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Provider-Agnostic Request 格式                  │  │
│  │           （我們自己定義的統一介面）                        │  │
│  └───────────────────────────┬──────────────────────────────┘  │
│                              │                                  │
│  ┌───────────────────────────▼──────────────────────────────┐  │
│  │                    Provider Router                        │  │
│  │  依據：租戶設定 / 模型名稱 / 成本策略 / Fallback 規則     │  │
│  └──────┬────────┬──────────┬──────────┬──────────┬─────────┘  │
│         │        │          │          │          │             │
│         ▼        ▼          ▼          ▼          ▼             │
│    ┌────────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│    │NVIDIA  │ │OpenAI│ │ Google │ │Anthropic│ │Ollama  │       │
│    │Adapter │ │Adapter│ │Adapter │ │ Adapter │ │Adapter │       │
│    └────────┘ └──────┘ └────────┘ └────────┘ └────────┘       │
│         │        │          │          │          │             │
└─────────┼────────┼──────────┼──────────┼──────────┼────────────┘
          │        │          │          │          │
          ▼        ▼          ▼          ▼          ▼
      NVIDIA    OpenAI    Google      Claude    Ollama
    Endpoints   API      Gemini API   API      (local)
```

---

## 3. 統一 LLM Provider 介面

```typescript
// packages/inference-gateway/src/providers/llm-provider.ts

/**
 * 所有 LLM 供應商必須實作此介面
 * 這是我們的「語言」，與任何供應商無關
 */
export interface LLMProvider {
  readonly id: ProviderID;
  readonly name: string;

  /** 非串流完成 */
  complete(request: CompletionRequest): Promise<CompletionResponse>;

  /** 串流完成（Server-Sent Events）*/
  stream(request: CompletionRequest): AsyncIterable<CompletionDelta>;

  /** 列出此供應商支援的模型 */
  listModels(): Promise<ModelInfo[]>;

  /** 驗證設定是否有效（測試 API Key 等）*/
  validateConfig(config: ProviderConfig): Promise<ValidationResult>;

  /** 估算成本（用於路由決策）*/
  estimateCost(request: CompletionRequest): TokenCost;
}

// ─── 統一請求格式（OpenAI 相容，業界事實標準）────────────────

export interface CompletionRequest {
  model: string;                    // 邏輯模型名（與供應商無關，由 Router 翻譯）
  messages: Message[];
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
  // 其他通用參數...
}

export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface CompletionResponse {
  id: string;
  model: string;
  message: Message;
  usage: TokenUsage;
  finish_reason: 'stop' | 'length' | 'error';
  latency_ms: number;
  provider: ProviderID;             // 回傳實際使用的供應商（透明度）
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export type ProviderID = 'nvidia' | 'openai' | 'google' | 'anthropic' | 'ollama' | string;
```

---

## 4. 各供應商 Adapter 實作

### 4.1 NVIDIA Endpoints Adapter

```typescript
// providers/nvidia-adapter.ts
export class NVIDIAAdapter implements LLMProvider {
  readonly id = 'nvidia' as ProviderID;
  readonly name = 'NVIDIA Endpoints';

  // 邏輯模型名 → NVIDIA 實際模型 ID
  private modelMap: Record<string, string> = {
    'nemotron-super':  'nvidia/nemotron-3-super-120b-a12b',
    'llama-3.1-70b':   'nvidia/llama-3.1-70b-instruct',
    'llama-3.1-8b':    'nvidia/llama-3.1-8b-instruct',
    // 新增模型只加這裡
  };

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    const nvidiaModel = this.modelMap[request.model] ?? request.model;

    const resp = await fetch('https://integrate.api.nvidia.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: nvidiaModel,
        messages: request.messages,
        temperature: request.temperature ?? 0.7,
        max_tokens: request.max_tokens ?? 1024,
      }),
    });

    const data = await resp.json();
    return this.toUnified(data);  // 翻譯回我們的統一格式
  }

  private toUnified(nvidiaResp: any): CompletionResponse {
    return {
      id: nvidiaResp.id,
      model: nvidiaResp.model,
      message: nvidiaResp.choices[0].message,
      usage: {
        input_tokens:  nvidiaResp.usage.prompt_tokens,
        output_tokens: nvidiaResp.usage.completion_tokens,
        total_tokens:  nvidiaResp.usage.total_tokens,
      },
      finish_reason: nvidiaResp.choices[0].finish_reason,
      latency_ms: 0,   // 由外層 wrapper 填入
      provider: 'nvidia',
    };
  }
}
```

### 4.2 OpenAI Adapter（ChatGPT）

```typescript
// providers/openai-adapter.ts
export class OpenAIAdapter implements LLMProvider {
  readonly id = 'openai' as ProviderID;
  readonly name = 'OpenAI';

  private modelMap: Record<string, string> = {
    'gpt-4o':         'gpt-4o',
    'gpt-4o-mini':    'gpt-4o-mini',
    'gpt-4-turbo':    'gpt-4-turbo',
    'o1':             'o1',
    'o3-mini':        'o3-mini',
  };

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    // OpenAI 本身就是 OpenAI-compatible 格式，幾乎不需要翻譯
    const resp = await this.openaiClient.chat.completions.create({
      model: this.modelMap[request.model] ?? request.model,
      messages: request.messages,
      temperature: request.temperature,
      max_tokens: request.max_tokens,
    });

    return {
      id: resp.id,
      model: resp.model,
      message: resp.choices[0].message,
      usage: {
        input_tokens:  resp.usage?.prompt_tokens ?? 0,
        output_tokens: resp.usage?.completion_tokens ?? 0,
        total_tokens:  resp.usage?.total_tokens ?? 0,
      },
      finish_reason: resp.choices[0].finish_reason as any,
      latency_ms: 0,
      provider: 'openai',
    };
  }
}
```

### 4.3 Google Gemini Adapter

```typescript
// providers/google-adapter.ts
export class GoogleAdapter implements LLMProvider {
  readonly id = 'google' as ProviderID;
  readonly name = 'Google Gemini';

  private modelMap: Record<string, string> = {
    'gemini-2.5-pro':   'gemini-2.5-pro',
    'gemini-2.0-flash': 'gemini-2.0-flash',
    'gemini-1.5-pro':   'gemini-1.5-pro',
  };

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    const model = this.genAI.getGenerativeModel({
      model: this.modelMap[request.model] ?? request.model
    });

    // Google 格式與 OpenAI 不同，需要翻譯
    const googleMessages = this.toGoogleFormat(request.messages);
    const result = await model.generateContent(googleMessages);
    
    return this.toUnified(result, request.model);
  }

  private toGoogleFormat(messages: Message[]) {
    // System message 在 Google 中是 systemInstruction
    // User/Assistant 交替排列
    const systemMsg = messages.find(m => m.role === 'system');
    const chatHistory = messages
      .filter(m => m.role !== 'system')
      .map(m => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: m.content }],
      }));
    return { systemInstruction: systemMsg?.content, history: chatHistory };
  }
}
```

### 4.4 Anthropic Claude Adapter

```typescript
// providers/anthropic-adapter.ts
export class AnthropicAdapter implements LLMProvider {
  readonly id = 'anthropic' as ProviderID;
  readonly name = 'Anthropic Claude';

  private modelMap: Record<string, string> = {
    'claude-opus-4':    'claude-opus-4-6',
    'claude-sonnet-4':  'claude-sonnet-4-6',
    'claude-haiku-4':   'claude-haiku-4-5-20251001',
  };

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    // Anthropic 的 system message 是獨立欄位
    const systemMsg = request.messages.find(m => m.role === 'system')?.content;
    const chatMessages = request.messages.filter(m => m.role !== 'system');

    const resp = await this.anthropic.messages.create({
      model: this.modelMap[request.model] ?? request.model,
      max_tokens: request.max_tokens ?? 1024,
      system: systemMsg,
      messages: chatMessages.map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
    });

    return {
      id: resp.id,
      model: resp.model,
      message: { role: 'assistant', content: resp.content[0].text },
      usage: {
        input_tokens:  resp.usage.input_tokens,
        output_tokens: resp.usage.output_tokens,
        total_tokens:  resp.usage.input_tokens + resp.usage.output_tokens,
      },
      finish_reason: resp.stop_reason === 'end_turn' ? 'stop' : 'length',
      latency_ms: 0,
      provider: 'anthropic',
    };
  }
}
```

### 4.5 Ollama Adapter（本機 / 私有部署）

```typescript
// providers/ollama-adapter.ts
export class OllamaAdapter implements LLMProvider {
  readonly id = 'ollama' as ProviderID;
  readonly name = 'Ollama (Local)';

  constructor(private baseUrl: string) {}   // 可指向任意 Ollama 端點

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    // Ollama 支援 OpenAI-compatible API
    const resp = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: 'POST',
      body: JSON.stringify({
        model: request.model,
        messages: request.messages,
      }),
    });
    const data = await resp.json();
    return { ...this.toUnified(data), provider: 'ollama' };
  }
}
```

---

## 5. Provider Router（路由決策核心）

```typescript
// router/provider-router.ts

export class ProviderRouter {
  constructor(
    private providers: Map<ProviderID, LLMProvider>,
    private tenantConfigService: TenantConfigService,
    private modelCatalog: ModelCatalog,
  ) {}

  async route(request: CompletionRequest, context: RequestContext): Promise<LLMProvider> {
    const tenantConfig = await this.tenantConfigService.getInferenceConfig(context.tenantId);

    // 優先序 1：沙箱層級的明確指定
    if (context.sandboxProviderOverride) {
      return this.getProvider(context.sandboxProviderOverride);
    }

    // 優先序 2：租戶明確設定的供應商
    if (tenantConfig.preferredProvider) {
      return this.getProvider(tenantConfig.preferredProvider);
    }

    // 優先序 3：依模型名稱自動選擇
    const modelInfo = this.modelCatalog.resolve(request.model);
    if (modelInfo?.defaultProvider) {
      return this.getProvider(modelInfo.defaultProvider);
    }

    // 優先序 4：成本最低路由（可選策略）
    if (tenantConfig.routingStrategy === 'cost-optimized') {
      return this.cheapestAvailableProvider(request);
    }

    // 預設：使用平台預設供應商（可設定）
    return this.getProvider(this.defaultProvider);
  }

  private cheapestAvailableProvider(request: CompletionRequest): LLMProvider {
    return [...this.providers.values()]
      .filter(p => p.estimateCost(request) !== null)
      .sort((a, b) => a.estimateCost(request).perToken - b.estimateCost(request).perToken)[0];
  }
}
```

---

## 6. 模型目錄（Model Catalog）

將「邏輯模型名稱」與「供應商實作」解耦：

```typescript
// catalog/model-catalog.ts

export const MODEL_CATALOG: ModelCatalog = {
  // NVIDIA 模型
  'nemotron-super':    { provider: 'nvidia', realName: 'nvidia/nemotron-3-super-120b-a12b', tier: 'premium' },
  'llama-3.1-70b':     { provider: 'nvidia', realName: 'nvidia/llama-3.1-70b-instruct',    tier: 'standard',
                         // 同一個邏輯模型，也可以從其他供應商取得
                         alternatives: [{ provider: 'ollama', realName: 'llama3.1:70b' }] },

  // OpenAI 模型
  'gpt-4o':            { provider: 'openai', realName: 'gpt-4o',       tier: 'premium' },
  'gpt-4o-mini':       { provider: 'openai', realName: 'gpt-4o-mini',  tier: 'standard' },

  // Google 模型
  'gemini-2.5-pro':    { provider: 'google', realName: 'gemini-2.5-pro',   tier: 'premium' },
  'gemini-2.0-flash':  { provider: 'google', realName: 'gemini-2.0-flash', tier: 'budget' },

  // Anthropic 模型
  'claude-opus-4':     { provider: 'anthropic', realName: 'claude-opus-4-6',           tier: 'premium' },
  'claude-sonnet-4':   { provider: 'anthropic', realName: 'claude-sonnet-4-6',         tier: 'standard' },
  'claude-haiku-4':    { provider: 'anthropic', realName: 'claude-haiku-4-5-20251001', tier: 'budget' },

  // 本機模型（Ollama）
  'llama-3.2-3b-local': { provider: 'ollama', realName: 'llama3.2:3b', tier: 'local' },
  'qwen2.5-7b-local':   { provider: 'ollama', realName: 'qwen2.5:7b',  tier: 'local' },
};
```

---

## 7. 租戶層級設定

每個租戶可以設定自己的推理偏好：

```typescript
// 租戶推理設定（儲存於 PostgreSQL）
interface TenantInferenceConfig {
  // 供應商選擇
  preferredProvider: ProviderID | 'auto';       // 預設 'auto'（平台決定）
  routingStrategy: 'default' | 'cost-optimized' | 'latency-optimized';

  // BYOK：Bring Your Own Key（Enterprise 方案）
  providerApiKeys?: {
    openai?:     string;    // 加密存於 Vault
    google?:     string;
    anthropic?:  string;
    nvidia?:     string;
  };

  // 允許使用的模型清單（管理員可限制）
  allowedModels?: string[];   // null = 全部允許（依方案）

  // Fallback 設定
  fallbackProvider?: ProviderID;    // 主要供應商失敗時的備選
  fallbackEnabled: boolean;
}
```

### 範例：租戶設定 API

```
PATCH /api/v1/settings/inference
{
  "preferred_provider": "anthropic",
  "routing_strategy": "default",
  "fallback_provider": "openai",
  "fallback_enabled": true
}
```

---

## 8. 成本計算（跨供應商統一）

```typescript
// billing/cost-calculator.ts

const PRICING: Record<ProviderID, Record<string, TokenCost>> = {
  nvidia: {
    'nemotron-super':  { input: 0.008, output: 0.024 },   // per 1K tokens (USD)
    'llama-3.1-70b':   { input: 0.003, output: 0.006 },
  },
  openai: {
    'gpt-4o':          { input: 0.005, output: 0.015 },
    'gpt-4o-mini':     { input: 0.00015, output: 0.0006 },
    'o1':              { input: 0.015, output: 0.060 },
  },
  google: {
    'gemini-2.5-pro':  { input: 0.00125, output: 0.010 },
    'gemini-2.0-flash':{ input: 0.0001,  output: 0.0004 },
  },
  anthropic: {
    'claude-opus-4':   { input: 0.015, output: 0.075 },
    'claude-sonnet-4': { input: 0.003, output: 0.015 },
    'claude-haiku-4':  { input: 0.0008, output: 0.004 },
  },
  ollama: {
    // 本機推理：硬體成本由平台吸收，對租戶免費計量
    '*':               { input: 0, output: 0 },
  },
};

export function calculateCost(provider: ProviderID, model: string, usage: TokenUsage): number {
  const pricing = PRICING[provider]?.[model] ?? PRICING[provider]?.['*'] ?? { input: 0, output: 0 };
  return (usage.input_tokens / 1000 * pricing.input)
       + (usage.output_tokens / 1000 * pricing.output);
}
```

---

## 9. 整體架構圖（更新版）

```
租戶的沙箱（OpenClaw Agent）
     │
     │ POST /v1/chat/completions（OpenAI-compatible 格式）
     ▼
┌────────────────────────────────────────────────────────────────┐
│                    Inference Gateway                            │
│                                                                 │
│  ┌────────────┐  ┌────────────────┐  ┌──────────────────────┐ │
│  │JWT 驗證 +  │  │  Quota Check   │  │   Rate Limiter       │ │
│  │Tenant 上下文│  │  (Redis)       │  │   (Redis)            │ │
│  └─────┬──────┘  └───────┬────────┘  └──────────┬───────────┘ │
│        └─────────────────┼───────────────────────┘             │
│                          │                                      │
│  ┌───────────────────────▼──────────────────────────────────┐  │
│  │              Provider Router                              │  │
│  │   租戶設定 / 模型目錄 / 成本策略 / Fallback 規則          │  │
│  └──────┬────────┬──────────┬──────────┬──────────┬─────────┘  │
│         │        │          │          │          │             │
│    ┌────▼───┐ ┌──▼───┐ ┌───▼────┐ ┌───▼────┐ ┌──▼─────┐      │
│    │NVIDIA  │ │OpenAI│ │Google  │ │Claude  │ │Ollama  │      │
│    │Adapter │ │Adapt.│ │Adapter │ │Adapter │ │Adapter │      │
│    └────┬───┘ └──┬───┘ └───┬────┘ └───┬────┘ └──┬─────┘      │
│         │        │          │          │          │             │
│  ┌──────▼────────▼──────────▼──────────▼──────────▼─────────┐  │
│  │              Usage Meter（統一計量）                        │  │
│  │  記錄：provider / model / tokens / cost / latency          │  │
│  └──────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────│──────────────────────────────────┘
                              │ Kafka
                              ▼
                     Usage Consumer → PostgreSQL + Redis
```

---

## 10. 新增供應商的成本

未來加入新供應商（例如 Mistral、Cohere、Amazon Bedrock）：

```
需要的工作：
  1. 實作 XxxAdapter（implements LLMProvider）  ← 1-2 天
  2. 在 MODEL_CATALOG 加入模型對應              ← 30 分鐘
  3. 在 PRICING 加入定價                        ← 30 分鐘
  4. 撰寫 Adapter 測試                          ← 半天
  5. 在 Admin 介面開放此供應商（Feature Flag）   ← 1 小時

完全不需要修改：
  ✅ Inference Gateway 主流程
  ✅ Quota/Rate Limiter 邏輯
  ✅ Usage Meter
  ✅ API 端點格式
  ✅ 所有其他平台服務
  ✅ NemoClaw Adapter
```

---

## 11. 與 NemoClaw 的關係

NemoClaw 內建了自己的推理路由（`src/lib/inference/`），但在 SaaS 平台中：

```
採用策略：完全繞過 NemoClaw 的推理模組

原因：
  1. NemoClaw 的 inference module 是為單機用戶設計
     （無計量、無多租戶、無供應商抽象）
  2. SaaS 平台需要在 Gateway 層做計量、限速、計費
  3. 我們的 Provider Abstraction 比 NemoClaw 的更通用

做法：
  沙箱容器內的 OpenClaw Agent 設定推理 endpoint
  指向 Inference Gateway（而非直接指向外部供應商）

  INFERENCE_ENDPOINT=https://inference.nemoclaw.ai/v1
  （Inference Gateway 的 URL）

  OpenClaw 使用 OpenAI-compatible API 格式呼叫 →
  Inference Gateway 路由至正確的供應商 →
  計量、限速、計費全部在 Gateway 處理
```

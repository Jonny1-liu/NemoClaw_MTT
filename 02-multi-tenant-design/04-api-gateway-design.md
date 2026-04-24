# API Gateway 與公開 API 設計

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. API Gateway 架構

```
外部請求
    │
    ▼
┌───────────────────────────────────────────────────────┐
│                    API Gateway                         │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │                 Middleware Pipeline               │ │
│  │  1. TLS Termination                              │ │
│  │  2. DDoS / Rate Limit（IP 層）                   │ │
│  │  3. WAF Rules                                    │ │
│  │  4. JWT 驗證（Auth Service 公鑰）                │ │
│  │  5. Tenant Context 注入                          │ │
│  │  6. Per-Tenant Rate Limit（Quota 層）             │ │
│  │  7. Request Logging                              │ │
│  │  8. Request ID 注入                              │ │
│  └──────────────────────────────────────────────────┘ │
│                        │                              │
│  ┌─────────────────────▼─────────────────────────┐   │
│  │              路由規則（Route Rules）             │   │
│  │                                                 │   │
│  │  /api/v1/auth/*       → Auth Service           │   │
│  │  /api/v1/tenants/*    → Tenant Service         │   │
│  │  /api/v1/sandboxes/*  → Sandbox Orchestrator   │   │
│  │  /api/v1/inference/*  → Inference Gateway      │   │
│  │  /api/v1/policies/*   → Policy Engine          │   │
│  │  /api/v1/billing/*    → Billing Service        │   │
│  │  /api/v1/usage/*      → Usage Service          │   │
│  │  /ws/*                → WebSocket Proxy        │   │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘

技術選型：Kong Gateway 或 Envoy Proxy（CNCF 標準）
```

---

## 2. REST API 設計規範

### 2.1 URL 結構

```
基礎 URL：https://api.nemoclaw.ai/api/v{version}/

資源路徑規則：
  GET    /sandboxes              # 列出所有沙箱（當前租戶）
  POST   /sandboxes              # 建立沙箱
  GET    /sandboxes/{id}         # 取得特定沙箱
  PUT    /sandboxes/{id}         # 完整更新
  PATCH  /sandboxes/{id}         # 部分更新
  DELETE /sandboxes/{id}         # 刪除沙箱

  GET    /sandboxes/{id}/logs    # 查看沙箱日誌
  GET    /sandboxes/{id}/metrics # 查看沙箱指標
  POST   /sandboxes/{id}/start   # 啟動沙箱
  POST   /sandboxes/{id}/stop    # 停止沙箱
  POST   /sandboxes/{id}/snapshot # 建立快照

# 租戶 ID 由 JWT 提取，不出現在 URL 路徑中
# 避免 /tenants/{tenant_id}/sandboxes 的混亂結構
```

### 2.2 HTTP 狀態碼規範

| 狀態碼 | 使用場景 |
|--------|---------|
| 200 OK | 成功的 GET、PUT、PATCH |
| 201 Created | 成功的 POST（資源建立） |
| 202 Accepted | 非同步操作已接受 |
| 204 No Content | 成功的 DELETE |
| 400 Bad Request | 請求格式錯誤 |
| 401 Unauthorized | 未認證或 Token 無效 |
| 403 Forbidden | 無權限 |
| 404 Not Found | 資源不存在（或不可見） |
| 409 Conflict | 資源衝突（如名稱重複） |
| 422 Unprocessable | 業務邏輯錯誤 |
| 429 Too Many Requests | 速率限制 |
| 500 Internal Server Error | 伺服器錯誤 |
| 503 Service Unavailable | 服務暫時不可用 |

### 2.3 標準回應格式

```json
// 成功回應
{
  "data": { ... },
  "meta": {
    "request_id": "req-uuid-12345",
    "timestamp": "2026-04-16T10:30:00Z"
  }
}

// 列表回應（支援分頁）
{
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "pages": 8,
    "next_cursor": "cursor-abc123"  // cursor-based pagination
  },
  "meta": {
    "request_id": "req-uuid-12345"
  }
}

// 錯誤回應
{
  "error": {
    "code": "SANDBOX_QUOTA_EXCEEDED",
    "message": "You have reached the maximum number of sandboxes for your plan (5).",
    "details": {
      "current_count": 5,
      "plan_limit": 5,
      "upgrade_url": "https://nemoclaw.ai/billing/upgrade"
    }
  },
  "meta": {
    "request_id": "req-uuid-12345",
    "timestamp": "2026-04-16T10:30:00Z"
  }
}

// 非同步操作回應（202）
{
  "data": {
    "operation_id": "op-uuid-12345",
    "status": "pending",
    "type": "sandbox.create",
    "poll_url": "https://api.nemoclaw.ai/api/v1/operations/op-uuid-12345",
    "estimated_seconds": 30
  }
}
```

---

## 3. 核心 API 端點設計

### 3.1 沙箱管理 API

```yaml
# OpenAPI 3.0 定義（節錄）

paths:
  /api/v1/sandboxes:
    get:
      summary: 列出租戶的所有沙箱
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [running, stopped, creating, error]
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SandboxList'

    post:
      summary: 建立新沙箱
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [name, blueprint_id]
              properties:
                name:
                  type: string
                  pattern: '^[a-z0-9-]+$'
                  maxLength: 63
                blueprint_id:
                  type: string
                  format: uuid
                inference:
                  type: object
                  properties:
                    model:
                      type: string
                      enum: [nvidia/nemotron-3-super-120b, nvidia/llama-3.1-70b]
                    backend:
                      type: string
                      enum: [nvidia_endpoints, ollama]
                network_policy:
                  type: object
                  properties:
                    presets:
                      type: array
                      items:
                        type: string
                        enum: [slack, discord, github, jira, confluence]
      responses:
        '202':
          description: 沙箱建立已接受（非同步操作）
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AsyncOperation'
```

### 3.2 推理 API

```yaml
  /api/v1/inference/chat:
    post:
      summary: 向沙箱內的代理發送對話訊息
      x-rateLimit:
        perMinute: 60      # 依方案調整
        perDay: 10000
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [sandbox_id, messages]
              properties:
                sandbox_id:
                  type: string
                  format: uuid
                messages:
                  type: array
                  items:
                    type: object
                    properties:
                      role:
                        type: string
                        enum: [user, assistant, system]
                      content:
                        type: string
                stream:
                  type: boolean
                  default: false
                session_id:
                  type: string
                  description: 會話 ID，用於多輪對話
      responses:
        '200':
          description: 推理回應
          content:
            application/json:
              schema:
                type: object
                properties:
                  message:
                    type: object
                  usage:
                    type: object
                    properties:
                      input_tokens:
                        type: integer
                      output_tokens:
                        type: integer
                      total_tokens:
                        type: integer
```

### 3.3 用量與配額 API

```yaml
  /api/v1/usage:
    get:
      summary: 查詢推理用量統計
      parameters:
        - name: start_date
          in: query
          schema:
            type: string
            format: date
        - name: end_date
          in: query
          schema:
            type: string
            format: date
        - name: sandbox_id
          in: query
          schema:
            type: string
            format: uuid
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  total_tokens:
                    type: integer
                  total_requests:
                    type: integer
                  quota_used_percent:
                    type: number
                  breakdown_by_day:
                    type: array
                  breakdown_by_sandbox:
                    type: array

  /api/v1/quota:
    get:
      summary: 查詢當前配額狀態
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  sandboxes:
                    type: object
                    properties:
                      used: { type: integer }
                      limit: { type: integer }
                  tokens:
                    type: object
                    properties:
                      used: { type: integer }
                      limit: { type: integer }
                      reset_at: { type: string, format: datetime }
                  plan:
                    type: string
```

---

## 4. WebSocket API（即時串流）

### 4.1 沙箱日誌串流

```
連線：ws://api.nemoclaw.ai/ws/v1/sandboxes/{id}/logs
認證：ws://...?token=<access_token>

訊息格式（Server → Client）：
{
  "type": "log",
  "timestamp": "2026-04-16T10:30:00.123Z",
  "level": "info",
  "source": "openclaw",
  "message": "Agent received: hello"
}

{
  "type": "status_change",
  "previous": "running",
  "current": "stopped",
  "reason": "idle_timeout"
}
```

### 4.2 推理串流（Streaming）

```
POST /api/v1/inference/chat
Content-Type: application/json
Accept: text/event-stream

{
  "sandbox_id": "...",
  "messages": [...],
  "stream": true
}

# Server-Sent Events 回應：
data: {"delta": "Hello", "finish_reason": null}

data: {"delta": " World", "finish_reason": null}

data: {"delta": "", "finish_reason": "stop", "usage": {"total_tokens": 25}}

data: [DONE]
```

---

## 5. 速率限制策略

### 5.1 多層速率限制

```
Layer 1：IP 層（API Gateway）
  - 未認證請求：100 req/min/IP
  - 認證請求：1000 req/min/IP

Layer 2：用戶層（Per User）
  - 全 API：500 req/min
  - 推理 API：60 req/min

Layer 3：租戶層（Per Tenant，依方案）
  | 方案 | API/min | 推理/min | Tokens/月 |
  |------|---------|---------|---------|
  | Free | 100 | 10 | 100K |
  | Pro | 1000 | 60 | 1M |
  | Team | 5000 | 300 | 5M |
  | Enterprise | 自訂 | 自訂 | 自訂 |

速率限制回應：
  HTTP 429 Too Many Requests
  Headers:
    X-RateLimit-Limit: 60
    X-RateLimit-Remaining: 0
    X-RateLimit-Reset: 1745000000
    Retry-After: 45
```

### 5.2 Redis 速率限制實作（Sliding Window）

```lua
-- Redis Lua 腳本（Token Bucket 演算法）
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window * 1000)
local count = redis.call('ZCARD', key)

if count < limit then
  redis.call('ZADD', key, now, now)
  redis.call('EXPIRE', key, window)
  return {1, limit - count - 1}
else
  return {0, 0}
end
```

---

## 6. API 版本管理

```
版本策略：URL 路徑版本號

/api/v1/...   → 當前穩定版本
/api/v2/...   → 下一主要版本（當 v1 deprecation 開始後）

廢棄政策：
  1. 公告廢棄（至少 6 個月前）
  2. 回應 Header 提醒：
     Deprecation: "2027-01-01"
     Sunset: "2027-07-01"
     Link: <https://docs.nemoclaw.ai/migration/v1-to-v2>; rel="deprecation"
  3. 新版本 GA 後 6 個月正式棄用舊版
  4. Enterprise 客戶可申請延長支援
```

---

## 7. Webhook 系統

### 7.1 支援的事件

```
沙箱事件：
  sandbox.created      - 沙箱建立完成
  sandbox.started      - 沙箱啟動
  sandbox.stopped      - 沙箱停止
  sandbox.deleted      - 沙箱刪除
  sandbox.error        - 沙箱錯誤
  sandbox.snapshot.created - 快照建立

配額事件：
  quota.tokens.80_percent  - Token 用量達 80%
  quota.tokens.exceeded    - Token 配額耗盡
  quota.sandboxes.exceeded - 沙箱數量達上限

帳單事件：
  billing.invoice.created  - 發票生成
  billing.payment.failed   - 付款失敗
  billing.plan.changed     - 方案變更
```

### 7.2 Webhook 傳遞保證

```
重試策略：指數退避
  - 失敗後 1 分鐘重試
  - 再失敗後 5 分鐘重試
  - 再失敗後 30 分鐘重試
  - 最多重試 5 次，之後標記為失敗

驗證：
  - 每個 Webhook 端點有獨立的 secret
  - 請求包含 HMAC-SHA256 簽名：
    X-NemoClaw-Signature-256: sha256=<hash>
  - 請求包含時間戳（防重放）：
    X-NemoClaw-Timestamp: 1745000000
```

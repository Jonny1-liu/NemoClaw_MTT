# 計費與訂閱系統設計

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 訂閱方案設計

### 1.1 方案層級

```
┌────────────────────────────────────────────────────────────────────┐
│  Free                │  Pro          │  Team           │ Enterprise │
│  $0/月               │  $29/月       │  $99/用戶/月    │  自訂報價  │
├──────────────────────┼───────────────┼─────────────────┼────────────┤
│ 沙箱數：1             │ 沙箱數：5     │ 沙箱數：20/組織 │ 無限制     │
│ Tokens：100K/月       │ Tokens：1M/月 │ Tokens：5M/月   │ 自訂       │
│ 快照：3個             │ 快照：10個    │ 快照：50個      │ 無限制     │
│ Idle 休眠：30分鐘     │ 無休眠        │ 無休眠          │ 無休眠     │
│ 支援：社群           │ 支援：Email   │ 支援：優先Email │ 支援：SLA  │
│ SLA：-               │ SLA：99.9%    │ SLA：99.9%      │ SLA：99.95%│
│ SSO：-               │ SSO：-        │ SSO：-          │ SSO：✅    │
│ 模型：基礎            │ 模型：標準    │ 模型：進階      │ 全部       │
│ 多地區：-             │ 多地區：-     │ 多地區：-       │ 自訂       │
│ BYOK：-              │ BYOK：-       │ BYOK：-         │ BYOK：✅   │
└──────────────────────┴───────────────┴─────────────────┴────────────┘
```

### 1.2 使用量超額處理

```
Token 超額：
  - 75% 時：Email 警告
  - 90% 時：Email 警告 + Console 橫幅
  - 100% 時：
    Free：推理 API 返回 402，沙箱仍可運行（無推理）
    Pro/Team：自動購買超量包（可選），或返回 402
    Enterprise：依合約執行

沙箱數量超額：
  - 到達上限時：新建沙箱返回 422 + 升級提示
  - 不影響現有運行中的沙箱
```

---

## 2. 計費模型

### 2.1 計費維度

```
基礎訂閱費（固定）：
  - 依選擇方案按月或年收取
  - 年付 20% 折扣

用量計費（變動，僅 Pro+ 超額部分）：
  - Token 超額包：每 1M tokens = $5
  - 額外沙箱：每個沙箱/月 = $10（超過方案上限）

Enterprise 自訂：
  - 依 GPU 時數計費（Committed Use Discount）
  - Token 批量採購折扣
  - 自訂計量週期
```

### 2.2 推理成本計算

```
成本追蹤（平台內部，用於財務核算）：

NVIDIA Endpoints 定價（示意）：
  Nemotron-3-Super-120B：$0.008/1K input tokens, $0.024/1K output tokens

每個租戶的推理成本：
  cost = (input_tokens * 0.000008) + (output_tokens * 0.000024)
  
成本對比訂閱費用：
  Free (100K tokens/月)：最高成本 ≈ $2.4（平台吸收）
  Pro (1M tokens/月)：最高成本 ≈ $24（訂閱費 $29，利潤 $5+固定成本）
  
注意：實際訂閱費設計需要考慮 GPU 基礎設施、運維等固定成本。
```

---

## 3. 計費技術架構

### 3.1 計費系統整合（Stripe）

```
┌──────────────────────────────────────────────────────────────┐
│                    Billing Service                           │
│                                                              │
│  ┌──────────────────┐    ┌─────────────────────────────┐   │
│  │  Stripe SDK       │    │  Usage Meter                 │   │
│  │  ─ 訂閱管理       │    │  ─ Token 計數（Redis）        │   │
│  │  ─ 支付處理       │    │  ─ 沙箱時數計算              │   │
│  │  ─ 發票生成       │    │  ─ 每日彙總（PostgreSQL）    │   │
│  │  ─ Webhook 處理   │    │  ─ 月結算（Kafka event）    │   │
│  └──────────────────┘    └─────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Quota Enforcer                          │   │
│  │  ─ 即時配額檢查（Redis）                             │   │
│  │  ─ 超額處理邏輯                                      │   │
│  │  ─ 月初重置（Cron job）                              │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 計量事件流

```
推理請求完成
    │
    ▼
Inference Gateway 發布 Kafka 事件：
{
  "event": "inference.completed",
  "tenant_id": "abc123",
  "sandbox_id": "sb-xyz",
  "model": "nvidia/nemotron-3-super-120b",
  "input_tokens": 150,
  "output_tokens": 450,
  "latency_ms": 1200,
  "timestamp": "2026-04-16T10:30:00Z"
}
    │
    ▼
Usage Consumer 消費事件：
  1. 累計至 Redis：
     INCRBY tenant:abc123:tokens:2026-04 600
     INCRBY tenant:abc123:input_tokens:2026-04 150
     INCRBY tenant:abc123:output_tokens:2026-04 450
  
  2. 寫入 PostgreSQL（批次，每分鐘）：
     INSERT INTO tenant_abc123.inference_usage ...
  
  3. 觸發配額檢查（如超過警告閾值）
```

### 3.3 Stripe Webhook 處理

```javascript
// Stripe Webhook 事件處理

const handlers = {
  'customer.subscription.created': async (event) => {
    const subscription = event.data.object;
    await tenantService.updatePlan(subscription.metadata.tenant_id, {
      plan: subscription.metadata.plan,
      status: 'active',
      current_period_end: subscription.current_period_end
    });
    await quotaService.resetAndSetQuota(subscription.metadata.tenant_id);
  },

  'customer.subscription.deleted': async (event) => {
    const subscription = event.data.object;
    await tenantService.updatePlan(subscription.metadata.tenant_id, {
      plan: 'free',
      status: 'inactive'
    });
    await sandboxService.suspendAllSandboxes(subscription.metadata.tenant_id);
  },

  'invoice.payment_failed': async (event) => {
    const invoice = event.data.object;
    await notificationService.sendPaymentFailedEmail(invoice.customer_email);
    // 給 3 天寬限期
    await tenantService.scheduleGracePeriod(invoice.metadata.tenant_id, 3);
  },

  'customer.subscription.updated': async (event) => {
    const subscription = event.data.object;
    await tenantService.updatePlan(subscription.metadata.tenant_id, {
      plan: subscription.metadata.new_plan
    });
    await quotaService.updateQuota(subscription.metadata.tenant_id);
    // 若降級，檢查是否超過新方案限制
    await sandboxService.enforceNewLimits(subscription.metadata.tenant_id);
  }
};
```

---

## 4. 配額管理系統

### 4.1 配額資料結構（Redis）

```
# Token 配額（每月）
tenant:{tenant_id}:quota:tokens:limit          → 1000000
tenant:{tenant_id}:quota:tokens:used:{YYYY-MM} → 450000
tenant:{tenant_id}:quota:tokens:reset_at       → 2026-05-01T00:00:00Z

# 沙箱配額
tenant:{tenant_id}:quota:sandboxes:limit       → 5
tenant:{tenant_id}:quota:sandboxes:active      → 3

# 速率限制（每分鐘）
tenant:{tenant_id}:ratelimit:inference:rpm     → 60
tenant:{tenant_id}:ratelimit:inference:current → {sorted set with timestamps}
```

### 4.2 配額執行 Middleware

```go
func (m *QuotaMiddleware) CheckInferenceQuota(ctx context.Context, tenantID string, estimatedTokens int) error {
    // 1. 檢查月度 Token 配額
    limit, err := m.redis.Get(ctx, fmt.Sprintf("tenant:%s:quota:tokens:limit", tenantID))
    used, err := m.redis.Get(ctx, fmt.Sprintf("tenant:%s:quota:tokens:used:%s", tenantID, time.Now().Format("2006-01")))
    
    if int(used) + estimatedTokens > int(limit) {
        return &QuotaExceededError{
            QuotaType: "tokens",
            Used: int(used),
            Limit: int(limit),
            UpgradeURL: "https://nemoclaw.ai/billing/upgrade",
        }
    }

    // 2. 速率限制檢查（Sliding Window）
    allowed, remaining, err := m.rateLimiter.Allow(ctx, tenantID, "inference")
    if !allowed {
        return &RateLimitError{
            RetryAfter: 60 - remaining,
        }
    }

    return nil
}
```

---

## 5. 財務報表與分析

### 5.1 MRR（每月經常性收入）追蹤

```sql
-- MRR 計算查詢
SELECT 
    DATE_TRUNC('month', created_at) AS month,
    plan,
    COUNT(*) AS tenant_count,
    SUM(CASE plan
        WHEN 'pro' THEN 29
        WHEN 'team' THEN 99 * member_count
        ELSE 0
    END) AS mrr_usd
FROM subscriptions
WHERE status = 'active'
GROUP BY 1, 2;
```

### 5.2 用量成本分析

```sql
-- 每租戶的推理成本 vs 訂閱收入
SELECT
    t.id AS tenant_id,
    t.plan,
    s.monthly_revenue,
    SUM(u.total_tokens) * 0.000024 AS estimated_inference_cost,
    s.monthly_revenue - (SUM(u.total_tokens) * 0.000024) AS gross_margin
FROM tenants t
JOIN subscriptions s ON t.id = s.tenant_id
JOIN (
    SELECT tenant_id, 
           SUM(input_tokens + output_tokens) AS total_tokens
    FROM inference_usage
    WHERE created_at >= DATE_TRUNC('month', NOW())
    GROUP BY tenant_id
) u ON t.id = u.tenant_id
GROUP BY t.id, t.plan, s.monthly_revenue
ORDER BY gross_margin ASC;
```

---

## 6. 發票與稅務

```
發票生成：
  - 透過 Stripe 自動生成 PDF 發票
  - 每月計費週期結束後自動寄送
  - 支援統一編號（B2B 台灣發票）
  - Enterprise 支援自訂發票抬頭

稅務處理：
  - 使用 Stripe Tax 自動計算各地區稅率
  - 台灣 VAT 5%
  - 歐盟 VAT MOSS 合規
  - 美國 Sales Tax（依州別）
  - Enterprise 支援免稅證明上傳
```

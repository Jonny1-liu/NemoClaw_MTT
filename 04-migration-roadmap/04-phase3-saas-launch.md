# Phase 3：SaaS 商業上線（GA Launch）

> 時程：2026 Q4（約 12 週）| 目標：完整自助服務 + 商業化上線

---

## 目標

Phase 3 在 Phase 2 的多租戶核心上，加入完整的自助服務體驗、計費系統和 Web Console，使平台能夠獨立運營並產生收入。

**完成標準（Definition of Done）：**
- 用戶可完全自助完成：註冊 → 訂閱 → 使用 → 管理
- 計費系統準確（誤差 < 0.01%）
- Web Console 功能完整
- SLA 可保證（99.9% uptime）
- 公開 Beta 用戶超過 100 人

---

## Week 1-3：Web Console 完整實作

### 技術棧

```
前端：Next.js 14 (App Router) + TypeScript
UI Library：shadcn/ui + Tailwind CSS
狀態管理：React Query (TanStack Query)
即時功能：WebSocket (xterm.js terminal)
圖表：Recharts / Apache ECharts
部署：Vercel 或 CloudFront + S3
```

### 主要頁面實作順序

**Week 1：認證 + 基礎框架**

```typescript
// app/layout.tsx - 全局布局
// app/(auth)/login/page.tsx - 登入頁
// app/(auth)/signup/page.tsx - 註冊頁（含方案選擇）
// app/(app)/layout.tsx - Console 側邊欄布局
// app/(app)/dashboard/page.tsx - 儀表板首頁
```

**Week 2：沙箱管理頁面**

```typescript
// app/(app)/sandboxes/page.tsx - 沙箱列表
// app/(app)/sandboxes/new/page.tsx - 建立精靈（3步驟）
//   Step 1: 選擇名稱 + 藍圖
//   Step 2: 設定推理後端 + 模型
//   Step 3: 網路政策設定
// app/(app)/sandboxes/[id]/page.tsx - 沙箱詳細頁
// app/(app)/sandboxes/[id]/terminal/page.tsx - 網頁終端

// 網頁終端實作（xterm.js）
'use client';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';

export function SandboxTerminal({ sandboxId }: { sandboxId: string }) {
  const termRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const term = new Terminal({ cursorBlink: true, theme: DARK_THEME });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(termRef.current!);
    fitAddon.fit();
    
    // 取得連線 Token
    const { token } = await getConnectionToken(sandboxId);
    
    // 建立 WebSocket
    const ws = new WebSocket(
      `${WS_URL}/ws/v1/sandboxes/${sandboxId}/terminal?token=${token}`
    );
    
    ws.onmessage = (e) => term.write(e.data);
    term.onData((data) => ws.send(data));
    
    return () => { ws.close(); term.dispose(); };
  }, [sandboxId]);
  
  return <div ref={termRef} className="w-full h-full" />;
}
```

**Week 3：設定 + 帳單頁面**

```
- app/(app)/settings/page.tsx         - 一般設定
- app/(app)/settings/members/page.tsx - 成員管理
- app/(app)/settings/tokens/page.tsx  - API Token 管理
- app/(app)/billing/page.tsx          - 帳單 + 訂閱管理
- app/(app)/usage/page.tsx            - 用量統計
```

---

## Week 4-6：計費系統整合

### 任務 1：Stripe 完整整合

```typescript
// 計費服務核心邏輯

class BillingService {
    async createSubscription(tenantId: string, planId: string, paymentMethodId: string) {
        // 1. 建立 Stripe Customer（如不存在）
        let customer = await this.getOrCreateStripeCustomer(tenantId);
        
        // 2. 附加付款方式
        await stripe.paymentMethods.attach(paymentMethodId, {
            customer: customer.id
        });
        
        // 3. 建立訂閱
        const subscription = await stripe.subscriptions.create({
            customer: customer.id,
            items: [{ price: PRICE_IDS[planId] }],
            payment_settings: {
                payment_method_types: ['card'],
                save_default_payment_method: 'on_subscription'
            },
            metadata: {
                tenant_id: tenantId,
                plan: planId
            }
        });
        
        // 4. 更新 DB
        await this.db.updateTenantPlan(tenantId, planId);
        await this.quotaService.resetQuota(tenantId, planId);
        
        return subscription;
    }
    
    async handleWebhook(event: Stripe.Event) {
        switch (event.type) {
            case 'customer.subscription.updated':
                await this.onSubscriptionUpdated(event.data.object);
                break;
            case 'invoice.payment_failed':
                await this.onPaymentFailed(event.data.object);
                break;
            case 'customer.subscription.deleted':
                await this.onSubscriptionDeleted(event.data.object);
                break;
        }
    }
}
```

### 任務 2：用量超額自動購買

```typescript
// 超額 Token 自動購買（Pro+ 方案選項）
async function handleTokenOverage(tenantId: string, additionalTokens: number) {
    const tenant = await getTenant(tenantId);
    
    if (!tenant.autoOverage) {
        // 拒絕推理請求
        throw new QuotaExceededError('Monthly token quota exhausted');
    }
    
    // 計算超額包數量（每包 1M tokens = $5）
    const packCount = Math.ceil(additionalTokens / 1_000_000);
    
    // 建立 Stripe Invoice Item（立即計費）
    await stripe.invoiceItems.create({
        customer: tenant.stripeCustomerId,
        unit_amount: 500,  // $5
        quantity: packCount,
        currency: 'usd',
        description: `Token overage pack (${packCount}M tokens)`
    });
    
    // 更新配額
    await quotaService.addTokens(tenantId, packCount * 1_000_000);
}
```

---

## Week 7-8：公開 Beta 準備

### 任務 1：狀態頁面

```
建立 status.nemoclaw.ai（使用 Statuspage.io 或自建）

顯示：
  - API 狀態
  - 沙箱服務狀態
  - 推理服務狀態
  - 各區域狀態
  - 過去 90 天的 Uptime 歷史
  - 維護公告

事件管理：
  - 事件發生時自動更新（AlertManager webhook）
  - 事件解決後自動關閉
  - 訂閱 Email/SMS 通知
```

### 任務 2：文件完善

```
docs.nemoclaw.ai（從現有 Sphinx 文件擴展）

新增文件：
  - 快速開始（Web Console 版）
  - API 參考（OpenAPI 3.0 + Swagger UI）
  - 多租戶架構說明
  - 安全最佳實踐
  - 計費 FAQ
  - CLI v2 遷移指南（從單機版遷移）
  - SDK 文件（Python、Node.js）
```

### 任務 3：Beta 用戶計畫

```
Beta 計畫：
  - 建立等候名單（waitlist form）
  - 前 100 名 Beta 用戶免費 Pro 方案 3 個月
  - 每週 Beta 用戶問卷
  - Discord 社群（使用現有 NemoClaw Discord）
  - Bug bounty 計畫（GitHub Security Advisory）
```

---

## Week 9-10：安全與合規

### 任務 1：SOC 2 Type I 準備

```
必要控制項：
  CC1: 控制環境（組織架構、職責）
  CC2: 通訊與資訊（政策、程序文件）
  CC3: 風險評估（風險識別與管理）
  CC6: 邏輯和實體存取控制
  CC7: 系統操作（監控、變更管理）
  CC8: 變更管理（SDLC、部署流程）
  CC9: 風險緩解（供應商管理）

時程：
  SOC 2 Type I：GA 前取得（約 2-3 個月）
  SOC 2 Type II：GA 後 6 個月開始審計（12 個月觀察期）
```

### 任務 2：GDPR 合規

```
歐洲用戶資料處理：
  - 資料處理合約（DPA）範本
  - 隱私政策（完整 GDPR 版本）
  - 資料主體請求（DSR）流程：
    - 資料存取請求
    - 資料刪除請求（Right to be Forgotten）
    - 資料可攜性

技術措施：
  - 歐洲資料確保存放於 eu-west-1
  - 資料最小化原則（只收集必要資料）
  - Cookie 同意管理（Cookiebot 或類似方案）
```

---

## Week 11-12：正式上線（GA）

### 上線檢查清單

```
技術就緒：
  [ ] Load testing 通過（100 租戶並行，API p99 < 500ms）
  [ ] 滲透測試通過（無嚴重/高風險漏洞）
  [ ] DR 演練通過（主區域故障可在 60 分鐘內恢復）
  [ ] 計費系統對帳準確（誤差 < 0.01%）
  [ ] 備份恢復演練通過
  [ ] On-call 流程就緒（PagerDuty 設定完成）

業務就緒：
  [ ] 服務條款（ToS）+ 隱私政策（PP）法律審核通過
  [ ] 退款政策確定
  [ ] 客服流程建立（Email + Discord）
  [ ] 計費 FAQ 文件完整
  [ ] 行銷材料（Product Hunt、部落格文章、社群媒體）

合規就緒：
  [ ] SOC 2 Type I 報告取得
  [ ] GDPR 合規文件就緒
  [ ] 安全漏洞揭露流程（已有 NVIDIA PSIRT 流程）
```

### 上線策略

```
軟上線（Week 11）：
  - 靜默開放自助服務（不主動宣傳）
  - 監控所有指標
  - Beta 用戶自動轉為付費帳號（保留免費期）

正式上線（Week 12）：
  - Product Hunt 發佈
  - 部落格文章：「NemoClaw SaaS：讓 AI 代理更安全的雲端平台」
  - 發送 Discord / GitHub 社群公告
  - NVIDIA 官方 Blog 交叉推廣
  - Hacker News Show HN
```

---

## Post-Launch：Enterprise 功能路線圖（Q1 2027+）

```
優先序 1（GA 後 1-2 個月）：
  - SSO（SAML 2.0）整合
  - SCIM 自動同步
  - BYOK（Bring Your Own NVIDIA API Key）
  - 自訂網路政策 UI

優先序 2（GA 後 3-4 個月）：
  - 多區域部署（eu-west-1）
  - 99.95% SLA Enterprise 方案
  - 專屬帳戶管理（TAM）

優先序 3（GA 後 5-6 個月）：
  - GPU 本機推理（Ollama on DGX）
  - 私有部署選項（On-premise）
  - 進階藍圖市場（Blueprint Marketplace）
  - 合作夥伴計畫（Reseller Program）
```

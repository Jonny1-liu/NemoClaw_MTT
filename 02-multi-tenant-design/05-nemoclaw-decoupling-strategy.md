# NemoClaw 解耦策略：Alpha 版快速迭代下的開發隔離設計

> 文件版本：v1.0 | 撰寫日期：2026-04-21

---

## 1. 核心問題與解法

### 1.1 問題

NemoClaw 目前是 Alpha 版，官方明確聲明：

> *"Interfaces, APIs, and behavior may change without notice as we iterate on the design."*

若直接依賴 NemoClaw 的 CLI 指令、Blueprint YAML 格式、或 OpenShell API，每次 NemoClaw 升版都可能破壞平台程式碼，造成大量修改工作。

### 1.2 解法：Anti-Corruption Layer（ACL）模式

```
╔══════════════════════════════════════════════════════════════╗
║              NemoClaw SaaS 平台（我們開發的）                 ║
║                                                              ║
║  Auth  Tenant  Billing  API GW  Console  Inference  Policy  ║
║    │       │       │       │       │         │         │    ║
║    └───────┴───────┴───────┴───────┴─────────┴─────────┘    ║
║                            │                                 ║
║              ┌─────────────▼─────────────┐                  ║
║              │   Sandbox Service（我們）   │                  ║
║              │   定義「沙箱」的抽象介面    │                  ║
║              └─────────────┬─────────────┘                  ║
║                            │                                 ║
║              ┌─────────────▼─────────────┐                  ║
║              │  NemoClaw Adapter（ACL）   │  ← 唯一需要      ║
║              │  翻譯我們的模型 ↔ NemoClaw │    跟著升版的地方 ║
║              └─────────────┬─────────────┘                  ║
╚════════════════════════════│═════════════════════════════════╝
                             │
             ╔═══════════════▼════════════════╗
             ║   NemoClaw（外部，不改動）       ║
             ║   v0.x → v1.x → v2.x ...       ║
             ╚════════════════════════════════╝
```

**核心原則：平台所有元件只與「我們自己定義的 Sandbox 抽象介面」溝通，絕不直接呼叫 NemoClaw CLI 或 API。**

---

## 2. 可完全獨立開發的元件（不碰 NemoClaw）

以下元件與 NemoClaw 零耦合，可立即平行開發：

```
優先度  元件                      說明
──────────────────────────────────────────────────────────────
 P0    Auth Service              用戶登入/JWT/SSO → 與 NemoClaw 無關
 P0    Tenant Service            租戶 CRUD/設定/配額 → 純業務邏輯
 P0    API Gateway               路由/JWT 驗證/Rate Limit → 純基礎設施
 P0    Infrastructure (IaC)     Terraform/K8s/VPC → 純基礎設施
 P0    CI/CD Pipeline           GitHub Actions/ArgoCD → 純工具鏈
 P0    Database Layer           PostgreSQL Schema-per-tenant → 純資料
 P0    Quota Service            Redis 計量/限額 → 純業務邏輯
 P1    Billing Service          Stripe 訂閱/計費 → 純商業邏輯
 P1    Inference Gateway        直接呼叫 NVIDIA Endpoints（跳過 NemoClaw）
 P1    Web Console              Next.js UI → 呼叫我們的 API
 P1    CLI v2 骨架               指令解析框架 → 呼叫我們的 API
 P1    Observability Stack      Prometheus/Loki/Grafana → 純基礎設施
 P1    Notification Service     Email/Webhook → 純業務邏輯
 P2    Policy Engine            建立政策資料模型（先不套用到 NemoClaw）
```

**結論：約 80% 的開發工作完全不需要接觸 NemoClaw。**

---

## 3. Anti-Corruption Layer 設計

### 3.1 Sandbox 抽象介面（我們定義，不變）

```typescript
// packages/sandbox-service/src/ports/sandbox-backend.ts
// 這是「我們的語言」，不是 NemoClaw 的語言

export interface SandboxBackend {
  // 生命週期
  create(spec: SandboxSpec): Promise<SandboxHandle>;
  start(handle: SandboxHandle): Promise<void>;
  stop(handle: SandboxHandle): Promise<void>;
  destroy(handle: SandboxHandle): Promise<void>;

  // 狀態查詢
  getStatus(handle: SandboxHandle): Promise<SandboxStatus>;
  getLogs(handle: SandboxHandle, opts: LogOptions): AsyncIterable<LogLine>;

  // 安全政策
  applyNetworkPolicy(handle: SandboxHandle, policy: NetworkPolicy): Promise<void>;

  // 連線
  openTerminal(handle: SandboxHandle): Promise<TerminalSession>;

  // 快照
  createSnapshot(handle: SandboxHandle): Promise<SnapshotRef>;
  restoreSnapshot(handle: SandboxHandle, ref: SnapshotRef): Promise<void>;
}

// 我們的領域模型（永遠不會因 NemoClaw 升版而改變）
export interface SandboxSpec {
  tenantId: string;
  sandboxId: string;
  name: string;
  resources: ResourceRequirements;
  inferenceConfig: InferenceConfig;
  securityProfile: SecurityProfile;
}

export interface SandboxStatus {
  phase: 'creating' | 'running' | 'stopping' | 'stopped' | 'error';
  startedAt?: Date;
  errorMessage?: string;
  resourceUsage?: ResourceUsage;
}
```

### 3.2 NemoClaw Adapter（ACL 實作，唯一需要跟著升版的地方）

```typescript
// packages/sandbox-service/src/adapters/nemoclaw-adapter.ts
// 這層翻譯我們的模型 ↔ 當前 NemoClaw 的 CLI/API

import { SandboxBackend, SandboxSpec, SandboxHandle, SandboxStatus } from '../ports/sandbox-backend';
import { execNemoclaw } from './nemoclaw-cli-runner';

export class NemoclawAdapter implements SandboxBackend {

  async create(spec: SandboxSpec): Promise<SandboxHandle> {
    // 將我們的 SandboxSpec 翻譯成 NemoClaw 當前版本的命令格式
    // 若 NemoClaw 升版改了 CLI 格式，只需修改這裡
    const blueprintYaml = this.toBlueprintYaml(spec);
    
    // 目前 NemoClaw 的方式（CLI 呼叫）
    await execNemoclaw(['sandbox', 'create',
      '--name', spec.name,
      '--blueprint', blueprintYaml,
      '--tenant', spec.tenantId
    ]);

    return { externalId: spec.sandboxId, adapter: 'nemoclaw' };
  }

  async applyNetworkPolicy(handle: SandboxHandle, policy: NetworkPolicy): Promise<void> {
    // 翻譯我們的 NetworkPolicy 模型 → NemoClaw 當前的 YAML 格式
    const policyYaml = this.toPolicyYaml(policy);
    
    await execNemoclaw(['policy', 'apply',
      '--sandbox', handle.externalId,
      '--policy', policyYaml
    ]);
  }

  // ─── 翻譯方法（版本升級時只改這裡）──────────────────
  private toBlueprintYaml(spec: SandboxSpec): string {
    // v0.x NemoClaw Blueprint 格式
    return yaml.stringify({
      sandbox: {
        image: 'nemoclaw-sandbox:latest',
        resources: {
          cpu: spec.resources.cpu,
          memory: spec.resources.memory,
        },
        security: {
          capabilities: 'DROP_ALL',
          seccomp: 'runtime/default',
          landlock: 'enabled',
        },
        inference: {
          model: spec.inferenceConfig.model,
          endpoint: spec.inferenceConfig.endpoint,
        }
      }
    });
  }

  private toPolicyYaml(policy: NetworkPolicy): string {
    // 翻譯至 NemoClaw 當前的政策 YAML 格式
    return yaml.stringify({
      allow: policy.allow.map(r => ({
        domain: r.domain,
        ports: r.ports,
      })),
      deny_all_other: true,
    });
  }
}
```

### 3.3 未來升版時的操作

當 NemoClaw 升至新版本，只需：

```
1. 查看 NemoClaw release notes / CHANGELOG
2. 只修改 nemoclaw-adapter.ts 中的翻譯方法
3. 所有其他服務完全不需要動

示例：假設 NemoClaw v1.0 改了 Blueprint 格式
  Before（v0.x）:  sandbox.resources.cpu
  After（v1.0）:   sandbox.compute.vcpu

  只改 toBlueprintYaml() 中的 mapping：
  cpu: spec.resources.cpu  →  vcpu: spec.resources.cpu
  
  Auth/Tenant/Billing/Console 完全不受影響。
```

---

## 4. 推理 Gateway 的特殊處理

推理服務有一個更好的選擇：**直接呼叫 NVIDIA Endpoints，完全跳過 NemoClaw 的推理路由**。

```
NemoClaw 現有路徑（有耦合）：
  沙箱 → NemoClaw Plugin（inference module）→ NVIDIA Endpoints

SaaS 平台路徑（獨立）：
  沙箱 → Inference Gateway（我們的服務）→ NVIDIA Endpoints
                   ↑
          直接使用 NVIDIA Endpoints API，
          不依賴 NemoClaw 的 inference module
```

**優點：**
- 不受 NemoClaw inference module 的 API 變更影響
- 可以在 Gateway 層加入計量、速率限制、多租戶配額
- 可以支援 NemoClaw 目前不支援的模型或後端

---

## 5. 開發優先序（依照耦合度分類）

### 立即可開始（零耦合）

```
Sprint 1-2（現在就可以開始）:
  ✅ Terraform 基礎設施（VPC/EKS/RDS/Redis）
  ✅ Auth Service（Keycloak 安裝 + 設定）
  ✅ Tenant Service（PostgreSQL Schema + API）
  ✅ API Gateway（Kong/Envoy 基礎路由）
  ✅ CI/CD Pipeline（GitHub Actions + ArgoCD）
  ✅ Observability Stack（Prometheus/Loki/Grafana）

Sprint 3-4（平行進行）:
  ✅ Billing Service（Stripe 整合）
  ✅ Quota Service（Redis 計量邏輯）
  ✅ Inference Gateway（直接對接 NVIDIA Endpoints）
  ✅ Web Console 骨架（Next.js + 路由 + 認證流程）
  ✅ CLI v2 框架（Commander 結構 + API Client）
  ✅ Notification Service（Email 範本）
```

### 需要少量 NemoClaw 整合（低耦合）

```
Sprint 5-6（建立 ACL 後開始）:
  ⚠️  Sandbox Orchestrator（透過 NemoclawAdapter）
      → 先用 Mock Adapter 開發，完成後接真實 NemoClaw
  ⚠️  Policy Engine（先建資料模型，後整合套用）
  ⚠️  Snapshot Service（先建 S3 架構，後接 NemoClaw 快照格式）
```

### 最後整合（高耦合，但已隔離）

```
Sprint 7-8（整合測試）:
  🔧  NemoclawAdapter 完整實作
  🔧  End-to-end 測試（真實沙箱建立流程）
  🔧  NemoClaw 版本鎖定與相容性測試
```

---

## 6. Mock Adapter 策略（讓開發不被 NemoClaw 阻塞）

在 NemoClaw Adapter 完成前，使用 **Mock Adapter** 讓整個平台可以完整運行：

```typescript
// packages/sandbox-service/src/adapters/mock-adapter.ts
// 用於開發和測試，不需要真實 NemoClaw

export class MockSandboxAdapter implements SandboxBackend {
  private sandboxes = new Map<string, SandboxStatus>();

  async create(spec: SandboxSpec): Promise<SandboxHandle> {
    console.log(`[MOCK] Creating sandbox: ${spec.name}`);
    
    // 模擬 30 秒的建立時間
    setTimeout(() => {
      this.sandboxes.set(spec.sandboxId, {
        phase: 'running',
        startedAt: new Date(),
      });
    }, 30_000);

    this.sandboxes.set(spec.sandboxId, { phase: 'creating' });
    return { externalId: spec.sandboxId, adapter: 'mock' };
  }

  async getStatus(handle: SandboxHandle): Promise<SandboxStatus> {
    return this.sandboxes.get(handle.externalId) ?? { phase: 'error', errorMessage: 'Not found' };
  }

  async getLogs(handle: SandboxHandle): AsyncIterable<LogLine> {
    // 返回模擬日誌
    const mockLogs = [
      { timestamp: new Date(), level: 'info', message: '[MOCK] OpenClaw agent started' },
      { timestamp: new Date(), level: 'info', message: '[MOCK] Inference endpoint configured' },
    ];
    for (const log of mockLogs) yield log;
  }

  // 其他方法也返回模擬結果...
}
```

**使用環境變數切換：**

```typescript
// packages/sandbox-service/src/container.ts
const adapter: SandboxBackend = 
  process.env.SANDBOX_BACKEND === 'mock'
    ? new MockSandboxAdapter()
    : new NemoclawAdapter();

export const sandboxService = new SandboxService(adapter);
```

```bash
# 開發環境：用 Mock
SANDBOX_BACKEND=mock npm run dev

# 整合測試：用真實 NemoClaw
SANDBOX_BACKEND=nemoclaw npm run test:integration
```

---

## 7. 版本相容性管理

### 7.1 NemoClaw 版本鎖定

```json
// packages/sandbox-service/package.json
{
  "dependencies": {
    "nemoclaw": "0.3.x"  // 明確鎖定版本範圍
  },
  "config": {
    "nemoclaw": {
      "minVersion": "0.3.0",
      "maxVersion": "0.4.0",  // 超出此範圍的版本需要 Adapter 評估
      "testedVersions": ["0.3.1", "0.3.2"]
    }
  }
}
```

### 7.2 升版測試自動化

```yaml
# .github/workflows/nemoclaw-upgrade-test.yml
# 當 NemoClaw 有新版本時，自動測試相容性

name: NemoClaw Compatibility Test
on:
  schedule:
    - cron: '0 9 * * 1'  # 每週一自動檢查

jobs:
  check-nemoclaw-updates:
    runs-on: ubuntu-latest
    steps:
      - name: Check latest NemoClaw version
        run: |
          LATEST=$(npm view nemoclaw version)
          CURRENT=$(cat .nemoclaw-version)
          echo "Current: $CURRENT, Latest: $LATEST"
          
          if [ "$LATEST" != "$CURRENT" ]; then
            echo "NEW_VERSION=$LATEST" >> $GITHUB_ENV
          fi

      - name: Run adapter compatibility tests
        if: env.NEW_VERSION != ''
        run: |
          npm install nemoclaw@$NEW_VERSION
          npm run test:adapter  # 只跑 Adapter 層的測試
          
      - name: Create issue if tests fail
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              title: `NemoClaw ${process.env.NEW_VERSION} compatibility check failed`,
              body: `Adapter tests failed for NemoClaw ${process.env.NEW_VERSION}. 
                     Review the [test results](${process.env.GITHUB_RUN_URL}).
                     Only NemoclawAdapter needs to be updated.`
            })
```

---

## 8. 進度追蹤：哪些工作不依賴 NemoClaw

```
可立即開始的工作（不需等待 NemoClaw 穩定）：

基礎設施（不依賴 NemoClaw）          預估週數
─────────────────────────────────────────────
  AWS 帳號 + IAM + Terraform           1週
  EKS 叢集 + Istio + 基礎工具           1週
  PostgreSQL HA + Redis Cluster         1週
  Kafka + Vault + S3 + ECR              1週
                                        共 4 週

服務開發（不依賴 NemoClaw）           預估週數
─────────────────────────────────────────────
  Auth Service（Keycloak）              1週
  Tenant Service + 資料庫 Schema        2週
  API Gateway + 認證中介層              1週
  Quota Service + Rate Limiter          1週
  Inference Gateway（直接呼叫 NVIDIA）   2週
  Billing Service（Stripe）             2週
  Notification Service                  1週
  Observability Stack                   1週
                                        共 11 週

前端（不依賴 NemoClaw）               預估週數
─────────────────────────────────────────────
  Web Console 框架 + 認證流程            1週
  儀表板 + 沙箱管理 UI（搭配 Mock）      2週
  設定 + 帳單 + 用量 UI                  2週
  CLI v2 框架（搭配 Mock Adapter）       1週
                                        共 6 週

小計：以上工作可並行，最短 ~6-8 週完成
（需要 NemoClaw 的部份：Sandbox Orchestrator + Policy Engine，預估 3-4 週）

NemoClaw 依賴項目占總工作量比例：約 15-20%
```

---

## 9. 重要提醒

### 9.1 不要複製貼上 NemoClaw 的內部邏輯

雖然 NemoClaw 是開源（Apache 2.0），但為了避免耦合，**不應直接複製其 TypeScript 模組到平台程式碼中**。

正確做法是：透過 CLI 呼叫或（未來）REST API 呼叫，在 Adapter 層封裝。

### 9.2 持續監控 NemoClaw 的 Discussions 和 PR

```
值得追蹤的 NemoClaw GitHub 活動：
  - Issues 中標記為 "breaking-change" 的項目
  - PR 中修改 blueprint/ 或 commands/ 目錄的變更
  - Release notes 中的 BREAKING CHANGES 區塊
  - Discord 中 maintainer 關於 API 穩定性的討論

訂閱方式：
  Watch → Custom → Releases（最低干擾）
  或訂閱 Discord #announcements 頻道
```

### 9.3 考慮貢獻 NemoClaw 上游

若在整合過程中發現需要某個 NemoClaw 功能（如 REST API、更好的輸出格式），可以：
1. 在 NemoClaw GitHub Discussion 提出需求
2. 貢獻 PR（CONTRIBUTING.md 有明確流程）
3. 若功能對 SaaS 場景有普遍需求，NVIDIA 可能直接採納

這樣做的好處是：未來升版時，我們需要的功能已在上游，Adapter 需要維護的程式碼更少。

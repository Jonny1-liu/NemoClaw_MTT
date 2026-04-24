# SaaS 平台服務設計

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 沙箱編排服務（Sandbox Orchestration Service）

### 1.1 服務職責

NemoClaw 的核心差異化能力來自安全沙箱。編排服務是將本機 CLI 邏輯轉化為雲端 API 服務的最關鍵元件。

```
現有（CLI）：
  nemoclaw onboard → 本機 openshell CLI → Docker + k3s（local）

目標（SaaS）：
  API 請求 → Sandbox Orchestrator → Kubernetes API → 租戶 Namespace
```

### 1.2 核心功能

```go
// 沙箱服務 Interface（Go）

type SandboxService interface {
    // 生命週期
    Create(ctx context.Context, req *CreateSandboxRequest) (*AsyncOperation, error)
    Start(ctx context.Context, sandboxID string) (*AsyncOperation, error)
    Stop(ctx context.Context, sandboxID string) (*AsyncOperation, error)
    Delete(ctx context.Context, sandboxID string) (*AsyncOperation, error)

    // 查詢
    Get(ctx context.Context, sandboxID string) (*Sandbox, error)
    List(ctx context.Context, tenantID string, opts *ListOptions) (*SandboxList, error)

    // 快照
    CreateSnapshot(ctx context.Context, sandboxID string) (*Snapshot, error)
    RestoreSnapshot(ctx context.Context, sandboxID, snapshotID string) (*AsyncOperation, error)
    ListSnapshots(ctx context.Context, sandboxID string) ([]*Snapshot, error)

    // 連線
    GetConnectionToken(ctx context.Context, sandboxID, userID string) (string, error)

    // 監控
    GetMetrics(ctx context.Context, sandboxID string) (*SandboxMetrics, error)
    GetLogs(ctx context.Context, sandboxID string, opts *LogOptions) (io.Reader, error)
}
```

### 1.3 沙箱建立流程（雲端版）

```
POST /api/v1/sandboxes
         │
         ▼
1. 驗證請求（JWT + 租戶 quota 檢查）
         │
         ▼
2. 建立 DB 記錄（status: CREATING）
         │
         ▼
3. 發布 Kafka 事件：sandbox.create.requested
         │
         ▼
4. Sandbox Orchestrator Worker 消費事件
   ├── 4a. 生成沙箱 K8s 資源配置
   │       （從藍圖模板 + 租戶設定生成 Pod Spec）
   ├── 4b. 從 Vault 取得租戶推理 API Key
   ├── 4c. 建立 K8s Secret（推理憑證）
   ├── 4d. 建立 Pod（含安全設定：Landlock/seccomp）
   ├── 4e. 等待 Pod Ready（健康檢查）
   └── 4f. 套用網路政策
         │
         ▼
5. 更新 DB 記錄（status: RUNNING）
         │
         ▼
6. 發布 Webhook 事件：sandbox.created
         │
         ▼
7. API 輪詢回應 / Push 通知（SSE/WebSocket）
```

### 1.4 沙箱 Pod 規格（K8s）

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sandbox-{sandbox-id}
  namespace: tenant-{tenant-id}
  labels:
    app: nemoclaw-sandbox
    sandbox-id: "{sandbox-id}"
    tenant-id: "{tenant-id}"
    plan: "pro"
  annotations:
    nemoclaw.ai/blueprint-version: "1.2.0"
    nemoclaw.ai/created-at: "2026-04-16T10:00:00Z"
spec:
  serviceAccountName: sandbox-runner
  automountServiceAccountToken: false

  # 安全設定（繼承自現有 NemoClaw）
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault

  containers:
  - name: openclaw-agent
    image: nemoclaw-sandbox:{version}
    resources:
      requests:
        cpu: "250m"
        memory: "512Mi"
      limits:
        cpu: "2"
        memory: "4Gi"
    env:
    - name: NEMOCLAW_TENANT_ID
      value: "{tenant-id}"
    - name: NEMOCLAW_SANDBOX_ID
      value: "{sandbox-id}"
    - name: INFERENCE_API_KEY
      valueFrom:
        secretKeyRef:
          name: tenant-inference-secret
          key: api_key
    - name: INFERENCE_ENDPOINT
      value: "https://integrate.api.nvidia.com/v1"
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    volumeMounts:
    - name: state
      mountPath: /home/agent/.nemoclaw
    - name: tmp
      mountPath: /tmp

  volumes:
  - name: state
    persistentVolumeClaim:
      claimName: sandbox-{sandbox-id}-state
  - name: tmp
    emptyDir: {}

  # 防止 Pod 逃脫至其他租戶
  topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        tenant-id: "{tenant-id}"
```

---

## 2. 推理 Gateway 服務

### 2.1 功能架構

```
Sandbox (Agent)
    │
    │ 推理請求（攜帶內部 JWT）
    ▼
┌─────────────────────────────────────────────────┐
│              Inference Gateway                   │
│                                                  │
│  ┌───────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Request  │  │   Quota &   │  │  Request  │ │
│  │  Validator│  │ Rate Limiter│  │  Enricher │ │
│  └─────┬─────┘  └──────┬──────┘  └─────┬─────┘ │
│        └───────────────┼───────────────┘        │
│                        │                        │
│  ┌─────────────────────▼────────────────────┐   │
│  │          Model Router                     │   │
│  │  ┌─────────────┐  ┌────────────────────┐ │   │
│  │  │NVIDIA Endpts│  │  Ollama (if allowed)│ │   │
│  │  └─────────────┘  └────────────────────┘ │   │
│  └───────────────────────────────────────────┘   │
│                        │                        │
│  ┌─────────────────────▼────────────────────┐   │
│  │         Usage Meter                       │   │
│  │  (Kafka → Token Counter → DB + Redis)     │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 2.2 推理 Key 管理策略

```
策略一：平台代管 Key（推薦）
  - 平台使用自己的 NVIDIA API Key 呼叫 Endpoints
  - 用量成本包含在訂閱費用中
  - 優勢：用戶無需管理 API Key；可做大量折扣
  - 需要：嚴格的租戶用量配額執行

策略二：BYOK（Bring Your Own Key）
  - 用戶提供自己的 NVIDIA API Key
  - Platform 代理請求（注入正確 Key）
  - Key 存放於 Vault（加密）
  - 優勢：企業用戶已有 NVIDIA 合約
  - 適用：Enterprise 方案

混合策略（最終方案）：
  - Free/Pro/Team → Platform Key（包含在訂閱費中）
  - Enterprise → 可選 Platform Key 或 BYOK
```

---

## 3. 狀態管理服務（State Manager）

### 3.1 快照系統設計

```
快照類型：
  1. Auto Snapshot（自動）
     - 代理 idle 後 5 分鐘觸發
     - 沙箱計畫停止前觸發
     - 配額：Free=3個, Pro=10個, Team=50個

  2. Manual Snapshot（手動）
     - 用戶透過 API/Console 觸發
     - 可加上標籤和描述

快照資料內容：
  - OpenClaw 代理狀態（memory、context、工具快取）
  - 環境變數（加密）
  - 已安裝工具列表
  - 設定文件

快照儲存：
  - 儲存至 S3：tenants/{tenant-id}/snapshots/{snapshot-id}.tar.gz.enc
  - 使用租戶專屬 KMS Key 加密
  - 版本標籤：snapshot-metadata.json
```

### 3.2 狀態同步機制

```
持久狀態（PostgreSQL）：
  - 沙箱設定
  - 代理配置
  - 快照 metadata

揮發狀態（Redis）：
  - 沙箱 runtime 狀態（running/stopped）
  - 活躍連線計數
  - 推理速率限制計數器

檔案狀態（S3）：
  - 代理記憶/上下文快照
  - 工作目錄備份
  - 日誌歸檔
```

---

## 4. 網路政策引擎

### 4.1 動態政策更新（無停機）

```
傳統方式（需重啟）：
  修改政策 YAML → 重啟沙箱 → 套用新政策

目標（動態更新）：
  API 更新政策 → Policy Engine 計算差異 → 
  eBPF 程式動態更新規則 → 沙箱無感知更新
```

### 4.2 政策 API

```json
// GET /api/v1/sandboxes/{id}/policies
{
  "inherited_from_tenant": {
    "allow": [
      {"domain": "*.nvidia.com", "ports": [443]},
      {"domain": "*.googleapis.com", "ports": [443]}
    ],
    "deny": []
  },
  "sandbox_overrides": {
    "allow": [
      {"domain": "api.slack.com", "ports": [443]}
    ]
  },
  "effective_policy": {
    "allow": [
      {"domain": "*.nvidia.com", "ports": [443]},
      {"domain": "*.googleapis.com", "ports": [443]},
      {"domain": "api.slack.com", "ports": [443]}
    ],
    "deny_all_other": true
  }
}

// POST /api/v1/sandboxes/{id}/policies/presets
{
  "preset": "slack",
  "action": "enable"
}
```

---

## 5. Web Console 設計

### 5.1 頁面結構

```
nemoclaw.ai/
├── /                  # 行銷首頁
├── /login             # 登入
├── /signup            # 註冊
└── /app/              # Console（需登入）
    ├── /dashboard     # 總覽（用量、狀態摘要）
    ├── /sandboxes      # 沙箱列表
    │   ├── /new        # 建立新沙箱精靈
    │   └── /{id}       # 沙箱詳細頁
    │       ├── /terminal    # 網頁終端（WebSocket）
    │       ├── /logs        # 日誌查看
    │       ├── /metrics     # 指標圖表
    │       ├── /snapshots   # 快照管理
    │       └── /policies    # 網路政策設定
    ├── /blueprints     # 藍圖管理
    ├── /settings       # 租戶設定
    │   ├── /members    # 成員管理
    │   ├── /api-tokens # API Token 管理
    │   ├── /sso        # SSO 設定（Enterprise）
    │   └── /security   # 安全設定
    ├── /usage          # 用量統計
    └── /billing        # 帳單管理
```

### 5.2 網頁終端（Web Terminal）

```
技術實作：xterm.js + WebSocket

連線流程：
  1. Console 請求臨時 Connection Token（TTL 5分鐘）
     GET /api/v1/sandboxes/{id}/connection-token
  
  2. WebSocket 連線（攜帶 Connection Token）
     ws://api.nemoclaw.ai/ws/v1/sandboxes/{id}/terminal?token=xxx
  
  3. Gateway 驗證 Token 並建立雙向 pipe 至沙箱容器
     （kubectl exec 的 API 封裝）

  4. 連線最大時間：2小時（Free）/ 8小時（Pro+）
```

---

## 6. 通知服務

### 6.1 通知通道

| 通道 | 使用場景 | 設定位置 |
|------|---------|---------|
| Email | 帳單、安全告警、重要事件 | 帳號設定 |
| Webhook | 沙箱事件、配額警告 | Console → Webhooks |
| In-app | 即時通知（Console UI） | 自動啟用 |
| Slack Integration | 沙箱事件推送至 Slack | Console → Integrations |

### 6.2 通知範本（Email）

```
配額警告（80%）：
  主旨：[NemoClaw] 您的 Token 使用量已達 80%
  內文：
    您的租戶「{tenant_name}」本月已使用 {used_tokens:,}/{limit_tokens:,} tokens（{percent}%）。
    
    如需繼續使用，請升級方案或等待下月重置。
    
    [升級方案] [查看用量]

沙箱錯誤：
  主旨：[NemoClaw] 沙箱 "{sandbox_name}" 發生錯誤
  內文：
    您的沙箱在 {timestamp} 發生錯誤。
    錯誤訊息：{error_message}
    
    [查看日誌] [重新啟動]
```

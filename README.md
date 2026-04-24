# NemoClaw 多租戶 SaaS 平台設計文件

> 建立日期：2026-04-16 | 參考來源：https://github.com/NVIDIA/NemoClaw

本文件集為 **NVIDIA NemoClaw** 從單機版（Standalone）轉型為**多租戶 SaaS 平台**的完整架構設計與遷移規劃。

---

## 文件結構

```
NemoClaw_MTT/
├── README.md                          ← 本文件（入口點）
│
├── 01-analysis/                       ← 現況分析
│   ├── 01-project-overview.md         # 專案概覽、技術生態、功能模組
│   ├── 02-current-architecture.md     # 架構深度解析（元件、資料流、安全層）
│   └── 03-gap-analysis.md             # 差距分析（17個面向的完整評估）
│
├── 02-multi-tenant-design/            ← 多租戶架構設計
│   ├── 01-architecture-overview.md    # 目標架構總覽（服務清單、通訊、安全）
│   ├── 02-tenant-isolation-strategy.md # 隔離模型（Silo/Pool/Shared 混合策略）
│   ├── 03-auth-and-authorization.md   # IAM 設計（JWT、RBAC、SSO、MFA）
│   └── 04-api-gateway-design.md       # API 設計規範（REST、WebSocket、Webhook）
│
├── 03-saas-platform/                  ← SaaS 平台服務設計
│   ├── 01-platform-services.md        # 核心服務（Sandbox Orchestrator、推理 GW）
│   ├── 02-billing-and-subscription.md # 計費系統（訂閱方案、Stripe、配額管理）
│   ├── 03-observability.md            # 可觀測性（Metrics/Logs/Traces/告警）
│   └── 04-deployment-topology.md      # 部署拓撲（多區域、K8s、IaC、DR）
│
├── 04-migration-roadmap/              ← 遷移路線圖
│   ├── 01-migration-strategy.md       # 遷移策略（Strangler Fig + 複用分析）
│   ├── 02-phase1-foundation.md        # Phase 1：基礎建設（12週）
│   ├── 03-phase2-multi-tenant.md      # Phase 2：多租戶核心（12週）
│   └── 04-phase3-saas-launch.md       # Phase 3：SaaS 商業上線（12週）
│
└── 05-diagrams/                       ← 架構圖（Mermaid 格式）
    ├── 01-current-architecture.mermaid      # 現有單機架構圖
    ├── 02-target-saas-architecture.mermaid  # 目標 SaaS 架構圖
    ├── 03-tenant-isolation-model.mermaid    # 租戶隔離模型圖
    ├── 04-migration-roadmap-timeline.mermaid # 遷移甘特圖
    └── 05-request-flow.mermaid              # 推理請求流程時序圖
```

> **Mermaid 圖表查看**：使用 [Mermaid Live Editor](https://mermaid.live) 或支援 Mermaid 的 Markdown 閱讀器（VS Code、GitHub、Notion）開啟 `.mermaid` 檔案。

---

## 核心發現摘要

### NemoClaw 是什麼

NVIDIA NemoClaw（Alpha，2026年3月）是一個在 NVIDIA OpenShell 安全沙箱中運行 OpenClaw AI 代理的開源參考堆疊。核心特色是**多層安全隔離**（Landlock + seccomp + 網路命名空間），但目前設計為**單一用戶、本機運行**。

### 單機版核心限制

| 限制面向 | 說明 |
|---------|------|
| 無認證/授權 | 完全依賴本機 OS 用戶，無 API 認證 |
| 本機狀態 | 所有設定、憑證、快照均存於本機檔案 |
| 無多租戶概念 | 一台機器 = 一個用戶環境 |
| CLI 唯一介面 | 無 REST API、無 Web UI |
| 無計費機制 | 完全開源免費，無用量追蹤 |
| 無水平擴展 | 綁定單機，無法跨機器調度 |

### 多租戶 SaaS 轉型關鍵決策

1. **隔離模型**：採用三層混合策略（Free=Shared, Pro/Team=Pool, Enterprise=Silo）
2. **資料隔離**：PostgreSQL Schema-per-tenant（強隔離 + 可接受的管理成本）
3. **認證方案**：Keycloak（OIDC/OAuth 2.0，支援 SSO 和 Social Login）
4. **API 設計**：REST API First，WebSocket 支援串流和終端
5. **計費方案**：Stripe 訂閱 + 用量超額自動計費
6. **技術棧**：沿用 TypeScript（CLI/Web）+ Go（後端服務）+ Kubernetes

### 現有程式碼可直接複用

NemoClaw 的安全機制、推理路由、藍圖系統均可作為 SaaS 平台的技術基礎，**減少約 30-40% 的重新開發工作**：

- 沙箱安全設定（Landlock/seccomp） → Sandbox Orchestrator Pod Spec
- 網路政策預設（policies/presets/） → Policy Engine 初始政策
- SSRF 防禦邏輯（ssrf.ts） → API Gateway 層面
- 推理路由邏輯（inference module） → Inference Gateway 核心
- CLI 介面設計 → CLI v2（改呼叫 API）

---

## 遷移路線圖摘要

```
2026 Q2          2026 Q3          2026 Q4          2027 Q1+
    │                │                │                │
    ▼                ▼                ▼                ▼
Phase 1          Phase 2          Phase 3          Post-Launch
基礎建設          多租戶核心        SaaS 上線         Enterprise
(12週)           (12週)           (12週)

Key Milestones:
  Week 8:  私測 Alpha（5-10 位用戶）
  Week 14: 50+ 租戶並行測試
  Week 20: 公開 Beta
  Week 24: GA 正式上線
  Q1 2027: SSO + 多區域 + Enterprise
```

---

## 訂閱方案規劃

| 方案 | 月費 | 沙箱數 | Tokens/月 | 特色 |
|------|------|--------|-----------|------|
| **Free** | $0 | 1 | 100K | 入門體驗，30分鐘 idle 休眠 |
| **Pro** | $29 | 5 | 1M | 無休眠，Email 支援 |
| **Team** | $99/用戶 | 20/組織 | 5M | 多人協作，優先支援 |
| **Enterprise** | 自訂 | 無限制 | 自訂 | SSO、BYOK、99.95% SLA |

---

## 技術棧總覽

| 層次 | 技術選型 |
|------|---------|
| 前端 | Next.js 14 + TypeScript + shadcn/ui |
| API Gateway | Kong Gateway 或 Envoy Proxy |
| 認證 | Keycloak（OIDC/OAuth 2.0） |
| 後端服務 | Go（高性能服務）+ Node.js/Fastify（業務服務）|
| 沙箱編排 | Kubernetes（EKS）+ Istio |
| 資料庫 | PostgreSQL HA（Schema-per-tenant）|
| 快取/限流 | Redis Cluster |
| 事件串流 | Apache Kafka 或 NATS JetStream |
| 機密管理 | HashiCorp Vault |
| 物件儲存 | AWS S3（跨區域複製）|
| 計費 | Stripe API |
| 可觀測性 | Prometheus + Loki + Tempo + Grafana |
| IaC | Terraform + ArgoCD（GitOps）|
| 容器 | Docker + AWS ECR |
| CI/CD | GitHub Actions + ArgoCD |

---

## 主要風險

1. **安全沙箱雲端相容性**：Landlock 需要 Linux Kernel 5.13+，需要確認 EKS 節點支援
2. **NVIDIA Endpoints 速率限制**：SaaS 規模需要提前洽談 Volume 合約
3. **多租戶性能隔離**：需要嚴格的 ResourceQuota + 公平排程
4. **合規要求**：SOC 2 Type I 至少需 2-3 個月，應在 Phase 2 即開始準備

---

*本文件集基於 NemoClaw GitHub Repository（https://github.com/NVIDIA/NemoClaw）的公開資訊，以及多租戶 SaaS 架構設計最佳實踐所撰寫。*

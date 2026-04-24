# 多租戶平台架構總覽

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 設計原則

在設計 NemoClaw SaaS 多租戶平台時，遵循以下核心原則：

1. **Security by Design** — 安全從架構層開始，非事後加補
2. **Tenant Isolation First** — 任何設計決策首先考慮租戶隔離
3. **API First** — 所有功能均透過 API 暴露，UI 是 API 的消費者
4. **Eventual Consistency** — 分散式系統中接受最終一致性
5. **Defense in Depth** — 多層安全防護，不依賴單一防線
6. **Graceful Degradation** — 部分故障時系統仍可部分服務
7. **Observable by Default** — 所有服務原生支援指標、日誌、追蹤

---

## 2. 目標架構全景圖

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          外部用戶 / 開發者                                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTPS
                    ┌───────────▼──────────────┐
                    │     CDN + DDoS 防護        │
                    │  (CloudFront / Cloudflare) │
                    └───────────┬──────────────┘
                                │
                    ┌───────────▼──────────────┐
                    │      API Gateway Layer    │
                    │  ┌────────┐ ┌──────────┐ │
                    │  │  WAF   │ │Rate Limit│ │
                    │  └────────┘ └──────────┘ │
                    └───────────┬──────────────┘
                                │
          ┌─────────────────────┼───────────────────────┐
          │                     │                       │
          ▼                     ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   Web Console   │   │   Public API    │   │   CLI (updated) │
│  (React/Next.js)│   │  (REST/GraphQL) │   │  (calls API)    │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
         ┌─────────────────────▼─────────────────────────────────┐
         │                  控制平面（Control Plane）               │
         │  ┌───────────┐  ┌────────────┐  ┌──────────────────┐  │
         │  │  Auth     │  │  Tenant    │  │   Billing &      │  │
         │  │  Service  │  │  Service   │  │   Quota Service  │  │
         │  └───────────┘  └────────────┘  └──────────────────┘  │
         └─────────────────────┬─────────────────────────────────┘
                               │
         ┌─────────────────────▼─────────────────────────────────┐
         │                  資料平面（Data Plane）                  │
         │  ┌────────────────┐  ┌────────────┐  ┌─────────────┐  │
         │  │  Sandbox       │  │  Inference │  │  Policy     │  │
         │  │  Orchestrator  │  │  Gateway   │  │  Engine     │  │
         │  └───────┬────────┘  └─────┬──────┘  └──────┬──────┘  │
         └──────────┼────────────────┼───────────────┼──────────┘
                    │                │               │
         ┌──────────▼────────────────▼───────────────▼──────────┐
         │              租戶基礎設施層（Tenant Infra）              │
         │                                                        │
         │  Tenant A NS          Tenant B NS        Tenant C NS  │
         │  ┌──────────────┐    ┌────────────────┐              │
         │  │ Sandbox Pod 1 │    │ Sandbox Pod 1  │     ...     │
         │  │ Sandbox Pod 2 │    │ Sandbox Pod 2  │             │
         │  └──────────────┘    └────────────────┘              │
         │                                                        │
         │              Kubernetes Cluster(s)                    │
         └────────────────────────────────────────────────────────┘
                               │
         ┌─────────────────────▼─────────────────────────────────┐
         │                  共享基礎設施層                          │
         │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
         │  │PostgreSQL│  │  Redis   │  │   S3 / Object Store  │ │
         │  │(per-tenant│  │(Rate/    │  │   (snapshots, logs)  │ │
         │  │  schema) │  │ Session) │  │                      │ │
         │  └──────────┘  └──────────┘  └──────────────────────┘ │
         │  ┌──────────────────────────────────────────────────┐  │
         │  │          HashiCorp Vault（Secrets Management）    │  │
         │  └──────────────────────────────────────────────────┘  │
         │  ┌──────────────────────────────────────────────────┐  │
         │  │   Observability Stack（Prometheus + Loki + Tempo）│  │
         │  └──────────────────────────────────────────────────┘  │
         └────────────────────────────────────────────────────────┘
```

---

## 3. 服務清單

### 3.1 控制平面服務

| 服務名稱 | 主要職責 | 技術選型 | 優先級 |
|---------|---------|---------|------|
| **Auth Service** | 用戶認證、JWT 簽發、SSO | Keycloak / Auth0 | P0 |
| **Tenant Service** | 租戶 CRUD、設定管理、配額 | Node.js/Fastify | P0 |
| **Billing Service** | 訂閱、發票、用量計費 | Stripe API + 自建 | P1 |
| **Quota Service** | 資源配額追蹤與執行 | Go + Redis | P0 |
| **Notification Service** | Email、Webhook 通知 | Node.js + SES | P2 |

### 3.2 資料平面服務

| 服務名稱 | 主要職責 | 技術選型 | 優先級 |
|---------|---------|---------|------|
| **Sandbox Orchestrator** | 沙箱 CRUD、生命週期管理 | Go + K8s client | P0 |
| **Inference Gateway** | 推理代理、速率限制、用量計量 | Go + NGINX | P0 |
| **Policy Engine** | 網路政策管理、動態更新 | Go + OPA | P1 |
| **State Manager** | 快照、狀態同步 | Go + PostgreSQL | P1 |
| **Blueprint Service** | 藍圖模板管理 | Node.js/Fastify | P2 |

### 3.3 前端

| 元件 | 主要職責 | 技術選型 | 優先級 |
|-----|---------|---------|------|
| **Web Console** | 管理 UI | Next.js + TypeScript | P1 |
| **Admin Portal** | 平台管理 | Next.js + TypeScript | P2 |
| **CLI v2** | 呼叫後端 API 的命令列工具 | Node.js（現有基礎） | P0 |

---

## 4. 服務間通訊

### 4.1 同步通訊（REST/gRPC）

```
使用場景：需要即時回應的操作
  - API Gateway → 各後端服務
  - Web Console → API Gateway
  - 服務間同步查詢（Tenant 驗證、Quota 檢查）

協議：
  - 外部 API：REST（JSON）+ OpenAPI 3.0
  - 內部服務間：gRPC（protobuf）
  - Service Mesh：Istio mTLS 確保服務間安全
```

### 4.2 非同步通訊（Event-Driven）

```
使用場景：可延遲處理的操作
  - 沙箱建立完成 → 發送歡迎 Email
  - 用量超額 → 觸發計費事件
  - 政策更新 → 非同步推送至沙箱
  - 快照完成 → 更新狀態資料庫

消息佇列：Apache Kafka 或 NATS JetStream
事件格式：CloudEvents 1.0
```

---

## 5. 資料架構

### 5.1 資料庫策略

| 資料類型 | 資料庫 | 隔離策略 |
|---------|-------|---------|
| 租戶 metadata | PostgreSQL | Schema-per-tenant |
| 用戶帳號 | PostgreSQL | 單一 schema，tenant_id 欄位 |
| 沙箱狀態 | PostgreSQL | Schema-per-tenant |
| 推理用量紀錄 | PostgreSQL（時序分區） | Table partition by tenant |
| 代理快照 | S3 / Object Store | Bucket prefix per tenant |
| 工作階段 / 快取 | Redis Cluster | Key prefix per tenant |
| 網路政策 | PostgreSQL + etcd | Namespace per tenant |
| 日誌 | Loki（或 Elasticsearch） | Label-based tenant filter |
| 指標 | Prometheus（Thanos） | Tenant label filter |

### 5.2 資料保護

```
靜態加密：
  - PostgreSQL：TDE（Transparent Data Encryption）
  - S3：SSE-KMS（per-tenant KMS key）
  - Redis：Encryption at rest（Redis Enterprise）

傳輸加密：
  - 所有外部通訊：TLS 1.3
  - 服務間通訊：Istio mTLS

憑證管理：
  - HashiCorp Vault：Dynamic secrets、API Key 加密存放
  - KMS（AWS KMS / Google KMS）：DEK 管理
```

---

## 6. 安全架構

### 6.1 Zero Trust 原則

```
原則：永不信任，始終驗證
  1. 所有請求必須附帶有效 JWT
  2. 服務間通訊使用 mTLS（Istio）
  3. 最小權限原則（每個服務僅有必要的 K8s RBAC）
  4. 網路政策預設 deny-all，白名單開放
  5. 定期輪換所有 secrets
```

### 6.2 防護層次

```
Layer 7: 應用安全
  ├── Input validation（所有 API 端點）
  ├── Output encoding（防 XSS）
  ├── CSRF 防護
  └── SQL Injection 防護（Parameterized queries）

Layer 6: 身份驗證
  ├── JWT 驗證（RS256）
  ├── Token 有效期短（15 分鐘 access token）
  ├── Refresh token rotation
  └── MFA 支援

Layer 5: 授權
  ├── RBAC（Tenant Owner/Admin/Dev/Viewer）
  ├── Resource-level permission check
  └── Tenant boundary enforcement

Layer 4: API Gateway
  ├── Rate limiting（per IP + per tenant）
  ├── Request size limits
  ├── WAF 規則
  └── Bot 防護

Layer 3: 沙箱隔離（繼承現有 NemoClaw）
  ├── Landlock
  ├── seccomp
  ├── Network namespace
  └── Capability drops

Layer 2: Kubernetes
  ├── Pod Security Standards (restricted)
  ├── NetworkPolicy（default deny + whitelist）
  ├── RBAC（per-namespace service accounts）
  └── OPA Gatekeeper（admission control）

Layer 1: 基礎設施
  ├── VPC / 私有網路
  ├── Security Groups / Firewall rules
  ├── DDoS 防護
  └── WAF（外圍）
```

---

## 7. 可用性設計

### 7.1 SLA 目標

| 方案 | SLA | RTO | RPO |
|------|-----|-----|-----|
| Free | 99.5% | 4 小時 | 24 小時 |
| Pro | 99.9% | 1 小時 | 1 小時 |
| Team | 99.9% | 30 分鐘 | 15 分鐘 |
| Enterprise | 99.95% | 15 分鐘 | 5 分鐘 |

### 7.2 HA 設計

```
控制平面 HA：
  - API Gateway：3 副本 + Load Balancer
  - Auth Service：3 副本（無狀態）
  - Tenant Service：3 副本 + 健康檢查
  - 資料庫：PostgreSQL HA（Primary + 2 Replica + PgBouncer）

資料平面 HA：
  - Sandbox Orchestrator：3 副本（Leader Election）
  - Inference Gateway：3+ 副本（HPA）
  - K8s 控制平面：3 etcd + 3 API Server

多區域：
  - Active-Active（Pro+：兩個主區域）
  - Active-Passive（Enterprise：専屬區域 + 熱備用）
```

---

## 8. 擴展性設計

### 8.1 水平擴展

```
無狀態服務（可直接水平擴展）：
  - API Gateway
  - Auth Service
  - Inference Gateway
  - Policy Engine

有狀態服務（需要特殊處理）：
  - Sandbox Orchestrator：Leader Election + Consistent Hashing
  - State Manager：分片（per-tenant shard）
  - 資料庫：Read Replicas + Connection Pooling

自動伸縮：
  - K8s HPA（Horizontal Pod Autoscaler）
  - KEDA（事件驅動伸縮，如 Kafka lag）
  - Cluster Autoscaler（節點自動伸縮）
```

### 8.2 多租戶容量規劃

```
Free 方案：
  - 最多 1 個沙箱
  - 100K tokens/月
  - 沙箱 idle 後 30 分鐘自動休眠

Pro 方案（$29/月）：
  - 最多 5 個沙箱
  - 1M tokens/月
  - 無 idle 休眠

Team 方案（$99/月/user）：
  - 最多 20 個沙箱/組織
  - 5M tokens/月
  - 優先排程

Enterprise（自訂定價）：
  - 無限沙箱（資源配額可談）
  - 自訂 token 用量
  - 專屬基礎設施選項
  - SLA 合約
```

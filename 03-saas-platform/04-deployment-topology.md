# 部署拓撲設計

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 多區域部署策略

### 1.1 區域選擇原則

```
初期（Phase 1）：單一區域
  → AWS us-east-1（美東，低延遲連接 NVIDIA Endpoints）

成長期（Phase 2）：雙區域 Active-Active
  → AWS us-east-1（美東主區）
  → AWS eu-west-1（歐洲，GDPR 合規）

成熟期（Phase 3）：多區域
  → AWS us-east-1（美東）
  → AWS eu-west-1（歐洲）
  → AWS ap-southeast-1（亞太，台灣用戶低延遲）
  → NVIDIA DGX Cloud（高階 GPU 推理，Enterprise）

用戶路由策略：
  - GeoDNS：根據用戶地理位置路由至最近區域
  - 資料主權：歐洲租戶資料僅存放於 eu-west-1
  - Enterprise：可指定專屬區域
```

### 1.2 完整部署架構

```
Internet
    │
    ▼ GeoDNS
┌──────────────────────────────────────────────────────────┐
│                    Global (CloudFront/Cloudflare)         │
│  ─ CDN（Web Console 靜態資源）                            │
│  ─ WAF（OWASP 規則 + DDoS 防護）                         │
│  ─ SSL 終止                                              │
└─────────────────┬────────────────────────────────────────┘
                  │ 動態請求
    ┌─────────────▼─────────────┐
    │   Regional Load Balancers │
    │   (AWS ALB / NLB)         │
    └──────────┬────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────┐
│                Region: us-east-1                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Control Plane VPC                     │   │
│  │  (10.0.0.0/8)                                       │   │
│  │                                                     │   │
│  │  ┌─────────────────────┐  ┌────────────────────┐   │   │
│  │  │  Public Subnet       │  │  Private Subnet     │   │   │
│  │  │  (10.0.1.0/24)       │  │  (10.0.10.0/24)    │   │   │
│  │  │  ─ API Gateway       │  │  ─ Auth Service     │   │   │
│  │  │    (Kong/Envoy)      │  │  ─ Tenant Service   │   │   │
│  │  │  ─ Web Console CDN   │  │  ─ Billing Service  │   │   │
│  │  └─────────────────────┘  └────────────────────┘   │   │
│  │                                                     │   │
│  │  ┌────────────────────────────────────────────┐     │   │
│  │  │  Database Subnet (10.0.20.0/24)             │     │   │
│  │  │  ─ PostgreSQL HA (Primary + 2 Replica)      │     │   │
│  │  │  ─ Redis Cluster (3 Master + 3 Replica)     │     │   │
│  │  │  ─ Kafka Cluster (3 Broker)                 │     │   │
│  │  └────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Data Plane VPC                        │   │
│  │  (10.1.0.0/8)  ─ VPC Peering ─ Control Plane VPC  │   │
│  │                                                     │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │   EKS Cluster（Shared, Pool Model）           │   │   │
│  │  │                                              │   │   │
│  │  │   System Namespaces:                         │   │   │
│  │  │   ─ kube-system                              │   │   │
│  │  │   ─ istio-system                             │   │   │
│  │  │   ─ monitoring                               │   │   │
│  │  │   ─ nemoclaw-operators                       │   │   │
│  │  │                                              │   │   │
│  │  │   Tenant Namespaces:                         │   │   │
│  │  │   ─ tenant-abc123  (Pro)                     │   │   │
│  │  │   ─ tenant-def456  (Team)                    │   │   │
│  │  │   ─ tenant-ghi789  (Free, shared pool)       │   │   │
│  │  │   ─ ...                                      │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  │                                                     │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │   EKS Cluster（Enterprise Silo）              │   │   │
│  │  │   tenant-enterprise-xyz (Dedicated Cluster)  │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Kubernetes 叢集設計

### 2.1 節點規格

```
控制節點（Control Plane）：
  類型：m5.xlarge（4 vCPU, 16 GB RAM）
  數量：3（HA across 3 AZs）
  目的：K8s API Server, etcd, Scheduler

系統節點（System Workloads）：
  類型：m5.2xlarge（8 vCPU, 32 GB RAM）
  數量：3（一般）→ 最多 10（HPA）
  目的：Istio, Monitoring, Operators

一般租戶節點（Sandbox Workloads）：
  類型：c5.2xlarge（8 vCPU, 16 GB RAM）
  數量：5（一般）→ 最多 50（Cluster Autoscaler）
  目的：Free/Pro 租戶的沙箱 Pod

Enterprise 專屬節點（GPU 節點，可選）：
  類型：g5.2xlarge（NVIDIA A10G GPU）或 p4d.24xlarge（A100）
  數量：依合約
  目的：Enterprise 租戶本機推理（Ollama）
```

### 2.2 節點池隔離

```yaml
# Free 租戶使用特定節點池（透過 Node Selector + Taint）
nodeSelector:
  nemoclaw.ai/node-pool: "free-tier"

tolerations:
- key: "nemoclaw.ai/free-tier"
  operator: "Equal"
  value: "true"
  effect: "NoSchedule"

# Pro+ 租戶使用標準節點池
nodeSelector:
  nemoclaw.ai/node-pool: "standard"
```

---

## 3. 基礎設施即程式碼（IaC）

### 3.1 工具選型

```
雲端資源管理：
  - Terraform（主要）
  - Terragrunt（多環境管理）
  - Terraform Cloud（狀態管理 + Plan review）

Kubernetes 資源管理：
  - Helm Charts（服務部署）
  - Kustomize（環境差異化）
  - ArgoCD（GitOps 持續部署）

機密管理：
  - HashiCorp Vault（動態 secrets）
  - External Secrets Operator（K8s ← Vault 同步）

映像管理：
  - Amazon ECR（映像倉庫）
  - Cosign（映像簽名驗證）
  - Trivy（映像漏洞掃描）
```

### 3.2 GitOps 工作流

```
程式碼合並至 main
    │
    ▼
CI Pipeline（GitHub Actions）：
  ├── 單元測試 + 整合測試
  ├── 映像建置
  ├── 映像掃描（Trivy）
  ├── 映像簽名（Cosign）
  └── 推送至 ECR（帶版本 tag）
    │
    ▼
自動更新 GitOps 倉庫：
  kustomize/production/sandbox-orchestrator/image.yaml
  └── image: 123456789.dkr.ecr.us-east-1.amazonaws.com/sandbox-orchestrator:v1.2.3
    │
    ▼
ArgoCD 偵測變更並自動部署（或需 PR 審核）
    │
    ▼
K8s Rolling Update（Zero-downtime）
    │
    ▼
部署後健康檢查（Argo Rollouts）
  ├── 如果 Error Rate < 1%：繼續
  └── 如果 Error Rate > 1%：自動回滾
```

---

## 4. 網路安全設計

### 4.1 VPC 設計

```
Control Plane VPC (10.0.0.0/16):
  Public Subnets（每個 AZ 一個）：
    - API Gateway / Load Balancer
    - NAT Gateway（出口流量）
  
  Private Subnets（每個 AZ 一個）：
    - 應用服務（Auth、Tenant、Billing）
    - EKS Control Plane
  
  Database Subnets（每個 AZ 一個）：
    - PostgreSQL RDS
    - Redis ElastiCache
    - 僅允許 Private Subnet 存取

Data Plane VPC (10.1.0.0/16):
  EKS Node Subnets（每個 AZ 一個）：
    - 沙箱 Pod 運行
    - 僅允許透過 VPC Peering 與 Control Plane 通訊
    - 出口流量：僅允許白名單 HTTPS（沙箱出口政策）

VPC Peering：
  Control Plane ↔ Data Plane（私有網路通訊）
  
Transit Gateway（多區域）：
  us-east-1 ↔ eu-west-1 ↔ ap-southeast-1
```

### 4.2 Service Mesh（Istio）設定

```yaml
# PeerAuthentication：強制 mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: nemoclaw-system
spec:
  mtls:
    mode: STRICT  # 所有服務間通訊必須 mTLS

---
# DestinationRule：TLS 設定
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: default
  namespace: nemoclaw-system
spec:
  host: "*.nemoclaw-system.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
```

---

## 5. 災難恢復計畫

### 5.1 備份策略

```
PostgreSQL 備份：
  - WAL 連續備份至 S3（Point-in-Time Recovery）
  - 每日快照備份（保留 30 天）
  - 跨區域備份複製（us-east-1 → eu-west-1）
  - 每月備份恢復演練

Redis 備份：
  - RDB 快照每 15 分鐘（S3）
  - AOF 持久化
  - 跨 AZ 副本

S3 物件（快照、日誌）：
  - S3 Cross-Region Replication 至 DR 區域
  - S3 Object Lock（7 年審計日誌不可刪除）
```

### 5.2 故障場景處理

```
場景 1：單一 AZ 故障
  影響：部分 Pod 重新排程
  RTO：5 分鐘（Kubernetes 自動重排程）
  操作：自動（無需人工介入）

場景 2：主區域部分服務故障
  影響：特定服務降級
  RTO：15 分鐘
  操作：PagerDuty 告警 → On-call 工程師 → 重啟/切換

場景 3：主區域完全故障
  影響：所有服務不可用
  RTO：1 小時（Pro）/ 15 分鐘（Enterprise）
  操作：
    1. DNS 切換至備用區域（Route53 Health Check）
    2. 啟動 DR 區域資料庫（從最近備份恢復）
    3. 驗證服務健康狀態
    4. 更新 Slack 狀態頁

場景 4：資料庫損毀
  影響：資料丟失風險
  RPO：< 15 分鐘（WAL 連續備份）
  操作：PITR 恢復至最後已知正常狀態
```

---

## 6. 維護與升級

### 6.1 K8s 版本升級

```
策略：滾動升級，零停機

排程：
  1. Staging 環境升級（至少 2 週測試）
  2. 宣布維護窗口（提前 2 週通知）
  3. 工作節點升級（Drain → 升級 → Uncordon，一次一個 AZ）
  4. 驗證所有工作負載恢復正常
  5. 控制節點升級（etcd → API Server → Scheduler）
```

### 6.2 資料庫遷移

```
工具：Flyway 或 golang-migrate

策略：
  - 每次遷移必須向前相容（新程式碼 + 舊 Schema 可同時運行）
  - 使用 expand-contract 模式（先加欄位，再移除舊欄位）
  - 多租戶 Schema 遷移：平行執行（per-tenant），有失敗重試

範例遷移流程：
  1. 部署新服務版本（支援新舊 Schema）
  2. 執行 Schema 遷移（flyway migrate）
  3. 驗證資料完整性
  4. 移除舊版本相容程式碼
```

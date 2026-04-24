# 租戶隔離策略設計

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 租戶隔離模型

### 1.1 三層混合隔離模型（推薦）

根據訂閱方案採用不同的隔離強度：

```
┌───────────────────────────────────────────────────────────────┐
│                      Enterprise 方案                           │
│           Silo Model（專屬 Kubernetes 叢集）                    │
│                                                               │
│  Cluster A          Cluster B          Cluster C             │
│  ┌─────────┐        ┌─────────┐        ┌─────────┐           │
│  │Tenant A │        │Tenant B │        │Tenant C │           │
│  │(Full   │        │(Full   │        │(Full   │           │
│  │Cluster)│        │Cluster)│        │Cluster)│           │
│  └─────────┘        └─────────┘        └─────────┘           │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                    Pro / Team 方案                             │
│           Pool Model（共享叢集，Namespace 隔離）               │
│                                                               │
│              Shared Kubernetes Cluster                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ NS: tenant-a │  │ NS: tenant-b │  │ NS: tenant-c │       │
│  │ Sandbox Pods │  │ Sandbox Pods │  │ Sandbox Pods │       │
│  │ NetworkPolicy│  │ NetworkPolicy│  │ NetworkPolicy│       │
│  │ ResourceQuota│  │ ResourceQuota│  │ ResourceQuota│       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                       Free 方案                                │
│           Shared Model（共享基礎設施，邏輯隔離）                │
│                                                               │
│              Shared Resource Pool                             │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Tenant A Sandbox  │  Tenant B Sandbox  │  ...       │    │
│  │  (Row-level data   │  (Row-level data   │            │    │
│  │   isolation)       │   isolation)       │            │    │
│  └──────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────┘
```

### 1.2 隔離強度比較

| 隔離面向 | Silo | Pool | Shared |
|---------|------|------|--------|
| 計算資源 | ✅ 完全獨立 | ✅ 命名空間隔離 | ⚠️ 共享，限額控制 |
| 網路流量 | ✅ 完全隔離 | ✅ NetworkPolicy | ⚠️ 邏輯隔離 |
| 資料庫 | ✅ 專屬 DB 實例 | ✅ 獨立 Schema | ⚠️ 行級安全 |
| 儲存 | ✅ 專屬 S3 Bucket | ✅ Bucket prefix | ⚠️ Object prefix |
| 金鑰 | ✅ 專屬 KMS Key | ✅ 獨立 DEK | ⚠️ 共用 KEK |
| 維護窗口 | ✅ 自訂 | ⚠️ 協調 | ⚠️ 統一 |
| 成本 | 最高 | 中等 | 最低 |

---

## 2. Kubernetes 層租戶隔離

### 2.1 Namespace 隔離（Pool Model）

每個租戶一個 Kubernetes Namespace，包含以下資源：

```yaml
# Namespace 命名規則：tenant-{tenant-id}
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-abc123
  labels:
    tenant-id: "abc123"
    plan: "pro"
    created-by: "nemoclaw-platform"
  annotations:
    nemoclaw.ai/tenant-name: "ACME Corp"
    nemoclaw.ai/created-at: "2026-04-16T00:00:00Z"
---
# 資源配額（依訂閱方案設定）
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
  namespace: tenant-abc123
spec:
  hard:
    requests.cpu: "4"
    requests.memory: "8Gi"
    limits.cpu: "8"
    limits.memory: "16Gi"
    pods: "20"
    services: "10"
    persistentvolumeclaims: "10"
---
# 限制範圍（單一 Pod 的限制）
apiVersion: v1
kind: LimitRange
metadata:
  name: tenant-limits
  namespace: tenant-abc123
spec:
  limits:
  - type: Container
    default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "250m"
      memory: "256Mi"
    max:
      cpu: "2"
      memory: "4Gi"
---
# 預設 NetworkPolicy：拒絕所有跨租戶流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: tenant-abc123
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-dns
    ports:
    - protocol: UDP
      port: 53
---
# 服務帳號（最小權限）
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sandbox-runner
  namespace: tenant-abc123
  annotations:
    nemoclaw.ai/tenant-id: "abc123"
```

### 2.2 Pod Security Standards

所有租戶 Pod 均強制套用 `restricted` Policy：

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-abc123
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

### 2.3 OPA Gatekeeper 政策

防止租戶之間的資源存取：

```rego
# 禁止 Pod 跨命名空間引用 Service
package tenantboundary

violation[{"msg": msg}] {
  input.review.kind.kind == "Pod"
  pod_namespace := input.review.object.metadata.namespace
  env := input.review.object.spec.containers[_].env[_]
  contains(env.value, "svc.cluster.local")
  not valid_service_reference(env.value, pod_namespace)
  msg := sprintf("Pod in namespace %v references service outside its namespace", [pod_namespace])
}

valid_service_reference(value, namespace) {
  contains(value, sprintf(".%v.svc.cluster.local", [namespace]))
}
```

---

## 3. 資料庫層租戶隔離

### 3.1 PostgreSQL Schema-per-Tenant

```sql
-- 每個租戶建立獨立 Schema
CREATE SCHEMA IF NOT EXISTS tenant_abc123;

-- 設定 RLS（Row Level Security）作為額外防護
ALTER TABLE tenant_abc123.sandboxes ENABLE ROW LEVEL SECURITY;

-- 搜尋路徑設定（應用層連線時）
SET search_path TO tenant_abc123, public;

-- 跨租戶查詢完全禁止（Schema 邊界即是隔離邊界）
```

**Schema 結構（每租戶複製）：**

```sql
-- 在 tenant_{id} schema 下的表結構
CREATE TABLE sandboxes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        VARCHAR(255) NOT NULL,
  status      VARCHAR(50) NOT NULL,
  blueprint   JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agents (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sandbox_id  UUID REFERENCES sandboxes(id),
  name        VARCHAR(255),
  config      JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE inference_usage (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sandbox_id      UUID REFERENCES sandboxes(id),
  model           VARCHAR(255),
  input_tokens    INTEGER,
  output_tokens   INTEGER,
  latency_ms      INTEGER,
  created_at      TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE TABLE snapshots (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id    UUID REFERENCES agents(id),
  s3_key      VARCHAR(1024),
  size_bytes  BIGINT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE network_policies (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sandbox_id  UUID REFERENCES sandboxes(id),
  policy_yaml TEXT,
  applied_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 連線池策略

```
應用層使用 PgBouncer 做連線池：
  - Transaction-level pooling
  - 每租戶設定獨立的連線數上限
  - 連線字串範例：
    postgres://app:password@pgbouncer:5432/platform?search_path=tenant_abc123
```

---

## 4. 物件儲存層租戶隔離

### 4.1 S3/MinIO Bucket 結構

```
s3://nemoclaw-platform/
├── tenants/
│   ├── {tenant-id}/
│   │   ├── snapshots/
│   │   │   ├── {agent-id}/
│   │   │   │   ├── 2026-04-16T00:00:00Z.snapshot.json
│   │   │   │   └── ...
│   │   ├── blueprints/
│   │   │   ├── custom-blueprint.yaml
│   │   │   └── ...
│   │   └── logs/
│   │       ├── 2026/04/16/
│   │       │   └── sandbox-{id}.log.gz
│   │       └── ...
│   └── ...
└── platform/
    ├── base-blueprints/    # 平台提供的標準藍圖
    └── policy-presets/     # 平台提供的政策預設
```

### 4.2 IAM 政策（Bucket Policy）

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TenantScopeAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789:role/sandbox-runner-role"
      },
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::nemoclaw-platform/tenants/${aws:PrincipalTag/tenant-id}/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
        }
      }
    }
  ]
}
```

---

## 5. 網路層租戶隔離

### 5.1 出口政策繼承鏈

```
Platform Global Policy（平台全域，不可覆蓋）
  ├── 封鎖：已知惡意 IP 清單
  ├── 封鎖：內部 RFC1918 位址（防 SSRF）
  └── 封鎖：其他租戶的端點
      ↓ 繼承
Tenant Default Policy（租戶預設，可擴展）
  ├── 允許：NVIDIA Endpoints (*.nvidia.com)
  ├── 允許：DNS (8.8.8.8, 1.1.1.1)
  └── 可選：啟用預設 presets（Slack、Discord 等）
      ↓ 繼承
Sandbox Policy（沙箱層，最細粒度）
  ├── 繼承租戶政策
  └── 可添加：特定沙箱的額外允許規則
```

### 5.2 Istio 服務網格隔離

```yaml
# 禁止跨租戶的 Pod 間直接通訊
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-cross-tenant
  namespace: istio-system
spec:
  action: DENY
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/tenant-*/sa/*"]
    to:
    - operation:
        notPaths: ["/api/*"]
    when:
    - key: request.auth.claims[tenant_id]
      notValues: ["tenant-abc123"]
```

---

## 6. 租戶生命週期管理

### 6.1 租戶建立流程

```
1. 用戶完成註冊 + 選擇方案
         ↓
2. Auth Service 建立 Identity
         ↓
3. Tenant Service 建立租戶記錄
         ↓
4. 非同步：Provisioner 建立基礎設施
   ├── 建立 Kubernetes Namespace
   ├── 套用 ResourceQuota + LimitRange
   ├── 套用預設 NetworkPolicy
   ├── 建立 PostgreSQL Schema
   ├── 建立 S3 Prefix + IAM 政策
   ├── 建立 Vault 租戶路徑
   └── 建立初始 Quota 記錄
         ↓
5. 發送歡迎 Email + Onboarding 引導
         ↓
6. 租戶狀態：Active
```

### 6.2 租戶暫停/刪除流程

```
暫停（方案過期/欠費）：
  1. 停止所有沙箱（graceful shutdown）
  2. 保留資料（30 天冷凍期）
  3. 禁止 API 存取（保留 Web 登入以更新付款）

刪除（用戶主動 + 30 天冷凍後）：
  1. 確認刪除（Email 驗證）
  2. 刪除所有沙箱
  3. 匯出資料給用戶（ZIP + 下載連結）
  4. 刪除 K8s Namespace（cascade）
  5. 刪除 PostgreSQL Schema（CASCADE）
  6. 刪除 S3 物件（批次）
  7. 撤銷 Vault 憑證
  8. 保留審計日誌（合規要求，7 年）
```

---

## 7. 共享資源安全存取

### 7.1 推理 Gateway 的租戶上下文注入

每個推理請求必須攜帶租戶識別，Gateway 負責驗證並注入：

```
Client Request
  Headers:
    Authorization: Bearer <JWT>
    X-Tenant-ID: abc123  (從 JWT claim 提取，不信任 header)

Inference Gateway:
  1. 驗證 JWT（Auth Service 公鑰）
  2. 提取 tenant_id claim
  3. 檢查 Quota（Redis：tenant:abc123:tokens:2026-04）
  4. 注入上游請求 header：
     X-Tenant-ID: abc123
     X-Sandbox-ID: sandbox-xyz
  5. 轉發至 NVIDIA Endpoints
  6. 記錄用量（Kafka event）
```

### 7.2 防止租戶間資源競爭

```
公平排程策略：
  - 推理請求：每租戶 sliding window 速率限制（Redis）
  - 沙箱建立：Priority Queue（Enterprise > Pro > Free）
  - 網路頻寬：K8s Network Bandwidth Plugin（per-namespace）
  - CPU/Memory：ResourceQuota + LimitRange（已實施）
```

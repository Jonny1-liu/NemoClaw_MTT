# Phase 1：基礎建設（Foundation）

> 時程：2026 Q2（約 12 週）| 目標：建立所有後續工作的基礎

---

## 目標

Phase 1 的核心目標是建立「能讓第一個真實租戶登入並使用」的最小可行平台（MVP），確保後續所有多租戶功能都建立在穩固的基礎上。

**完成標準（Definition of Done）：**
- 可以透過 Web 或 CLI 完成用戶註冊、登入
- 可以建立一個沙箱並在其中使用 OpenClaw 代理
- 系統有基本可觀測性（日誌 + 指標）
- CI/CD Pipeline 可正常運作
- 基礎設施完全 IaC 管理

---

## 週次計畫

### Week 1-2：基礎設施搭建

**工作項目：**

1. **AWS 帳號與 IAM 結構**
   - 建立 Management、Production、Staging、Dev 帳號（AWS Organizations）
   - 設定 IAM 角色與最小權限策略
   - 啟用 CloudTrail 全域稽核

2. **Terraform 基礎模組**
   ```
   modules/
   ├── vpc/           # VPC + Subnet + NAT Gateway
   ├── eks/           # EKS 叢集
   ├── rds/           # PostgreSQL HA
   ├── elasticache/   # Redis Cluster
   ├── s3/            # Object Store + Lifecycle
   └── vault/         # HashiCorp Vault（HCP 或 Self-hosted）
   ```

3. **K8s 基礎元件安裝**
   - Istio（Service Mesh）
   - cert-manager（TLS 憑證自動化）
   - External Secrets Operator（Vault 整合）
   - Cluster Autoscaler
   - Metrics Server

4. **CI/CD Pipeline 初始化**
   - GitHub Actions：build → test → scan → push image
   - ArgoCD：GitOps 部署
   - SonarCloud：程式碼品質掃描
   - Snyk：依賴漏洞掃描

**交付物：**
- Terraform 程式碼（可重複執行）
- 所有服務可在 Staging 環境部署
- CI/CD 第一個 Pipeline 可運行

---

### Week 3-4：Auth Service

**工作項目：**

1. **選型與安裝（建議：Keycloak on K8s）**
   ```bash
   # Helm 安裝 Keycloak
   helm install keycloak bitnami/keycloak \
     --namespace auth \
     --set auth.adminPassword=$ADMIN_PASSWORD \
     --set postgresql.enabled=true \
     --set postgresql.primary.persistence.size=10Gi
   ```

2. **Realm 設定**
   - 建立 `nemoclaw` realm
   - 設定 OAuth 2.0 / OIDC flows
   - 建立 Client（Web Console、API、CLI）
   - 設定 Token lifetimes（Access: 15min, Refresh: 7d）

3. **Social Login 整合**
   - GitHub OAuth（開發者友好）
   - Google OAuth（一般用戶）

4. **自訂 Claims Mapper**
   ```javascript
   // Keycloak Script Mapper：注入 tenant_id 到 JWT
   var tenantId = user.getAttribute("tenant_id");
   var plan = user.getAttribute("plan");
   token.setOtherClaims("tenant_id", tenantId);
   token.setOtherClaims("plan", plan || "free");
   token.setOtherClaims("roles", user.getGroups());
   ```

**交付物：**
- Auth Service 可在 Staging 運行
- 可完成 Email/GitHub/Google 登入
- JWT 包含所需的自訂 Claims

---

### Week 5-6：Tenant Service + API Gateway

**工作項目：**

1. **Tenant Service（Node.js/Fastify）**

   核心 API：
   ```
   POST   /internal/tenants          # 建立租戶（由 Auth 觸發）
   GET    /internal/tenants/:id      # 查詢租戶資訊
   PATCH  /internal/tenants/:id      # 更新租戶設定
   GET    /internal/tenants/:id/quota # 查詢配額
   ```

   資料庫 Schema（單一 Schema，初期不做 per-tenant 隔離）：
   ```sql
   CREATE TABLE tenants (
     id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     name         VARCHAR(255) NOT NULL,
     slug         VARCHAR(63) UNIQUE NOT NULL,
     plan         VARCHAR(50) DEFAULT 'free',
     status       VARCHAR(50) DEFAULT 'active',
     created_at   TIMESTAMPTZ DEFAULT NOW()
   );
   
   CREATE TABLE tenant_quotas (
     tenant_id    UUID REFERENCES tenants(id),
     resource     VARCHAR(50) NOT NULL,  -- 'tokens', 'sandboxes'
     monthly_limit BIGINT NOT NULL,
     used         BIGINT DEFAULT 0,
     reset_at     TIMESTAMPTZ,
     PRIMARY KEY (tenant_id, resource)
   );
   ```

2. **API Gateway 設定（Kong/Envoy）**

   基礎路由規則：
   ```yaml
   services:
   - name: tenant-service
     url: http://tenant-service.nemoclaw-system:8080
     routes:
     - name: tenant-routes
       paths: [/api/v1/me, /api/v1/settings]
       strip_path: false
   
   plugins:
   - name: jwt
     config:
       key_claim_name: kid
       claims_to_verify: [exp, nbf]
   
   - name: rate-limiting
     config:
       minute: 100
       policy: redis
       redis_host: redis-cluster
   ```

**交付物：**
- Tenant Service 完整 API
- API Gateway 設定完成
- 可透過 API 完成租戶建立

---

### Week 7-9：CLI v2 骨架 + 沙箱 API

**工作項目：**

1. **CLI v2 架構重構**

   目標：保留相同 CLI 介面，改呼叫後端 API
   ```typescript
   // 原本：直接呼叫 openshell CLI
   // nemoclaw onboard → openshell gateway start → openshell sandbox create
   
   // 新版：呼叫後端 API
   // nemoclaw sandbox create my-assistant → POST /api/v1/sandboxes
   
   class NemoclawClient {
     constructor(
       private apiBase: string,
       private token: TokenManager
     ) {}
     
     async createSandbox(name: string, opts: SandboxOptions): Promise<Sandbox> {
       return this.post('/api/v1/sandboxes', { name, ...opts });
     }
   }
   ```

2. **Sandbox Orchestrator（初版，最小可行）**

   Phase 1 只需支援單一租戶，先不做完整隔離：
   ```go
   func (s *SandboxOrchestrator) Create(ctx context.Context, req *CreateRequest) error {
       // 1. 驗證請求
       // 2. 建立 K8s Namespace（如不存在）
       // 3. 部署沙箱 Pod（從 NemoClaw blueprint 轉換）
       // 4. 等待 Pod Ready
       // 5. 更新 DB 狀態
       return nil
   }
   ```

**交付物：**
- CLI v2 可完成 `nemoclaw login`、`nemoclaw sandbox create/list/delete`
- Sandbox Orchestrator 可建立/刪除沙箱（單租戶測試）

---

### Week 10-11：基礎可觀測性

**工作項目：**

1. **監控堆疊部署**
   ```bash
   # Prometheus + Grafana Stack
   helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
     --namespace monitoring
   
   # Loki（日誌收集）
   helm install loki grafana/loki-stack \
     --namespace monitoring \
     --set promtail.enabled=true
   
   # Tempo（分散式追蹤）
   helm install tempo grafana/tempo \
     --namespace monitoring
   ```

2. **初始 Grafana 儀表板**
   - K8s 叢集資源使用（CPU/Memory/Pod）
   - API Gateway 請求量、錯誤率、延遲
   - 沙箱建立成功率與時間

3. **告警規則（最小集合）**
   - API 錯誤率 > 10%（觸發 Slack 通知）
   - 沙箱 Pod 重啟次數 > 3（觸發 Slack 通知）
   - 節點記憶體 > 85%（觸發 Slack 通知）

---

### Week 12：Phase 1 整合測試與私測

**工作項目：**

1. **端到端測試**
   - 用戶註冊流程
   - 沙箱建立 → 連接 → 使用 → 刪除
   - CLI v2 全流程

2. **安全審查**
   - JWT 驗證邏輯確認
   - API Gateway 路由隔離確認
   - 沙箱安全設定驗證（seccomp/Landlock 在雲端 K8s 上是否正常）

3. **邀請私測用戶（5-10 人）**
   - 手動 onboard（不需自助服務）
   - 收集反饋
   - 記錄 Bug 和改善建議

**Phase 1 完成標準：**
- [ ] 用戶可完成自助註冊（Email）
- [ ] 用戶可透過 CLI v2 建立沙箱
- [ ] 沙箱安全隔離在 K8s 上正常運作
- [ ] 系統可觀測（日誌 + 指標 + 告警）
- [ ] CI/CD 可自動部署至 Staging
- [ ] 5+ 私測用戶成功使用

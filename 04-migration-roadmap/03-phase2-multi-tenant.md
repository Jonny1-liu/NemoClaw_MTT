# Phase 2：多租戶核心（Multi-Tenant Core）

> 時程：2026 Q3（約 12 週，緊接 Phase 1）| 目標：真正的多租戶隔離

---

## 目標

Phase 2 將 Phase 1 建立的單租戶系統升級為真正的多租戶平台。這是整個遷移過程最技術複雜的階段，涉及資料隔離、沙箱隔離、推理配額等核心能力。

**完成標準（Definition of Done）：**
- 50+ 個租戶可同時安全運行，互不干擾
- 資料完全隔離（PostgreSQL Schema-per-tenant）
- 沙箱完全隔離（K8s Namespace + NetworkPolicy）
- 推理用量可精確計量並執行配額
- 動態網路政策可更新（無需重啟沙箱）

---

## Week 1-3：資料隔離實作

### 任務 1：PostgreSQL Schema-per-Tenant 遷移

```sql
-- 遷移腳本：將現有單一 Schema 資料遷至 per-tenant Schema

-- 1. 為每個現有租戶建立 Schema
CREATE OR REPLACE FUNCTION create_tenant_schema(tenant_id TEXT) RETURNS void AS $$
BEGIN
    -- 建立 Schema
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS tenant_%s', tenant_id);
    
    -- 建立所有必要的表
    EXECUTE format('CREATE TABLE tenant_%s.sandboxes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT ''creating'',
        blueprint_id UUID,
        inference_config JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )', tenant_id);
    
    EXECUTE format('CREATE TABLE tenant_%s.inference_usage (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sandbox_id UUID REFERENCES tenant_%1$s.sandboxes(id),
        model VARCHAR(255),
        input_tokens INTEGER,
        output_tokens INTEGER,
        latency_ms INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW()
    ) PARTITION BY RANGE (created_at)', tenant_id, tenant_id);
    
    EXECUTE format('CREATE TABLE tenant_%s.network_policies (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sandbox_id UUID,
        policy_config JSONB,
        applied_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )', tenant_id);
    
    EXECUTE format('CREATE TABLE tenant_%s.snapshots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sandbox_id UUID REFERENCES tenant_%1$s.sandboxes(id),
        s3_key VARCHAR(1024),
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )', tenant_id, tenant_id);
    
    -- 建立索引
    EXECUTE format('CREATE INDEX ON tenant_%s.sandboxes(status)', tenant_id);
    EXECUTE format('CREATE INDEX ON tenant_%s.inference_usage(created_at)', tenant_id);
END;
$$ LANGUAGE plpgsql;

-- 2. 為所有現有租戶執行
SELECT create_tenant_schema(id::text) FROM tenants;
```

### 任務 2：應用層 Schema 路由

```typescript
// 資料庫連線中介層：自動設定 search_path

class TenantAwareDatabase {
    async withTenantContext<T>(tenantId: string, fn: (db: Database) => Promise<T>): Promise<T> {
        const client = await this.pool.connect();
        try {
            await client.query(`SET search_path TO tenant_${tenantId}, public`);
            // 執行業務邏輯
            return await fn(new Database(client));
        } finally {
            // 重設 search_path（歸還連線前）
            await client.query('SET search_path TO public');
            client.release();
        }
    }
}

// 使用範例
async getSandboxes(tenantId: string): Promise<Sandbox[]> {
    return this.db.withTenantContext(tenantId, async (db) => {
        return db.query<Sandbox>('SELECT * FROM sandboxes WHERE status != $1', ['deleted']);
    });
}
```

---

## Week 4-6：K8s 多租戶隔離

### 任務 1：Namespace 自動化 Provisioner

```go
// Tenant Namespace Provisioner
// 當新租戶建立時，自動建立 K8s 資源

type TenantProvisioner struct {
    k8sClient kubernetes.Interface
    db        *Database
    vault     *VaultClient
}

func (p *TenantProvisioner) ProvisionTenant(ctx context.Context, tenant *Tenant) error {
    // 1. 建立 Namespace
    ns := &corev1.Namespace{
        ObjectMeta: metav1.ObjectMeta{
            Name: fmt.Sprintf("tenant-%s", tenant.ID),
            Labels: map[string]string{
                "app.kubernetes.io/managed-by": "nemoclaw-platform",
                "nemoclaw.ai/tenant-id":        tenant.ID,
                "nemoclaw.ai/plan":             tenant.Plan,
                // Pod Security Standards
                "pod-security.kubernetes.io/enforce": "restricted",
            },
        },
    }
    if _, err := p.k8sClient.CoreV1().Namespaces().Create(ctx, ns, metav1.CreateOptions{}); err != nil {
        return fmt.Errorf("create namespace: %w", err)
    }

    // 2. 建立 ResourceQuota（依方案）
    quota := p.buildResourceQuota(tenant.Plan)
    if _, err := p.k8sClient.CoreV1().ResourceQuotas(ns.Name).Create(ctx, quota, metav1.CreateOptions{}); err != nil {
        return fmt.Errorf("create resource quota: %w", err)
    }

    // 3. 建立預設 NetworkPolicy（deny all）
    netpol := p.buildDefaultNetworkPolicy(ns.Name)
    if _, err := p.k8sClient.NetworkingV1().NetworkPolicies(ns.Name).Create(ctx, netpol, metav1.CreateOptions{}); err != nil {
        return fmt.Errorf("create network policy: %w", err)
    }

    // 4. 建立 ServiceAccount（沙箱用）
    sa := &corev1.ServiceAccount{
        ObjectMeta: metav1.ObjectMeta{
            Name:      "sandbox-runner",
            Namespace: ns.Name,
            Annotations: map[string]string{
                "nemoclaw.ai/tenant-id": tenant.ID,
            },
        },
        AutomountServiceAccountToken: boolPtr(false),
    }
    if _, err := p.k8sClient.CoreV1().ServiceAccounts(ns.Name).Create(ctx, sa, metav1.CreateOptions{}); err != nil {
        return fmt.Errorf("create service account: %w", err)
    }

    // 5. 在 Vault 建立租戶路徑
    if err := p.vault.CreateTenantPath(ctx, tenant.ID); err != nil {
        return fmt.Errorf("create vault path: %w", err)
    }

    return nil
}
```

### 任務 2：動態網路政策更新

```go
// 無停機更新 NetworkPolicy
func (pe *PolicyEngine) UpdateSandboxPolicy(ctx context.Context, sandboxID string, policy *NetworkPolicy) error {
    // 1. 計算新政策（租戶預設 + 沙箱覆蓋）
    effectivePolicy := pe.mergeWithTenantPolicy(policy)
    
    // 2. 生成 K8s NetworkPolicy 資源
    k8sPolicy := pe.buildK8sNetworkPolicy(sandboxID, effectivePolicy)
    
    // 3. Apply（K8s 支援非破壞性更新）
    existing, err := pe.k8sClient.NetworkingV1().NetworkPolicies(namespace).
        Get(ctx, k8sPolicy.Name, metav1.GetOptions{})
    
    if err != nil {
        // 不存在，建立
        _, err = pe.k8sClient.NetworkingV1().NetworkPolicies(namespace).
            Create(ctx, k8sPolicy, metav1.CreateOptions{})
    } else {
        // 存在，更新（不重啟 Pod）
        existing.Spec = k8sPolicy.Spec
        _, err = pe.k8sClient.NetworkingV1().NetworkPolicies(namespace).
            Update(ctx, existing, metav1.UpdateOptions{})
    }
    
    // 4. 記錄政策變更（審計）
    pe.auditLog.Record(ctx, "policy.updated", map[string]string{
        "sandbox_id": sandboxID,
        "change_summary": policy.ChangeSummary(),
    })
    
    return err
}
```

---

## Week 7-8：推理 Gateway 完整實作

### 任務：計量 + 速率限制

```go
// Inference Gateway 核心處理器
func (g *InferenceGateway) HandleRequest(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    
    // 1. 從 JWT 提取租戶上下文
    tenantCtx := auth.TenantContextFromJWT(r.Header.Get("Authorization"))
    
    // 2. 配額檢查（Redis 原子操作）
    if err := g.quotaChecker.Check(ctx, tenantCtx.TenantID); err != nil {
        handleQuotaError(w, err)
        return
    }
    
    // 3. 速率限制（Sliding Window）
    if allowed, _ := g.rateLimiter.Allow(ctx, tenantCtx.TenantID); !allowed {
        w.Header().Set("Retry-After", "60")
        http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
        return
    }
    
    // 4. 轉發至 NVIDIA Endpoints（注入平台 API Key）
    resp, err := g.upstreamClient.Forward(r, g.getNVIDIAKey(tenantCtx.Plan))
    
    // 5. 解析回應取得 Token 計數
    tokenUsage := parseTokenUsage(resp)
    
    // 6. 非同步記錄用量（Kafka）
    go g.usageMeter.Record(ctx, UsageEvent{
        TenantID:     tenantCtx.TenantID,
        SandboxID:    tenantCtx.SandboxID,
        Model:        tokenUsage.Model,
        InputTokens:  tokenUsage.InputTokens,
        OutputTokens: tokenUsage.OutputTokens,
        LatencyMs:    resp.LatencyMs,
    })
    
    // 7. 返回回應給客戶端
    copyResponse(w, resp)
}
```

---

## Week 9-10：狀態管理與快照

### 任務：雲端快照系統

```go
// 快照服務：本機快照 → S3 加密快照
type SnapshotService struct {
    k8sClient  kubernetes.Interface
    s3Client   *s3.Client
    kmsClient  *kms.Client
    db         *Database
}

func (s *SnapshotService) CreateSnapshot(ctx context.Context, sandboxID, tenantID string) (*Snapshot, error) {
    // 1. 從沙箱 Pod 提取狀態（exec 命令）
    state, err := s.extractSandboxState(ctx, sandboxID, tenantID)
    
    // 2. 壓縮
    compressed, err := compress(state)
    
    // 3. 取得租戶 KMS Key
    kmsKeyID := fmt.Sprintf("alias/nemoclaw-tenant-%s", tenantID)
    
    // 4. 加密並上傳至 S3
    s3Key := fmt.Sprintf("tenants/%s/snapshots/%s/%s.tar.gz.enc", 
        tenantID, sandboxID, time.Now().Format(time.RFC3339))
    
    encResult, err := s.kmsClient.GenerateDataKey(ctx, &kms.GenerateDataKeyInput{
        KeyId:   &kmsKeyID,
        KeySpec: types.DataKeySpecAes256,
    })
    
    encrypted := encrypt(compressed, encResult.Plaintext)
    
    s.s3Client.PutObject(ctx, &s3.PutObjectInput{
        Bucket: aws.String("nemoclaw-platform"),
        Key:    aws.String(s3Key),
        Body:   bytes.NewReader(encrypted),
    })
    
    // 5. 記錄 metadata 至 DB
    snapshot := &Snapshot{
        ID:        uuid.New().String(),
        SandboxID: sandboxID,
        S3Key:     s3Key,
        SizeBytes: int64(len(encrypted)),
        CreatedAt: time.Now(),
    }
    
    return snapshot, s.db.WithTenantContext(tenantID, func(db *Database) error {
        return db.Insert("snapshots", snapshot)
    })
}
```

---

## Week 11-12：負載測試與安全審查

### 任務 1：多租戶負載測試

```
測試場景：

1. 基準測試：50 個租戶，每個 2 個沙箱
   - 目標：API p99 < 500ms
   - 工具：k6 + Grafana

2. 租戶隔離壓力測試：
   - 租戶 A 大量推理請求 → 確認不影響租戶 B 的回應時間
   - 工具：自定義 k6 腳本

3. 沙箱建立速度測試：
   - 同時建立 20 個沙箱
   - 目標：P95 < 60 秒

4. 網路政策壓力測試：
   - 100 次動態政策更新
   - 確認無沙箱重啟
```

### 任務 2：滲透測試（重點）

```
租戶隔離滲透測試：
  1. 嘗試透過 API 存取其他租戶的沙箱
  2. 嘗試透過 K8s 逃脫至其他 Namespace
  3. 嘗試 SSRF 攻擊至其他租戶服務
  4. 嘗試路徑遍歷存取 S3 其他租戶資料

工具：OWASP ZAP + 手動測試 + 雇用外部安全顧問
```

**Phase 2 完成標準：**
- [ ] 50+ 個租戶同時運行，無相互干擾
- [ ] 跨租戶 API 存取返回 404（不洩漏存在性）
- [ ] 推理配額準確執行（誤差 < 0.1%）
- [ ] 動態網路政策更新 < 5 秒生效
- [ ] 滲透測試無嚴重漏洞
- [ ] 沙箱建立時間 P95 < 60 秒

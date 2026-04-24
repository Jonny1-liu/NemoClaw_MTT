# 遷移策略總覽

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 遷移策略選擇

### 1.1 可行策略比較

| 策略 | 說明 | 優勢 | 劣勢 | 建議 |
|------|------|------|------|------|
| **Big Bang** | 一次性完全重寫 | 乾淨、無技術債 | 風險極高、時間長 | ❌ 不建議 |
| **Strangler Fig** | 逐步遷移，新舊並行 | 風險低、可回滾 | 複雜度高、過渡期長 | ✅ **建議** |
| **Fork & Evolve** | Fork 程式碼，並行開發 | 開發獨立 | 兩份程式碼維護 | ⚠️ 初期可考慮 |

### 1.2 採用 Strangler Fig 模式

```
現有 NemoClaw（單機 CLI）
         │
         │ 逐步萃取服務
         ▼
┌────────────────────────────────────────────────────────┐
│              遷移過程中的混合態                          │
│                                                        │
│  CLI（保留，改呼叫後端 API）                           │
│     ↕ API 呼叫                                         │
│  新 SaaS 後端服務（逐步建立）                           │
│     ↓ 底層仍然使用                                     │
│  OpenShell / K8s / Docker                              │
└────────────────────────────────────────────────────────┘
         │
         │ 完全遷移後
         ▼
NemoClaw SaaS 平台（純雲端）
  + 相容的 CLI v2（呼叫 API）
  + 可選的本機模式（開源版保留）
```

---

## 2. 遷移路線圖（三階段）

### 2.1 總體時程

```
2026 Q2 ──────────────────────────────────────── 2027 Q1

Phase 1: Foundation      Phase 2: Multi-tenant   Phase 3: SaaS
(3個月, Q2 2026)         (3個月, Q3 2026)         (3個月, Q4 2026)
─────────────────────────────────────────────────────────────────
│                        │                        │
│ ✦ Auth Service         │ ✦ 租戶隔離 K8s         │ ✦ Web Console GA
│ ✦ Tenant Service       │ ✦ 資料隔離 DB          │ ✦ 計費系統上線
│ ✦ API Gateway (v1)     │ ✦ Sandbox Orchestrator │ ✦ 公開 Beta
│ ✦ CLI v2 骨架          │ ✦ 推理 Gateway         │ ✦ 自助服務
│ ✦ 基礎設施 IaC         │ ✦ 政策引擎             │ ✦ GA Launch
│ ✦ CI/CD Pipeline       │ ✦ 狀態管理服務          │
│ ✦ 基礎可觀測性          │ ✦ 快照系統             │
│                        │ ✦ 完整可觀測性          │
─────────────────────────────────────────────────────────────────

2027 Q1+ Post-Launch
  ✦ Enterprise 功能（SSO、BYOK、SLA）
  ✦ 多區域擴展
  ✦ GPU 本機推理選項
  ✦ Marketplace / Plugin 系統
```

### 2.2 里程碑總覽

| 里程碑 | 時程 | 關鍵交付物 |
|--------|------|-----------|
| M1: 基礎服務就緒 | Week 6 | Auth + Tenant Service + API Gateway 可運行 |
| M2: 私測 Alpha | Week 8 | 邀請 10-20 個測試用戶（手動 onboard） |
| M3: 多租戶核心完成 | Week 14 | 完整租戶隔離，50+ 個租戶可同時運行 |
| M4: 內部 Beta | Week 18 | Web Console + 計費系統就緒 |
| M5: 公開 Beta | Week 20 | 自助服務，接受公眾報名 |
| M6: GA Launch | Week 24 | 正式商業上線，SLA 保證生效 |

---

## 3. 現有程式碼複用策略

### 3.1 直接複用（高優先）

```
1. 沙箱安全設定（Landlock/seccomp/netns）
   複用方式：從 nemoclaw-blueprint/ 提取安全設定模板
   目標服務：Sandbox Orchestrator（Pod Spec 生成）

2. 網路政策預設（policies/presets/）
   複用方式：作為 Policy Engine 的初始預設值
   目標服務：Policy Engine Service

3. SSRF 防禦邏輯（ssrf.ts）
   複用方式：提升至 API Gateway 層面，所有出口 URL 均驗證
   目標服務：Inference Gateway

4. 推理路由邏輯（src/lib/inference/）
   複用方式：重構為 Inference Gateway 的核心邏輯
   目標服務：Inference Gateway Service

5. 藍圖 YAML 格式
   複用方式：作為 Blueprint Service 的模板格式
   目標服務：Blueprint Service

6. CLI 命令介面設計（Commander 結構）
   複用方式：CLI v2 保留相同介面，改為呼叫 API
   目標服務：CLI v2
```

### 3.2 大幅修改（需重構）

```
7. 狀態管理（src/lib/runner/ + nemoclaw/src/blueprint/state.ts）
   現況：本機 JSON 檔案
   目標：PostgreSQL + Redis（分散式狀態）
   工作量：大

8. 憑證管理（src/lib/credentials/）
   現況：本機設定檔
   目標：HashiCorp Vault + 動態 Secrets
   工作量：大

9. 快照系統（nemoclaw/src/blueprint/snapshot.ts）
   現況：本機快照
   目標：S3 + KMS 加密快照
   工作量：中
```

### 3.3 全新建立（無現有基礎）

```
10. Auth Service（完全新建）
11. Tenant Service（完全新建）
12. API Gateway 設定（完全新建）
13. 計費系統（完全新建）
14. Web Console（完全新建）
15. 可觀測性堆疊（完全新建）
16. CI/CD Pipeline（部分現有，需擴展）
```

---

## 4. 團隊結構建議

### 4.1 工程團隊組成

```
Phase 1 最小可行團隊：
  ─ 後端工程師 × 2（核心服務）
  ─ DevOps/SRE × 1（基礎設施 + CI/CD）
  ─ 全端工程師 × 1（Web Console 骨架）

Phase 2 擴充：
  ─ 後端工程師 × 3（多租戶 + 資料隔離）
  ─ DevOps/SRE × 2（K8s + 監控）
  ─ 前端工程師 × 1（Web Console 完整）
  ─ 安全工程師 × 1（滲透測試 + 審計）

Phase 3 完整團隊：
  ─ 後端工程師 × 5
  ─ DevOps/SRE × 2
  ─ 前端工程師 × 2
  ─ PM × 1
  ─ 客服 × 1
  ─ 安全工程師 × 1（兼任）
```

---

## 5. 風險矩陣

| 風險 | 可能性 | 影響 | 緩解策略 |
|------|--------|------|---------|
| 安全沙箱在雲端無法正常運作 | 中 | 高 | 早期 PoC 驗證；考慮在 Bare Metal K8s 上部署 |
| NVIDIA Endpoints 速率限制 | 高 | 中 | 早期協商 Volume 合約；實作佇列緩衝 |
| 多租戶性能隔離不足 | 中 | 高 | Phase 2 進行負載測試；引入 ResourceQuota |
| 計費系統計量不準確 | 低 | 高 | 雙重計量（Redis + DB）；定期對帳 |
| 法規合規（GDPR/SOC2） | 低 | 高 | 從架構設計期開始考慮；聘請合規顧問 |
| 關鍵工程師離職 | 中 | 高 | 充分文件化；知識分享文化；合理薪酬 |
| OpenShell 上游 API 變更 | 中 | 中 | 建立版本鎖定機制；抽象層隔離 |

---

## 6. 成功指標（KPI）

```
技術 KPI（Phase 完成標準）：
  Phase 1: API p99 延遲 < 500ms，沙箱建立成功率 > 95%
  Phase 2: 支援 100 個並發租戶，沙箱建立時間 < 60s (P95)
  Phase 3: API Availability > 99.9%，計費準確率 > 99.99%

業務 KPI（Launch 後 6 個月）：
  ─ 總租戶數 > 1,000
  ─ 付費租戶轉換率 > 5%
  ─ MRR > $10,000
  ─ 客戶 NPS > 40
  ─ 系統 Uptime > 99.9%
```

# NemoClaw 差距分析：單機版 → 多租戶 SaaS

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 差距分析總覽

| 面向 | 現況（單機版） | 目標（多租戶 SaaS） | 差距等級 |
|------|--------------|-------------------|---------|
| 身份驗證 | 無（本機用戶） | OAuth 2.0 / OIDC / SSO | 🔴 嚴重 |
| 授權控制 | 無 | RBAC + 租戶隔離 | 🔴 嚴重 |
| 資料隔離 | 單一本機用戶 | 完整租戶隔離 | 🔴 嚴重 |
| 憑證管理 | 本機明文檔案 | 集中化 Vault/KMS | 🔴 嚴重 |
| 沙箱調度 | 本機 CLI | 雲端編排服務 | 🔴 嚴重 |
| API 介面 | CLI only | REST / gRPC API | 🔴 嚴重 |
| 計費計量 | 無 | 訂閱 + 用量計費 | 🔴 嚴重 |
| 狀態儲存 | 本機檔案 | 分散式資料庫 | 🔴 嚴重 |
| 可觀測性 | 本機日誌 | 集中化監控/追蹤 | 🟠 高度 |
| 水平擴展 | 不支援 | 自動伸縮 | 🟠 高度 |
| 網路政策 | 單沙箱層級 | 租戶層級繼承 | 🟠 高度 |
| 推理資源池 | 獨立實例 | 共享推理池 | 🟠 高度 |
| Web UI | 無 | 控制台 + 儀表板 | 🟡 中度 |
| 多區域支援 | 不支援 | 多 Region 部署 | 🟡 中度 |
| 災難恢復 | 無 | 自動備份/還原 | 🟡 中度 |
| SLA 管理 | 無 | 99.9%+ Uptime | 🟡 中度 |

---

## 2. 身份與存取管理（IAM）差距

### 2.1 現況問題

```
現況：
  - 完全依賴本機作業系統用戶
  - 無任何認證機制
  - 無角色或權限概念
  - API Key 明文儲存於本機設定檔

SaaS 需求：
  - 用戶帳號（Email + 密碼 / 社交登入 / SSO）
  - 租戶（Organization）概念
  - 細粒度 RBAC（Owner / Admin / Developer / Viewer）
  - API Token 管理（建立/撤銷/輪換）
  - MFA（多因素驗證）
  - SSO 整合（SAML 2.0、OIDC）
```

### 2.2 需要建立的元件

- **Identity Provider (IdP)**：Auth0、Keycloak 或自建 OIDC 服務
- **Authorization Service**：OPA（Open Policy Agent）或自建 RBAC 服務
- **API Key Service**：生成、儲存（hashed）、撤銷 API Token
- **Session Management**：JWT + Refresh Token 管理

---

## 3. 多租戶資料隔離差距

### 3.1 現況問題

```
現況：
  ~/.nemoclaw/
    ├── config.json        # 單一用戶的全部設定
    ├── blueprints/        # 沒有租戶分隔
    ├── snapshots/         # 混在一起
    └── credentials/       # 全部在同一路徑

SaaS 需求：
  每個租戶需要完全獨立的：
  - 設定與偏好設定
  - 沙箱實例（不互相可見）
  - 代理狀態快照
  - 推理使用歷史
  - 網路政策
  - 帳單資料
```

### 3.2 隔離模型選擇

| 模型 | 說明 | 隔離強度 | 成本效率 | 適用場景 |
|------|------|---------|---------|---------|
| **Silo（獨立叢集）** | 每租戶一個 K8s 叢集 | 最高 | 最低 | 企業/政府客戶 |
| **Pool（命名空間隔離）** | 共享叢集，K8s Namespace per tenant | 中等 | 中等 | 標準 SaaS 用戶 |
| **Shared（邏輯隔離）** | 共享基礎設施，DB row-level security | 最低 | 最高 | 免費/試用用戶 |

**建議策略**：採用混合模型
- Free/Starter 方案 → Shared 模型
- Pro/Team 方案 → Pool 模型（Namespace 隔離）
- Enterprise 方案 → Silo 模型（專屬叢集）

---

## 4. 沙箱生命週期管理差距

### 4.1 現況問題

```
現況：
  - 使用者手動執行 nemoclaw onboard
  - 沙箱由本機 openshell CLI 管理
  - 無中央調度，無佇列，無資源配額
  - 一台機器 = 一個（或少數幾個）沙箱

SaaS 需求：
  - 雲端 API 觸發沙箱建立/銷毀
  - 資源配額管理（per-tenant CPU/Memory/GPU 限制）
  - 沙箱池化（預建立沙箱以減少冷啟動時間）
  - 自動伸縮（根據排隊請求擴展沙箱數量）
  - 跨區域沙箱排程
  - 沙箱活動監控（idle timeout、health checks）
```

### 4.2 需要建立的元件

- **Sandbox Orchestration Service**：REST API 封裝 K8s 操作
- **Resource Quota Controller**：K8s ResourceQuota + LimitRange per namespace
- **Scheduler**：優先佇列 + 資源感知排程
- **Health Check Controller**：主動探針 + 自動恢復

---

## 5. 推理服務差距

### 5.1 現況問題

```
現況：
  - 每個用戶自行設定推理後端
  - NVIDIA API Key 由用戶提供並本機儲存
  - 無速率限制
  - 無使用量追蹤
  - 無推理成本分攤

SaaS 需求：
  - 平台集中管理 NVIDIA API Key（或代理模式）
  - 用量追蹤（tokens/month per tenant）
  - 速率限制（per-tenant RPM/TPM 限制）
  - 推理成本計算（用於計費）
  - 模型選擇 UI（依方案開放不同模型）
  - 推理結果快取（降低成本）
```

### 5.2 需要建立的元件

- **Inference Gateway**：代理推理請求，注入用量計量 hook
- **Rate Limiter**：Redis-based sliding window 速率限制
- **Token Counter**：追蹤每次請求的 token 用量
- **Model Registry**：可用模型清單，依訂閱方案過濾

---

## 6. 網路安全差距

### 6.1 現況問題

```
現況：
  - 網路政策以單一沙箱為單位設定
  - 政策修改需要重啟沙箱
  - 無租戶層級的預設政策繼承
  - 無 API 可動態修改政策

SaaS 需求：
  - 租戶可自訂出口政策（在平台允許範圍內）
  - 平台管理員可設定全域禁止清單
  - 動態政策更新（無需重啟沙箱）
  - 政策版本控制與審計日誌
  - 基於風險評分的自動政策調整
```

### 6.2 需要建立的元件

- **Policy Management API**：CRUD 政策的 REST API
- **Policy Inheritance Engine**：平台 → 租戶 → 沙箱的政策繼承
- **Dynamic Policy Applier**：不停機更新出口規則
- **Audit Logger**：記錄所有政策變更

---

## 7. 可觀測性差距

### 7.1 現況問題

```
現況：
  - 僅有本機 Docker/k3s 日誌
  - nemoclaw <name> logs 命令讀取本機日誌
  - 無指標收集
  - 無分散式追蹤
  - 無告警系統

SaaS 需求：
  - 集中化日誌（Elasticsearch / Loki）
  - 指標收集（Prometheus + Grafana）
  - 分散式追蹤（Jaeger / Tempo）
  - 告警規則（PagerDuty / OpsGenie 整合）
  - 租戶可見的使用量儀表板
  - SLO/SLA 監控
  - 異常偵測
```

---

## 8. 開發者體驗差距

### 8.1 現況問題

```
現況：
  - 純 CLI 介面
  - 本機安裝（curl | bash 方式）
  - 無 Web Console
  - 無 REST API 可程式化整合

SaaS 需求：
  - Web Console（租戶管理、沙箱管理、日誌查看）
  - REST API（完整的 API first 設計）
  - SDK（Python、Node.js、Go）
  - CLI 保留但改為呼叫後端 API
  - API 文件（OpenAPI 3.0 + Swagger UI）
  - Webhook（事件驅動整合）
```

---

## 9. 計費與訂閱差距

### 9.1 現況問題

```
現況：
  - 完全無計費機制
  - 開源免費使用

SaaS 需求：
  - 訂閱方案（Free / Pro / Team / Enterprise）
  - 用量計費（沙箱運行時間 + 推理 tokens）
  - 計費週期（月付/年付）
  - 發票生成
  - 超額警告與硬性限制
  - 成本管理儀表板
```

---

## 10. 基礎設施差距

### 10.1 現況問題

```
現況：
  - 依賴本機 Docker + k3s（embedded）
  - 無 HA（High Availability）
  - 無備份
  - 無災難恢復

SaaS 需求：
  - 多區域部署（AWS / Azure / GCP + NVIDIA DGX Cloud）
  - HA 控制平面（etcd 三副本 + 多 API Server）
  - 自動備份（PostgreSQL PITR + S3）
  - 災難恢復（RTO < 1hr, RPO < 15min）
  - CDN（靜態資源）
  - DDoS 防護
```

---

## 11. 差距優先級矩陣

```
高影響 × 高緊迫
┌──────────────────────────────────────┐
│ ✦ 身份驗證 / IAM                      │
│ ✦ 租戶資料隔離                        │
│ ✦ 沙箱編排服務（API 化）               │
│ ✦ 集中化憑證管理                      │
└──────────────────────────────────────┘

高影響 × 中緊迫
┌──────────────────────────────────────┐
│ ◆ 推理 Gateway（計量/速率限制）        │
│ ◆ 計費與訂閱系統                      │
│ ◆ 可觀測性堆疊                        │
│ ◆ REST API（OpenAPI）                │
└──────────────────────────────────────┘

中影響 × 中緊迫
┌──────────────────────────────────────┐
│ ● Web Console                        │
│ ● 動態網路政策管理                    │
│ ● 多區域支援                          │
│ ● SDK                               │
└──────────────────────────────────────┘

中影響 × 低緊迫
┌──────────────────────────────────────┐
│ ○ 推理快取                           │
│ ○ 異常偵測                           │
│ ○ Webhook 系統                       │
│ ○ 市場 / 插件系統                    │
└──────────────────────────────────────┘
```

---

## 12. 可利用的現有優勢

儘管差距龐大，NemoClaw 現有架構中有若干重要資產可以直接複用：

1. **安全沙箱技術**（Landlock + seccomp + netns）→ 直接成為 SaaS 的核心差異化能力
2. **藍圖系統**（YAML blueprint）→ 可擴展為租戶自訂沙箱模板
3. **SSRF 防禦**（ssrf.ts）→ 可提升至 API Gateway 層面
4. **推理路由邏輯**（inference module）→ 可包裝為 Inference Gateway 服務
5. **網路政策預設**（policies/presets/）→ 可作為平台層政策的基礎
6. **k8s/ 目錄**（實驗性 manifests）→ 多租戶 K8s 架構的起始點
7. **測試架構**（三層測試）→ 可擴展至 SaaS 服務測試

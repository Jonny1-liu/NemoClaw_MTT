# NemoClaw 現有架構深度解析

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 整體架構圖（現況）

```
┌──────────────────────────────────────────────────────────────────────┐
│                    使用者機器（Host Machine）                           │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                   NemoClaw CLI（Node.js/TS）                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │  │
│  │  │  onboard │ │credentials│ │inference │ │  policies/runner │  │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │  │
│  └───────┼────────────┼────────────┼─────────────────┼────────────┘  │
│          │            │            │                  │               │
│  ┌───────▼────────────────────────────────────────────▼────────────┐  │
│  │              OpenShell Gateway Container（Docker）               │  │
│  │                                                                   │  │
│  │  ┌────────────────────────────────────────────────────────────┐  │  │
│  │  │                    k3s（embedded）                          │  │  │
│  │  │                                                              │  │  │
│  │  │  ┌──────────────────────────────────────────────────────┐  │  │  │
│  │  │  │              NemoClaw Sandbox Pod                     │  │  │  │
│  │  │  │                                                        │  │  │  │
│  │  │  │  ┌────────────────────┐  ┌──────────────────────────┐ │  │  │  │
│  │  │  │  │   OpenClaw Agent   │  │   NemoClaw Plugin（TS）   │ │  │  │  │
│  │  │  │  │  (always-on)       │  │  slash cmds / blueprint   │ │  │  │  │
│  │  │  │  └────────────────────┘  └──────────────────────────┘ │  │  │  │
│  │  │  │                                                        │  │  │  │
│  │  │  │  Security: Landlock + seccomp + netns + cap drops      │  │  │  │
│  │  │  └──────────────────────────────────────────────────────┘  │  │  │
│  │  └────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  Local State: ~/.nemoclaw/ (credentials, blueprints, snapshots)        │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS（推理請求）
                              ▼
               ┌──────────────────────────────┐
               │   NVIDIA Endpoints            │
               │   (Nemotron-3-Super-120B)     │
               │        或                     │
               │   Ollama（本機 GPU 推理）       │
               └──────────────────────────────┘
```

---

## 2. 目錄結構與職責

```
NemoClaw/
├── bin/                    # CLI 入口點（CommonJS）
│   └── nemoclaw.js         # 可執行入口，載入 dist/
│
├── src/                    # 主 CLI TypeScript 原始碼
│   └── lib/
│       ├── onboard/        # 引導精靈邏輯
│       ├── credentials/    # 本機憑證管理（API keys）
│       ├── inference/      # 推理後端路由與驗證
│       ├── policies/       # 網路政策管理
│       ├── preflight/      # 環境預檢（Docker、Node.js 版本等）
│       └── runner/         # 沙箱生命週期管理
│
├── nemoclaw/               # TypeScript Plugin（Commander 擴充）
│   └── src/
│       ├── blueprint/      # 藍圖執行器、快照、SSRF 驗證、狀態
│       ├── commands/       # Slash 命令、migration 狀態
│       └── onboard/        # Plugin 初始化設定
│
├── nemoclaw-blueprint/     # 藍圖定義（YAML）
│   └── policies/
│       └── presets/        # 預設網路政策（slack.yaml、discord.yaml 等）
│
├── k8s/                    # Kubernetes manifests（實驗性）
├── scripts/                # 安裝助手、自動化腳本
├── test/                   # 整合測試（Vitest）
│   └── e2e/                # E2E 測試（Brev 雲端實例）
└── docs/                   # Sphinx/MyST 使用者文件
```

---

## 3. 核心元件詳解

### 3.1 CLI 層（`src/lib/`）

#### `credentials` 模組
- **功能**：管理 NVIDIA API Key、Ollama endpoint 等憑證
- **儲存位置**：本機檔案系統（`~/.nemoclaw/` 或類似路徑）
- **加密**：未提及加密靜態儲存（單機設計的簡化假設）
- **多租戶問題**：憑證與本機用戶綁定，無法集中管理

#### `inference` 模組
- **功能**：路由推理請求至適當後端
- **支援後端**：
  - NVIDIA Endpoints（雲端，需 API Key）
  - Ollama（本機 GPU，無需 API Key）
- **驗證**：推理設定的有效性驗證
- **多租戶問題**：每個實例獨立設定，無共享推理池

#### `policies` 模組
- **功能**：管理 OpenShell 的出口網路政策
- **機制**：YAML 政策文件 → OpenShell gateway 套用 iptables/eBPF 規則
- **預設政策**：Slack、Discord、GitHub 等預設允許清單
- **多租戶問題**：政策與個別沙箱綁定，無租戶層級的政策繼承

#### `runner` 模組
- **功能**：沙箱的建立、啟動、停止、銷毀
- **機制**：呼叫 OpenShell CLI (`openshell sandbox create/start/stop`)
- **狀態追蹤**：本機 JSON 狀態文件
- **多租戶問題**：無中央化的沙箱調度，每機器獨立管理

### 3.2 Plugin 層（`nemoclaw/src/`）

#### `blueprint/` 子模組
| 檔案 | 職責 |
|------|------|
| `runner.ts` | 執行藍圖生命週期（apply/destroy） |
| `snapshot.ts` | 代理狀態快照與恢復 |
| `ssrf.ts` | SSRF 攻擊防禦驗證 |
| `state.ts` | 本機狀態持久化 |

#### `commands/` 子模組
- OpenClaw 內的 `/` 斜線命令
- Migration 狀態機（版本升級處理）

### 3.3 Blueprint 層（`nemoclaw-blueprint/`）

藍圖是一個 YAML 定義文件，描述：
- 沙箱容器規格（映像、資源限制）
- 預設掛載點
- 環境變數注入
- 初始網路政策
- 安全設定（capabilities、seccomp profiles）

```yaml
# 概念性藍圖結構（非實際程式碼）
sandbox:
  image: nemoclaw-sandbox:latest
  resources:
    cpu: "2"
    memory: "4Gi"
  security:
    capabilities: DROP_ALL
    seccomp: runtime/default
    landlock: enabled
  network:
    policies:
      - presets/default.yaml
  state:
    snapshot_interval: 300s
```

### 3.4 安全層

```
┌────────────────────────────────────────────────────────────┐
│                    安全防護層次                              │
│                                                              │
│  Layer 4: 應用層                                            │
│  ├── SSRF 驗證（ssrf.ts）                                   │
│  └── 憑證防洩漏（credentials sanitization）                  │
│                                                              │
│  Layer 3: 容器層                                            │
│  ├── Docker capability drops（ALL）                          │
│  ├── 程序數量限制（防 fork bomb）                            │
│  └── 唯讀根檔案系統                                          │
│                                                              │
│  Layer 2: 核心層                                             │
│  ├── seccomp（系統呼叫白名單）                               │
│  └── Landlock（檔案系統存取控制）                            │
│                                                              │
│  Layer 1: 網路層                                            │
│  ├── 網路命名空間隔離                                        │
│  └── 出口政策（iptables/eBPF）                              │
└────────────────────────────────────────────────────────────┘
```

---

## 4. 資料流分析

### 4.1 推理請求流程

```
使用者 → OpenClaw TUI/CLI
         → NemoClaw Plugin（命令解析）
           → inference 模組（路由選擇）
             → SSRF 驗證
               → NVIDIA Endpoints 或 Ollama
                 → 回應 → 使用者
```

### 4.2 沙箱初始化流程

```
nemoclaw onboard
  → preflight 檢查（Docker? Node? 版本?）
  → 詢問推理後端設定
  → 儲存憑證（本機）
  → openshell gateway start（啟動 k3s）
  → openshell sandbox create（從藍圖建立 Pod）
  → 套用網路政策
  → 驗證沙箱健康狀態
  → 顯示完成摘要
```

### 4.3 狀態快照流程

```
定時或手動觸發
  → snapshot.ts 讀取代理狀態
  → 序列化至 JSON
  → 儲存至本機 ~/.nemoclaw/snapshots/
```

---

## 5. 依賴關係圖

```
NemoClaw CLI
    ├── Node.js 22.16+
    ├── npm 10+
    ├── OpenShell CLI（openshell binary）
    └── Docker（container runtime）
         └── k3s（embedded in gateway container）
              └── 沙箱 Pod
                   ├── OpenClaw（AI agent runtime）
                   └── NemoClaw Plugin（TS compiled）
                        └── Inference Backend
                             ├── NVIDIA Endpoints API
                             └── Ollama（optional, local）
```

---

## 6. 狀態管理現況

| 狀態類型 | 儲存位置 | 格式 | 問題 |
|---------|---------|------|------|
| 用戶憑證 | `~/.nemoclaw/config` | JSON/YAML | 本機，無加密 |
| 沙箱設定 | `~/.nemoclaw/blueprints/` | YAML | 本機，無版本控制 |
| 代理狀態快照 | `~/.nemoclaw/snapshots/` | JSON | 本機，無備份 |
| 推理設定 | `~/.nemoclaw/inference` | JSON | 本機，無共享 |
| 網路政策 | `nemoclaw-blueprint/policies/` | YAML | Git 倉庫，非動態 |

---

## 7. 網路架構現況

```
沙箱內部（隔離網路命名空間）
  ├── OpenClaw Agent
  └── NemoClaw Plugin
        │
        │（出口政策控制）
        ▼
OpenShell Gateway（iptables/eBPF 出口控制）
        │
        ├── 允許：NVIDIA Endpoints (*.nvidia.com)
        ├── 允許：Ollama localhost
        ├── 允許：預設政策中的服務（Slack、Discord 等）
        └── 拒絕：所有其他出口流量
```

---

## 8. 測試架構

```
vitest.config.ts 定義三個專案：

1. cli    → test/**/*.test.{js,ts}
             CLI 行為整合測試（ESM）

2. plugin → nemoclaw/src/**/*.test.ts
             Plugin 單元測試（TypeScript，與原始碼共置）

3. e2e-brev → test/e2e/brev-e2e.test.js
               雲端 E2E 測試（需要 BREV_API_TOKEN）
               在 Brev 雲端臨時實例上執行
```

---

## 9. CI/CD 流程

```
Git Push
  → prek pre-push hook
    ├── TypeScript 型別檢查（tsc --noEmit）
    └── （其他 lint 規則）

PR 建立
  → GitHub Actions CI
    ├── make check（所有 linter）
    ├── npm test（unit + integration）
    └── E2E（如有 BREV_API_TOKEN）
```

---

## 10. 現有 Kubernetes 支援

`k8s/` 目錄包含實驗性的 Kubernetes manifests。這暗示 NVIDIA 已經在考慮叢集化部署，但目前主要場景仍是單機 Docker 方式。

k8s 目錄的存在是轉型為多租戶平台的一個重要起點。

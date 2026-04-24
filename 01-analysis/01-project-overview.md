# NemoClaw 專案概覽分析

> 文件版本：v1.0 | 撰寫日期：2026-04-16 | 來源：https://github.com/NVIDIA/NemoClaw

---

## 1. 專案定位

**NVIDIA NemoClaw** 是一個開源的參考堆疊（Reference Stack），專為在 NVIDIA OpenShell 沙箱環境中安全地運行 [OpenClaw](https://openclaw.ai) 持續性 AI 助理而設計。

- **發布狀態**：Alpha（2026 年 3 月 16 日起）
- **授權**：Apache 2.0
- **主要語言**：TypeScript (70.3%)、Shell (25.7%)、Python (2.6%)
- **GitHub Stars**：~19k（截至 2026-04-16）
- **核心依賴**：NVIDIA OpenShell runtime（NVIDIA Agent Toolkit 的一部分）

### 核心價值主張

NemoClaw 在 OpenClaw 這個 AI 助理框架之上，疊加了以下能力：

1. **引導式初始化（Guided Onboarding）** — 自動化設定沙箱、推理端點、安全政策
2. **強化藍圖（Hardened Blueprint）** — 經過安全加固的沙箱設定模板
3. **狀態管理（State Management）** — 代理狀態快照與恢復
4. **通道訊息管理（Channel Messaging）** — OpenShell 管理的通訊通道
5. **路由式推理（Routed Inference）** — 支援多種推理後端（NVIDIA Endpoints、Ollama）
6. **分層防護（Layered Protection）** — Landlock + seccomp + 網路命名空間

---

## 2. 技術生態系

```
┌─────────────────────────────────────────────┐
│              NemoClaw (本專案)                │
│  CLI 工具 + 藍圖 + 安全層 + 狀態管理          │
└───────────────────────┬─────────────────────┘
                        │ 建立於
                        ▼
┌─────────────────────────────────────────────┐
│         NVIDIA OpenShell Runtime             │
│   k3s + 沙箱容器 + 網路命名空間               │
└───────────────────────┬─────────────────────┘
                        │ 運行
                        ▼
┌─────────────────────────────────────────────┐
│              OpenClaw Agent                  │
│   持續性 AI 助理核心 + 工具使用能力            │
└───────────────────────┬─────────────────────┘
                        │ 呼叫
                        ▼
┌─────────────────────────────────────────────┐
│           推理後端（Inference）               │
│  NVIDIA Endpoints (Nemotron-3) / Ollama      │
└─────────────────────────────────────────────┘
```

---

## 3. 支援平台

| 作業系統 | 容器執行環境 | 狀態 |
|----------|-------------|------|
| Linux | Docker | ✅ 主要測試路徑 |
| macOS (Apple Silicon) | Colima / Docker Desktop | ✅ 有限支援 |
| DGX Spark | Docker | ✅ 已測試 |
| Windows WSL2 | Docker Desktop (WSL backend) | ✅ 有限支援 |

---

## 4. 硬體需求

| 資源 | 最低需求 | 建議需求 |
|------|---------|---------|
| CPU | 4 vCPU | 4+ vCPU |
| RAM | 8 GB | 16 GB |
| 磁碟 | 20 GB 可用 | 40 GB 可用 |

沙箱映像約 2.4 GB（壓縮後）。低於 8 GB RAM 的機器可能觸發 OOM killer。

---

## 5. 主要功能模組

### 5.1 CLI 工具（`bin/` + `src/lib/`）
- `nemoclaw onboard` — 引導式初始化精靈
- `nemoclaw <name> connect` — 連接至沙箱
- `nemoclaw <name> status` — 查看狀態
- `nemoclaw <name> logs` — 查看日誌
- `nemoclaw setup-spark` — DGX Spark 專用設定

### 5.2 藍圖引擎（`nemoclaw-blueprint/`）
- YAML 定義的沙箱設定
- 網路政策（出口控制）
- 預設政策：Slack、Discord 等

### 5.3 Plugin 系統（`nemoclaw/`）
- Commander CLI 擴充
- Slash 命令支援
- 狀態快照機制
- SSRF 驗證

### 5.4 安全層
- **Landlock**：檔案系統存取控制（Linux Kernel 5.13+）
- **seccomp**：系統呼叫過濾
- **網路命名空間**：網路隔離
- **Docker capability drops**：最小化容器權限
- **程序限制**：防止 fork bomb
- **SSRF 驗證**：防止伺服端請求偽造

---

## 6. 目前的使用流程

```
1. 使用者執行安裝腳本
   curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash

2. NemoClaw 安裝 Node.js（透過 nvm）並設定環境

3. 執行 nemoclaw onboard（引導精靈）
   - 選擇推理後端（NVIDIA Endpoints 或 Ollama）
   - 設定 API 金鑰
   - 建立沙箱（OpenShell gateway + k3s）
   - 套用安全政策

4. 連接至沙箱
   nemoclaw my-assistant connect

5. 在沙箱內使用 OpenClaw
   openclaw tui          # 互動式 TUI
   openclaw agent -m "..." # 單次查詢
```

---

## 7. 專案成熟度評估

| 面向 | 評估 | 備註 |
|------|------|------|
| 程式碼品質 | ⭐⭐⭐⭐ | TypeScript + 嚴格 lint + commitlint |
| 測試覆蓋 | ⭐⭐⭐ | 三層測試（unit/integration/e2e）但 Alpha 階段 |
| 文件完整性 | ⭐⭐⭐⭐ | Sphinx 文件站 + AGENTS.md |
| 安全設計 | ⭐⭐⭐⭐⭐ | 多層沙箱防護，SSRF 防禦 |
| 可擴展性 | ⭐⭐ | 單機設計，無多租戶概念 |
| 生產就緒性 | ⭐⭐ | 明確標示為 Alpha，不建議生產使用 |

---

## 8. 總結

NemoClaw 是一個設計精良的**單機、單用戶**參考實作，核心優勢在於安全沙箱隔離與簡化的代理管理體驗。然而作為 SaaS 平台的基礎，它目前缺乏多租戶架構所需的所有關鍵能力，需要進行系統性的架構升級。詳細的差距分析請參見 `03-gap-analysis.md`。

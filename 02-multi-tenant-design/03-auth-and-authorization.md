# 身份驗證與授權設計

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 身份驗證架構

### 1.1 整體 Auth 流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       用戶（Browser / CLI）                       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                      ┌───────────▼───────────┐
                      │     API Gateway        │
                      │  (JWT 驗證 middleware)  │
                      └───────────┬───────────┘
                                  │
              ┌───────────────────┼──────────────────────┐
              │                   │                      │
              ▼                   ▼                      ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │  Auth Service   │  │  Web Console    │  │   Public API    │
    │  (Keycloak)     │  │  (Next.js)      │  │  (REST/gRPC)    │
    └─────────────────┘  └─────────────────┘  └─────────────────┘
              │
    ┌─────────▼─────────┐
    │  Identity Store    │
    │  (PostgreSQL)      │
    │  + External IdP    │
    │  (SAML/OIDC SSO)   │
    └───────────────────┘
```

### 1.2 認證方式

| 認證方式 | 使用場景 | 方案 |
|---------|---------|------|
| Email + Password | 一般用戶登入 | 全方案 |
| Social Login (GitHub/Google) | 快速註冊 | Free/Pro |
| SSO (SAML 2.0 / OIDC) | 企業用戶整合 IdP | Enterprise |
| API Token | CLI / 程式化存取 | 全方案 |
| mTLS（服務間） | 服務帳號 | 內部服務 |

---

## 2. JWT Token 設計

### 2.1 Access Token 結構

```json
// Header
{
  "alg": "RS256",
  "typ": "JWT",
  "kid": "2026-04-key-1"
}

// Payload
{
  "iss": "https://auth.nemoclaw.ai",
  "sub": "user-uuid-12345",
  "aud": ["nemoclaw-api", "nemoclaw-console"],
  "exp": 1745000000,
  "iat": 1744999100,
  "nbf": 1744999100,
  "jti": "unique-token-id",

  // NemoClaw 自訂 Claims
  "tenant_id": "tenant-abc123",
  "tenant_name": "ACME Corp",
  "plan": "pro",
  "roles": ["tenant:pro:admin"],
  "permissions": [
    "sandboxes:create",
    "sandboxes:read",
    "sandboxes:delete",
    "inference:use",
    "policies:read",
    "policies:write",
    "members:invite"
  ],
  "sandbox_quota": 5,
  "token_quota_monthly": 1000000
}
```

### 2.2 Token 有效期設定

| Token 類型 | 有效期 | 儲存位置 |
|-----------|--------|---------|
| Access Token | 15 分鐘 | 記憶體（不存 localStorage） |
| Refresh Token | 7 天（滑動） | HttpOnly Cookie（Secure） |
| API Token（CLI） | 90 天（可撤銷） | Vault（hashed） |
| Service Account Token | 24 小時（自動輪換） | K8s Secret + Vault |

---

## 3. RBAC 設計

### 3.1 角色定義

```
Platform Level（平台層）：
  ├── platform:super-admin    # 平台工程師（最高權限）
  ├── platform:admin          # 客服/運維人員
  └── platform:viewer         # 唯讀監控

Tenant Level（租戶層）：
  ├── tenant:{plan}:owner     # 租戶擁有者（帳單、刪除租戶）
  ├── tenant:{plan}:admin     # 管理員（成員管理、設定）
  ├── tenant:{plan}:developer # 開發者（沙箱 CRUD、推理使用）
  └── tenant:{plan}:viewer    # 唯讀查看
```

### 3.2 權限矩陣

| 操作 | Owner | Admin | Developer | Viewer |
|------|:-----:|:-----:|:---------:|:------:|
| 建立沙箱 | ✅ | ✅ | ✅ | ❌ |
| 刪除沙箱 | ✅ | ✅ | ✅ | ❌ |
| 連接沙箱 | ✅ | ✅ | ✅ | ❌ |
| 查看沙箱 | ✅ | ✅ | ✅ | ✅ |
| 修改網路政策 | ✅ | ✅ | ❌ | ❌ |
| 查看網路政策 | ✅ | ✅ | ✅ | ✅ |
| 邀請成員 | ✅ | ✅ | ❌ | ❌ |
| 管理 API Token | ✅ | ✅ | 自己的 | 自己的 |
| 查看用量統計 | ✅ | ✅ | ✅ | ✅ |
| 修改計費資訊 | ✅ | ❌ | ❌ | ❌ |
| 刪除租戶 | ✅ | ❌ | ❌ | ❌ |
| 自訂藍圖 | ✅ | ✅ | ✅ | ❌ |
| 匯出資料 | ✅ | ✅ | ❌ | ❌ |

### 3.3 RBAC 實作（OPA Policy）

```rego
package nemoclaw.authz

import future.keywords

# 主要決策點
default allow := false

allow if {
  has_permission
}

# 租戶邊界強制執行
has_permission if {
  input.user.tenant_id == input.resource.tenant_id
  permission_granted
}

# Platform admin 可跨租戶操作
has_permission if {
  "platform:admin" in input.user.roles
}

# 權限檢查
permission_granted if {
  required := required_permission[input.action]
  required in input.user.permissions
}

# 動作與所需權限的對應
required_permission := {
  "sandbox.create": "sandboxes:create",
  "sandbox.delete": "sandboxes:delete",
  "sandbox.connect": "sandboxes:connect",
  "sandbox.read": "sandboxes:read",
  "policy.write": "policies:write",
  "policy.read": "policies:read",
  "inference.use": "inference:use",
  "member.invite": "members:invite",
  "billing.manage": "billing:manage",
}
```

---

## 4. API Token 管理

### 4.1 Token 生命週期

```
生成：
  POST /api/v1/tokens
  {
    "name": "my-ci-token",
    "expires_in_days": 90,
    "scopes": ["sandboxes:read", "inference:use"]
  }
  
  Response:
  {
    "token_id": "tok_abc123",
    "token": "sk-live-xxxxxxxxxxxx",  // 只顯示一次！
    "expires_at": "2026-07-16T00:00:00Z"
  }

儲存（Server Side）：
  - token_id 儲存至 DB
  - token 以 SHA-256 hash 後儲存（不存原文）
  - 查詢時比對 hash

使用：
  Authorization: Bearer sk-live-xxxxxxxxxxxx

撤銷：
  DELETE /api/v1/tokens/{token_id}
  - 立即生效（Redis 黑名單，TTL = token 剩餘有效期）
```

### 4.2 Token 輪換

```
API Token 90 天後自動到期：
  - 提前 14 天 Email 提醒
  - 提前 7 天再次提醒
  - 到期後 API 返回 401 + 訊息說明如何更新

CI/CD Token 建議：
  - 使用短期 Token（30 天）
  - 搭配 GitHub Actions OIDC 自動輪換（免密碼）
```

---

## 5. SSO 整合（Enterprise）

### 5.1 SAML 2.0 整合

```
設定流程：
  1. Enterprise 管理員在 Web Console 進入 SSO 設定頁面
  2. 下載 NemoClaw 的 Service Provider Metadata
  3. 在客戶 IdP（Okta/Azure AD/Ping）建立 Application
  4. 上傳客戶 IdP Metadata 至 NemoClaw
  5. 設定屬性對應：
     - email → email
     - groups → nemoclaw_roles（對應到 admin/developer/viewer）
  6. 測試 SSO 登入流程
  7. 啟用 SSO（可同時保留 Email 登入作為備用）

Just-In-Time Provisioning：
  - 首次 SSO 登入時自動建立用戶帳號
  - 角色根據 IdP 群組自動對應
  - 離職員工從 IdP 移除後，下次 token 過期即無法存取
```

### 5.2 SCIM 自動同步（Enterprise Plus）

```
SCIM 2.0 端點：
  GET  /scim/v2/Users
  POST /scim/v2/Users
  PUT  /scim/v2/Users/{id}
  DELETE /scim/v2/Users/{id}  // 停用，不刪除資料

功能：
  - 從 IdP 自動同步用戶列表
  - 自動建立/停用帳號
  - 自動同步角色/群組
```

---

## 6. MFA（多因素驗證）

| MFA 類型 | 說明 | 支援方案 |
|---------|------|---------|
| TOTP（驗證器 App） | Google Authenticator、Authy 等 | 全方案 |
| WebAuthn（硬體金鑰） | YubiKey、Touch ID 等 | Pro+ |
| 備用碼（Recovery Code） | 一次性備用碼 | 全方案 |
| Email OTP | 登入時發送驗證碼 | 全方案 |

```
MFA 強制要求：
  - Enterprise 方案：管理員可設定全員強制 MFA
  - Admin 角色：平台強制 MFA
  - API Token 操作（建立/刪除）：需 MFA 重新確認
```

---

## 7. 安全審計日誌

所有認證與授權事件均記錄：

```json
{
  "event_id": "evt-uuid",
  "timestamp": "2026-04-16T10:30:00Z",
  "event_type": "auth.login_success",
  "actor": {
    "user_id": "user-uuid",
    "email": "user@example.com",
    "tenant_id": "tenant-abc123",
    "ip": "203.0.113.1",
    "user_agent": "NemoClaw-CLI/2.0.0"
  },
  "resource": {
    "type": "session",
    "id": "session-uuid"
  },
  "result": "success",
  "mfa_used": true
}
```

稽核事件類型：
- `auth.login_success/failure`
- `auth.logout`
- `auth.token_created/revoked`
- `auth.mfa_enabled/disabled`
- `authz.permission_denied`
- `tenant.member_invited/removed`
- `tenant.role_changed`
- `sandbox.created/deleted`
- `policy.modified`
- `billing.plan_changed`

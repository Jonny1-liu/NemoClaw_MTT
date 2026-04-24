# 可觀測性設計（Observability）

> 文件版本：v1.0 | 撰寫日期：2026-04-16

---

## 1. 可觀測性三支柱

```
┌────────────────────────────────────────────────────────────────┐
│                    可觀測性架構（LGTM Stack）                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │    Metrics    │  │     Logs     │  │       Traces         │ │
│  │   Prometheus  │  │    Loki      │  │  Grafana Tempo       │ │
│  │  + Thanos     │  │  + Promtail  │  │  (OpenTelemetry)     │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│           │               │                    │               │
│           └───────────────┼────────────────────┘               │
│                           ▼                                    │
│                    ┌─────────────┐                             │
│                    │   Grafana   │                             │
│                    │  Dashboard  │                             │
│                    └─────────────┘                             │
│                           │                                    │
│                    ┌─────────────┐                             │
│                    │ AlertManager│                             │
│                    │  + PagerDuty│                             │
│                    └─────────────┘                             │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. 指標（Metrics）

### 2.1 平台層指標

```yaml
# Prometheus 指標定義（節錄）

# 沙箱相關
nemoclaw_sandboxes_total{tenant_id, status, plan}
nemoclaw_sandbox_create_duration_seconds{tenant_id, blueprint}
nemoclaw_sandbox_uptime_seconds{tenant_id, sandbox_id}
nemoclaw_sandbox_restarts_total{tenant_id, sandbox_id, reason}

# 推理相關
nemoclaw_inference_requests_total{tenant_id, model, status}
nemoclaw_inference_tokens_total{tenant_id, model, type}  # type=input|output
nemoclaw_inference_latency_seconds{tenant_id, model, quantile}
nemoclaw_inference_queue_length{tenant_id}

# 配額相關
nemoclaw_quota_tokens_used{tenant_id}
nemoclaw_quota_tokens_limit{tenant_id, plan}
nemoclaw_quota_sandboxes_used{tenant_id}

# API Gateway
nemoclaw_api_requests_total{method, path, status, tenant_id}
nemoclaw_api_request_duration_seconds{method, path, quantile}
nemoclaw_api_rate_limit_hits_total{tenant_id, limit_type}

# 系統資源（per sandbox）
nemoclaw_sandbox_cpu_usage_cores{tenant_id, sandbox_id}
nemoclaw_sandbox_memory_usage_bytes{tenant_id, sandbox_id}
nemoclaw_sandbox_network_bytes_total{tenant_id, sandbox_id, direction}
```

### 2.2 SLO 指標定義

```yaml
# SLO 定義（Sloth 格式）
apiVersion: sloth.slok.dev/v1
kind: PrometheusServiceLevel
metadata:
  name: nemoclaw-api-availability
spec:
  service: "nemoclaw-api"
  slos:
  - name: "requests-availability"
    objective: 99.9
    description: "99.9% of API requests succeed"
    sli:
      events:
        errorQuery: |
          sum(rate(nemoclaw_api_requests_total{status=~"5.."}[{{.window}}]))
        totalQuery: |
          sum(rate(nemoclaw_api_requests_total[{{.window}}]))
    alerting:
      pageAlert:
        labels:
          severity: critical
      ticketAlert:
        labels:
          severity: warning

  - name: "sandbox-creation-latency"
    objective: 95
    description: "95% of sandbox creations complete within 60 seconds"
    sli:
      events:
        errorQuery: |
          sum(rate(nemoclaw_sandbox_create_duration_seconds_bucket{le="60"}[{{.window}}]))
        totalQuery: |
          sum(rate(nemoclaw_sandbox_create_duration_seconds_count[{{.window}}]))
```

---

## 3. 日誌（Logging）

### 3.1 日誌結構化規範

```json
// 所有服務日誌必須使用 JSON 格式（Structured Logging）
{
  "timestamp": "2026-04-16T10:30:00.123Z",
  "level": "info",
  "service": "sandbox-orchestrator",
  "version": "1.2.0",
  "trace_id": "4bf92f3577b34da6",
  "span_id": "00f067aa0ba902b7",
  "tenant_id": "tenant-abc123",
  "sandbox_id": "sb-xyz789",
  "user_id": "user-123",
  "message": "Sandbox created successfully",
  "duration_ms": 28450,
  "fields": {
    "blueprint_id": "bp-standard",
    "namespace": "tenant-abc123",
    "pod_name": "sandbox-sb-xyz789"
  }
}
```

### 3.2 日誌隔離策略

```
租戶日誌隔離：
  - 所有日誌攜帶 tenant_id 標籤
  - Loki 查詢時強制過濾 tenant_id
  - 用戶透過 Console/API 只能查看自己租戶的日誌
  - 平台管理員可查看所有租戶日誌（額外審計記錄）

Loki Label 設計：
  {
    "app": "sandbox-orchestrator",
    "tenant_id": "tenant-abc123",
    "environment": "production",
    "region": "us-east-1"
  }

日誌保留政策：
  Free：7 天
  Pro：30 天
  Team：90 天
  Enterprise：1 年（可延長）
```

### 3.3 敏感資訊遮蔽

```go
// 日誌中的敏感資訊必須遮蔽
type LogSanitizer struct {
    patterns []SanitizePattern
}

var defaultPatterns = []SanitizePattern{
    {Pattern: `sk-[a-zA-Z0-9]{32,}`, Replacement: "sk-***"},           // API Keys
    {Pattern: `Bearer [a-zA-Z0-9._-]{20,}`, Replacement: "Bearer ***"}, // JWT
    {Pattern: `[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}`, Replacement: "****-****-****-****"}, // Credit card
    {Pattern: `\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b`, Replacement: "***@***.***"},   // Email
}
```

---

## 4. 分散式追蹤（Tracing）

### 4.1 OpenTelemetry 整合

```go
// 所有服務使用 OpenTelemetry SDK

// 初始化 Tracer
func initTracer(serviceName string) {
    exporter, _ := otlptracehttp.New(context.Background(),
        otlptracehttp.WithEndpoint("tempo:4318"),
    )
    
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName(serviceName),
            semconv.ServiceVersion(version),
            attribute.String("tenant.id", tenantID),
        )),
    )
    otel.SetTracerProvider(tp)
}

// 使用範例
func (s *SandboxService) Create(ctx context.Context, req *CreateRequest) (*Sandbox, error) {
    ctx, span := tracer.Start(ctx, "sandbox.create",
        trace.WithAttributes(
            attribute.String("tenant.id", req.TenantID),
            attribute.String("blueprint.id", req.BlueprintID),
        ),
    )
    defer span.End()
    
    // ...業務邏輯...
    
    span.SetAttributes(attribute.String("sandbox.id", sandbox.ID))
    return sandbox, nil
}
```

### 4.2 追蹤傳播

```
使用者請求 → API Gateway（Span A）
                └──→ Auth Service（Span B，子 Span）
                └──→ Sandbox Orchestrator（Span C，子 Span）
                        └──→ K8s API（Span D，子 Span）
                        └──→ Vault（Span E，子 Span）

W3C TraceContext Header 跨服務傳播：
  traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

---

## 5. 告警設計

### 5.1 告警規則

```yaml
# Prometheus AlertRules

groups:
- name: nemoclaw-platform
  rules:
  # API 可用性
  - alert: APIHighErrorRate
    expr: |
      sum(rate(nemoclaw_api_requests_total{status=~"5.."}[5m])) /
      sum(rate(nemoclaw_api_requests_total[5m])) > 0.05
    for: 5m
    labels:
      severity: critical
      team: platform
    annotations:
      summary: "API error rate > 5%"
      runbook: "https://runbooks.nemoclaw.ai/api-high-error-rate"

  # 沙箱建立延遲
  - alert: SandboxCreationSlow
    expr: |
      histogram_quantile(0.95, rate(nemoclaw_sandbox_create_duration_seconds_bucket[10m])) > 120
    for: 5m
    labels:
      severity: warning
      team: platform
    annotations:
      summary: "P95 sandbox creation time > 120 seconds"

  # 推理 Gateway 佇列積壓
  - alert: InferenceQueueBacklog
    expr: nemoclaw_inference_queue_length > 100
    for: 3m
    labels:
      severity: warning
    annotations:
      summary: "Inference queue backlog: {{ $value }} requests"

  # 租戶配額接近耗盡
  - alert: TenantQuotaNearExhaustion
    expr: |
      nemoclaw_quota_tokens_used / nemoclaw_quota_tokens_limit > 0.9
    for: 1m
    labels:
      severity: info
      alert_channel: email  # 發送 Email 給租戶，非 PagerDuty
    annotations:
      tenant_id: "{{ $labels.tenant_id }}"

  # K8s 節點資源壓力
  - alert: NodeMemoryPressure
    expr: node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.1
    for: 5m
    labels:
      severity: warning
      team: infra
```

### 5.2 On-Call 輪值

```
告警路由：

Critical（立即響應，24/7）：
  → PagerDuty → On-call 工程師
  觸發條件：API down、資料庫不可用、安全事件

Warning（工作時間內響應）：
  → Slack #platform-alerts
  觸發條件：高延遲、配額警告、單節點故障

Info（非響應，記錄用）：
  → Slack #platform-info
  觸發條件：租戶配額 80%、計畫維護前通知
```

---

## 6. 租戶可見的用量儀表板

租戶可在 Console 中查看：

```
儀表板面板：
┌─────────────────────────────────────────────────┐
│  本月 Token 用量                                  │
│  [============================---] 450K / 1M 45% │
│                                                   │
│  活躍沙箱    平均回應時間    請求數/小時           │
│  3 / 5      1.2 秒          127                  │
│                                                   │
│  [折線圖：過去 7 天的每日 Token 用量]              │
│                                                   │
│  [表格：各沙箱的 Token 用量排名]                   │
│  Sandbox A  │ 280K tokens │ 62%                   │
│  Sandbox B  │ 120K tokens │ 27%                   │
│  Sandbox C  │  50K tokens │ 11%                   │
└─────────────────────────────────────────────────┘
```

API 端點：
- `GET /api/v1/usage/dashboard?period=7d` — 儀表板資料
- `GET /api/v1/usage/export?format=csv&start=...&end=...` — 匯出明細

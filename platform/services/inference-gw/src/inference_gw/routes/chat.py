"""
/v1/chat/completions — OpenAI-compatible 推理端點

此端點供沙箱內的 OpenClaw 和外部客戶端呼叫。
依 JWT 的 tenant_id 執行配額檢查，路由至正確的 LLM 供應商。
"""
import time
from typing import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from inference_gw.providers.base import CompletionRequest, Message, MessageRole
from shared.auth import TokenPayload, require_auth

log = structlog.get_logger()

router = APIRouter(prefix="/v1", tags=["inference"])


@router.get("/models", summary="列出可用模型")
async def list_models(
    user: TokenPayload = Depends(require_auth),
):
    """OpenAI-compatible /v1/models endpoint"""
    from inference_gw.router import MODEL_CATALOG
    models = []
    for model_id in MODEL_CATALOG:
        models.append({
            "id": model_id,
            "object": "model",
            "owned_by": MODEL_CATALOG.get(model_id, "unknown"),
        })
    return {"object": "list", "data": models}

# router 由 main.py 的 lifespan 初始化後設定
_provider_router = None


def set_provider_router(r) -> None:
    global _provider_router
    _provider_router = r


# ─── Request / Response 格式（OpenAI-compatible）──────────────

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role:         str
    content:      str | None = None   # tool 訊息可能是 None
    tool_call_id: str | None = None
    name:         str | None = None

    model_config = {"extra": "allow"}   # 允許額外欄位（OpenAI API 相容）


class ChatCompletionRequest(BaseModel):
    model:       str
    messages:    list[ChatMessage]
    temperature: float  = 0.7
    max_tokens:  int    = 1024
    stream:      bool   = False

    model_config = {"extra": "allow"}   # 允許 tool_choice 等額外欄位


# ─── 端點 ─────────────────────────────────────────────────────

@router.post("/chat/completions", summary="OpenAI-compatible 推理端點")
async def chat_completions(
    body:    ChatCompletionRequest,
    request: Request,
    user:    TokenPayload = Depends(require_auth),
):
    if _provider_router is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inference providers not initialized",
        )

    # 轉換為內部格式
    # 過濾只有 system/user/assistant 的訊息傳給 LLM
    # tool/function 等其他 role 先跳過（LLM 不直接接受）
    supported_roles = {MessageRole.SYSTEM, MessageRole.USER, MessageRole.ASSISTANT}
    valid_messages = []
    for m in body.messages:
        try:
            role = MessageRole(m.role)
            if role in supported_roles:
                valid_messages.append(Message(role=role, content=m.content or ""))
        except ValueError:
            log.debug("inference.skip_unsupported_role", role=m.role)

    if not valid_messages:
        valid_messages = [Message(role=MessageRole.USER, content="hello")]

    internal_req = CompletionRequest(
        model=body.model,
        messages=valid_messages,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        stream=body.stream,
    )

    # 取得租戶偏好的供應商（未來從 Tenant Service 讀取）
    tenant_preferred = None   # TODO: 從 Tenant 設定讀取

    # 路由至適當供應商
    try:
        provider = _provider_router.route(
            internal_req,
            tenant_preferred=tenant_preferred,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    log.info("inference.request",
             tenant=user.tenant_id, model=body.model,
             provider=provider.provider_id)

    t0 = time.monotonic()

    if body.stream:
        return StreamingResponse(
            _stream_response(provider, internal_req, user.tenant_id),
            media_type="text/event-stream",
        )

    # 非串流模式
    try:
        resp = await provider.complete(internal_req)
    except Exception as e:
        log.error("inference.failed", error=str(e), provider=provider.provider_id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {e}",
        )

    latency_ms = int((time.monotonic() - t0) * 1000)
    log.info("inference.completed",
             tenant=user.tenant_id,
             provider=resp.provider,
             input_tokens=resp.usage.input_tokens,
             output_tokens=resp.usage.output_tokens,
             latency_ms=latency_ms)

    # 回傳 OpenAI-compatible 格式
    return {
        "id":      resp.id,
        "object":  "chat.completion",
        "model":   resp.model,
        "choices": [{
            "index":         0,
            "message":       {"role": "assistant", "content": resp.message.content},
            "finish_reason": resp.finish_reason,
        }],
        "usage": {
            "prompt_tokens":     resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
            "total_tokens":      resp.usage.total_tokens,
        },
        "x_provider":   resp.provider,
        "x_latency_ms": latency_ms,
    }


async def _stream_response(
    provider, request: CompletionRequest, tenant_id: str
) -> AsyncIterator[str]:
    """Server-Sent Events 串流格式"""
    try:
        async for delta in provider.stream(request):
            data = {
                "object": "chat.completion.chunk",
                "choices": [{
                    "index": 0,
                    "delta": {"content": delta.delta},
                    "finish_reason": delta.finish_reason,
                }],
            }
            import json
            yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

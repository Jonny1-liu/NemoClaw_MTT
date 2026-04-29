"""
/v1/chat/completions — OpenAI-compatible 推理端點

此端點供沙箱內的 OpenClaw 和外部客戶端呼叫。
依 JWT 的 tenant_id 執行配額檢查，路由至正確的 LLM 供應商。
"""
import json
import time
from typing import Any, AsyncIterator

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

from typing import Any

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role:         str
    content:      Any = None   # str | list | None（OpenAI 多模態格式）
    tool_call_id: str | None = None
    name:         str | None = None

    model_config = {"extra": "allow"}


class ChatCompletionRequest(BaseModel):
    model:       str
    messages:    list[ChatMessage]
    temperature: float = 0.7
    max_tokens:  int   = 1024
    stream:      bool  = False

    model_config = {"extra": "allow"}


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
                # content 可能是 str、list 或 None
                if isinstance(m.content, list):
                    # 把 list 裡的 text 項目串接成 str
                    text = " ".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in m.content
                    )
                else:
                    text = m.content or ""
                valid_messages.append(Message(role=role, content=text))
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
    """
    Server-Sent Events 串流格式（OpenAI 標準格式）

    正確的 OpenAI streaming 格式：
      Chunk 1: {"delta": {"role": "assistant", "content": ""}, "finish_reason": null}
      Chunk N: {"delta": {"content": "..."}, "finish_reason": null}
      Final:   {"delta": {}, "finish_reason": "stop|tool_calls"}
      [DONE]

    finish_reason 必須在「空 delta 的獨立最後一個 chunk」，
    不能與 content 同在一個 chunk，否則 OpenClaw 無法正確識別 tool calls。
    """
    import time
    import uuid

    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:16]}"
    created  = int(time.time())
    model    = request.model

    def _chunk(delta_data: dict, finish_reason: str | None) -> str:
        return f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': created, 'model': model, 'choices': [{'index': 0, 'delta': delta_data, 'finish_reason': finish_reason}]})}\n\n"

    try:
        # Chunk 1：角色宣告
        yield _chunk({"role": "assistant", "content": ""}, None)

        full_content  = ""
        finish_reason = "stop"

        async for delta in provider.stream(request):
            if delta.delta:
                full_content += delta.delta
                # 內容 chunk：finish_reason 為 null
                yield _chunk({"content": delta.delta}, None)
            if delta.finish_reason:
                finish_reason = delta.finish_reason

        # 最後一個 chunk：空 delta + finish_reason
        yield _chunk({}, finish_reason)
        yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

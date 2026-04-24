"""Sandbox API 請求/回應格式"""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from sandbox.models.sandbox import SandboxStatus

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")


class NetworkPolicyRequest(BaseModel):
    allow_domains: list[str] = Field(default_factory=list,
                                     description="允許的出口 domain，例如 api.slack.com")
    deny_all_other: bool = True


class CreateSandboxRequest(BaseModel):
    name:            str = Field(min_length=2, max_length=63)
    inference_model: str = Field(default="llama-3.1-70b")
    network_policy:  NetworkPolicyRequest = Field(default_factory=NetworkPolicyRequest)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError("name 只能包含小寫英數字與連字號，不能以連字號開頭或結尾")
        return v


class UpdateNetworkPolicyRequest(BaseModel):
    allow_domains: list[str]
    deny_all_other: bool = True


class SandboxResponse(BaseModel):
    id:              uuid.UUID
    tenant_id:       str
    name:            str
    status:          SandboxStatus
    inference_model: str
    adapter:         str
    error_message:   str | None = None
    created_at:      datetime
    started_at:      datetime | None = None
    stopped_at:      datetime | None = None

    model_config = {"from_attributes": True}


class SandboxListResponse(BaseModel):
    items: list[SandboxResponse]
    total: int

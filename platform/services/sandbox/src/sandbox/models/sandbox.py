"""Sandbox ORM 模型"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SandboxStatus(str, enum.Enum):
    CREATING = "creating"
    RUNNING  = "running"
    STOPPING = "stopping"
    STOPPED  = "stopped"
    ERROR    = "error"
    DELETED  = "deleted"


class Sandbox(Base):
    __tablename__ = "sandboxes"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id:   Mapped[str]       = mapped_column(String(64),  nullable=False, index=True)
    name:        Mapped[str]       = mapped_column(String(255), nullable=False)
    status:      Mapped[SandboxStatus] = mapped_column(
        Enum(SandboxStatus, name="sandbox_status_enum",
             values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=SandboxStatus.CREATING,
    )
    external_id: Mapped[str | None]= mapped_column(String(255), nullable=True)
    adapter:     Mapped[str]       = mapped_column(String(50),  nullable=False, default="mock")
    inference_model:  Mapped[str]  = mapped_column(String(255), nullable=False, default="llama-3.1-70b")
    blueprint_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message:    Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    policies: Mapped[list["NetworkPolicyRecord"]] = relationship(
        "NetworkPolicyRecord", back_populates="sandbox", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Sandbox name={self.name} tenant={self.tenant_id} status={self.status}>"


class NetworkPolicyRecord(Base):
    """租戶自訂網路政策的歷史記錄"""
    __tablename__ = "sandbox_network_policies"

    id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sandbox_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sandboxes.id", ondelete="CASCADE"))
    policy_config: Mapped[dict]   = mapped_column(JSONB, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())

    sandbox: Mapped[Sandbox] = relationship("Sandbox", back_populates="policies")

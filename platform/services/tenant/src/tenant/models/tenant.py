"""SQLAlchemy ORM 模型 — 對應資料庫實際結構"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Plan(str, enum.Enum):
    FREE       = "free"
    PRO        = "pro"
    TEAM       = "team"
    ENTERPRISE = "enterprise"


class TenantStatus(str, enum.Enum):
    ACTIVE    = "active"
    SUSPENDED = "suspended"   # 欠費 / 超量暫停
    DELETED   = "deleted"     # 軟刪除


# 各方案的配額上限（-1 = 無限制）
PLAN_QUOTAS: dict[Plan, dict[str, int]] = {
    Plan.FREE:       {"tokens": 100_000,    "sandboxes": 1},
    Plan.PRO:        {"tokens": 1_000_000,  "sandboxes": 5},
    Plan.TEAM:       {"tokens": 5_000_000,  "sandboxes": 20},
    Plan.ENTERPRISE: {"tokens": -1,         "sandboxes": -1},
}


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63),  nullable=False, unique=True)
    plan: Mapped[Plan] = mapped_column(
        Enum(Plan, name="plan_enum",
             values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=Plan.FREE,
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status_enum",
             values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=TenantStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    quotas: Mapped[list["TenantQuota"]] = relationship(
        "TenantQuota", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant slug={self.slug} plan={self.plan}>"


class TenantQuota(Base):
    __tablename__ = "tenant_quotas"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    resource: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # "tokens" | "sandboxes"
    limit: Mapped[int]  = mapped_column(BigInteger, nullable=False)
    used:  Mapped[int]  = mapped_column(BigInteger, nullable=False, default=0)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="quotas")

    @property
    def remaining(self) -> int:
        """剩餘額度；-1 表示無限制"""
        if self.limit == -1:
            return -1
        return max(0, self.limit - self.used)

    @property
    def is_exceeded(self) -> bool:
        if self.limit == -1:
            return False
        return self.used >= self.limit

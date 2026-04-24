"""initial schema

Revision ID: 001
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenants 表
    op.create_table(
        "tenants",
        sa.Column("id",         sa.UUID(),        primary_key=True),
        sa.Column("name",       sa.String(255),   nullable=False),
        sa.Column("slug",       sa.String(63),    nullable=False),
        sa.Column("plan",       sa.Enum("free", "pro", "team", "enterprise",
                                        name="plan_enum"), nullable=False),
        sa.Column("status",     sa.Enum("active", "suspended", "deleted",
                                        name="tenant_status_enum"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # tenant_quotas 表
    op.create_table(
        "tenant_quotas",
        sa.Column("tenant_id", sa.UUID(),     nullable=False),
        sa.Column("resource",  sa.String(50), nullable=False),
        sa.Column("limit",     sa.BigInteger(), nullable=False),
        sa.Column("used",      sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reset_at",  sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "resource"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"],
                                ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("tenant_quotas")
    op.drop_table("tenants")
    op.execute("DROP TYPE IF EXISTS plan_enum")
    op.execute("DROP TYPE IF EXISTS tenant_status_enum")

"""initial schema

Revision ID: 001
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sandboxes",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id",        sa.String(64),  nullable=False),
        sa.Column("name",             sa.String(255), nullable=False),
        sa.Column("status",           sa.Enum(
            "creating", "running", "stopping", "stopped", "error", "deleted",
            name="sandbox_status_enum"), nullable=False),
        sa.Column("external_id",      sa.String(255), nullable=True),
        sa.Column("adapter",          sa.String(50),  nullable=False, server_default="mock"),
        sa.Column("inference_model",  sa.String(255), nullable=False),
        sa.Column("blueprint_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_message",    sa.Text(),      nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at",       sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at",       sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sandboxes_tenant_id", "sandboxes", ["tenant_id"])

    op.create_table(
        "sandbox_network_policies",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sandbox_id",    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sandboxes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_config", postgresql.JSONB(), nullable=False),
        sa.Column("applied_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sandbox_network_policies")
    op.drop_table("sandboxes")
    op.execute("DROP TYPE IF EXISTS sandbox_status_enum")

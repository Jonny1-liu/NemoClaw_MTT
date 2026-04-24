"""unique sandbox name per tenant (excluding deleted)

Revision ID: 002
Revises: 001
Create Date: 2026-04-23
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial Unique Index：同 Tenant 內名稱唯一，但已刪除的不算
    op.execute("""
        CREATE UNIQUE INDEX uix_sandbox_tenant_name
        ON sandboxes (tenant_id, name)
        WHERE status != 'deleted'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uix_sandbox_tenant_name")

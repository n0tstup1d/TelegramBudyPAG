"""add yookassa payment status fields

Revision ID: c4f0a1b2d3e4
Revises: b7e3d9a0c2f1
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4f0a1b2d3e4"
down_revision: Union[str, Sequence[str], None] = "b7e3d9a0c2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("provider", sa.String(length=32), nullable=False, server_default="legacy"))
    op.add_column("transactions", sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"))
    op.add_column("transactions", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_transactions_payment_id", "transactions", ["payment_id"], unique=False)
    op.create_index("ix_transactions_status", "transactions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transactions_status", table_name="transactions")
    op.drop_index("ix_transactions_payment_id", table_name="transactions")
    op.drop_column("transactions", "updated_at")
    op.drop_column("transactions", "status")
    op.drop_column("transactions", "provider")

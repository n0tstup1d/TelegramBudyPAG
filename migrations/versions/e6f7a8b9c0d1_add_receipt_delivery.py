"""add receipt queue and delivery fields

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("receipt_status", sa.String(length=24), nullable=False, server_default="not_required"),
    )
    op.add_column("transactions", sa.Column("receipt_url", sa.String(length=1024), nullable=True))
    op.add_column("transactions", sa.Column("receipt_file_id", sa.String(length=256), nullable=True))
    op.add_column("transactions", sa.Column("receipt_file_type", sa.String(length=16), nullable=True))
    op.add_column("transactions", sa.Column("receipt_delivery_method", sa.String(length=16), nullable=True))
    op.add_column("transactions", sa.Column("receipt_sent_at", sa.DateTime(), nullable=True))
    op.add_column("transactions", sa.Column("receipt_admin_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("receipt_reminder_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("transactions", sa.Column("receipt_updated_at", sa.DateTime(), nullable=True))

    op.create_index("ix_transactions_receipt_status", "transactions", ["receipt_status"], unique=False)
    op.create_index("ix_transactions_receipt_sent_at", "transactions", ["receipt_sent_at"], unique=False)

    # Уже подтверждённые платежи тоже должны попасть в очередь чеков.
    op.execute(
        """
        UPDATE transactions
        SET receipt_status = 'pending',
            receipt_updated_at = COALESCE(updated_at, created_at),
            receipt_reminder_level = 0
        WHERE paid = TRUE AND status = 'succeeded'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_receipt_sent_at", table_name="transactions")
    op.drop_index("ix_transactions_receipt_status", table_name="transactions")
    op.drop_column("transactions", "receipt_updated_at")
    op.drop_column("transactions", "receipt_reminder_level")
    op.drop_column("transactions", "receipt_admin_id")
    op.drop_column("transactions", "receipt_sent_at")
    op.drop_column("transactions", "receipt_delivery_method")
    op.drop_column("transactions", "receipt_file_type")
    op.drop_column("transactions", "receipt_file_id")
    op.drop_column("transactions", "receipt_url")
    op.drop_column("transactions", "receipt_status")

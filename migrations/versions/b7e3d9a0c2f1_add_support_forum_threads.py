"""add support forum threads

Revision ID: b7e3d9a0c2f1
Revises: 9b2c1f4a6d10
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e3d9a0c2f1"
down_revision: Union[str, Sequence[str], None] = "9b2c1f4a6d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("support_tickets", sa.Column("staff_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("support_tickets", sa.Column("staff_thread_id", sa.Integer(), nullable=True))
    op.add_column("support_tickets", sa.Column("staff_topic_name", sa.String(length=128), nullable=True))
    op.create_index("ix_support_tickets_staff_chat_id", "support_tickets", ["staff_chat_id"])
    op.create_index("ix_support_tickets_staff_thread_id", "support_tickets", ["staff_thread_id"])


def downgrade() -> None:
    op.drop_index("ix_support_tickets_staff_thread_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_staff_chat_id", table_name="support_tickets")
    op.drop_column("support_tickets", "staff_topic_name")
    op.drop_column("support_tickets", "staff_thread_id")
    op.drop_column("support_tickets", "staff_chat_id")

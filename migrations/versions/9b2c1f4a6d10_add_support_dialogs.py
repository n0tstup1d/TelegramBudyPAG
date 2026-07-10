"""add support dialogs

Revision ID: 9b2c1f4a6d10
Revises: 8d4375056ed1
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b2c1f4a6d10"
down_revision: Union[str, Sequence[str], None] = "8d4375056ed1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="support"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])

    op.create_table(
        "support_message_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("staff_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("staff_message_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_support_message_links_ticket_id", "support_message_links", ["ticket_id"])
    op.create_index("ix_support_message_links_user_id", "support_message_links", ["user_id"])
    op.create_index("ix_support_message_links_staff_chat_id", "support_message_links", ["staff_chat_id"])
    op.create_index("ix_support_message_links_staff_message_id", "support_message_links", ["staff_message_id"])


def downgrade() -> None:
    op.drop_index("ix_support_message_links_staff_message_id", table_name="support_message_links")
    op.drop_index("ix_support_message_links_staff_chat_id", table_name="support_message_links")
    op.drop_index("ix_support_message_links_user_id", table_name="support_message_links")
    op.drop_index("ix_support_message_links_ticket_id", table_name="support_message_links")
    op.drop_table("support_message_links")
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_table("support_tickets")

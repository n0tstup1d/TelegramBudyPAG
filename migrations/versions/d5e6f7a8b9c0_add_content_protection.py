"""add content protection state and indexes

Revision ID: d5e6f7a8b9c0
Revises: c4f0a1b2d3e4
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4f0a1b2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_content_stats_user_clicked_at",
        "content_stats",
        ["user_id", "clicked_at"],
        unique=False,
    )
    op.create_index(
        "ix_content_stats_content_id",
        "content_stats",
        ["content_id"],
        unique=False,
    )
    op.create_table(
        "content_protection_states",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reason", sa.String(length=128), nullable=True),
        sa.Column("last_alert_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_content_protection_states_blocked_until",
        "content_protection_states",
        ["blocked_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_protection_states_blocked_until",
        table_name="content_protection_states",
    )
    op.drop_table("content_protection_states")
    op.drop_index("ix_content_stats_content_id", table_name="content_stats")
    op.drop_index("ix_content_stats_user_clicked_at", table_name="content_stats")

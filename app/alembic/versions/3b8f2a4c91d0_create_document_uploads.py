"""create document uploads

Revision ID: 3b8f2a4c91d0
Revises: 980b32f130df
Create Date: 2026-05-21 21:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "3b8f2a4c91d0"
down_revision: Union[str, None] = "980b32f130df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "document_uploads" in inspector.get_table_names():
        return

    op.create_table(
        "document_uploads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=16), nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("upload_time", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "document_uploads" not in inspector.get_table_names():
        return

    op.drop_table("document_uploads")

"""baseline existing init sql schema

Revision ID: 980b32f130df
Revises:
Create Date: 2026-05-21 21:40:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "980b32f130df"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The current start.sh stamps this baseline after init.sql has prepared
    # the existing local schema, so this migration intentionally does nothing.
    pass


def downgrade() -> None:
    pass

"""align messages history fields

Revision ID: 7f2d4c9b1a6e
Revises: ee6fda53681d
Create Date: 2026-05-25 23:20:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "7f2d4c9b1a6e"
down_revision: Union[str, None] = "ee6fda53681d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'create_time'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'created_at'
            ) THEN
                ALTER TABLE messages RENAME COLUMN create_time TO created_at;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'created_at'
            ) THEN
                ALTER TABLE messages ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT now();
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'recommend_questions'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'recommended_questions'
            ) THEN
                ALTER TABLE messages RENAME COLUMN recommend_questions TO recommended_questions;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'recommended_questions'
            ) THEN
                ALTER TABLE messages ADD COLUMN recommended_questions JSONB NOT NULL DEFAULT '[]'::jsonb;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'think'
            ) THEN
                ALTER TABLE messages ADD COLUMN think TEXT;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'think'
            ) THEN
                ALTER TABLE messages DROP COLUMN think;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'recommended_questions'
            ) THEN
                ALTER TABLE messages DROP COLUMN recommended_questions;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'created_at'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'create_time'
            ) THEN
                ALTER TABLE messages RENAME COLUMN created_at TO create_time;
            END IF;
        END $$;
        """
    )

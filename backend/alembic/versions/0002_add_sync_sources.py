"""Add sync_sources table with OAuth columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-25

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sync_sources table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS sync_sources (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            source_type VARCHAR(50) NOT NULL DEFAULT 'yandex_disk',
            folder_path VARCHAR(512) NOT NULL,
            sync_interval INTEGER NOT NULL DEFAULT 30,
            last_synced_at TIMESTAMP,
            status VARCHAR(20) NOT NULL DEFAULT 'not_connected',
            error_message TEXT,
            oauth_token TEXT,
            yandex_user VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # If table already existed (from create_all), add missing columns
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sync_sources' AND column_name = 'oauth_token'
            ) THEN
                ALTER TABLE sync_sources ADD COLUMN oauth_token TEXT;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sync_sources' AND column_name = 'yandex_user'
            ) THEN
                ALTER TABLE sync_sources ADD COLUMN yandex_user VARCHAR(255);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_table('sync_sources')

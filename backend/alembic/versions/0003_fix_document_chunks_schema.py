"""Fix document_chunks schema: vector dims 384->768, add chunk_uuid, context_header

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add chunk_uuid column (with default for any existing rows)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_chunks' AND column_name = 'chunk_uuid'
            ) THEN
                ALTER TABLE document_chunks
                    ADD COLUMN chunk_uuid VARCHAR(36) NOT NULL DEFAULT '';
                CREATE INDEX IF NOT EXISTS ix_document_chunks_chunk_uuid
                    ON document_chunks (chunk_uuid);
            END IF;
        END $$;
    """)

    # 2. Add context_header column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_chunks' AND column_name = 'context_header'
            ) THEN
                ALTER TABLE document_chunks ADD COLUMN context_header TEXT;
            END IF;
        END $$;
    """)

    # 3. Change embedding dimension from vector(384) to vector(768)
    # Safe because DB was just recreated and table is empty
    op.execute("""
        ALTER TABLE document_chunks
            ALTER COLUMN embedding TYPE vector(768);
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(384)")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_chunk_uuid")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS context_header")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS chunk_uuid")

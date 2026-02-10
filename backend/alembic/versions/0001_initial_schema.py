"""Initial schema with all tables

Revision ID: 0001
Revises: 
Create Date: 2026-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Create document_status enum type (if not exists)
    # SQLAlchemy Enum creates the type automatically, but we handle it explicitly
    document_status = sa.Enum('processing', 'ready', 'failed', name='documentstatus')
    document_status.create(op.get_bind(), checkfirst=True)
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('status', document_status, nullable=False, server_default='processing'),
        sa.Column('processing_stage', sa.String(50), nullable=True, server_default='uploading'),
        sa.Column('processing_progress', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_documents_id', 'documents', ['id'])
    
    # Document chunks table (with pgvector)
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_document_chunks_id', 'document_chunks', ['id'])
    
    # Chat sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True, index=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_chat_sessions_id', 'chat_sessions', ['id'])
    
    # Chat messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_chat_messages_id', 'chat_messages', ['id'])


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('users')
    
    # Drop enum type
    sa.Enum(name='documentstatus').drop(op.get_bind(), checkfirst=True)

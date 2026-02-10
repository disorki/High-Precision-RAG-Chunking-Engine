from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import enum

from app.database import Base
from app.config import get_settings

settings = get_settings()


class DocumentStatus(str, enum.Enum):
    """Status of document processing."""
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class User(Base):
    """User model for authentication and ownership."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")


class Document(Base):
    """Document model for uploaded files."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    status = Column(
        Enum(DocumentStatus),
        default=DocumentStatus.PROCESSING,
        nullable=False
    )
    processing_stage = Column(String(50), default="uploading", nullable=True)
    processing_progress = Column(Integer, default=0, nullable=True)  # 0-100
    error_message = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="document")


class DocumentChunk(Base):
    """Vector storage for document chunks with embeddings."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text_content = Column(Text, nullable=False)
    embedding = Column(Vector(settings.vector_dimensions), nullable=False)
    page_number = Column(Integer, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")


class ChatSession(Base):
    """Chat session for conversation context."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    title = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)  # IPv4/IPv6
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    document = relationship("Document", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Individual chat messages within a session."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

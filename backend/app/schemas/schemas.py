from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


# Enums
class DocumentStatusEnum(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# User Schemas
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Document Schemas
class DocumentBase(BaseModel):
    filename: str


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    status: DocumentStatusEnum
    processing_stage: Optional[str] = None
    processing_progress: Optional[int] = None
    error_message: Optional[str] = None
    page_count: Optional[int] = None
    chunk_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


# Chat Schemas
class ChatMessageBase(BaseModel):
    role: str
    content: str


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessageResponse(ChatMessageBase):
    id: int
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionBase(BaseModel):
    title: Optional[str] = None
    document_id: Optional[int] = None


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSessionResponse(ChatSessionBase):
    id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []

    class Config:
        from_attributes = True


# Chat Request/Response
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    document_id: Optional[int] = None


class SaveMessageRequest(BaseModel):
    """Request to save assistant response after streaming."""
    session_id: int
    content: str


class ChunkSource(BaseModel):
    """Source chunk information for citations."""
    chunk_id: int
    chunk_uuid: str
    text: str
    page_number: Optional[int] = None
    score: float
    context_header: Optional[str] = None
    source_filename: Optional[str] = None


class SearchResult(BaseModel):
    chunk_uuid: str
    text: str
    page_number: Optional[int] = None
    score: float
    context_header: Optional[str] = None
    document_id: int
    document_filename: str


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query: str


class ChatResponse(BaseModel):
    content: str
    session_id: int
    sources: List[ChunkSource] = []


# Upload Response
class UploadResponse(BaseModel):
    document_id: int
    filename: str
    status: DocumentStatusEnum
    message: str


class UploadBatchResponse(BaseModel):
    results: List[UploadResponse]
    message: str

"""
Agent Tools Router — exposes 7 specialized endpoints for the Flowise AI agent.

Each endpoint is designed to be called by Flowise Custom Tool nodes.
All responses are plain JSON — structured for easy LLM consumption.
"""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import Document, DocumentChunk, DocumentStatus
from app.services import rag_pipeline, retrieval_service
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-tools", tags=["agent-tools"])


# ─── Request schemas ─────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 8


class CompareRequest(BaseModel):
    query: str
    document_ids: List[int]


class ExtractRequest(BaseModel):
    query: str
    document_id: Optional[int] = None


# ─── Tool 1: search_all ───────────────────────────────────────────────────────

@router.post("/search")
async def search_all(req: SearchRequest, db: Session = Depends(get_db)):
    """
    TOOL: search_all
    Semantic search across ALL documents in the knowledge base.
    Use this when the user asks a general question without specifying a document.

    Returns: list of relevant text chunks with document name and page number.
    """
    try:
        embedding = await rag_pipeline.generate_embedding(req.query)
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")

        chunks = retrieval_service.search_all_documents(
            db=db,
            query_embedding=embedding,
            query_text=req.query,
            top_k=req.top_k
        )

        return {
            "tool": "search_all",
            "query": req.query,
            "results_count": len(chunks),
            "results": [
                {
                    "document": chunk.get("document_filename", "unknown"),
                    "page": chunk.get("page_number", "?"),
                    "score": round(chunk.get("score", 0), 3),
                    "text": chunk["text"][:1200]
                }
                for chunk in chunks
            ]
        }
    except Exception as e:
        logger.error(f"search_all error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Tool 2: search_document ─────────────────────────────────────────────────

@router.post("/search/{document_id}")
async def search_in_document(
    document_id: int,
    req: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    TOOL: search_document
    Semantic search within a SPECIFIC document.
    Use when the user specifies which document they want to search in.

    Returns: relevant chunks from that document only.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    if doc.status != DocumentStatus.READY:
        raise HTTPException(status_code=400, detail=f"Document is not ready (status: {doc.status.value})")

    try:
        embedding = await rag_pipeline.generate_embedding(req.query)
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")

        chunks = retrieval_service.search_similar_chunks(
            db=db,
            document_id=document_id,
            query_embedding=embedding,
            query_text=req.query,
            top_k=req.top_k
        )

        return {
            "tool": "search_document",
            "document_id": document_id,
            "document_name": doc.original_filename,
            "query": req.query,
            "results_count": len(chunks),
            "results": [
                {
                    "page": chunk.get("page_number", "?"),
                    "score": round(chunk.get("score", 0), 3),
                    "text": chunk["text"][:1200]
                }
                for chunk in chunks
            ]
        }
    except Exception as e:
        logger.error(f"search_document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Tool 3: list_documents ──────────────────────────────────────────────────

@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    """
    TOOL: list_documents
    Returns a complete list of all documents in the knowledge base.
    Use this FIRST when the user asks what documents are available,
    or before searching in a specific document to find its ID.

    Returns: id, name, status, page count, chunk count for each document.
    """
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    ready = [d for d in docs if d.status == DocumentStatus.READY]
    processing = [d for d in docs if d.status == DocumentStatus.PROCESSING]
    failed = [d for d in docs if d.status == DocumentStatus.FAILED]

    return {
        "tool": "list_documents",
        "total": len(docs),
        "ready_count": len(ready),
        "processing_count": len(processing),
        "failed_count": len(failed),
        "documents": [
            {
                "id": d.id,
                "name": d.original_filename,
                "status": d.status.value,
                "pages": d.page_count,
                "chunks": d.chunk_count,
                "uploaded_at": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else None
            }
            for d in docs
        ]
    }


# ─── Tool 4: get_document_info ───────────────────────────────────────────────

@router.get("/documents/{document_id}")
def get_document_info(document_id: int, db: Session = Depends(get_db)):
    """
    TOOL: get_document_info
    Returns metadata and first few chunks of a specific document.
    Use this to understand what a document is about before deeper search.

    Returns: document metadata + preview of first 3 text chunks.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    # Fetch first 3 chunks as preview
    preview_chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .limit(3)
        .all()
    )

    return {
        "tool": "get_document_info",
        "id": doc.id,
        "name": doc.original_filename,
        "status": doc.status.value,
        "pages": doc.page_count,
        "chunks": doc.chunk_count,
        "uploaded_at": doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else None,
        "preview": [
            {
                "chunk_index": c.chunk_index,
                "page": c.page_number,
                "text": c.text_content[:600]
            }
            for c in preview_chunks
        ]
    }


# ─── Tool 5: summarize ───────────────────────────────────────────────────────

@router.get("/documents/{document_id}/summarize")
async def summarize_document(document_id: int, db: Session = Depends(get_db)):
    """
    TOOL: summarize
    Generate a concise summary of a document using the LLM.
    Use when the user asks 'What is this document about?' or 'Give me an overview of X'.

    Returns: LLM-generated summary paragraph.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    if doc.status != DocumentStatus.READY:
        raise HTTPException(status_code=400, detail="Document not ready")

    # Get first N chunks for summarization
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .limit(settings.agent_summarize_chunks)
        .all()
    )
    if not chunks:
        raise HTTPException(status_code=404, detail="No content found in document")

    context = "\n\n---\n\n".join(
        f"[Page {c.page_number}]\n{c.text_content}" for c in chunks
    )

    prompt = f"""You are a document analyst. Read the following document excerpts and write a concise summary (3-5 sentences) in the user's language.
Focus on: main topic, key information, intended audience.

DOCUMENT: {doc.original_filename}

CONTENT:
{context}

SUMMARY:"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.agent_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_ctx": 4096}
                }
            )
            resp.raise_for_status()
            summary = resp.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Summarize LLM error: {e}")
        summary = f"Could not generate summary: {e}"

    return {
        "tool": "summarize",
        "document_id": document_id,
        "document_name": doc.original_filename,
        "pages": doc.page_count,
        "summary": summary
    }


# ─── Tool 6: compare_documents ───────────────────────────────────────────────

@router.post("/compare")
async def compare_documents(req: CompareRequest, db: Session = Depends(get_db)):
    """
    TOOL: compare_documents
    Compare multiple documents on a specific topic or question.
    Use when user asks to compare, contrast or find differences between documents.

    Body: { "query": "...", "document_ids": [1, 2, 3] }
    Returns: per-document relevant context for the LLM to compare.
    """
    if len(req.document_ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 document_ids to compare")

    try:
        embedding = await rag_pipeline.generate_embedding(req.query)
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")

        results = []
        for doc_id in req.document_ids:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc or doc.status != DocumentStatus.READY:
                results.append({"document_id": doc_id, "error": "Not found or not ready"})
                continue

            chunks = retrieval_service.search_similar_chunks(
                db=db,
                document_id=doc_id,
                query_embedding=embedding,
                query_text=req.query,
                top_k=4
            )

            results.append({
                "document_id": doc_id,
                "document_name": doc.original_filename,
                "relevant_content": [
                    {"page": c.get("page_number", "?"), "text": c["text"][:800]}
                    for c in chunks
                ]
            })

        return {
            "tool": "compare_documents",
            "query": req.query,
            "documents_compared": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"compare_documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Tool 7: extract_facts ───────────────────────────────────────────────────

@router.post("/extract")
async def extract_facts(req: ExtractRequest, db: Session = Depends(get_db)):
    """
    TOOL: extract_facts
    Extract specific facts, numbers, names, or data points from documents.
    Use when the user asks for specific values: dates, names, numbers, clauses, etc.
    Optionally scoped to a single document_id.

    Returns: extracted chunks with highest relevance score for fact extraction.
    """
    try:
        embedding = await rag_pipeline.generate_embedding(req.query)
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")

        if req.document_id:
            doc = db.query(Document).filter(Document.id == req.document_id).first()
            if not doc or doc.status != DocumentStatus.READY:
                raise HTTPException(status_code=404, detail="Document not found or not ready")
            chunks = retrieval_service.search_similar_chunks(
                db=db,
                document_id=req.document_id,
                query_embedding=embedding,
                query_text=req.query,
                top_k=6
            )
            scope = doc.original_filename
        else:
            chunks = retrieval_service.search_all_documents(
                db=db,
                query_embedding=embedding,
                query_text=req.query,
                top_k=6
            )
            scope = "all documents"

        # Build a focused extraction prompt context
        context_parts = []
        for c in chunks:
            doc_label = c.get("document_filename", "")
            page = c.get("page_number", "?")
            context_parts.append(f"[{doc_label} | Page {page} | score={c.get('score', 0):.2f}]\n{c['text']}")

        return {
            "tool": "extract_facts",
            "query": req.query,
            "scope": scope,
            "results_count": len(chunks),
            "extracted_context": context_parts
        }
    except Exception as e:
        logger.error(f"extract_facts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

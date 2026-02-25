import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas import SearchResponse, SearchResult
from app.services import rag_pipeline, retrieval_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Search"])

@router.get("", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=50),
    document_id: Optional[int] = Query(None, description="Filter by document ID"),
    db: Session = Depends(get_db)
):
    """
    Search across all documents in the vector database using a text query.
    Returns matching chunks with their context headers, scores, and parent document info.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    try:
        # Generate embedding for the query
        logger.info(f"Search request: q='{q[:50]}', top_k={top_k}, document_id={document_id}")
        query_embedding = await rag_pipeline.generate_embedding(q)
        if not query_embedding:
            raise HTTPException(status_code=500, detail="Failed to generate query embedding.")
            
        # Search chunks using retrieval service
        chunks = retrieval_service.search_all_documents(
            db=db,
            query_embedding=query_embedding,
            query_text=q,
            top_k=top_k,
            document_id=document_id
        )
        
        results = [
            SearchResult(
                chunk_uuid=str(chunk["id"]),
                text=chunk["text"],
                page_number=chunk["page_number"],
                score=chunk["score"],
                context_header=chunk.get("context_header", ""),
                document_id=chunk["document_id"],
                document_filename=chunk["document_filename"]
            )
            for chunk in chunks
        ]
        
        return SearchResponse(
            results=results,
            total=len(results),
            query=q
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Global search failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform search. Check logs.")

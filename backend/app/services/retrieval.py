import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models import DocumentChunk, Document
from app.config import get_settings
from app.services.reranker import reranker_service

settings = get_settings()
logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for vector similarity search and context retrieval."""

    def __init__(self):
        self.top_k = settings.top_k_chunks
        self.similarity_threshold = settings.similarity_threshold

    def search_similar_chunks(
        self,
        db: Session,
        query_embedding: List[float],
        document_id: int,
        query_text: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using cosine similarity.
        
        Uses pgvector's <=> operator for cosine distance.
        Lower distance = more similar.
        Filters out chunks below similarity_threshold.
        
        Returns:
            List of dicts with chunk info and similarity score
        """
        k = top_k or self.top_k
        fetch_k = k * 3 if reranker_service.enabled else k
        
        try:
            # Convert embedding list to pgvector string format: [1.2, 3.4, ...]
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # Using cosine distance operator `<=>` (0 = identical, 2 = completely opposite)
            # We want similarity = 1 - distance
            query_str = """
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.text_content,
                    dc.page_number,
                    dc.chunk_index,
                    d.original_filename,
                    1 - (dc.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.document_id = :document_id
                ORDER BY dc.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """
            
            result = db.execute(text(query_str), {"document_id": document_id, "limit": fetch_k, "embedding": embedding_str})
            
            chunks = []
            filtered_count = 0
            for row in result:
                similarity = float(row.similarity)
                # Filter out chunks below similarity threshold
                if similarity < self.similarity_threshold:
                    filtered_count += 1
                    continue
                chunks.append({
                    "id": row.id,
                    "document_id": row.document_id,
                    "text": row.text_content,
                    "page_number": row.page_number,
                    "chunk_index": row.chunk_index,
                    "score": similarity
                })
            
            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} chunks below threshold {self.similarity_threshold}")
            
            # Rerank if enabled and query text is provided
            if reranker_service.enabled and query_text and len(chunks) > 0:
                chunks = reranker_service.rerank(query=query_text, chunks=chunks)
            else:
                chunks = chunks[:k]
                
            logger.info(f"Found {len(chunks)} relevant chunks for document {document_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error searching similar chunks: {e}")
            raise

    def search_all_documents(
        self,
        db: Session,
        query_embedding: List[float],
        query_text: Optional[str] = None,
        top_k: Optional[int] = None,
        document_id: Optional[int] = None
    ) -> List[dict]:
        """
        Search for similar chunks across ALL documents (or filter by one if provided).
        """
        k = top_k or self.top_k
        fetch_k = k * 3 if reranker_service.enabled else k
        
        try:
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # Base query
            query_str = """
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.text_content,
                    dc.page_number,
                    dc.chunk_index,
                    d.original_filename,
                    1 - (dc.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE LOWER(d.status::text) = 'ready'
            """
            
            params = {"limit": fetch_k, "embedding": embedding_str}
            if document_id is not None:
                query_str += " AND dc.document_id = :document_id"
                params["document_id"] = document_id
                
            query_str += """
                ORDER BY dc.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """
            
            result = db.execute(text(query_str), params)
            
            chunks = []
            for row in result:
                similarity = float(row.similarity)
                # Keep slightly more relaxed threshold for global search to ensure results
                if similarity < self.similarity_threshold - 0.05:
                    continue
                chunks.append({
                    "id": row.id,
                    "document_id": row.document_id,
                    "document_filename": row.original_filename,
                    "text": row.text_content,
                    "page_number": row.page_number,
                    "chunk_index": row.chunk_index,
                    "score": similarity
                })
            
            # Rerank if enabled and query text is provided
            if reranker_service.enabled and query_text and len(chunks) > 0:
                chunks = reranker_service.rerank(query=query_text, chunks=chunks)
            else:
                chunks = chunks[:k]
                
            logger.info(f"Global search found {len(chunks)} relevant chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in global search: {e}")
            raise

    def build_context(self, chunks: List[dict], max_tokens: Optional[int] = None) -> str:
        """
        Build context string from retrieved chunks.
        
        Sorts by document position (page, chunk_index) for natural reading order.
        Only includes chunks that passed the similarity threshold.
        """
        if not chunks:
            return ""
        
        max_tokens = max_tokens or settings.context_max_tokens
        
        # Sort by document position for natural reading order
        sorted_chunks = sorted(
            chunks,
            key=lambda x: (x.get("page_number", 0), x.get("chunk_index", 0))
        )
        
        context_parts = []
        total_chars = 0
        char_limit = max_tokens * 4  # Rough approximation of tokens to chars
        
        for i, chunk in enumerate(sorted_chunks):
            chunk_text = chunk["text"]
            page_num = chunk.get("page_number", "?")
            score = chunk.get("score", 0)
            
            # Log each chunk for debugging
            logger.debug(f"Chunk {i+1}: page={page_num}, score={score:.4f}, len={len(chunk_text)}")
            logger.debug(f"Content preview: {chunk_text[:200]}...")
            
            if total_chars + len(chunk_text) > char_limit:
                # Add partial chunk if possible
                remaining = char_limit - total_chars
                if remaining > 200:
                    context_parts.append(f"[Page {page_num} | score={score:.2f}]\n{chunk_text[:remaining]}...")
                break
            
            # Add page reference and score to each chunk
            context_parts.append(f"[Page {page_num} | score={score:.2f}]\n{chunk_text}")
            total_chars += len(chunk_text)
        
        logger.info(f"Built context with {len(context_parts)} chunks, {total_chars} chars")
        return "\n\n---\n\n".join(context_parts)

    def format_sources(self, chunks: List[dict]) -> List[dict]:
        """Format chunks as source citations."""
        return [
            {
                "chunk_id": chunk["id"],
                "text": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                "page_number": chunk["page_number"],
                "score": round(chunk["score"], 4)
            }
            for chunk in chunks
        ]


# Singleton instance
retrieval_service = RetrievalService()

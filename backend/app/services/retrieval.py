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
    # сервис поиска и извлечения контекста

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
        # поиск похожих чанков по косинусному сходству
        k = top_k or self.top_k
        fetch_k = k * 3 if reranker_service.enabled else k
        
        try:
            # конвертация эмбеддинга в строку для pgvector
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # использование оператора <=> для косинусного расстояния
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
                # фильтрация по порогу
                if similarity < self.similarity_threshold:
                    filtered_count += 1
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
            
            if filtered_count > 0:
                logger.info(f"Отфильтровано {filtered_count} чанков ниже порога {self.similarity_threshold}")
            
            # реранжирование
            if reranker_service.enabled and query_text and len(chunks) > 0:
                chunks = reranker_service.rerank(query=query_text, chunks=chunks)
            else:
                chunks = chunks[:k]
                
            logger.info(f"Найдено {len(chunks)} чанков для документа {document_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Ошибка поиска чанков: {e}")
            raise

    def search_all_documents(
        self,
        db: Session,
        query_embedding: List[float],
        query_text: Optional[str] = None,
        top_k: Optional[int] = None,
        document_id: Optional[int] = None
    ) -> List[dict]:
        # поиск по всем готовым документам
        k = top_k or self.top_k
        fetch_k = k * 3 if reranker_service.enabled else k
        
        try:
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # базовый запрос
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
                # более мягкий порог для глобального поиска
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
            
            # реранжирование
            if reranker_service.enabled and query_text and len(chunks) > 0:
                chunks = reranker_service.rerank(query=query_text, chunks=chunks)
            else:
                chunks = chunks[:k]
                
            logger.info(f"Глобальный поиск: найдено {len(chunks)} чанков")
            return chunks
            
        except Exception as e:
            logger.error(f"Ошибка глобального поиска: {e}")
            raise

    def build_context(self, chunks: List[dict], max_tokens: Optional[int] = None) -> str:
        # сборка строки контекста из найденных чанков
        if not chunks:
            return ""
        
        max_tokens = max_tokens or settings.context_max_tokens
        
        # сортировка для естественного чтения
        sorted_chunks = sorted(
            chunks,
            key=lambda x: (
                x.get("document_filename", ""),
                x.get("page_number", 0),
                x.get("chunk_index", 0),
            )
        )
        
        context_parts = []
        total_chars = 0
        char_limit = max_tokens * 4
        
        for i, chunk in enumerate(sorted_chunks):
            chunk_text = chunk["text"]
            page_num = chunk.get("page_number", "?")
            score = chunk.get("score", 0)
            doc_name = chunk.get("document_filename", "")
            
            logger.debug(f"Чанк {i+1}: док={doc_name}, стр={page_num}, score={score:.4f}")
            
            if total_chars + len(chunk_text) > char_limit:
                # обрезка при превышении лимита
                remaining = char_limit - total_chars
                if remaining > 200:
                    header = f"[Документ: {doc_name} | Стр. {page_num}]" if doc_name else f"[Стр. {page_num}]"
                    context_parts.append(f"{header}\n{chunk_text[:remaining]}...")
                break
            
            header = f"[Документ: {doc_name} | Стр. {page_num}]" if doc_name else f"[Стр. {page_num}]"
            context_parts.append(f"{header}\n{chunk_text}")
            total_chars += len(chunk_text)
        
        logger.info(f"Контекст собран: {len(context_parts)} чанков, {total_chars} симв.")
        return "\n\n---\n\n".join(context_parts)

    def format_sources(self, chunks: List[dict]) -> List[dict]:
        # форматирование источников для ответа
        return [
            {
                "chunk_id": chunk["id"],
                "text": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                "page_number": chunk["page_number"],
                "score": round(chunk["score"], 4)
            }
            for chunk in chunks
        ]


# синглтон сервиса
retrieval_service = RetrievalService()

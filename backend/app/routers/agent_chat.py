import json
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import Document, DocumentStatus
from app.services import rag_pipeline, retrieval_service
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


# схемы
class AgentChatRequest(BaseModel):
    question: str
    document_id: Optional[int] = None
    session_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    text: str
    sources: List[dict] = []
    documents_used: int = 0


# системный промпт помощника
SYSTEM_PROMPT = """Ты — AI-ассистент университета. Отвечай ТОЛЬКО на основе КОНТЕКСТА ниже.

ПРАВИЛА:
- ЗАПРЕЩЕНО придумывать. Только данные из контекста.
- Давай пошаговые инструкции с нумерованными шагами.
- Кнопки и поля оформляй: «Нажмите кнопку «Название»», «В поле «Название» выберите...».
- Ссылайся на рисунки если есть: (Рис. X).
- После КАЖДОГО шага указывай источник в скобках: (Стр. X)
- В конце добавь: При возникновении вопросов обратитесь в поддержку +7 (499) 956–09–11 / https://help.ranepa.ru
- В самом конце укажи полный источник: [Документ: Название | Стр. X-Y]
- Если информации НЕТ — скажи прямо."""


# поиск по документам
async def _search_documents(db: Session, question: str, document_id: Optional[int] = None) -> list:
    # мульти-запрос для лучшего поиска (3 варианта)
    queries = [
        question,
        f"инструкция {question}",
        f"{question} порядок действий процедура настройка",
    ]

    seen_ids = set()
    all_chunks = []

    for q in queries:
        try:
            embedding = await rag_pipeline.generate_embedding(q)
            if not embedding:
                continue

            if document_id:
                # поиск в конкретном документе
                chunks = retrieval_service.search_similar_chunks(
                    db=db,
                    document_id=document_id,
                    query_embedding=embedding,
                    query_text=q,
                    top_k=10
                )
            else:
                # поиск по всем документам
                chunks = retrieval_service.search_all_documents(
                    db=db,
                    query_embedding=embedding,
                    query_text=q,
                    top_k=10
                )

            for chunk in chunks:
                cid = chunk.get("id")
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    all_chunks.append(chunk)

        except Exception as e:
            logger.error(f"Search error for '{q[:50]}': {e}")
            continue

    # сортировка по файлу и странице
    all_chunks.sort(key=lambda c: (
        c.get("document_filename", ""),
        c.get("page_number", 0),
        c.get("chunk_index", 0)
    ))

    return all_chunks


# сборка контекста
def _build_context(chunks: list) -> str:
    # объединение чанков в текст лимитированной длины
    if not chunks:
        return ""

    parts = []
    total = 0
    MAX_CHARS = 12000

    for chunk in chunks:
        doc_name = chunk.get("document_filename", "")
        page = chunk.get("page_number", "?")
        text = chunk.get("text", "")

        entry = f"[{doc_name} | Стр. {page}]\n{text}"

        if total + len(entry) > MAX_CHARS:
            break

        parts.append(entry)
        total += len(entry)

    return "\n\n---\n\n".join(parts)


# запрос к llm
async def _call_llm(context: str, question: str) -> str:
    # генерация ответа через ollama
    prompt = f"""{SYSTEM_PROMPT}

КОНТЕКСТ:
{context}

ВОПРОС: {question}

ОТВЕТ:"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.agent_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_ctx": 8192,
                        "num_predict": 2048,
                    }
                }
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM timeout (120s)")
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


# чат с агентом
@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(req: AgentChatRequest, db: Session = Depends(get_db)):
    # основной процесс rag: поиск -> контекст -> llm
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Пустой вопрос")

    logger.info(f"Agent RAG: '{question[:80]}', doc_id={req.document_id}")

    # проверка документа
    if req.document_id:
        doc = db.query(Document).filter(Document.id == req.document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Документ {req.document_id} не найден")
        if doc.status != DocumentStatus.READY:
            raise HTTPException(status_code=400, detail=f"Документ не готов ({doc.status.value})")

    # 1. поиск
    chunks = await _search_documents(db, question, req.document_id)
    logger.info(f"Found {len(chunks)} chunks")

    if not chunks:
        return AgentChatResponse(
            text="В загруженных документах нет информации по данному вопросу.",
            sources=[],
            documents_used=0,
        )

    # 2. сборка контекста
    context = _build_context(chunks)
    logger.info(f"Context: {len(context)} chars")

    # 3. генерация ответа
    answer = await _call_llm(context, question)

    if not answer:
        answer = "Не удалось сгенерировать ответ."

    # 4. формирование списка источников
    docs_used = set()
    sources = []
    for chunk in chunks[:10]:
        doc_name = chunk.get("document_filename", "")
        docs_used.add(doc_name)
        sources.append({
            "chunk_id": chunk.get("id", 0),
            "text": chunk.get("text", "")[:150] + "...",
            "page_number": chunk.get("page_number"),
            "score": round(chunk.get("score", 0), 3),
            "document": doc_name
        })

    logger.info(f"Answer: {len(answer)} chars")

    return AgentChatResponse(
        text=answer,
        sources=sources,
        documents_used=len(docs_used),
    )

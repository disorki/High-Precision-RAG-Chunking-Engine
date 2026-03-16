import json
import logging
from datetime import datetime
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, ChatSession, ChatMessage, DocumentStatus
from app.schemas import ChatRequest, ChatSessionResponse, SaveMessageRequest
from app.services import rag_pipeline, retrieval_service
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# шаблон системного промпта
SYSTEM_PROMPT = """Ты — точный аналитик документов. Отвечай СТРОГО на основе контекста ниже.

КОНТЕКСТ ИЗ ДОКУМЕНТОВ:
{context}

## АБСОЛЮТНЫЕ ПРАВИЛА
1. Используй ТОЛЬКО информацию из КОНТЕКСТА выше. ЗАПРЕЩЕНО добавлять данные из своих знаний.
2. ЦИТИРУЙ конкретные фрагменты из контекста. Каждый факт подтверждай цитатой.
3. После каждого утверждения указывай источник: [{page_label} X].
4. Давай РАЗВЁРНУТЫЙ ответ — включай ВСЮ релевантную информацию из контекста.
5. Таблицы из контекста воспроизводи как Markdown-таблицы с точными значениями.
6. Если информация неполная — укажи что найдено и чего не хватает.
7. Если информации НЕТ в контексте, ответь: "{no_info_message}"
8. НЕ повторяй вопрос. Начинай сразу с ответа.
9. {language_instruction}"""


def get_localized_prompt(user_language: str) -> dict:
    # локализация элементов промпта
    if user_language.lower() == "russian":
        return {
            "page_label": "Стр.",
            "no_info_message": "Запрашиваемая информация не найдена в предоставленном контексте.",
            "language_instruction": "Respond ONLY in Russian. Use Russian for all text."
        }
    elif user_language.lower() == "chinese":
        return {
            "page_label": "页",
            "no_info_message": "在提供的上下文中未找到所请求的信息。",
            "language_instruction": "Respond ONLY in Chinese. Use Chinese for all text."
        }
    else:
        return {
            "page_label": "Page",
            "no_info_message": "The requested information was not found in the provided context.",
            "language_instruction": "Respond in English."
        }


def get_client_ip(request: Request) -> str:
    # получение реального ip клиента
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

async def stream_direct_rag(prompt: str, session_id: str, document_id: int = None):
    # прямой rag: поиск -> контекст -> llm
    from app.routers.agent_chat import _search_documents, _build_context, _call_llm
    from app.database import SessionLocal

    try:
        yield f"data: {json.dumps({'status': 'thinking'})}\n\n"

        db = SessionLocal()
        try:
            chunks = await _search_documents(db, prompt, document_id)

            if not chunks:
                yield f"data: {json.dumps({'content': 'В загруженных документах нет информации по данному вопросу.'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            context = _build_context(chunks)
            answer = await _call_llm(context, prompt)

            if not answer:
                answer = "Не удалось сгенерировать ответ."

            yield f"data: {json.dumps({'content': answer})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Ошибка прямого RAG: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"



@router.post("/chat")
async def chat(
    request: ChatRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    # эндпоинт чата
    client_ip = req.client.host if req.client else "unknown"
    user_agent = req.headers.get("User-Agent", "")[:512]
    
    logger.info(f"Запрос в чат с IP: {client_ip}")
    
    # проверка документа
    if request.document_id:
        document = db.query(Document).filter(Document.id == request.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Документ не найден")
        if document.status != DocumentStatus.READY:
            raise HTTPException(
                status_code=400,
                detail=f"Документ не готов. Статус: {document.status.value}"
            )
    
    try:
        session = None
        if request.session_id:
            session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
            
        if not session:
            query = db.query(ChatSession).filter(ChatSession.ip_address == client_ip)
            if request.document_id:
                query = query.filter(ChatSession.document_id == request.document_id)
            else:
                query = query.filter(ChatSession.document_id.is_(None))
            session = query.order_by(ChatSession.updated_at.desc()).first()
            
        if not session:
            session = ChatSession(
                document_id=request.document_id,
                title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
                ip_address=client_ip,
                user_agent=user_agent
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        else:
            session.updated_at = datetime.utcnow()
            db.commit()
            
        # сохранение сообщения пользователя
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=request.message,
            ip_address=client_ip
        )
        db.add(user_message)
        db.commit()
        
        # потоковый ответ с использованием прямого RAG
        return StreamingResponse(
            stream_direct_rag(request.message, str(session.id), request.document_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-Id": str(session.id),
                "X-Sources": json.dumps([])
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка чата: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    document_id: int = None,
    ip_address: str = None,
    db: Session = Depends(get_db)
):
    # получение списка сессий чата
    query = db.query(ChatSession)
    
    if document_id:
        query = query.filter(ChatSession.document_id == document_id)
    
    if ip_address:
        query = query.filter(ChatSession.ip_address == ip_address)
    
    sessions = query.order_by(ChatSession.updated_at.desc()).limit(50).all()
    return sessions


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    # получение сессии со всеми сообщениями
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    return session


@router.get("/chat/my-sessions", response_model=list[ChatSessionResponse])
async def get_my_sessions(
    req: Request,
    document_id: int = None,
    db: Session = Depends(get_db)
):
    # сессии текущего пользователя по ip
    client_ip = get_client_ip(req)
    
    query = db.query(ChatSession).filter(ChatSession.ip_address == client_ip)
    
    if document_id:
        query = query.filter(ChatSession.document_id == document_id)
    
    sessions = query.order_by(ChatSession.updated_at.desc()).limit(50).all()
    return sessions




@router.post("/chat/save-response")
async def save_response(
    request: SaveMessageRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    # сохранение ответа ассистента после завершения стриминга
    client_ip = get_client_ip(req)
    
    session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    # сохранение сообщения
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=request.content,
        ip_address=client_ip
    )
    db.add(assistant_message)
    
    # обновление времени сессии
    session.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "saved"}

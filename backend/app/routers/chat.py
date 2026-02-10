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

# System prompt template for RAG
SYSTEM_PROMPT = """You are a precise document analyst. Your task is to answer user questions STRICTLY based on the provided context.

CONTEXT FROM DOCUMENT:
{context}

INSTRUCTIONS:
1. Answer ONLY using the provided context. Do NOT add information from your training data.
2. Structure your answer clearly: use bullet points, numbered lists, or short paragraphs.
3. For TABLES: identify columns/rows, quote exact values with units (e.g., "Flash: 16KB").
4. ALWAYS cite the source page: "[Стр. X]" or "[Page X]" after each fact.
5. If context is partial, state what you found and what is missing.
6. If NO relevant info exists, say: "В предоставленном контексте информация не найдена."
7. ALWAYS respond in the SAME LANGUAGE as the user's question (Russian → Russian, English → English).
8. Be concise. Avoid repeating the question. Go straight to the answer.
9. If the user asks to compare or list, format as a table when appropriate."""


def get_client_ip(request: Request) -> str:
    """
    Get real client IP, respecting X-Forwarded-For for proxies/Docker.
    Falls back to direct client host.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"



async def rewrite_query(original_query: str, chat_history: list = None) -> str:
    """
    Rewrite conversational query into a precise search query for better retrieval.
    Falls back to original query on any error.
    """
    history_context = ""
    if chat_history:
        recent = chat_history[-4:]
        history_context = "\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in recent
        )
    
    prompt = f"""Rewrite the following user question into a clear, specific search query 
for finding information in a technical document.
Keep the same language as the original question.
Output ONLY the rewritten query, nothing else.

Chat context (last messages):
{history_context if history_context else 'none'}

User question: {original_query}

Rewritten query:"""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.chat_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_ctx": 2048
                    }
                }
            )
            response.raise_for_status()
            rewritten = response.json().get("response", "").strip()
            if rewritten and len(rewritten) < 500:
                logger.info(f"Query rewritten: '{original_query[:80]}' -> '{rewritten[:80]}'")
                return rewritten
            return original_query
    except Exception as e:
        logger.warning(f"Query rewriting failed, using original: {e}")
        return original_query


def prepare_chat_history(messages: list, max_total_chars: int = None) -> list:
    """
    Keep recent messages, truncating old assistant responses to save context budget.
    """
    max_total_chars = max_total_chars or settings.history_max_chars
    result = []
    total = 0
    for msg in reversed(messages[-10:]):
        content = msg["content"]
        # Truncate long assistant responses to save context
        if msg["role"] == "assistant" and len(content) > 500:
            content = content[:500] + "..."
        if total + len(content) > max_total_chars:
            break
        result.insert(0, {"role": msg["role"], "content": content})
        total += len(content)
    return result


async def generate_stream(
    prompt: str,
    context: str,
    chat_history: list = None
):
    """
    Generate streaming response from Ollama.
    The model responds directly in the user's language (no separate translation step).
    Includes chat history for conversation memory.
    
    Yields Server-Sent Events formatted chunks.
    """
    system_prompt = SYSTEM_PROMPT.format(context=context)
    
    # Build messages with history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add chat history (last 10 messages for context)
    if chat_history:
        for msg in chat_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current user message
    messages.append({"role": "user", "content": prompt})
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.chat_model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "num_ctx": settings.chat_num_ctx,
                        "temperature": settings.chat_temperature,
                        "top_k": settings.chat_top_k,
                        "top_p": settings.chat_top_p,
                    }
                }
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                content = data["message"]["content"]
                                yield f"data: {json.dumps({'content': content})}\n\n"
                            
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
            
            yield f"data: {json.dumps({'done': True})}\n\n"
                            
    except httpx.HTTPError as e:
        logger.error(f"Ollama API error: {e}")
        yield f"data: {json.dumps({'error': 'Failed to generate response'})}\n\n"
    except Exception as e:
        logger.error(f"Stream generation error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.post("/chat")
async def chat(
    request: ChatRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    Chat endpoint with RAG context retrieval and streaming response.
    Sessions are identified by client IP + document_id (no auth required).
    
    1. Capture client IP address
    2. Generate embedding for user query
    3. Retrieve relevant chunks via cosine similarity
    4. Build context from retrieved chunks
    5. Find or create session by IP + document
    6. Stream response from Ollama with context
    """
    client_ip = get_client_ip(req)
    user_agent = req.headers.get("User-Agent", "")[:512]
    
    logger.info(f"Chat request from IP: {client_ip}")
    
    # Validate document exists and is ready
    if request.document_id:
        document = db.query(Document).filter(Document.id == request.document_id).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if document.status != DocumentStatus.READY:
            raise HTTPException(
                status_code=400,
                detail=f"Document is not ready. Current status: {document.status.value}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="document_id is required for chat"
        )
    
    try:
        # Build early chat history for query rewriting
        early_history = []
        if request.session_id:
            existing_msgs = db.query(ChatMessage).filter(
                ChatMessage.session_id == request.session_id
            ).order_by(ChatMessage.created_at).all()
            early_history = [{"role": m.role, "content": m.content} for m in existing_msgs]
        
        # Rewrite query for better retrieval
        search_query = await rewrite_query(request.message, early_history)
        
        # Generate embedding for rewritten search query
        query_embedding = await rag_pipeline.generate_embedding(search_query)
        
        if not query_embedding:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate query embedding"
            )
        
        # Retrieve similar chunks
        similar_chunks = retrieval_service.search_similar_chunks(
            db=db,
            query_embedding=query_embedding,
            document_id=request.document_id,
            top_k=settings.top_k_chunks
        )
        
        # Debug: log retrieved chunks (only visible at DEBUG level)
        logger.debug(f"Retrieved {len(similar_chunks)} chunks for query: '{request.message[:80]}'")
        for i, chunk in enumerate(similar_chunks):
            logger.debug(f"  Chunk {i+1}: page={chunk.get('page_number', '?')}, score={chunk.get('score', 0):.4f}")
        
        # Build context from chunks
        context = retrieval_service.build_context(similar_chunks)
        
        # Log context length
        logger.info(f"Built context length: {len(context)} chars")
        
        if not context:
            context = "No relevant context found in the document."
        
        # Get or create chat session by IP + document
        session = None
        
        # If session_id is provided, try to find it
        if request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == request.session_id
            ).first()
        
        # If no session found, look for existing session by IP + document
        if not session:
            session = db.query(ChatSession).filter(
                ChatSession.ip_address == client_ip,
                ChatSession.document_id == request.document_id
            ).order_by(ChatSession.updated_at.desc()).first()
        
        # If still no session, create a new one
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
            logger.info(f"Created new session {session.id} for IP {client_ip}")
        else:
            # Update session metadata on reuse
            session.updated_at = datetime.utcnow()
            if user_agent:
                session.user_agent = user_agent
            db.commit()
            logger.info(f"Reusing session {session.id} for IP {client_ip}")
        
        # Save user message with IP
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=request.message,
            ip_address=client_ip
        )
        db.add(user_message)
        db.commit()
        
        # Prepare sources for response header
        sources = retrieval_service.format_sources(similar_chunks)
        
        # Get chat history for memory (compressed to save context budget)
        existing_messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).all()
        
        raw_history = [{"role": m.role, "content": m.content} for m in existing_messages[:-1]]
        chat_history = prepare_chat_history(raw_history)
        
        # Return streaming response
        return StreamingResponse(
            generate_stream(request.message, context, chat_history),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-Id": str(session.id),
                "X-Sources": json.dumps(sources)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    document_id: int = None,
    ip_address: str = None,
    db: Session = Depends(get_db)
):
    """List chat sessions, optionally filtered by document and/or IP address."""
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
    """Get a chat session with all messages."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session


@router.get("/chat/my-sessions", response_model=list[ChatSessionResponse])
async def get_my_sessions(
    req: Request,
    document_id: int = None,
    db: Session = Depends(get_db)
):
    """Get all chat sessions for the current user (identified by IP)."""
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
    """Save assistant response after streaming completes."""
    client_ip = get_client_ip(req)
    
    session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Save assistant message with IP
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=request.content,
        ip_address=client_ip
    )
    db.add(assistant_message)
    
    # Update session timestamp
    session.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "saved"}

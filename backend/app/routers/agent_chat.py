import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import run_agent
from app.agent.ollama_client import ollama_chat
from app.agent.tools import DocumentToolbox
from app.config import get_settings
from app.database import get_db
from app.models import Document, DocumentStatus

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


# схемы
class AgentChatRequest(BaseModel):
    question: str
    document_id: Optional[int] = None
    session_id: Optional[str] = None


class AgentStepOut(BaseModel):
    tool: str
    arguments: dict
    error: Optional[str] = None


class AgentChatResponse(BaseModel):
    text: str
    sources: List[dict] = []
    documents_used: int = 0
    steps: List[AgentStepOut] = []


# чат с агентом
@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(req: AgentChatRequest, db: Session = Depends(get_db)):
    # агент сам выбирает инструменты: поиск, пересказ, сравнение, извлечение фактов
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Пустой вопрос")

    if req.document_id:
        doc = db.query(Document).filter(Document.id == req.document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Документ {req.document_id} не найден")
        if doc.status != DocumentStatus.READY:
            raise HTTPException(status_code=400, detail=f"Документ не готов ({doc.status.value})")

    logger.info(f"Agent: '{question[:80]}', doc_id={req.document_id}")

    toolbox = DocumentToolbox(db=db, llm=ollama_chat)
    try:
        result = await run_agent(
            question=question,
            chat=lambda messages, tools: ollama_chat(messages, tools=tools),
            toolbox=toolbox,
            max_iterations=settings.agent_max_iterations,
            document_id=req.document_id,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM timeout")
    except httpx.HTTPError as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

    logger.info(
        f"Agent done: {len(result.steps)} tool calls, {len(result.sources)} sources, "
        f"limit={result.stopped_by_limit}"
    )

    return AgentChatResponse(
        text=result.text or "Не удалось сгенерировать ответ.",
        sources=result.sources[:10],
        documents_used=len({s["document"] for s in result.sources}),
        steps=[AgentStepOut(tool=s.tool, arguments=s.arguments, error=s.error) for s in result.steps],
    )

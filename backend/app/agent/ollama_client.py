from typing import Any, List, Optional

import httpx

from app.config import get_settings

settings = get_settings()


async def ollama_chat(
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    format: Optional[Any] = None,
    timeout: float = 180.0,
) -> dict:
    # один запрос к /api/chat без стриминга, возвращает message ассистента
    body: dict = {
        "model": settings.agent_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": settings.chat_num_ctx},
    }
    if tools:
        body["tools"] = tools
    if format is not None:
        # json schema для структурированного ответа
        body["format"] = format

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=body)
        resp.raise_for_status()
        return resp.json().get("message", {})

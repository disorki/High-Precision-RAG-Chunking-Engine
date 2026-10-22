import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

# функция чата с llm: (messages, tools) -> message ответа ассистента
ChatFn = Callable[[List[dict], List[dict]], Awaitable[dict]]


@dataclass
class ToolResult:
    # результат инструмента: текст для модели и найденные источники
    content: str
    sources: List[dict] = field(default_factory=list)


class Toolbox(Protocol):
    def schemas(self) -> List[dict]: ...

    async def call(self, name: str, arguments: Dict[str, Any]) -> ToolResult: ...


@dataclass
class AgentStep:
    tool: str
    arguments: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class AgentResult:
    text: str
    steps: List[AgentStep]
    sources: List[dict]
    stopped_by_limit: bool = False


SYSTEM_PROMPT = """Ты — ассистент для работы с базой документов пользователя.
У тебя есть инструменты для поиска и анализа документов. Порядок работы:
1. Если не знаешь, какие документы есть, вызови list_documents.
2. Ищи факты инструментами search_all или search_document. Для сложного вопроса делай несколько поисков с разными формулировками.
3. Для обзора документа используй summarize, для сравнения — compare_documents, для точных данных (даты, суммы, сроки) — extract_facts.
4. Когда данных достаточно, ответь без вызова инструментов.

Правила ответа:
- Используй только то, что вернули инструменты. Ничего не придумывай.
- После каждого утверждения указывай источник: (Документ, стр. N).
- Если в документах нет ответа, скажи об этом прямо."""

LIMIT_PROMPT = (
    "Лимит вызовов инструментов исчерпан. Ответь на вопрос пользователя "
    "по уже собранным данным, без вызова инструментов."
)


def _parse_arguments(raw: Any) -> Dict[str, Any]:
    # ollama отдаёт аргументы объектом, openai-совместимые api — строкой json
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("arguments must be a JSON object")
    return {}


def _dedupe_sources(sources: List[dict]) -> List[dict]:
    seen = set()
    unique = []
    for s in sources:
        key = s.get("chunk_id")
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


async def run_agent(
    question: str,
    chat: ChatFn,
    toolbox: Toolbox,
    max_iterations: int = 8,
    document_id: Optional[int] = None,
) -> AgentResult:
    # цикл агента: модель вызывает инструменты, пока не даст финальный ответ
    user_content = question
    if document_id is not None:
        user_content += f"\n\n(Пользователь выбрал документ с id={document_id}, ищи в первую очередь в нём.)"

    messages: List[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    tools = toolbox.schemas()
    steps: List[AgentStep] = []
    sources: List[dict] = []

    for _ in range(max_iterations):
        reply = await chat(messages, tools)
        tool_calls = reply.get("tool_calls") or []
        messages.append({
            "role": "assistant",
            "content": reply.get("content", ""),
            "tool_calls": tool_calls,
        })

        if not tool_calls:
            return AgentResult(
                text=reply.get("content", "").strip(),
                steps=steps,
                sources=_dedupe_sources(sources),
            )

        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                args = _parse_arguments(fn.get("arguments"))
                result = await toolbox.call(name, args)
                steps.append(AgentStep(tool=name, arguments=args))
                sources.extend(result.sources)
                content = result.content
            except Exception as e:
                # ошибку отдаём модели, чтобы она могла исправить вызов
                logger.warning(f"Tool {name} failed: {e}")
                steps.append(AgentStep(tool=name, arguments={}, error=str(e)))
                content = f"Ошибка инструмента {name}: {e}"
            messages.append({"role": "tool", "tool_name": name, "content": content})

    # лимит итераций: просим ответ без инструментов
    messages.append({"role": "user", "content": LIMIT_PROMPT})
    reply = await chat(messages, [])
    return AgentResult(
        text=reply.get("content", "").strip(),
        steps=steps,
        sources=_dedupe_sources(sources),
        stopped_by_limit=True,
    )

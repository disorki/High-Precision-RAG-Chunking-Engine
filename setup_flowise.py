"""
setup_flowise.py — Автоматическая настройка Flowise AI Agent

Запуск:
    python setup_flowise.py

Что делает:
    1. Ждёт пока Flowise запустится
    2. Создаёт chatflow с Tool Agent + 7 инструментами
    3. Сохраняет CHATFLOW_ID в frontend/.env
"""

import json
import time
import sys
import os
import requests

# ── Настройки ─────────────────────────────────────────────────────────────────
FLOWISE_HOST    = os.getenv("FLOWISE_HOST",    "http://localhost:3001")
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "5pMcKPyW8H1tz7TpTtv8RsEgmhpvKko_x70kwHy0K6I")
BACKEND_HOST    = os.getenv("BACKEND_HOST",    "http://backend:8000")      # внутри Docker
OLLAMA_HOST     = os.getenv("OLLAMA_HOST",     "http://ollama:11434")       # внутри Docker
FRONTEND_ENV    = os.path.join(os.path.dirname(__file__), "frontend", ".env")
CHATFLOW_NAME   = "University RAG Agent"

# ── Системный промпт агента ────────────────────────────────────────────────────
SYSTEM_PROMPT = """Ты — умный AI-ассистент для работы с документами университета.
Твоя задача — помогать преподавателям и сотрудникам быстро находить нужную информацию без полного прочтения документов.

ПРАВИЛА:
1. Всегда отвечай на языке пользователя (русский или английский).
2. Для получения информации ВСЕГДА используй инструменты — не придумывай данные.
3. Если вопрос сложный — раздели его на подзадачи и выполняй по шагам.
4. При первом вопросе о документах используй list_documents чтобы узнать что есть в базе.
5. Для сравнения документов используй compare_documents.
6. Всегда указывай источник: название документа и номер страницы.
7. Если информации недостаточно — честно скажи об этом и предложи уточнить.

ФОРМАТ ОТВЕТА:
- Конкретный, структурированный ответ
- Ссылки на источники [Документ: имя, Стр. X]
- Таблицы Markdown для сравнений и списков"""


def wait_for_flowise(timeout: int = 120):
    """Ждём пока Flowise поднимется."""
    print(f"⏳ Ожидаем Flowise на {FLOWISE_HOST} ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{FLOWISE_HOST}/api/v1/ping", timeout=3)
            if r.status_code == 200:
                print("✅ Flowise доступен!")
                return True
        except requests.ConnectionError:
            pass
        time.sleep(3)
    print("❌ Flowise не запустился за отведённое время.")
    return False


def get_headers() -> dict:
    """Заголовки с API-ключом для Flowise v2."""
    return {
        "Content-Type": "application/json",
        "x-api-key": FLOWISE_API_KEY,
    }


def build_flowdata() -> str:
    """
    Строим граф Flowise chatflow из нод и рёбер.
    Все координаты расположены для удобного просмотра в UI.
    """

    # ── Вспомогательная функция позиции ──────────────────────────────────────
    def pos(x, y):
        return {"x": x, "y": y}

    # ─── НОДА 1: Ollama LLM ───────────────────────────────────────────────────
    ollama_node = {
        "id": "ollamaChatModel_0",
        "position": pos(100, 200),
        "type": "customNode",
        "data": {
            "id": "ollamaChatModel_0",
            "label": "ChatOllama",
            "name": "chatOllama",
            "type": "ChatOllama",
            "category": "Chat Models",
            "description": "Local LLM via Ollama",
            "inputParams": [
                {"label": "Base URL", "name": "baseUrl", "type": "string"},
                {"label": "Model Name", "name": "modelName", "type": "string"},
                {"label": "Temperature", "name": "temperature", "type": "number"},
            ],
            "inputAnchors": [],
            "inputs": {
                "baseUrl": OLLAMA_HOST,
                "modelName": "qwen2.5:7b",
                "temperature": 0.2,
                "numCtx": 8192,
            },
            "outputs": {},
            "selected": False,
        },
    }

    # ─── НОДА 2: Buffer Memory ────────────────────────────────────────────────
    memory_node = {
        "id": "bufferMemory_0",
        "position": pos(100, 500),
        "type": "customNode",
        "data": {
            "id": "bufferMemory_0",
            "label": "Buffer Memory",
            "name": "bufferMemory",
            "type": "BufferMemory",
            "category": "Memory",
            "description": "Conversation history",
            "inputParams": [
                {"label": "Memory Key", "name": "memoryKey", "type": "string"},
                {"label": "Window Size", "name": "k", "type": "number"},
            ],
            "inputAnchors": [],
            "inputs": {
                "memoryKey": "chat_history",
                "k": 15,
            },
            "outputs": {},
            "selected": False,
        },
    }

    # ─── ИНСТРУМЕНТЫ ─────────────────────────────────────────────────────────
    tools_config = [
        {
            "id": "tool_search_all",
            "x": 100, "y": 800,
            "name": "search_all_documents",
            "description": "Semantic search across ALL documents in the knowledge base. Use this for general questions not tied to a specific document. Input: {\"query\": \"your search query\"}",
            "url": f"{BACKEND_HOST}/api/agent-tools/search",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": "{\"query\": \"{{query}}\", \"top_k\": 8}",
        },
        {
            "id": "tool_list_docs",
            "x": 400, "y": 800,
            "name": "list_documents",
            "description": "Get the complete list of all documents in the knowledge base with their IDs, names, status, and page counts. Always call this first when user asks what documents are available.",
            "url": f"{BACKEND_HOST}/api/agent-tools/documents",
            "method": "GET",
            "headers": {},
            "body": "",
        },
        {
            "id": "tool_summarize",
            "x": 700, "y": 800,
            "name": "summarize_document",
            "description": "Generate an AI summary of a specific document. Use when user asks 'what is this document about' or 'give me an overview of document X'. Input: document_id (integer)",
            "url": f"{BACKEND_HOST}/api/agent-tools/documents/{{{{document_id}}}}/summarize",
            "method": "GET",
            "headers": {},
            "body": "",
        },
        {
            "id": "tool_get_info",
            "x": 1000, "y": 800,
            "name": "get_document_info",
            "description": "Get metadata and a preview of a specific document (first few chunks). Use before deep search to understand what a document contains. Input: document_id (integer)",
            "url": f"{BACKEND_HOST}/api/agent-tools/documents/{{{{document_id}}}}",
            "method": "GET",
            "headers": {},
            "body": "",
        },
        {
            "id": "tool_search_doc",
            "x": 1300, "y": 800,
            "name": "search_in_document",
            "description": "Search for information within a SPECIFIC document only. Use when user specifies which document to search or when you know which document contains the answer. Input: {\"query\": \"search text\", \"document_id\": 1}",
            "url": f"{BACKEND_HOST}/api/agent-tools/search/{{{{document_id}}}}",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": "{\"query\": \"{{query}}\", \"top_k\": 6}",
        },
        {
            "id": "tool_compare",
            "x": 1600, "y": 800,
            "name": "compare_documents",
            "description": "Compare multiple documents on a specific topic. Use when user asks to compare, contrast, or find differences between documents. Input: {\"query\": \"what to compare\", \"document_ids\": [1, 2, 3]}",
            "url": f"{BACKEND_HOST}/api/agent-tools/compare",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": "{\"query\": \"{{query}}\", \"document_ids\": {{document_ids}}}",
        },
        {
            "id": "tool_extract",
            "x": 1900, "y": 800,
            "name": "extract_facts",
            "description": "Extract specific facts, numbers, names, dates, or data points from documents. Use for precise data extraction like 'find all deadlines', 'list all professors mentioned', 'what is the budget'. Input: {\"query\": \"fact to extract\", \"document_id\": null for all}",
            "url": f"{BACKEND_HOST}/api/agent-tools/extract",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": "{\"query\": \"{{query}}\", \"document_id\": {{document_id}}}",
        },
    ]

    def make_tool_node(cfg):
        return {
            "id": cfg["id"],
            "position": pos(cfg["x"], cfg["y"]),
            "type": "customNode",
            "data": {
                "id": cfg["id"],
                "label": "Custom Tool",
                "name": "customTool",
                "type": "Tool",
                "category": "Tools",
                "description": "Custom HTTP API Tool",
                "inputParams": [
                    {"label": "Tool Name", "name": "name", "type": "string"},
                    {"label": "Tool Description", "name": "description", "type": "string"},
                    {"label": "URL", "name": "url", "type": "string"},
                    {"label": "HTTP Method", "name": "method", "type": "string"},
                ],
                "inputAnchors": [],
                "inputs": {
                    "name": cfg["name"],
                    "description": cfg["description"],
                    "url": cfg["url"],
                    "method": cfg["method"],
                    "headers": json.dumps(cfg["headers"]) if cfg["headers"] else "{}",
                    "body": cfg["body"],
                },
                "outputs": {},
                "selected": False,
            },
        }

    tool_nodes = [make_tool_node(cfg) for cfg in tools_config]

    # ─── Tool Agent ───────────────────────────────────────────────────────────
    agent_node = {
        "id": "toolAgent_0",
        "position": pos(1000, 300),
        "type": "customNode",
        "data": {
            "id": "toolAgent_0",
            "label": "Tool Agent",
            "name": "toolAgent",
            "type": "AgentExecutor",
            "category": "Agents",
            "description": "ReAct agent with tool use",
            "inputParams": [
                {"label": "System Message", "name": "systemMessage", "type": "string"},
                {"label": "Max Iterations", "name": "maxIterations", "type": "number"},
            ],
            "inputAnchors": [
                {"label": "Tools", "name": "tools", "type": "Tool", "list": True},
                {"label": "Language Model", "name": "model", "type": "BaseChatModel"},
                {"label": "Memory", "name": "memory", "type": "BaseMemory"},
            ],
            "inputs": {
                "model": "{{ollamaChatModel_0.data.instance}}",
                "memory": "{{bufferMemory_0.data.instance}}",
                "tools": [f"{{{{{cfg['id']}.data.instance}}}}" for cfg in tools_config],
                "systemMessage": SYSTEM_PROMPT,
                "maxIterations": 8,
                "returnIntermediateSteps": True,
                "verbose": True,
            },
            "outputs": {},
            "selected": False,
        },
    }

    # ─── Edges ────────────────────────────────────────────────────────────────
    edges = [
        {"id": "e-ollama-agent",  "source": "ollamaChatModel_0", "target": "toolAgent_0", "sourceHandle": "ollamaChatModel_0-output-model-ChatOllama",  "targetHandle": "toolAgent_0-input-model-BaseChatModel"},
        {"id": "e-memory-agent",  "source": "bufferMemory_0",    "target": "toolAgent_0", "sourceHandle": "bufferMemory_0-output-memory-BufferMemory",    "targetHandle": "toolAgent_0-input-memory-BaseMemory"},
    ]
    for cfg in tools_config:
        edges.append({
            "id": f"e-{cfg['id']}-agent",
            "source": cfg["id"],
            "target": "toolAgent_0",
            "sourceHandle": f"{cfg['id']}-output-tool-Tool",
            "targetHandle": "toolAgent_0-input-tools-Tool",
        })

    nodes = [ollama_node, memory_node, agent_node] + tool_nodes
    graph = {"nodes": nodes, "edges": edges}
    return json.dumps(graph)


def create_chatflow() -> str | None:
    """POST /api/v1/chatflows — создаём chatflow, возвращаем ID."""
    print("🔨 Создаём chatflow ...")
    flow_data = build_flowdata()
    payload = {
        "name": CHATFLOW_NAME,
        "flowData": flow_data,
        "deployed": True,
        "isPublic": True,
        "chatbotConfig": json.dumps({
            "welcomeMessage": "Привет! Я AI-ассистент университета. Задайте любой вопрос о документах.",
            "botMessage": {"backgroundColor": "#f7f8ff", "textColor": "#1e1e2e"},
            "userMessage": {"backgroundColor": "#6366f1", "textColor": "#ffffff"},
            "textInput": {"placeholder": "Задайте вопрос о документах..."},
        }),
    }
    try:
        r = requests.post(
            f"{FLOWISE_HOST}/api/v1/chatflows",
            json=payload,
            headers=get_headers(),
            timeout=30,
        )
        r.raise_for_status()
        chatflow = r.json()
        chatflow_id = chatflow.get("id")
        print(f"✅ Chatflow создан! ID: {chatflow_id}")
        return chatflow_id
    except requests.HTTPError as e:
        print(f"❌ Ошибка создания chatflow: {e.response.status_code} — {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return None


def save_to_frontend_env(chatflow_id: str):
    """Дописываем CHATFLOW_ID в frontend/.env."""
    lines = []

    if os.path.exists(FRONTEND_ENV):
        with open(FRONTEND_ENV, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Удаляем старые значения если есть
    lines = [l for l in lines if not l.startswith("NEXT_PUBLIC_FLOWISE_CHATFLOW_ID=") and not l.startswith("NEXT_PUBLIC_FLOWISE_HOST=")]

    lines.append(f"NEXT_PUBLIC_FLOWISE_CHATFLOW_ID={chatflow_id}\n")
    lines.append(f"NEXT_PUBLIC_FLOWISE_HOST=http://localhost:3001\n")

    with open(FRONTEND_ENV, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"✅ Chatflow ID записан в {FRONTEND_ENV}")


def check_existing_chatflow() -> str | None:
    """Проверяем не создан ли уже chatflow с таким именем."""
    try:
        r = requests.get(f"{FLOWISE_HOST}/api/v1/chatflows", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            for flow in r.json():
                if flow.get("name") == CHATFLOW_NAME:
                    print(f"ℹ️  Chatflow '{CHATFLOW_NAME}' уже существует. ID: {flow['id']}")
                    return flow["id"]
    except Exception:
        pass
    return None


def main():
    print("=" * 55)
    print("  🤖 Flowise University RAG Agent — Auto Setup")
    print("=" * 55)

    # 1. Ждём Flowise
    if not wait_for_flowise():
        print("\n💡 Убедитесь что контейнеры запущены:")
        print("   docker-compose up -d flowise")
        sys.exit(1)

    # 2. Проверяем нет ли уже chatflow
    chatflow_id = check_existing_chatflow()

    # 3. Создаём если нет
    if not chatflow_id:
        chatflow_id = create_chatflow()

    if not chatflow_id:
        print("\n❌ Не удалось создать chatflow. Проверьте логи Flowise.")
        sys.exit(1)

    # 4. Сохраняем в .env
    save_to_frontend_env(chatflow_id)

    # 5. Итог
    print()
    print("=" * 55)
    print("  ✅ Настройка завершена!")
    print("=" * 55)
    print(f"  Flowise UI:  {FLOWISE_HOST}")
    print(f"  Chatflow ID: {chatflow_id}")
    print(f"  Agent URL:   {FLOWISE_HOST}/chatbot/{chatflow_id}")
    print()
    print("  Следующий шаг — перезапустить фронтенд:")
    print("  docker-compose restart frontend")
    print("=" * 55)


if __name__ == "__main__":
    main()

import json
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.loop import ToolResult
from app.config import get_settings
from app.models import Document, DocumentChunk, DocumentStatus
from app.services import rag_pipeline, retrieval_service

settings = get_settings()

SEARCH_TOP_K = 8
SNIPPET_CHARS = 800
SUMMARY_CHARS = 12000

# схема структурированного ответа для extract_facts
FACTS_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string"},
                    "value": {"type": "string"},
                    "page": {"type": "integer"},
                },
                "required": ["fact", "value", "page"],
            },
        }
    },
    "required": ["facts"],
}


def _fn(name: str, description: str, properties: dict, required: List[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_QUERY = {"type": "string", "description": "Поисковый запрос своими словами"}
_DOC_ID = {"type": "integer", "description": "id документа из list_documents"}

SCHEMAS = [
    _fn("search_all", "Семантический поиск по всем документам базы.", {"query": _QUERY}, ["query"]),
    _fn("search_document", "Семантический поиск внутри одного документа.",
        {"document_id": _DOC_ID, "query": _QUERY}, ["document_id", "query"]),
    _fn("list_documents", "Список готовых документов: id, имя файла, число страниц.", {}, []),
    _fn("get_document_info", "Метаданные документа: имя, страницы, число чанков, статус, дата загрузки.",
        {"document_id": _DOC_ID}, ["document_id"]),
    _fn("summarize", "Краткое содержание документа или его части по теме.",
        {"document_id": _DOC_ID, "focus": {"type": "string", "description": "Необязательная тема для фокуса"}},
        ["document_id"]),
    _fn("compare_documents", "Найти, что говорят несколько документов по одному аспекту, для сравнения.",
        {"document_ids": {"type": "array", "items": {"type": "integer"}, "description": "id документов"},
         "aspect": {"type": "string", "description": "Что сравнивать"}},
        ["document_ids", "aspect"]),
    _fn("extract_facts", "Извлечь точные факты (даты, суммы, сроки, названия) по запросу в виде списка.",
        {"query": _QUERY, "document_id": {"type": "integer", "description": "Необязательно: искать только в этом документе"}},
        ["query"]),
]

LLMFn = Callable[..., Awaitable[dict]]


def _source(chunk: dict) -> dict:
    return {
        "chunk_id": chunk.get("id"),
        "document": chunk.get("document_filename", ""),
        "page_number": chunk.get("page_number"),
        "score": round(chunk.get("score", 0) or 0, 3),
        "text": (chunk.get("text", "") or "")[:150] + "...",
    }


def _format_chunks(chunks: List[dict]) -> str:
    if not chunks:
        return "Ничего не найдено."
    return "\n\n".join(
        f"[{c.get('document_filename', '')} | стр. {c.get('page_number', '?')} | id={c.get('document_id')}]\n"
        f"{(c.get('text') or '')[:SNIPPET_CHARS]}"
        for c in chunks
    )


class DocumentToolbox:
    # инструменты агента поверх базы документов и векторного поиска
    def __init__(self, db: Session, llm: LLMFn):
        self.db = db
        self.llm = llm

    def schemas(self) -> List[dict]:
        return SCHEMAS

    async def call(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            raise ValueError(f"неизвестный инструмент: {name}")
        return await handler(**arguments)

    def _ready_document(self, document_id: int) -> Document:
        doc = self.db.query(Document).filter(Document.id == int(document_id)).first()
        if doc is None:
            raise ValueError(f"документ {document_id} не найден")
        if doc.status != DocumentStatus.READY:
            raise ValueError(f"документ {document_id} ещё не обработан ({doc.status.value})")
        return doc

    async def _search(self, query: str, document_id: Optional[int] = None) -> List[dict]:
        embedding = await rag_pipeline.generate_embedding(query)
        if not embedding:
            raise RuntimeError("не удалось получить эмбеддинг запроса")
        if document_id is not None:
            self._ready_document(document_id)
            return retrieval_service.search_similar_chunks(
                db=self.db, query_embedding=embedding, document_id=int(document_id),
                query_text=query, top_k=SEARCH_TOP_K,
            )
        return retrieval_service.search_all_documents(
            db=self.db, query_embedding=embedding, query_text=query, top_k=SEARCH_TOP_K,
        )

    async def _tool_search_all(self, query: str) -> ToolResult:
        chunks = await self._search(query)
        return ToolResult(_format_chunks(chunks), [_source(c) for c in chunks])

    async def _tool_search_document(self, document_id: int, query: str) -> ToolResult:
        chunks = await self._search(query, document_id)
        return ToolResult(_format_chunks(chunks), [_source(c) for c in chunks])

    async def _tool_list_documents(self) -> ToolResult:
        docs = (
            self.db.query(Document)
            .filter(Document.status == DocumentStatus.READY)
            .order_by(Document.id)
            .all()
        )
        if not docs:
            return ToolResult("В базе нет готовых документов.")
        lines = [f"id={d.id}: {d.original_filename} ({d.page_count or '?'} стр.)" for d in docs]
        return ToolResult("\n".join(lines))

    async def _tool_get_document_info(self, document_id: int) -> ToolResult:
        doc = self.db.query(Document).filter(Document.id == int(document_id)).first()
        if doc is None:
            raise ValueError(f"документ {document_id} не найден")
        info = {
            "id": doc.id,
            "filename": doc.original_filename,
            "status": doc.status.value,
            "pages": doc.page_count,
            "chunks": doc.chunk_count,
            "uploaded_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        return ToolResult(json.dumps(info, ensure_ascii=False))

    async def _tool_summarize(self, document_id: int, focus: Optional[str] = None) -> ToolResult:
        doc = self._ready_document(document_id)
        if focus:
            chunks = await self._search(focus, doc.id)
        else:
            rows = (
                self.db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index)
                .limit(settings.agent_summarize_chunks)
                .all()
            )
            chunks = [{
                "id": r.id, "document_id": doc.id, "document_filename": doc.original_filename,
                "text": r.text_content, "page_number": r.page_number, "score": 1.0,
            } for r in rows]
        if not chunks:
            return ToolResult("В документе нет текста для пересказа.")

        context = _format_chunks(chunks)[:SUMMARY_CHARS]
        task = f"Кратко перескажи фрагменты документа «{doc.original_filename}»"
        task += f" с фокусом на теме: {focus}." if focus else "."
        reply = await self.llm([
            {"role": "system", "content": "Пересказывай только то, что есть во фрагментах, с указанием страниц."},
            {"role": "user", "content": f"{task}\n\n{context}"},
        ])
        return ToolResult(reply.get("content", "").strip(), [_source(c) for c in chunks])

    async def _tool_compare_documents(self, document_ids: List[int], aspect: str) -> ToolResult:
        if len(document_ids) < 2:
            raise ValueError("для сравнения нужно минимум два документа")
        parts, sources = [], []
        for doc_id in document_ids:
            doc = self._ready_document(doc_id)
            chunks = (await self._search(aspect, doc.id))[:3]
            sources.extend(_source(c) for c in chunks)
            parts.append(f"### {doc.original_filename} (id={doc.id})\n{_format_chunks(chunks)}")
        return ToolResult("\n\n".join(parts), sources)

    async def _tool_extract_facts(self, query: str, document_id: Optional[int] = None) -> ToolResult:
        chunks = await self._search(query, document_id)
        if not chunks:
            return ToolResult(json.dumps({"facts": []}, ensure_ascii=False))
        reply = await self.llm(
            [
                {"role": "system", "content": "Извлекай только факты, которые явно есть во фрагментах. "
                                              "Номер страницы бери из заголовка фрагмента."},
                {"role": "user", "content": f"Запрос: {query}\n\n{_format_chunks(chunks)}"},
            ],
            format=FACTS_SCHEMA,
        )
        try:
            facts = json.loads(reply.get("content", "") or "{}").get("facts", [])
        except json.JSONDecodeError:
            facts = []
        return ToolResult(json.dumps({"facts": facts}, ensure_ascii=False), [_source(c) for c in chunks])

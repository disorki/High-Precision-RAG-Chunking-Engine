import asyncio
import inspect

import pytest

from app.agent.tools import SCHEMAS, DocumentToolbox

EXPECTED_TOOLS = {
    "search_all",
    "search_document",
    "list_documents",
    "get_document_info",
    "summarize",
    "compare_documents",
    "extract_facts",
}


def test_all_seven_tools_are_declared():
    assert {s["function"]["name"] for s in SCHEMAS} == EXPECTED_TOOLS


@pytest.mark.parametrize("schema", SCHEMAS, ids=lambda s: s["function"]["name"])
def test_schema_matches_handler_signature(schema):
    fn = schema["function"]
    handler = getattr(DocumentToolbox, f"_tool_{fn['name']}")
    params = inspect.signature(handler).parameters
    declared = set(fn["parameters"]["properties"])
    required = set(fn["parameters"]["required"])

    handler_args = {name for name in params if name != "self"}
    handler_required = {
        name for name, p in params.items()
        if name != "self" and p.default is inspect.Parameter.empty
    }
    assert declared == handler_args
    assert required == handler_required


def test_unknown_tool_is_rejected():
    toolbox = DocumentToolbox(db=None, llm=None)
    with pytest.raises(ValueError, match="неизвестный инструмент"):
        asyncio.run(toolbox.call("drop_database", {}))


def test_compare_needs_at_least_two_documents():
    toolbox = DocumentToolbox(db=None, llm=None)
    with pytest.raises(ValueError, match="минимум два"):
        asyncio.run(toolbox.call("compare_documents", {"document_ids": [1], "aspect": "цена"}))
